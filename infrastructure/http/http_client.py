"""HTTP client with retry logic and proxy rotation.

Uses curl_cffi for Chrome TLS fingerprint impersonation to avoid
Wildberries anti-bot detection.
"""
import asyncio
import random
import time
from typing import Optional, Dict
import httpx
from curl_cffi.requests import AsyncSession
from curl_cffi import CurlError
from core.config import config
from core.logger import logger
from infrastructure.http.proxy_pool import ProxyPool, Proxy
from observability.runtime import WB_REQUESTS_TOTAL, runtime_state


class HTTPClient:
    """HTTP client with connection pooling and proxy rotation."""

    def __init__(self):
        self._sessions: Dict[str, AsyncSession] = {}
        self.proxy_pool = ProxyPool(config.PROXY_LIST)

        if config.PROXY_LIST:
            stats = self.proxy_pool.get_stats()
            logger.info(
                f"Proxy pool initialized: {stats['total']} total, "
                f"{stats['active']} active proxies"
            )
        else:
            logger.info("No proxies configured, using direct connection")

        self._cb_state = "closed"
        self._cb_opened_at = 0.0
        self._cb_failure_count = 0
        self._cb_half_open_calls = 0

    def _is_retryable_status(self, status_code: int) -> bool:
        return status_code in {403, 408, 425, 429, 498} or status_code >= 500

    def _classify_error(self, exc: Exception) -> str:
        if isinstance(exc, httpx.HTTPStatusError):
            return str(exc.response.status_code)
        if isinstance(exc, (httpx.TimeoutException, asyncio.TimeoutError)):
            return "timeout"
        return "request_error"

    def _compute_backoff(self, attempt: int) -> float:
        base = config.WB_API_RETRY_BASE_DELAY
        max_delay = config.WB_API_RETRY_MAX_DELAY
        jitter = config.WB_API_RETRY_JITTER
        exp_delay = min(max_delay, base * (2 ** attempt))
        if jitter > 0:
            exp_delay += random.uniform(0, jitter)
        return min(max_delay + jitter, exp_delay)

    def _circuit_can_execute(self) -> bool:
        if self._cb_state != "open":
            return True
        elapsed = time.monotonic() - self._cb_opened_at
        if elapsed >= config.WB_API_CIRCUIT_BREAKER_RECOVERY_TIMEOUT:
            self._cb_state = "half_open"
            self._cb_half_open_calls = 0
            logger.warning("Circuit breaker moving to half-open state")
            return True
        return False

    def _circuit_on_success(self) -> None:
        if self._cb_state in {"open", "half_open"}:
            logger.info("Circuit breaker closed after successful trial request")
        self._cb_state = "closed"
        self._cb_opened_at = 0.0
        self._cb_failure_count = 0
        self._cb_half_open_calls = 0

    def _circuit_on_failure(self) -> None:
        self._cb_failure_count += 1
        if self._cb_state == "half_open":
            self._cb_state = "open"
            self._cb_opened_at = time.monotonic()
            self._cb_half_open_calls = 0
            logger.warning("Circuit breaker re-opened after half-open failure")
            return
        if self._cb_failure_count >= config.WB_API_CIRCUIT_BREAKER_FAILURE_THRESHOLD:
            self._cb_state = "open"
            self._cb_opened_at = time.monotonic()
            logger.error(
                f"Circuit breaker opened after {self._cb_failure_count} consecutive failures"
            )

    def _circuit_on_before_request(self) -> None:
        if self._cb_state == "half_open":
            self._cb_half_open_calls += 1

    def _circuit_after_half_open_success(self) -> None:
        if self._cb_state == "half_open":
            if self._cb_half_open_calls >= config.WB_API_CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS:
                self._circuit_on_success()

    async def _get_session(self, proxy: Optional[Proxy] = None) -> AsyncSession:
        proxy_key = proxy.url if proxy else "direct"

        if proxy_key not in self._sessions:
            proxy_url = proxy.to_httpx_proxy() if proxy else None
            self._sessions[proxy_key] = AsyncSession(
                impersonate="chrome",
                proxy=proxy_url,
                timeout=float(config.WB_API_TIMEOUT),
            )

        return self._sessions[proxy_key]

    async def _random_delay(self) -> None:
        delay = random.uniform(config.WB_REQUEST_DELAY_MIN, config.WB_REQUEST_DELAY_MAX)
        await asyncio.sleep(delay)

    async def get(
        self,
        url: str,
        params: Optional[dict] = None,
        retries: int = config.WB_API_RETRIES,
    ):
        """GET request with retry logic and proxy rotation.

        Returns a response with .status_code, .content, .text, .json().
        Raises httpx.HTTPStatusError on non-2xx (for compatibility).
        """
        if retries is None:
            retries = config.WB_API_RETRIES

        if not self._circuit_can_execute():
            retry_in = max(
                0.0,
                config.WB_API_CIRCUIT_BREAKER_RECOVERY_TIMEOUT
                - (time.monotonic() - self._cb_opened_at),
            )
            raise httpx.RequestError(
                f"Circuit breaker is open, retry in {retry_in:.1f}s"
            )

        self._circuit_on_before_request()
        await self._random_delay()
        last_exception: Exception | None = None
        tried_direct = not bool(config.PROXY_LIST)
        proxy_failures = 0

        for attempt in range(retries + 1):
            proxy = None if tried_direct else await self.proxy_pool.get_proxy()
            if proxy is None and config.PROXY_LIST:
                logger.warning("All proxies unavailable, waiting 5s before retry...")
                await asyncio.sleep(5)
                proxy = await self.proxy_pool.get_proxy(exclude_failed=False)
            if proxy is None and not config.PROXY_LIST:
                tried_direct = True

            session = await self._get_session(proxy)
            proxy_info = proxy.url if proxy else "direct connection"
            logger.debug(f"Request to {url} using {proxy_info} (attempt {attempt + 1})")

            try:
                response = await session.get(url, params=params)

                if response.status_code >= 400:
                    request = httpx.Request("GET", url)
                    httpx_response = httpx.Response(
                        status_code=response.status_code,
                        content=response.content,
                        request=request,
                    )
                    raise httpx.HTTPStatusError(
                        f"Client error '{response.status_code}' for url '{url}'",
                        request=request,
                        response=httpx_response,
                    )

                if proxy:
                    await self.proxy_pool.mark_success(proxy)
                self._circuit_after_half_open_success()
                if self._cb_state == "closed":
                    self._cb_failure_count = 0
                WB_REQUESTS_TOTAL.labels(result="success").inc()
                return response

            except httpx.HTTPStatusError as e:
                last_exception = e
                status = e.response.status_code
                retryable = self._is_retryable_status(status)
                WB_REQUESTS_TOTAL.labels(result="error").inc()
                runtime_state.inc_wb_error(str(status))

                if proxy:
                    await self.proxy_pool.mark_failure(proxy)
                    proxy_failures += 1

                logger.warning(
                    f"HTTP {status} on {proxy_info} (retryable={retryable})"
                )

                if status in {403, 498}:
                    pass  # rotate proxy, never go direct
                elif status == 429:
                    if not config.PROXY_LIST:
                        tried_direct = True

                if not retryable or attempt >= retries:
                    break

                delay = self._compute_backoff(attempt)
                logger.warning(f"Retrying in {delay:.2f}s")
                await asyncio.sleep(delay)

            except (CurlError, OSError, asyncio.TimeoutError) as e:
                last_exception = httpx.RequestError(str(e))
                WB_REQUESTS_TOTAL.labels(result="error").inc()
                runtime_state.inc_wb_error("request_error")

                if proxy:
                    await self.proxy_pool.mark_failure(proxy)
                    proxy_failures += 1

                logger.warning(f"Request error on {proxy_info}: {e}")

                if proxy_failures >= 3 and not config.PROXY_LIST:
                    tried_direct = True

                if attempt >= retries:
                    break

                delay = self._compute_backoff(attempt)
                logger.warning(f"Retrying in {delay:.2f}s")
                await asyncio.sleep(delay)

        self._circuit_on_failure()
        if last_exception is None:
            last_exception = httpx.RequestError("Unknown request failure")
        raise last_exception

    async def close(self) -> None:
        for session in self._sessions.values():
            await session.close()
        self._sessions.clear()


http_client = HTTPClient()

"""Proxy pool for request distribution."""
import asyncio
import random
from typing import List, Optional, Dict
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urlsplit
from core.config import config
from core.logger import logger


@dataclass
class Proxy:
    """Proxy configuration."""
    url: str
    username: Optional[str] = None
    password: Optional[str] = None
    last_used: Optional[datetime] = None
    failure_count: int = 0
    success_count: int = 0
    is_active: bool = True
    
    def to_httpx_proxy(self) -> str:
        """Convert to single proxy URL string.

        curl_cffi AsyncSession expects a string proxy URL (not a mapping).
        """
        proxy_url = self.url

        if self.username and self.password:
            # Preserve proxy scheme (http/socks5/etc) while injecting credentials.
            parts = urlsplit(self.url)
            proxy_url = (
                f"{parts.scheme}://{self.username}:{self.password}@"
                f"{parts.hostname}:{parts.port}"
            )
        return proxy_url


class ProxyPool:
    """Proxy pool with rotation and health checking."""
    
    def __init__(self, proxies: List[str]):
        """Initialize proxy pool.
        
        Args:
            proxies: List of proxy URLs (format: http://host:port or http://user:pass@host:port)
        """
        self.proxies: List[Proxy] = []
        self.current_index = 0
        self.lock = asyncio.Lock()
        
        # Parse proxy strings
        for proxy_str in proxies:
            proxy = self._parse_proxy(proxy_str)
            if proxy:
                self.proxies.append(proxy)
        
        if not self.proxies:
            logger.warning("No proxies configured, using direct connection")
        else:
            logger.info(f"Initialized proxy pool with {len(self.proxies)} proxies")
    
    def _parse_proxy(self, proxy_str: str) -> Optional[Proxy]:
        """Parse proxy string to Proxy object."""
        try:
            proxy_str = proxy_str.strip()
            if not proxy_str:
                return None

            # Expected formats:
            # - http://host:port
            # - http://user:pass@host:port
            # - socks5://host:port
            # - socks5://user:pass@host:port
            if "://" not in proxy_str:
                proxy_str = f"http://{proxy_str}"

            parts = urlsplit(proxy_str)
            if not parts.scheme or not parts.hostname or not parts.port:
                return None

            url = f"{parts.scheme}://{parts.hostname}:{parts.port}"
            return Proxy(url=url, username=parts.username, password=parts.password)
        except Exception as e:
            logger.error(f"Failed to parse proxy {proxy_str}: {e}")
            return None
    
    async def get_proxy(self, exclude_failed: bool = True) -> Optional[Proxy]:
        """Get next proxy using round-robin with health check.
        
        Args:
            exclude_failed: If True, skip proxies with too many failures
        
        Returns:
            Proxy object or None if no proxies available
        """
        if not self.proxies:
            return None
        
        async with self.lock:
            # Filter active proxies
            available = [
                p for p in self.proxies 
                if p.is_active and (not exclude_failed or p.failure_count < 5)
            ]
            
            if not available:
                # Reset all proxies if all are marked as failed
                logger.warning("All proxies failed, resetting failure counts")
                for p in self.proxies:
                    p.failure_count = 0
                    p.is_active = True
                available = self.proxies
            
            # Round-robin selection
            if available:
                proxy = available[self.current_index % len(available)]
                self.current_index = (self.current_index + 1) % len(available)
                proxy.last_used = datetime.utcnow()
                return proxy
        
        return None
    
    async def mark_success(self, proxy: Proxy) -> None:
        """Mark proxy as successful."""
        async with self.lock:
            proxy.success_count += 1
            proxy.failure_count = max(0, proxy.failure_count - 1)
    
    async def mark_failure(self, proxy: Proxy) -> None:
        """Mark proxy as failed."""
        async with self.lock:
            proxy.failure_count += 1
            if proxy.failure_count >= 10:
                proxy.is_active = False
                logger.warning(f"Proxy {proxy.url} marked as inactive after {proxy.failure_count} failures")
    
    def get_stats(self) -> Dict:
        """Get proxy pool statistics."""
        active = sum(1 for p in self.proxies if p.is_active)
        return {
            "total": len(self.proxies),
            "active": active,
            "failed": len(self.proxies) - active,
        }

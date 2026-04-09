"""Runtime observability state and Prometheus counters."""
from collections import defaultdict
from threading import Lock

from prometheus_client import Counter

# Generic WB request metric used by HTTP client.
WB_REQUESTS_TOTAL = Counter(
    "wb_requests_total",
    "Total WB HTTP requests grouped by result",
    ["result"],
)


class RuntimeState:
    """In-memory runtime counters for lightweight alerting/diagnostics."""

    def __init__(self) -> None:
        self._lock = Lock()
        self.wb_errors = defaultdict(int)

    def inc_wb_error(self, code: str) -> None:
        """Increment WB error bucket by status/error code."""
        with self._lock:
            self.wb_errors[str(code)] += 1


runtime_state = RuntimeState()


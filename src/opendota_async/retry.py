"""Application-level retry policy with exponential backoff, jitter, and time caps."""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import Any

_IDEMPOTENT = frozenset({"GET", "HEAD", "PUT", "DELETE", "OPTIONS"})
_RETRY_STATUSES = frozenset({429, 502, 503, 504})


def _parse_retry_after(response: Any) -> float | None:
    h = response.headers.get("Retry-After") or response.headers.get("retry-after")
    if not h:
        return None
    try:
        return float(h)
    except ValueError:
        return None


@dataclass(slots=True)
class RetryPolicy:
    """Retries for conditions not fully covered by transport-level urllib3 retries.

    Honors ``Retry-After`` when present. Caps wall-clock time via ``max_total_seconds``.
    """

    max_attempts: int = 5
    max_total_seconds: float = 60.0
    base_delay: float = 0.5
    max_delay: float = 30.0
    retry_post: bool = False
    jitter: bool = True

    def allows_method(self, method: str) -> bool:
        m = method.upper()
        if m in _IDEMPOTENT:
            return True
        return bool(m == "POST" and self.retry_post)

    def should_retry_status(self, status: int) -> bool:
        return status in _RETRY_STATUSES

    def should_retry_http(self, method: str, status: int) -> bool:
        """Whether an HTTP *status* on *method* should trigger an application retry."""
        if not self.should_retry_status(status):
            return False
        return not (method.upper() == "POST" and not self.retry_post)

    def next_delay(
        self,
        attempt: int,
        *,
        response: Any | None = None,
    ) -> float:
        if response is not None:
            ra = _parse_retry_after(response)
            if ra is not None:
                return min(ra, self.max_delay)
        exp = min(self.base_delay * (2 ** (attempt - 1)), self.max_delay)
        if self.jitter:
            return float(random.uniform(0, exp))
        return float(exp)


@dataclass
class RetryState:
    """Tracks deadline across attempts for one logical call."""

    deadline: float
    attempt: int = 0
    started: float = field(default_factory=time.monotonic)

    def expired(self) -> bool:
        return time.monotonic() >= self.deadline

    def remaining(self) -> float:
        return max(0.0, self.deadline - time.monotonic())


async def sleep_delay(seconds: float) -> None:
    await asyncio.sleep(seconds)

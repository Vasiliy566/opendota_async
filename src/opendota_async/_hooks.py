"""Niquests :class:`AsyncLifeCycleHook` subclasses (note spelling: LifeCycle, not Lifecycle)."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, cast

from niquests.hooks import AsyncLeakyBucketLimiter, AsyncLifeCycleHook

from opendota_async.auth import redact_headers

if TYPE_CHECKING:
    from niquests.models import PreparedRequest, Response

log = logging.getLogger("opendota_async.client")


class OpenDotaObservabilityHook(AsyncLifeCycleHook[Any]):
    """Structured request/response logging using ``conn_info`` timings when available."""

    def __init__(self, *, logger: logging.Logger | None = None) -> None:
        super().__init__()
        self._log = logger or log
        self._t0: float = 0.0

    async def pre_request(self, prepared_request: PreparedRequest, **kwargs: Any) -> Any:
        self._t0 = time.perf_counter()
        return None

    async def response(self, response: Response, **kwargs: Any) -> Any:
        elapsed_ms = (time.perf_counter() - self._t0) * 1000.0
        ci = getattr(response, "conn_info", None)
        dns_ms = tls_ms = None
        http_ver = getattr(response, "http_version", None)
        if ci is not None:
            dns_ms = getattr(ci, "dns_time", None)
            tls_ms = getattr(ci, "tls_time", None) or getattr(ci, "handshake_time", None)
            http_ver = getattr(ci, "protocol", None) or http_ver
        rid = response.headers.get("X-Request-Id") or response.headers.get("x-request-id")
        self._log.info(
            "http_request",
            extra={
                "method": getattr(response.request, "method", None),
                "url": str(response.url),
                "status": response.status_code,
                "http_version": http_ver,
                "duration_ms": round(elapsed_ms, 3),
                "dns_ms": dns_ms,
                "tls_ms": tls_ms,
                "request_id": rid,
            },
        )
        return None


class AdaptiveRateLimitHook(AsyncLifeCycleHook[Any]):
    """Tune leaky-bucket rate using ``X-RateLimit-Remaining`` / ``X-RateLimit-Reset``."""

    def __init__(self, limiter: AsyncLeakyBucketLimiter) -> None:
        super().__init__()
        self._limiter = limiter

    async def response(self, response: Response, **kwargs: Any) -> Any:
        rem = response.headers.get("X-RateLimit-Remaining") or response.headers.get(
            "x-ratelimit-remaining"
        )
        if rem is None:
            return None
        try:
            remaining = int(rem)
        except ValueError:
            return None
        if remaining <= 2:
            self._limiter.rate = max(0.1, self._limiter.rate * 0.5)
        elif remaining > 100:
            self._limiter.rate = min(200.0, self._limiter.rate * 1.1)
        return None


def build_async_hooks(
    *,
    rate_rps: float | None,
    observability_logger: logging.Logger | None = None,
) -> AsyncLifeCycleHook[Any] | None:
    """Combine transport limiter + observability + adaptive server hints."""
    parts: list[AsyncLifeCycleHook[Any]] = []
    limiter: AsyncLeakyBucketLimiter | None = None
    if rate_rps is not None and rate_rps > 0:
        limiter = AsyncLeakyBucketLimiter(rate=rate_rps)
        parts.append(limiter)
    parts.append(OpenDotaObservabilityHook(logger=observability_logger))
    if limiter is not None:
        parts.append(AdaptiveRateLimitHook(limiter))
    acc: Any = None
    for p in parts:
        acc = p if acc is None else acc + p
    return cast(AsyncLifeCycleHook[Any] | None, acc)


def debug_safe_headers(headers: Any) -> dict[str, str]:
    if headers is None:
        return {}
    try:
        raw = dict(headers)
    except Exception:
        return {}
    return redact_headers({str(k): str(v) for k, v in raw.items()})

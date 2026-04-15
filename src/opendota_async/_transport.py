"""Niquests ``AsyncSession`` / ``Session`` construction."""

from __future__ import annotations

from typing import Any, cast

from niquests import AsyncSession, Session

from opendota_async._hooks import build_async_hooks
from opendota_async.config import OpenDotaClientConfig

try:
    from urllib3_future.util.retry import Retry as Urllib3Retry
except ImportError:  # pragma: no cover
    Urllib3Retry = None  # type: ignore[misc, assignment]


def _transport_retries(config: OpenDotaClientConfig) -> Any:
    r = config.retries
    if isinstance(r, int) and Urllib3Retry is not None and r > 0:
        return Urllib3Retry(
            total=r,
            connect=r,
            read=r,
            status=r,
            backoff_factor=0.3,
            status_forcelist=(429, 502, 503, 504),
            allowed_methods=frozenset({"GET", "HEAD", "PUT", "DELETE", "OPTIONS", "TRACE"}),
            raise_on_status=False,
        )
    return r


def _default_headers_params(config: OpenDotaClientConfig) -> tuple[dict[str, str], dict[str, str]]:
    headers: dict[str, str] = {}
    params: dict[str, str] = {}
    if config.user_agent:
        headers["User-Agent"] = config.user_agent
    if config.auth is None:
        if config.bearer_token:
            headers["Authorization"] = f"Bearer {config.bearer_token}"
        elif config.api_key:
            params["api_key"] = config.api_key
    return headers, params


def create_async_session(config: OpenDotaClientConfig) -> AsyncSession:
    """Build a configured :class:`niquests.AsyncSession` (one per :class:`OpenDotaClient`)."""
    hooks = build_async_hooks(rate_rps=config.rate_limit_rps)
    headers, default_params = _default_headers_params(config)
    s = AsyncSession(
        base_url=config.base_url,
        timeout=config.timeout,
        pool_connections=config.pool_connections,
        pool_maxsize=config.pool_maxsize,
        retries=_transport_retries(config),
        multiplexed=config.multiplexed,
        disable_http2=config.disable_http2,
        disable_http3=config.disable_http3,
        happy_eyeballs=config.happy_eyeballs,
        keepalive_delay=config.keepalive_delay,
        keepalive_idle_window=config.keepalive_idle_window,
        headers=headers or None,
        auth=config.auth,
        hooks=hooks,
        revocation_configuration=config.revocation_configuration,
    )
    if default_params:
        cast(Any, s.params).update(default_params)
    s.verify = config.verify
    if config.proxies:
        s.proxies = config.proxies
    return s


def create_sync_session(config: OpenDotaClientConfig) -> Session:
    """Sync :class:`niquests.Session` mirroring async settings (no ``Async*`` auth)."""
    from niquests.hooks import LeakyBucketLimiter

    hooks = None
    if config.rate_limit_rps is not None and config.rate_limit_rps > 0:
        hooks = LeakyBucketLimiter(rate=config.rate_limit_rps)
    headers, default_params = _default_headers_params(config)
    s = Session(
        base_url=config.base_url,
        timeout=config.timeout,
        pool_connections=config.pool_connections,
        pool_maxsize=config.pool_maxsize,
        retries=_transport_retries(config),
        multiplexed=config.multiplexed,
        disable_http2=config.disable_http2,
        disable_http3=config.disable_http3,
        happy_eyeballs=config.happy_eyeballs,
        keepalive_delay=config.keepalive_delay,
        keepalive_idle_window=config.keepalive_idle_window,
        headers=headers or None,
        auth=config.auth,
        hooks=hooks,
        revocation_configuration=config.revocation_configuration,
    )
    if default_params:
        cast(Any, s.params).update(default_params)
    s.verify = config.verify
    if config.proxies:
        s.proxies = config.proxies
    return s

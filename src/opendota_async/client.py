"""Async OpenDota API client."""

from __future__ import annotations

import asyncio
import contextvars
import json
import time
from collections.abc import Callable, Mapping
from typing import Any, TypeVar

import niquests
from niquests import AsyncSession
from pydantic import BaseModel

from opendota_async._compat import async_read_body
from opendota_async._parse import parse_json_model
from opendota_async._transport import create_async_session
from opendota_async.config import OpenDotaClientConfig
from opendota_async.errors import (
    APIError,
    OpenDotaError,
    map_http_error,
    wrap_niquests_connection,
)
from opendota_async.errors import (
    ValidationError as ResponseValidationError,
)
from opendota_async.resources.players import PlayersResource
from opendota_async.retry import RetryPolicy, RetryState, sleep_delay

T = TypeVar("T", bound=BaseModel)

_last_response_var: contextvars.ContextVar[niquests.Response | None] = contextvars.ContextVar(
    "opendota_last_raw_response",
    default=None,
)


class OpenDotaClient:
    """High-level async client with retries, typing, and optional HTTP/2 multiplexing.

    Use ``async with OpenDotaClient(...) as client:`` or call :meth:`aclose` when done.
    Do not share one client across different event loops; create one client per loop.

    Args:
        config: Fully constructed configuration (optional if keyword args are passed).
        session_factory: Inject a custom :class:`niquests.AsyncSession` builder for tests.
        retry_policy: Application-level retry policy (transport retries are separate).

    Example:
        >>> async def main():
        ...     async with OpenDotaClient(api_key="...") as c:
        ...         p = await c.players.get(123)
    """

    def __init__(
        self,
        config: OpenDotaClientConfig | None = None,
        *,
        session_factory: Callable[[OpenDotaClientConfig], AsyncSession] | None = None,
        retry_policy: RetryPolicy | None = None,
        **kwargs: Any,
    ) -> None:
        self._config = config or OpenDotaClientConfig(**kwargs)
        self._session_factory = session_factory or create_async_session
        self._retry_policy = retry_policy or RetryPolicy(
            max_attempts=self._config.retry_max_attempts,
            max_total_seconds=self._config.retry_max_total_seconds,
            retry_post=self._config.retry_post,
        )
        self._session: AsyncSession | None = None
        self._closed = False
        self._sem = asyncio.Semaphore(self._config.max_concurrency)
        self._mpx_lock = asyncio.Lock()
        self.players = PlayersResource(self)

    @property
    def last_raw_response(self) -> niquests.Response | None:
        """Last Niquests response for this async task (safe under concurrent tasks)."""
        return _last_response_var.get()

    @property
    def config(self) -> OpenDotaClientConfig:
        return self._config

    @property
    def session(self) -> AsyncSession:
        if self._closed:
            raise OpenDotaError("Client is closed")
        if self._session is None:
            self._session = self._session_factory(self._config)
        return self._session

    async def aclose(self) -> None:
        """Close the underlying Niquests session. Idempotent."""
        if self._closed:
            return
        self._closed = True
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def __aenter__(self) -> OpenDotaClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def request(
        self,
        method: str,
        path: str,
        *,
        response_model: type[Any] | None = None,
        params: Mapping[str, Any] | None = None,
        json_body: Any = None,
        headers: Mapping[str, str] | None = None,
        timeout: Any = None,
        stream: bool = False,
    ) -> Any:
        """Send an HTTP request and optionally validate JSON against a Pydantic model.

        Args:
            method: HTTP verb.
            path: Path relative to ``base_url``.
            response_model: Pydantic model class, or ``list[Model]`` for JSON arrays.
            params: Query parameters merged with session defaults.
            json_body: JSON body for ``POST``/``PUT``.
            headers: Extra headers.
            timeout: Per-request timeout override.
            stream: If True, returns the raw response after checking status (read body yourself).

        Returns:
            Validated model instance, raw dict/list, or streaming response.

        Raises:
            opendota_async.errors.OpenDotaError: On transport, HTTP, or validation errors.
        """
        m = method.upper()
        state = RetryState(deadline=time.monotonic() + self._retry_policy.max_total_seconds)
        last_exc: Exception | None = None

        async with self._sem:
            while True:
                state.attempt += 1
                if state.expired():
                    if last_exc:
                        raise wrap_niquests_connection(last_exc) from last_exc
                    raise OpenDotaError("Retry budget exhausted")

                try:
                    kw: dict[str, Any] = {}
                    if timeout is not None:
                        kw["timeout"] = timeout
                    if headers is not None:
                        kw["headers"] = dict(headers)
                    if stream:
                        kw["stream"] = True

                    r = await self.session.request(
                        m,
                        path,
                        params=dict(params) if params else None,
                        json=json_body,
                        **kw,
                    )
                    _last_response_var.set(r)

                    if stream:
                        if r.status_code >= 400:
                            err_body = await async_read_body(r)
                            raise map_http_error(r, err_body)
                        return r

                    body_bytes = await async_read_body(r)
                    if r.status_code >= 400:
                        if (
                            self._retry_policy.should_retry_http(m, r.status_code)
                            and state.attempt < self._retry_policy.max_attempts
                        ):
                            delay = self._retry_policy.next_delay(state.attempt, response=r)
                            if state.remaining() < delay:
                                raise map_http_error(r, body_bytes)
                            await sleep_delay(delay)
                            continue
                        raise map_http_error(r, body_bytes)

                    if not body_bytes:
                        parsed: Any = None
                    else:
                        try:
                            parsed = json.loads(body_bytes.decode("utf-8"))
                        except json.JSONDecodeError as e:
                            raise ResponseValidationError("Invalid JSON body") from e

                    try:
                        return parse_json_model(parsed, response_model)
                    except Exception as e:
                        raise ResponseValidationError(str(e)) from e

                except APIError:
                    raise
                except OpenDotaError:
                    raise
                except ResponseValidationError:
                    raise
                except Exception as e:
                    import niquests.exceptions as ne

                    transient = (
                        ne.ConnectionError,
                        ne.Timeout,
                        ne.ConnectTimeout,
                        ne.ReadTimeout,
                    )
                    if isinstance(e, transient):
                        last_exc = e
                        if state.attempt >= self._retry_policy.max_attempts or state.expired():
                            raise wrap_niquests_connection(e) from e
                        delay = self._retry_policy.next_delay(state.attempt, response=None)
                        if state.remaining() < delay:
                            raise wrap_niquests_connection(e) from e
                        await sleep_delay(delay)
                        continue
                    raise

    async def gather_responses(self, *responses: niquests.Response) -> None:
        """Resolve lazy multiplexed responses; requires ``multiplexed=True`` on the session."""
        await self.session.gather(*responses)

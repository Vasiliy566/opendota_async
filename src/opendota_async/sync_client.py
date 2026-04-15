"""Synchronous OpenDota client (optional facade sharing serializers with async)."""

from __future__ import annotations

import inspect
import json
import threading
import time
from collections.abc import Mapping
from typing import Any, cast

import niquests
import niquests.exceptions as ne

from opendota_async._parse import parse_json_model
from opendota_async._transport import create_sync_session
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
from opendota_async.retry import RetryPolicy, RetryState

_tls = threading.local()


class OpenDotaSyncClient:
    """Thread-safe blocking client using :class:`niquests.Session` (same config model as async)."""

    def __init__(
        self,
        config: OpenDotaClientConfig | None = None,
        *,
        retry_policy: RetryPolicy | None = None,
        **kwargs: Any,
    ) -> None:
        self._config = config or OpenDotaClientConfig(**kwargs)
        self._session = create_sync_session(self._config)
        self._retry_policy = retry_policy or RetryPolicy(
            max_attempts=self._config.retry_max_attempts,
            max_total_seconds=self._config.retry_max_total_seconds,
            retry_post=self._config.retry_post,
        )
        self.players = _SyncPlayers(self)

    @property
    def last_raw_response(self) -> niquests.Response | None:
        """Last Niquests response for the current thread (safe across threads)."""
        return getattr(_tls, "last_raw_response", None)

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> OpenDotaSyncClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        response_model: type[Any] | None = None,
        params: Mapping[str, Any] | None = None,
        json_body: Any = None,
        headers: Mapping[str, str] | None = None,
        timeout: Any = None,
    ) -> Any:
        m = method.upper()
        state = RetryState(deadline=time.monotonic() + self._retry_policy.max_total_seconds)
        last_exc: Exception | None = None

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
                r = self._session.request(
                    m,
                    path,
                    params=dict(params) if params else None,
                    json=json_body,
                    **kw,
                )
                _tls.last_raw_response = r
                sc = r.status_code
                code = int(sc) if sc is not None else 0
                body = r.content
                if inspect.isawaitable(body):
                    raise RuntimeError("unexpected async body in sync client")
                if code >= 400:
                    if (
                        self._retry_policy.should_retry_http(m, code)
                        and state.attempt < self._retry_policy.max_attempts
                    ):
                        delay = self._retry_policy.next_delay(state.attempt, response=r)
                        if state.remaining() < delay:
                            raise map_http_error(r, body)
                        time.sleep(delay)
                        continue
                    raise map_http_error(r, body)
                if not body:
                    parsed = None
                else:
                    try:
                        parsed = json.loads(body.decode("utf-8"))
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
                    time.sleep(delay)
                    continue
                raise


class _SyncPlayers:
    __slots__ = ("_c",)

    def __init__(self, client: OpenDotaSyncClient) -> None:
        self._c = client

    def get(self, account_id: int, *, timeout: Any = None) -> Any:
        from opendota_async.models import PlayerData

        return cast(
            Any,
            self._c.request(
                "GET",
                f"/players/{account_id}",
                response_model=PlayerData,
                timeout=timeout,
            ),
        )

"""Exception hierarchy for the OpenDota client."""

from __future__ import annotations

from typing import Any, cast

import niquests


class OpenDotaError(Exception):
    """Base error for all client failures."""


class ConnectionError(OpenDotaError):
    """Transport failure (DNS, TCP, TLS handshake, etc.)."""

    def __init__(self, message: str, *, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.__cause__ = cause


class TimeoutError(OpenDotaError):
    """Request timed out (connect or read)."""

    def __init__(self, message: str, *, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.__cause__ = cause


class APIError(OpenDotaError):
    """HTTP response indicated failure (non-2xx)."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        request_id: str | None,
        response_body: bytes | str | None,
        headers: dict[str, str],
        negotiated_protocol: str | None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.request_id = request_id
        self.response_body = response_body
        self.headers = headers
        self.negotiated_protocol = negotiated_protocol
        self.__cause__ = cause


class BadRequestError(APIError):
    """HTTP 400."""


class AuthenticationError(APIError):
    """HTTP 401."""


class ForbiddenError(APIError):
    """HTTP 403 (permission denied on resource)."""


class NotFoundError(APIError):
    """HTTP 404."""


class ConflictError(APIError):
    """HTTP 409."""


class RateLimitError(APIError):
    """HTTP 429."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        request_id: str | None,
        response_body: bytes | str | None,
        headers: dict[str, str],
        negotiated_protocol: str | None,
        retry_after: float | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(
            message,
            status_code=status_code,
            request_id=request_id,
            response_body=response_body,
            headers=headers,
            negotiated_protocol=negotiated_protocol,
            cause=cause,
        )
        self.retry_after = retry_after


class UnprocessableError(APIError):
    """HTTP 422."""


class ServerError(APIError):
    """HTTP 5xx."""


class ValidationError(OpenDotaError):
    """Response body could not be validated against the expected schema."""

    def __init__(self, message: str, *, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.__cause__ = cause


def _header_map(response: niquests.Response) -> dict[str, str]:
    try:
        h = response.headers
        if h is None:
            return {}
        return {str(k): str(v) for k, v in cast(Any, h).items()}
    except Exception:
        return {}


def _request_id(headers: dict[str, str]) -> str | None:
    for key in ("X-Request-Id", "X-Request-ID", "x-request-id"):
        if key in headers:
            return headers[key]
        lk = key.lower()
        for hk, hv in headers.items():
            if hk.lower() == lk:
                return hv
    return None


def _protocol(response: niquests.Response) -> str | None:
    ci = getattr(response, "conn_info", None)
    if ci is None:
        return getattr(response, "http_version", None)
    return getattr(ci, "protocol", None) or getattr(response, "http_version", None)


def map_http_error(response: niquests.Response, body: bytes | str | None) -> APIError:
    """Build a typed APIError subclass from a niquests response."""
    sc = response.status_code
    status = int(sc) if sc is not None else 0
    headers = _header_map(response)
    rid = _request_id(headers)
    proto = _protocol(response)
    ra_hdr = headers.get("Retry-After") or headers.get("retry-after")
    retry_after: float | None = None
    if ra_hdr:
        try:
            retry_after = float(ra_hdr)
        except ValueError:
            retry_after = None

    msg = f"HTTP {status} for {response.url!s}"
    common: dict[str, Any] = dict(
        status_code=status,
        request_id=rid,
        response_body=body,
        headers=headers,
        negotiated_protocol=proto,
    )

    if status == 400:
        return BadRequestError(msg, **common)
    if status == 401:
        return AuthenticationError(msg, **common)
    if status == 403:
        return ForbiddenError(msg, **common)
    if status == 404:
        return NotFoundError(msg, **common)
    if status == 409:
        return ConflictError(msg, **common)
    if status == 429:
        return RateLimitError(msg, retry_after=retry_after, **common)
    if status == 422:
        return UnprocessableError(msg, **common)
    if status >= 500:
        return ServerError(msg, **common)
    return APIError(msg, **common)


def wrap_niquests_connection(exc: Exception) -> OpenDotaError:
    import niquests.exceptions as ne

    if isinstance(exc, (ne.Timeout, ne.ConnectTimeout, ne.ReadTimeout)):
        return TimeoutError(str(exc), cause=exc)
    if isinstance(exc, ne.ConnectionError):
        return ConnectionError(str(exc), cause=exc)
    return ConnectionError(str(exc), cause=exc)

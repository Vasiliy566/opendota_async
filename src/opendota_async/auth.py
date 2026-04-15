"""Authentication strategies wrapping Niquests auth types."""

from __future__ import annotations

import asyncio
import hmac
import time
from abc import ABC, abstractmethod
from collections.abc import Mapping
from hashlib import sha256
from typing import Any, Protocol, TypeVar

from niquests.auth import HTTPBasicAuth as _HTTPBasicAuth
from niquests.auth import HTTPDigestAuth as _HTTPDigestAuth
from niquests.models import PreparedRequest

try:
    from niquests.auth import AsyncHTTPDigestAuth as _AsyncHTTPDigestAuth
except ImportError:  # pragma: no cover
    _AsyncHTTPDigestAuth = None  # type: ignore[misc, assignment]

T_co = TypeVar("T_co", covariant=True)


class AsyncAuth(Protocol):
    async def __call__(self, request: PreparedRequest) -> PreparedRequest: ...


class BearerAuth:
    """Set ``Authorization: Bearer <token>`` on each request."""

    __slots__ = ("token",)

    def __init__(self, token: str) -> None:
        self.token = token

    def __call__(self, request: PreparedRequest) -> PreparedRequest:
        h = request.headers
        if h is not None:
            h["Authorization"] = f"Bearer {self.token}"
        return request


class AsyncBearerAuth:
    """Async variant of :class:`BearerAuth`."""

    __slots__ = ("token",)

    def __init__(self, token: str) -> None:
        self.token = token

    async def __call__(self, request: PreparedRequest) -> PreparedRequest:
        h = request.headers
        if h is not None:
            h["Authorization"] = f"Bearer {self.token}"
        return request


class ApiKeyQueryAuth:
    """Append ``api_key`` to the query string (OpenDota-compatible)."""

    __slots__ = ("name", "api_key")

    def __init__(self, api_key: str, *, name: str = "api_key") -> None:
        self.name = name
        self.api_key = api_key

    def __call__(self, request: PreparedRequest) -> PreparedRequest:
        request.prepare_url(request.url, {self.name: self.api_key})
        return request


class AsyncApiKeyQueryAuth:
    __slots__ = ("name", "api_key")

    def __init__(self, api_key: str, *, name: str = "api_key") -> None:
        self.name = name
        self.api_key = api_key

    async def __call__(self, request: PreparedRequest) -> PreparedRequest:
        request.prepare_url(request.url, {self.name: self.api_key})
        return request


HTTPBasicAuth = _HTTPBasicAuth
HTTPDigestAuth = _HTTPDigestAuth
AsyncHTTPDigestAuth = _AsyncHTTPDigestAuth


class OAuth2ClientCredentialsAuth(ABC):
    """Bearer auth with async token acquisition and single-flight refresh on 401."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._token: str | None = None
        self._expiry: float = 0.0

    @abstractmethod
    async def fetch_token(self) -> tuple[str, float | None]:
        """Return ``(access_token, expires_at_unix_or_none)``."""

    async def _ensure_token(self, *, force: bool = False) -> str:
        async with self._lock:
            now = time.time()
            if not force and self._token and (self._expiry == 0.0 or now < self._expiry - 30):
                return self._token
            token, exp = await self.fetch_token()
            self._token = token
            self._expiry = exp if exp is not None else 0.0
            return token

    async def __call__(self, request: PreparedRequest) -> PreparedRequest:
        tok = await self._ensure_token()
        h = request.headers
        if h is not None:
            h["Authorization"] = f"Bearer {tok}"
        return request


class HmacSignatureAuth:
    """Sign a canonical string with HMAC-SHA256 (generic hook for bespoke APIs)."""

    __slots__ = ("secret", "header_name")

    def __init__(self, secret: bytes, *, header_name: str = "X-Signature") -> None:
        self.secret = secret
        self.header_name = header_name

    def sign(self, prepared: PreparedRequest) -> str:
        url = prepared.url or ""
        raw = prepared.body
        if raw is None:
            body = b""
        elif isinstance(raw, (bytes, bytearray)):
            body = bytes(raw)
        elif isinstance(raw, str):
            body = raw.encode()
        else:
            body = b""
        msg = f"{prepared.method}:{url}:".encode() + body
        return hmac.new(self.secret, msg, sha256).hexdigest()

    def __call__(self, request: PreparedRequest) -> PreparedRequest:
        h = request.headers
        if h is not None:
            h[self.header_name] = self.sign(request)
        return request


class ClientCertificateAuth:
    """Hold client cert material for Niquests (paths or ``(cert_pem, key_pem)`` bytes tuples)."""

    __slots__ = ("cert",)

    def __init__(self, cert: Any) -> None:
        self.cert = cert


def redact_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Mask sensitive headers for logging."""
    sensitive = frozenset(
        {
            "authorization",
            "cookie",
            "set-cookie",
            "x-api-key",
            "x-auth-token",
            "proxy-authorization",
        }
    )
    out: dict[str, str] = {}
    for k, v in headers.items():
        lk = k.lower()
        if lk in sensitive or "token" in lk or "secret" in lk:
            out[k] = "<redacted>"
        else:
            out[k] = v
    return out

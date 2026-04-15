"""Test doubles and adapter examples for downstream test suites."""

from __future__ import annotations

from typing import Any

from opendota_async.client import OpenDotaClient
from opendota_async.config import OpenDotaClientConfig


def client_with_session(
    session: Any,
    *,
    config: OpenDotaClientConfig | None = None,
) -> OpenDotaClient:
    """Build :class:`OpenDotaClient` with a stub or mock ``AsyncSession``.

    Niquests is ``requests``-shaped, so you can also use a ``BaseAdapter`` that returns
    canned :class:`niquests.Response` objects mounted on a real session in tests.
    """

    def _factory(_: OpenDotaClientConfig) -> Any:
        return session

    return OpenDotaClient(config=config or OpenDotaClientConfig(), session_factory=_factory)

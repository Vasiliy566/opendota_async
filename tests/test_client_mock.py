"""Unit tests with a stub session factory (no network)."""

from __future__ import annotations

import json
from typing import Any

import niquests
import pytest

from opendota_async.client import OpenDotaClient
from opendota_async.config import OpenDotaClientConfig


class _StubAsyncSession:
    """Minimal async session that returns canned JSON."""

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self._responses = responses
        self._i = 0
        self.multiplexed = True

    async def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        **kwargs: Any,
    ) -> _StubResponse:
        idx = min(self._i, len(self._responses) - 1)
        self._i += 1
        return _StubResponse(self._responses[idx], method, url)

    async def gather(self, *responses: niquests.Response, max_fetch: int | None = None) -> None:
        return None

    async def close(self) -> None:
        return None


class _StubResponse:
    status_code = 200
    headers: dict[str, str] = {}

    def __init__(self, payload: dict[str, Any], method: str, url: str) -> None:
        self._payload = payload
        self.request = type("R", (), {"method": method})()
        self.url = url
        self.conn_info = None

    @property
    def content(self):
        async def _go() -> bytes:
            return json.dumps(self._payload).encode()

        return _go()


@pytest.mark.asyncio
async def test_players_get_parses_model() -> None:
    payload = {
        "rank_tier": 80,
        "profile": {"account_id": 1, "personaname": "tester"},
    }
    session = _StubAsyncSession([payload])

    def factory(_: OpenDotaClientConfig) -> Any:
        return session

    client = OpenDotaClient(config=OpenDotaClientConfig(), session_factory=factory)
    p = await client.players.get(1)
    assert p.rank_tier == 80
    assert p.profile is not None
    assert p.profile.personaname == "tester"
    await client.aclose()

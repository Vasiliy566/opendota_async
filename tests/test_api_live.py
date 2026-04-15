"""Integration tests against https://api.opendota.com (no API key required).

Set ``OPENDOTA_OFFLINE=1`` to skip these tests (e.g. air-gapped CI).
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("OPENDOTA_OFFLINE") == "1",
    reason="OPENDOTA_OFFLINE=1 skips network tests",
)


@pytest.mark.asyncio
async def test_get_heroes() -> None:
    from opendota_async import OpenDotaClient

    async with OpenDotaClient() as c:
        data = await c.request("GET", "/heroes", response_model=None)
        assert c.last_raw_response is not None
        assert int(c.last_raw_response.status_code or 0) == 200
        assert isinstance(data, list)
        assert len(data) >= 1


@pytest.mark.asyncio
async def test_get_metadata() -> None:
    from opendota_async import OpenDotaClient

    async with OpenDotaClient() as c:
        await c.request("GET", "/metadata", response_model=None)
        assert int(c.last_raw_response.status_code or 0) == 200


@pytest.mark.asyncio
async def test_get_public_matches_sample() -> None:
    from opendota_async import OpenDotaClient

    async with OpenDotaClient() as c:
        data = await c.request("GET", "/publicMatches", response_model=None)
        assert int(c.last_raw_response.status_code or 0) == 200
        assert isinstance(data, list)

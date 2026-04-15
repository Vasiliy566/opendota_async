"""Player endpoints — profile, matches, win/loss, multiplexed fan-out, pagination."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, cast

import niquests

from opendota_async._compat import async_read_body
from opendota_async.errors import map_http_error
from opendota_async.models import (
    PlayerData,
    PlayerMatch,
    PlayerRecentMatch,
    PlayerWinLoss,
)
from opendota_async.pagination import AsyncPaginator

if TYPE_CHECKING:
    from opendota_async.client import OpenDotaClient


class PlayersResource:
    """``/players/...`` API surface."""

    __slots__ = ("_client",)

    def __init__(self, client: OpenDotaClient) -> None:
        self._client = client

    async def get(self, account_id: int, *, timeout: Any = None) -> PlayerData:
        """Load player summary (medals, profile, aliases).

        Args:
            account_id: Steam32 account id.
            timeout: Optional per-request timeout override.

        Returns:
            Parsed :class:`~opendota_async.models.PlayerData`.

        Raises:
            opendota_async.errors.NotFoundError: If the profile cannot be loaded.
            opendota_async.errors.OpenDotaError: Other transport/API failures.

        Example:
            >>> async with OpenDotaClient() as c:
            ...     p = await c.players.get(86745912)
        """
        return cast(
            PlayerData,
            await self._client.request(
                "GET",
                f"/players/{account_id}",
                response_model=PlayerData,
                timeout=timeout,
            ),
        )

    async def win_loss(
        self,
        account_id: int,
        *,
        timeout: Any = None,
        **filters: Any,
    ) -> PlayerWinLoss:
        """Win/loss counts with optional filters (``limit``, ``patch``, ``hero_id``, …)."""
        return cast(
            PlayerWinLoss,
            await self._client.request(
                "GET",
                f"/players/{account_id}/wl",
                response_model=PlayerWinLoss,
                params=filters,
                timeout=timeout,
            ),
        )

    async def recent_matches(
        self,
        account_id: int,
        *,
        timeout: Any = None,
    ) -> list[PlayerRecentMatch]:
        """Recent matches (small fixed window from the API)."""
        return cast(
            list[PlayerRecentMatch],
            await self._client.request(
                "GET",
                f"/players/{account_id}/recentMatches",
                response_model=list[PlayerRecentMatch],
                timeout=timeout,
            ),
        )

    def matches(
        self,
        account_id: int,
        *,
        page_size: int = 100,
        start_offset: int = 0,
        **filters: Any,
    ) -> AsyncPaginator[PlayerMatch]:
        """Async iterator over match history using ``limit``/``offset`` pagination.

        Example:
            >>> async with OpenDotaClient() as c:
            ...     async for m in c.players.matches(123, hero_id=1):
            ...         print(m.match_id)
        """

        async def fetch(*, limit: int, offset: int, **kw: Any) -> list[PlayerMatch]:
            params = dict(kw)
            params["limit"] = limit
            params["offset"] = offset
            return cast(
                list[PlayerMatch],
                await self._client.request(
                    "GET",
                    f"/players/{account_id}/matches",
                    response_model=list[PlayerMatch],
                    params=params,
                ),
            )

        return AsyncPaginator(
            fetch,
            page_size=page_size,
            start_offset=start_offset,
            **filters,
        )

    async def refresh(self, account_id: int, *, timeout: Any = None) -> None:
        """Queue a profile refresh (POST — not retried on failure unless configured)."""
        await self._client.request(
            "POST",
            f"/players/{account_id}/refresh",
            response_model=None,
            timeout=timeout,
        )

    async def gather_get(
        self,
        account_ids: Sequence[int],
        *,
        timeout: Any = None,
    ) -> list[PlayerData]:
        """Fetch many player profiles over one multiplexed HTTP/2+ connection.

        Temporarily enables session multiplexing, dispatches lazy responses, then restores
        the previous setting. Responses are resolved via :meth:`OpenDotaClient.gather_responses`.

        Args:
            account_ids: Steam32 ids to load in parallel.
            timeout: Optional per-request timeout.

        Returns:
            Parsed profiles in the same order as ``account_ids``.

        Raises:
            opendota_async.errors.OpenDotaError: On failures after retries.

        Note:
            Resolve all lazy responses before closing the client.
        """
        sess = self._client.session
        lazy: list[niquests.Response] = []
        async with self._client._mpx_lock:
            prev_mpx = sess.multiplexed
            sess.multiplexed = True
            try:
                for aid in account_ids:
                    resp = await sess.get(
                        f"/players/{aid}",
                        timeout=timeout,
                    )
                    lazy.append(resp)
                await self._client.gather_responses(*lazy)
            finally:
                sess.multiplexed = prev_mpx
        out: list[PlayerData] = []
        for r in lazy:
            if r.status_code is not None and int(r.status_code) >= 400:
                err = await async_read_body(r)
                raise map_http_error(r, err)
            raw = await async_read_body(r)
            if not raw:
                out.append(PlayerData.model_validate({}))
                continue
            data = json.loads(raw.decode("utf-8"))
            out.append(PlayerData.model_validate(data))
        return out

"""Async iterators for offset/limit style pagination."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class OffsetLimitPaginator(Generic[T]):
    """Iterate pages using ``limit`` / ``offset`` query parameters."""

    def __init__(
        self,
        fetch_page: Callable[..., Awaitable[list[T]]],
        *,
        page_size: int = 100,
        start_offset: int = 0,
        **fixed_params: object,
    ) -> None:
        self._fetch = fetch_page
        self._page_size = page_size
        self._offset = start_offset
        self._fixed = fixed_params

    def __aiter__(self) -> AsyncIterator[T]:
        return self._gen()

    async def _gen(self) -> AsyncIterator[T]:
        while True:
            batch = await self._fetch(limit=self._page_size, offset=self._offset, **self._fixed)
            if not batch:
                break
            for item in batch:
                yield item
            if len(batch) < self._page_size:
                break
            self._offset += self._page_size

    async def all(self, *, max_items: int = 100_000) -> list[T]:
        """Materialize results up to ``max_items`` (safety cap)."""
        out: list[T] = []
        async for item in self:
            out.append(item)
            if len(out) >= max_items:
                break
        return out


class AsyncPaginator(OffsetLimitPaginator[T]):
    """Alias matching the common ``AsyncPaginator`` name from the design doc."""

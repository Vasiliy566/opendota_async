"""Small helpers bridging Niquests response body access."""

from __future__ import annotations

import inspect
from typing import Any


async def async_read_body(response: Any) -> bytes | None:
    """Read ``response.content`` whether it is awaitable or plain bytes."""
    c = response.content
    if inspect.isawaitable(c):
        return await c  # type: ignore[no-any-return]
    if c is None:
        return None
    if isinstance(c, (bytes, bytearray)):
        return bytes(c)
    return None

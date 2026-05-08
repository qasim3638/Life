"""Tests for the UI health runner — skip-text-marker + dynamic-collection logic.

These don't run the real Playwright probe (too slow); we mock the
parts that touch the network and exercise just the new control flow.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services import ui_health_runner as runner


# ───── _resolve_first_collection_url ─────

@pytest.mark.asyncio
async def test_resolve_first_collection_returns_url_for_top_collection():
    """Picks the collection with the most products and URL-encodes it."""
    fake_db = MagicMock()

    class FakeAggCursor:
        def __init__(self, rows):
            self.rows = rows
        def __aiter__(self):
            self._iter = iter(self.rows)
            return self
        async def __anext__(self):
            try:
                return next(self._iter)
            except StopIteration:
                raise StopAsyncIteration

    fake_db.tiles.aggregate = MagicMock(
        return_value=FakeAggCursor([{"_id": "Calacatta Marble", "n": 42}])
    )

    with patch("config.get_db", return_value=fake_db):
        url = await runner._resolve_first_collection_url()

    # URL-encoded space, prefixed with /shop/collection/
    assert url == "/shop/collection/Calacatta%20Marble"


@pytest.mark.asyncio
async def test_resolve_first_collection_returns_none_when_empty():
    fake_db = MagicMock()

    class EmptyCursor:
        def __aiter__(self):
            return self
        async def __anext__(self):
            raise StopAsyncIteration

    fake_db.tiles.aggregate = MagicMock(return_value=EmptyCursor())
    with patch("config.get_db", return_value=fake_db):
        url = await runner._resolve_first_collection_url()
    assert url is None


@pytest.mark.asyncio
async def test_resolve_first_collection_handles_db_exception():
    fake_db = MagicMock()
    fake_db.tiles.aggregate = MagicMock(side_effect=RuntimeError("db down"))
    with patch("config.get_db", return_value=fake_db):
        url = await runner._resolve_first_collection_url()
    assert url is None


@pytest.mark.asyncio
async def test_resolve_first_collection_encodes_special_chars():
    """Names with special chars (& slashes, brackets) must be URL-safe."""
    fake_db = MagicMock()

    class Cursor:
        def __init__(self, rows): self.rows = rows
        def __aiter__(self):
            self._iter = iter(self.rows)
            return self
        async def __anext__(self):
            try:
                return next(self._iter)
            except StopIteration:
                raise StopAsyncIteration

    fake_db.tiles.aggregate = MagicMock(
        return_value=Cursor([{"_id": "Bath & Beyond", "n": 5}])
    )
    with patch("config.get_db", return_value=fake_db):
        url = await runner._resolve_first_collection_url()
    assert "Bath" in url and "%26" in url and "Beyond" in url

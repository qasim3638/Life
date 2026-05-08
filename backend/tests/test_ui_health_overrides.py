"""Tests for the disabled-check override system in ui_health_runner."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services import ui_health_runner as runner


# ───── set_check_disabled ─────

@pytest.mark.asyncio
async def test_set_check_disabled_writes_disabled_row():
    fake_db = MagicMock()
    fake_col = MagicMock()
    fake_col.update_one = AsyncMock()
    fake_db.__getitem__ = MagicMock(return_value=fake_col)

    with patch("config.get_db", return_value=fake_db):
        result = await runner.set_check_disabled(
            "tile_detail_trade_box",
            disabled=True,
            reason="Trade login removed for May",
            actor_email="qasim@tilestation.co.uk",
        )

    assert result["check_id"] == "tile_detail_trade_box"
    assert result["disabled"] is True
    assert result["reason"] == "Trade login removed for May"
    fake_col.update_one.assert_awaited_once()
    args = fake_col.update_one.call_args.args
    assert args[0] == {"check_id": "tile_detail_trade_box"}
    set_payload = args[1]["$set"]
    assert set_payload["disabled"] is True
    assert set_payload["disabled_by"] == "qasim@tilestation.co.uk"
    # call_args.kwargs will contain upsert=True
    assert fake_col.update_one.call_args.kwargs.get("upsert") is True


@pytest.mark.asyncio
async def test_set_check_disabled_re_enable_clears_disabled_flag():
    fake_db = MagicMock()
    fake_col = MagicMock()
    fake_col.update_one = AsyncMock()
    fake_db.__getitem__ = MagicMock(return_value=fake_col)

    with patch("config.get_db", return_value=fake_db):
        result = await runner.set_check_disabled(
            "refer_page", disabled=False, actor_email="admin@test.com",
        )

    set_payload = fake_col.update_one.call_args.args[1]["$set"]
    assert set_payload["disabled"] is False
    assert set_payload["enabled_by"] == "admin@test.com"
    assert "disabled_by" not in set_payload
    assert result["disabled"] is False


@pytest.mark.asyncio
async def test_set_check_disabled_clamps_long_reasons():
    """Reason field is hard-capped at 280 chars to avoid bloating
    responses with admin-pasted essays."""
    fake_db = MagicMock()
    fake_col = MagicMock()
    fake_col.update_one = AsyncMock()
    fake_db.__getitem__ = MagicMock(return_value=fake_col)

    with patch("config.get_db", return_value=fake_db):
        await runner.set_check_disabled(
            "x", disabled=True, reason="A" * 500,
        )

    set_payload = fake_col.update_one.call_args.args[1]["$set"]
    assert len(set_payload["reason"]) <= 280


@pytest.mark.asyncio
async def test_set_check_disabled_uses_default_reason_when_blank():
    fake_db = MagicMock()
    fake_col = MagicMock()
    fake_col.update_one = AsyncMock()
    fake_db.__getitem__ = MagicMock(return_value=fake_col)

    with patch("config.get_db", return_value=fake_db):
        await runner.set_check_disabled("y", disabled=True, reason="   ")

    set_payload = fake_col.update_one.call_args.args[1]["$set"]
    assert set_payload["reason"] == "Disabled by admin"


# ───── _get_disabled_overrides ─────

@pytest.mark.asyncio
async def test_get_disabled_overrides_returns_dict_keyed_on_id():
    fake_db = MagicMock()
    fake_col = MagicMock()

    class FakeCursor:
        def __init__(self, rows): self.rows = rows
        def __aiter__(self):
            self._iter = iter(self.rows)
            return self
        async def __anext__(self):
            try:
                return next(self._iter)
            except StopIteration:
                raise StopAsyncIteration

    rows = [
        {"check_id": "refer_page", "reason": "paused", "disabled_by": "admin@x.co",
         "disabled_at": datetime(2026, 5, 4, tzinfo=timezone.utc)},
        {"check_id": "contact_page", "reason": None, "disabled_by": "user@x.co"},
    ]
    fake_col.find = MagicMock(return_value=FakeCursor(rows))
    fake_db.__getitem__ = MagicMock(return_value=fake_col)

    with patch("config.get_db", return_value=fake_db):
        out = await runner._get_disabled_overrides()

    assert "refer_page" in out
    assert "contact_page" in out
    assert out["refer_page"]["reason"] == "paused"
    assert out["refer_page"]["by"] == "admin@x.co"
    assert isinstance(out["refer_page"]["at"], str)  # ISO-formatted


@pytest.mark.asyncio
async def test_get_disabled_overrides_returns_empty_on_db_error():
    """Resilient — DB outage must NOT cause every check to be reported
    as disabled. Falls back to empty (run all checks)."""
    fake_db = MagicMock()
    fake_db.__getitem__ = MagicMock(side_effect=RuntimeError("db down"))

    with patch("config.get_db", return_value=fake_db):
        out = await runner._get_disabled_overrides()

    assert out == {}


@pytest.mark.asyncio
async def test_get_disabled_overrides_skips_rows_without_check_id():
    """Defensive — drop any row that's missing the check_id key."""
    fake_db = MagicMock()
    fake_col = MagicMock()

    class FakeCursor:
        def __init__(self, rows): self.rows = rows
        def __aiter__(self):
            self._iter = iter(self.rows)
            return self
        async def __anext__(self):
            try:
                return next(self._iter)
            except StopIteration:
                raise StopAsyncIteration

    rows = [
        {"check_id": "refer_page", "reason": "paused"},
        {"reason": "no id row — should be skipped"},  # malformed
    ]
    fake_col.find = MagicMock(return_value=FakeCursor(rows))
    fake_db.__getitem__ = MagicMock(return_value=fake_col)

    with patch("config.get_db", return_value=fake_db):
        out = await runner._get_disabled_overrides()

    assert len(out) == 1
    assert "refer_page" in out


# ───── list_overrides ─────

@pytest.mark.asyncio
async def test_list_overrides_serialises_datetimes_to_iso():
    fake_db = MagicMock()
    fake_col = MagicMock()

    class FakeCursor:
        def __init__(self, rows): self.rows = rows
        def __aiter__(self):
            self._iter = iter(self.rows)
            return self
        async def __anext__(self):
            try:
                return next(self._iter)
            except StopIteration:
                raise StopAsyncIteration

    rows = [{
        "check_id": "x", "disabled": True,
        "updated_at": datetime(2026, 5, 4, 12, 0, tzinfo=timezone.utc),
        "disabled_at": datetime(2026, 5, 4, 12, 0, tzinfo=timezone.utc),
    }]
    fake_col.find = MagicMock(return_value=FakeCursor(rows))
    fake_db.__getitem__ = MagicMock(return_value=fake_col)

    with patch("config.get_db", return_value=fake_db):
        out = await runner.list_overrides()

    assert len(out) == 1
    assert isinstance(out[0]["updated_at"], str)
    assert isinstance(out[0]["disabled_at"], str)

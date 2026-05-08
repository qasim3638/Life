"""Tests for the weekly Stealth-Keyword Performance digest email."""
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402


@pytest_asyncio.fixture
async def db(monkeypatch):
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    test_db = client[f"test_stealth_dig_{uuid.uuid4().hex[:8]}"]
    monkeypatch.setattr("services.stealth_seo_digest.get_db", lambda: test_db)
    yield test_db
    await client.drop_database(test_db.name)
    client.close()


def _fake_this_week():
    return {
        "gsc_connected": True,
        "totals": {"clicks": 200, "impressions": 4000, "ctr": 0.05, "queries_count": 100, "share_pct": 0},
        "stealth": {"clicks": 60, "impressions": 1200, "ctr": 0.05, "queries_count": 30, "share_pct": 30},
        "brand": {"clicks": 40, "impressions": 800, "ctr": 0.05, "queries_count": 20, "share_pct": 20},
        "other": {"clicks": 100, "impressions": 2000, "ctr": 0.05, "queries_count": 50, "share_pct": 50},
        "top_winners": [
            {"keyword": "Onyx White", "scope": "product", "product_name": "Alabaster", "clicks": 40, "impressions": 800, "ctr": 0.05},
            {"keyword": "LP-6611", "scope": "product", "product_name": "Alabaster", "clicks": 20, "impressions": 400, "ctr": 0.05},
        ],
        "missed_wins": [
            {"query": "spanish tiles", "clicks": 0, "impressions": 49, "ctr": 0, "position": 15.1},
            {"query": "tiles gravesend", "clicks": 0, "impressions": 37, "ctr": 0, "position": 14.0},
        ],
        "underperformers": [{"keyword": "dead_kw", "scope": "product"}],
        "start_date": "2026-04-28", "end_date": "2026-05-04",
    }


def _fake_fortnight():
    # Cumulative 14-day — used to subtract-out this-week to get last week
    return {
        "gsc_connected": True,
        "totals": {"clicks": 350, "impressions": 7000, "ctr": 0.05, "queries_count": 175, "share_pct": 0},
        "stealth": {"clicks": 100, "impressions": 2000, "ctr": 0.05, "queries_count": 50, "share_pct": 28},
        "brand": {"clicks": 70, "impressions": 1400, "ctr": 0.05, "queries_count": 35, "share_pct": 20},
        "other": {"clicks": 180, "impressions": 3600, "ctr": 0.05, "queries_count": 90, "share_pct": 52},
        "top_winners": [],
        "missed_wins": [
            # "tiles gravesend" was in last week's list → not "new"
            {"query": "tiles gravesend", "clicks": 0, "impressions": 60, "ctr": 0, "position": 14.5},
            # "old query" that's not in this week's missed set
            {"query": "old query no longer", "clicks": 0, "impressions": 20, "ctr": 0, "position": 50.0},
        ],
        "underperformers": [],
        "start_date": "2026-04-21", "end_date": "2026-05-04",
    }


# ───── Settings round-trip ─────

@pytest.mark.asyncio
async def test_settings_default(db):
    from services.stealth_seo_digest import get_settings
    s = await get_settings()
    assert s["enabled"] is True
    assert s["recipients"] == []
    assert s["last_sent_at"] is None


@pytest.mark.asyncio
async def test_settings_update_enabled_flag(db):
    from services.stealth_seo_digest import update_settings, get_settings
    await update_settings({"enabled": False}, admin_email="a@b.com")
    s = await get_settings()
    assert s["enabled"] is False


@pytest.mark.asyncio
async def test_settings_recipients_whitelist(db):
    from services.stealth_seo_digest import update_settings, get_settings
    # String format (comma-separated)
    await update_settings({"recipients": "a@b.com, c@d.com, garbage, x"})
    s = await get_settings()
    assert s["recipients"] == ["a@b.com", "c@d.com"]


@pytest.mark.asyncio
async def test_settings_recipients_caps_at_10(db):
    from services.stealth_seo_digest import update_settings, get_settings
    await update_settings({"recipients": [f"x{i}@b.com" for i in range(20)]})
    s = await get_settings()
    assert len(s["recipients"]) == 10


# ───── _build_digest — delta math + new-missed diff ─────

@pytest.mark.asyncio
async def test_build_digest_computes_deltas_and_new_missed(db, monkeypatch):
    from services import stealth_seo_digest as dig
    perf_mock = AsyncMock(side_effect=[_fake_this_week(), _fake_fortnight()])
    monkeypatch.setattr(dig, "get_settings", AsyncMock(return_value={"enabled": True, "recipients": []}))
    with patch("services.stealth_seo_performance.get_performance", perf_mock):
        d = await dig._build_digest(days=7)
    # this week stealth = 60 clicks, last (fortnight - this) = 100 - 60 = 40
    assert d["this"]["clicks"] == 60
    assert d["last"]["clicks"] == 40
    # +50% delta
    assert d["delta_pct"]["clicks"] == 50
    # top winners pass through
    assert d["top_winners"][0]["keyword"] == "Onyx White"
    # new_missed = this-week missed queries NOT in fortnight-minus-this-week
    # "spanish tiles" is NEW (not in fortnight missed); "tiles gravesend" was there → not new
    new_qs = {m["query"] for m in d["new_missed"]}
    assert "spanish tiles" in new_qs
    assert "tiles gravesend" not in new_qs


@pytest.mark.asyncio
async def test_build_digest_zero_last_week_shows_100_pct(db, monkeypatch):
    from services import stealth_seo_digest as dig
    # this week has 50 clicks, fortnight also has 50 (i.e. all new from this week, nothing last week)
    this = _fake_this_week()
    this["stealth"]["clicks"] = 50
    fort = _fake_fortnight()
    fort["stealth"]["clicks"] = 50  # same — last week had 0
    perf_mock = AsyncMock(side_effect=[this, fort])
    with patch("services.stealth_seo_performance.get_performance", perf_mock):
        d = await dig._build_digest(days=7)
    assert d["last"]["clicks"] == 0
    assert d["delta_pct"]["clicks"] == 100


# ───── _render_html — smoke render doesn't crash ─────

@pytest.mark.asyncio
async def test_render_html_includes_key_signals(db, monkeypatch):
    from services import stealth_seo_digest as dig
    perf_mock = AsyncMock(side_effect=[_fake_this_week(), _fake_fortnight()])
    with patch("services.stealth_seo_performance.get_performance", perf_mock):
        d = await dig._build_digest(days=7)
    html = dig._render_html(d)
    assert "Onyx White" in html
    assert "spanish tiles" in html
    assert "60" in html  # this-week clicks
    assert "40" in html  # last-week clicks


@pytest.mark.asyncio
async def test_render_html_without_gsc_shows_reconnect_cta(db):
    from services import stealth_seo_digest as dig
    html = dig._render_html({
        "gsc_connected": False,
        "this": {}, "last": {}, "delta_pct": {"clicks": 0, "impressions": 0},
        "top_winners": [], "new_missed": [], "underperformer_count": 0,
    })
    assert "GSC" in html or "Google Search Console" in html


# ───── send_digest_now — the always-on entrypoint ─────

@pytest.mark.asyncio
async def test_send_digest_no_recipients_returns_reason(db, monkeypatch):
    from services import stealth_seo_digest as dig
    monkeypatch.delenv("ADMIN_EMAIL", raising=False)
    res = await dig.send_digest_now()
    assert res["ok"] is False
    assert res["reason"] == "no_recipients"


@pytest.mark.asyncio
async def test_send_digest_now_fires_and_stamps(db, monkeypatch):
    from services import stealth_seo_digest as dig
    monkeypatch.setenv("ADMIN_EMAIL", "admin@x.com")
    perf_mock = AsyncMock(side_effect=[_fake_this_week(), _fake_fortnight()])
    send_mock = AsyncMock(return_value=True)
    with patch("services.stealth_seo_performance.get_performance", perf_mock), \
         patch("services.email.send_email_notification", send_mock):
        res = await dig.send_digest_now()
    assert res["ok"] is True
    assert res["recipients"] == ["admin@x.com"]
    assert "clicks" in res["subject"]
    # Persisted
    row = await db.seo_stealth_digest_settings.find_one({"id": "main"}, {"_id": 0})
    assert row is not None and row.get("last_sent_at") is not None
    hist = await db.seo_stealth_digest_history.count_documents({})
    assert hist == 1


# ───── run_weekly_digest_if_due — guardrails ─────

@pytest.mark.asyncio
async def test_weekly_skips_when_disabled(db):
    from services import stealth_seo_digest as dig
    await dig.update_settings({"enabled": False})
    res = await dig.run_weekly_digest_if_due()
    assert res["skipped"] is True
    assert res["reason"] == "disabled"


@pytest.mark.asyncio
async def test_weekly_skips_when_throttled(db):
    from services import stealth_seo_digest as dig
    # simulate a send 2 days ago
    await db.seo_stealth_digest_settings.update_one(
        {"id": "main"},
        {"$set": {"id": "main", "enabled": True,
                   "last_sent_at": datetime.now(timezone.utc) - timedelta(days=2)}},
        upsert=True,
    )
    res = await dig.run_weekly_digest_if_due()
    assert res["skipped"] is True
    assert res["reason"] == "throttled"


@pytest.mark.asyncio
async def test_weekly_skips_when_no_signal(db, monkeypatch):
    from services import stealth_seo_digest as dig
    empty = {"gsc_connected": True, "totals": {}, "stealth": {"clicks": 0},
             "brand": {"clicks": 0}, "other": {"clicks": 0},
             "top_winners": [], "missed_wins": [], "underperformers": [],
             "start_date": "a", "end_date": "b"}
    perf_mock = AsyncMock(return_value=empty)
    with patch("services.stealth_seo_performance.get_performance", perf_mock):
        res = await dig.run_weekly_digest_if_due()
    assert res["skipped"] is True
    assert res["reason"] == "no_signal"


@pytest.mark.asyncio
async def test_weekly_runs_when_signal_present(db, monkeypatch):
    from services import stealth_seo_digest as dig
    monkeypatch.setenv("ADMIN_EMAIL", "admin@x.com")
    perf_mock = AsyncMock(side_effect=[
        _fake_this_week(), _fake_fortnight(),  # _build_digest for gate-check
        _fake_this_week(), _fake_fortnight(),  # _build_digest inside send_digest_now
    ])
    send_mock = AsyncMock(return_value=True)
    with patch("services.stealth_seo_performance.get_performance", perf_mock), \
         patch("services.email.send_email_notification", send_mock):
        res = await dig.run_weekly_digest_if_due()
    assert res["ok"] is True
    assert send_mock.call_count == 1


@pytest.mark.asyncio
async def test_weekly_does_not_throttle_after_failed_send(db, monkeypatch):
    """A failed Resend delivery must NOT silence the next week's cron —
    if last_sent_ok is False, the 6-day throttle is bypassed."""
    from services import stealth_seo_digest as dig
    # simulate a recent FAILED send (ok=False) yesterday
    await db.seo_stealth_digest_settings.update_one(
        {"id": "main"},
        {"$set": {"id": "main", "enabled": True,
                   "last_sent_at": datetime.now(timezone.utc) - timedelta(days=1),
                   "last_sent_ok": False}},
        upsert=True,
    )
    monkeypatch.setenv("ADMIN_EMAIL", "admin@x.com")
    perf_mock = AsyncMock(side_effect=[
        _fake_this_week(), _fake_fortnight(),
        _fake_this_week(), _fake_fortnight(),
    ])
    send_mock = AsyncMock(return_value=True)
    with patch("services.stealth_seo_performance.get_performance", perf_mock), \
         patch("services.email.send_email_notification", send_mock):
        res = await dig.run_weekly_digest_if_due()
    assert res["ok"] is True  # RAN despite 1-day-ago prior send
    assert send_mock.call_count == 1

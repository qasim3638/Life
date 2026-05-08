"""Tests for the SEO Dashboard Snapshot composer."""
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
    test_db = client[f"test_dashboard_{uuid.uuid4().hex[:8]}"]
    monkeypatch.setattr("services.seo_dashboard_snapshot.get_db", lambda: test_db)
    yield test_db
    await client.drop_database(test_db.name)
    client.close()


# ───── _headline_perf ─────

@pytest.mark.asyncio
async def test_headline_no_gsc(db, monkeypatch):
    from services import seo_dashboard_snapshot as snap
    from services import stealth_seo_performance as perf
    empty_no_gsc = {"gsc_connected": False, "stealth": {}, "totals": {}}
    monkeypatch.setattr(perf, "get_performance",
                        AsyncMock(return_value=empty_no_gsc))
    res = await snap._headline_perf()
    assert res["gsc_connected"] is False
    assert res["stealth_clicks_this_week"] == 0
    assert res["stealth_clicks_delta_pct"] == 0


@pytest.mark.asyncio
async def test_headline_computes_wow_delta(db, monkeypatch):
    from services import seo_dashboard_snapshot as snap
    from services import stealth_seo_performance as perf
    this_week = {
        "gsc_connected": True,
        "stealth": {"clicks": 60, "impressions": 1200},
        "totals": {"clicks": 200, "impressions": 4000},
        "start_date": "2026-04-28", "end_date": "2026-05-04",
    }
    fortnight = {
        "gsc_connected": True,
        "stealth": {"clicks": 100, "impressions": 2000},
        "totals": {"clicks": 350, "impressions": 7000},
    }
    monkeypatch.setattr(perf, "get_performance",
                        AsyncMock(side_effect=[this_week, fortnight]))
    res = await snap._headline_perf()
    # last_week stealth = 100 - 60 = 40 → delta = (60-40)/40*100 = 50%
    assert res["stealth_clicks_this_week"] == 60
    assert res["stealth_clicks_delta_pct"] == 50
    assert res["total_clicks_this_week"] == 200
    assert res["total_impressions_this_week"] == 4000


@pytest.mark.asyncio
async def test_headline_zero_last_week_returns_100(db, monkeypatch):
    from services import seo_dashboard_snapshot as snap
    from services import stealth_seo_performance as perf
    this_week = {
        "gsc_connected": True,
        "stealth": {"clicks": 25}, "totals": {},
    }
    fortnight = {
        "gsc_connected": True,
        "stealth": {"clicks": 25}, "totals": {},  # → last_week = 0
    }
    monkeypatch.setattr(perf, "get_performance",
                        AsyncMock(side_effect=[this_week, fortnight]))
    res = await snap._headline_perf()
    assert res["stealth_clicks_delta_pct"] == 100


# ───── _top_keyword ─────

@pytest.mark.asyncio
async def test_top_keyword_skips_zero_traffic(db, monkeypatch):
    from services import seo_dashboard_snapshot as snap
    from services import stealth_seo_kw_attribution as attr
    monkeypatch.setattr(attr, "get_attribution_timeline",
                        AsyncMock(return_value={"rows": [
                            {"keyword": "quiet-kw", "scope": "collection",
                             "target_label": "C", "clicks_total": 0,
                             "impressions_total": 0, "ctr": 0,
                             "roi_score": 0.1, "roi_band": "quiet",
                             "days_live": 14, "spark": [0] * 28},
                        ]}))
    res = await snap._top_keyword()
    assert res is None  # zero-click kw filtered out


@pytest.mark.asyncio
async def test_top_keyword_surfaces_winner(db, monkeypatch):
    from services import seo_dashboard_snapshot as snap
    from services import stealth_seo_kw_attribution as attr
    monkeypatch.setattr(attr, "get_attribution_timeline",
                        AsyncMock(return_value={"rows": [
                            {"keyword": "spanish tiles", "scope": "collection",
                             "target_label": "Spanish", "clicks_total": 47,
                             "impressions_total": 800, "ctr": 0.059,
                             "roi_score": 3.2, "roi_band": "winner",
                             "days_live": 21, "spark": [0] * 27 + [5]},
                        ]}))
    res = await snap._top_keyword()
    assert res["keyword"] == "spanish tiles"
    assert res["roi_band"] == "winner"
    assert res["clicks_total"] == 47
    assert len(res["spark"]) == 28


@pytest.mark.asyncio
async def test_top_keyword_empty_report(db, monkeypatch):
    from services import seo_dashboard_snapshot as snap
    from services import stealth_seo_kw_attribution as attr
    monkeypatch.setattr(attr, "get_attribution_timeline",
                        AsyncMock(return_value={"rows": []}))
    assert await snap._top_keyword() is None


# ───── _top_product ─────

@pytest.mark.asyncio
async def test_top_product_skips_zero_score(db, monkeypatch):
    from services import seo_dashboard_snapshot as snap
    from services import supplier_margin_intel as mi
    monkeypatch.setattr(mi, "get_margin_report",
                        AsyncMock(return_value={"top_revenue_gen": [
                            {"product_id": "t1", "name": "X",
                             "score": 0, "margin_pct": 60,
                             "impressions_this_week": 0},
                        ]}))
    assert await snap._top_product() is None


@pytest.mark.asyncio
async def test_top_product_surfaces_winner(db, monkeypatch):
    from services import seo_dashboard_snapshot as snap
    from services import supplier_margin_intel as mi
    monkeypatch.setattr(mi, "get_margin_report",
                        AsyncMock(return_value={"top_revenue_gen": [
                            {"product_id": "t1", "slug": "alabaster", "name": "Alabaster",
                             "image_url": "https://example.com/a.jpg",
                             "supplier_name": "LP", "collection": "Marble",
                             "price": 28.99, "margin_pct": 64.0,
                             "impressions_this_week": 250,
                             "impressions_delta_pct": 25.0, "score": 38.5},
                        ]}))
    res = await snap._top_product()
    assert res["product_id"] == "t1"
    assert res["margin_pct"] == 64.0


# ───── _auto_promote_summary ─────

@pytest.mark.asyncio
async def test_auto_promote_count_within_7_days(db):
    from services.seo_dashboard_snapshot import _auto_promote_summary
    now = datetime.now(timezone.utc)
    await db.seo_stealth_auto_promotes.insert_many([
        # In window (3 days ago) — counts
        {"id": "a1", "query": "spanish tiles", "scope": "collection",
         "collection": "Spanish", "promoted_at": now - timedelta(days=3),
         "undone_at": None, "impressions": 50},
        # Outside window (10 days ago) — excluded
        {"id": "a2", "query": "old kw", "scope": "collection",
         "collection": "Old", "promoted_at": now - timedelta(days=10),
         "undone_at": None, "impressions": 30},
        # Undone — excluded
        {"id": "a3", "query": "undone kw", "scope": "collection",
         "collection": "C", "promoted_at": now - timedelta(days=2),
         "undone_at": now, "impressions": 40},
        # City-page scope, in window — counts (with town label)
        {"id": "a4", "query": "tiles gravesend", "scope": "city_page",
         "city_slug": "tile-shop-gravesend", "town": "Gravesend",
         "promoted_at": now - timedelta(days=1), "undone_at": None,
         "impressions": 60},
    ])
    res = await _auto_promote_summary()
    assert res["count_this_week"] == 2
    queries = {r["query"] for r in res["recent"]}
    assert queries == {"spanish tiles", "tiles gravesend"}
    # City row uses town as target
    by_q = {r["query"]: r for r in res["recent"]}
    assert by_q["tiles gravesend"]["target"] == "Gravesend"
    assert by_q["tiles gravesend"]["scope"] == "city_page"
    assert by_q["spanish tiles"]["target"] == "Spanish"


@pytest.mark.asyncio
async def test_auto_promote_recent_capped_at_3(db):
    from services.seo_dashboard_snapshot import _auto_promote_summary
    now = datetime.now(timezone.utc)
    for i in range(5):
        await db.seo_stealth_auto_promotes.insert_one({
            "id": f"a{i}", "query": f"kw{i}", "scope": "collection",
            "collection": "C", "promoted_at": now - timedelta(hours=i),
            "undone_at": None, "impressions": 50,
        })
    res = await _auto_promote_summary()
    assert res["count_this_week"] == 5  # total
    assert len(res["recent"]) == 3       # capped


# ───── _health_summary ─────

@pytest.mark.asyncio
async def test_health_summary_all_green(db):
    """Now reads from `health_checks` (live monitor collection) with
    per-row label/healthy schema, not the old `seo_health_checks`."""
    from services.seo_dashboard_snapshot import _health_summary
    now = datetime.now(timezone.utc)
    await db.health_checks.insert_many([
        {"label": "homepage", "healthy": True, "checked_at": now},
        {"label": "sitemap", "healthy": True, "checked_at": now},
    ])
    res = await _health_summary()
    assert res["status"] == "all_green"
    assert res["ok_count"] == 2
    assert res["total_count"] == 2


@pytest.mark.asyncio
async def test_health_summary_warning(db):
    from services.seo_dashboard_snapshot import _health_summary
    now = datetime.now(timezone.utc)
    # 4 of 5 OK = 80% = "warning" boundary
    await db.health_checks.insert_many([
        {"label": "a", "healthy": True, "checked_at": now},
        {"label": "b", "healthy": True, "checked_at": now},
        {"label": "c", "healthy": True, "checked_at": now},
        {"label": "d", "healthy": True, "checked_at": now},
        {"label": "e", "healthy": False, "checked_at": now},
    ])
    res = await _health_summary()
    assert res["status"] == "warning"


@pytest.mark.asyncio
async def test_health_summary_critical(db):
    from services.seo_dashboard_snapshot import _health_summary
    now = datetime.now(timezone.utc)
    await db.health_checks.insert_many([
        {"label": "homepage", "healthy": False, "checked_at": now},
        {"label": "sitemap", "healthy": False, "checked_at": now},
        {"label": "products", "healthy": True, "checked_at": now},
    ])
    res = await _health_summary()
    assert res["status"] == "critical"
    assert "homepage" in res["first_failures"]


@pytest.mark.asyncio
async def test_health_summary_no_data(db):
    from services.seo_dashboard_snapshot import _health_summary
    assert await _health_summary() is None


# ───── _compose_alerts ─────

def test_alerts_gsc_disconnected():
    from services.seo_dashboard_snapshot import _compose_alerts
    snap = {"headline": {"gsc_connected": False}, "margin": {}, "auto_promote": {"count_this_week": 0}, "health": {}}
    alerts = _compose_alerts(snap)
    assert any(a["kind"] == "gsc_disconnected" for a in alerts)


def test_alerts_low_coverage():
    from services.seo_dashboard_snapshot import _compose_alerts
    snap = {
        "headline": {"gsc_connected": True},
        "margin": {"total_products": 1000, "with_organic_traffic": 5, "with_cost_data": 800},
        "auto_promote": {"count_this_week": 2},
        "health": {"status": "all_green"},
    }
    alerts = _compose_alerts(snap)
    assert any(a["kind"] == "low_coverage" for a in alerts)


def test_alerts_no_low_coverage_when_no_cost_data():
    """If cost_data is missing, the low-coverage alert should NOT
    fire — admin needs to fix cost data first, no point nagging
    about traffic."""
    from services.seo_dashboard_snapshot import _compose_alerts
    snap = {
        "headline": {"gsc_connected": True},
        "margin": {"total_products": 1000, "with_organic_traffic": 5, "with_cost_data": 0},
        "auto_promote": {"count_this_week": 2},
        "health": {"status": "all_green"},
    }
    alerts = _compose_alerts(snap)
    assert not any(a["kind"] == "low_coverage" for a in alerts)


def test_alerts_auto_promote_idle():
    from services.seo_dashboard_snapshot import _compose_alerts
    snap = {
        "headline": {"gsc_connected": True},
        "margin": {"total_products": 100, "with_organic_traffic": 50, "with_cost_data": 100},
        "auto_promote": {"count_this_week": 0},
        "health": {"status": "all_green"},
    }
    alerts = _compose_alerts(snap)
    assert any(a["kind"] == "auto_promote_idle" for a in alerts)


def test_alerts_health_critical():
    from services.seo_dashboard_snapshot import _compose_alerts
    snap = {
        "headline": {"gsc_connected": True},
        "margin": {"total_products": 100, "with_organic_traffic": 50, "with_cost_data": 100},
        "auto_promote": {"count_this_week": 5},
        "health": {"status": "critical", "ok_count": 1, "total_count": 5},
    }
    alerts = _compose_alerts(snap)
    crit = [a for a in alerts if a["kind"] == "health_critical"]
    assert len(crit) == 1
    assert crit[0]["severity"] == "critical"


def test_alerts_no_noise_on_healthy_state():
    """When everything's fine, no alerts should fire."""
    from services.seo_dashboard_snapshot import _compose_alerts
    snap = {
        "headline": {"gsc_connected": True},
        "margin": {"total_products": 100, "with_organic_traffic": 30, "with_cost_data": 90},
        "auto_promote": {"count_this_week": 3},
        "health": {"status": "all_green"},
    }
    alerts = _compose_alerts(snap)
    assert alerts == []


# ───── get_snapshot — full E2E ─────

@pytest.mark.asyncio
async def test_get_snapshot_resilient_when_one_section_fails(db, monkeypatch):
    """If one underlying service throws, the snapshot still returns
    with that section as None — no 500 error."""
    from services import seo_dashboard_snapshot as snap
    monkeypatch.setattr(snap, "_headline_perf",
                        AsyncMock(side_effect=RuntimeError("boom")))
    monkeypatch.setattr(snap, "_top_keyword",
                        AsyncMock(return_value={"keyword": "x", "spark": []}))
    monkeypatch.setattr(snap, "_top_product",
                        AsyncMock(return_value=None))
    monkeypatch.setattr(snap, "_margin_summary",
                        AsyncMock(return_value={"median_margin_pct": 60}))
    monkeypatch.setattr(snap, "_auto_promote_summary",
                        AsyncMock(return_value={"count_this_week": 0, "recent": []}))
    monkeypatch.setattr(snap, "_health_summary",
                        AsyncMock(return_value=None))
    res = await snap.get_snapshot()
    # headline failed → defaulted to {}
    assert res["headline"] == {}
    # other sections survive
    assert res["top_keyword"]["keyword"] == "x"
    assert res["top_product"] is None
    assert res["margin"]["median_margin_pct"] == 60
    assert "alerts" in res
    assert res["generated_at"]


@pytest.mark.asyncio
async def test_get_snapshot_full_happy_path(db, monkeypatch):
    from services import seo_dashboard_snapshot as snap
    monkeypatch.setattr(snap, "_headline_perf", AsyncMock(return_value={
        "stealth_clicks_this_week": 60, "stealth_clicks_delta_pct": 50,
        "total_clicks_this_week": 200, "total_impressions_this_week": 4000,
        "gsc_connected": True,
    }))
    monkeypatch.setattr(snap, "_top_keyword", AsyncMock(return_value={
        "keyword": "spanish tiles", "scope": "collection",
        "clicks_total": 47, "roi_band": "winner", "spark": [0] * 28,
    }))
    monkeypatch.setattr(snap, "_top_product", AsyncMock(return_value={
        "product_id": "t1", "name": "Alabaster", "margin_pct": 64,
        "impressions_this_week": 250, "score": 38.5,
    }))
    monkeypatch.setattr(snap, "_margin_summary", AsyncMock(return_value={
        "median_margin_pct": 64.1, "with_organic_traffic": 30,
        "with_cost_data": 90, "total_products": 100,
    }))
    monkeypatch.setattr(snap, "_auto_promote_summary", AsyncMock(return_value={
        "count_this_week": 3,
        "recent": [{"query": "x", "target": "Y", "scope": "collection"}],
    }))
    monkeypatch.setattr(snap, "_health_summary", AsyncMock(return_value={
        "status": "all_green", "ok_count": 5, "total_count": 5,
    }))
    res = await snap.get_snapshot()
    assert res["headline"]["stealth_clicks_delta_pct"] == 50
    assert res["top_keyword"]["roi_band"] == "winner"
    assert res["top_product"]["product_id"] == "t1"
    assert res["auto_promote"]["count_this_week"] == 3
    assert res["health"]["status"] == "all_green"
    # Healthy state → no alerts
    assert res["alerts"] == []

"""Tests for the Stealth-Keyword Attribution Timeline service."""
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
    test_db = client[f"test_kw_attr_{uuid.uuid4().hex[:8]}"]
    monkeypatch.setattr("services.stealth_seo_kw_attribution.get_db", lambda: test_db)
    monkeypatch.setattr("services.stealth_seo.get_db", lambda: test_db)
    yield test_db
    await client.drop_database(test_db.name)
    client.close()


# ───── _load_tracked_keywords ─────

@pytest.mark.asyncio
async def test_load_tracked_from_autopromote(db):
    from services.stealth_seo_kw_attribution import _load_tracked_keywords
    await db.seo_stealth_auto_promotes.insert_many([
        {"id": "a1", "query": "spanish tiles", "scope": "collection",
         "collection": "Spanish", "added_keyword": "spanish tiles",
         "promoted_at": datetime.now(timezone.utc) - timedelta(days=10),
         "undone_at": None},
        {"id": "a2", "query": "tiles gravesend", "scope": "city_page",
         "city_slug": "tile-shop-gravesend", "town": "Gravesend",
         "added_keyword": "tiles gravesend",
         "promoted_at": datetime.now(timezone.utc) - timedelta(days=5),
         "undone_at": None},
    ])
    rows = await _load_tracked_keywords()
    queries = {r["keyword"] for r in rows}
    assert queries == {"spanish tiles", "tiles gravesend"}
    scopes = {r["scope"] for r in rows}
    assert scopes == {"collection", "city_page"}


@pytest.mark.asyncio
async def test_load_tracked_skips_undone(db):
    from services.stealth_seo_kw_attribution import _load_tracked_keywords
    await db.seo_stealth_auto_promotes.insert_one({
        "id": "a1", "query": "spanish tiles", "scope": "collection",
        "collection": "Spanish", "added_keyword": "spanish tiles",
        "promoted_at": datetime.now(timezone.utc),
        "undone_at": datetime.now(timezone.utc),  # UNDONE
    })
    rows = await _load_tracked_keywords()
    assert rows == []


@pytest.mark.asyncio
async def test_load_tracked_merges_collection_ui(db):
    from services.stealth_seo_kw_attribution import _load_tracked_keywords
    await db.seo_collection_keywords.insert_one({
        "collection": "Marble",
        "keywords": ["Calacatta", "Carrara"],
        "updated_at": datetime.now(timezone.utc) - timedelta(days=3),
    })
    rows = await _load_tracked_keywords()
    kws = {r["keyword"] for r in rows}
    assert kws == {"Calacatta", "Carrara"}
    for r in rows:
        assert r["source"] == "admin_ui"
        assert r["scope"] == "collection"


@pytest.mark.asyncio
async def test_load_tracked_auto_promote_wins_over_admin_ui(db):
    """When the same kw appears in both sources, auto_promote row
    wins (has more context like `town` for city_page scope)."""
    from services.stealth_seo_kw_attribution import _load_tracked_keywords
    await db.seo_stealth_auto_promotes.insert_one({
        "id": "a1", "query": "spanish tiles", "scope": "collection",
        "collection": "Spanish", "added_keyword": "spanish tiles",
        "promoted_at": datetime.now(timezone.utc) - timedelta(days=10),
        "undone_at": None, "impressions": 49,
    })
    await db.seo_collection_keywords.insert_one({
        "collection": "Spanish",
        "keywords": ["spanish tiles"],
        "updated_at": datetime.now(timezone.utc),
    })
    rows = await _load_tracked_keywords()
    assert len(rows) == 1
    assert rows[0]["source"] == "auto_promote"
    assert rows[0]["promoted_impressions_at_add"] == 49


# ───── rebuild_timeline_cache ─────

@pytest.mark.asyncio
async def test_rebuild_no_gsc_returns_reason(db, monkeypatch):
    from services import stealth_seo_kw_attribution as attr
    monkeypatch.setattr(attr.gsc_service, "_pick_connected_admin",
                        AsyncMock(return_value=None))
    res = await attr.rebuild_timeline_cache()
    assert res["ok"] is False
    assert res["reason"] == "gsc_not_connected"


@pytest.mark.asyncio
async def test_rebuild_gsc_error_handled(db, monkeypatch):
    from services import stealth_seo_kw_attribution as attr
    await db.seo_stealth_auto_promotes.insert_one({
        "id": "a1", "query": "spanish tiles", "scope": "collection",
        "collection": "Spanish", "added_keyword": "spanish tiles",
        "promoted_at": datetime.now(timezone.utc),
        "undone_at": None,
    })
    monkeypatch.setattr(attr.gsc_service, "_pick_connected_admin",
                        AsyncMock(return_value="admin"))
    monkeypatch.setattr(attr.gsc_service, "get_daily_query_rows",
                        AsyncMock(side_effect=RuntimeError("boom")))
    res = await attr.rebuild_timeline_cache()
    assert res["ok"] is False
    assert res["reason"] == "gsc_error"


@pytest.mark.asyncio
async def test_rebuild_empty_tracked_returns_zero_rows(db, monkeypatch):
    from services import stealth_seo_kw_attribution as attr
    # No tracked keywords seeded — nothing to match against
    monkeypatch.setattr(attr.gsc_service, "_pick_connected_admin",
                        AsyncMock(return_value="admin"))
    monkeypatch.setattr(attr.gsc_service, "get_daily_query_rows",
                        AsyncMock(return_value={"rows": [
                            {"query": "spanish tiles", "date": "2026-05-01",
                             "clicks": 5, "impressions": 100, "ctr": 0.05, "position": 3},
                        ]}))
    res = await attr.rebuild_timeline_cache()
    assert res["ok"] is True
    assert res["tracked_kws"] == 0
    assert res["matched_pairs"] == 0
    # Regression (iter171 code review): early-return must still include
    # rebuilt_at so UI + downstream code has a consistent response shape
    assert "rebuilt_at" in res


@pytest.mark.asyncio
async def test_rebuild_writes_and_upserts(db, monkeypatch):
    from services import stealth_seo_kw_attribution as attr
    await db.seo_stealth_auto_promotes.insert_one({
        "id": "a1", "query": "spanish tiles", "scope": "collection",
        "collection": "Spanish", "added_keyword": "spanish tiles",
        "promoted_at": datetime.now(timezone.utc) - timedelta(days=10),
        "undone_at": None,
    })
    monkeypatch.setattr(attr.gsc_service, "_pick_connected_admin",
                        AsyncMock(return_value="admin"))
    monkeypatch.setattr(attr.gsc_service, "get_daily_query_rows",
                        AsyncMock(return_value={"rows": [
                            {"query": "spanish tiles uk", "date": "2026-05-01",
                             "clicks": 5, "impressions": 100, "ctr": 0.05, "position": 4.5},
                            {"query": "spanish tiles uk", "date": "2026-05-02",
                             "clicks": 8, "impressions": 120, "ctr": 0.067, "position": 3.8},
                            # Unmatched — should NOT land in cache
                            {"query": "how to grout floor", "date": "2026-05-01",
                             "clicks": 2, "impressions": 50, "ctr": 0.04, "position": 20},
                        ]}))
    res = await attr.rebuild_timeline_cache()
    assert res["ok"] is True
    assert res["tracked_kws"] == 1
    assert res["matched_pairs"] == 2  # both matching dates
    count = await db.seo_stealth_kw_timeline.count_documents({})
    assert count == 2

    # Upsert — second run with same data should not duplicate rows
    res2 = await attr.rebuild_timeline_cache()
    assert res2["ok"] is True
    count2 = await db.seo_stealth_kw_timeline.count_documents({})
    assert count2 == 2  # still 2 — upsert-safe


# ───── get_attribution_timeline — the read path ─────

@pytest.mark.asyncio
async def test_timeline_empty_universe(db):
    from services.stealth_seo_kw_attribution import get_attribution_timeline
    res = await get_attribution_timeline()
    assert res["rows"] == []
    assert res["summary"] == {}


@pytest.mark.asyncio
async def test_timeline_builds_sparkline_and_rollup(db):
    from services.stealth_seo_kw_attribution import get_attribution_timeline
    # Tracked keyword added 10 days ago
    await db.seo_stealth_auto_promotes.insert_one({
        "id": "a1", "query": "spanish tiles", "scope": "collection",
        "collection": "Spanish", "added_keyword": "spanish tiles",
        "promoted_at": datetime.now(timezone.utc) - timedelta(days=10),
        "undone_at": None,
    })
    # Seed 3 cache rows — days 27, 5, 3 (relative to today)
    today = datetime.now(timezone.utc)
    await db.seo_stealth_kw_timeline.insert_many([
        {"keyword_lower": "spanish tiles", "keyword": "spanish tiles",
         "date": (today - timedelta(days=5)).date().isoformat(),
         "clicks": 4, "impressions": 50, "ctr": 0.08, "position": 3.0,
         "cached_at": today},
        {"keyword_lower": "spanish tiles", "keyword": "spanish tiles",
         "date": (today - timedelta(days=3)).date().isoformat(),
         "clicks": 6, "impressions": 80, "ctr": 0.075, "position": 2.5,
         "cached_at": today},
        # Outside the window (41 days old) — should NOT count
        {"keyword_lower": "spanish tiles", "keyword": "spanish tiles",
         "date": (today - timedelta(days=41)).date().isoformat(),
         "clicks": 99, "impressions": 999, "ctr": 0.099, "position": 1,
         "cached_at": today},
    ])
    res = await get_attribution_timeline(days=28)
    assert len(res["rows"]) == 1
    row = res["rows"][0]
    assert row["keyword"] == "spanish tiles"
    assert row["clicks_total"] == 10  # 4 + 6 (the 41-day-old row excluded)
    assert row["impressions_total"] == 130
    assert row["days_live"] == 10
    assert row["clicks_per_day_live"] == round(10 / 10, 3)
    # Sparkline has 28 slots, oldest → newest
    assert len(row["spark"]) == 28
    # The 2 known clicks live at offsets 5 and 3 from today
    # spark[offset=28] = day -28, spark[27] = day -27, ... spark[0] = day -1
    # offset 5 → spark index 28-5 = 23, offset 3 → spark index 28-3 = 25
    assert row["spark"][23] == 4
    assert row["spark"][25] == 6
    # Other slots are 0
    assert sum(row["spark"]) == 10


@pytest.mark.asyncio
async def test_timeline_roi_score_band(db):
    """ROI score = kw_clicks / median_kw_clicks. Winners ≥ 1.5."""
    from services.stealth_seo_kw_attribution import get_attribution_timeline
    now = datetime.now(timezone.utc)
    for i, (q, clicks) in enumerate([
        ("winner-kw", 30),      # will be ROI ~3.0 if median=10
        ("median-kw-a", 10),
        ("median-kw-b", 10),
        ("quiet-kw", 1),
    ]):
        await db.seo_stealth_auto_promotes.insert_one({
            "id": f"a{i}", "query": q, "scope": "collection",
            "collection": "c", "added_keyword": q,
            "promoted_at": now - timedelta(days=14),
            "undone_at": None,
        })
        await db.seo_stealth_kw_timeline.insert_one({
            "keyword_lower": q, "keyword": q,
            "date": (now - timedelta(days=5)).date().isoformat(),
            "clicks": clicks, "impressions": clicks * 10,
            "ctr": 0.1, "position": 3, "cached_at": now,
        })
    res = await get_attribution_timeline()
    by_kw = {r["keyword"]: r for r in res["rows"]}
    assert by_kw["winner-kw"]["roi_band"] == "winner"
    assert by_kw["winner-kw"]["roi_score"] >= 1.5
    assert by_kw["quiet-kw"]["roi_band"] == "quiet"
    # Summary rolls-up correctly
    assert res["summary"]["tracked_kws"] == 4
    assert res["summary"]["with_traffic"] == 4
    assert res["summary"]["winners"] >= 1


@pytest.mark.asyncio
async def test_timeline_scope_filter(db):
    from services.stealth_seo_kw_attribution import get_attribution_timeline
    now = datetime.now(timezone.utc)
    await db.seo_stealth_auto_promotes.insert_many([
        {"id": "a1", "query": "collection-kw", "scope": "collection",
         "collection": "C", "added_keyword": "collection-kw",
         "promoted_at": now - timedelta(days=3), "undone_at": None},
        {"id": "a2", "query": "city-kw", "scope": "city_page",
         "city_slug": "tile-shop-gravesend", "town": "Gravesend",
         "added_keyword": "city-kw",
         "promoted_at": now - timedelta(days=3), "undone_at": None},
    ])
    res = await get_attribution_timeline(scope="city_page")
    assert len(res["rows"]) == 1
    assert res["rows"][0]["keyword"] == "city-kw"

    res2 = await get_attribution_timeline(scope="collection")
    assert len(res2["rows"]) == 1
    assert res2["rows"][0]["keyword"] == "collection-kw"


@pytest.mark.asyncio
async def test_timeline_min_days_live_filter(db):
    from services.stealth_seo_kw_attribution import get_attribution_timeline
    now = datetime.now(timezone.utc)
    await db.seo_stealth_auto_promotes.insert_many([
        {"id": "a1", "query": "young-kw", "scope": "collection",
         "collection": "C", "added_keyword": "young-kw",
         "promoted_at": now - timedelta(days=2), "undone_at": None},
        {"id": "a2", "query": "mature-kw", "scope": "collection",
         "collection": "C", "added_keyword": "mature-kw",
         "promoted_at": now - timedelta(days=20), "undone_at": None},
    ])
    res = await get_attribution_timeline(min_days_live=14)
    kws = {r["keyword"] for r in res["rows"]}
    assert "mature-kw" in kws
    assert "young-kw" not in kws


@pytest.mark.asyncio
async def test_timeline_sort_by_clicks_desc(db):
    from services.stealth_seo_kw_attribution import get_attribution_timeline
    now = datetime.now(timezone.utc)
    for i, (q, clicks) in enumerate([
        ("third", 5), ("first", 50), ("second", 20),
    ]):
        await db.seo_stealth_auto_promotes.insert_one({
            "id": f"a{i}", "query": q, "scope": "collection",
            "collection": "c", "added_keyword": q,
            "promoted_at": now - timedelta(days=5), "undone_at": None,
        })
        await db.seo_stealth_kw_timeline.insert_one({
            "keyword_lower": q, "keyword": q,
            "date": (now - timedelta(days=2)).date().isoformat(),
            "clicks": clicks, "impressions": clicks * 10,
            "ctr": 0.1, "position": 3, "cached_at": now,
        })
    res = await get_attribution_timeline()
    assert [r["keyword"] for r in res["rows"]] == ["first", "second", "third"]


@pytest.mark.asyncio
async def test_timeline_keyword_with_no_gsc_data_still_appears(db):
    """Critical: a keyword added 3 weeks ago with zero GSC hits MUST
    still show up in the list (with clicks=0) so the admin knows
    it's underperforming."""
    from services.stealth_seo_kw_attribution import get_attribution_timeline
    await db.seo_stealth_auto_promotes.insert_one({
        "id": "a1", "query": "no-traffic-kw", "scope": "collection",
        "collection": "c", "added_keyword": "no-traffic-kw",
        "promoted_at": datetime.now(timezone.utc) - timedelta(days=20),
        "undone_at": None,
    })
    res = await get_attribution_timeline()
    assert len(res["rows"]) == 1
    assert res["rows"][0]["clicks_total"] == 0
    assert res["rows"][0]["roi_band"] == "quiet"
    # Sparkline is still 28 zeros (not None / empty)
    assert res["rows"][0]["spark"] == [0] * 28

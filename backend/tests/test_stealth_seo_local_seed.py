"""Tests for the Stealth-Keyword Local Seeder (city-page targeting)."""
import os
import sys
import uuid

import pytest
import pytest_asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402


@pytest_asyncio.fixture
async def db(monkeypatch):
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    test_db = client[f"test_local_seed_{uuid.uuid4().hex[:8]}"]
    monkeypatch.setattr("services.stealth_seo_local_seed.get_db", lambda: test_db)
    monkeypatch.setattr("services.stealth_seo_auto_promote.get_db", lambda: test_db)
    monkeypatch.setattr("services.stealth_seo.get_db", lambda: test_db)
    monkeypatch.setattr("services.stealth_seo_digest.get_db", lambda: test_db)
    yield test_db
    await client.drop_database(test_db.name)
    client.close()


# ───── find_matching_city_page — the town detector ─────

def test_matcher_single_token_town():
    from services.stealth_seo_local_seed import find_matching_city_page
    pages = [
        {"slug": "tile-shop-gravesend", "town": "Gravesend",
         "town_lower": "gravesend", "town_slug": "gravesend",
         "intent_slug": "tile-shop", "intent_tokens": set()},
        {"slug": "tile-shop-brighton", "town": "Brighton",
         "town_lower": "brighton", "town_slug": "brighton",
         "intent_slug": "tile-shop", "intent_tokens": set()},
    ]
    match = find_matching_city_page("tiles gravesend", pages)
    assert match is not None
    assert match["slug"] == "tile-shop-gravesend"


def test_matcher_multi_word_town():
    """'Tunbridge Wells' is 2 tokens — both must appear in the query."""
    from services.stealth_seo_local_seed import find_matching_city_page
    pages = [
        {"slug": "tile-shop-tunbridge-wells", "town": "Tunbridge Wells",
         "town_lower": "tunbridge wells", "town_slug": "tunbridge-wells",
         "intent_slug": "tile-shop", "intent_tokens": set()},
    ]
    assert find_matching_city_page("tile shop tunbridge wells", pages) is not None
    assert find_matching_city_page("tile shop tunbridge only", pages) is None


def test_matcher_picks_best_intent_match():
    """When multiple pages exist for the same town, prefer the one
    whose intent tokens overlap most with the query."""
    from services.stealth_seo_local_seed import find_matching_city_page
    pages = [
        {"slug": "tile-shop-gravesend", "town": "Gravesend",
         "town_lower": "gravesend", "town_slug": "gravesend",
         "intent_slug": "tile-shop", "intent_tokens": {"shop"}},
        {"slug": "bathroom-tiles-gravesend", "town": "Gravesend",
         "town_lower": "gravesend", "town_slug": "gravesend",
         "intent_slug": "bathroom-tiles", "intent_tokens": {"bathroom"}},
    ]
    match = find_matching_city_page("bathroom tiles gravesend", pages)
    assert match["slug"] == "bathroom-tiles-gravesend"
    match = find_matching_city_page("tile shop gravesend", pages)
    assert match["slug"] == "tile-shop-gravesend"


def test_matcher_no_town_returns_none():
    from services.stealth_seo_local_seed import find_matching_city_page
    pages = [{"slug": "tile-shop-gravesend", "town": "Gravesend",
              "town_lower": "gravesend", "town_slug": "gravesend",
              "intent_slug": "tile-shop", "intent_tokens": set()}]
    assert find_matching_city_page("how to grout a floor", pages) is None
    assert find_matching_city_page("spanish tiles", pages) is None


def test_matcher_tiebreak_prefers_tile_shop():
    """When no intent tokens match, the broadest intent ("tile-shop") wins."""
    from services.stealth_seo_local_seed import find_matching_city_page
    pages = [
        {"slug": "porcelain-tiles-gravesend", "town": "Gravesend",
         "town_lower": "gravesend", "town_slug": "gravesend",
         "intent_slug": "porcelain-tiles", "intent_tokens": {"porcelain"}},
        {"slug": "tile-shop-gravesend", "town": "Gravesend",
         "town_lower": "gravesend", "town_slug": "gravesend",
         "intent_slug": "tile-shop", "intent_tokens": set()},
    ]
    # Query has no intent overlap with either, so tile-shop wins by fallback
    match = find_matching_city_page("tiles gravesend", pages)
    assert match["slug"] == "tile-shop-gravesend"


# ───── pick_local_candidates_from_digest ─────

@pytest.mark.asyncio
async def test_pick_local_happy_path(db):
    from services.stealth_seo_local_seed import pick_local_candidates_from_digest
    await db.city_landing_pages.insert_one({
        "slug": "tile-shop-gravesend", "town": "Gravesend",
        "town_slug": "gravesend", "intent_slug": "tile-shop",
        "intent_phrase": "tile shop", "status": "approved",
    })
    digest = {
        "gsc_connected": True,
        "new_missed": [
            {"query": "tiles gravesend", "impressions": 49, "clicks": 2},
            {"query": "spanish tiles", "impressions": 80, "clicks": 3},  # no town match
        ],
    }
    rows = await pick_local_candidates_from_digest(
        digest, min_impressions=20, max_count=1, impression_multiplier=1.0,
    )
    assert len(rows) == 1
    assert rows[0]["query"] == "tiles gravesend"
    assert rows[0]["slug"] == "tile-shop-gravesend"
    assert rows[0]["town"] == "Gravesend"


@pytest.mark.asyncio
async def test_pick_local_skips_already_seeded(db):
    from services.stealth_seo_local_seed import pick_local_candidates_from_digest
    await db.city_landing_pages.insert_one({
        "slug": "tile-shop-gravesend", "town": "Gravesend",
        "town_slug": "gravesend", "intent_slug": "tile-shop",
        "intent_phrase": "tile shop", "status": "approved",
        "hidden_seo_keywords": "tiles gravesend",
    })
    digest = {"gsc_connected": True,
              "new_missed": [{"query": "tiles gravesend", "impressions": 50, "clicks": 1}]}
    rows = await pick_local_candidates_from_digest(
        digest, min_impressions=20, max_count=1, impression_multiplier=1.0,
    )
    assert rows == []


@pytest.mark.asyncio
async def test_pick_local_respects_2x_threshold(db):
    from services.stealth_seo_local_seed import pick_local_candidates_from_digest
    await db.city_landing_pages.insert_one({
        "slug": "tile-shop-gravesend", "town": "Gravesend",
        "town_slug": "gravesend", "intent_slug": "tile-shop",
        "intent_phrase": "tile shop", "status": "approved",
    })
    digest = {"gsc_connected": True,
              "new_missed": [{"query": "tiles gravesend", "impressions": 30, "clicks": 0}]}
    # min=20 × 2.0 = effective 40. 30 < 40 → no pick
    rows = await pick_local_candidates_from_digest(
        digest, min_impressions=20, max_count=5, impression_multiplier=2.0,
    )
    assert rows == []


@pytest.mark.asyncio
async def test_pick_local_one_per_page_guard(db):
    """Two queries both mapping to the same city-page should produce
    only ONE promotion (highest impressions wins)."""
    from services.stealth_seo_local_seed import pick_local_candidates_from_digest
    await db.city_landing_pages.insert_one({
        "slug": "tile-shop-gravesend", "town": "Gravesend",
        "town_slug": "gravesend", "intent_slug": "tile-shop",
        "intent_phrase": "tile shop", "status": "approved",
    })
    digest = {
        "gsc_connected": True,
        "new_missed": [
            {"query": "tiles gravesend", "impressions": 80, "clicks": 2},
            {"query": "tile shop gravesend", "impressions": 60, "clicks": 1},
        ],
    }
    rows = await pick_local_candidates_from_digest(
        digest, min_impressions=20, max_count=5, impression_multiplier=1.0,
    )
    assert len(rows) == 1
    assert rows[0]["query"] == "tiles gravesend"  # highest impr


@pytest.mark.asyncio
async def test_pick_local_skips_unpublished_statuses(db):
    from services.stealth_seo_local_seed import pick_local_candidates_from_digest
    await db.city_landing_pages.insert_one({
        "slug": "tile-shop-gravesend", "town": "Gravesend",
        "town_slug": "gravesend", "intent_slug": "tile-shop",
        "intent_phrase": "tile shop", "status": "rejected",
    })
    digest = {"gsc_connected": True,
              "new_missed": [{"query": "tiles gravesend", "impressions": 50, "clicks": 0}]}
    rows = await pick_local_candidates_from_digest(
        digest, min_impressions=20, max_count=1, impression_multiplier=1.0,
    )
    assert rows == []


# ───── apply_local_seed — writes + records ─────

@pytest.mark.asyncio
async def test_apply_writes_to_city_page_and_records(db):
    from services.stealth_seo_local_seed import apply_local_seed
    await db.city_landing_pages.insert_one({
        "slug": "tile-shop-gravesend", "town": "Gravesend",
        "town_slug": "gravesend", "intent_slug": "tile-shop",
        "intent_phrase": "tile shop", "status": "approved",
    })
    record = await apply_local_seed({
        "query": "tiles gravesend", "slug": "tile-shop-gravesend",
        "town": "Gravesend", "intent_slug": "tile-shop",
        "impressions": 49, "clicks": 2, "position": 15.0,
    })
    assert record["scope"] == "city_page"
    assert record["city_slug"] == "tile-shop-gravesend"
    assert record["token"] and len(record["token"]) > 20
    # Keyword applied to city page
    page = await db.city_landing_pages.find_one(
        {"slug": "tile-shop-gravesend"}, {"_id": 0, "hidden_seo_keywords": 1},
    )
    assert "tiles gravesend" in (page.get("hidden_seo_keywords") or "")
    # Audit row persisted with scope=city_page
    count = await db.seo_stealth_auto_promotes.count_documents({"scope": "city_page"})
    assert count == 1


@pytest.mark.asyncio
async def test_apply_preserves_existing_kws(db):
    from services.stealth_seo_local_seed import apply_local_seed
    await db.city_landing_pages.insert_one({
        "slug": "tile-shop-gravesend", "town": "Gravesend",
        "town_slug": "gravesend", "intent_slug": "tile-shop",
        "intent_phrase": "tile shop", "status": "approved",
        "hidden_seo_keywords": "existing-kw-1, existing-kw-2",
    })
    await apply_local_seed({
        "query": "tiles gravesend", "slug": "tile-shop-gravesend",
        "town": "Gravesend", "intent_slug": "tile-shop",
        "impressions": 49, "clicks": 0,
    })
    page = await db.city_landing_pages.find_one(
        {"slug": "tile-shop-gravesend"}, {"_id": 0, "hidden_seo_keywords": 1},
    )
    kws = page["hidden_seo_keywords"]
    assert "existing-kw-1" in kws and "existing-kw-2" in kws
    assert "tiles gravesend" in kws


@pytest.mark.asyncio
async def test_apply_25_cap_drops_oldest_not_newest(db):
    """Regression: when the city-page is at the 25-kw cap, a new seed
    should push out the OLDEST entry and land at the end — not get
    silently dropped. (iter170 code review item.)"""
    from services.stealth_seo_local_seed import apply_local_seed
    existing_25 = ", ".join(f"old-kw-{i}" for i in range(25))
    await db.city_landing_pages.insert_one({
        "slug": "tile-shop-gravesend", "town": "Gravesend",
        "town_slug": "gravesend", "intent_slug": "tile-shop",
        "intent_phrase": "tile shop", "status": "approved",
        "hidden_seo_keywords": existing_25,
    })
    await apply_local_seed({
        "query": "tiles gravesend", "slug": "tile-shop-gravesend",
        "town": "Gravesend", "intent_slug": "tile-shop",
        "impressions": 49, "clicks": 0,
    })
    page = await db.city_landing_pages.find_one(
        {"slug": "tile-shop-gravesend"}, {"_id": 0, "hidden_seo_keywords": 1},
    )
    kws = [s.strip() for s in (page["hidden_seo_keywords"] or "").split(",") if s.strip()]
    # Exactly 25 (cap enforced)
    assert len(kws) == 25
    # New kw IS there
    assert "tiles gravesend" in kws
    # Oldest kw was evicted
    assert "old-kw-0" not in kws
    # Most recent old kws still present
    assert "old-kw-24" in kws


# ───── Undo via shared auto_promote.undo_by_token (scope dispatch) ─────

@pytest.mark.asyncio
async def test_undo_city_page_scope_removes_from_city_page(db):
    from services.stealth_seo_local_seed import apply_local_seed
    from services.stealth_seo_auto_promote import undo_by_token
    await db.city_landing_pages.insert_one({
        "slug": "tile-shop-gravesend", "town": "Gravesend",
        "town_slug": "gravesend", "intent_slug": "tile-shop",
        "intent_phrase": "tile shop", "status": "approved",
    })
    rec = await apply_local_seed({
        "query": "tiles gravesend", "slug": "tile-shop-gravesend",
        "town": "Gravesend", "intent_slug": "tile-shop",
        "impressions": 49, "clicks": 0,
    })
    res = await undo_by_token(rec["token"])
    assert res["ok"] is True
    assert res["kw_was_present_at_undo"] is True
    page = await db.city_landing_pages.find_one(
        {"slug": "tile-shop-gravesend"}, {"_id": 0, "hidden_seo_keywords": 1},
    )
    # Keyword removed
    assert "tiles gravesend" not in (page.get("hidden_seo_keywords") or "")


@pytest.mark.asyncio
async def test_undo_still_works_for_collection_scope(db):
    """Regression: make sure the scope-dispatch in undo_by_token
    didn't break the collection-scope path."""
    from services.stealth_seo_auto_promote import apply_auto_promote, undo_by_token
    from services.stealth_seo import get_collection_keywords
    await db.tiles.insert_one({"id": "t1", "is_active": True, "collection": "Spanish"})
    rec = await apply_auto_promote({
        "query": "spanish tiles", "collection": "Spanish",
        "impressions": 49, "clicks": 0,
    })
    res = await undo_by_token(rec["token"])
    assert res["ok"] is True
    assert "spanish tiles" not in await get_collection_keywords("Spanish")


# ───── run_once — local seeder dispatcher ─────

@pytest.mark.asyncio
async def test_run_once_disabled(db):
    from services.stealth_seo_local_seed import run_once
    res = await run_once(
        {"gsc_connected": True, "new_missed": []},
        {"auto_local_seed_enabled": False, "auto_promote_enabled": True},
    )
    assert res == []


@pytest.mark.asyncio
async def test_run_once_needs_auto_promote_enabled(db):
    """Local seed piggy-backs on auto_promote_enabled — if AP is off,
    local seed is off even when its own flag is on."""
    from services.stealth_seo_local_seed import run_once
    await db.city_landing_pages.insert_one({
        "slug": "tile-shop-gravesend", "town": "Gravesend",
        "town_slug": "gravesend", "intent_slug": "tile-shop",
        "intent_phrase": "tile shop", "status": "approved",
    })
    digest = {"gsc_connected": True,
              "new_missed": [{"query": "tiles gravesend", "impressions": 50}]}
    # auto_promote_enabled explicitly False
    res = await run_once(digest, {
        "auto_local_seed_enabled": True, "auto_promote_enabled": False,
        "auto_promote_min_impressions": 20,
    })
    assert res == []


@pytest.mark.asyncio
async def test_run_once_happy_path(db):
    from services.stealth_seo_local_seed import run_once
    await db.city_landing_pages.insert_one({
        "slug": "tile-shop-gravesend", "town": "Gravesend",
        "town_slug": "gravesend", "intent_slug": "tile-shop",
        "intent_phrase": "tile shop", "status": "approved",
    })
    digest = {"gsc_connected": True,
              "new_missed": [{"query": "tiles gravesend", "impressions": 50}]}
    res = await run_once(digest, {
        "auto_local_seed_enabled": True, "auto_promote_enabled": True,
        "auto_promote_min_impressions": 20,
    })
    assert len(res) == 1
    assert res[0]["query"] == "tiles gravesend"


@pytest.mark.asyncio
async def test_run_once_batch_mode_caps(db):
    from services.stealth_seo_local_seed import run_once
    await db.city_landing_pages.insert_many([
        {"slug": "tile-shop-gravesend", "town": "Gravesend",
         "town_slug": "gravesend", "intent_slug": "tile-shop",
         "intent_phrase": "tile shop", "status": "approved"},
        {"slug": "tile-shop-brighton", "town": "Brighton",
         "town_slug": "brighton", "intent_slug": "tile-shop",
         "intent_phrase": "tile shop", "status": "approved"},
        {"slug": "tile-shop-canterbury", "town": "Canterbury",
         "town_slug": "canterbury", "intent_slug": "tile-shop",
         "intent_phrase": "tile shop", "status": "approved"},
    ])
    digest = {"gsc_connected": True, "new_missed": [
        {"query": "tiles gravesend", "impressions": 100, "clicks": 0},
        {"query": "tiles brighton", "impressions": 80, "clicks": 0},
        {"query": "tiles canterbury", "impressions": 60, "clicks": 0},
    ]}
    # Batch mode cap=2, 2x multiplier, min=20 → effective 40 (all qualify)
    res = await run_once(digest, {
        "auto_local_seed_enabled": True, "auto_promote_enabled": True,
        "auto_promote_min_impressions": 20,
        "auto_promote_batch_mode": True, "auto_promote_batch_max": 2,
    })
    assert len(res) == 2
    assert {r["town"] for r in res} == {"Gravesend", "Brighton"}


# ───── Settings whitelist for new flag ─────

@pytest.mark.asyncio
async def test_settings_local_seed_flag(db):
    from services.stealth_seo_digest import update_settings, get_settings
    await update_settings({"auto_local_seed_enabled": True})
    assert (await get_settings())["auto_local_seed_enabled"] is True


# ───── Budget coordination via the digest cron ─────

@pytest.mark.asyncio
async def test_digest_cron_local_seed_consumes_from_shared_budget(db, monkeypatch):
    """When local seed promotes 2 and batch_max=5, collection auto-promote
    should only be allowed to promote up to 3 more (5 - 2)."""
    from unittest.mock import AsyncMock, patch
    from services import stealth_seo_digest as dig

    await db.city_landing_pages.insert_many([
        {"slug": "tile-shop-gravesend", "town": "Gravesend",
         "town_slug": "gravesend", "intent_slug": "tile-shop",
         "intent_phrase": "tile shop", "status": "approved"},
        {"slug": "tile-shop-brighton", "town": "Brighton",
         "town_slug": "brighton", "intent_slug": "tile-shop",
         "intent_phrase": "tile shop", "status": "approved"},
    ])
    await db.tiles.insert_many([
        {"id": "t1", "is_active": True, "collection": "Spanish"},
        {"id": "t2", "is_active": True, "collection": "Terrazzo"},
    ])
    await dig.update_settings({
        "enabled": True, "auto_promote_enabled": True,
        "auto_local_seed_enabled": True,
        "auto_promote_batch_mode": True, "auto_promote_batch_max": 5,
        "auto_promote_min_impressions": 20,
    })

    fake_this = {
        "gsc_connected": True,
        "totals": {"clicks": 100, "impressions": 2000, "ctr": 0.05, "queries_count": 10},
        "stealth": {"clicks": 10, "impressions": 100, "ctr": 0.1, "queries_count": 1, "share_pct": 10},
        "brand": {"clicks": 0, "impressions": 0, "ctr": 0, "queries_count": 0, "share_pct": 0},
        "other": {"clicks": 90, "impressions": 1900, "ctr": 0.047, "queries_count": 9, "share_pct": 90},
        "top_winners": [],
        "missed_wins": [
            {"query": "tiles gravesend", "impressions": 100, "clicks": 0, "ctr": 0, "position": 10},
            {"query": "tiles brighton", "impressions": 80, "clicks": 0, "ctr": 0, "position": 12},
            {"query": "spanish tiles", "impressions": 70, "clicks": 0, "ctr": 0, "position": 15},
            {"query": "terrazzo tiles", "impressions": 60, "clicks": 0, "ctr": 0, "position": 18},
        ],
        "underperformers": [],
        "start_date": "2026-04-28", "end_date": "2026-05-04",
    }
    fake_fortnight = {**fake_this, "stealth": {**fake_this["stealth"], "clicks": 15},
                       "missed_wins": []}
    monkeypatch.setenv("ADMIN_EMAIL", "admin@x.com")
    send_mock = AsyncMock(return_value=True)
    perf_mock = AsyncMock(side_effect=[fake_this, fake_fortnight,
                                         fake_this, fake_fortnight])
    with patch("services.stealth_seo_performance.get_performance", perf_mock), \
         patch("services.email.send_email_notification", send_mock):
        res = await dig.run_weekly_digest_if_due()
    # Local seed picked 2 (gravesend + brighton), collection picked 2 more
    # (spanish + terrazzo), total = 4 — all under the batch_max=5
    promoted = res.get("auto_promoted") or []
    # Assert BOTH scopes are represented
    scopes = {p["scope"] for p in promoted}
    assert "city_page" in scopes
    assert "collection" in scopes
    # Assert total ≤ batch_max
    assert len(promoted) <= 5

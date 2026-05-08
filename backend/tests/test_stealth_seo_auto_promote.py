"""Tests for the Stealth-Keyword Auto-Promote feature."""
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
    test_db = client[f"test_stealth_ap_{uuid.uuid4().hex[:8]}"]
    # Both the auto-promote module AND the stealth_seo module it
    # delegates into share the same test DB
    monkeypatch.setattr("services.stealth_seo_auto_promote.get_db", lambda: test_db)
    monkeypatch.setattr("services.stealth_seo.get_db", lambda: test_db)
    monkeypatch.setattr("services.stealth_seo_digest.get_db", lambda: test_db)
    yield test_db
    await client.drop_database(test_db.name)
    client.close()


# ───── _find_matching_collection — the fuzzy matcher ─────

@pytest.mark.asyncio
async def test_find_matching_single_token(db):
    from services.stealth_seo_auto_promote import _find_matching_collection
    coll = await _find_matching_collection(
        "spanish tiles uk", ["Spanish", "Marble Effect", "Terrazzo"]
    )
    assert coll == "Spanish"


@pytest.mark.asyncio
async def test_find_matching_prefers_most_specific(db):
    """When 'calacatta marble' matches both 'Marble' and 'Marble Calacatta',
    the more specific (longer) match wins."""
    from services.stealth_seo_auto_promote import _find_matching_collection
    coll = await _find_matching_collection(
        "calacatta marble tile uk",
        ["Marble", "Marble Calacatta", "Terrazzo"],
    )
    assert coll == "Marble Calacatta"


@pytest.mark.asyncio
async def test_find_matching_requires_all_tokens(db):
    """Collection 'Marble Effect' needs both 'marble' AND 'effect' in the query."""
    from services.stealth_seo_auto_promote import _find_matching_collection
    coll = await _find_matching_collection(
        "calacatta marble tile uk", ["Marble Effect"],
    )
    assert coll is None  # 'effect' not in query


@pytest.mark.asyncio
async def test_find_matching_strips_stopwords(db):
    """'tile(s)' and 'the/a/uk/...' don't count as meaningful tokens."""
    from services.stealth_seo_auto_promote import _find_matching_collection
    coll = await _find_matching_collection(
        "buy tiles uk best", ["Tiles UK"]  # both tokens are stopwords
    )
    assert coll is None  # nothing meaningful to match on


@pytest.mark.asyncio
async def test_find_matching_no_match_returns_none(db):
    from services.stealth_seo_auto_promote import _find_matching_collection
    assert await _find_matching_collection(
        "how to grout a floor", ["Marble", "Terrazzo"],
    ) is None


# ───── pick_candidate_from_digest — the gate ─────

@pytest.mark.asyncio
async def test_pick_candidate_happy_path(db):
    from services.stealth_seo_auto_promote import pick_candidate_from_digest
    # Seed real active tiles so _list_active_collections returns them
    await db.tiles.insert_many([
        {"id": "t1", "is_active": True, "collection": "Spanish"},
        {"id": "t2", "is_active": True, "collection": "Marble Effect"},
    ])
    digest = {
        "gsc_connected": True,
        "new_missed": [
            {"query": "spanish tiles uk", "impressions": 49, "clicks": 2, "position": 15.1},
            {"query": "cheap subway tiles", "impressions": 30, "clicks": 0, "position": 20},
        ],
    }
    cand = await pick_candidate_from_digest(digest, min_impressions=20)
    assert cand is not None
    assert cand["query"] == "spanish tiles uk"
    assert cand["collection"] == "Spanish"
    assert cand["impressions"] == 49


@pytest.mark.asyncio
async def test_pick_candidate_skips_below_threshold(db):
    from services.stealth_seo_auto_promote import pick_candidate_from_digest
    await db.tiles.insert_one({"id": "t1", "is_active": True, "collection": "Spanish"})
    digest = {
        "gsc_connected": True,
        "new_missed": [
            {"query": "spanish tiles", "impressions": 10, "clicks": 0},  # below threshold
        ],
    }
    assert await pick_candidate_from_digest(digest, min_impressions=20) is None


@pytest.mark.asyncio
async def test_pick_candidate_skips_no_collection_match(db):
    from services.stealth_seo_auto_promote import pick_candidate_from_digest
    await db.tiles.insert_one({"id": "t1", "is_active": True, "collection": "Spanish"})
    digest = {
        "gsc_connected": True,
        "new_missed": [
            {"query": "porcelain tile uk", "impressions": 100, "clicks": 3},
        ],
    }
    assert await pick_candidate_from_digest(digest, min_impressions=20) is None


@pytest.mark.asyncio
async def test_pick_candidate_skips_if_already_in_collection_keywords(db):
    from services.stealth_seo_auto_promote import pick_candidate_from_digest
    await db.tiles.insert_one({"id": "t1", "is_active": True, "collection": "Spanish"})
    await db.seo_collection_keywords.insert_one({
        "collection": "Spanish", "keywords": ["spanish tiles uk"],
    })
    digest = {
        "gsc_connected": True,
        "new_missed": [
            {"query": "spanish tiles uk", "impressions": 49, "clicks": 2},
        ],
    }
    assert await pick_candidate_from_digest(digest, min_impressions=20) is None


@pytest.mark.asyncio
async def test_pick_candidate_no_gsc_returns_none(db):
    from services.stealth_seo_auto_promote import pick_candidate_from_digest
    digest = {"gsc_connected": False, "new_missed": [
        {"query": "spanish tiles", "impressions": 100},
    ]}
    assert await pick_candidate_from_digest(digest, min_impressions=20) is None


# ───── apply_auto_promote — write + record ─────

@pytest.mark.asyncio
async def test_apply_writes_keyword_and_record(db):
    from services.stealth_seo_auto_promote import apply_auto_promote
    from services.stealth_seo import get_collection_keywords
    await db.tiles.insert_one({"id": "t1", "is_active": True, "collection": "Spanish"})

    record = await apply_auto_promote({
        "query": "spanish tiles uk", "collection": "Spanish",
        "impressions": 49, "clicks": 2, "position": 15.1,
    })
    assert record["token"]
    assert len(record["token"]) > 20  # URL-safe 24-byte token is longer than 20 chars
    # Keyword applied to collection
    assert "spanish tiles uk" in await get_collection_keywords("Spanish")
    # History row persisted
    count = await db.seo_stealth_auto_promotes.count_documents({})
    assert count == 1


# ───── undo_by_token — reversal ─────

@pytest.mark.asyncio
async def test_undo_removes_keyword_and_stamps(db):
    from services.stealth_seo_auto_promote import apply_auto_promote, undo_by_token
    from services.stealth_seo import get_collection_keywords
    await db.tiles.insert_one({"id": "t1", "is_active": True, "collection": "Spanish"})
    rec = await apply_auto_promote({
        "query": "spanish tiles", "collection": "Spanish",
        "impressions": 49, "clicks": 0,
    })
    res = await undo_by_token(rec["token"])
    assert res["ok"] is True
    assert res["already_undone"] is False
    # Keyword gone
    assert "spanish tiles" not in await get_collection_keywords("Spanish")
    # Stamped
    row = await db.seo_stealth_auto_promotes.find_one({"token": rec["token"]})
    assert row["undone_at"] is not None


@pytest.mark.asyncio
async def test_undo_idempotent(db):
    from services.stealth_seo_auto_promote import apply_auto_promote, undo_by_token
    await db.tiles.insert_one({"id": "t1", "is_active": True, "collection": "Spanish"})
    rec = await apply_auto_promote({
        "query": "spanish tiles", "collection": "Spanish",
        "impressions": 49, "clicks": 0,
    })
    r1 = await undo_by_token(rec["token"])
    r2 = await undo_by_token(rec["token"])
    assert r1["ok"] is True and r1["already_undone"] is False
    assert r2["ok"] is True and r2["already_undone"] is True


@pytest.mark.asyncio
async def test_undo_unknown_token(db):
    from services.stealth_seo_auto_promote import undo_by_token
    res = await undo_by_token("bogus")
    assert res["ok"] is False and res["reason"] == "not_found"


@pytest.mark.asyncio
async def test_undo_by_record_id_single_query_path(db):
    """Admin-UI path — undo_by_record_id is idempotent and correctly
    surfaces the same kw_was_present_at_undo flag as the token path."""
    from services.stealth_seo_auto_promote import apply_auto_promote, undo_by_record_id
    await db.tiles.insert_one({"id": "t1", "is_active": True, "collection": "Spanish"})
    rec = await apply_auto_promote({
        "query": "spanish tiles", "collection": "Spanish",
        "impressions": 49, "clicks": 0,
    })
    res = await undo_by_record_id(rec["id"])
    assert res["ok"] is True
    assert res["kw_was_present_at_undo"] is True
    # Unknown id
    assert (await undo_by_record_id("nope"))["ok"] is False


@pytest.mark.asyncio
async def test_undo_flags_when_kw_already_removed(db):
    """If an admin manually removed the keyword between promote and
    undo, kw_was_present_at_undo is False (useful for audit debugging)."""
    from services.stealth_seo_auto_promote import apply_auto_promote, undo_by_token
    from services.stealth_seo import set_collection_keywords
    await db.tiles.insert_one({"id": "t1", "is_active": True, "collection": "Spanish"})
    rec = await apply_auto_promote({
        "query": "spanish tiles", "collection": "Spanish",
        "impressions": 49, "clicks": 0,
    })
    # Manually clear the collection's kws
    await set_collection_keywords("Spanish", [])
    res = await undo_by_token(rec["token"])
    assert res["ok"] is True
    assert res["kw_was_present_at_undo"] is False


# ───── run_once — end-to-end (with digest + settings) ─────

@pytest.mark.asyncio
async def test_run_once_skipped_when_disabled(db):
    from services.stealth_seo_auto_promote import run_once
    out = await run_once(
        {"gsc_connected": True, "new_missed": []},
        {"auto_promote_enabled": False, "auto_promote_min_impressions": 20},
    )
    assert out == []


@pytest.mark.asyncio
async def test_run_once_happy_path(db):
    from services.stealth_seo_auto_promote import run_once
    from services.stealth_seo import get_collection_keywords
    await db.tiles.insert_one({"id": "t1", "is_active": True, "collection": "Spanish"})
    digest = {
        "gsc_connected": True,
        "new_missed": [{"query": "spanish tiles uk", "impressions": 49, "clicks": 2}],
    }
    settings = {"auto_promote_enabled": True, "auto_promote_min_impressions": 20}
    records = await run_once(digest, settings)
    assert len(records) == 1
    assert records[0]["query"] == "spanish tiles uk"
    assert records[0]["collection"] == "Spanish"
    assert "spanish tiles uk" in await get_collection_keywords("Spanish")


@pytest.mark.asyncio
async def test_run_once_returns_none_when_no_candidate(db):
    from services.stealth_seo_auto_promote import run_once
    await db.tiles.insert_one({"id": "t1", "is_active": True, "collection": "Spanish"})
    digest = {
        "gsc_connected": True,
        "new_missed": [{"query": "how to grout a floor", "impressions": 100}],
    }
    settings = {"auto_promote_enabled": True, "auto_promote_min_impressions": 20}
    assert await run_once(digest, settings) == []


# ───── Batch mode ─────

@pytest.mark.asyncio
async def test_pick_candidates_single_mode_returns_max_1(db):
    from services.stealth_seo_auto_promote import pick_candidates_from_digest
    await db.tiles.insert_many([
        {"id": "t1", "is_active": True, "collection": "Spanish"},
        {"id": "t2", "is_active": True, "collection": "Terrazzo"},
    ])
    digest = {
        "gsc_connected": True,
        "new_missed": [
            {"query": "spanish tiles", "impressions": 49, "clicks": 2},
            {"query": "terrazzo tiles", "impressions": 30, "clicks": 0},
        ],
    }
    rows = await pick_candidates_from_digest(
        digest, min_impressions=20, max_count=1, impression_multiplier=1.0,
    )
    assert len(rows) == 1
    assert rows[0]["query"] == "spanish tiles"  # highest impressions


@pytest.mark.asyncio
async def test_pick_candidates_batch_mode_applies_2x_threshold(db):
    """min=20 + multiplier=2.0 = effective threshold 40. Queries below
    40 must be excluded even if they'd qualify at the base threshold."""
    from services.stealth_seo_auto_promote import pick_candidates_from_digest
    await db.tiles.insert_many([
        {"id": "t1", "is_active": True, "collection": "Spanish"},
        {"id": "t2", "is_active": True, "collection": "Terrazzo"},
        {"id": "t3", "is_active": True, "collection": "Onyx"},
    ])
    digest = {
        "gsc_connected": True,
        "new_missed": [
            {"query": "spanish tiles", "impressions": 49, "clicks": 2},   # ≥40 ✓
            {"query": "terrazzo tiles", "impressions": 60, "clicks": 3},  # ≥40 ✓
            {"query": "onyx tiles", "impressions": 30, "clicks": 1},      # <40 ✗
        ],
    }
    rows = await pick_candidates_from_digest(
        digest, min_impressions=20, max_count=5, impression_multiplier=2.0,
    )
    queries = {r["query"] for r in rows}
    assert queries == {"terrazzo tiles", "spanish tiles"}
    assert "onyx tiles" not in queries


@pytest.mark.asyncio
async def test_pick_candidates_batch_caps_at_max_count(db):
    from services.stealth_seo_auto_promote import pick_candidates_from_digest
    await db.tiles.insert_many([
        {"id": "t1", "is_active": True, "collection": "Spanish"},
        {"id": "t2", "is_active": True, "collection": "Terrazzo"},
        {"id": "t3", "is_active": True, "collection": "Onyx"},
        {"id": "t4", "is_active": True, "collection": "Marble"},
    ])
    digest = {
        "gsc_connected": True,
        "new_missed": [
            {"query": "spanish tiles", "impressions": 100, "clicks": 0},
            {"query": "terrazzo tiles", "impressions": 90, "clicks": 0},
            {"query": "onyx tiles", "impressions": 80, "clicks": 0},
            {"query": "marble tiles", "impressions": 70, "clicks": 0},
        ],
    }
    rows = await pick_candidates_from_digest(
        digest, min_impressions=20, max_count=2, impression_multiplier=2.0,
    )
    assert len(rows) == 2
    # Top 2 by impressions
    assert [r["query"] for r in rows] == ["spanish tiles", "terrazzo tiles"]


@pytest.mark.asyncio
async def test_pick_candidates_one_per_collection_guard(db):
    """Two distinct queries both mapping to the same collection should
    only result in ONE promotion (prevents burying a collection under
    multiple new kws in a single run)."""
    from services.stealth_seo_auto_promote import pick_candidates_from_digest
    await db.tiles.insert_one({"id": "t1", "is_active": True, "collection": "Spanish"})
    digest = {
        "gsc_connected": True,
        "new_missed": [
            {"query": "spanish tiles uk", "impressions": 80, "clicks": 2},
            # Second query ALSO maps to Spanish collection
            {"query": "spanish style tiles", "impressions": 70, "clicks": 1},
        ],
    }
    rows = await pick_candidates_from_digest(
        digest, min_impressions=20, max_count=5, impression_multiplier=2.0,
    )
    assert len(rows) == 1
    # Top by impressions wins
    assert rows[0]["query"] == "spanish tiles uk"


@pytest.mark.asyncio
async def test_run_once_batch_mode_promotes_multiple(db):
    from services.stealth_seo_auto_promote import run_once
    from services.stealth_seo import get_collection_keywords
    await db.tiles.insert_many([
        {"id": "t1", "is_active": True, "collection": "Spanish"},
        {"id": "t2", "is_active": True, "collection": "Terrazzo"},
        {"id": "t3", "is_active": True, "collection": "Marble"},
    ])
    digest = {
        "gsc_connected": True,
        "new_missed": [
            {"query": "spanish tiles", "impressions": 100, "clicks": 0},
            {"query": "terrazzo tiles", "impressions": 80, "clicks": 0},
            {"query": "marble tiles", "impressions": 50, "clicks": 0},
        ],
    }
    settings = {
        "auto_promote_enabled": True,
        "auto_promote_min_impressions": 20,
        "auto_promote_batch_mode": True,
        "auto_promote_batch_max": 5,
    }
    records = await run_once(digest, settings)
    assert len(records) == 3
    # All three collections got their respective kws
    assert "spanish tiles" in await get_collection_keywords("Spanish")
    assert "terrazzo tiles" in await get_collection_keywords("Terrazzo")
    assert "marble tiles" in await get_collection_keywords("Marble")


@pytest.mark.asyncio
async def test_run_once_batch_mode_respects_max(db):
    from services.stealth_seo_auto_promote import run_once
    await db.tiles.insert_many([
        {"id": f"t{i}", "is_active": True, "collection": c}
        for i, c in enumerate(["Spanish", "Terrazzo", "Marble", "Onyx", "Granite"])
    ])
    digest = {
        "gsc_connected": True,
        "new_missed": [
            {"query": f"{c.lower()} tiles", "impressions": 100 - i, "clicks": 0}
            for i, c in enumerate(["Spanish", "Terrazzo", "Marble", "Onyx", "Granite"])
        ],
    }
    settings = {
        "auto_promote_enabled": True,
        "auto_promote_min_impressions": 20,
        "auto_promote_batch_mode": True,
        "auto_promote_batch_max": 2,  # CAP at 2
    }
    records = await run_once(digest, settings)
    assert len(records) == 2


@pytest.mark.asyncio
async def test_run_once_batch_mode_below_2x_threshold_still_runs_for_qualifiers(db):
    """If ONLY 1 query clears the 2× bar in batch mode, it should still
    promote that single one (not fall back to single-mode's lower bar)."""
    from services.stealth_seo_auto_promote import run_once
    await db.tiles.insert_many([
        {"id": "t1", "is_active": True, "collection": "Spanish"},
        {"id": "t2", "is_active": True, "collection": "Terrazzo"},
    ])
    digest = {
        "gsc_connected": True,
        "new_missed": [
            {"query": "spanish tiles", "impressions": 50, "clicks": 0},   # ≥40 ✓
            {"query": "terrazzo tiles", "impressions": 30, "clicks": 0},  # <40 ✗
        ],
    }
    settings = {
        "auto_promote_enabled": True,
        "auto_promote_min_impressions": 20,
        "auto_promote_batch_mode": True,
        "auto_promote_batch_max": 5,
    }
    records = await run_once(digest, settings)
    assert len(records) == 1
    assert records[0]["query"] == "spanish tiles"


# ───── Settings: batch_max clamping ─────

@pytest.mark.asyncio
async def test_settings_batch_max_clamped(db):
    from services.stealth_seo_digest import update_settings, get_settings
    await update_settings({"auto_promote_batch_max": 1})
    assert (await get_settings())["auto_promote_batch_max"] == 2  # floor
    await update_settings({"auto_promote_batch_max": 99})
    assert (await get_settings())["auto_promote_batch_max"] == 10  # ceiling


@pytest.mark.asyncio
async def test_settings_batch_mode_flag(db):
    from services.stealth_seo_digest import update_settings, get_settings
    await update_settings({"auto_promote_batch_mode": True})
    assert (await get_settings())["auto_promote_batch_mode"] is True


# ───── Settings whitelist for new fields ─────

@pytest.mark.asyncio
async def test_settings_auto_promote_flag(db):
    from services.stealth_seo_digest import update_settings, get_settings
    await update_settings({"auto_promote_enabled": True})
    s = await get_settings()
    assert s["auto_promote_enabled"] is True


@pytest.mark.asyncio
async def test_settings_min_impressions_clamped(db):
    from services.stealth_seo_digest import update_settings, get_settings
    # Below floor 5
    await update_settings({"auto_promote_min_impressions": 1})
    assert (await get_settings())["auto_promote_min_impressions"] == 5
    # Above ceiling 500
    await update_settings({"auto_promote_min_impressions": 9999})
    assert (await get_settings())["auto_promote_min_impressions"] == 500
    # Garbage ignored (no-op)
    await update_settings({"auto_promote_min_impressions": "banana"})
    assert (await get_settings())["auto_promote_min_impressions"] == 500


# ───── list_since — digest pulls recent promotions ─────

@pytest.mark.asyncio
async def test_list_since_returns_recent_rows(db):
    from services.stealth_seo_auto_promote import apply_auto_promote, list_since
    await db.tiles.insert_many([
        {"id": "t1", "is_active": True, "collection": "Spanish"},
        {"id": "t2", "is_active": True, "collection": "Marble"},
    ])
    await apply_auto_promote({"query": "spanish tiles", "collection": "Spanish",
                               "impressions": 50, "clicks": 1})
    await apply_auto_promote({"query": "marble tiles", "collection": "Marble",
                               "impressions": 30, "clicks": 0})
    # Seed an ancient row that should NOT appear
    await db.seo_stealth_auto_promotes.insert_one({
        "id": "ancient", "query": "old", "collection": "x",
        "added_keyword": "old", "token": "ancient-token",
        "promoted_at": datetime.now(timezone.utc) - timedelta(days=90),
        "undone_at": None, "promoted_by": "cron",
    })
    cutoff = datetime.now(timezone.utc) - timedelta(days=8)
    rows = await list_since(cutoff)
    queries = {r["query"] for r in rows}
    assert "spanish tiles" in queries
    assert "marble tiles" in queries
    assert "old" not in queries

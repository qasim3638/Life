"""Tests for the Stealth-Keyword SEO targeting service."""
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
    test_db = client[f"test_stealth_{uuid.uuid4().hex[:8]}"]
    monkeypatch.setattr("services.stealth_seo.get_db", lambda: test_db)
    yield test_db
    await client.drop_database(test_db.name)
    client.close()


# ───── _normalise — input sanitisation ─────

def test_normalise_handles_string_csv():
    from services.stealth_seo import _normalise
    assert _normalise("Opal, LP-6611, Onyx White") == ["Opal", "LP-6611", "Onyx White"]


def test_normalise_handles_list():
    from services.stealth_seo import _normalise
    assert _normalise(["Opal", "Opal", "  LP-6611  ", ""]) == ["Opal", "LP-6611"]


def test_normalise_caps_each_keyword_at_80_chars():
    from services.stealth_seo import _normalise
    too_long = "x" * 200
    out = _normalise([too_long, "ok"])
    # Items >80 chars are dropped entirely (not truncated) per service contract
    assert "ok" in out
    assert all(len(k) <= 80 for k in out)


def test_normalise_caps_total_at_25():
    from services.stealth_seo import _normalise
    items = [f"kw{i}" for i in range(40)]
    assert len(_normalise(items)) == 25


def test_normalise_dedupes_case_insensitive():
    from services.stealth_seo import _normalise
    assert _normalise(["Opal", "opal", "OPAL"]) == ["Opal"]


def test_normalise_handles_none_and_empty():
    from services.stealth_seo import _normalise
    assert _normalise(None) == []
    assert _normalise("") == []
    assert _normalise([]) == []


# ───── Per-product set/clear ─────

@pytest.mark.asyncio
async def test_set_product_keywords_round_trip(db):
    from services.stealth_seo import set_product_keywords, list_products
    await db.tiles.insert_one({
        "id": "t1", "name": "Alabaster Polished 60x60cm", "is_active": True,
        "collection": "Marble Effect", "original_name": "Onyx White 60x60cm",
        "supplier_code": "LP-6611",
    })
    res = await set_product_keywords("t1", ["Opal", "LP-6611"], admin_email="admin@x.com")
    assert res["ok"] is True
    assert res["stealth_keywords"] == ["Opal", "LP-6611"]
    rows = await list_products(collection="Marble Effect")
    assert rows[0]["stealth_keywords"] == ["Opal", "LP-6611"]
    audit = await db.seo_stealth_audit.find_one({"scope": "product", "target_id": "t1"})
    assert audit is not None and audit["admin_email"] == "admin@x.com"


@pytest.mark.asyncio
async def test_set_product_keywords_404(db):
    from services.stealth_seo import set_product_keywords
    with pytest.raises(LookupError):
        await set_product_keywords("missing", ["x"])


@pytest.mark.asyncio
async def test_set_product_keywords_clears_when_empty_list(db):
    from services.stealth_seo import set_product_keywords
    await db.tiles.insert_one({
        "id": "t1", "name": "X", "is_active": True,
        "hidden_seo_keywords": "old, kws",
    })
    await set_product_keywords("t1", [])
    row = await db.tiles.find_one({"id": "t1"}, {"_id": 0, "hidden_seo_keywords": 1})
    assert row["hidden_seo_keywords"] == ""


# ───── list_products & list_collections — admin queries ─────

@pytest.mark.asyncio
async def test_list_products_only_missing_filter(db):
    from services.stealth_seo import list_products
    await db.tiles.insert_many([
        {"id": "t1", "name": "A", "is_active": True, "collection": "C1",
         "original_name": "Original A", "supplier_code": "SC-1",
         "hidden_seo_keywords": "Original A"},
        {"id": "t2", "name": "B", "is_active": True, "collection": "C1",
         "original_name": "Original B", "supplier_code": "SC-2",
         "hidden_seo_keywords": ""},
        {"id": "t3", "name": "C", "is_active": True, "collection": "C1",
         "original_name": "Original C", "supplier_code": "SC-3"},
    ])
    rows = await list_products(collection="C1", only_missing=True)
    ids = {r["id"] for r in rows}
    assert ids == {"t2", "t3"}


@pytest.mark.asyncio
async def test_list_products_suggestions(db):
    from services.stealth_seo import list_products
    await db.tiles.insert_one({
        "id": "t1", "name": "Alabaster Polished",
        "original_name": "Onyx White Polished", "supplier_code": "LP-6611",
        "is_active": True, "collection": "C1",
    })
    rows = await list_products(collection="C1")
    assert rows[0]["suggested_keywords"] == ["Onyx White Polished", "LP-6611"]


@pytest.mark.asyncio
async def test_list_products_suggestions_skip_when_orig_matches_name(db):
    from services.stealth_seo import list_products
    await db.tiles.insert_one({
        "id": "t1", "name": "Onyx White", "original_name": "onyx white",
        "is_active": True, "collection": "C1",
    })
    rows = await list_products(collection="C1")
    assert rows[0]["suggested_keywords"] == []


@pytest.mark.asyncio
async def test_list_collections_with_counts(db):
    from services.stealth_seo import list_collections_with_counts
    await db.tiles.insert_many([
        {"id": "t1", "is_active": True, "collection": "C1", "hidden_seo_keywords": "x"},
        {"id": "t2", "is_active": True, "collection": "C1", "hidden_seo_keywords": ""},
        {"id": "t3", "is_active": True, "collection": "C1"},
        {"id": "t4", "is_active": True, "collection": "C2", "hidden_seo_keywords": "y"},
    ])
    rows = await list_collections_with_counts()
    by_name = {r["collection"]: r for r in rows}
    assert by_name["C1"]["product_count"] == 3
    assert by_name["C1"]["with_stealth_keywords"] == 1
    assert by_name["C1"]["coverage_pct"] == 33  # 1/3


# ───── Bulk apply (merge / replace / append_supplier_original) ─────

@pytest.mark.asyncio
async def test_bulk_apply_merge(db):
    from services.stealth_seo import bulk_apply_to_collection
    await db.tiles.insert_many([
        {"id": "t1", "name": "A", "is_active": True, "collection": "C1",
         "hidden_seo_keywords": "Existing"},
        {"id": "t2", "name": "B", "is_active": True, "collection": "C1"},
    ])
    res = await bulk_apply_to_collection("C1", ["NewA", "NewB"], mode="merge")
    assert res["matched"] == 2 and res["updated"] == 2
    t1 = await db.tiles.find_one({"id": "t1"}, {"_id": 0, "hidden_seo_keywords": 1})
    t2 = await db.tiles.find_one({"id": "t2"}, {"_id": 0, "hidden_seo_keywords": 1})
    assert t1["hidden_seo_keywords"] == "Existing, NewA, NewB"
    assert t2["hidden_seo_keywords"] == "NewA, NewB"


@pytest.mark.asyncio
async def test_bulk_apply_replace_overwrites(db):
    from services.stealth_seo import bulk_apply_to_collection
    await db.tiles.insert_one({
        "id": "t1", "name": "A", "is_active": True, "collection": "C1",
        "hidden_seo_keywords": "Old, Stuff",
    })
    await bulk_apply_to_collection("C1", ["Fresh"], mode="replace")
    t1 = await db.tiles.find_one({"id": "t1"}, {"_id": 0, "hidden_seo_keywords": 1})
    assert t1["hidden_seo_keywords"] == "Fresh"


@pytest.mark.asyncio
async def test_bulk_apply_append_supplier_original(db):
    from services.stealth_seo import bulk_apply_to_collection
    await db.tiles.insert_many([
        {"id": "t1", "name": "Alabaster", "is_active": True, "collection": "C1",
         "original_name": "Onyx White", "supplier_code": "LP-6611"},
        {"id": "t2", "name": "Same Name", "is_active": True, "collection": "C1",
         "original_name": "Same Name"},  # original equals name → skipped from extras
    ])
    res = await bulk_apply_to_collection("C1", [], mode="append_supplier_original")
    assert res["matched"] == 2
    t1 = await db.tiles.find_one({"id": "t1"}, {"_id": 0, "hidden_seo_keywords": 1})
    t2 = await db.tiles.find_one({"id": "t2"}, {"_id": 0, "hidden_seo_keywords": 1})
    assert t1["hidden_seo_keywords"] == "Onyx White, LP-6611"
    # t2 had no eligible extras (original==name and no supplier_code) → no write
    assert t2.get("hidden_seo_keywords") is None or t2["hidden_seo_keywords"] == ""


@pytest.mark.asyncio
async def test_bulk_apply_idempotent(db):
    from services.stealth_seo import bulk_apply_to_collection
    await db.tiles.insert_one({
        "id": "t1", "name": "A", "is_active": True, "collection": "C1",
        "hidden_seo_keywords": "X, Y",
    })
    r1 = await bulk_apply_to_collection("C1", ["X", "Y"], mode="merge")
    r2 = await bulk_apply_to_collection("C1", ["X", "Y"], mode="merge")
    assert r1["updated"] == 0 and r2["updated"] == 0


@pytest.mark.asyncio
async def test_bulk_apply_invalid_mode_rejected(db):
    from services.stealth_seo import bulk_apply_to_collection
    with pytest.raises(ValueError):
        await bulk_apply_to_collection("C1", [], mode="nonsense")


# ───── auto_fill_all_supplier_originals — the headline feature ─────

@pytest.mark.asyncio
async def test_auto_fill_all_dry_run_doesnt_write(db):
    from services.stealth_seo import auto_fill_all_supplier_originals
    await db.tiles.insert_one({
        "id": "t1", "name": "A", "is_active": True, "collection": "C1",
        "original_name": "Original A", "supplier_code": "SC-1",
    })
    res = await auto_fill_all_supplier_originals(dry_run=True)
    assert res["dry_run"] is True
    assert res["matched"] == 1 and res["updated"] == 1
    assert res["keywords_added"] == 2  # original + supplier_code
    # Verify nothing was written
    t1 = await db.tiles.find_one({"id": "t1"}, {"_id": 0, "hidden_seo_keywords": 1})
    assert t1.get("hidden_seo_keywords") is None
    # And no audit row
    assert await db.seo_stealth_audit.count_documents({}) == 0


@pytest.mark.asyncio
async def test_auto_fill_all_writes_and_audits(db):
    from services.stealth_seo import auto_fill_all_supplier_originals
    await db.tiles.insert_many([
        {"id": "t1", "name": "Alabaster", "is_active": True, "collection": "C1",
         "original_name": "Onyx White", "supplier_code": "LP-6611"},
        {"id": "t2", "name": "Calacatta", "is_active": True, "collection": "C2",
         "original_name": "Marble Pro", "supplier_code": "MP-9000"},
    ])
    res = await auto_fill_all_supplier_originals(admin_email="admin@x.com")
    assert res["dry_run"] is False
    assert res["matched"] == 2 and res["updated"] == 2
    t1 = await db.tiles.find_one({"id": "t1"}, {"_id": 0, "hidden_seo_keywords": 1})
    assert "Onyx White" in t1["hidden_seo_keywords"] and "LP-6611" in t1["hidden_seo_keywords"]
    audit = await db.seo_stealth_audit.find_one({"scope": "auto_fill_all_supplier_originals"})
    assert audit and audit["admin_email"] == "admin@x.com"
    assert audit["updated"] == 2


@pytest.mark.asyncio
async def test_auto_fill_all_skips_already_covered(db):
    from services.stealth_seo import auto_fill_all_supplier_originals
    await db.tiles.insert_one({
        "id": "t1", "name": "A", "is_active": True, "collection": "C1",
        "original_name": "Onyx White", "supplier_code": "LP-6611",
        "hidden_seo_keywords": "Onyx White, LP-6611",
    })
    res = await auto_fill_all_supplier_originals()
    assert res["updated"] == 0
    assert res["skipped_already_have"] == 1


@pytest.mark.asyncio
async def test_auto_fill_all_skips_no_supplier_data(db):
    from services.stealth_seo import auto_fill_all_supplier_originals
    await db.tiles.insert_one({
        "id": "t1", "name": "Lonely", "is_active": True, "collection": "C1",
        # no original_name, no supplier_code
    })
    res = await auto_fill_all_supplier_originals()
    assert res["updated"] == 0
    assert res["skipped_no_supplier_data"] == 1


@pytest.mark.asyncio
async def test_auto_fill_all_skips_inactive(db):
    from services.stealth_seo import auto_fill_all_supplier_originals
    await db.tiles.insert_many([
        {"id": "t1", "name": "Live", "is_active": True,
         "original_name": "X", "supplier_code": "SC-1"},
        {"id": "t2", "name": "Archived", "is_active": False,
         "original_name": "Y", "supplier_code": "SC-2"},
    ])
    res = await auto_fill_all_supplier_originals()
    assert res["matched"] == 1 and res["updated"] == 1
    t2 = await db.tiles.find_one({"id": "t2"}, {"_id": 0, "hidden_seo_keywords": 1})
    assert t2.get("hidden_seo_keywords") is None  # untouched


@pytest.mark.asyncio
async def test_auto_fill_all_idempotent(db):
    from services.stealth_seo import auto_fill_all_supplier_originals
    await db.tiles.insert_one({
        "id": "t1", "name": "A", "is_active": True,
        "original_name": "Onyx White", "supplier_code": "LP-6611",
    })
    r1 = await auto_fill_all_supplier_originals()
    r2 = await auto_fill_all_supplier_originals()
    assert r1["updated"] == 1
    assert r2["updated"] == 0
    assert r2["skipped_already_have"] == 1


# ───── Collection-level keywords (read by SSR) ─────

@pytest.mark.asyncio
async def test_collection_keywords_round_trip(db):
    from services.stealth_seo import set_collection_keywords, get_collection_keywords
    await set_collection_keywords("Marble Effect", ["Calacatta", "Carrara"],
                                   admin_email="admin@x.com")
    keys = await get_collection_keywords("Marble Effect")
    assert keys == ["Calacatta", "Carrara"]


@pytest.mark.asyncio
async def test_collection_keywords_replaces(db):
    from services.stealth_seo import set_collection_keywords, get_collection_keywords
    await set_collection_keywords("X", ["a", "b"])
    await set_collection_keywords("X", ["c"])
    assert await get_collection_keywords("X") == ["c"]


@pytest.mark.asyncio
async def test_get_stealth_keywords_for_tile_merges_collection(db):
    from services.stealth_seo import (
        set_product_keywords, set_collection_keywords,
        get_stealth_keywords_for_tile,
    )
    await db.tiles.insert_one({
        "id": "t1", "slug": "alabaster-60x60", "name": "Alabaster",
        "is_active": True, "collection": "Marble Effect",
    })
    await set_product_keywords("t1", ["Onyx White"])
    await set_collection_keywords("Marble Effect", ["Calacatta", "Carrara"])
    keys = await get_stealth_keywords_for_tile("alabaster-60x60")
    assert "Onyx White" in keys
    assert "Calacatta" in keys
    assert "Carrara" in keys


@pytest.mark.asyncio
async def test_get_stealth_keywords_for_missing_tile_returns_empty(db):
    from services.stealth_seo import get_stealth_keywords_for_tile
    assert await get_stealth_keywords_for_tile("nope") == []


# ───── Stats — admin dashboard top-of-card metrics ─────

@pytest.mark.asyncio
async def test_stats_coverage_calculation(db):
    from services.stealth_seo import stats
    await db.tiles.insert_many([
        {"id": "t1", "is_active": True, "original_name": "X",
         "hidden_seo_keywords": "kw1"},
        {"id": "t2", "is_active": True, "original_name": "Y",
         "hidden_seo_keywords": ""},
        {"id": "t3", "is_active": True, "original_name": "Z"},
        {"id": "t4", "is_active": False, "original_name": "Q",
         "hidden_seo_keywords": "kw"},
    ])
    s = await stats()
    assert s["products_total"] == 3  # active only
    assert s["products_with_keywords"] == 1
    assert s["products_eligible"] == 3
    assert s["coverage_pct"] == 33

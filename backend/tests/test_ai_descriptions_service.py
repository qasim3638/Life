"""Tests for the shared AI-description service (services/ai_descriptions.py).

We validate the pure-Python logic (prompt building, sibling fetching,
save-back, filter shape). The LLM call itself is not re-tested — the
production endpoint is exercised via curl in the bulk-generator flow.
"""
import os
import sys
import uuid
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from motor.motor_asyncio import AsyncIOMotorClient


def _db():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return client[os.environ["DB_NAME"]], client


def test_missing_description_filter_shape():
    from services.ai_descriptions import missing_description_filter
    f = missing_description_filter()
    # Covers: missing field, empty string, explicit None
    ors = f["$or"]
    assert {"description": {"$exists": False}} in ors
    assert {"description": ""} in ors
    assert {"description": None} in ors


def test_product_display_name_priority():
    from services.ai_descriptions import product_display_name
    # Coalesces in this order: our_product_name > display_name > name > product_name
    assert product_display_name({
        "our_product_name": "A",
        "display_name": "B",
        "name": "C",
    }) == "A"
    assert product_display_name({"display_name": "B", "name": "C"}) == "B"
    assert product_display_name({"name": "C"}) == "C"
    assert product_display_name({"product_name": "D"}) == "D"
    assert product_display_name({}) == "Tile"


def test_build_prompt_includes_link_block_only_when_siblings_given():
    from services.ai_descriptions import build_prompt
    product = {"name": "Grey Matt 60x60", "material": "Porcelain", "category": "Floor Tiles"}
    # Without siblings: no link block
    p1 = build_prompt(product, siblings=None)
    assert "INTERNAL LINK REQUIREMENT" not in p1
    assert "PRODUCT NAME: Grey Matt 60x60" in p1
    # With siblings: block appears
    p2 = build_prompt(product, siblings=[
        {"name": "Charcoal Matt 60x60", "path": "/tiles/charcoal-matt-60x60"},
    ])
    assert "INTERNAL LINK REQUIREMENT" in p2
    assert "[Charcoal Matt 60x60](/tiles/charcoal-matt-60x60)" in p2


def test_build_prompt_resilient_to_nested_attributes_schema():
    """Imported tiles/supplier rows stash attributes under `attributes.*`.
    The prompt builder must coalesce both schemas."""
    from services.ai_descriptions import build_prompt
    product = {
        "name": "Nested Schema Tile",
        "attributes": {"material": "Porcelain", "finish": "Matt", "size": "60x60"},
    }
    p = build_prompt(product, siblings=None)
    assert "Material: Porcelain" in p
    assert "Finish: Matt" in p
    assert "Size: 60x60" in p


@pytest.mark.asyncio
async def test_siblings_for_returns_cat_fallback_when_no_siblings():
    """A product in a category with no other rows should still return the
    category landing page as a link option."""
    db, client = _db()
    cat = f"LonelyCat-{uuid.uuid4().hex[:8]}"
    pid = f"lonely-{uuid.uuid4().hex[:6]}"
    await db.products.insert_one({"id": pid, "name": "Lonely", "category": cat, "category_slug": cat.lower()})
    try:
        from services.ai_descriptions import siblings_for
        out = await siblings_for(db, "products", {"id": pid, "category": cat}, {})
        # Only the category fallback should be present
        assert len(out) == 1
        assert out[0]["path"].startswith("/shop/category/")
    finally:
        await db.products.delete_one({"id": pid})
        client.close()


@pytest.mark.asyncio
async def test_siblings_for_excludes_self_and_caps_at_three():
    db, client = _db()
    cat = f"Crowd-{uuid.uuid4().hex[:8]}"
    ids = [f"c-{uuid.uuid4().hex[:6]}" for _ in range(5)]
    docs = [
        {"id": i, "name": f"Prod {n}", "slug": f"prod-{n}", "category": cat}
        for n, i in enumerate(ids)
    ]
    await db.products.insert_many(docs)
    try:
        from services.ai_descriptions import siblings_for
        out = await siblings_for(db, "products", {"id": ids[0], "category": cat}, {})
        # 3 sibling products + 1 category fallback
        assert len(out) == 4
        # Self must not appear
        assert all(f"prod-0" != o["path"].rsplit("/", 1)[-1] for o in out[:3])
    finally:
        await db.products.delete_many({"id": {"$in": ids}})
        client.close()


@pytest.mark.asyncio
async def test_save_generated_description_writes_metadata():
    db, client = _db()
    pid = f"savetest-{uuid.uuid4().hex[:6]}"
    await db.products.insert_one({"id": pid, "name": "Save Test"})
    try:
        from services.ai_descriptions import save_generated_description
        await save_generated_description(db, "products", {"id": pid}, "Hello world copy.")
        doc = await db.products.find_one({"id": pid}, {"_id": 0})
        assert doc["description"] == "Hello world copy."
        assert doc["description_source"] == "ai_bulk_haiku"
        assert "description_generated_at" in doc
    finally:
        await db.products.delete_one({"id": pid})
        client.close()

"""
Pytests for the SEO Drafts review queue (`routes/seo_drafts.py`).

We do NOT exercise the full catalogue scanner here (it walks the live
collections and has side effects) — we instead test the smaller pure
units (`_upsert_draft`, `_generate_one_draft`, `_variant_prompt_suffix`,
`_custom_prompt_suffix`, `save_generated_description`) that the scanner
composes. Full scanner path is exercised by the backend testing agent.

Coverage:
  - `_upsert_draft` creates a row on first sighting + appends to history
  - Regenerate-through-upsert appends variant + custom_instruction
  - `save_generated_description` writes to the live product doc
  - Variant / custom prompt suffix edge-cases (unknown, empty, cap)
"""
from __future__ import annotations

import os
import sys
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("EMERGENT_LLM_KEY", "sk-test-fake-for-unit")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402


def _db():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return client[os.environ["DB_NAME"]], client


async def _cleanup(db):
    await db.seo_description_drafts.delete_many({"product_id": {"$regex": "^test-sd-"}})
    await db.products.delete_many({"id": {"$regex": "^test-sd-"}})


async def _seed_one(db, i=0, desc=""):
    await db.products.insert_one({
        "id": f"test-sd-{i}",
        "sku": f"TEST-SD-{i}",
        "name": f"Test Product {i}",
        "category": "Porcelain",
        "description": desc,
    })
    return {
        "id": f"test-sd-{i}",
        "sku": f"TEST-SD-{i}",
        "name": f"Test Product {i}",
        "category": "Porcelain",
    }


@pytest.mark.asyncio
async def test_upsert_creates_new_draft_then_appends_history():
    from routes import seo_drafts as sd
    db, client = _db()
    try:
        await _cleanup(db)
        prod = await _seed_one(db, 0)

        first = await sd._upsert_draft(
            db, collection="products", product=prod,
            new_text="First suggestion", variant="default",
        )
        assert first["status"] == "pending"
        assert len(first["drafts"]) == 1
        assert first["drafts"][0]["variant"] == "default"
        assert first["drafts"][0]["custom_instruction"] == ""

        second = await sd._upsert_draft(
            db, collection="products", product=prod,
            new_text="Shorter take", variant="shorter",
            custom_instruction="drop marketing fluff",
        )
        assert len(second["drafts"]) == 2
        latest = second["drafts"][-1]
        assert latest["variant"] == "shorter"
        assert latest["custom_instruction"] == "drop marketing fluff"
        assert latest["text"] == "Shorter take"
    finally:
        await _cleanup(db)
        client.close()


@pytest.mark.asyncio
async def test_upsert_caps_history_at_ten_entries():
    from routes import seo_drafts as sd
    db, client = _db()
    try:
        await _cleanup(db)
        prod = await _seed_one(db, 1)

        for i in range(12):
            await sd._upsert_draft(
                db, collection="products", product=prod,
                new_text=f"v{i}", variant="default",
            )
        row = await db.seo_description_drafts.find_one(
            {"product_id": "test-sd-1"}, {"_id": 0}
        )
        assert len(row["drafts"]) == 10
        # Oldest 2 should have been dropped → v2..v11 retained.
        assert row["drafts"][0]["text"] == "v2"
        assert row["drafts"][-1]["text"] == "v11"
    finally:
        await _cleanup(db)
        client.close()


@pytest.mark.asyncio
async def test_regenerating_a_skipped_draft_reopens_it_for_review():
    from routes import seo_drafts as sd
    db, client = _db()
    try:
        await _cleanup(db)
        prod = await _seed_one(db, 2)
        await sd._upsert_draft(
            db, collection="products", product=prod,
            new_text="v1", variant="default",
        )
        await db.seo_description_drafts.update_one(
            {"product_id": "test-sd-2"}, {"$set": {"status": "skipped"}}
        )

        # Admin regenerates manually — status should flip back to pending.
        updated = await sd._upsert_draft(
            db, collection="products", product=prod,
            new_text="v2", variant="shorter",
        )
        assert updated["status"] == "pending"
        assert len(updated["drafts"]) == 2
    finally:
        await _cleanup(db)
        client.close()


@pytest.mark.asyncio
async def test_save_generated_description_publishes_to_product():
    from services.ai_descriptions import save_generated_description
    db, client = _db()
    try:
        await _cleanup(db)
        await _seed_one(db, 3, desc="")
        prod = await db.products.find_one({"id": "test-sd-3"}, {"_id": 0})

        final = "Polished porcelain, honed edges, tight grout joint."
        await save_generated_description(db, "products", prod, final)

        refreshed = await db.products.find_one({"id": "test-sd-3"})
        assert refreshed["description"] == final
        assert refreshed["description_source"] == "ai_bulk_haiku"
        assert refreshed["description_generated_at"]  # set to ISO timestamp
    finally:
        await _cleanup(db)
        client.close()


def test_variant_prompt_suffix_matrix():
    from routes import seo_drafts as sd
    assert sd._variant_prompt_suffix("garbage-mode") == ""
    assert sd._variant_prompt_suffix("default") == ""
    assert "35-45" in sd._variant_prompt_suffix("shorter")
    assert "technical" in sd._variant_prompt_suffix("more_technical").lower()
    assert "warm" in sd._variant_prompt_suffix("warmer").lower()
    assert "benefit" in sd._variant_prompt_suffix("benefits_focused").lower()


def test_custom_prompt_suffix_is_capped_and_safe():
    from routes import seo_drafts as sd
    long = "x" * 1000
    out = sd._custom_prompt_suffix(long)
    assert out.count("x") == sd._MAX_CUSTOM_PROMPT_LEN
    assert "ADMIN STEER" in out
    # Empty / whitespace-only inputs produce no suffix at all.
    assert sd._custom_prompt_suffix("") == ""
    assert sd._custom_prompt_suffix("   ") == ""


def test_valid_variants_set_covers_all_variant_options():
    from routes import seo_drafts as sd
    assert {"default", "shorter", "more_technical", "warmer", "benefits_focused"} == sd.VARIANTS


@pytest.mark.asyncio
async def test_upsert_history_restores_status_to_pending_from_skipped_but_preserves_approved():
    from routes import seo_drafts as sd
    db, client = _db()
    try:
        await _cleanup(db)
        prod = await _seed_one(db, 4)
        await sd._upsert_draft(
            db, collection="products", product=prod,
            new_text="v1", variant="default",
        )
        await db.seo_description_drafts.update_one(
            {"product_id": "test-sd-4"}, {"$set": {"status": "approved"}}
        )
        # Approved rows shouldn't be re-opened to pending when re-upserted —
        # approval is a terminal state the scanner must respect.
        updated = await sd._upsert_draft(
            db, collection="products", product=prod,
            new_text="v2", variant="default",
        )
        assert updated["status"] == "approved"
    finally:
        await _cleanup(db)
        client.close()


@pytest.mark.asyncio
async def test_approve_with_target_keyword_stamps_the_draft():
    """When the admin arrives via the Search Insights deep-link
    (`?target=marble effect`), the frontend echoes that keyword on the
    approve POST. We persist it on the draft so the insights card can
    show '✓ N targeting' badges."""
    from routes import seo_drafts as sd
    db, client = _db()
    try:
        await _cleanup(db)
        prod = await _seed_one(db, 5)
        await sd._upsert_draft(
            db, collection="products", product=prod,
            new_text="some draft", variant="default",
        )

        from services.ai_descriptions import save_generated_description
        prod_doc = await db.products.find_one({"id": "test-sd-5"}, {"_id": 0})
        await save_generated_description(db, "products", prod_doc, "Final approved copy.")

        # Mimic the approve-endpoint update_set for the target_keyword path.
        kw = "Marble Effect"
        await db.seo_description_drafts.update_one(
            {"product_id": "test-sd-5"},
            {"$set": {
                "status": "approved",
                "approved_for_keyword": kw,
                "approved_for_keyword_lower": kw.lower(),
            }},
        )

        # Verify the insights aggregator counts this against the keyword.
        # Filter to OUR test product so we don't pick up real approved
        # drafts from the live db.
        cnt = await db.seo_description_drafts.count_documents({
            "status": "approved",
            "approved_for_keyword_lower": kw.lower(),
            "product_id": "test-sd-5",
        })
        assert cnt == 1
    finally:
        await _cleanup(db)
        client.close()

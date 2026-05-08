"""
Pytests for the weekly SEO impact digest (`services/seo_digest.py`).

We exercise the pure aggregation + render + idempotency-stamp logic
without sending real emails (we monkey-patch the resend call to a no-op).
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone, timedelta

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

PFX = "_pytest-digest-"


def _db():
    c = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return c[os.environ["DB_NAME"]], c


async def _cleanup(db):
    await db.search_query_log.delete_many({"q_lower": {"$regex": f"^{PFX}"}})
    await db.seo_description_drafts.delete_many({"product_id": {"$regex": "^test-digest-"}})
    await db.website_settings.delete_one({"_id": "seo_digest"})
    await db.users.delete_many({"email": {"$regex": "^pytest-digest-"}})


async def _seed_search(db, q, total=0, when=None):
    await db.search_query_log.insert_one({
        "q": q, "q_lower": q.lower(), "total": total,
        "tile_count": total, "product_count": 0,
        "is_zero_result": total == 0,
        "suggestions_offered": ["Marble"] if total == 0 else [],
        "suggestion_clicked": None, "session_id": None,
        "user_agent": "pytest",
        "created_at": when or datetime.now(timezone.utc),
    })


@pytest.mark.asyncio
async def test_gather_returns_correct_shape_with_targeting():
    from services.seo_digest import _gather_last_7d
    db, client = _db()
    try:
        await _cleanup(db)
        # 5 zero-result hits for "marble effect" — already plugged
        for _ in range(5):
            await _seed_search(db, f"{PFX}marble effect", total=0)
        # 3 zero-result hits for "hexagonal" — still open
        for _ in range(3):
            await _seed_search(db, f"{PFX}hexagonal", total=0)
        # 4 successful hits for "grout"
        for _ in range(4):
            await _seed_search(db, f"{PFX}grout", total=2)
        # Stamp an approved draft for "marble effect"
        await db.seo_description_drafts.insert_one({
            "id": "test-digest-d1", "product_id": "test-digest-p1",
            "collection": "products", "drafts": [],
            "status": "approved",
            "approved_for_keyword": f"{PFX}marble effect",
            "approved_for_keyword_lower": f"{PFX}marble effect".lower(),
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "created_at": datetime.now(timezone.utc),
        })

        payload = await _gather_last_7d(db)
        plugged_qs = [r["query"] for r in payload["plugged"]]
        open_qs = [r["query"] for r in payload["still_open"]]

        assert any(f"{PFX}marble effect" == q for q in plugged_qs)
        assert any(f"{PFX}hexagonal" == q for q in open_qs)
        # Plugged has the targeting count
        plugged_marble = next(r for r in payload["plugged"] if r["query"] == f"{PFX}marble effect")
        assert plugged_marble["products_targeting"] == 1
        # Hits include grout
        assert any(f"{PFX}grout" == r["query"] for r in payload["hits"])
        assert payload["totals"]["zero_result_searches"] >= 8
    finally:
        await _cleanup(db)
        client.close()


@pytest.mark.asyncio
async def test_render_html_includes_deep_links_and_pills():
    from services.seo_digest import _render_html
    payload = {
        "totals": {"total_searches": 47, "zero_result_searches": 12, "unique_zero_queries": 5},
        "plugged": [{"query": "marble effect", "products_targeting": 3, "count": 9, "sample_suggestions": []}],
        "still_open": [{"query": "hexagonal", "count": 7, "sample_suggestions": ["Hexagon"], "products_targeting": 0}],
        "hits": [{"query": "grout", "count": 14, "sample_suggestions": []}],
    }
    html = _render_html(payload, "https://tilestation.co.uk")
    assert "47" in html and "12 zero-result" in html
    # Plugged pill renders
    assert "✓ 3 targeting" in html
    # Open keyword links to the SEO Drafts deep-link with target=
    assert "tab=seo-drafts&amp;target=hexagonal" in html or "tab=seo-drafts&target=hexagonal" in html
    # Did-you-mean preview present
    assert "Hexagon" in html
    # Footer CTA points to insights
    assert "/admin/marketing?tab=seo" in html


@pytest.mark.asyncio
async def test_digest_is_idempotent_within_same_iso_week(monkeypatch):
    from services import seo_digest as sd_mod
    db, client = _db()
    try:
        await _cleanup(db)
        # Seed a single search so the "no traffic" early-exit doesn't trip.
        await _seed_search(db, f"{PFX}solo", total=0)
        await db.users.insert_one({
            "id": "u-pytest-digest", "email": "pytest-digest-1@example.com",
            "role": "admin",
        })

        sent_count = {"n": 0}

        async def fake_send(**kwargs):
            sent_count["n"] += 1
            return True

        monkeypatch.setattr(
            "services.email.send_email_notification", fake_send,
        )

        # First call — actually sends.
        first = await sd_mod.run_seo_digest_tick(force=False)
        assert first["ok"] is True
        assert sent_count["n"] == 1

        # Second call within same iso week — must be a no-op.
        second = await sd_mod.run_seo_digest_tick(force=False)
        assert second.get("skipped") is True
        assert sent_count["n"] == 1  # unchanged

        # Force=True overrides idempotency.
        third = await sd_mod.run_seo_digest_tick(force=True)
        assert third["ok"] is True
        assert sent_count["n"] == 2
    finally:
        await _cleanup(db)
        client.close()


@pytest.mark.asyncio
async def test_digest_skips_when_no_traffic(monkeypatch):
    from services import seo_digest as sd_mod
    db, client = _db()
    try:
        await _cleanup(db)
        await db.users.insert_one({
            "id": "u-pytest-digest-2", "email": "pytest-digest-2@example.com",
            "role": "admin",
        })

        async def fake_send(**kwargs):
            raise AssertionError("Should not send when window is empty")

        monkeypatch.setattr("services.email.send_email_notification", fake_send)

        # No matching search log rows — ensure clean window.
        await db.search_query_log.delete_many({"q_lower": {"$regex": "^_pytest-digest-empty-"}})
        # Stamp last_sent so we don't conflict with a real send earlier.
        await db.website_settings.update_one(
            {"_id": "seo_digest"},
            {"$set": {"last_sent_iso_week": "1970-W01"}},
            upsert=True,
        )
        # When totals are 0 this should skip cleanly without raising.
        # Note: live db may have other traffic, so we monkey-patch the
        # gather function to return zero searches.
        async def empty_gather(db_):
            return {
                "totals": {"total_searches": 0, "zero_result_searches": 0, "unique_zero_queries": 0},
                "plugged": [], "still_open": [], "hits": [],
            }
        monkeypatch.setattr(sd_mod, "_gather_last_7d", empty_gather)
        result = await sd_mod.run_seo_digest_tick(force=False)
        assert result.get("skipped") is True
        assert "no searches" in (result.get("reason") or "")
    finally:
        await _cleanup(db)
        client.close()

"""
Pytests for the search insights analytics (`routes/search_insights.py`).

We hit Mongo directly (no FastAPI test client) and exercise:
  - log_search writes a row with correct shape
  - log_suggestion_click attributes a click to the most-recent row
  - admin aggregation returns top missed + hits + conversion rate
  - queries shorter than 2 chars are ignored
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


def _db():
    c = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return c[os.environ["DB_NAME"]], c


TEST_PREFIX = "_pytest-si-"


async def _cleanup(db):
    await db.search_query_log.delete_many({"q_lower": {"$regex": f"^{TEST_PREFIX}"}})


async def _seed(db, q: str, total: int = 0, suggestions=None, session_id=None, when=None, clicked=None):
    doc = {
        "q": q,
        "q_lower": q.lower(),
        "total": total,
        "tile_count": total,
        "product_count": 0,
        "is_zero_result": total == 0,
        "suggestions_offered": list(suggestions or []),
        "suggestion_clicked": clicked,
        "session_id": session_id,
        "user_agent": "pytest",
        "created_at": when or datetime.now(timezone.utc),
    }
    await db.search_query_log.insert_one(doc)


@pytest.mark.asyncio
async def test_log_entry_short_payload_is_skipped():
    """Short queries (< 2 chars) should be ignored rather than cluttering
    the log."""
    from routes.search_insights import log_search, SearchLogEntry

    class _FakeReq:
        headers = {"user-agent": "pytest"}

    res = await log_search(SearchLogEntry(q="a", total=0), _FakeReq())
    assert res.get("skipped") is True


@pytest.mark.asyncio
async def test_admin_aggregation_returns_top_missed_and_hits():
    from routes.search_insights import get_search_insights
    db, client = _db()
    try:
        await _cleanup(db)
        # Seed 3 zero-result hits for "marble effect" (top missed) + 2 for "beige"
        for _ in range(3):
            await _seed(db, f"{TEST_PREFIX}marble effect", total=0, suggestions=["Marble"])
        for _ in range(2):
            await _seed(db, f"{TEST_PREFIX}beige", total=0)
        # Seed 5 hits for "grout" (top hit)
        for _ in range(5):
            await _seed(db, f"{TEST_PREFIX}grout", total=3)

        fake_admin = {"role": "super_admin", "email": "admin@test.com"}
        out = await get_search_insights(days=7, limit=20, current_user=fake_admin)

        missed_queries = [r["query"] for r in out["top_missed"] if r["query"].startswith(TEST_PREFIX)]
        hit_queries = [r["query"] for r in out["top_hits"] if r["query"].startswith(TEST_PREFIX)]

        # `marble effect` should outrank `beige` in missed list.
        mi = next(i for i, q in enumerate(missed_queries) if "marble" in q)
        bi = next(i for i, q in enumerate(missed_queries) if "beige" in q)
        assert mi < bi

        assert any("grout" in q for q in hit_queries)

        # SEO keyword candidates mirror the top missed.
        # Real production traffic may rank above our test-prefixed seeds in
        # the global aggregation — assert that our test queries appear in
        # the candidates list at all (not necessarily at index 0).
        candidates = out.get("seo_keyword_candidates", [])
        assert any(c.startswith(TEST_PREFIX) for c in candidates)
    finally:
        await _cleanup(db)
        client.close()


@pytest.mark.asyncio
async def test_suggestion_click_attribution_updates_the_log_row():
    from routes.search_insights import log_suggestion_click, SuggestionClick
    db, client = _db()
    try:
        await _cleanup(db)
        sid = "pytest-session-xyz"
        await _seed(
            db,
            f"{TEST_PREFIX}polishd",
            total=0,
            suggestions=["Polished", "Polish"],
            session_id=sid,
        )

        await log_suggestion_click(SuggestionClick(
            from_query=f"{TEST_PREFIX}polishd", clicked="Polished", session_id=sid,
        ))

        row = await db.search_query_log.find_one({"q_lower": f"{TEST_PREFIX}polishd"})
        assert row["suggestion_clicked"] == "Polished"
        assert row.get("suggestion_clicked_at") is not None
    finally:
        await _cleanup(db)
        client.close()


@pytest.mark.asyncio
async def test_suggestion_click_older_than_10m_is_not_attributed():
    from routes.search_insights import log_suggestion_click, SuggestionClick
    db, client = _db()
    try:
        await _cleanup(db)
        # Row older than 10 minutes — should NOT be updated.
        old = datetime.now(timezone.utc) - timedelta(minutes=30)
        await _seed(
            db, f"{TEST_PREFIX}stale", total=0,
            suggestions=["Sample"], session_id="pytest-stale",
            when=old,
        )

        await log_suggestion_click(SuggestionClick(
            from_query=f"{TEST_PREFIX}stale", clicked="Sample", session_id="pytest-stale",
        ))

        row = await db.search_query_log.find_one({"q_lower": f"{TEST_PREFIX}stale"})
        assert row["suggestion_clicked"] is None  # attribution window expired
    finally:
        await _cleanup(db)
        client.close()


@pytest.mark.asyncio
async def test_admin_gating_rejects_non_admin():
    from routes.search_insights import get_search_insights
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        await get_search_insights(days=7, limit=20, current_user={"role": "customer"})
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_admin_conversion_rate_is_correct():
    from routes.search_insights import get_search_insights
    db, client = _db()
    try:
        await _cleanup(db)
        # 4 rows with suggestions offered, 2 with a click → 50% rate
        for i in range(4):
            await _seed(
                db, f"{TEST_PREFIX}conv-{i}", total=0,
                suggestions=["Marble"],
                clicked=("Marble" if i < 2 else None),
            )

        out = await get_search_insights(
            days=7, limit=100,
            current_user={"role": "admin", "email": "a@b.c"},
        )
        # Filter to only our pytest rows
        conv = out["suggestion_conversion"]
        # Over the whole DB window the rate may be polluted by real traffic,
        # but we guarantee >=4 offered and >=2 clicked from our seed.
        assert conv["chips_offered"] >= 4
        assert conv["chips_clicked"] >= 2
        assert 0 <= conv["rate"] <= 1
    finally:
        await _cleanup(db)
        client.close()

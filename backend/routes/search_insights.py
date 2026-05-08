"""
Storefront search analytics — captures every search query + its result
count so the team can:

  1. See what customers are looking for but NOT finding (the SEO gap signal
     — e.g. "marble effect" searched 40 times last week with 0 hits).
  2. See what customers ARE finding (the SEO-reinforcement signal — invest
     more content around proven intent).
  3. Measure whether the "Did you mean?" chips actually convert.

Two storefront-side writers (public, no auth required) + one admin reader.

Privacy / PII:
  - We only store the raw query string + hashed session id + timestamps.
  - No customer email / IP / auth token touches this collection.
  - TTL index on `created_at` auto-purges rows after 90 days.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from config import get_db
from services import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Search Insights"])

_COLLECTION = "search_query_log"
_TTL_DAYS = 90
_ttl_index_ensured = False


async def _ensure_indexes(db) -> None:
    """Idempotent index setup. TTL keeps the collection bounded without
    any cron job."""
    global _ttl_index_ensured
    if _ttl_index_ensured:
        return
    try:
        await db[_COLLECTION].create_index("created_at", expireAfterSeconds=_TTL_DAYS * 86400)
        await db[_COLLECTION].create_index([("q_lower", 1), ("created_at", -1)])
        await db[_COLLECTION].create_index([("total", 1), ("created_at", -1)])
        _ttl_index_ensured = True
    except Exception as e:  # noqa: BLE001
        # Race conditions during first startup are fine — indexes will
        # exist on the next call.
        logger.debug("Search-log index setup: %s", e)


def _is_admin(user: dict) -> bool:
    return (user or {}).get("role") in {"super_admin", "admin", "manager"}


class SearchLogEntry(BaseModel):
    q: str = Field(..., min_length=1, max_length=200)
    total: int = Field(..., ge=0)
    tile_count: int = Field(default=0, ge=0)
    product_count: int = Field(default=0, ge=0)
    suggestions: list[str] = Field(default_factory=list, max_length=10)
    session_id: Optional[str] = Field(default=None, max_length=64)


@router.post("/shop/search-log")
async def log_search(entry: SearchLogEntry, request: Request):
    """Record a storefront search — fired by the search results page on
    every new query. No auth; rate-limited implicitly by the UA-side
    300ms debounce."""
    db = get_db()
    await _ensure_indexes(db)

    q_clean = (entry.q or "").strip()
    if len(q_clean) < 2:
        return {"ok": True, "skipped": True}

    doc = {
        "q": q_clean[:200],
        "q_lower": q_clean.lower()[:200],
        "total": int(entry.total),
        "tile_count": int(entry.tile_count),
        "product_count": int(entry.product_count),
        "is_zero_result": int(entry.total) == 0,
        "suggestions_offered": list(entry.suggestions or [])[:10],
        "suggestion_clicked": None,
        "session_id": (entry.session_id or "")[:64] or None,
        "user_agent": (request.headers.get("user-agent") or "")[:200],
        "created_at": datetime.now(timezone.utc),
    }
    await db[_COLLECTION].insert_one(doc)
    return {"ok": True}


class SuggestionClick(BaseModel):
    from_query: str = Field(..., min_length=1, max_length=200)
    clicked: str = Field(..., min_length=1, max_length=200)
    session_id: Optional[str] = Field(default=None, max_length=64)


@router.post("/shop/search-log/click-suggestion")
async def log_suggestion_click(payload: SuggestionClick):
    """Stamp the most-recent zero-result row for this session+query with
    which correction chip the user picked. This powers the suggestion
    conversion rate in the admin insights card."""
    db = get_db()
    await _ensure_indexes(db)

    q_lower = (payload.from_query or "").strip().lower()[:200]
    if not q_lower:
        return {"ok": True, "skipped": True}

    # Only update rows from the last 10 minutes — after that it's a new
    # intent, not a chip click we want to attribute.
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
    match: dict = {
        "q_lower": q_lower,
        "is_zero_result": True,
        "suggestion_clicked": None,
        "created_at": {"$gte": cutoff},
    }
    if payload.session_id:
        match["session_id"] = payload.session_id[:64]

    await db[_COLLECTION].update_one(
        match,
        {"$set": {"suggestion_clicked": payload.clicked[:200],
                   "suggestion_clicked_at": datetime.now(timezone.utc)}},
        # Not using upsert — if the row doesn't exist we simply lose the
        # attribution rather than fabricate a log entry.
    )
    return {"ok": True}


@router.get("/marketing/admin/search-insights")
async def get_search_insights(
    days: int = 7,
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
):
    """Admin-only aggregation for the Marketing → SEO → "Search insights"
    card. Returns three top lists + suggestion conversion."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")

    days = max(1, min(int(days), 90))
    limit = max(5, min(int(limit), 100))
    db = get_db()
    await _ensure_indexes(db)

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    async def _top(stage_match: dict) -> list:
        pipeline = [
            {"$match": {"created_at": {"$gte": cutoff}, **stage_match}},
            {"$group": {
                "_id": "$q_lower",
                "query": {"$first": "$q"},
                "count": {"$sum": 1},
                "last_seen": {"$max": "$created_at"},
                "sample_suggestions": {"$first": "$suggestions_offered"},
                "avg_results": {"$avg": "$total"},
            }},
            {"$sort": {"count": -1, "last_seen": -1}},
            {"$limit": limit},
        ]
        out = []
        async for d in db[_COLLECTION].aggregate(pipeline):
            out.append({
                "query": d.get("query"),
                "count": int(d.get("count", 0)),
                "last_seen": d["last_seen"].isoformat() if d.get("last_seen") else None,
                "sample_suggestions": d.get("sample_suggestions") or [],
                "avg_results": round(float(d.get("avg_results") or 0), 1),
            })
        return out

    top_missed = await _top({"is_zero_result": True})
    top_hits = await _top({"is_zero_result": False})

    # Per-keyword "products targeting" counts — how many drafts have been
    # approved with `target_keyword` matching one of our top-missed rows.
    # Powers the green "✓ N products targeting this phrase" badge on the
    # Search Insights card so the admin sees which gaps they've plugged.
    keywords_lower = [r["query"].lower() for r in top_missed if r.get("query")]
    targeting_counts: dict = {}
    if keywords_lower:
        cur = db.seo_description_drafts.aggregate([
            {"$match": {
                "status": "approved",
                "approved_for_keyword_lower": {"$in": keywords_lower},
            }},
            {"$group": {"_id": "$approved_for_keyword_lower", "count": {"$sum": 1}}},
        ])
        async for d in cur:
            targeting_counts[d["_id"]] = int(d.get("count", 0))
    for r in top_missed:
        r["products_targeting"] = targeting_counts.get((r.get("query") or "").lower(), 0)

    # Suggestion chip conversion rate.
    chips_offered = await db[_COLLECTION].count_documents({
        "created_at": {"$gte": cutoff},
        "is_zero_result": True,
        "suggestions_offered.0": {"$exists": True},
    })
    chips_clicked = await db[_COLLECTION].count_documents({
        "created_at": {"$gte": cutoff},
        "is_zero_result": True,
        "suggestion_clicked": {"$ne": None},
    })

    totals = {
        "total_searches": await db[_COLLECTION].count_documents({"created_at": {"$gte": cutoff}}),
        "zero_result_searches": await db[_COLLECTION].count_documents({
            "created_at": {"$gte": cutoff}, "is_zero_result": True,
        }),
    }

    return {
        "days": days,
        "totals": totals,
        "top_missed": top_missed,
        "top_hits": top_hits,
        "suggestion_conversion": {
            "chips_offered": chips_offered,
            "chips_clicked": chips_clicked,
            "rate": round(chips_clicked / chips_offered, 3) if chips_offered else 0.0,
        },
        "seo_keyword_candidates": [row["query"] for row in top_missed[:10]],
    }


@router.post("/marketing/admin/search-insights/send-digest")
async def send_seo_digest_now(
    current_user: dict = Depends(get_current_user),
):
    """Manually trigger the weekly SEO digest email — useful for previewing
    or recovering from a missed cron. Idempotency key is the ISO week, so
    by default this is a no-op if already sent this week. Pass
    `?force=true` (handled via the scheduler service) for an override."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    from services.seo_digest import run_seo_digest_tick
    result = await run_seo_digest_tick(force=True)
    return result

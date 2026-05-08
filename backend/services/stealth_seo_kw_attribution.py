"""
Stealth-Keyword Attribution Timeline
─────────────────────────────────────

For every keyword the admin has added (auto-promoted, or scheduled
for tracking), builds a daily click+impression sparkline so you can
literally see whether the keyword is paying off.

Why this feature exists
───────────────────────
The Performance card shows *aggregate* GSC data. It can say "stealth
keywords drove 70 clicks this month" but can't answer:

  • Which specific supplier names paid off?
  • Does "spanish tiles" (auto-promoted 3 weeks ago) bring in more
    clicks than "LP-6611" (added 6 weeks ago)?
  • Is our auto-promote actually lifting traffic week-over-week?

Attribution timeline answers all three with one table + sparklines.

Data flow
─────────
1. Daily cron at 09:00 BST calls `rebuild_timeline_cache(days=28)`:
   pulls `dimensions=['query','date']` from GSC (one row per query
   per day), matches each row against the tracked-keyword list
   (every auto-promote record + every collection-wide keyword ever
   set), writes matched rows to `seo_stealth_kw_timeline`.

2. Admin dashboard hits `get_attribution_timeline()` which reads the
   cache + joins with the tracked-keyword list + computes rollups:
     • clicks/impressions over the window
     • clicks-per-day since added (normalises for keywords added
       mid-window — a kw added yesterday that got 5 clicks today
       has a better rate than a 3-week-old kw with 10 clicks total)
     • ROI score: (this kw's clicks) / (median tracked-kw clicks).
       Score ≥ 1.5 = winner. Score < 0.5 = underperformer.

3. Output is sorted by `clicks_total` desc with ROI badge colours.

Schema
──────
`seo_stealth_kw_timeline`:
  { keyword_lower, keyword, date (YYYY-MM-DD), clicks, impressions,
    ctr, position, cached_at }
  Compound index on (keyword_lower, date) — upsert-friendly.

Stays small: 28 days × ~50 tracked keywords = ~1400 rows max, even
with the most active auto-promote schedule.
"""
from __future__ import annotations

import logging
import re
import statistics
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from config import get_db
from services import gsc as gsc_service
from services.stealth_seo_performance import _query_matches_keyword

logger = logging.getLogger(__name__)


CACHE_COLLECTION = "seo_stealth_kw_timeline"


# ───────── Tracked-keyword list ─────────

async def _load_tracked_keywords() -> list[dict]:
    """Returns a deduped list of every keyword we want to track
    attribution for, annotated with `added_at`, `scope`, and
    `target` (collection name or city-page slug).

    Sources:
      • `seo_stealth_auto_promotes` — the clearest signal (promoted
        by cron or manually via /promote-missed-win) with precise
        timestamps
      • `seo_collection_keywords` — admin-set collection-wide kws.
        We use `updated_at` as the proxy for `added_at` since we
        don't track per-keyword add dates.

    Dedupes by (keyword_lower, target_scope, target_id) so a keyword
    set on the same target via multiple paths counts once.
    """
    db = get_db()
    by_key: dict[str, dict] = {}

    # 1) auto-promote rows — most precise
    async for r in db.seo_stealth_auto_promotes.find(
        {"undone_at": None},
        {"_id": 0, "query": 1, "promoted_at": 1, "scope": 1,
         "collection": 1, "city_slug": 1, "town": 1, "impressions": 1},
    ):
        q = (r.get("query") or "").strip()
        if not q:
            continue
        scope = r.get("scope") or "collection"
        target_id = r.get("city_slug") if scope == "city_page" else r.get("collection")
        if not target_id:
            continue
        key = f"{q.lower()}|{scope}|{str(target_id).lower()}"
        by_key[key] = {
            "keyword": q, "added_at": r.get("promoted_at"),
            "scope": scope, "target_id": target_id,
            "target_label": r.get("town") if scope == "city_page" else target_id,
            "source": "auto_promote",
            "promoted_impressions_at_add": r.get("impressions"),
        }

    # 2) Collection-wide kws set via the admin API
    async for r in db.seo_collection_keywords.find(
        {}, {"_id": 0, "collection": 1, "keywords": 1, "updated_at": 1},
    ):
        coll = (r.get("collection") or "").strip()
        if not coll:
            continue
        kws = r.get("keywords") or []
        if isinstance(kws, str):
            kws = [s.strip() for s in re.split(r"[,\n]+", kws) if s.strip()]
        for kw in kws:
            kw = (kw or "").strip()
            if not kw:
                continue
            key = f"{kw.lower()}|collection|{coll.lower()}"
            if key in by_key:
                continue  # auto_promote row wins (has more context)
            by_key[key] = {
                "keyword": kw, "added_at": r.get("updated_at"),
                "scope": "collection", "target_id": coll, "target_label": coll,
                "source": "admin_ui",
            }

    return list(by_key.values())


# ───────── Cache rebuild ─────────

async def rebuild_timeline_cache(
    *, days: int = 28, admin_id: Optional[str] = None,
) -> dict:
    """Pulls daily-dimension GSC rows and writes matched keyword-date
    rows to `seo_stealth_kw_timeline`. Safe to call repeatedly — it
    upserts on (keyword_lower, date) so duplicate calls don't inflate.

    Returns stats: rows_pulled, matched_pairs, tracked_kws, keywords_with_data.
    """
    db = get_db()
    if admin_id is None:
        admin_id = await gsc_service._pick_connected_admin()
    if not admin_id:
        return {"ok": False, "reason": "gsc_not_connected"}

    try:
        gsc_data = await gsc_service.get_daily_query_rows(admin_id, days=days, limit=10000)
    except Exception:  # noqa: BLE001
        logger.exception("get_daily_query_rows failed for timeline cache")
        return {"ok": False, "reason": "gsc_error"}

    rows = gsc_data.get("rows") or []
    tracked = await _load_tracked_keywords()
    now = datetime.now(timezone.utc)
    if not tracked:
        return {"ok": True, "rows_pulled": len(rows), "tracked_kws": 0,
                "matched_pairs": 0, "keywords_with_data": 0,
                "rebuilt_at": now.isoformat()}

    tracked_kws = [t["keyword"] for t in tracked]
    matched_pairs = 0
    kws_with_data: set[str] = set()

    # We iterate once over GSC rows, checking each against the tracked
    # list. For ~5000 rows × ~50 kws = 250K matches — still sub-second
    # because the matcher is pure regex-free string ops.
    ops: list[tuple[dict, dict]] = []  # (filter, set) pairs for upserts
    for row in rows:
        q = (row.get("query") or "").strip()
        if not q:
            continue
        date = row.get("date") or row.get("keys")
        if not date:
            continue
        for kw in tracked_kws:
            if _query_matches_keyword(q, kw):
                kw_lower = kw.lower()
                ops.append(({
                    "keyword_lower": kw_lower, "date": date,
                }, {
                    "$set": {
                        "keyword_lower": kw_lower, "keyword": kw, "date": date,
                        "clicks": int(row.get("clicks") or 0),
                        "impressions": int(row.get("impressions") or 0),
                        "ctr": float(row.get("ctr") or 0.0),
                        "position": float(row.get("position") or 0.0),
                        "cached_at": now,
                    },
                }))
                kws_with_data.add(kw_lower)

    if ops:
        for flt, upd in ops:
            await db[CACHE_COLLECTION].update_one(flt, upd, upsert=True)
        matched_pairs = len(ops)

    # Cull rows older than (days × 2) to keep the collection small
    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days * 2)).date().isoformat()
    await db[CACHE_COLLECTION].delete_many({"date": {"$lt": cutoff_date}})

    return {
        "ok": True,
        "rows_pulled": len(rows),
        "tracked_kws": len(tracked_kws),
        "matched_pairs": matched_pairs,
        "keywords_with_data": len(kws_with_data),
        "rebuilt_at": now.isoformat(),
    }


# ───────── Read + rollup ─────────

def _roi_band(score: float) -> str:
    if score >= 1.5:
        return "winner"
    if score >= 0.75:
        return "ok"
    if score >= 0.25:
        return "slow"
    return "quiet"


async def get_attribution_timeline(
    *, days: int = 28, scope: Optional[str] = None,
    min_days_live: int = 0, limit: int = 100,
) -> dict:
    """Joins the tracked keywords with the cached timeline rows and
    computes the full output for the UI.

    Filters:
      • `scope` = "collection" | "city_page" | None (all)
      • `min_days_live` = only show keywords that have been live for
        at least N days (default 0 = show everything)
      • `limit` = cap the output (default 100)
    """
    db = get_db()
    tracked = await _load_tracked_keywords()
    if not tracked:
        return {"rows": [], "summary": {}, "generated_at": datetime.now(timezone.utc).isoformat()}

    # Load the cache ONCE, group by keyword_lower
    cache_rows: list[dict] = []
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    async for c in db[CACHE_COLLECTION].find(
        {"date": {"$gte": cutoff}}, {"_id": 0},
    ):
        cache_rows.append(c)
    by_kw: dict[str, list[dict]] = {}
    for r in cache_rows:
        kw = r.get("keyword_lower")
        if kw:
            by_kw.setdefault(kw, []).append(r)

    now = datetime.now(timezone.utc)
    rows: list[dict] = []
    for t in tracked:
        if scope and t["scope"] != scope:
            continue
        added_at = t.get("added_at")
        if isinstance(added_at, datetime):
            if added_at.tzinfo is None:
                added_at = added_at.replace(tzinfo=timezone.utc)
            days_live = max(0, (now - added_at).days)
        else:
            days_live = days  # best-effort default for rows without stamps
        if days_live < min_days_live:
            continue
        kw_rows = by_kw.get(t["keyword"].lower(), [])
        clicks = sum(int(r.get("clicks") or 0) for r in kw_rows)
        impressions = sum(int(r.get("impressions") or 0) for r in kw_rows)
        ctr = (clicks / impressions) if impressions else 0.0
        # Build 28-element sparkline — fill gaps with 0 so the admin
        # can actually see "promoted 3 weeks ago but only clicks this
        # week" patterns visually.
        by_date = {r["date"]: r for r in kw_rows}
        spark: list[int] = []
        for offset in range(days, 0, -1):
            d = (now - timedelta(days=offset)).date().isoformat()
            spark.append(int((by_date.get(d) or {}).get("clicks") or 0))
        rows.append({
            "keyword": t["keyword"],
            "scope": t["scope"],
            "target_id": t["target_id"],
            "target_label": t.get("target_label") or t["target_id"],
            "added_at": added_at.isoformat() if isinstance(added_at, datetime) else None,
            "days_live": days_live,
            "source": t.get("source"),
            "clicks_total": clicks,
            "impressions_total": impressions,
            "ctr": round(ctr, 4),
            "clicks_per_day_live": round((clicks / days_live) if days_live else 0.0, 3),
            "spark": spark,  # daily clicks oldest → newest
        })

    # Compute ROI score: each kw's clicks / median clicks. Use median
    # because auto-promoted keywords span 0-100 clicks/week and the
    # mean skews hard on a few winners.
    click_counts = [r["clicks_total"] for r in rows if r["clicks_total"] > 0]
    median_clicks = statistics.median(click_counts) if click_counts else 1.0
    if median_clicks == 0:
        median_clicks = 1.0
    for r in rows:
        score = r["clicks_total"] / median_clicks
        r["roi_score"] = round(score, 2)
        r["roi_band"] = _roi_band(score)

    rows.sort(key=lambda r: (r["clicks_total"], r["impressions_total"]), reverse=True)
    rows = rows[:limit]

    summary = {
        "tracked_kws": len(tracked),
        "with_traffic": sum(1 for r in rows if r["clicks_total"] > 0),
        "winners": sum(1 for r in rows if r["roi_band"] == "winner"),
        "median_kw_clicks": median_clicks,
        "window_days": days,
    }
    return {
        "rows": rows,
        "summary": summary,
        "generated_at": now.isoformat(),
    }

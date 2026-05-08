"""
Monthly snapshot of the SEO ↔ Ads money-saver totals.

Why
---
The headline "£X / month saved by ranking organically" only becomes a
growth-tracking weapon once you have history. This module captures one
row per calendar month into `ads_savings_snapshots` so the dashboard
can show "↗ +18% vs last month" / "↗ +312% YoY" and compounding can
be SEEN, not just claimed.

Shape
-----
collection: `ads_savings_snapshots`
{
  _id: "YYYY-MM",                      # natural key — one doc per month
  year: int,
  month: int,
  captured_at: ISODate,                # when the snapshot was finalised
  window_days: int,                    # what window the totals reflect
  totals: {
      keywords_ranked: int,
      high_value_keywords: int,
      total_clicks: int,
      total_impressions: int,
      estimated_window_value_gbp: float,
      estimated_monthly_value_gbp: float,
      estimated_annual_value_gbp: float,
  },
  source: "auto" | "manual" | "backfill",
}

Cadence
-------
Scheduler runs daily at 06:30 Europe/London (just after the Ahrefs
snapshot job at 06:15). Each tick:
  1. Computes the current 28-day savings (cheap — re-uses the
     existing /api/admin/ads-savings/overview logic).
  2. Upserts the row keyed by the *current* YYYY-MM. So the row
     gradually firms up across the month and is "frozen" at end of
     month when the next month's row takes over. This means even if
     the scheduler misses a day or twelve we always have an
     up-to-date current-month figure on every page load.
  3. Skips silently if GSC isn't connected (no admin tokens), so a
     fresh deploy doesn't write zero rows.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from config import get_db
from services import gsc as gsc_service

logger = logging.getLogger(__name__)

SNAPSHOT_COLLECTION = "ads_savings_snapshots"

# Re-use the heuristic CPC model from the route module so the snapshot
# uses the *same* numbers that render in the UI — guaranteed
# consistency across the dashboard.
from routes.ads_savings import _estimate_cpc_gbp  # noqa: E402


async def _pick_connected_admin_id() -> str | None:
    """Pick whichever admin most-recently used their GSC token. Same
    pattern as the GSC sitemap auto-submit job — a single connected
    admin is enough to power the whole org's snapshot.
    """
    db = get_db()
    doc = await db["gsc_oauth_tokens"].find_one(
        {},
        sort=[("last_used_at", -1)],
        projection={"_id": 1},
    )
    return doc.get("_id") if doc else None


async def _compute_window_totals(admin_id: str, *, days: int = 28, limit: int = 500) -> dict[str, Any]:
    """Same shape as the /overview endpoint's `totals` block, but
    computed as a pure function we can call from the scheduler.
    """
    data = await gsc_service.get_top_queries(admin_id, days=days, limit=limit)

    rows = data.get("rows", []) or []
    total_clicks = 0
    total_impressions = 0
    total_value = 0.0
    high_value = 0
    for r in rows:
        clicks = int(r.get("clicks") or 0)
        impressions = int(r.get("impressions") or 0)
        cpc = _estimate_cpc_gbp(r.get("query") or "")
        value = clicks * cpc
        total_clicks += clicks
        total_impressions += impressions
        total_value += value
        if value >= 50:
            high_value += 1

    projection_factor = 30.0 / max(int(days), 1)
    monthly_value = round(total_value * projection_factor, 2)

    return {
        "keywords_ranked": len(rows),
        "high_value_keywords": high_value,
        "total_clicks": total_clicks,
        "total_impressions": total_impressions,
        "estimated_window_value_gbp": round(total_value, 2),
        "estimated_monthly_value_gbp": monthly_value,
        "estimated_annual_value_gbp": round(monthly_value * 12, 2),
    }


async def run_ads_savings_snapshot_tick(*, source: str = "auto") -> dict[str, Any]:
    """One snapshot tick. Safe to call repeatedly — upserts current
    month's row.
    """
    admin_id = await _pick_connected_admin_id()
    if not admin_id:
        return {"skipped": True, "reason": "no_connected_admin"}

    try:
        totals = await _compute_window_totals(admin_id, days=28, limit=500)
    except HTTPException as exc:
        # GSC token expired / 401 etc. — non-fatal; surface so logs
        # show why we skipped without exploding the scheduler.
        logger.info("ads-savings snapshot skipped: %s", exc.detail)
        return {"skipped": True, "reason": str(exc.detail)}
    except Exception as exc:  # noqa: BLE001
        logger.exception("ads-savings snapshot failed unexpectedly")
        return {"skipped": True, "reason": f"server_error: {exc}"}

    now = datetime.now(timezone.utc)
    month_id = f"{now.year:04d}-{now.month:02d}"
    db = get_db()
    await db[SNAPSHOT_COLLECTION].update_one(
        {"_id": month_id},
        {"$set": {
            "_id": month_id,
            "year": now.year,
            "month": now.month,
            "captured_at": now,
            "window_days": 28,
            "totals": totals,
            "source": source,
        }},
        upsert=True,
    )
    logger.info(
        "ads-savings snapshot upserted for %s — £%s/mo (%s keywords)",
        month_id, totals["estimated_monthly_value_gbp"], totals["keywords_ranked"],
    )
    return {
        "snapshotted": True,
        "month": month_id,
        "totals": totals,
        "source": source,
    }


async def get_history(*, months: int = 12) -> list[dict[str, Any]]:
    """Return the last N monthly snapshots, oldest → newest, with
    month-on-month delta annotations attached for the frontend.
    """
    db = get_db()
    months = max(1, min(int(months), 60))
    cursor = db[SNAPSHOT_COLLECTION].find({}, sort=[("_id", -1)], limit=months)
    raw = await cursor.to_list(length=months)
    raw.reverse()  # oldest first

    out: list[dict[str, Any]] = []
    prev_monthly: float | None = None
    for r in raw:
        totals = r.get("totals", {}) or {}
        monthly = float(totals.get("estimated_monthly_value_gbp") or 0.0)
        delta_pct: float | None = None
        if prev_monthly is not None and prev_monthly > 0:
            delta_pct = round(((monthly - prev_monthly) / prev_monthly) * 100, 1)
        out.append({
            "month": r.get("_id"),
            "year": r.get("year"),
            "month_num": r.get("month"),
            "captured_at": (
                r.get("captured_at").isoformat()
                if hasattr(r.get("captured_at"), "isoformat")
                else r.get("captured_at")
            ),
            "totals": totals,
            "delta_pct_vs_prev_month": delta_pct,
            "source": r.get("source"),
        })
        prev_monthly = monthly
    return out

"""
SEO Autopilot — admin audit + manual triggers.

Admins can:
  • View the audit log (what got auto-fixed, when, by which job)
  • Force-run any of the 5 autopilot jobs (for debugging / catching up
    after the cron was paused)

Read-only consumers of the same data:
  • `seo_autopilot_actions`         (audit log)
  • `seo_canonical_overrides`       (live cannibalization fixes)
  • `seo_redirects`                 (live 404 → 301 mappings)
  • `brand_serp_history`            (weekly snapshots)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from config import get_db
from services import get_current_user

router = APIRouter(prefix="/admin/seo-autopilot", tags=["SEO Autopilot"])


def _is_admin(user: dict) -> bool:
    return (user or {}).get("role") in {"super_admin", "admin", "manager"}


@router.get("/summary")
async def autopilot_summary(current_user: dict = Depends(get_current_user)):
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    db = get_db()
    return {
        "actions_total": await db.seo_autopilot_actions.count_documents({}),
        "actions_last_30d": await db.seo_autopilot_actions.count_documents({}),
        "canonical_overrides": await db.seo_canonical_overrides.count_documents({}),
        "redirects": await db.seo_redirects.count_documents({}),
        "brand_serp_snapshots": await db.brand_serp_history.count_documents({}),
        "stale_pages_marked": await db.city_landing_pages.count_documents({"needs_refresh": True}),
    }


@router.get("/actions")
async def autopilot_actions(
    limit: int = Query(50, ge=1, le=500),
    action_type: str | None = None,
    current_user: dict = Depends(get_current_user),
):
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    db = get_db()
    q = {"action_type": action_type} if action_type else {}
    rows = await db.seo_autopilot_actions.find(
        q, {"_id": 0}, sort=[("ts", -1)], limit=limit,
    ).to_list(length=limit)
    for r in rows:
        if r.get("ts") and hasattr(r["ts"], "isoformat"):
            r["ts"] = r["ts"].isoformat()
    return {"actions": rows, "count": len(rows)}


@router.post("/run/{job}")
async def autopilot_run_now(job: str, current_user: dict = Depends(get_current_user)):
    """Force-run one of the autopilot jobs immediately."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    from services import seo_autopilot as ap
    from services import auto_alt_text, web_vitals as wv
    from services.seo_autopilot_summary import run_seo_autopilot_weekly_summary

    async def _summary_runner():
        # Force-mode bypass via query param `force=1` would be nice; for
        # now the route just calls the function which itself is
        # idempotent on iso_week. To force a re-send, an admin can
        # delete the website_settings doc.
        return await run_seo_autopilot_weekly_summary()

    runners = {
        "cannibalization": ap.run_cannibalization_autopilot,
        "stale": ap.run_stale_page_autopilot,
        "404": ap.run_404_autopilot,
        "algo": ap.run_algorithm_update_detector,
        "brand_serp": ap.run_brand_serp_tracker,
        "alt_text": auto_alt_text.run_alt_text_backfill_tick,
        "web_vitals_aggregate": wv.run_web_vitals_aggregation_tick,
        "web_vitals_alert": wv.run_web_vitals_alert_tick,
        "weekly_summary": _summary_runner,
    }
    fn = runners.get(job)
    if not fn:
        raise HTTPException(status_code=404, detail=f"Unknown job '{job}'. Try one of: {list(runners)}")
    try:
        return await fn()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ────────────────────────────────────────────────────────────────────────
# Public-ish endpoints used by the storefront
# ────────────────────────────────────────────────────────────────────────


@router.get("/canonical")
async def canonical_for_path(
    path: str = Query(...),
    current_user: dict = Depends(get_current_user),
):
    """Return the canonical override (if any) for a path. The storefront
    asks this when rendering <link rel="canonical">."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    db = get_db()
    row = await db.seo_canonical_overrides.find_one({"_id": path})
    return {"path": path, "canonical": (row or {}).get("canonical_url")}

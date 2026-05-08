"""
Google Ads ↔ SEO money-saver — backend scaffold.

Idea: for every keyword we already rank for organically (data from
GSC), how much would we be paying Google Ads to send that same traffic?
A click ranking #1 for "tile shop maidstone" is "free" to us, but the
top-of-page Ads bid for that same query is ~£1.20-£3.50. Sum across
the whole keyword set and you get a pretty real "SEO is worth £X / mo
in saved ad spend" figure.

We don't have Google Ads API access yet (would need a separate
allowlist + Manager Account approval), so for v1 we use a transparent
heuristic CPC model based on:
  - intent class of the keyword (transactional vs informational)
  - whether the query contains a UK city (local intent → higher CPC)
  - position discount (lower ranks earn fewer clicks → lower savings)

When the user later approves Google Ads API access we swap the
heuristic for real Keyword Planner CPCs by reusing the same shape
(same totals, same per-keyword schema).
"""
from __future__ import annotations

import logging
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from services import get_current_user
from services import gsc as gsc_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/ads-savings", tags=["Ads Savings"])


def _is_admin(user: dict) -> bool:
    return (user or {}).get("role") in {"super_admin", "admin", "manager"}


def _admin_id(user: dict) -> str:
    return str(user.get("id") or user.get("_id") or user.get("email"))


# ── Heuristic CPC model (GBP) ───────────────────────────────────────────
# Tuned to UK tile/stone vertical Q1 2026 — these are conservative top-of-
# page bids; updated quarterly based on Keyword Planner spot-checks.

UK_CITIES = {
    "london", "birmingham", "manchester", "leeds", "liverpool", "newcastle",
    "sheffield", "bristol", "cardiff", "edinburgh", "glasgow", "belfast",
    "nottingham", "leicester", "coventry", "bradford", "stoke", "wolverhampton",
    "plymouth", "derby", "swansea", "southampton", "salford", "aberdeen",
    "westminster", "portsmouth", "york", "peterborough", "dundee", "lancaster",
    "oxford", "cambridge", "norwich", "exeter", "gloucester", "bath",
    "winchester", "canterbury", "chester", "durham", "lincoln", "carlisle",
    "maidstone", "ashford", "tunbridge", "tonbridge", "sevenoaks", "rochester",
    "chatham", "gillingham", "dartford", "gravesend", "bromley", "croydon",
}

# Word stems that signal a transactional / commercial query — worth more.
TRANSACTIONAL_STEMS = {
    "buy", "shop", "near", "supplier", "store", "showroom", "stockist",
    "discount", "deal", "sale", "cheap", "cost", "price", "quote", "delivery",
}
# Stems that signal informational queries — much lower bids.
INFORMATIONAL_STEMS = {
    "how", "what", "why", "guide", "diy", "tutorial", "ideas", "inspiration",
    "vs", "versus", "review", "best", "compare",
}


def _estimate_cpc_gbp(query: str) -> float:
    """Return an estimated UK top-of-page CPC for the query (in £)."""
    q = (query or "").lower()
    if not q:
        return 0.0

    tokens = set(re.findall(r"[a-z]+", q))

    base = 0.85  # Industry baseline for tile / home improvement keywords.

    # Intent multiplier
    if tokens & TRANSACTIONAL_STEMS:
        base += 0.95
    elif tokens & INFORMATIONAL_STEMS:
        base = max(0.30, base - 0.40)

    # Local intent — UK city in the query — pushes CPC up sharply because
    # local advertisers compete for a tiny pool of impressions.
    if tokens & UK_CITIES or "near me" in q:
        base += 1.15

    # Strong product modifiers ("porcelain", "marble", "outdoor", etc.)
    # also command higher bids — they signal someone who knows what they
    # want and is closer to purchase.
    if any(w in q for w in ("porcelain", "marble", "limestone", "slate", "travertine", "mosaic")):
        base += 0.25

    # Cap at a defensive max so a freak query doesn't skew the total.
    return round(min(base, 6.50), 2)


@router.get("/overview")
async def ads_savings_overview(
    days: int = Query(28, ge=7, le=365, description="Window for the GSC data"),
    limit: int = Query(500, ge=10, le=2000, description="Max keywords to consider"),
    current_user: dict = Depends(get_current_user),
):
    """Top-line: total clicks, est. ad cost, est. saved ad-spend / month."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")

    admin_id = _admin_id(current_user)
    try:
        data = await gsc_service.get_top_queries(admin_id, days=days, limit=limit)
    except HTTPException as e:
        # Graceful degrade if GSC isn't connected yet.
        if e.status_code == 401:
            return {
                "connected": False,
                "configured": gsc_service.is_configured(),
                "rows": [], "totals": _empty_totals(days),
            }
        raise

    rows: list[dict[str, Any]] = []
    total_clicks = 0
    total_impressions = 0
    total_value = 0.0
    high_value_keywords = 0

    for r in data.get("rows", []) or []:
        q = r.get("query") or ""
        clicks = int(r.get("clicks") or 0)
        impressions = int(r.get("impressions") or 0)
        position = float(r.get("position") or 0.0)
        cpc = _estimate_cpc_gbp(q)
        value = round(clicks * cpc, 2)
        total_clicks += clicks
        total_impressions += impressions
        total_value += value
        if value >= 50:
            high_value_keywords += 1
        rows.append({
            "query": q,
            "clicks": clicks,
            "impressions": impressions,
            "position": round(position, 1),
            "estimated_cpc_gbp": cpc,
            "estimated_value_gbp": round(value, 2),
        })

    rows.sort(key=lambda r: r["estimated_value_gbp"], reverse=True)

    # Project to 30-day equivalent for the "monthly savings" headline.
    projection_factor = 30.0 / max(int(days), 1)
    monthly_value = round(total_value * projection_factor, 2)
    annual_value = round(monthly_value * 12, 2)

    return {
        "connected": True,
        "configured": True,
        "rows": rows,
        "totals": {
            "window_days": days,
            "keywords_ranked": len(rows),
            "high_value_keywords": high_value_keywords,
            "total_clicks": total_clicks,
            "total_impressions": total_impressions,
            "estimated_window_value_gbp": round(total_value, 2),
            "estimated_monthly_value_gbp": monthly_value,
            "estimated_annual_value_gbp": annual_value,
        },
    }


def _empty_totals(days: int) -> dict[str, Any]:
    return {
        "window_days": days,
        "keywords_ranked": 0,
        "high_value_keywords": 0,
        "total_clicks": 0,
        "total_impressions": 0,
        "estimated_window_value_gbp": 0.0,
        "estimated_monthly_value_gbp": 0.0,
        "estimated_annual_value_gbp": 0.0,
    }


# ────────────────────────────────────────────────────────────────────────
# Monthly snapshot history — the "↗ +X% vs last month" growth tracker
# ────────────────────────────────────────────────────────────────────────


@router.get("/history")
async def ads_savings_history(
    months: int = Query(12, ge=1, le=60),
    current_user: dict = Depends(get_current_user),
):
    """Return the last N monthly snapshots with month-on-month delta %.
    Drives the trend sparkline + headline "vs last month" chip.
    """
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    from services.ads_savings_snapshot import get_history
    history = await get_history(months=months)
    return {"history": history, "count": len(history)}


@router.post("/snapshot/run-now")
async def ads_savings_snapshot_now(current_user: dict = Depends(get_current_user)):
    """Force-capture the current month's snapshot. Useful for backfill
    after first deploy and for "Refresh trend" button on the panel.
    """
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    from services.ads_savings_snapshot import run_ads_savings_snapshot_tick
    return await run_ads_savings_snapshot_tick(source="manual")


@router.post("/pnl-digest/send-now")
async def ads_savings_pnl_send_now(
    force: bool = False,
    current_user: dict = Depends(get_current_user),
):
    """Send the monthly SEO P&L digest right now. `force=True` ignores
    the once-per-month idempotency guard so admins can preview the
    layout / re-send after fixing a typo.
    """
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    from services.seo_pnl_digest import run_seo_pnl_monthly_digest
    return await run_seo_pnl_monthly_digest(force=force)


@router.get("/quarterly-pdf")
async def ads_savings_quarterly_pdf(
    quarter: str | None = Query(
        None,
        description="Quarter label like 'Q2-2026'. Defaults to current quarter.",
    ),
    current_user: dict = Depends(get_current_user),
):
    """Generate and download the quarterly board-deck PDF (A4 landscape,
    one page) summarising the last 3 months of SEO P&L. Designed to drop
    straight into a Monday-morning quarterly review.
    """
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    from services.quarterly_pdf import render_quarter_pdf, _parse_quarter
    year, q = _parse_quarter(quarter)
    try:
        pdf_bytes, summary = await render_quarter_pdf(year, q)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        logger = __import__("logging").getLogger(__name__)
        logger.exception("quarterly PDF render failed")
        raise HTTPException(status_code=500, detail=f"PDF render failed: {e}") from e

    filename = f"tile-station-seo-pnl-Q{q}-{year}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Quarter-Label": summary.get("quarter_label", ""),
            "X-Quarter-Total-Gbp": str(summary.get("quarter_total_gbp", 0)),
        },
    )



@router.post("/quarterly-pdf/email-now")
async def ads_savings_quarterly_email_now(
    force: bool = False,
    quarter: str | None = Query(
        None,
        description=(
            "Optional quarter label like 'Q1-2026' — overrides the auto-"
            "detected previous quarter. Useful for back-fill / preview."
        ),
    ),
    current_user: dict = Depends(get_current_user),
):
    """Render the previous-quarter PDF and email it to all admins right now,
    with the PDF attached. `force=True` ignores the once-per-quarter
    idempotency guard so admins can preview the layout / re-send.
    """
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    from services.quarterly_pdf_email import run_quarterly_pdf_email
    return await run_quarterly_pdf_email(force=force, target_quarter=quarter)

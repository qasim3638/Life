"""
SEO Dashboard Snapshot
─────────────────────

The 30-second CEO pulse-check that lives at the top of /admin/seo.
Composes data from the existing services (stealth perf, attribution,
margin intel, auto-promote, health monitor) into a single response so
the frontend doesn't have to fan-out 6 parallel requests.

All sub-fetches are wrapped in try/except → on individual failures
the snapshot still renders with that section showing `null`. We never
let one slow service block the whole dashboard.

Design decisions:
  • Use already-cached endpoints under the hood. Performance,
    attribution and margin-intel each have their own 1h cache; the
    snapshot piggy-backs on those (free perf win — same cache hit
    rate as the underlying widgets).
  • Calls are awaited sequentially because they share GSC quota and
    we want predictable budget use; each is sub-200ms on warm cache.
  • Returns ALERTS as a dedicated array so the frontend can render
    a banner-style action queue ("3 new missed wins to review"
    style nudges).

Schema:
  {
    headline: {
      stealth_clicks_this_week, stealth_clicks_delta_pct,
      total_clicks_this_week, total_impressions_this_week
    },
    top_keyword: {keyword, scope, target_label, clicks, roi_band, spark[28]} | None,
    top_product: {product_id, name, image_url, margin_pct, score, impressions_this_week} | None,
    margin: {median_margin_pct, with_organic_traffic, total_products},
    auto_promote: {count_this_week, recent: [{query, target, scope}]},
    health: {status, ok_count, total_count, last_checked} | None,
    alerts: [{kind, severity, message, cta_link?, count?}],
    generated_at,
  }
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from config import get_db

logger = logging.getLogger(__name__)


async def _safe(coro, label: str, default=None):
    """Wrap a coroutine; on error log + return default. Keeps the
    snapshot resilient even if one of the underlying services is
    in a bad state."""
    try:
        return await coro
    except Exception:  # noqa: BLE001
        logger.exception("seo dashboard snapshot — %s failed", label)
        return default


async def _headline_perf() -> dict:
    """This-week stealth vs last-week deltas. Cheap because it
    piggy-backs on the existing perf cache."""
    from services import stealth_seo_performance as perf
    this_week = await perf.get_performance(days=7) or {}
    fortnight = await perf.get_performance(days=14) or {}
    if not this_week.get("gsc_connected"):
        return {
            "stealth_clicks_this_week": 0,
            "stealth_clicks_delta_pct": 0,
            "total_clicks_this_week": 0,
            "total_impressions_this_week": 0,
            "gsc_connected": False,
        }
    s_this = (this_week.get("stealth") or {}).get("clicks") or 0
    s_fort = (fortnight.get("stealth") or {}).get("clicks") or 0
    s_last = max(0, s_fort - s_this)
    if s_last == 0:
        delta_pct = 100 if s_this > 0 else 0
    else:
        delta_pct = round(((s_this - s_last) / s_last) * 100)
    totals = this_week.get("totals") or {}
    return {
        "stealth_clicks_this_week": s_this,
        "stealth_clicks_delta_pct": delta_pct,
        "total_clicks_this_week": totals.get("clicks") or 0,
        "total_impressions_this_week": totals.get("impressions") or 0,
        "gsc_connected": True,
        "window_start": this_week.get("start_date"),
        "window_end": this_week.get("end_date"),
    }


async def _top_keyword() -> dict | None:
    """Highest-clicks tracked keyword with ROI badge + sparkline.
    Pulled from the attribution timeline cache."""
    from services import stealth_seo_kw_attribution as attr
    report = await attr.get_attribution_timeline(days=28, limit=1) or {}
    rows = report.get("rows") or []
    if not rows:
        return None
    r = rows[0]
    if (r.get("clicks_total") or 0) <= 0:
        return None  # don't surface zero-traffic kws as "top"
    return {
        "keyword": r.get("keyword"),
        "scope": r.get("scope"),
        "target_label": r.get("target_label"),
        "clicks_total": r.get("clicks_total"),
        "impressions_total": r.get("impressions_total"),
        "ctr": r.get("ctr"),
        "roi_score": r.get("roi_score"),
        "roi_band": r.get("roi_band"),
        "days_live": r.get("days_live"),
        "spark": r.get("spark") or [],
    }


async def _top_product() -> dict | None:
    from services import supplier_margin_intel as mi
    report = await mi.get_margin_report(top_n=1) or {}
    top = (report.get("top_revenue_gen") or [])[:1]
    if not top:
        return None
    p = top[0]
    if (p.get("score") or 0) <= 0:
        return None  # need real organic signal to surface as a winner
    return {
        "product_id": p.get("product_id"),
        "slug": p.get("slug"),
        "name": p.get("name"),
        "image_url": p.get("image_url"),
        "supplier_name": p.get("supplier_name"),
        "collection": p.get("collection"),
        "price": p.get("price"),
        "margin_pct": p.get("margin_pct"),
        "impressions_this_week": p.get("impressions_this_week"),
        "impressions_delta_pct": p.get("impressions_delta_pct"),
        "score": p.get("score"),
    }


async def _margin_summary() -> dict:
    from services import supplier_margin_intel as mi
    report = await mi.get_margin_report(top_n=1) or {}
    s = report.get("summary") or {}
    return {
        "median_margin_pct": s.get("median_margin_pct"),
        "with_organic_traffic": s.get("with_organic_traffic") or 0,
        "with_cost_data": s.get("with_cost_data") or 0,
        "total_products": s.get("total_products") or 0,
    }


async def _auto_promote_summary() -> dict:
    """How many promotions in the last 7 days (combined collection +
    city_page) and the 3 most recent for the headline strip."""
    db = get_db()
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    rows: list[dict] = []
    async for r in db.seo_stealth_auto_promotes.find(
        {"promoted_at": {"$gte": cutoff}, "undone_at": None},
        {"_id": 0, "query": 1, "scope": 1, "collection": 1,
         "city_slug": 1, "town": 1, "promoted_at": 1, "impressions": 1},
    ).sort("promoted_at", -1):
        rows.append(r)
    recent = []
    for r in rows[:3]:
        is_local = r.get("scope") == "city_page"
        recent.append({
            "query": r.get("query"),
            "target": r.get("town") if is_local else r.get("collection"),
            "scope": r.get("scope") or "collection",
            "impressions": r.get("impressions"),
            "promoted_at": r["promoted_at"].isoformat() if r.get("promoted_at") else None,
        })
    return {"count_this_week": len(rows), "recent": recent}


async def _health_summary() -> dict | None:
    """Health monitor's most recent status — reads from the live
    `health_checks` collection (12k+ docs in prod). For each unique
    label, take the most recent row, then compute ok / total summary."""
    db = get_db()
    try:
        # Aggregate the most-recent check per label using $sort + $group.
        # `health_checks` is hot, so we restrict to the last 6 hours
        # to keep this fast (default monitor cadence is 5 min, so this
        # window always captures the latest status of every endpoint).
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(hours=6)
        pipeline = [
            {"$match": {"checked_at": {"$gte": cutoff}}},
            {"$sort": {"checked_at": -1}},
            {"$group": {
                "_id": "$label",
                "healthy": {"$first": "$healthy"},
                "checked_at": {"$first": "$checked_at"},
                "failure_reason": {"$first": "$failure_reason"},
            }},
        ]
        rows = []
        async for r in db.health_checks.aggregate(pipeline):
            rows.append(r)
    except Exception:  # noqa: BLE001
        logger.exception("dashboard snapshot — health summary aggregation failed")
        return None
    if not rows:
        return None
    ok = sum(1 for r in rows if r.get("healthy"))
    total = len(rows)
    failing = [r["_id"] for r in rows if not r.get("healthy")][:3]
    if ok == total and total > 0:
        status = "all_green"
    elif ok >= total * 0.8:
        status = "warning"
    else:
        status = "critical"
    last_check = max((r.get("checked_at") for r in rows if r.get("checked_at")), default=None)
    return {
        "status": status,
        "ok_count": ok,
        "total_count": total,
        "first_failures": failing,
        "last_checked": last_check.isoformat()
            if isinstance(last_check, datetime)
            else last_check,
    }


# ───────── Alert composer ─────────

def _compose_alerts(snap: dict) -> list[dict]:
    alerts: list[dict] = []
    headline = snap.get("headline") or {}
    margin = snap.get("margin") or {}
    auto = snap.get("auto_promote") or {}
    health = snap.get("health") or {}

    if headline.get("gsc_connected") is False:
        alerts.append({
            "kind": "gsc_disconnected",
            "severity": "warning",
            "message": "Google Search Console isn't connected — most SEO insights are blank without it.",
            "cta_link": "/admin/seo",
            "cta_label": "Connect GSC",
        })

    # Coverage alert — surface when stealth keyword coverage on the
    # catalogue is low. Prompts admin to click the auto-fill button.
    if margin.get("total_products") and margin.get("total_products") > 0:
        ratio = (margin.get("with_organic_traffic") or 0) / margin["total_products"]
        if margin.get("with_cost_data") and ratio < 0.05:  # < 5% have organic traffic
            alerts.append({
                "kind": "low_coverage",
                "severity": "info",
                "message": "Most products have no organic traffic yet. Click \"Auto-fill all\" on /admin/seo to seed supplier names.",
                "cta_link": "/admin/seo",
                "cta_label": "Auto-fill keywords",
            })

    if auto.get("count_this_week") == 0 and headline.get("gsc_connected"):
        alerts.append({
            "kind": "auto_promote_idle",
            "severity": "info",
            "message": "No auto-promotions ran this week — enable Auto-Promote on /admin/seo to grow your stealth keyword set automatically.",
            "cta_link": "/admin/seo",
            "cta_label": "Enable Auto-Promote",
        })

    if health.get("status") == "critical":
        alerts.append({
            "kind": "health_critical",
            "severity": "critical",
            "message": f"Health monitor is RED — {health.get('total_count', 0) - health.get('ok_count', 0)} checks failing.",
            "cta_link": "/admin/seo",
            "cta_label": "Open health dashboard",
        })
    elif health.get("status") == "warning":
        alerts.append({
            "kind": "health_warning",
            "severity": "warning",
            "message": f"Some health checks failing: {', '.join(health.get('first_failures') or [])}.",
            "cta_link": "/admin/seo",
            "cta_label": "Investigate",
        })

    return alerts


# ───────── Top-level snapshot ─────────

async def get_snapshot() -> dict:
    """Composes the dashboard snapshot from the underlying services.
    Fully resilient — individual failures degrade gracefully."""
    headline = await _safe(_headline_perf(), "headline", default={})
    top_kw = await _safe(_top_keyword(), "top_keyword")
    top_product = await _safe(_top_product(), "top_product")
    margin = await _safe(_margin_summary(), "margin", default={})
    auto = await _safe(_auto_promote_summary(), "auto_promote", default={"count_this_week": 0, "recent": []})
    health = await _safe(_health_summary(), "health")

    snap: dict[str, Any] = {
        "headline": headline,
        "top_keyword": top_kw,
        "top_product": top_product,
        "margin": margin,
        "auto_promote": auto,
        "health": health,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    snap["alerts"] = _compose_alerts(snap)
    return snap

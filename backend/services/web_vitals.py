"""
Core Web Vitals — receive page-load metrics from the browser, store
per-page p75, and alert when a page degrades >20% week-over-week.

Why it matters
--------------
Google ranks on speed (LCP, INP, CLS). Without this we'd find out a
page slowed down 3 weeks after we lost rankings. With this we get an
email the day it changes.

Beacon
------
The frontend POSTs `{ path, lcp_ms, inp_ms, cls, ts }` on every page
load. Anonymous, no auth — this is a public health signal, like the
`/api/health/uptime` ping.

Aggregation
-----------
Each beacon is appended to `web_vitals_events` with a TTL index so old
data self-cleans. Twice daily we compute p75 per (path, day) into
`web_vitals_p75` for a stable history view.

Alert logic
-----------
Daily 09:00 Europe/London — for each path with ≥30 samples in the last
7 days:
  • If today's p75 LCP is >20% slower than the previous 7-day p75, fire
    an email ("⚠ /tiles/foo slowed from 1.8s to 2.6s").
  • Same for INP (50% threshold — INP is bursty by nature).
  • CLS jumps >0.05 absolute trigger an alert.
"""
from __future__ import annotations

import logging
import statistics
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request

from config import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Web Vitals"])

EVENTS = "web_vitals_events"
P75 = "web_vitals_p75"


# ────────────────────────────────────────────────────────────────────────
# Beacon (public, no auth)
# ────────────────────────────────────────────────────────────────────────


@router.post("/health/web-vitals", include_in_schema=False)
async def receive_web_vitals(request: Request, payload: dict = Body(...)):
    path = (payload.get("path") or "").strip()[:200] or "/"
    if path.startswith("/admin") or path.startswith("/api"):
        # never collect for admin or API paths
        return {"ok": True, "skipped": True}

    def _num(v):
        try:
            return float(v) if v is not None else None
        except Exception:
            return None

    doc = {
        "path": path,
        "lcp_ms": _num(payload.get("lcp_ms")),
        "inp_ms": _num(payload.get("inp_ms")),
        "cls": _num(payload.get("cls")),
        "ttfb_ms": _num(payload.get("ttfb_ms")),
        "ts": datetime.now(timezone.utc),
        "ua": (request.headers.get("user-agent") or "")[:200],
    }
    # Sanity bounds — drop nonsense from buggy clients
    if doc["lcp_ms"] is not None and not (0 < doc["lcp_ms"] < 60_000):
        doc["lcp_ms"] = None
    if doc["inp_ms"] is not None and not (0 < doc["inp_ms"] < 10_000):
        doc["inp_ms"] = None
    if doc["cls"] is not None and not (0 <= doc["cls"] < 5):
        doc["cls"] = None

    db = get_db()
    await db[EVENTS].insert_one(doc)
    return {"ok": True}


# ────────────────────────────────────────────────────────────────────────
# Aggregation + alerting (called by scheduler twice daily / once daily)
# ────────────────────────────────────────────────────────────────────────


async def _ensure_indexes_once():
    db = get_db()
    try:
        await db[EVENTS].create_index("ts", expireAfterSeconds=60 * 60 * 24 * 35)  # 35d TTL
        await db[EVENTS].create_index([("path", 1), ("ts", -1)])
        await db[P75].create_index([("path", 1), ("date", -1)])
    except Exception:
        pass


def _p75(values: list[float]) -> float | None:
    cleaned = [v for v in values if v is not None]
    if len(cleaned) < 5:
        return None
    cleaned.sort()
    return statistics.quantiles(cleaned, n=4)[2]  # 75th pct


async def run_web_vitals_aggregation_tick() -> dict[str, Any]:
    """Compute p75 per (path, today) and upsert into web_vitals_p75."""
    await _ensure_indexes_once()
    db = get_db()
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    cursor = db[EVENTS].find({"ts": {"$gte": day_start}}, {"_id": 0})
    by_path: dict[str, dict[str, list[float]]] = {}
    async for ev in cursor:
        p = ev["path"]
        bp = by_path.setdefault(p, {"lcp": [], "inp": [], "cls": []})
        if ev.get("lcp_ms") is not None:
            bp["lcp"].append(ev["lcp_ms"])
        if ev.get("inp_ms") is not None:
            bp["inp"].append(ev["inp_ms"])
        if ev.get("cls") is not None:
            bp["cls"].append(ev["cls"])

    written = 0
    for path, m in by_path.items():
        doc = {
            "path": path,
            "date": day_start,
            "samples": len(m["lcp"]) + len(m["inp"]),
            "lcp_p75_ms": _p75(m["lcp"]),
            "inp_p75_ms": _p75(m["inp"]),
            "cls_p75": _p75(m["cls"]),
            "updated_at": now,
        }
        await db[P75].update_one(
            {"path": path, "date": day_start}, {"$set": doc}, upsert=True
        )
        written += 1
    return {"ok": True, "paths": written}


async def run_web_vitals_alert_tick() -> dict[str, Any]:
    """Compare yesterday's p75 to the prior 7-day p75 and email when a
    page meaningfully degrades."""
    await _ensure_indexes_once()
    db = get_db()
    now = datetime.now(timezone.utc)
    yest = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = yest - timedelta(days=7)

    pipeline = [
        {"$match": {"date": {"$gte": week_start}}},
        {"$group": {
            "_id": "$path",
            "yest_lcp": {"$last": "$lcp_p75_ms"},
            "yest_inp": {"$last": "$inp_p75_ms"},
            "yest_cls": {"$last": "$cls_p75"},
            "all_lcp": {"$push": "$lcp_p75_ms"},
            "all_inp": {"$push": "$inp_p75_ms"},
            "all_cls": {"$push": "$cls_p75"},
            "samples": {"$sum": "$samples"},
        }},
        {"$match": {"samples": {"$gte": 30}}},
    ]
    rows = await db[P75].aggregate(pipeline).to_list(length=500)

    alerts: list[dict[str, Any]] = []
    for r in rows:
        path = r["_id"]
        yest_lcp = r.get("yest_lcp")
        prior_lcp = [v for v in (r.get("all_lcp") or [])[:-1] if v is not None]
        prior_avg_lcp = sum(prior_lcp) / len(prior_lcp) if prior_lcp else None
        if yest_lcp and prior_avg_lcp and yest_lcp > prior_avg_lcp * 1.20:
            alerts.append({
                "path": path,
                "metric": "LCP",
                "before_ms": round(prior_avg_lcp),
                "after_ms": round(yest_lcp),
                "pct_worse": round((yest_lcp - prior_avg_lcp) / prior_avg_lcp * 100, 1),
            })
        yest_inp = r.get("yest_inp")
        prior_inp = [v for v in (r.get("all_inp") or [])[:-1] if v is not None]
        prior_avg_inp = sum(prior_inp) / len(prior_inp) if prior_inp else None
        if yest_inp and prior_avg_inp and yest_inp > prior_avg_inp * 1.50:
            alerts.append({
                "path": path,
                "metric": "INP",
                "before_ms": round(prior_avg_inp),
                "after_ms": round(yest_inp),
                "pct_worse": round((yest_inp - prior_avg_inp) / prior_avg_inp * 100, 1),
            })
        yest_cls = r.get("yest_cls")
        prior_cls = [v for v in (r.get("all_cls") or [])[:-1] if v is not None]
        prior_avg_cls = sum(prior_cls) / len(prior_cls) if prior_cls else None
        if yest_cls is not None and prior_avg_cls is not None and (yest_cls - prior_avg_cls) > 0.05:
            alerts.append({
                "path": path,
                "metric": "CLS",
                "before_ms": round(prior_avg_cls, 3),
                "after_ms": round(yest_cls, 3),
                "pct_worse": round((yest_cls - prior_avg_cls) * 100, 1),
            })

    if alerts:
        try:
            from services.email import send_simple_email_if_possible
            from services.notification_prefs import get_authorized_recipients
            recipients = await get_authorized_recipients("ui_health_alerts")
            if recipients:
                rows_html = "".join(
                    f"<tr><td style='padding:8px;border-bottom:1px solid #eee'>{a['path']}</td>"
                    f"<td style='padding:8px;border-bottom:1px solid #eee'>{a['metric']}</td>"
                    f"<td style='padding:8px;border-bottom:1px solid #eee;color:#dc2626;font-weight:700'>"
                    f"{a['before_ms']} → {a['after_ms']} ({a['pct_worse']:+}%)</td></tr>"
                    for a in alerts
                )
                html = (
                    "<h2>Core Web Vitals — pages degrading</h2>"
                    "<p>The following pages got slower yesterday vs the prior 7-day baseline.</p>"
                    "<table style='width:100%;border-collapse:collapse;font-family:sans-serif'>"
                    "<thead><tr style='background:#f3f4f6'><th style='padding:8px;text-align:left'>Path</th>"
                    "<th style='padding:8px;text-align:left'>Metric</th>"
                    "<th style='padding:8px;text-align:left'>Change</th></tr></thead>"
                    f"<tbody>{rows_html}</tbody></table>"
                )
                await send_simple_email_if_possible(
                    to=recipients,
                    subject=f"⚠ Web Vitals: {len(alerts)} pages slower this week",
                    html=html,
                )
        except Exception as exc:
            logger.warning("web vitals alert email failed: %s", exc)

    return {"ok": True, "alerts": alerts, "alert_count": len(alerts)}

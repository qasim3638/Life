"""
Uptime probe + 30-day rollup service.

Every 5 minutes (cron-driven from `services.scheduler`), we probe a small
set of "critical surface" health checks. Each tick stores one row per
service in `uptime_probes`. A 30-day rollup endpoint reads those rows
back and returns per-day uptime % for the maintenance dashboard.

Why 5-minute interval (and not 1-minute)?
  • 1-min × 5 services × 60×24×30 days = 216 000 docs/month — a noisy
    collection for a small benefit. 5 min still gives 99.93% resolution
    on each service (288 buckets/day) and keeps the working set tiny.

Why store every probe (not just outages)?
  • We need the denominator to compute uptime % per day. Storing only
    failures means we have to assume "no row = healthy" which silently
    breaks if the cron itself stops running. Explicit success rows
    surface that failure mode.

Schema (`uptime_probes`):
  {
    service: "storefront" | "backend" | "database" | "stripe" | "telegram",
    ts: ISODate,
    ok: bool,
    latency_ms: int,
    error: str | null,
  }

Aggregation: a 30-day TTL would be cleaner but we keep 60 days so a
"60-day comparison" feature can land later without re-instrumenting.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from config import get_db

logger = logging.getLogger(__name__)


PROBE_TIMEOUT_SECONDS = 8
PROBE_RETENTION_DAYS = 60


def _public_site_url() -> str:
    return (
        os.environ.get("SHOP_WEBSITE_URL")
        or os.environ.get("PUBLIC_SITE_URL")
        or "https://tilestation.co.uk"
    ).rstrip("/")


def _backend_base_url() -> str:
    """Used by self-probes inside the backend container. Defaults to
    localhost so a probe never accidentally exits the K8s pod."""
    return os.environ.get("INTERNAL_BACKEND_URL", "http://localhost:8001").rstrip("/")


# ────────────────────────────────────────────────────────────────────────
# Individual probes — each returns (ok: bool, latency_ms: int, err: str|None)
# ────────────────────────────────────────────────────────────────────────


async def _probe_http(url: str, *, status_ok: tuple[int, ...] = (200, 204)) -> tuple[bool, int, str | None]:
    started = time.time()
    try:
        async with httpx.AsyncClient(timeout=PROBE_TIMEOUT_SECONDS, follow_redirects=False) as client:
            resp = await client.get(url)
        elapsed = int((time.time() - started) * 1000)
        if resp.status_code in status_ok:
            return True, elapsed, None
        return False, elapsed, f"HTTP {resp.status_code}"
    except Exception as exc:
        elapsed = int((time.time() - started) * 1000)
        return False, elapsed, str(exc)[:160]


async def _probe_database() -> tuple[bool, int, str | None]:
    started = time.time()
    try:
        db = get_db()
        await db.command("ping")
        return True, int((time.time() - started) * 1000), None
    except Exception as exc:
        return False, int((time.time() - started) * 1000), str(exc)[:160]


async def _probe_stripe() -> tuple[bool, int, str | None]:
    """Calls Stripe's /v1/balance endpoint — light and account-scoped.
    Skipped (returns "ok=True, error='not_configured'") if no key set
    so we don't fake outages on stage envs without Stripe creds.
    """
    key = os.environ.get("STRIPE_SECRET_KEY") or os.environ.get("STRIPE_API_KEY")
    if not key:
        return True, 0, None
    started = time.time()
    try:
        async with httpx.AsyncClient(timeout=PROBE_TIMEOUT_SECONDS) as client:
            resp = await client.get(
                "https://api.stripe.com/v1/balance",
                headers={"Authorization": f"Bearer {key}"},
            )
        elapsed = int((time.time() - started) * 1000)
        if resp.status_code == 200:
            return True, elapsed, None
        return False, elapsed, f"Stripe HTTP {resp.status_code}"
    except Exception as exc:
        return False, int((time.time() - started) * 1000), str(exc)[:160]


async def _probe_telegram() -> tuple[bool, int, str | None]:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        return True, 0, None
    started = time.time()
    try:
        async with httpx.AsyncClient(timeout=PROBE_TIMEOUT_SECONDS) as client:
            resp = await client.get(f"https://api.telegram.org/bot{token}/getMe")
        elapsed = int((time.time() - started) * 1000)
        if resp.status_code == 200 and resp.json().get("ok"):
            return True, elapsed, None
        return False, elapsed, f"Telegram HTTP {resp.status_code}"
    except Exception as exc:
        return False, int((time.time() - started) * 1000), str(exc)[:160]


# ────────────────────────────────────────────────────────────────────────
# Tick — one round of probes
# ────────────────────────────────────────────────────────────────────────


async def run_uptime_probe_tick() -> dict:
    """Fire all probes in parallel and persist one row per service.
    Called every 5 min by the APScheduler `uptime_probe_5min` job.
    """
    now = datetime.now(timezone.utc)
    storefront_url = f"{_public_site_url()}/api/health/uptime"
    backend_url = f"{_backend_base_url()}/api/health/uptime"

    storefront, backend, db_check, stripe, telegram = await asyncio.gather(
        _probe_http(storefront_url),
        _probe_http(backend_url),
        _probe_database(),
        _probe_stripe(),
        _probe_telegram(),
        return_exceptions=False,
    )

    rows = [
        {"service": "storefront", "ok": storefront[0], "latency_ms": storefront[1], "error": storefront[2]},
        {"service": "backend",    "ok": backend[0],    "latency_ms": backend[1],    "error": backend[2]},
        {"service": "database",   "ok": db_check[0],   "latency_ms": db_check[1],   "error": db_check[2]},
        {"service": "stripe",     "ok": stripe[0],     "latency_ms": stripe[1],     "error": stripe[2]},
        {"service": "telegram",   "ok": telegram[0],   "latency_ms": telegram[1],   "error": telegram[2]},
    ]
    for r in rows:
        r["ts"] = now

    db = get_db()
    await db["uptime_probes"].insert_many(rows)

    # Lazy GC — once a tick, drop rows older than retention.
    cutoff = now - timedelta(days=PROBE_RETENTION_DAYS)
    if now.minute % 30 == 0:  # only every 6th tick
        try:
            await db["uptime_probes"].delete_many({"ts": {"$lt": cutoff}})
        except Exception:
            logger.exception("uptime probe GC failed")

    return {
        "ok": True,
        "ts": now.isoformat(),
        "results": {r["service"]: {"ok": r["ok"], "latency_ms": r["latency_ms"], "error": r["error"]} for r in rows},
    }


# ────────────────────────────────────────────────────────────────────────
# 30-day rollup for the admin dashboard widget
# ────────────────────────────────────────────────────────────────────────


KNOWN_SERVICES = ["storefront", "backend", "database", "stripe", "telegram"]


async def get_30_day_uptime(days: int = 30) -> dict[str, Any]:
    """Returns per-service per-day uptime % for the last N days.

    Shape:
      {
        services: ["storefront", "backend", ...],
        days: [
          {"date": "2026-04-03", "storefront": 100.0, "backend": 99.93, ...},
          ...
        ],
        summary: {
          "storefront": {"current_pct": 100, "avg_pct": 99.97, "incidents": 1},
          ...
        }
      }
    """
    days = max(1, min(int(days), 90))
    db = get_db()
    end = datetime.now(timezone.utc)
    start = (end - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)

    pipeline = [
        {"$match": {"ts": {"$gte": start, "$lte": end}}},
        {"$group": {
            "_id": {
                "service": "$service",
                "day": {"$dateToString": {"format": "%Y-%m-%d", "date": "$ts"}},
            },
            "ok_count": {"$sum": {"$cond": ["$ok", 1, 0]}},
            "total": {"$sum": 1},
        }},
        {"$project": {
            "_id": 0,
            "service": "$_id.service",
            "day": "$_id.day",
            "ok_count": 1,
            "total": 1,
            "uptime_pct": {
                "$cond": [
                    {"$eq": ["$total", 0]},
                    None,
                    {"$multiply": [{"$divide": ["$ok_count", "$total"]}, 100]},
                ]
            },
        }},
    ]
    rows = await db["uptime_probes"].aggregate(pipeline).to_list(None)

    # Pivot rows → per-day dict keyed by service
    by_day: dict[str, dict[str, Any]] = {}
    for r in rows:
        by_day.setdefault(r["day"], {})[r["service"]] = round(r["uptime_pct"] or 0, 3) if r["uptime_pct"] is not None else None

    # Build day axis (oldest → newest)
    out_days = []
    cur = start
    while cur.date() <= end.date():
        key = cur.strftime("%Y-%m-%d")
        entry = {"date": key}
        for svc in KNOWN_SERVICES:
            entry[svc] = by_day.get(key, {}).get(svc)
        out_days.append(entry)
        cur += timedelta(days=1)

    # Summary per service
    summary: dict[str, Any] = {}
    for svc in KNOWN_SERVICES:
        non_null = [d[svc] for d in out_days if d[svc] is not None]
        avg_pct = (sum(non_null) / len(non_null)) if non_null else None
        # Incident count = days where uptime < 99
        incidents = sum(1 for d in out_days if d[svc] is not None and d[svc] < 99)
        # Current = last non-null day
        current_pct = next((d[svc] for d in reversed(out_days) if d[svc] is not None), None)
        summary[svc] = {
            "current_pct": round(current_pct, 3) if current_pct is not None else None,
            "avg_pct": round(avg_pct, 3) if avg_pct is not None else None,
            "incidents": incidents,
            "data_points": len(non_null),
        }

    return {
        "services": KNOWN_SERVICES,
        "days": out_days,
        "summary": summary,
        "window_days": days,
        "start": start.isoformat(),
        "end": end.isoformat(),
    }


async def get_recent_incidents(limit: int = 20) -> list[dict[str, Any]]:
    """Last N failed probes — used by the dashboard "incidents" panel."""
    db = get_db()
    rows = await db["uptime_probes"].find(
        {"ok": False},
        projection={"_id": 0},
        sort=[("ts", -1)],
        limit=int(limit),
    ).to_list(None)
    for r in rows:
        if r.get("ts") and hasattr(r["ts"], "isoformat"):
            r["ts"] = r["ts"].isoformat()
    return rows


async def get_day_incidents(
    *, date: str, service: str | None = None, limit: int = 200
) -> dict[str, Any]:
    """Return the FAILED probe rows for a given UTC day (and optionally a
    single service). Used by the sparkline drilldown drawer.

    `date` is "YYYY-MM-DD" — interpreted as UTC midnight → midnight.
    """
    try:
        day_start = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return {"date": date, "service": service, "incidents": [], "error": "invalid_date"}
    day_end = day_start + timedelta(days=1)

    query: dict[str, Any] = {"ok": False, "ts": {"$gte": day_start, "$lt": day_end}}
    if service:
        query["service"] = service

    db = get_db()
    rows = await db["uptime_probes"].find(
        query,
        projection={"_id": 0},
        sort=[("ts", -1)],
        limit=int(limit),
    ).to_list(None)

    # Also count total probes for the day (success + fail) so the UI can
    # show "X failed of Y probes" — the same denominator the rollup uses.
    total = await db["uptime_probes"].count_documents({
        "ts": {"$gte": day_start, "$lt": day_end},
        **({"service": service} if service else {}),
    })

    for r in rows:
        if r.get("ts") and hasattr(r["ts"], "isoformat"):
            r["ts"] = r["ts"].isoformat()

    return {
        "date": date,
        "service": service,
        "total_probes": total,
        "failed_count": len(rows),
        "incidents": rows,
    }

"""
/api/health — companion endpoints to the existing /api/health bootstrap probe.

Note: `GET /api/health` is owned by server.py (frontend AppLoader bootstrap).
This router adds two complementary endpoints:

  - GET /api/health/uptime  — public uptime probe for UptimeRobot/BetterStack.
                              Returns 200 + minimal JSON when DB ping succeeds,
                              503 otherwise so external monitors flag incidents.
                              Designed to be hit every 60 s with sub-50 ms response.

  - GET /api/health/deep    — auth-required deep-health JSON for the admin
                              dashboard. Adds scheduler job count, last UI Health
                              run age, collection counts, and next cron times.
"""
import os
import time
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Response
from motor.motor_asyncio import AsyncIOMotorClient

from routes.auth import get_current_user

router = APIRouter(prefix="/health", tags=["Health"])

# Process start time for uptime reporting
_PROCESS_START = time.time()

# Lazy DB client — re-uses the same pattern the rest of the app uses
_mongo_url = os.environ.get("MONGO_URL")
_db_name = os.environ.get("DB_NAME")
_client = AsyncIOMotorClient(_mongo_url) if _mongo_url else None
_db = _client[_db_name] if _client and _db_name else None


@router.get("/uptime")
async def public_uptime(response: Response):
    """Public uptime probe — used by external monitors (UptimeRobot etc.).

    Returns 200 + minimal JSON when DB ping succeeds. Returns 503 when:
      - MongoDB ping fails
      - The DB pool is unreachable

    This endpoint is intentionally fast (<50 ms) and does NOT touch user data.
    """
    started_at = time.time()
    db_ok = False
    db_error = None
    db_latency_ms = None

    if _db is not None:
        ping_start = time.time()
        try:
            await _db.command("ping")
            db_ok = True
            db_latency_ms = round((time.time() - ping_start) * 1000, 1)
        except Exception as exc:
            db_error = str(exc)[:120]

    healthy = db_ok
    if not healthy:
        response.status_code = 503

    return {
        "status": "ok" if healthy else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": round(time.time() - _PROCESS_START, 1),
        "checks": {
            "database": {
                "ok": db_ok,
                "latency_ms": db_latency_ms,
                "error": db_error,
            },
        },
        "response_time_ms": round((time.time() - started_at) * 1000, 1),
    }


@router.get("/deep")
async def deep_health(current_user: dict = Depends(get_current_user)):
    """Authenticated deep health — used by the admin dashboard.

    Adds: collection counts, last UI health run age, scheduler job count,
    last cron run timestamps, pending maintenance flag.
    """
    if current_user.get("role") not in ("super_admin", "admin", "manager"):
        return {"error": "Not authorized"}

    out = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": round(time.time() - _PROCESS_START, 1),
        "database": {"ok": False},
        "ui_health_last_run": None,
        "scheduler": {"jobs": None},
        "collections": {},
        "endpoint_cache": {},
    }

    # Endpoint cache stats — quick sanity check that 60s caching is working
    try:
        from utils.endpoint_cache import endpoint_cache
        out["endpoint_cache"] = endpoint_cache.stats()
    except Exception as exc:
        out["endpoint_cache"] = {"error": str(exc)[:120]}

    # DB ping
    try:
        await _db.command("ping")
        out["database"]["ok"] = True
    except Exception as exc:
        out["database"]["error"] = str(exc)[:120]

    # Collection counts (cheap)
    try:
        out["collections"] = {
            "tiles": await _db.tiles.count_documents({}),
            "shop_orders_paid": await _db.shop_orders.count_documents({"payment_status": "paid"}),
            "users": await _db.users.count_documents({}),
            "abandoned_carts_open": await _db.abandoned_carts.count_documents({"status": {"$ne": "recovered"}}),
        }
    except Exception as exc:
        out["collections"] = {"error": str(exc)[:120]}

    # Last UI Health run
    try:
        doc = await _db.website_settings.find_one({"_id": "ui_health_last_run"})
        if doc:
            ran_at = doc.get("ran_at")
            failed = doc.get("failed_count", 0)
            total = doc.get("total", 0)
            passed = doc.get("passed_count", total - failed if total else 0)
            out["ui_health_last_run"] = {
                "ran_at": ran_at,
                "passed": passed,
                "total": total,
                "all_green": failed == 0 and total > 0,
            }
    except Exception as exc:
        out["ui_health_last_run"] = {"error": str(exc)[:120]}

    # Scheduler — APScheduler exposes job count if available
    try:
        from services import scheduler as sched
        if hasattr(sched, "scheduler") and sched.scheduler:
            jobs = sched.scheduler.get_jobs()
            out["scheduler"]["jobs"] = len(jobs)
            out["scheduler"]["next_runs"] = sorted([
                {"id": j.id, "next_run": j.next_run_time.isoformat() if j.next_run_time else None}
                for j in jobs
            ], key=lambda x: x["next_run"] or "")[:5]
    except Exception as exc:
        out["scheduler"] = {"error": str(exc)[:120]}

    return out

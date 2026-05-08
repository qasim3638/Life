"""
Admin endpoints for the health monitor:

  GET    /api/admin/health/status            → live snapshot
  GET    /api/admin/health/active            → unacknowledged active alerts (used by banner)
  POST   /api/admin/health/active/{id}/ack   → acknowledge a specific alert
  POST   /api/admin/health/active/ack-all    → acknowledge everything
  GET    /api/admin/health/history           → last N checks (for the timeline graph)
  GET    /api/admin/health/incidents         → past 30 days of incidents
  GET    /api/admin/health/settings          → notification config
  PUT    /api/admin/health/settings          → update notification config
  POST   /api/admin/health/test-alert        → fire a TEST alert through every channel
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from config import get_db
from services import get_current_user

router = APIRouter(prefix="/admin/health", tags=["Health Monitor"])


def _require_admin(user: dict):
    if (user or {}).get("role") not in ("super_admin", "admin", "manager"):
        raise HTTPException(status_code=403, detail="Admin access required")


def _strip(doc):
    if not doc:
        return doc
    doc.pop("_id", None)
    for k, v in list(doc.items()):
        if isinstance(v, datetime):
            doc[k] = v.isoformat()
    return doc


@router.get("/status")
async def status(current_user: dict = Depends(get_current_user)):
    """Per-endpoint health snapshot, computed from the last check."""
    _require_admin(current_user)
    db = get_db()
    state_docs = await db.health_endpoint_state.find({}, {"_id": 0}).to_list(length=None)
    last_checks = {}
    # Pick the most recent check per label (one Mongo round-trip per label is OK
    # since there are <20 labels)
    from services.health_monitor import MONITORED_ENDPOINTS
    for ep in MONITORED_ENDPOINTS:
        last = await db.health_checks.find_one(
            {"label": ep["label"]}, {"_id": 0}, sort=[("checked_at", -1)]
        )
        last_checks[ep["label"]] = _strip(last) if last else None

    summary = {
        "monitored": len(MONITORED_ENDPOINTS),
        "healthy": sum(1 for c in last_checks.values() if c and c.get("healthy")),
        "unhealthy": sum(1 for c in last_checks.values() if c and not c.get("healthy")),
        "unknown": sum(1 for c in last_checks.values() if not c),
    }
    active = await db.health_alerts.count_documents({"resolved": False, "acknowledged": False})
    return {
        "summary": summary,
        "active_unack_alerts": active,
        "endpoints": [
            {
                "label": ep["label"],
                "path": ep["path"],
                "last_check": last_checks.get(ep["label"]),
                "state": next(
                    (_strip(s) for s in state_docs if s.get("label") == ep["label"]),
                    None,
                ),
            }
            for ep in MONITORED_ENDPOINTS
        ],
    }


@router.get("/active")
async def active_alerts(current_user: dict = Depends(get_current_user)):
    """Live alerts that haven't been resolved AND haven't been acknowledged.
    The admin nav banner polls this — when the array is non-empty, the
    big red banner shows.

    If the admin snoozed all alerts via `/snooze`, we return an empty
    list until the snooze window expires. The suppression state is
    included so the UI can render a "Muted until X" strip instead of
    the red banner.
    """
    _require_admin(current_user)
    db = get_db()
    now = datetime.now(timezone.utc)
    supp = await db.health_alerts_suppression.find_one(
        {"id": "global"}, {"_id": 0}
    )
    suppressed_until = None
    if supp and supp.get("suppressed_until"):
        ts = supp["suppressed_until"]
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except Exception:
                ts = None
        # Mongo stores naive UTC — force tz-aware before comparing
        if isinstance(ts, datetime) and ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts and ts > now:
            suppressed_until = ts.isoformat()
    if suppressed_until:
        return {
            "alerts": [],
            "count": 0,
            "suppressed_until": suppressed_until,
            "suppressed_by": supp.get("suppressed_by"),
            "suppression_reason": supp.get("reason"),
        }
    rows = await db.health_alerts.find(
        {"resolved": False, "acknowledged": False},
        {"_id": 0},
    ).sort("first_failure_at", -1).limit(10).to_list(length=None)
    return {"alerts": [_strip(r) for r in rows], "count": len(rows)}


class SnoozePayload(BaseModel):
    hours: Optional[int] = 24
    reason: Optional[str] = None


@router.post("/active/snooze")
async def snooze_all(
    payload: SnoozePayload,
    current_user: dict = Depends(get_current_user),
):
    """Mute the outage banner for the next N hours. Also acknowledges
    every active incident so the admin history stays clean. Useful when
    admin knows the underlying issue (e.g. monitor misconfig) and wants
    the alarm off while they fix it."""
    _require_admin(current_user)
    hours = max(1, min(int(payload.hours or 24), 168))  # cap at 7 days
    db = get_db()
    now = datetime.now(timezone.utc)
    until = now + timedelta(hours=hours)
    # Also ack current incidents so they don't resurrect after the
    # suppression window expires.
    await db.health_alerts.update_many(
        {"resolved": False, "acknowledged": False},
        {"$set": {
            "acknowledged": True,
            "acknowledged_at": now,
            "acknowledged_by": (current_user or {}).get("email"),
            "snoozed": True,
        }},
    )
    await db.health_alerts_suppression.update_one(
        {"id": "global"},
        {"$set": {
            "id": "global",
            "suppressed_until": until,
            "suppressed_by": (current_user or {}).get("email"),
            "suppressed_at": now,
            "reason": payload.reason or "",
            "hours": hours,
        }},
        upsert=True,
    )
    return {"ok": True, "suppressed_until": until.isoformat(), "hours": hours}


@router.post("/active/resume")
async def resume_alerts(current_user: dict = Depends(get_current_user)):
    """End the snooze window early and restore the outage banner."""
    _require_admin(current_user)
    db = get_db()
    await db.health_alerts_suppression.delete_one({"id": "global"})
    return {"ok": True}


@router.post("/active/{incident_id}/ack")
async def ack(incident_id: str, current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    db = get_db()
    res = await db.health_alerts.update_one(
        {"id": incident_id},
        {"$set": {
            "acknowledged": True,
            "acknowledged_at": datetime.now(timezone.utc),
            "acknowledged_by": (current_user or {}).get("email"),
        }},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {"ok": True}


@router.post("/active/ack-all")
async def ack_all(current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    db = get_db()
    res = await db.health_alerts.update_many(
        {"resolved": False, "acknowledged": False},
        {"$set": {
            "acknowledged": True,
            "acknowledged_at": datetime.now(timezone.utc),
            "acknowledged_by": (current_user or {}).get("email"),
        }},
    )
    return {"ok": True, "acknowledged": res.modified_count}


@router.post("/active/cleanup-zombies")
async def cleanup_zombies(current_user: dict = Depends(get_current_user)):
    """Resolve duplicate/zombie outage incidents.

    Context: a timezone-naive datetime crash in `_should_dispatch`
    (fixed Feb 2026) caused the monitor to lose `active_incident_id`
    state on every cycle, opening a fresh duplicate incident every
    60s. The result is dozens of unresolved-but-identical "outage"
    rows for the same endpoint.

    This endpoint cleans them up:
      1. For each endpoint label, keep only the MOST RECENT unresolved
         incident — mark all older duplicates as resolved.
      2. Auto-resolve any unresolved incident whose endpoint is
         currently healthy (has a successful check in the last 90s).

    Safe to run repeatedly. Returns counts of what was cleaned.
    """
    _require_admin(current_user)
    db = get_db()
    now = datetime.now(timezone.utc)

    # Step 1: dedupe — keep newest unresolved per label, resolve older.
    pipeline = [
        {"$match": {"resolved": False}},
        {"$sort": {"first_failure_at": -1}},
        {"$group": {
            "_id": "$label",
            "keep_id": {"$first": "$id"},
            "all_ids": {"$push": "$id"},
        }},
    ]
    groups = await db.health_alerts.aggregate(pipeline).to_list(length=None)
    duplicate_ids: list[str] = []
    for g in groups:
        keep = g.get("keep_id")
        for inc_id in g.get("all_ids", []):
            if inc_id and inc_id != keep:
                duplicate_ids.append(inc_id)
    duplicates_resolved = 0
    if duplicate_ids:
        res = await db.health_alerts.update_many(
            {"id": {"$in": duplicate_ids}, "resolved": False},
            {"$set": {
                "resolved": True,
                "resolved_at": now,
                "acknowledged": True,
                "acknowledged_at": now,
                "acknowledged_by": "system:cleanup-zombies",
            }},
        )
        duplicates_resolved = res.modified_count

    # Step 2: auto-resolve unresolved incidents whose endpoint is
    # currently healthy (last successful check within 90s).
    cutoff = now - timedelta(seconds=90)
    healthy_labels: set[str] = set()
    async for row in db.health_checks.find(
        {"healthy": True, "checked_at": {"$gte": cutoff}},
        {"_id": 0, "label": 1},
    ):
        if row.get("label"):
            healthy_labels.add(row["label"])
    healthy_resolved = 0
    if healthy_labels:
        res = await db.health_alerts.update_many(
            {"resolved": False, "label": {"$in": list(healthy_labels)}},
            {"$set": {
                "resolved": True,
                "resolved_at": now,
                "acknowledged": True,
                "acknowledged_at": now,
                "acknowledged_by": "system:cleanup-zombies",
            }},
        )
        healthy_resolved = res.modified_count

    # Step 3: clear stale active_incident_id on endpoint state docs
    # whose target incident is now resolved (so future failures open
    # fresh incidents cleanly).
    state_cleared = 0
    state_docs = await db.health_endpoint_state.find(
        {"active_incident_id": {"$ne": None}}, {"_id": 0}
    ).to_list(length=None)
    for s in state_docs:
        inc_id = s.get("active_incident_id")
        if not inc_id:
            continue
        inc = await db.health_alerts.find_one({"id": inc_id}, {"_id": 0, "resolved": 1})
        if inc and inc.get("resolved"):
            await db.health_endpoint_state.update_one(
                {"label": s["label"]},
                {"$set": {"active_incident_id": None, "consecutive_failures": 0}},
            )
            state_cleared += 1

    return {
        "ok": True,
        "duplicates_resolved": duplicates_resolved,
        "healthy_endpoints_resolved": healthy_resolved,
        "stale_state_cleared": state_cleared,
        "total_resolved": duplicates_resolved + healthy_resolved,
    }


@router.get("/history")
async def history(limit: int = 200, current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    limit = max(10, min(limit, 1000))
    db = get_db()
    rows = await db.health_checks.find({}, {"_id": 0}).sort("checked_at", -1).limit(limit).to_list(length=None)
    return {"checks": [_strip(r) for r in rows], "count": len(rows)}


@router.get("/incidents")
async def incidents(days: int = 30, current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    db = get_db()
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, min(days, 365)))
    rows = await db.health_alerts.find(
        {"first_failure_at": {"$gte": cutoff}},
        {"_id": 0},
    ).sort("first_failure_at", -1).limit(500).to_list(length=None)
    return {"incidents": [_strip(r) for r in rows], "count": len(rows)}


# ---------- Settings ----------

class HealthSettings(BaseModel):
    email_recipients: Optional[list[str]] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    alert_sender_name: Optional[str] = None
    alert_sender_email: Optional[str] = None


@router.get("/settings")
async def get_settings_route(current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    from services.alert_dispatcher import get_settings
    cfg = await get_settings()
    # Don't echo the bot token in plaintext — mask it in the UI
    if cfg.get("telegram_bot_token"):
        token = cfg["telegram_bot_token"]
        cfg["telegram_bot_token_masked"] = f"…{token[-6:]}" if len(token) > 8 else "set"
        cfg["telegram_bot_token"] = ""  # never send back the full token
    return cfg


@router.put("/settings")
async def put_settings_route(
    payload: HealthSettings,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    from services.alert_dispatcher import get_settings, update_settings
    existing = await get_settings()
    incoming = {k: v for k, v in payload.dict().items() if v is not None}
    # Don't blow away the saved token if the form submitted blank
    if "telegram_bot_token" in incoming and not incoming["telegram_bot_token"]:
        incoming.pop("telegram_bot_token")
    new_cfg = {**existing, **incoming}
    await update_settings(new_cfg, updated_by=(current_user or {}).get("email"))
    return await get_settings_route(current_user)


@router.post("/test-alert")
async def test_alert(
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    from services.alert_dispatcher import dispatch_test_alert
    return await dispatch_test_alert()

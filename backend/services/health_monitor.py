"""
Health monitor — pings every customer-facing endpoint every 60 seconds
and raises an URGENT, IMPOSSIBLE-TO-IGNORE alert if any one fails for
more than two consecutive checks (~2 minutes of badness).

Three alert layers stacked together so a single missed notification
can't take the storefront down silently:

    1. Email via Resend, with a deliberately-different sender name
       and 🚨🚨🚨 subject line — visually distinct from normal mail.
    2. Telegram bot — distinctive ringtone, no spam filtering, hits
       the admin's phone instantly.
    3. Admin nav banner — every admin page shows a red, full-width
       "PRODUCTION OUTAGE" banner until the admin clicks
       "Acknowledge & investigate".

Re-alerts every 5 minutes if the outage continues AND the admin has
not acknowledged. So if you miss the first email/telegram, you get
another one 5 min later, and another 5 min after that, until you
either fix it or click acknowledge.

Health state is persisted in three Mongo collections:

    health_checks          → one doc per check, last 7 days only (TTL)
    health_alerts          → one doc per outage incident (active +
                             acknowledged), permanent
    health_settings        → singleton: notification recipients, urls
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from config import get_db

logger = logging.getLogger(__name__)


# Endpoints we monitor — same list as the regression tests, kept in
# sync because the policy is "if it goes on the website, it must
# never disappear silently".
MONITORED_ENDPOINTS = [
    {"label": "Tile Products",      "path": "/api/tiles/products?limit=3",
     "expect_key": "products"},
    {"label": "Tile Collections",   "path": "/api/tiles/collections?group=tiles&page=1&limit=3",
     "expect_key": "collections"},
    {"label": "Featured Tiles",     "path": "/api/tiles/featured?limit=3",
     "expect_key": None},  # returns either list or {items:[]}
    {"label": "Tile Filters",       "path": "/api/tiles/filters",
     "expect_key": "suppliers"},
    {"label": "Tile Categories",    "path": "/api/tiles/categories",
     "expect_key": None},
    {"label": "Tile Search",        "path": "/api/tiles/search?q=onyx",
     "expect_key": None},
    {"label": "Promo Banner",       "path": "/api/website/promo-banner",
     "expect_key": "enabled"},
    {"label": "Backend Health",     "path": "/api/health",
     "expect_key": "status"},
]

CHECK_INTERVAL_SECONDS = 60
FAILURE_THRESHOLD = 2  # consecutive failures before raising an alert
RE_ALERT_INTERVAL_SECONDS = 300  # 5 min between re-alerts on the same incident
MAX_CHECKS_RETAINED = 10_000  # safety net so the collection never grows forever


def _self_base_url() -> str:
    """Where to ping ourselves from inside the pod.

    Default: `http://localhost:8001` — same pod, guaranteed-fast, never
    subject to DNS/CDN/WAF issues. This is the RIGHT default for
    "is uvicorn alive and returning good data?" — which is what the
    monitor is actually designed to answer.

    Opt-in: set `MONITOR_BASE_URL` to the public storefront URL if you
    want to catch CDN/Cloudflare/Railway-edge issues as well. Caveats:
    many CDN providers (Cloudflare included) rate-limit or JS-challenge
    requests from Railway egress IPs, producing chronic false-positive
    timeouts. Keep `MONITOR_BASE_URL` pointing at an origin URL (e.g.
    `https://api.yourdomain.com`) that resolves directly to the
    backend, NOT the frontend domain with an SPA fallback.

    Previously this fell back to `REACT_APP_BACKEND_URL` which, on
    production, is the public frontend domain — the monitor ended up
    pinging through Cloudflare → Express SPA → SPA HTML fallback →
    confused JSON parser → every endpoint "failed". That was a bad
    default; it's fixed.
    """
    return os.environ.get("MONITOR_BASE_URL", "http://localhost:8001").rstrip("/")


async def _check_one(client: httpx.AsyncClient, ep: dict) -> dict:
    """Hit a single endpoint and classify the result."""
    started = time.time()
    base = _self_base_url()
    url = f"{base}{ep['path']}"
    failure_reason: Optional[str] = None
    status_code = 0
    healthy = False
    body_preview = ""
    try:
        r = await client.get(url, timeout=12.0)
        status_code = r.status_code
        if r.status_code != 200:
            failure_reason = f"HTTP {r.status_code}"
        else:
            body_text = (r.text or "")[:400].lower()
            # If the response is HTML (e.g. the React SPA shell), that
            # means MONITOR_BASE_URL is pointing at the frontend domain
            # instead of the backend. Distinct error so admin knows
            # it's a config problem, not a real outage.
            if "<!doctype html" in body_text or "<html" in body_text:
                failure_reason = (
                    "backend returned SPA HTML — MONITOR_BASE_URL likely "
                    "points at frontend domain (set it to the backend URL)"
                )
                data = None
            else:
                try:
                    data = r.json()
                except Exception:
                    failure_reason = "non-JSON response"
                    data = None
            if data is not None:
                if ep["expect_key"]:
                    if ep["expect_key"] not in (data or {}):
                        failure_reason = f"missing key '{ep['expect_key']}' in response"
                # Empty list / dict counts as failure too — that's the EXACT
                # symptom of today's outage.
                if isinstance(data, dict) and ep["expect_key"]:
                    val = data.get(ep["expect_key"])
                    if isinstance(val, list) and len(val) == 0 and ep["expect_key"] in ("products", "collections"):
                        failure_reason = f"empty {ep['expect_key']}"
                healthy = failure_reason is None
                body_preview = str(data)[:140]
    except httpx.TimeoutException:
        failure_reason = "timeout (>12s)"
    except Exception as exc:
        failure_reason = f"{type(exc).__name__}: {str(exc)[:100]}"
    elapsed_ms = int((time.time() - started) * 1000)
    return {
        "label": ep["label"],
        "path": ep["path"],
        "status_code": status_code,
        "elapsed_ms": elapsed_ms,
        "healthy": healthy,
        "failure_reason": failure_reason,
        "body_preview": body_preview,
        "checked_at": datetime.now(timezone.utc),
    }


async def _persist_check(check: dict) -> None:
    db = get_db()
    await db.health_checks.insert_one(dict(check))
    # Periodic prune so the collection cannot grow unbounded
    if int(time.time()) % 60 == 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        await db.health_checks.delete_many({"checked_at": {"$lt": cutoff}})


async def _get_state(label: str) -> dict:
    """Per-endpoint state: consecutive failures + active incident id."""
    db = get_db()
    doc = await db.health_endpoint_state.find_one({"label": label}, {"_id": 0}) or {
        "label": label,
        "consecutive_failures": 0,
        "active_incident_id": None,
        "last_alerted_at": None,
        "last_seen_healthy_at": None,
    }
    return doc


async def _save_state(state: dict) -> None:
    db = get_db()
    await db.health_endpoint_state.update_one(
        {"label": state["label"]}, {"$set": state}, upsert=True
    )


async def _open_or_continue_incident(state: dict, check: dict) -> str:
    """Open a new incident OR re-use the existing active one.

    Idempotency: even if the in-memory state lost `active_incident_id`
    (e.g. because a prior round crashed before `_save_state`), look up
    Mongo for any unresolved incident on this label and reuse it.
    Without this, transient state-save failures generate duplicate
    "outage" rows on every monitor tick.
    """
    db = get_db()
    if state.get("active_incident_id"):
        return state["active_incident_id"]

    # Recover lost state: any unresolved incident on this label is the
    # one we should continue tracking.
    existing = await db.health_alerts.find_one(
        {"label": check["label"], "resolved": False},
        sort=[("first_failure_at", -1)],
    )
    if existing and existing.get("id"):
        state["active_incident_id"] = existing["id"]
        return existing["id"]

    # Genuinely new incident
    import uuid
    incident_id = uuid.uuid4().hex[:14]
    now = datetime.now(timezone.utc)
    doc = {
        "id": incident_id,
        "label": check["label"],
        "path": check["path"],
        "first_failure_at": now,
        "last_failure_at": now,
        "first_failure_reason": check["failure_reason"],
        "alert_count": 0,
        "acknowledged": False,
        "acknowledged_at": None,
        "acknowledged_by": None,
        "resolved": False,
        "resolved_at": None,
    }
    await db.health_alerts.insert_one(doc)
    state["active_incident_id"] = incident_id
    return incident_id


async def _resolve_incident(state: dict) -> Optional[str]:
    """Mark the active incident resolved. Returns the incident id we
    just resolved (so the caller can dispatch a 'recovered' message)."""
    incident_id = state.get("active_incident_id")
    if not incident_id:
        return None
    db = get_db()
    await db.health_alerts.update_one(
        {"id": incident_id, "resolved": False},
        {"$set": {"resolved": True, "resolved_at": datetime.now(timezone.utc)}},
    )
    state["active_incident_id"] = None
    return incident_id


async def _should_dispatch(state: dict) -> bool:
    """Re-alert only every RE_ALERT_INTERVAL_SECONDS so we don't spam.

    Important: Mongo returns naive datetimes by default. Coerce to UTC
    before subtraction so we don't crash with a TypeError. (Older
    rows in `health_endpoint_state` were written in March/April with
    no tzinfo — those still need to roundtrip cleanly.)
    """
    last = state.get("last_alerted_at")
    if last is None:
        return True
    if isinstance(last, str):
        try:
            last = datetime.fromisoformat(last.replace("Z", "+00:00"))
        except Exception:
            return True
    # Coerce naive datetimes (legacy Mongo rows) to UTC.
    if isinstance(last, datetime) and last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    try:
        delta = datetime.now(timezone.utc) - last
    except TypeError:
        # Defensive: belt-and-braces for any future weirdness.
        return True
    return delta.total_seconds() >= RE_ALERT_INTERVAL_SECONDS


async def _run_one_round() -> None:
    """One pass over every monitored endpoint."""
    from services.alert_dispatcher import dispatch_outage_alert, dispatch_recovery_alert

    async with httpx.AsyncClient(headers={"User-Agent": "TileStation-HealthMonitor/1.0"}) as client:
        results = await asyncio.gather(*[_check_one(client, ep) for ep in MONITORED_ENDPOINTS])

    for check in results:
        await _persist_check(check)
        state = await _get_state(check["label"])

        if check["healthy"]:
            state["consecutive_failures"] = 0
            state["last_seen_healthy_at"] = datetime.now(timezone.utc)
            recovered = await _resolve_incident(state)
            await _save_state(state)
            if recovered:
                # Send a "recovered" follow-up so the admin knows it's
                # safe to stand down.
                try:
                    await dispatch_recovery_alert(check, recovered)
                except Exception:
                    logger.exception(f"recovery alert failed for {check['label']}")
            continue

        # Unhealthy — always persist state at the end, even if dispatch
        # or any inner step crashes. Without try/finally, a transient
        # error would lose `active_incident_id` and the next monitor
        # tick would open a duplicate incident → exactly the bug we
        # saw on prod with 10 zombie "Tile Products" alerts.
        try:
            state["consecutive_failures"] = int(state.get("consecutive_failures", 0)) + 1
            if state["consecutive_failures"] >= FAILURE_THRESHOLD:
                incident_id = await _open_or_continue_incident(state, check)
                db = get_db()
                await db.health_alerts.update_one(
                    {"id": incident_id},
                    {"$set": {
                        "last_failure_at": datetime.now(timezone.utc),
                        "last_failure_reason": check["failure_reason"],
                    }},
                )
                if await _should_dispatch(state):
                    try:
                        await dispatch_outage_alert(check, incident_id, state)
                        state["last_alerted_at"] = datetime.now(timezone.utc)
                        await db.health_alerts.update_one(
                            {"id": incident_id}, {"$inc": {"alert_count": 1}}
                        )
                    except Exception:
                        logger.exception(f"alert dispatch failed for {check['label']}")
        finally:
            await _save_state(state)


_BACKGROUND_TASK: Optional[asyncio.Task] = None


async def _monitor_loop():
    logger.info("Health monitor started — checking every %ds", CHECK_INTERVAL_SECONDS)
    while True:
        try:
            await _run_one_round()
        except Exception:
            logger.exception("Health monitor round crashed — continuing")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


def start_health_monitor() -> None:
    """Called once at FastAPI startup to kick off the background loop."""
    global _BACKGROUND_TASK
    if _BACKGROUND_TASK is not None and not _BACKGROUND_TASK.done():
        return
    if os.environ.get("DISABLE_HEALTH_MONITOR", "").lower() in ("1", "true", "yes"):
        logger.info("Health monitor disabled via DISABLE_HEALTH_MONITOR env")
        return
    try:
        loop = asyncio.get_event_loop()
        _BACKGROUND_TASK = loop.create_task(_monitor_loop())
    except RuntimeError:
        # No running loop (e.g. test imports) — defer to FastAPI startup.
        pass


def stop_health_monitor() -> None:
    global _BACKGROUND_TASK
    if _BACKGROUND_TASK is not None:
        _BACKGROUND_TASK.cancel()
        _BACKGROUND_TASK = None

"""
SEO Health Status Board — /api/admin/seo-health/status

One endpoint that surfaces traffic-light status for the four "manual /
external" pieces of the SEO + payments stack so the admin can see at a
glance whether they're 100% locked in:

  1. Stripe webhook        — must point at the live Railway backend
  2. Resend custom domain  — must be verified for tilestation.co.uk
  3. Google Business Profile (API allowlist)
  4. Google Ads developer token (Keyword Planner CPCs)

Plus:
  • Count of active SEO Autopilot APScheduler jobs (sanity)
  • Last seo_autopilot_actions activity timestamp

All checks are best-effort and degrade gracefully — a missing API key
returns "not_configured", never raises 500. The whole call is capped to
a few seconds with timeouts so a slow Resend/Stripe API doesn't hang the
admin page.
"""
from __future__ import annotations

import os
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from config import get_db
from services import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/seo-health", tags=["SEO Health Status"])


def _is_admin(user: dict) -> bool:
    return (user or {}).get("role") in {"super_admin", "admin", "manager"}


def _stamp(status: str, **kwargs) -> dict:
    """Convenience: build a uniform check result dict."""
    out = {"status": status, **kwargs}
    return out


async def _check_stripe_webhook() -> dict:
    """List Stripe webhook endpoints; report whether any are configured
    and pointing at the real production webhook URL.

    The storefront registers its webhook at `/api/webhook/stripe`
    (singular — see `shop.py`), so that's what we must look for here.
    The old check used `/api/webhooks/stripe` (plural) which was wrong
    and produced a permanent red lock-in even on correctly-configured
    production deployments.
    """
    api_key = os.environ.get("STRIPE_SECRET_KEY") or os.environ.get("STRIPE_API_KEY")
    if not api_key:
        return _stamp("not_configured", message="STRIPE_SECRET_KEY not set on backend")
    try:
        async with httpx.AsyncClient(timeout=8.0) as cli:
            r = await cli.get(
                "https://api.stripe.com/v1/webhook_endpoints",
                auth=(api_key, ""),
                params={"limit": 10},
            )
        if r.status_code != 200:
            return _stamp("error", message=f"Stripe API returned {r.status_code}")
        endpoints = (r.json().get("data") or [])
        if not endpoints:
            return _stamp(
                "red",
                message="No webhook endpoints exist in Stripe",
                endpoints=[],
            )
        # Categorise endpoints
        live_prod, preview, disabled = [], [], []
        for ep in endpoints:
            url = ep.get("url", "") or ""
            enabled = (ep.get("status") == "enabled")
            entry = {
                "id": ep.get("id"),
                "url": url,
                "enabled": enabled,
                "events": (ep.get("enabled_events") or [])[:6],
            }
            if not enabled:
                disabled.append(entry)
            elif "preview.emergent" in url or "localhost" in url:
                preview.append(entry)
            elif "/api/webhook/stripe" in url or "/api/webhooks/stripe" in url:
                # Accept both singular (actual backend route) and
                # plural (historic expected) so this check is robust
                # to a future route rename.
                live_prod.append(entry)
            else:
                preview.append(entry)
        if live_prod:
            required = {"payment_intent.succeeded", "payment_intent.payment_failed",
                        "charge.refunded", "checkout.session.completed"}
            covered = required.issubset(set().union(
                *(set(ep.get("enabled_events") or []) for ep in endpoints if ep.get("status") == "enabled")
            ))
            return _stamp(
                "green" if covered else "amber",
                message=("Live webhook configured" if covered
                         else "Live webhook configured but missing some required events"),
                endpoints=live_prod + preview + disabled,
            )
        return _stamp(
            "red",
            message="Webhook(s) exist but none point at the production /api/webhook/stripe URL",
            endpoints=preview + disabled,
        )
    except httpx.TimeoutException:
        return _stamp("error", message="Stripe API timeout")
    except Exception as exc:
        return _stamp("error", message=f"Stripe check failed: {str(exc)[:120]}")


async def _check_resend_domain() -> dict:
    """List Resend domains; check whether tilestation.co.uk is verified."""
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        return _stamp("not_configured", message="RESEND_API_KEY not set")
    try:
        async with httpx.AsyncClient(timeout=8.0) as cli:
            r = await cli.get(
                "https://api.resend.com/domains",
                headers={"Authorization": f"Bearer {api_key}"},
            )
        if r.status_code != 200:
            return _stamp("error", message=f"Resend API returned {r.status_code}")
        body = r.json() or {}
        domains = body.get("data") or body.get("domains") or []
        target = "tilestation.co.uk"
        target_doc = next((d for d in domains if (d.get("name") or "").lower() == target), None)
        if not target_doc:
            return _stamp(
                "red",
                message=f"{target} not added to Resend yet",
                domains=[d.get("name") for d in domains],
            )
        verif = (target_doc.get("status") or "").lower()
        if verif == "verified":
            return _stamp(
                "green",
                message=f"{target} verified · sending from {os.environ.get('SENDER_EMAIL', 'default')}",
                domain=target_doc.get("name"),
                region=target_doc.get("region"),
            )
        return _stamp(
            "amber",
            message=f"{target} pending verification (status: {verif or 'unknown'})",
            domain=target_doc.get("name"),
        )
    except httpx.TimeoutException:
        return _stamp("error", message="Resend API timeout")
    except Exception as exc:
        return _stamp("error", message=f"Resend check failed: {str(exc)[:120]}")


async def _check_gbp() -> dict:
    """Check whether any admin has an active GBP OAuth token + Google
    has approved API access (we treat a connected token as 'approved')."""
    db = get_db()
    try:
        token_doc = await db.gbp_oauth_tokens.find_one({}, {"_id": 0})
        if token_doc:
            return _stamp(
                "green",
                message="GBP API connected · reviews + insights live",
                connected_admin=token_doc.get("admin_email"),
            )
        return _stamp(
            "amber",
            message="GBP backend ready · waiting for Google API allowlist + admin Connect",
            apply_url="https://support.google.com/business/contact/api_default",
        )
    except Exception as exc:
        return _stamp("error", message=f"GBP check failed: {str(exc)[:120]}")


async def _check_ads_api() -> dict:
    """Check whether Google Ads developer token has been pasted in."""
    dev_token = (os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN") or "").strip()
    if dev_token:
        return _stamp(
            "green",
            message="Google Ads dev token configured · Keyword Planner CPCs live",
        )
    return _stamp(
        "amber",
        message="Heuristic CPC model active · apply for dev token to upgrade",
        apply_url="https://ads.google.com/aw/signup/landing",
    )


async def _check_autopilot_jobs() -> dict:
    """Sanity: count APScheduler SEO Autopilot jobs."""
    try:
        from services import scheduler as sched_mod  # type: ignore
        if not (hasattr(sched_mod, "scheduler") and sched_mod.scheduler):
            return _stamp("amber", message="Scheduler not yet initialised", count=0)
        jobs = sched_mod.scheduler.get_jobs()
        ap_jobs = [j for j in jobs if j.id.startswith("seo_autopilot_")]
        next_runs = sorted(
            [{"id": j.id, "next_run": j.next_run_time.isoformat() if j.next_run_time else None}
             for j in ap_jobs],
            key=lambda x: x["next_run"] or "",
        )
        return _stamp(
            "green" if len(ap_jobs) >= 8 else "amber",
            message=f"{len(ap_jobs)} of 9 autopilot jobs scheduled",
            count=len(ap_jobs),
            next_runs=next_runs[:5],
        )
    except Exception as exc:
        return _stamp("error", message=f"Autopilot check failed: {str(exc)[:120]}")


async def _check_last_autopilot_action() -> dict:
    db = get_db()
    try:
        latest = await db.seo_autopilot_actions.find_one(
            {}, {"_id": 0, "action_type": 1, "created_at": 1, "summary": 1},
            sort=[("created_at", -1)],
        )
        if not latest:
            return _stamp(
                "amber",
                message="No autopilot actions logged yet — first cron tick at 04:00 BST",
            )
        ts = latest.get("created_at")
        return _stamp(
            "green",
            message=f"Last autopilot action: {latest.get('action_type', 'unknown')}",
            last_action=latest,
            last_action_at=ts,
        )
    except Exception as exc:
        return _stamp("error", message=f"Action check failed: {str(exc)[:120]}")


@router.get("/status")
async def seo_health_status(current_user: dict = Depends(get_current_user)):
    """The full status board — runs all 6 checks in parallel."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")

    stripe_check, resend_check, gbp_check, ads_check, jobs_check, last_action = await asyncio.gather(
        _check_stripe_webhook(),
        _check_resend_domain(),
        _check_gbp(),
        _check_ads_api(),
        _check_autopilot_jobs(),
        _check_last_autopilot_action(),
    )

    checks = {
        "stripe_webhook": stripe_check,
        "resend_domain": resend_check,
        "gbp_api": gbp_check,
        "ads_api": ads_check,
        "autopilot_jobs": jobs_check,
        "autopilot_last_action": last_action,
    }

    # Apply admin dismissals. A dismissed item gets status=acknowledged
    # (hidden from the red/amber action list) UNLESS the live check has
    # since gone green on its own — in which case we auto-clear the
    # override so the user isn't stuck with stale dismissals.
    db = get_db()
    now = datetime.now(timezone.utc)
    try:
        overrides = await db.seo_health_overrides.find({}, {"_id": 0}).to_list(length=None)
    except Exception:  # noqa: BLE001
        overrides = []
    for ov in overrides:
        key = ov.get("key")
        if key not in checks:
            continue
        expires = ov.get("expires_at")
        if isinstance(expires, str):
            try:
                expires = datetime.fromisoformat(expires.replace("Z", "+00:00"))
            except Exception:
                expires = None
        # Mongo stores naive UTC — force tz-aware before comparing
        if isinstance(expires, datetime) and expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires and expires < now:
            # Override expired — drop it silently
            try:
                await db.seo_health_overrides.delete_one({"key": key})
            except Exception:
                pass
            continue
        live = checks[key]
        if live.get("status") == "green":
            # Auto-clear — live check is now green, no need for the override
            try:
                await db.seo_health_overrides.delete_one({"key": key})
            except Exception:
                pass
            continue
        # Apply override — preserves live message in `live_message` for
        # full transparency.
        checks[key] = {
            **live,
            "status": "acknowledged",
            "overridden": True,
            "override_reason": ov.get("reason") or "",
            "override_by": ov.get("dismissed_by"),
            "override_expires_at": (expires.isoformat() if expires else None),
            "live_status": live.get("status"),
            "live_message": live.get("message"),
        }

    # Roll-up: how many of the 4 "lock-in" items are green or acknowledged?
    locked = sum(1 for k in ("stripe_webhook", "resend_domain", "gbp_api", "ads_api")
                 if checks[k]["status"] in ("green", "acknowledged"))
    total_locked = 4

    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "locked_count": locked,
            "locked_total": total_locked,
            "percent": round((locked / total_locked) * 100),
            "all_green": locked == total_locked,
        },
        "checks": checks,
    }


class DismissPayload(BaseModel):
    reason: Optional[str] = None
    days: Optional[int] = 30


@router.post("/{key}/dismiss")
async def dismiss_item(
    key: str,
    payload: DismissPayload,
    current_user: dict = Depends(get_current_user),
):
    """Mark a lock-in item as acknowledged by the admin so it stops
    showing as red/amber. Auto-expires after N days (default 30) so
    the admin gets reminded to re-check. Auto-clears earlier if the
    live check goes green on its own."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    if key not in ("stripe_webhook", "resend_domain", "gbp_api", "ads_api"):
        raise HTTPException(status_code=400, detail="Unknown lock-in key")
    days = max(1, min(int(payload.days or 30), 180))
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=days)
    db = get_db()
    await db.seo_health_overrides.update_one(
        {"key": key},
        {"$set": {
            "key": key,
            "reason": payload.reason or "",
            "dismissed_by": (current_user or {}).get("email"),
            "dismissed_at": now,
            "expires_at": expires,
            "days": days,
        }},
        upsert=True,
    )
    return {"ok": True, "expires_at": expires.isoformat(), "days": days}


@router.post("/{key}/undismiss")
async def undismiss_item(
    key: str,
    current_user: dict = Depends(get_current_user),
):
    """Restore the live check for a lock-in item — the banner starts
    showing its real red/amber status again."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    db = get_db()
    await db.seo_health_overrides.delete_one({"key": key})
    return {"ok": True}


@router.post("/sync-stripe-payment-methods")
async def manual_stripe_pm_sync(current_user: dict = Depends(get_current_user)):
    """Force-run the Stripe payment-method auto-sync without rebooting
    the backend. Useful after toggling a method on/off in the Stripe
    Dashboard so it propagates to our admin DB immediately."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    db = get_db()
    try:
        from services.stripe_pm_sync import sync_stripe_payment_methods_to_db
        result = await sync_stripe_payment_methods_to_db(db)
        return result
    except Exception as exc:
        return {"ran": False, "error": str(exc)[:200]}

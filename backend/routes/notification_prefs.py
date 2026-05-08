"""
Super-Admin-only endpoints for managing per-admin notification
authorisations.

Read endpoints are open to admins (they can SEE who's subscribed) but
WRITE endpoints are super-admin-only — the audit-trail rule.
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException

from services import get_current_user
from services import notification_prefs as np

router = APIRouter(prefix="/admin/notification-prefs", tags=["Notification Prefs"])


def _is_super_admin(user: dict) -> bool:
    return (user or {}).get("role") == "super_admin"


def _is_admin(user: dict) -> bool:
    return (user or {}).get("role") in {"super_admin", "admin", "manager"}


@router.get("/channels")
async def list_channels(current_user: dict = Depends(get_current_user)):
    """Return the channel registry (id, label, description, cadence).
    Used by the admin UI to render column headers + tooltips.
    """
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    return {
        "channels": [
            {"id": cid, **meta} for cid, meta in np.CHANNELS.items()
        ]
    }


@router.get("/admins")
async def list_admins_with_authorizations(current_user: dict = Depends(get_current_user)):
    """Every admin user + their current per-channel authorisation flags.
    Defaults to deny-all for users without an authorisation row yet.
    """
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    rows = await np.list_admins_with_authorizations()
    return {"admins": rows, "count": len(rows)}


@router.get("/me")
async def my_subscriptions(current_user: dict = Depends(get_current_user)):
    """Read-only view of the current user's notification subscriptions.
    Surfaces "here's what you'll receive" without exposing the
    super-admin write controls. Closes the loop for new admins so they
    don't wonder why expected emails haven't arrived.
    """
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    email = (current_user or {}).get("email") or ""
    if not email:
        raise HTTPException(status_code=400, detail="Current user has no email on record.")

    # Reuse the same source-of-truth resolver so this view can never
    # drift from what the email senders actually do.
    from config import get_db
    db = get_db()
    row = await db[np.COLLECTION].find_one({"_id": email}) or {}
    stored = row.get("channels") or {}
    is_super = (current_user or {}).get("role") == "super_admin"

    channels_view = []
    for cid, meta in np.CHANNELS.items():
        # Mirror the resolver: super-admin defaults to subscribed unless
        # explicitly opted out; everyone else defaults to unsubscribed.
        default = is_super
        subscribed = bool(stored.get(cid, default))
        channels_view.append({
            "id": cid,
            "label": meta["label"],
            "description": meta["description"],
            "cadence": meta["cadence"],
            "subscribed": subscribed,
        })

    ua = row.get("updated_at")
    return {
        "email": email,
        "role": (current_user or {}).get("role"),
        "channels": channels_view,
        "subscribed_count": sum(1 for c in channels_view if c["subscribed"]),
        "total_channels": len(channels_view),
        "last_changed_at": ua.isoformat() if hasattr(ua, "isoformat") else ua,
        "last_changed_by": row.get("updated_by"),
    }


@router.put("/admin/{target_email}")
async def update_admin_authorization(
    target_email: str,
    payload: dict = Body(...),
    current_user: dict = Depends(get_current_user),
):
    """Replace the channel toggles for one admin. Super-admin only —
    keeps the financial-channel access trail tight.
    """
    if not _is_super_admin(current_user):
        raise HTTPException(
            status_code=403,
            detail="Only super-admins can modify notification authorisations.",
        )
    channels = payload.get("channels")
    if not isinstance(channels, dict):
        raise HTTPException(
            status_code=400,
            detail="Body must be {channels: {channel_id: bool, ...}}",
        )
    try:
        return await np.update_authorization(
            target_email=target_email,
            channels=channels,
            updated_by=current_user.get("email") or "unknown",
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

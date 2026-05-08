"""
Per-admin notification authorisations — Super-Admin-managed.

Default policy: deny.
  An admin only receives an automated email if a super-admin has
  *explicitly* enabled that channel for them. New admins onboarded
  to the platform receive nothing until they've been authorised.

Why super-admin-managed (not self-service)?
  Some channels expose board-level financials (P&L, quarterly deck).
  Self-service opt-in would mean a junior staff member could grant
  themselves access by toggling a checkbox. Centralising authorisation
  with the super-admin keeps the audit trail tight.

Storage shape
-------------
collection: `notification_authorizations`
{
  _id: <admin email>,         # natural key — emails are stable + human-readable in audits
  channels: {
    monthly_pnl: bool,
    quarterly_deck: bool,
    gsc_weekly_digest: bool,
    ctr_drop_alerts: bool,
    seo_quality_digest: bool,
    ui_health_alerts: bool,
  },
  updated_by: <super-admin email>,
  updated_at: ISODate,
}
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from config import get_db

logger = logging.getLogger(__name__)

COLLECTION = "notification_authorizations"

# Stable channel registry — IDs are referenced from the email-sending
# services, so DO NOT rename without a migration. Order is the order
# they appear in the admin UI (most-frequent → least-frequent).
CHANNELS: dict[str, dict[str, str]] = {
    "ui_health_alerts": {
        "label": "UI health alerts",
        "description": "Daily UI/uptime health report — JS console errors, slow pages, broken images.",
        "cadence": "Daily, 09:00",
    },
    "ctr_drop_alerts": {
        "label": "CTR drop alerts",
        "description": "Wakes you up when a high-traffic page suddenly loses clicks (Google update, lost ranking).",
        "cadence": "Daily, when triggered",
    },
    "seo_quality_digest": {
        "label": "Daily SEO digest",
        "description": "Daily roll-up of SEO drafts, AI city-page generation status, schema-markup health.",
        "cadence": "Weekly, Mon 09:30",
    },
    "gsc_weekly_digest": {
        "label": "GSC weekly digest",
        "description": "Search Console weekly digest — top queries, click trends, CTR movements.",
        "cadence": "Weekly, Mon 08:00",
    },
    "monthly_pnl": {
        "label": "Monthly SEO P&L email",
        "description": "Pound-equivalent SEO scoreboard — saved ad spend, top 5 keywords, page-1 wins/losses.",
        "cadence": "Monthly, 1st @ 08:00",
    },
    "quarterly_deck": {
        "label": "Quarterly board deck (PDF)",
        "description": "Quarterly SEO P&L PDF attachment — board-meeting ready summary of the last 3 months.",
        "cadence": "Quarterly, Jan/Apr/Jul/Oct 1st @ 09:00",
    },
}

DEFAULT_CHANNELS = {cid: False for cid in CHANNELS}


def is_valid_channel(channel_id: str) -> bool:
    return channel_id in CHANNELS


# ────────────────────────────────────────────────────────────────────────
# Read paths
# ────────────────────────────────────────────────────────────────────────


async def get_authorized_recipients(channel_id: str) -> list[str]:
    """Return the email list for a given channel.

    Authorisation policy:
      • **super_admin**: opted-in by default. Receives every channel
        unless they've explicitly opted-out (channel stored as False).
        Rationale: super-admins manage the system; making them tick
        their own boxes is bureaucracy with no security benefit.
      • **admin / manager**: deny-by-default. Receives a channel only
        when a super-admin has explicitly toggled it on (stored True).

    A super-admin who genuinely wants to opt out of one channel can
    still do so from the same Permissions UI — we honour the False.
    """
    if channel_id not in CHANNELS:
        logger.warning("Unknown notification channel requested: %s", channel_id)
        return []
    db = get_db()

    eligible = await db.users.find(
        {"role": {"$in": ["admin", "super_admin"]}, "email": {"$ne": None}},
        {"_id": 0, "email": 1, "role": 1},
    ).to_list(length=500)
    if not eligible:
        return []

    auth_rows = await db[COLLECTION].find(
        {"_id": {"$in": [u["email"] for u in eligible if u.get("email")]}}
    ).to_list(length=500)
    explicit_by_email: dict[str, dict] = {r["_id"]: (r.get("channels") or {}) for r in auth_rows}

    authorised: list[str] = []
    for u in eligible:
        email = u.get("email")
        if not email:
            continue
        stored = explicit_by_email.get(email)
        if u.get("role") == "super_admin":
            # Default-allow for super-admins. Only excluded if they've
            # *explicitly* set this channel to False.
            if stored is None or stored.get(channel_id) is not False:
                authorised.append(email)
        else:
            # Deny-by-default for admins/managers.
            if stored and stored.get(channel_id) is True:
                authorised.append(email)
    return authorised


async def list_admins_with_authorizations() -> list[dict[str, Any]]:
    """For the super-admin UI: every admin/super_admin user with their
    current per-channel authorisation flags merged in.
    """
    db = get_db()
    users = await db.users.find(
        {"role": {"$in": ["admin", "super_admin"]}, "email": {"$ne": None}},
        {"_id": 0, "email": 1, "role": 1, "name": 1, "first_name": 1, "last_name": 1},
    ).to_list(length=500)

    by_email: dict[str, dict[str, Any]] = {}
    for u in users:
        email = u.get("email")
        if not email:
            continue
        full_name = (
            u.get("name")
            or " ".join(filter(None, [u.get("first_name"), u.get("last_name")]))
            or ""
        ).strip()
        # Default state mirrors the resolver:
        #   • super_admin → all channels enabled by default
        #   • admin/manager → all channels disabled by default
        is_super = u.get("role") == "super_admin"
        default_channels = {cid: is_super for cid in CHANNELS}
        by_email[email] = {
            "email": email,
            "role": u.get("role"),
            "name": full_name,
            "channels": default_channels,
            "updated_by": None,
            "updated_at": None,
        }

    auth_rows = await db[COLLECTION].find(
        {"_id": {"$in": list(by_email.keys())}}
    ).to_list(length=500)
    for row in auth_rows:
        email = row.get("_id")
        if email not in by_email:
            continue
        is_super = by_email[email]["role"] == "super_admin"
        stored = row.get("channels") or {}
        # Merge stored channels with the registry. For super-admins, an
        # absent key means "default-allow" (True). For admins, absent
        # key means "default-deny" (False). This keeps the UI in sync
        # with what the resolver will actually do at send time.
        by_email[email]["channels"] = {
            cid: bool(stored.get(cid, is_super)) for cid in CHANNELS
        }
        by_email[email]["updated_by"] = row.get("updated_by")
        ua = row.get("updated_at")
        by_email[email]["updated_at"] = ua.isoformat() if hasattr(ua, "isoformat") else ua

    # Stable sort: super_admin first, then by email
    return sorted(
        by_email.values(),
        key=lambda x: (0 if x["role"] == "super_admin" else 1, x["email"]),
    )


# ────────────────────────────────────────────────────────────────────────
# Write paths
# ────────────────────────────────────────────────────────────────────────


async def update_authorization(
    *, target_email: str, channels: dict[str, bool], updated_by: str
) -> dict[str, Any]:
    """Replace the channel toggles for one admin. Validates that
    `target_email` is an actual admin/super_admin user, and that every
    incoming channel id is in the registry.
    """
    db = get_db()
    user = await db.users.find_one(
        {"email": target_email, "role": {"$in": ["admin", "super_admin"]}},
        {"_id": 0, "email": 1, "role": 1},
    )
    if not user:
        raise ValueError(f"{target_email} is not an admin user")

    cleaned = {
        cid: bool(channels.get(cid, False))
        for cid in CHANNELS  # drops unknown keys, back-fills missing
    }
    now = datetime.now(timezone.utc)
    await db[COLLECTION].update_one(
        {"_id": target_email},
        {"$set": {
            "_id": target_email,
            "channels": cleaned,
            "updated_by": updated_by,
            "updated_at": now,
        }},
        upsert=True,
    )
    return {
        "email": target_email,
        "channels": cleaned,
        "updated_by": updated_by,
        "updated_at": now.isoformat(),
    }

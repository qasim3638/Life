"""
One-shot migration: replace `qasim@tilestation.co.uk` with
`notifications@tilestation.co.uk` everywhere it's used for routing
notifications — and ONLY there. Auth, audit, identity and order-owner
fields are explicitly left untouched.

Exposed as an admin-only endpoint so the user can run it on
production from `/admin` without needing shell access.

Strategy: explicit allow-list of (collection, field) pairs known to
hold notification routing. We don't blanket-rewrite every doc that
contains the email — that would corrupt audit trails and order data.

Returns a detailed before/after report so the admin sees exactly what
changed.
"""
from __future__ import annotations

import logging
from typing import Any

from config import get_db

logger = logging.getLogger(__name__)


# Source → target email constants. Hardcoded because this is a one-off
# tenant-specific migration; not worth parameterising.
SOURCE_EMAIL = "qasim@tilestation.co.uk"
TARGET_EMAIL = "notifications@tilestation.co.uk"


# Allow-list of (collection, field) pairs that hold notification
# routing. ANYTHING not on this list is preserved as-is.
#   • `array` field type: list of email strings, replace exact matches
#   • `string` field type: single email string, replace if exact match
ROUTING_FIELDS: list[tuple[str, str, str]] = [
    # Live chat — admin alerts when a visitor messages
    ("website_chat_settings", "notification_emails", "array"),
    # SEO stealth-keyword weekly digest
    ("seo_stealth_digest_settings", "recipients", "array"),
    # UI health daily report
    ("website_settings", "ui_health_recipients", "array"),
    # Maintenance UI-checks schedule
    ("ui_health_schedule", "recipients", "array"),
    # Editorial autopilot summary
    ("editorial_autopilot_settings", "recipients", "array"),
    ("editorial_autopilot_settings", "notify_emails", "array"),
    # Failed payments alert
    ("failed_payments_settings", "notify_emails", "array"),
    # Quarterly P&L recipients
    ("quarterly_report_settings", "recipients", "array"),
    # Marketing studio admin alerts
    ("marketing_studio_settings", "notify_emails", "array"),
    # Weekly digest
    ("weekly_digest_settings", "recipients", "array"),
    # Generic alert recipient lists (some old code uses these)
    ("website_settings", "alert_recipients", "array"),
    ("website_settings", "notification_emails", "array"),
]


async def run_migration(dry_run: bool = True) -> dict[str, Any]:
    """Execute the migration. `dry_run=True` returns a preview without
    modifying any documents."""
    db = get_db()
    cols = await db.list_collection_names()
    changes: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    # 1. Update routing fields in admin-editable settings docs
    for col_name, field, kind in ROUTING_FIELDS:
        if col_name not in cols:
            continue
        try:
            cur = db[col_name].find({}, {"_id": 1, field: 1})
            async for doc in cur:
                v = doc.get(field)
                if not v:
                    continue
                if kind == "array" and isinstance(v, list) and SOURCE_EMAIL in v:
                    new_list = [TARGET_EMAIL if e == SOURCE_EMAIL else e for e in v]
                    # Dedupe in case both already present
                    seen = set()
                    deduped = []
                    for e in new_list:
                        if e not in seen:
                            seen.add(e)
                            deduped.append(e)
                    changes.append({
                        "collection": col_name,
                        "doc_id": str(doc["_id"]),
                        "field": field,
                        "before": v,
                        "after": deduped,
                    })
                    if not dry_run:
                        await db[col_name].update_one(
                            {"_id": doc["_id"]},
                            {"$set": {field: deduped}},
                        )
                elif kind == "string" and v == SOURCE_EMAIL:
                    changes.append({
                        "collection": col_name,
                        "doc_id": str(doc["_id"]),
                        "field": field,
                        "before": v,
                        "after": TARGET_EMAIL,
                    })
                    if not dry_run:
                        await db[col_name].update_one(
                            {"_id": doc["_id"]},
                            {"$set": {field: TARGET_EMAIL}},
                        )
        except Exception as exc:  # noqa: BLE001
            logger.exception("migration: error on %s.%s", col_name, field)
            skipped.append({
                "collection": col_name,
                "field": field,
                "reason": f"error: {str(exc)[:120]}",
            })
            continue

    # 2. notification_authorizations — per-user opt-in. Add a new row
    # for the notifications mailbox with ALL channels enabled, but do
    # NOT delete qasim's existing row (user may still want personal
    # alerts and admin login is a separate concern).
    notif_auth_action: dict[str, Any]
    if "notification_authorizations" in cols:
        existing_target = await db.notification_authorizations.find_one(
            {"_id": TARGET_EMAIL}
        )
        if existing_target:
            notif_auth_action = {
                "status": "already_present",
                "email": TARGET_EMAIL,
            }
        else:
            new_row = {
                "_id": TARGET_EMAIL,
                "channels": {
                    "ui_health_alerts": True,
                    "ctr_drop_alerts": True,
                    "seo_quality_digest": True,
                    "gsc_weekly_digest": True,
                    "monthly_pnl": True,
                    "quarterly_deck": True,
                },
                "updated_by": "notification_email_migration",
            }
            notif_auth_action = {
                "status": "would_add" if dry_run else "added",
                "email": TARGET_EMAIL,
                "row": new_row,
            }
            if not dry_run:
                from datetime import datetime, timezone
                new_row["updated_at"] = datetime.now(timezone.utc)
                try:
                    await db.notification_authorizations.insert_one(new_row)
                except Exception as exc:  # noqa: BLE001
                    notif_auth_action = {
                        "status": "skipped",
                        "email": TARGET_EMAIL,
                        "reason": str(exc)[:120],
                    }
    else:
        notif_auth_action = {"status": "collection_missing"}

    return {
        "dry_run": dry_run,
        "source_email": SOURCE_EMAIL,
        "target_email": TARGET_EMAIL,
        "routing_changes": changes,
        "routing_change_count": len(changes),
        "notification_authorizations": notif_auth_action,
        "skipped": skipped,
        "preserved_fields": [
            "users.email (admin login — never touched)",
            "*.created_by, *.updated_by, *.uploaded_by, *.disabled_by (audit fields)",
            "shop_orders.customer_email (order owner)",
            "payment_transactions.customer_email (customer ID)",
            "chat_messages.sender_email (message author)",
            "chat_sessions.assigned_to (agent assignment)",
            "Supplier credential constants in business_rules.py (login emails)",
        ],
    }

"""
Stripe ↔ DB payment-method capability auto-sync.

Runs once on backend startup. Calls Stripe's
`/v1/payment_method_configurations` to discover which methods are
*actually* activated on the connected Stripe account, then patches
`website_settings.checkout_settings.value.payments.{klarna,paypal}_enabled`
to match reality.

Why we need it
--------------
The admin "Payments" settings UI lets staff toggle Klarna/PayPal on,
which adds them to `payment_method_types` at checkout time. If those
methods aren't *actually* activated in the Stripe Dashboard, every
checkout 500s with "payment method type provided: <x> is invalid".

Sample-orders incident on May 2 2026 was exactly this — `paypal_enabled`
was true in our DB but PayPal was never activated on Stripe. Customers
saw "Failed to create sample order" on the Pay button. We have a runtime
safe-retry now (catches the error and falls back to card), but this
proactive sync stops the drift in the first place.

Audit trail: writes a row into `audit_logs` whenever it flips a flag.
"""
from __future__ import annotations

import os
import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

# Map Stripe payment-method config keys → our DB toggle keys.
# Add new entries here when we add Klarna BNPL etc.
_PM_TO_DB_TOGGLE = {
    "klarna": "klarna_enabled",
    "paypal": "paypal_enabled",
}


async def _fetch_stripe_pmc(api_key: str) -> dict | None:
    """Fetch the default Payment Method Configuration from Stripe.
    Returns the parsed config dict or None on any failure."""
    try:
        async with httpx.AsyncClient(timeout=8.0) as cli:
            r = await cli.get(
                "https://api.stripe.com/v1/payment_method_configurations",
                auth=(api_key, ""),
                params={"limit": 5},
            )
        if r.status_code != 200:
            logger.warning(f"[stripe-pm-sync] Stripe API returned {r.status_code}; skipping sync")
            return None
        configs = (r.json().get("data") or [])
        if not configs:
            logger.info("[stripe-pm-sync] no payment_method_configurations on this account; skipping")
            return None
        # Prefer the active / default configuration. Fall back to first.
        active = next((c for c in configs if c.get("active") and c.get("is_default")), None)
        active = active or next((c for c in configs if c.get("active")), configs[0])
        return active
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[stripe-pm-sync] fetch failed: {exc}")
        return None


def _is_method_active(pmc: dict, method_key: str) -> bool | None:
    """Read whether a single payment method is enabled on the live config.
    Returns True/False, or None if Stripe didn't include this method at all."""
    method_doc = (pmc or {}).get(method_key)
    if not isinstance(method_doc, dict):
        return None
    pref = method_doc.get("display_preference") or {}
    # Stripe surfaces three states: "on" (admin enabled), "off" (admin
    # disabled), "none" (never configured). Treat "on" as live, anything
    # else as not live.
    value = (pref.get("value") or "").lower()
    if value == "on":
        return True
    if value in ("off", "none", ""):
        return False
    return False


async def sync_stripe_payment_methods_to_db(db) -> dict:
    """Run the full sync. Returns a summary dict for log/audit."""
    api_key = os.environ.get("STRIPE_API_KEY") or os.environ.get("STRIPE_SECRET_KEY")
    if not api_key:
        return {"ran": False, "reason": "STRIPE_API_KEY not set"}

    pmc = await _fetch_stripe_pmc(api_key)
    if not pmc:
        return {"ran": False, "reason": "no payment_method_configurations available"}

    doc = await db.website_settings.find_one({"key": "checkout_settings"}, {"_id": 0})
    if not doc:
        return {"ran": False, "reason": "checkout_settings missing in DB"}

    payments_cfg = ((doc.get("value") or {}).get("payments") or {})
    changes: list[dict] = []

    for stripe_key, db_key in _PM_TO_DB_TOGGLE.items():
        live = _is_method_active(pmc, stripe_key)
        if live is None:
            # Stripe didn't include this method in its config; skip safely.
            continue
        currently = bool(payments_cfg.get(db_key))
        # Only auto-flip from True→False (i.e. disable a method that isn't
        # really on). We never auto-flip False→True, so an admin who has
        # explicitly disabled a method stays disabled even if Stripe says
        # it's available.
        if currently and not live:
            changes.append({
                "method": stripe_key,
                "db_key": db_key,
                "from": True,
                "to": False,
                "reason": "Stripe Dashboard reports this method as not activated",
            })

    if not changes:
        return {"ran": True, "changes": [], "message": "All payment methods in sync"}

    # Apply changes
    update_doc = {"updated_at": datetime.now(timezone.utc).isoformat()}
    for ch in changes:
        update_doc[f"value.payments.{ch['db_key']}"] = False

    await db.website_settings.update_one(
        {"key": "checkout_settings"},
        {"$set": update_doc},
        upsert=False,
    )

    # Best-effort audit log
    try:
        await db.audit_logs.insert_one({
            "action": "stripe_pm_autosync",
            "actor": "system",
            "at": datetime.now(timezone.utc).isoformat(),
            "changes": changes,
        })
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[stripe-pm-sync] audit log skipped: {exc}")

    logger.warning(
        f"[stripe-pm-sync] auto-disabled {len(changes)} payment methods that "
        f"Stripe reports inactive: {[c['method'] for c in changes]}"
    )
    return {"ran": True, "changes": changes}

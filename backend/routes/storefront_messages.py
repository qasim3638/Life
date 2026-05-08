"""
Storefront Messages — admin-controlled microcopy for transient toast/banner
messages shown on the public storefront.

Currently covers:
  - trade_login_toast   (fires when guest signs in as trade and cart re-prices)
  - trade_logout_toast  (fires when trade user logs out)

Stored in `website_settings.storefront_messages.value`. Public read so the
storefront can render the configured copy without needing auth.

Use {savings} placeholder in trade_login_toast.text — it gets replaced live
with the formatted £ amount the user just saved on their current cart.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException

from config import get_db
from services import get_current_user

router = APIRouter(prefix="/storefront-messages", tags=["Storefront Messages"])


# ---- Defaults ----
DEFAULT_TRADE_LOGIN = {
    "enabled": True,
    "text": "Welcome back — your basket switched to trade pricing. You just saved £{savings}.",
    "duration_ms": 6000,
}
DEFAULT_TRADE_LOGOUT = {
    "enabled": True,
    "text": "Switched back to retail pricing. Sign in to your trade account to save.",
    "duration_ms": 5000,
}
DEFAULT_IN_STORE_CREDIT = {
    "enabled": False,  # opt-in — store-wide trade credit accrual on EPOS invoices
}
DEFAULTS = {
    "trade_login_toast": DEFAULT_TRADE_LOGIN,
    "trade_logout_toast": DEFAULT_TRADE_LOGOUT,
    "in_store_credit": DEFAULT_IN_STORE_CREDIT,
}

# Allowed message keys + which sub-fields callers can mutate.
ALLOWED_FIELDS = {"enabled", "text", "duration_ms"}
DURATION_MIN_MS = 1500
DURATION_MAX_MS = 30000
TEXT_MAX_LEN = 280


def _require_super_admin(current_user: dict):
    if (current_user or {}).get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")


def _merge_defaults(stored: dict | None) -> dict:
    """Return a fully-populated config dict, falling back to defaults for any
    missing keys/fields. Always emits the same shape so the frontend can rely
    on it without optional-chaining everywhere."""
    out = {k: dict(v) for k, v in DEFAULTS.items()}
    if isinstance(stored, dict):
        for key, defaults in DEFAULTS.items():
            override = stored.get(key)
            if isinstance(override, dict):
                merged = dict(defaults)
                for f, v in override.items():
                    if f in ALLOWED_FIELDS:
                        merged[f] = v
                out[key] = merged
    return out


async def _load(db) -> dict:
    doc = await db.website_settings.find_one({"key": "storefront_messages"}, {"_id": 0})
    return _merge_defaults(doc.get("value") if doc else None)


def _validate_message(payload: dict, defaults: dict) -> dict:
    """Pick allowed fields off a payload, coerce types, and clamp ranges."""
    out = dict(defaults)
    if not isinstance(payload, dict):
        return out
    if "enabled" in payload:
        out["enabled"] = bool(payload["enabled"])
    if "text" in payload:
        text = str(payload["text"] or "").strip()
        # Basic sanity — don't let admins paste 5KB into a toast.
        if len(text) > TEXT_MAX_LEN:
            text = text[:TEXT_MAX_LEN]
        if text:
            out["text"] = text
    if "duration_ms" in payload:
        try:
            d = int(payload["duration_ms"])
            out["duration_ms"] = max(DURATION_MIN_MS, min(DURATION_MAX_MS, d))
        except (TypeError, ValueError):
            pass
    return out


@router.get("/public")
async def get_public():
    """No-auth read — used by the storefront toast watcher."""
    return await _load(get_db())


@router.get("")
async def get_admin(current_user: dict = Depends(get_current_user)):
    if (current_user or {}).get("role") not in {"super_admin", "admin", "manager"}:
        raise HTTPException(status_code=403, detail="Admin access required")
    return await _load(get_db())


@router.put("")
async def update_admin(payload: dict, current_user: dict = Depends(get_current_user)):
    _require_super_admin(current_user)
    db = get_db()
    current = await _load(db)
    for key, defaults in DEFAULTS.items():
        if key in (payload or {}):
            current[key] = _validate_message(payload[key], current.get(key, defaults))
    await db.website_settings.update_one(
        {"key": "storefront_messages"},
        {"$set": {"value": current, "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return current

"""
Storefront feature flags — single source of truth for whether each customer-facing
"lead magnet" / engagement feature is visible on the live storefront.

Stored in `website_settings.storefront_features.value`. Public read so the storefront
header/footer and Compare tray can decide whether to render.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException

from config import get_db
from services import get_current_user

router = APIRouter(prefix="/storefront-features", tags=["Storefront Features"])

DEFAULTS = {
    # Compare-products tray
    "compare_enabled": False,
    "compare_max": 3,
    # Refer-a-friend public page (/shop/refer)
    "refer_a_friend_enabled": False,
    "refer_a_friend_footer_link": True,
    # Welcome popup (separate from the welcome_popup config — this is just the on/off shortcut here)
    "welcome_popup_visible": True,
    # Cart-page "Save 10% — email me my code" banner (uses the same welcome-popup coupon settings)
    "cart_save_banner_enabled": False,
}


def _require_super_admin(current_user: dict):
    if (current_user or {}).get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")


async def _load(db) -> dict:
    doc = await db.website_settings.find_one({"key": "storefront_features"}, {"_id": 0})
    out = dict(DEFAULTS)
    if doc and isinstance(doc.get("value"), dict):
        out.update(doc["value"])
    return out


@router.get("/public")
async def get_public():
    """No-auth read — used by the storefront layout / Compare tray / footer."""
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
    allowed = set(DEFAULTS.keys())
    for k, v in (payload or {}).items():
        if k in allowed:
            if k in {"compare_max"}:
                try:
                    current[k] = max(2, min(6, int(v)))
                except (TypeError, ValueError):
                    pass
            else:
                current[k] = bool(v)
    await db.website_settings.update_one(
        {"key": "storefront_features"},
        {"$set": {"value": current, "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return current

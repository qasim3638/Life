"""
Admin endpoints for pallet pricing + stock status management.

  PUT  /api/admin/pallet-settings              — set/get pallet pricing mode
  GET  /api/admin/pallet-settings              — read current settings
  POST /api/admin/products/bulk/set-stock-status  — set stock status on N products
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from services import get_current_user
from config import get_db
from services.pallet_pricing import (
    PALLET_DEFAULTS,
    PALLET_PRICING_MODES,
    STOCK_STATUSES,
)

router = APIRouter(prefix="/admin", tags=["Pallet Pricing"])


def _require_admin(user: Optional[dict]) -> None:
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    role = (user or {}).get("role") or ""
    if role not in ("admin", "super_admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Admin access required")


# ── Pallet pricing settings ───────────────────────────────────────────

class PalletSettings(BaseModel):
    pallet_pricing_mode: str
    pallet_trade_extra_discount_pct: float = 0.0


@router.get("/pallet-settings")
async def get_pallet_settings(current_user: dict = Depends(get_current_user)):
    """Reads the current pallet pricing rules. Returns defaults if
    the website_settings doc has no pallet config yet."""
    _require_admin(current_user)
    db = get_db()
    settings_doc = await db.website_settings.find_one({}, {"_id": 0}) or {}
    return {
        "pallet_pricing_mode": settings_doc.get("pallet_pricing_mode", PALLET_DEFAULTS["pallet_pricing_mode"]),
        "pallet_trade_extra_discount_pct": float(
            settings_doc.get("pallet_trade_extra_discount_pct", PALLET_DEFAULTS["pallet_trade_extra_discount_pct"]) or 0
        ),
        "allowed_modes": list(PALLET_PRICING_MODES),
    }


@router.put("/pallet-settings")
async def update_pallet_settings(
    payload: PalletSettings,
    current_user: dict = Depends(get_current_user),
):
    """Saves new pallet pricing rules to website_settings."""
    _require_admin(current_user)
    if payload.pallet_pricing_mode not in PALLET_PRICING_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode. Must be one of: {', '.join(PALLET_PRICING_MODES)}",
        )
    pct = max(0.0, min(100.0, float(payload.pallet_trade_extra_discount_pct or 0)))
    db = get_db()
    await db.website_settings.update_one(
        {},
        {"$set": {
            "pallet_pricing_mode": payload.pallet_pricing_mode,
            "pallet_trade_extra_discount_pct": pct,
            "updated_at": datetime.now(timezone.utc),
        }},
        upsert=True,
    )
    return {
        "ok": True,
        "pallet_pricing_mode": payload.pallet_pricing_mode,
        "pallet_trade_extra_discount_pct": pct,
    }


# ── Bulk stock-status setter ──────────────────────────────────────────

class BulkStockStatusBody(BaseModel):
    product_ids: List[str]
    status: str  # one of STOCK_STATUSES


@router.post("/products/bulk/set-stock-status")
async def bulk_set_stock_status(
    body: BulkStockStatusBody,
    current_user: dict = Depends(get_current_user),
):
    """Apply a stock status to N products in one call.

    Used by the bottom toolbar of the Suppliers & Products page so
    admins can mark a batch of clearance / job-lot tiles as
    `out_of_stock` without opening each one.

    Bulk endpoint to avoid N round-trips. Idempotent — running
    twice with the same body produces the same DB state.
    """
    _require_admin(current_user)
    if body.status not in STOCK_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(STOCK_STATUSES)}",
        )
    if not body.product_ids:
        return {"ok": True, "updated": 0}

    db = get_db()
    res = await db.products.update_many(
        {"id": {"$in": body.product_ids}},
        {"$set": {
            "stock_status": body.status,
            "updated_at": datetime.now(timezone.utc),
        }},
    )
    return {
        "ok": True,
        "updated": res.modified_count,
        "matched": res.matched_count,
        "status": body.status,
    }

"""
Marketing Funnel — last-N-days metrics aggregating every lead-magnet / recovery
channel into one admin dashboard tile.

Sources:
  - popup_emails           → Welcome Popup + Cart Save Banner captures (source field)
  - abandoned_carts        → recovery emails / WhatsApp / £ recovered
  - shop_discount_codes    → minted + redeemed by source

GET /api/marketing/funnel?days=7   (admin / manager / super_admin)
"""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query

from config import get_db
from services import get_current_user

router = APIRouter(prefix="/marketing", tags=["Marketing Funnel"])


def _require_admin(current_user: dict):
    if (current_user or {}).get("role") not in {"super_admin", "admin", "manager"}:
        raise HTTPException(status_code=403, detail="Admin access required")


@router.get("/funnel")
async def get_funnel(
    days: int = Query(7, ge=1, le=90),
    current_user: dict = Depends(get_current_user),
):
    """Aggregate the last `days` (default 7) of marketing-funnel activity."""
    _require_admin(current_user)
    db = get_db()
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)

    # popup_emails uses naive datetime.utcnow() in the welcome-popup capture handler,
    # so compare against a naive cutoff to avoid timezone-aware/naive mix-ups.
    since_naive = since.replace(tzinfo=None)

    # ---- 1. Email captures (Welcome Popup + Cart Save Banner) ----
    popup_pipeline = [
        {"$match": {"$or": [
            {"captured_at": {"$gte": since}},
            {"captured_at": {"$gte": since_naive}},
        ]}},
        {"$group": {"_id": "$source", "count": {"$sum": 1}}},
    ]
    popup_rows = await db.popup_emails.aggregate(popup_pipeline).to_list(50)
    popups_captured = 0
    banners_captured = 0
    for row in popup_rows:
        src = (row.get("_id") or "").lower()
        c = int(row.get("count") or 0)
        if src == "cart_save_banner":
            banners_captured += c
        else:
            popups_captured += c

    # ---- 2. Abandoned-cart channel activity ----
    abandoned_in_window = await db.abandoned_carts.count_documents({
        "created_at": {"$gte": since},
    })

    emails_sent = await db.abandoned_carts.count_documents({
        "$or": [
            {"day_0_sent_at": {"$gte": since}},
            {"day_1_sent_at": {"$gte": since}},
            {"last_chance_sent_at": {"$gte": since}},
        ],
    })

    whatsapp_sent = await db.abandoned_carts.count_documents({
        "whatsapp_sent_at": {"$gte": since},
    })

    recovered_pipeline = await db.abandoned_carts.aggregate([
        {"$match": {"status": "recovered", "recovered_at": {"$gte": since}}},
        {"$group": {
            "_id": None,
            "count": {"$sum": 1},
            "value": {"$sum": "$cart_total"},
        }},
    ]).to_list(1)
    rec = recovered_pipeline[0] if recovered_pipeline else {}
    recovered_count = int(rec.get("count") or 0)
    revenue_recovered = round(float(rec.get("value") or 0), 2)

    # ---- 3. Promo codes — minted + redeemed by source ----
    minted_rows = await db.shop_discount_codes.aggregate([
        {"$match": {"created_at": {"$gte": since}}},
        {"$group": {"_id": "$source", "count": {"$sum": 1}}},
    ]).to_list(50)
    minted_by_source = {(r.get("_id") or "manual"): int(r.get("count") or 0) for r in minted_rows}

    redeemed_rows = await db.shop_discount_codes.aggregate([
        {"$match": {
            "used_count": {"$gte": 1},
            "updated_at": {"$gte": since},
        }},
        {"$group": {"_id": "$source", "count": {"$sum": "$used_count"}}},
    ]).to_list(50)
    redeemed_by_source = {(r.get("_id") or "manual"): int(r.get("count") or 0) for r in redeemed_rows}

    sources = sorted(set(list(minted_by_source.keys()) + list(redeemed_by_source.keys())))
    by_source = [
        {
            "source": s,
            "minted": minted_by_source.get(s, 0),
            "redeemed": redeemed_by_source.get(s, 0),
        }
        for s in sources
    ]

    codes_minted = sum(minted_by_source.values())
    codes_redeemed = sum(redeemed_by_source.values())

    return {
        "days": days,
        "since": since.isoformat(),
        "captures": {
            "welcome_popup": popups_captured,
            "cart_save_banner": banners_captured,
            "total": popups_captured + banners_captured,
        },
        "abandoned": {
            "new": abandoned_in_window,
            "emails_sent": emails_sent,
            "whatsapp_sent": whatsapp_sent,
            "recovered_count": recovered_count,
            "revenue_recovered": revenue_recovered,
        },
        "codes": {
            "minted": codes_minted,
            "redeemed": codes_redeemed,
            "by_source": by_source,
        },
    }

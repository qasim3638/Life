"""
Recently Viewed Products System
Tracks and returns recently viewed products for customers
"""
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query

from config import get_db

router = APIRouter(prefix="/recently-viewed", tags=["Recently Viewed"])

# ============ ROUTES ============

@router.post("/track")
async def track_product_view(product_id: str, session_id: str):
    """
    Track a product view for a session.
    """
    db = get_db()
    
    if not product_id or not session_id:
        raise HTTPException(status_code=400, detail="product_id and session_id required")
    
    # Update or create session record
    await db.recently_viewed.update_one(
        {"session_id": session_id},
        {
            "$set": {"updated_at": datetime.now(timezone.utc)},
            "$setOnInsert": {"created_at": datetime.now(timezone.utc)},
            "$push": {
                "products": {
                    "$each": [{
                        "product_id": product_id,
                        "viewed_at": datetime.now(timezone.utc)
                    }],
                    "$slice": -20  # Keep last 20 views
                }
            }
        },
        upsert=True
    )
    
    return {"status": "tracked"}


@router.get("/{session_id}")
async def get_recently_viewed(
    session_id: str,
    limit: int = Query(10, le=20)
):
    """
    Get recently viewed products for a session.
    """
    db = get_db()
    
    # Get session's recently viewed
    session = await db.recently_viewed.find_one({"session_id": session_id})
    
    if not session or not session.get("products"):
        return {"products": []}
    
    # Get unique product IDs (most recent first)
    seen = set()
    unique_product_ids = []
    for p in reversed(session["products"]):
        pid = p["product_id"]
        if pid not in seen:
            seen.add(pid)
            unique_product_ids.append(pid)
            if len(unique_product_ids) >= limit:
                break
    
    if not unique_product_ids:
        return {"products": []}
    
    # Fetch product details
    products = await db.products.find(
        {"id": {"$in": unique_product_ids}, "website_visible": True},
        {"_id": 0, "id": 1, "name": 1, "display_name": 1, "website_name": 1, 
         "price": 1, "room_lot_price": 1, "images": 1, "slug": 1, "size": 1, "finish": 1}
    ).to_list(limit)
    
    # Sort by original order
    product_map = {p["id"]: p for p in products}
    ordered_products = [product_map[pid] for pid in unique_product_ids if pid in product_map]
    
    return {"products": ordered_products}


@router.delete("/{session_id}")
async def clear_recently_viewed(session_id: str):
    """
    Clear recently viewed history for a session.
    """
    db = get_db()
    
    await db.recently_viewed.delete_one({"session_id": session_id})
    
    return {"status": "cleared"}

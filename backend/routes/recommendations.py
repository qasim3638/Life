"""
Product Recommendations System
Provides "Customers also bought" and "Complete the look" suggestions
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from collections import Counter

from config import get_db
from services import get_current_user, is_admin_user
from services.recommendations_builder import rebuild_co_purchase_cache, is_installation_essential

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])
logger = logging.getLogger(__name__)

# ============ ROUTES ============

@router.get("/frequently-bought-together/{product_id}")
async def get_frequently_bought_together(product_id: str, limit: int = 4):
    """
    Returns up to N **installation essentials** (adhesive, grout, sealer,
    primer, spacer, trim, etc.) frequently bought alongside the given tile.
    Sourced from `frequently_bought_cache` (rebuilt nightly). Falls back to a
    popular-essentials list when the product has no co-purchase history yet.

    `product_id` is the storefront-facing tile id (which is the BSON `_id`
    serialized as a hex string by `serialize_tile_for_shop`).
    """
    from bson import ObjectId
    from routes.tiles import serialize_tile_for_shop

    db = get_db()
    cache_doc = await db.frequently_bought_cache.find_one(
        {"product_id": product_id},
        {"_id": 0, "related": 1},
    )

    related = (cache_doc or {}).get("related") or []
    related = related[:limit]

    if not related:
        return await _popular_essentials_fallback(db, product_id, limit)

    related_ids = [r["product_id"] for r in related]
    count_map = {r["product_id"]: int(r["count"]) for r in related}

    # Hydrate from `tiles`. The cache may store ids as either:
    #   * hex `_id` strings (what shop_orders stores via `serialize_tile_for_shop`)
    #   * native tile.id values (rare — legacy / EPOS rows that didn't carry _id)
    # Try both lookup paths so hydration always succeeds.
    object_ids = []
    for pid in related_ids:
        try:
            object_ids.append(ObjectId(pid))
        except Exception:
            pass

    or_clauses = []
    if object_ids:
        or_clauses.append({"_id": {"$in": object_ids}})
    or_clauses.append({"id": {"$in": related_ids}})

    tile_cursor = db.tiles.find(
        {"$or": or_clauses, "is_active": {"$ne": False}},
    )
    hydrated = {}
    async for t in tile_cursor:
        # Belt-and-braces filter — cache builder already filtered to essentials,
        # but a stale cache row could otherwise leak a tile through.
        if not is_installation_essential(t):
            continue
        hex_id = str(t.get("_id"))
        hydrated[hex_id] = t
        if t.get("id"):
            hydrated[t["id"]] = t

    out = []
    seen = set()
    for pid in related_ids:
        t = hydrated.get(pid)
        if not t:
            continue
        marker = str(t.get("_id"))
        if marker in seen:
            continue
        seen.add(marker)
        serialized = serialize_tile_for_shop(t)
        serialized["times_bought_together"] = count_map.get(pid, 0)
        out.append(serialized)

    if not out:
        return await _popular_essentials_fallback(db, product_id, limit)

    return out


@router.post("/rebuild-cache")
async def admin_rebuild_cache(current_user: dict = Depends(get_current_user)):
    """Manual trigger for the nightly co-purchase rebuild — useful after a
    data migration or to seed the cache for the first time."""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    return await rebuild_co_purchase_cache()


@router.get("/admin/essentials-needing-photos")
async def admin_essentials_needing_photos(
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
):
    """
    Audit checklist for the photography backlog. Returns installation
    essentials with no product image, prioritised by:
      1. Whether the SKU is *currently surfaced* in `frequently_bought_cache`
         (these embarrass us most — they show up on real PDPs as "No image").
      2. view_count (popularity proxy) — picture these next.
    """
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")

    db = get_db()

    # Build the set of essential ids currently used as recommendations.
    in_cache_ids: set = set()
    async for row in db.frequently_bought_cache.find({}, {"_id": 0, "related": 1}):
        for r in (row.get("related") or []):
            if r.get("product_id"):
                in_cache_ids.add(str(r["product_id"]))

    cursor = db.tiles.find(
        {"is_active": {"$ne": False}},
        {"_id": 1, "id": 1, "display_name": 1, "name": 1, "sku": 1,
         "category": 1, "sub_category": 1, "main_category": 1,
         "images": 1, "view_count": 1, "price": 1},
    )
    no_photo = []
    async for t in cursor:
        if not is_installation_essential(t):
            continue
        imgs = t.get("images") or []
        if any(isinstance(i, str) and i.strip() for i in imgs):
            continue
        hex_id = str(t.get("_id"))
        no_photo.append({
            "id": hex_id,
            "display_name": t.get("display_name") or t.get("name") or "(unnamed)",
            "sku": t.get("sku") or "",
            "price": float(t.get("price") or 0),
            "view_count": int(t.get("view_count") or 0),
            "in_fbt_cache": (hex_id in in_cache_ids) or (t.get("id") and t["id"] in in_cache_ids),
        })

    # Sort: in-cache first, then by view_count desc, then by name.
    no_photo.sort(key=lambda r: (not r["in_fbt_cache"], -r["view_count"], r["display_name"].lower()))

    total = len(no_photo)
    in_cache_total = sum(1 for r in no_photo if r["in_fbt_cache"])
    return {
        "total_missing": total,
        "in_cache_missing": in_cache_total,
        "items": no_photo[:limit],
    }


@router.get("/complete-the-look/{product_id}")
async def get_complete_the_look(product_id: str, limit: int = 4):
    """
    Get complementary products to complete the look.
    Suggests accessories, grout, adhesive, trims based on product type.
    """
    db = get_db()
    
    # Get the source product
    product = await db.products.find_one({"id": product_id})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    recommendations = []
    
    # Get product attributes
    product_type = (product.get("type") or "").lower()
    product_color = (product.get("color") or "").lower()
    
    # If it's a tile, suggest accessories
    if "tile" in product_type or product.get("category", "").lower() in ["floor tiles", "wall tiles"]:
        # Suggest matching grout colors (color suggestions for future use)
        _ = get_matching_grout_colors(product_color)
        grout_products = await db.products.find({
            "website_visible": True,
            "$or": [
                {"name": {"$regex": "grout", "$options": "i"}},
                {"category": {"$regex": "grout", "$options": "i"}},
                {"type": {"$regex": "grout", "$options": "i"}}
            ]
        }, {"_id": 0}).limit(2).to_list(2)
        recommendations.extend(grout_products)
        
        # Suggest adhesive
        adhesive_products = await db.products.find({
            "website_visible": True,
            "$or": [
                {"name": {"$regex": "adhesive", "$options": "i"}},
                {"category": {"$regex": "adhesive", "$options": "i"}}
            ]
        }, {"_id": 0}).limit(1).to_list(1)
        recommendations.extend(adhesive_products)
        
        # Suggest trim/edging
        trim_products = await db.products.find({
            "website_visible": True,
            "$or": [
                {"name": {"$regex": "trim", "$options": "i"}},
                {"name": {"$regex": "edge", "$options": "i"}},
                {"category": {"$regex": "trim", "$options": "i"}}
            ]
        }, {"_id": 0}).limit(1).to_list(1)
        recommendations.extend(trim_products)
    
    # If not enough, top up with popular essentials
    if len(recommendations) < limit:
        more = await _popular_essentials_fallback(
            db, product_id, limit - len(recommendations)
        )
        recommendations.extend(more)
    
    return recommendations[:limit]


@router.get("/trending")
async def get_trending_products(limit: int = 8, days: int = 30):
    """
    Get trending products based on recent sales.
    """
    db = get_db()
    
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Aggregate sales by product
    pipeline = [
        {"$match": {"created_at": {"$gte": cutoff_date}}},
        {"$unwind": "$items"},
        {"$group": {
            "_id": "$items.product_id",
            "total_sold": {"$sum": "$items.quantity"},
            "revenue": {"$sum": {"$multiply": ["$items.quantity", "$items.price"]}}
        }},
        {"$sort": {"total_sold": -1}},
        {"$limit": limit}
    ]
    
    trending_ids = await db.invoices.aggregate(pipeline).to_list(limit)
    product_ids = [t["_id"] for t in trending_ids if t["_id"]]
    
    if not product_ids:
        # Fallback to featured products
        return await db.products.find(
            {"website_visible": True, "featured": True},
            {"_id": 0}
        ).limit(limit).to_list(limit)
    
    # Fetch product details
    products = await db.products.find(
        {"id": {"$in": product_ids}, "website_visible": True},
        {"_id": 0}
    ).to_list(limit)
    
    # Add sales data and sort by sales
    sales_map = {t["_id"]: t for t in trending_ids}
    for product in products:
        sales_data = sales_map.get(product["id"], {})
        product["trending_score"] = sales_data.get("total_sold", 0)
    
    products.sort(key=lambda x: x.get("trending_score", 0), reverse=True)
    
    return products


@router.get("/recently-viewed/{session_id}")
async def get_recently_viewed(session_id: str, limit: int = 6):
    """
    Get recently viewed products for a session/user.
    Frontend stores this in localStorage and syncs periodically.
    """
    db = get_db()
    
    # Find session's recently viewed
    session = await db.user_sessions.find_one({"session_id": session_id})
    
    if not session or not session.get("recently_viewed"):
        return []
    
    product_ids = session["recently_viewed"][-limit:][::-1]  # Most recent first
    
    products = await db.products.find(
        {"id": {"$in": product_ids}, "website_visible": True},
        {"_id": 0}
    ).to_list(limit)
    
    # Sort by view order
    product_map = {p["id"]: p for p in products}
    return [product_map[pid] for pid in product_ids if pid in product_map]


@router.post("/track-view")
async def track_product_view(product_id: str, session_id: str):
    """
    Track a product view for recommendations.
    """
    db = get_db()
    
    # Update or create session
    await db.user_sessions.update_one(
        {"session_id": session_id},
        {
            "$push": {
                "recently_viewed": {
                    "$each": [product_id],
                    "$slice": -20  # Keep last 20
                }
            },
            "$set": {"updated_at": datetime.now(timezone.utc)},
            "$setOnInsert": {"created_at": datetime.now(timezone.utc)}
        },
        upsert=True
    )
    
    # Also increment view count on product
    await db.products.update_one(
        {"id": product_id},
        {"$inc": {"view_count": 1}}
    )
    
    return {"status": "tracked"}


# ============ HELPER FUNCTIONS ============

async def _popular_essentials_fallback(db, product_id: str, limit: int):
    """
    Cold-start fallback. Returns popular installation essentials so a brand-new
    tile PDP still gets a useful "Frequently Bought Together" section.

    Skips entirely when the anchor product itself is an essential — we don't
    want a grout PDP recommending more grout via the FBT slot. (The legacy
    `/complete-the-look` endpoint is a better surface for that case.)
    """
    from bson import ObjectId
    from routes.tiles import serialize_tile_for_shop

    # Resolve the anchor so we can decide whether to suggest at all.
    anchor = None
    try:
        anchor = await db.tiles.find_one({"_id": ObjectId(product_id)})
    except Exception:
        pass
    if not anchor:
        anchor = await db.tiles.find_one({"id": product_id})

    if anchor and is_installation_essential(anchor):
        return []

    # Pick essentials with the highest sales/view signal we have available.
    # `view_count` is incremented by the existing /recommendations/track-view
    # endpoint; it's a reasonable proxy for general popularity. Essentials
    # often ship without uploaded product photos so we don't filter on images
    # — the frontend renders a graceful "No image" placeholder.
    cursor = db.tiles.find(
        {"is_active": {"$ne": False}},
    ).sort([("view_count", -1), ("updated_at", -1)])

    out = []
    seen = set()
    async for t in cursor:
        if not is_installation_essential(t):
            continue
        marker = str(t.get("_id"))
        if marker in seen:
            continue
        seen.add(marker)
        out.append(serialize_tile_for_shop(t))
        if len(out) >= limit:
            break

    return out


def get_matching_grout_colors(tile_color: str) -> List[str]:
    """
    Suggest grout colors that complement the tile color.
    """
    color_map = {
        "white": ["white", "ivory", "light grey"],
        "grey": ["grey", "charcoal", "white"],
        "black": ["black", "charcoal", "dark grey"],
        "beige": ["beige", "cream", "ivory"],
        "cream": ["cream", "white", "ivory"],
        "brown": ["brown", "chocolate", "beige"],
        "blue": ["grey", "white", "navy"],
        "green": ["grey", "white", "sage"],
    }
    
    tile_color_lower = tile_color.lower()
    
    for key, values in color_map.items():
        if key in tile_color_lower:
            return values
    
    # Default suggestions
    return ["white", "grey", "matching"]

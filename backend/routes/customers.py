"""
Customer management routes
"""
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Body, Query

from config import get_db
from services import get_current_user, is_admin_user

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.get("/email-suggestions")
async def get_customer_email_suggestions(
    search: str = Query("", description="Search term for email suggestions"),
    current_user: dict = Depends(get_current_user)
):
    """Get customer email suggestions from past documents for auto-complete.
    Searches invoices, quotations, cash_quotations, refunds, and credit_notes.
    Returns unique customer records with email, name, and phone."""
    
    # Staff with EPOS permission need to access customers for invoices
    user_permissions = current_user.get("permissions", [])
    has_epos_access = is_admin_user(current_user) or "epos" in user_permissions
    if not has_epos_access:
        raise HTTPException(status_code=403, detail="EPOS access required")
    
    db = get_db()
    
    # Build search query - search by email, name, or phone
    search_lower = search.lower().strip() if search else ""
    
    # Aggregate unique customers from all document collections
    customers_map = {}  # Use email as key to deduplicate
    
    collections = ["invoices", "quotations", "cash_quotations", "refunds", "credit_notes"]
    
    for collection_name in collections:
        collection = db[collection_name]
        
        # Build match query
        if search_lower:
            match_query = {
                "$or": [
                    {"customer_email": {"$regex": search_lower, "$options": "i"}},
                    {"customer_name": {"$regex": search_lower, "$options": "i"}},
                    {"customer_phone": {"$regex": search_lower, "$options": "i"}}
                ],
                "customer_email": {"$exists": True, "$nin": ["", None]}
            }
        else:
            match_query = {
                "customer_email": {"$exists": True, "$nin": ["", None]}
            }
        
        # Get documents with customer info
        docs = await collection.find(
            match_query,
            {"_id": 0, "customer_email": 1, "customer_name": 1, "customer_phone": 1, "customer_address": 1, "date": 1}
        ).sort("date", -1).limit(100).to_list(100)
        
        for doc in docs:
            email = doc.get("customer_email", "").strip().lower()
            if email and email not in customers_map:
                customers_map[email] = {
                    "email": doc.get("customer_email", ""),
                    "name": doc.get("customer_name", ""),
                    "phone": doc.get("customer_phone", ""),
                    "address": doc.get("customer_address", "")
                }
    
    # Convert to list and sort by email
    suggestions = sorted(customers_map.values(), key=lambda x: x["email"].lower())
    
    # Limit results
    return suggestions[:20]


@router.get("")
async def get_customers(
    showroom_id: Optional[str] = None,
    marketing_opt_in: Optional[bool] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all customers with optional filters (authenticated users with EPOS access)"""
    # Staff with EPOS permission need to access customers for invoices
    user_permissions = current_user.get("permissions", [])
    has_epos_access = is_admin_user(current_user) or "epos" in user_permissions
    if not has_epos_access:
        raise HTTPException(status_code=403, detail="EPOS access required")
    
    db = get_db()
    query = {"role": "customer"}
    
    if showroom_id:
        query["showroom_id"] = showroom_id
    
    if marketing_opt_in is not None:
        query["marketing_opt_in"] = marketing_opt_in
    
    customers = await db.users.find(query, {"_id": 0, "password": 0}).to_list(100000)
    
    # Add showroom names
    showrooms = {s["id"]: s["name"] for s in await db.showrooms.find({}, {"_id": 0}).to_list(100000)}
    for customer in customers:
        if customer.get("showroom_id"):
            customer["showroom_name"] = showrooms.get(customer["showroom_id"], "Unknown")
    
    return customers


@router.put("/{customer_email}/showroom")
async def assign_customer_showroom(
    customer_email: str,
    showroom_id: Optional[str] = Body(None, embed=True),
    current_user: dict = Depends(get_current_user)
):
    """Assign a customer to a showroom (admin only)"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    db = get_db()
    result = await db.users.update_one(
        {"email": customer_email, "role": "customer"},
        {"$set": {"showroom_id": showroom_id}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    return {"message": "Customer showroom updated"}



@router.get("/unified-search")
async def unified_customer_search(
    q: str = Query("", description="Free-text search across name/email/phone/postcode"),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """Search BOTH the staff-managed `users` table AND the online-registered
    `shop_customers` table at once, so the EPOS Invoice / Quotation / etc.
    can find a trade customer who registered online but is paying in store.

    Returns a single de-duplicated list (matched on email) with a `source`
    field so the UI can show a 🌐 chip for online accounts:
      - source='users'        → existing in-store customer
      - source='shop'         → online customer not yet linked
      - source='users+shop'   → already linked (same email in both tables)

    For shop_customers we also surface the trade fields the till needs so a
    trade customer can be priced + invoiced correctly without a second
    round-trip:
      `is_trade`, `trade_account_number`, `trade_account_status`,
      `business_name`, `credit_balance`, `credit_rate`, `trade_tier`,
      `trade_discount`, `total_spent`.
    """
    user_permissions = (current_user or {}).get("permissions", [])
    has_epos_access = is_admin_user(current_user) or "epos" in user_permissions
    if not has_epos_access:
        raise HTTPException(status_code=403, detail="EPOS access required")

    db = get_db()
    needle = (q or "").strip()
    if not needle:
        return {"results": [], "total": 0}

    # Build a $regex for partial / case-insensitive matches across the most
    # useful fields. Stay anchored on prefix where possible to keep query
    # cheap on the indexed `email` field.
    import re as _re
    safe = _re.escape(needle)
    rx = {"$regex": safe, "$options": "i"}

    users_q = {
        "role": "customer",
        "$or": [
            {"name": rx},
            {"email": rx},
            {"phone": rx},
            {"address.postcode": rx},
            {"address.city": rx},
        ],
    }
    shop_q = {
        "$or": [
            {"name": rx},
            {"email": rx},
            {"phone": rx},
            {"business_name": rx},
            {"trade_account_number": rx},
            {"address.postcode": rx},
            {"address.city": rx},
        ],
    }

    users_proj = {"_id": 0, "password": 0}
    shop_proj = {
        "_id": 0,
        "id": 1, "name": 1, "email": 1, "phone": 1, "address": 1,
        "is_trade": 1, "trade_account_number": 1, "trade_account_status": 1,
        "business_name": 1, "credit_balance": 1, "credit_rate": 1,
        "trade_tier": 1, "trade_discount": 1, "total_spent": 1,
        "created_at": 1,
    }

    users_rows = await db.users.find(users_q, users_proj).limit(limit).to_list(limit)
    shop_rows = await db.shop_customers.find(shop_q, shop_proj).limit(limit).to_list(limit)

    # De-dupe on email (case-insensitive). users row wins on shared fields,
    # but trade fields from the shop row are merged in. This is how a trade
    # customer with both an old in-store record AND an online registration
    # ends up presented as a single entry that staff can pick once.
    by_email: dict = {}
    for u in users_rows:
        key = (u.get("email") or "").lower().strip()
        if not key:
            continue
        u["source"] = "users"
        by_email[key] = u
    for s in shop_rows:
        key = (s.get("email") or "").lower().strip()
        if not key:
            continue
        existing = by_email.get(key)
        if existing:
            existing["source"] = "users+shop"
            existing["shop_customer_id"] = s.get("id")
            for tf in ("is_trade", "trade_account_number", "trade_account_status",
                       "business_name", "credit_balance", "credit_rate",
                       "trade_tier", "trade_discount", "total_spent"):
                if s.get(tf) is not None:
                    existing[tf] = s[tf]
        else:
            s["source"] = "shop"
            s["shop_customer_id"] = s.get("id")
            by_email[key] = s

    # Sort: trade customers first (so they're easy to spot), then by name.
    results = list(by_email.values())
    results.sort(
        key=lambda r: (
            0 if r.get("is_trade") else 1,
            (r.get("name") or "").lower(),
        ),
    )
    results = results[:limit]
    return {"results": results, "total": len(results)}



# ============================================================================
# EPOS feature flags — minimal key/value store on `website_settings`. Used so
# super-admin can toggle experimental EPOS behaviours (e.g. auto trade
# pricing) without a redeploy. Read-by-anyone-with-EPOS, write-by-super-admin.
# ============================================================================

# Hardcoded list of valid flag keys — keeps the surface area tight, prevents
# drive-by writes to arbitrary settings docs, and gives the frontend a single
# place to look up defaults. Default is always "hidden" (opt-in by design).
EPOS_FEATURE_FLAGS_DEFAULTS = {
    "trade_pricing_apply_button": False,  # opt-in apply-trade-pricing button on Invoice
}


def _is_super_admin(user: dict) -> bool:
    return (user or {}).get("role") == "super_admin"


@router.get("/epos-feature-flags")
async def get_epos_feature_flags(current_user: dict = Depends(get_current_user)):
    """Returns the current EPOS feature-flag map, with defaults filled in for
    any key not yet persisted. Permission: any user with EPOS access — they
    just need to know whether to show the experimental UI bits."""
    user_permissions = (current_user or {}).get("permissions", [])
    has_epos_access = is_admin_user(current_user) or "epos" in user_permissions
    if not has_epos_access:
        raise HTTPException(status_code=403, detail="EPOS access required")
    db = get_db()
    doc = await db.website_settings.find_one(
        {"_id": "epos_feature_flags"},
        {"_id": 0, "flags": 1},
    ) or {}
    flags = dict(EPOS_FEATURE_FLAGS_DEFAULTS)
    flags.update(doc.get("flags") or {})
    return {"flags": flags}


@router.put("/epos-feature-flags")
async def update_epos_feature_flags(
    flags: dict = Body(..., embed=True),
    current_user: dict = Depends(get_current_user),
):
    """Update one or more EPOS feature flags. Super-admin only.
    Body shape: `{"flags": {"trade_pricing_apply_button": true}}`."""
    if not _is_super_admin(current_user):
        raise HTTPException(status_code=403, detail="Super admin access required")
    if not isinstance(flags, dict):
        raise HTTPException(status_code=400, detail="flags must be an object")
    # Coerce to bools, drop unknown keys so the surface stays tight.
    safe = {k: bool(v) for k, v in flags.items() if k in EPOS_FEATURE_FLAGS_DEFAULTS}
    if not safe:
        raise HTTPException(status_code=400, detail="No valid flag keys supplied")
    db = get_db()
    await db.website_settings.update_one(
        {"_id": "epos_feature_flags"},
        {"$set": {f"flags.{k}": v for k, v in safe.items()}},
        upsert=True,
    )
    # Return the merged map so the UI doesn't need a second round-trip.
    doc = await db.website_settings.find_one(
        {"_id": "epos_feature_flags"},
        {"_id": 0, "flags": 1},
    ) or {}
    out = dict(EPOS_FEATURE_FLAGS_DEFAULTS)
    out.update(doc.get("flags") or {})
    return {"flags": out, "updated": list(safe.keys())}

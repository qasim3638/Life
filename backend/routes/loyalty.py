"""
Customer Loyalty Program
Points system, tiers, and rewards for repeat customers
"""
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel

from config import get_db
from routes.auth import get_current_user

router = APIRouter(prefix="/loyalty", tags=["Loyalty Program"])

# ============ CONSTANTS ============

# Points per £1 spent
POINTS_PER_POUND = 10

# Tier thresholds (total lifetime points)
TIERS = {
    "bronze": {"min_points": 0, "discount": 0, "name": "Bronze", "color": "#CD7F32"},
    "silver": {"min_points": 5000, "discount": 5, "name": "Silver", "color": "#C0C0C0"},
    "gold": {"min_points": 15000, "discount": 10, "name": "Gold", "color": "#FFD700"},
    "platinum": {"min_points": 50000, "discount": 15, "name": "Platinum", "color": "#E5E4E2"}
}

# Points redemption rate: 100 points = £1 discount
POINTS_REDEMPTION_RATE = 100

# ============ MODELS ============

class RedeemPointsRequest(BaseModel):
    points: int
    order_id: Optional[str] = None

class LoyaltyEnrollRequest(BaseModel):
    customer_id: str
    email: str
    name: str

# ============ HELPER FUNCTIONS ============

def get_tier(total_points: int) -> dict:
    """Determine customer tier based on total points."""
    tier = TIERS["bronze"]
    for tier_name, tier_info in TIERS.items():
        if total_points >= tier_info["min_points"]:
            tier = {**tier_info, "tier_id": tier_name}
    return tier

def calculate_points_to_next_tier(total_points: int) -> dict:
    """Calculate points needed for next tier."""
    tiers_list = sorted(TIERS.items(), key=lambda x: x[1]["min_points"])
    
    for i, (tier_name, tier_info) in enumerate(tiers_list):
        if total_points < tier_info["min_points"]:
            return {
                "next_tier": tier_name,
                "points_needed": tier_info["min_points"] - total_points
            }
    
    return {"next_tier": None, "points_needed": 0}

# ============ ROUTES ============

@router.get("/account/{customer_id}")
async def get_loyalty_account(customer_id: str):
    """
    Get customer's loyalty account details.
    """
    db = get_db()
    
    account = await db.loyalty_accounts.find_one({"customer_id": customer_id}, {"_id": 0})
    
    if not account:
        return {
            "enrolled": False,
            "customer_id": customer_id
        }
    
    # Calculate tier
    total_points = account.get("lifetime_points", 0)
    current_tier = get_tier(total_points)
    next_tier_info = calculate_points_to_next_tier(total_points)
    
    return {
        "enrolled": True,
        "customer_id": customer_id,
        "current_points": account.get("current_points", 0),
        "lifetime_points": total_points,
        "tier": current_tier,
        "next_tier": next_tier_info,
        "total_redeemed": account.get("total_redeemed", 0),
        "enrolled_at": account.get("enrolled_at"),
        "last_activity": account.get("last_activity")
    }


@router.post("/enroll")
async def enroll_customer(request: LoyaltyEnrollRequest):
    """
    Enroll a customer in the loyalty program.
    """
    db = get_db()
    
    # Check if already enrolled
    existing = await db.loyalty_accounts.find_one({"customer_id": request.customer_id})
    if existing:
        raise HTTPException(status_code=400, detail="Customer already enrolled in loyalty program")
    
    # Create loyalty account
    account = {
        "id": str(uuid.uuid4()),
        "customer_id": request.customer_id,
        "email": request.email,
        "name": request.name,
        "current_points": 0,
        "lifetime_points": 0,
        "total_redeemed": 0,
        "enrolled_at": datetime.now(timezone.utc),
        "last_activity": datetime.now(timezone.utc)
    }
    
    await db.loyalty_accounts.insert_one(account)
    
    # Remove _id for response
    account.pop("_id", None)
    
    return {
        "status": "success",
        "message": "Customer enrolled in loyalty program",
        "account": account,
        "tier": TIERS["bronze"]
    }


@router.post("/earn")
async def earn_points(
    customer_id: str,
    amount: float,
    invoice_id: Optional[str] = None
):
    """
    Award points for a purchase. Usually called after invoice is created.
    """
    db = get_db()
    
    account = await db.loyalty_accounts.find_one({"customer_id": customer_id})
    if not account:
        return {"status": "not_enrolled", "points_earned": 0}
    
    # Calculate points
    points_earned = int(amount * POINTS_PER_POUND)
    
    # Update account
    await db.loyalty_accounts.update_one(
        {"customer_id": customer_id},
        {
            "$inc": {
                "current_points": points_earned,
                "lifetime_points": points_earned
            },
            "$set": {"last_activity": datetime.now(timezone.utc)}
        }
    )
    
    # Log transaction
    transaction = {
        "id": str(uuid.uuid4()),
        "customer_id": customer_id,
        "type": "earn",
        "points": points_earned,
        "amount": amount,
        "invoice_id": invoice_id,
        "created_at": datetime.now(timezone.utc)
    }
    await db.loyalty_transactions.insert_one(transaction)
    
    # Get updated account
    updated = await db.loyalty_accounts.find_one({"customer_id": customer_id})
    new_tier = get_tier(updated["lifetime_points"])
    
    return {
        "status": "success",
        "points_earned": points_earned,
        "current_points": updated["current_points"],
        "tier": new_tier
    }


@router.post("/redeem")
async def redeem_points(request: RedeemPointsRequest, current_user: dict = Depends(get_current_user)):
    """
    Redeem points for a discount.
    """
    db = get_db()
    
    customer_id = current_user.get("id") or current_user.get("customer_id")
    if not customer_id:
        raise HTTPException(status_code=401, detail="Customer authentication required")
    
    account = await db.loyalty_accounts.find_one({"customer_id": customer_id})
    if not account:
        raise HTTPException(status_code=404, detail="Loyalty account not found")
    
    if account["current_points"] < request.points:
        raise HTTPException(status_code=400, detail="Insufficient points")
    
    # Calculate discount value
    discount_value = request.points / POINTS_REDEMPTION_RATE
    
    # Update account
    await db.loyalty_accounts.update_one(
        {"customer_id": customer_id},
        {
            "$inc": {
                "current_points": -request.points,
                "total_redeemed": request.points
            },
            "$set": {"last_activity": datetime.now(timezone.utc)}
        }
    )
    
    # Log transaction
    transaction = {
        "id": str(uuid.uuid4()),
        "customer_id": customer_id,
        "type": "redeem",
        "points": -request.points,
        "discount_value": discount_value,
        "order_id": request.order_id,
        "created_at": datetime.now(timezone.utc)
    }
    await db.loyalty_transactions.insert_one(transaction)
    
    # Create redemption code
    redemption_code = f"LYL-{str(uuid.uuid4())[:8].upper()}"
    
    await db.loyalty_redemptions.insert_one({
        "code": redemption_code,
        "customer_id": customer_id,
        "points_used": request.points,
        "discount_value": discount_value,
        "used": False,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(days=30)
    })
    
    return {
        "status": "success",
        "points_redeemed": request.points,
        "discount_value": discount_value,
        "redemption_code": redemption_code,
        "remaining_points": account["current_points"] - request.points
    }


@router.get("/transactions/{customer_id}")
async def get_loyalty_transactions(
    customer_id: str,
    limit: int = Query(20, le=100)
):
    """
    Get recent loyalty transactions for a customer.
    """
    db = get_db()
    
    transactions = await db.loyalty_transactions.find(
        {"customer_id": customer_id},
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    return {"transactions": transactions}


@router.get("/recent-activity")
async def get_recent_activity(limit: int = Query(20, le=100)):
    """
    Get recent loyalty transactions across all customers (admin).
    """
    db = get_db()
    
    transactions = await db.loyalty_transactions.find(
        {},
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    return {"transactions": transactions}


@router.get("/stats")
async def get_loyalty_stats():
    """
    Get overall loyalty program statistics (admin).
    """
    db = get_db()
    
    # Total enrolled
    total_enrolled = await db.loyalty_accounts.count_documents({})
    
    # Active last 30 days
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    active_members = await db.loyalty_accounts.count_documents({
        "last_activity": {"$gte": thirty_days_ago}
    })
    
    # Points stats
    points_pipeline = [
        {"$group": {
            "_id": None,
            "total_current": {"$sum": "$current_points"},
            "total_lifetime": {"$sum": "$lifetime_points"},
            "total_redeemed": {"$sum": "$total_redeemed"}
        }}
    ]
    
    points_result = await db.loyalty_accounts.aggregate(points_pipeline).to_list(1)
    points_stats = points_result[0] if points_result else {
        "total_current": 0, "total_lifetime": 0, "total_redeemed": 0
    }
    
    # Tier distribution
    tier_distribution = []
    for tier_name, tier_info in TIERS.items():
        next_tier_threshold = float('inf')
        for t_name, t_info in TIERS.items():
            if t_info["min_points"] > tier_info["min_points"]:
                if t_info["min_points"] < next_tier_threshold:
                    next_tier_threshold = t_info["min_points"]
        
        if next_tier_threshold == float('inf'):
            query = {"lifetime_points": {"$gte": tier_info["min_points"]}}
        else:
            query = {
                "lifetime_points": {
                    "$gte": tier_info["min_points"],
                    "$lt": next_tier_threshold
                }
            }
        
        count = await db.loyalty_accounts.count_documents(query)
        tier_distribution.append({
            "tier": tier_name,
            "name": tier_info["name"],
            "count": count,
            "color": tier_info["color"]
        })
    
    return {
        "total_enrolled": total_enrolled,
        "active_members": active_members,
        "points": {
            "total_in_circulation": points_stats["total_current"],
            "total_earned": points_stats["total_lifetime"],
            "total_redeemed": points_stats["total_redeemed"]
        },
        "tier_distribution": tier_distribution,
        "points_per_pound": POINTS_PER_POUND,
        "redemption_rate": POINTS_REDEMPTION_RATE
    }


@router.post("/validate-code/{code}")
async def validate_redemption_code(code: str):
    """
    Validate a loyalty redemption code.
    """
    db = get_db()
    
    redemption = await db.loyalty_redemptions.find_one({"code": code}, {"_id": 0})
    
    if not redemption:
        raise HTTPException(status_code=404, detail="Invalid redemption code")
    
    if redemption.get("used"):
        raise HTTPException(status_code=400, detail="Code already used")
    
    if redemption.get("expires_at") and redemption["expires_at"] < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Code expired")
    
    return {
        "valid": True,
        "discount_value": redemption["discount_value"],
        "expires_at": redemption.get("expires_at")
    }


@router.post("/use-code/{code}")
async def use_redemption_code(code: str, order_id: Optional[str] = None):
    """
    Mark a redemption code as used.
    """
    db = get_db()
    
    result = await db.loyalty_redemptions.update_one(
        {"code": code, "used": False},
        {
            "$set": {
                "used": True,
                "used_at": datetime.now(timezone.utc),
                "order_id": order_id
            }
        }
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Could not use code")
    
    return {"status": "success", "message": "Code applied successfully"}

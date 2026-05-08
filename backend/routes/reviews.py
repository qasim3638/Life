"""
Customer Reviews & Ratings System
Allows verified purchasers to leave reviews for products
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from config import get_db
from routes.auth import get_current_user

router = APIRouter(prefix="/reviews", tags=["Reviews"])

# ============ MODELS ============

class ReviewCreate(BaseModel):
    product_id: str
    rating: int = Field(..., ge=1, le=5)
    title: Optional[str] = ""
    comment: str
    
class ReviewResponse(BaseModel):
    id: str
    product_id: str
    customer_id: str
    customer_name: str
    rating: int
    title: str
    comment: str
    verified_purchase: bool
    created_at: datetime
    helpful_votes: int = 0

# ============ ROUTES ============

@router.post("/create")
async def create_review(review: ReviewCreate, current_user: dict = Depends(get_current_user)):
    """
    Create a new product review. Only verified purchasers can leave reviews.
    """
    db = get_db()
    
    customer_id = current_user.get("id") or current_user.get("customer_id")
    if not customer_id:
        raise HTTPException(status_code=401, detail="Customer authentication required")
    
    # Check if user already reviewed this product
    existing = await db.reviews.find_one({
        "product_id": review.product_id,
        "customer_id": customer_id
    })
    if existing:
        raise HTTPException(status_code=400, detail="You have already reviewed this product")
    
    # Check if user has purchased this product (verified purchase)
    verified_purchase = False
    purchase_check = await db.invoices.find_one({
        "customer_id": customer_id,
        "items.product_id": review.product_id,
        "status": {"$in": ["paid", "completed", "delivered"]}
    })
    if purchase_check:
        verified_purchase = True
    
    # Also check orders for online purchases
    if not verified_purchase:
        order_check = await db.orders.find_one({
            "$or": [
                {"customer_id": customer_id},
                {"customer_email": current_user.get("email")}
            ],
            "items.product_id": review.product_id,
            "status": {"$in": ["completed", "delivered"]}
        })
        if order_check:
            verified_purchase = True
    
    review_doc = {
        "id": str(uuid.uuid4()),
        "product_id": review.product_id,
        "customer_id": customer_id,
        "customer_name": current_user.get("name", "Anonymous"),
        "rating": review.rating,
        "title": review.title or "",
        "comment": review.comment,
        "verified_purchase": verified_purchase,
        "created_at": datetime.now(timezone.utc),
        "helpful_votes": 0,
        "status": "approved" if verified_purchase else "pending"  # Auto-approve verified purchases
    }
    
    await db.reviews.insert_one(review_doc)
    
    # Update product average rating
    await update_product_rating(db, review.product_id)
    
    return {
        "status": "success",
        "message": "Review submitted" + (" and approved" if verified_purchase else " for moderation"),
        "review_id": review_doc["id"],
        "verified_purchase": verified_purchase
    }


@router.get("/product/{product_id}")
async def get_product_reviews(
    product_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(10, le=50),
    sort: str = Query("recent", enum=["recent", "helpful", "rating_high", "rating_low"])
):
    """
    Get reviews for a specific product.
    """
    db = get_db()
    
    # Build sort
    sort_map = {
        "recent": [("created_at", -1)],
        "helpful": [("helpful_votes", -1), ("created_at", -1)],
        "rating_high": [("rating", -1), ("created_at", -1)],
        "rating_low": [("rating", 1), ("created_at", -1)]
    }
    sort_spec = sort_map.get(sort, [("created_at", -1)])
    
    skip = (page - 1) * limit
    
    # Only show approved reviews publicly
    query = {
        "product_id": product_id,
        "status": "approved"
    }
    
    reviews = await db.reviews.find(query, {"_id": 0}).sort(sort_spec).skip(skip).limit(limit).to_list(limit)
    total = await db.reviews.count_documents(query)
    
    # Calculate rating breakdown
    rating_pipeline = [
        {"$match": query},
        {"$group": {
            "_id": "$rating",
            "count": {"$sum": 1}
        }}
    ]
    rating_breakdown_raw = await db.reviews.aggregate(rating_pipeline).to_list(5)
    rating_breakdown = {str(r["_id"]): r["count"] for r in rating_breakdown_raw}
    
    # Calculate average rating
    avg_pipeline = [
        {"$match": query},
        {"$group": {
            "_id": None,
            "average": {"$avg": "$rating"},
            "total": {"$sum": 1}
        }}
    ]
    avg_result = await db.reviews.aggregate(avg_pipeline).to_list(1)
    average_rating = round(avg_result[0]["average"], 1) if avg_result else 0
    
    return {
        "reviews": reviews,
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit,
        "average_rating": average_rating,
        "rating_breakdown": {
            "5": rating_breakdown.get("5", 0),
            "4": rating_breakdown.get("4", 0),
            "3": rating_breakdown.get("3", 0),
            "2": rating_breakdown.get("2", 0),
            "1": rating_breakdown.get("1", 0)
        }
    }


@router.get("/summary/{product_id}")
async def get_review_summary(product_id: str):
    """
    Get review summary (average rating, total reviews) for a product.
    """
    db = get_db()
    
    query = {"product_id": product_id, "status": "approved"}
    
    pipeline = [
        {"$match": query},
        {"$group": {
            "_id": None,
            "average_rating": {"$avg": "$rating"},
            "total_reviews": {"$sum": 1},
            "verified_count": {"$sum": {"$cond": ["$verified_purchase", 1, 0]}}
        }}
    ]
    
    result = await db.reviews.aggregate(pipeline).to_list(1)
    
    if not result:
        return {
            "product_id": product_id,
            "average_rating": 0,
            "total_reviews": 0,
            "verified_count": 0
        }
    
    return {
        "product_id": product_id,
        "average_rating": round(result[0]["average_rating"], 1),
        "total_reviews": result[0]["total_reviews"],
        "verified_count": result[0]["verified_count"]
    }


@router.post("/{review_id}/helpful")
async def mark_review_helpful(review_id: str):
    """
    Mark a review as helpful (upvote).
    """
    db = get_db()
    
    result = await db.reviews.update_one(
        {"id": review_id},
        {"$inc": {"helpful_votes": 1}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Review not found")
    
    return {"status": "success", "message": "Marked as helpful"}


@router.get("/can-review/{product_id}")
async def can_user_review(product_id: str, current_user: dict = Depends(get_current_user)):
    """
    Check if current user can review a product.
    """
    db = get_db()
    
    customer_id = current_user.get("id") or current_user.get("customer_id")
    if not customer_id:
        return {"can_review": False, "reason": "Not logged in"}
    
    # Check if already reviewed
    existing = await db.reviews.find_one({
        "product_id": product_id,
        "customer_id": customer_id
    })
    if existing:
        return {"can_review": False, "reason": "Already reviewed"}
    
    # Check if purchased
    purchase = await db.invoices.find_one({
        "customer_id": customer_id,
        "items.product_id": product_id,
        "status": {"$in": ["paid", "completed", "delivered"]}
    })
    
    if purchase:
        return {"can_review": True, "verified_purchase": True}
    
    # Check orders
    order = await db.orders.find_one({
        "$or": [
            {"customer_id": customer_id},
            {"customer_email": current_user.get("email")}
        ],
        "items.product_id": product_id,
        "status": {"$in": ["completed", "delivered"]}
    })
    
    if order:
        return {"can_review": True, "verified_purchase": True}
    
    # Anyone can review but won't be verified
    return {"can_review": True, "verified_purchase": False}


# ============ HELPER FUNCTIONS ============

async def update_product_rating(db, product_id: str):
    """
    Update the average rating on a product document.
    """
    pipeline = [
        {"$match": {"product_id": product_id, "status": "approved"}},
        {"$group": {
            "_id": None,
            "average": {"$avg": "$rating"},
            "count": {"$sum": 1}
        }}
    ]
    
    result = await db.reviews.aggregate(pipeline).to_list(1)
    
    if result:
        await db.products.update_one(
            {"id": product_id},
            {"$set": {
                "average_rating": round(result[0]["average"], 1),
                "review_count": result[0]["count"]
            }}
        )

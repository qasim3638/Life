"""
Staff Performance Analytics
Tracks sales, conversions, and performance metrics per staff member
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from fastapi import APIRouter, Query

from config import get_db

router = APIRouter(prefix="/staff-performance", tags=["Staff Performance"])

# ============ ROUTES ============

@router.get("/overview")
async def get_staff_overview(
    days: int = Query(30, description="Number of days to analyze"),
    showroom_id: Optional[str] = Query(None, description="Filter by showroom")
):
    """
    Get overview of all staff performance metrics.
    """
    db = get_db()
    
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Build match query
    match_query = {"created_at": {"$gte": cutoff_date}}
    if showroom_id:
        match_query["showroom_id"] = showroom_id
    
    # Aggregate invoices by staff
    pipeline = [
        {"$match": match_query},
        {"$group": {
            "_id": "$sales_person",
            "total_invoices": {"$sum": 1},
            "total_revenue": {"$sum": "$total"},
            "total_items": {"$sum": {"$size": {"$ifNull": ["$items", []]}}},
            "avg_invoice_value": {"$avg": "$total"},
            "showrooms": {"$addToSet": "$showroom_id"}
        }},
        {"$sort": {"total_revenue": -1}}
    ]
    
    invoice_stats = await db.invoices.aggregate(pipeline).to_list(100)
    
    # Get quotation stats per staff
    quote_pipeline = [
        {"$match": match_query},
        {"$group": {
            "_id": "$sales_person",
            "total_quotations": {"$sum": 1},
            "quotation_value": {"$sum": "$total"},
            "converted": {
                "$sum": {
                    "$cond": [
                        {"$and": [
                            {"$ne": ["$converted_to_invoice", None]},
                            {"$ne": ["$converted_to_invoice", ""]}
                        ]},
                        1, 0
                    ]
                }
            }
        }}
    ]
    
    quote_stats = await db.quotations.aggregate(quote_pipeline).to_list(100)
    quote_map = {q["_id"]: q for q in quote_stats}
    
    # Combine data
    staff_data = []
    for inv in invoice_stats:
        staff_name = inv["_id"] or "Unknown"
        quote_data = quote_map.get(staff_name, {})
        
        total_quotes = quote_data.get("total_quotations", 0)
        converted = quote_data.get("converted", 0)
        conversion_rate = (converted / total_quotes * 100) if total_quotes > 0 else 0
        
        staff_data.append({
            "staff_name": staff_name,
            "total_invoices": inv["total_invoices"],
            "total_revenue": round(inv["total_revenue"] or 0, 2),
            "avg_invoice_value": round(inv["avg_invoice_value"] or 0, 2),
            "total_items_sold": inv["total_items"],
            "total_quotations": total_quotes,
            "quotation_value": round(quote_data.get("quotation_value", 0) or 0, 2),
            "converted_quotations": converted,
            "conversion_rate": round(conversion_rate, 1),
            "showrooms": inv["showrooms"]
        })
    
    # Calculate totals
    total_revenue = sum(s["total_revenue"] for s in staff_data)
    total_invoices = sum(s["total_invoices"] for s in staff_data)
    
    return {
        "period_days": days,
        "staff": staff_data,
        "totals": {
            "total_staff": len(staff_data),
            "total_revenue": round(total_revenue, 2),
            "total_invoices": total_invoices,
            "avg_per_staff": round(total_revenue / len(staff_data), 2) if staff_data else 0
        }
    }


@router.get("/individual/{staff_name}")
async def get_staff_individual(
    staff_name: str,
    days: int = Query(30, description="Number of days to analyze")
):
    """
    Get detailed performance metrics for a specific staff member.
    """
    db = get_db()
    
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Daily revenue trend
    daily_pipeline = [
        {"$match": {
            "sales_person": staff_name,
            "created_at": {"$gte": cutoff_date}
        }},
        {"$group": {
            "_id": {
                "$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}
            },
            "revenue": {"$sum": "$total"},
            "invoices": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]
    
    daily_data = await db.invoices.aggregate(daily_pipeline).to_list(days)
    
    # Top products sold by this staff
    product_pipeline = [
        {"$match": {
            "sales_person": staff_name,
            "created_at": {"$gte": cutoff_date}
        }},
        {"$unwind": "$items"},
        {"$group": {
            "_id": "$items.name",
            "quantity": {"$sum": "$items.quantity"},
            "revenue": {"$sum": {"$multiply": ["$items.quantity", "$items.price"]}}
        }},
        {"$sort": {"revenue": -1}},
        {"$limit": 10}
    ]
    
    top_products = await db.invoices.aggregate(product_pipeline).to_list(10)
    
    # Recent invoices
    recent_invoices = await db.invoices.find(
        {"sales_person": staff_name, "created_at": {"$gte": cutoff_date}},
        {"_id": 0, "id": 1, "invoice_no": 1, "total": 1, "created_at": 1, "customer_name": 1}
    ).sort("created_at", -1).limit(10).to_list(10)
    
    # Calculate streaks and achievements
    total_revenue = sum(d["revenue"] for d in daily_data)
    best_day = max(daily_data, key=lambda x: x["revenue"]) if daily_data else None
    
    return {
        "staff_name": staff_name,
        "period_days": days,
        "daily_trend": daily_data,
        "top_products": [
            {"name": p["_id"], "quantity": p["quantity"], "revenue": round(p["revenue"], 2)}
            for p in top_products
        ],
        "recent_invoices": recent_invoices,
        "summary": {
            "total_revenue": round(total_revenue, 2),
            "total_invoices": sum(d["invoices"] for d in daily_data),
            "best_day": {
                "date": best_day["_id"] if best_day else None,
                "revenue": round(best_day["revenue"], 2) if best_day else 0
            },
            "avg_daily_revenue": round(total_revenue / len(daily_data), 2) if daily_data else 0
        }
    }


@router.get("/leaderboard")
async def get_staff_leaderboard(
    period: str = Query("month", enum=["day", "week", "month", "year"]),
    showroom_id: Optional[str] = Query(None, description="Filter by showroom"),
    metric: str = Query("revenue", enum=["revenue", "invoices", "conversion"])
):
    """
    Get staff leaderboard for gamification.
    """
    db = get_db()
    
    # Calculate date range
    now = datetime.now(timezone.utc)
    if period == "day":
        cutoff_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        cutoff_date = now - timedelta(days=now.weekday())
        cutoff_date = cutoff_date.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "month":
        cutoff_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:  # year
        cutoff_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    
    match_query = {"created_at": {"$gte": cutoff_date}}
    if showroom_id:
        match_query["showroom_id"] = showroom_id
    
    # Get invoice stats
    pipeline = [
        {"$match": match_query},
        {"$group": {
            "_id": "$sales_person",
            "revenue": {"$sum": "$total"},
            "invoices": {"$sum": 1}
        }}
    ]
    
    invoice_data = await db.invoices.aggregate(pipeline).to_list(100)
    
    # Get conversion data if needed
    conversion_map = {}
    if metric == "conversion":
        conv_pipeline = [
            {"$match": match_query},
            {"$group": {
                "_id": "$sales_person",
                "total": {"$sum": 1},
                "converted": {
                    "$sum": {"$cond": [{"$ne": ["$converted_to_invoice", None]}, 1, 0]}
                }
            }}
        ]
        conv_data = await db.quotations.aggregate(conv_pipeline).to_list(100)
        conversion_map = {c["_id"]: (c["converted"] / c["total"] * 100) if c["total"] > 0 else 0 for c in conv_data}
    
    # Build leaderboard
    leaderboard = []
    for inv in invoice_data:
        staff_name = inv["_id"] or "Unknown"
        score = 0
        
        if metric == "revenue":
            score = inv["revenue"] or 0
        elif metric == "invoices":
            score = inv["invoices"]
        elif metric == "conversion":
            score = conversion_map.get(staff_name, 0)
        
        leaderboard.append({
            "staff_name": staff_name,
            "score": round(score, 2) if metric != "invoices" else score,
            "revenue": round(inv["revenue"] or 0, 2),
            "invoices": inv["invoices"]
        })
    
    # Sort by score
    leaderboard.sort(key=lambda x: x["score"], reverse=True)
    
    # Add rank and badges
    for i, entry in enumerate(leaderboard):
        entry["rank"] = i + 1
        if i == 0:
            entry["badge"] = "🥇"
        elif i == 1:
            entry["badge"] = "🥈"
        elif i == 2:
            entry["badge"] = "🥉"
        else:
            entry["badge"] = None
    
    return {
        "period": period,
        "metric": metric,
        "leaderboard": leaderboard,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }


@router.get("/targets/{staff_name}")
async def get_staff_targets(
    staff_name: str,
    month: int = Query(None),
    year: int = Query(None)
):
    """
    Get targets and progress for a specific staff member.
    """
    db = get_db()
    
    now = datetime.now(timezone.utc)
    target_month = month or now.month
    target_year = year or now.year
    
    # Get staff target
    target = await db.staff_targets.find_one({
        "staff_name": staff_name,
        "month": target_month,
        "year": target_year
    })
    
    if not target:
        return {
            "staff_name": staff_name,
            "has_target": False,
            "month": target_month,
            "year": target_year
        }
    
    # Calculate current progress
    start_date = datetime(target_year, target_month, 1, tzinfo=timezone.utc)
    if target_month == 12:
        end_date = datetime(target_year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end_date = datetime(target_year, target_month + 1, 1, tzinfo=timezone.utc)
    
    revenue_pipeline = [
        {"$match": {
            "sales_person": staff_name,
            "created_at": {"$gte": start_date, "$lt": end_date}
        }},
        {"$group": {
            "_id": None,
            "total": {"$sum": "$total"},
            "count": {"$sum": 1}
        }}
    ]
    
    result = await db.invoices.aggregate(revenue_pipeline).to_list(1)
    current_revenue = result[0]["total"] if result else 0
    current_invoices = result[0]["count"] if result else 0
    
    monthly_target = target.get("monthly_target", 0)
    progress = (current_revenue / monthly_target * 100) if monthly_target > 0 else 0
    
    return {
        "staff_name": staff_name,
        "has_target": True,
        "month": target_month,
        "year": target_year,
        "monthly_target": monthly_target,
        "current_revenue": round(current_revenue, 2),
        "current_invoices": current_invoices,
        "progress": round(progress, 1),
        "remaining": round(max(0, monthly_target - current_revenue), 2),
        "on_track": progress >= (now.day / 30 * 100)  # Simple on-track calculation
    }

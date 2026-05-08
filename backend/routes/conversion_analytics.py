"""
Quote to Invoice Conversion Analytics
Tracks how many quotations convert to invoices
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Query

from config import get_db

router = APIRouter(prefix="/conversion-analytics", tags=["Conversion Analytics"])

# ============ ROUTES ============

@router.get("/quote-to-invoice")
async def get_quote_conversion_stats(
    days: int = Query(30, description="Number of days to analyze"),
    showroom_id: Optional[str] = Query(None, description="Filter by showroom")
):
    """
    Get quotation to invoice conversion statistics.
    """
    db = get_db()
    
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Build match query
    quotation_match = {"created_at": {"$gte": cutoff_date}}
    invoice_match = {"created_at": {"$gte": cutoff_date}}
    
    if showroom_id:
        quotation_match["showroom_id"] = showroom_id
        invoice_match["showroom_id"] = showroom_id
    
    # Count quotations
    total_quotations = await db.quotations.count_documents(quotation_match)
    
    # Count quotations that converted to invoices (have converted_to_invoice field)
    converted_quotations = await db.quotations.count_documents({
        **quotation_match,
        "converted_to_invoice": {"$exists": True, "$ne": None}
    })
    
    # Also check invoices created from quotations
    invoices_from_quotes = await db.invoices.count_documents({
        **invoice_match,
        "from_quotation": {"$exists": True, "$ne": None}
    })
    
    # Total invoices in period
    total_invoices = await db.invoices.count_documents(invoice_match)
    
    # Calculate values
    quotation_value_pipeline = [
        {"$match": quotation_match},
        {"$group": {"_id": None, "total": {"$sum": "$total"}}}
    ]
    quotation_value_result = await db.quotations.aggregate(quotation_value_pipeline).to_list(1)
    total_quotation_value = quotation_value_result[0]["total"] if quotation_value_result else 0
    
    # Converted value
    converted_value_pipeline = [
        {"$match": {**quotation_match, "converted_to_invoice": {"$exists": True, "$ne": None}}},
        {"$group": {"_id": None, "total": {"$sum": "$total"}}}
    ]
    converted_value_result = await db.quotations.aggregate(converted_value_pipeline).to_list(1)
    converted_value = converted_value_result[0]["total"] if converted_value_result else 0
    
    # Calculate conversion rate
    conversion_rate = (converted_quotations / total_quotations * 100) if total_quotations > 0 else 0
    value_conversion_rate = (converted_value / total_quotation_value * 100) if total_quotation_value > 0 else 0
    
    # Get trend data (by week)
    weeks_data = []
    for week in range(4):
        week_start = datetime.now(timezone.utc) - timedelta(days=(week + 1) * 7)
        week_end = datetime.now(timezone.utc) - timedelta(days=week * 7)
        
        week_match = {
            "created_at": {"$gte": week_start, "$lt": week_end}
        }
        if showroom_id:
            week_match["showroom_id"] = showroom_id
        
        week_quotes = await db.quotations.count_documents(week_match)
        week_converted = await db.quotations.count_documents({
            **week_match,
            "converted_to_invoice": {"$exists": True, "$ne": None}
        })
        
        week_rate = (week_converted / week_quotes * 100) if week_quotes > 0 else 0
        
        weeks_data.append({
            "week": f"Week {4 - week}",
            "quotations": week_quotes,
            "converted": week_converted,
            "rate": round(week_rate, 1)
        })
    
    weeks_data.reverse()
    
    return {
        "period_days": days,
        "total_quotations": total_quotations,
        "converted_quotations": converted_quotations,
        "conversion_rate": round(conversion_rate, 1),
        "total_quotation_value": round(total_quotation_value or 0, 2),
        "converted_value": round(converted_value or 0, 2),
        "value_conversion_rate": round(value_conversion_rate, 1),
        "total_invoices": total_invoices,
        "invoices_from_quotes": invoices_from_quotes,
        "weekly_trend": weeks_data,
        "lost_opportunity": round((total_quotation_value or 0) - (converted_value or 0), 2)
    }


@router.get("/unconverted-quotations")
async def get_unconverted_quotations(
    days: int = Query(30, description="Look back period"),
    min_value: float = Query(0, description="Minimum quotation value"),
    limit: int = Query(20, description="Max results"),
    showroom_id: Optional[str] = Query(None, description="Filter by showroom")
):
    """
    Get list of high-value unconverted quotations for follow-up.
    """
    db = get_db()
    
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    query = {
        "created_at": {"$gte": cutoff_date},
        "$or": [
            {"converted_to_invoice": {"$exists": False}},
            {"converted_to_invoice": None}
        ],
        "total": {"$gte": min_value}
    }
    
    if showroom_id:
        query["showroom_id"] = showroom_id
    
    quotations = await db.quotations.find(
        query,
        {"_id": 0}
    ).sort("total", -1).limit(limit).to_list(limit)
    
    # Calculate days since created
    for q in quotations:
        if q.get("created_at"):
            days_old = (datetime.now(timezone.utc) - q["created_at"]).days
            q["days_since_created"] = days_old
            q["urgency"] = "high" if days_old > 14 else ("medium" if days_old > 7 else "low")
    
    return {
        "quotations": quotations,
        "total_value": sum(q.get("total", 0) for q in quotations),
        "count": len(quotations)
    }


@router.get("/conversion-by-staff")
async def get_conversion_by_staff(
    days: int = Query(30, description="Number of days to analyze"),
    showroom_id: Optional[str] = Query(None, description="Filter by showroom")
):
    """
    Get conversion rates broken down by sales staff.
    """
    db = get_db()
    
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    match_stage = {"created_at": {"$gte": cutoff_date}}
    if showroom_id:
        match_stage["showroom_id"] = showroom_id
    
    # Aggregate by staff
    pipeline = [
        {"$match": match_stage},
        {"$group": {
            "_id": "$sales_person",
            "total_quotations": {"$sum": 1},
            "total_value": {"$sum": "$total"},
            "converted": {
                "$sum": {
                    "$cond": [
                        {"$and": [
                            {"$ne": ["$converted_to_invoice", None]},
                            {"$ne": ["$converted_to_invoice", ""]}
                        ]},
                        1,
                        0
                    ]
                }
            },
            "converted_value": {
                "$sum": {
                    "$cond": [
                        {"$and": [
                            {"$ne": ["$converted_to_invoice", None]},
                            {"$ne": ["$converted_to_invoice", ""]}
                        ]},
                        "$total",
                        0
                    ]
                }
            }
        }},
        {"$project": {
            "staff_name": "$_id",
            "total_quotations": 1,
            "total_value": 1,
            "converted": 1,
            "converted_value": 1,
            "conversion_rate": {
                "$cond": [
                    {"$gt": ["$total_quotations", 0]},
                    {"$multiply": [{"$divide": ["$converted", "$total_quotations"]}, 100]},
                    0
                ]
            }
        }},
        {"$sort": {"conversion_rate": -1}}
    ]
    
    results = await db.quotations.aggregate(pipeline).to_list(100)
    
    # Clean up results
    for r in results:
        r["conversion_rate"] = round(r.get("conversion_rate", 0), 1)
        r["total_value"] = round(r.get("total_value", 0) or 0, 2)
        r["converted_value"] = round(r.get("converted_value", 0) or 0, 2)
        r.pop("_id", None)
    
    return results


@router.get("/average-conversion-time")
async def get_average_conversion_time(
    days: int = Query(90, description="Number of days to analyze"),
    showroom_id: Optional[str] = Query(None, description="Filter by showroom")
):
    """
    Calculate average time from quotation to invoice conversion.
    """
    db = get_db()
    
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    match_stage = {
        "created_at": {"$gte": cutoff_date},
        "converted_to_invoice": {"$exists": True, "$ne": None},
        "converted_at": {"$exists": True}
    }
    
    if showroom_id:
        match_stage["showroom_id"] = showroom_id
    
    quotations = await db.quotations.find(match_stage).to_list(1000)
    
    if not quotations:
        return {
            "average_days": 0,
            "median_days": 0,
            "fastest_conversion": 0,
            "slowest_conversion": 0,
            "sample_size": 0
        }
    
    conversion_times = []
    for q in quotations:
        if q.get("created_at") and q.get("converted_at"):
            diff = (q["converted_at"] - q["created_at"]).days
            conversion_times.append(diff)
    
    if not conversion_times:
        return {
            "average_days": 0,
            "median_days": 0,
            "fastest_conversion": 0,
            "slowest_conversion": 0,
            "sample_size": 0
        }
    
    conversion_times.sort()
    median_idx = len(conversion_times) // 2
    
    return {
        "average_days": round(sum(conversion_times) / len(conversion_times), 1),
        "median_days": conversion_times[median_idx],
        "fastest_conversion": min(conversion_times),
        "slowest_conversion": max(conversion_times),
        "sample_size": len(conversion_times),
        "distribution": {
            "same_day": len([t for t in conversion_times if t == 0]),
            "within_week": len([t for t in conversion_times if 1 <= t <= 7]),
            "within_month": len([t for t in conversion_times if 8 <= t <= 30]),
            "over_month": len([t for t in conversion_times if t > 30])
        }
    }

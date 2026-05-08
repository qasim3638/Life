"""
Smart Reorder Suggestions - AI-based inventory reorder recommendations
Analyzes sales velocity, seasonality, and stock levels to suggest reorders
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from config import get_db

router = APIRouter(prefix="/reorder-suggestions", tags=["Reorder Suggestions"])


class ReorderSuggestion(BaseModel):
    product_id: str
    sku: str
    name: str
    current_stock: int
    avg_daily_sales: float
    days_of_stock_remaining: int
    suggested_order_qty: int
    urgency: str  # critical, high, medium, low
    reason: str
    supplier: Optional[str] = None
    last_order_date: Optional[str] = None
    cost_price: Optional[float] = None
    estimated_order_value: Optional[float] = None


@router.get("/analyze")
async def get_reorder_suggestions(
    days_lookback: int = Query(30, description="Days of sales history to analyze"),
    min_sales: int = Query(1, description="Minimum sales to consider"),
    stock_days_threshold: int = Query(14, description="Suggest reorder if stock covers less than X days"),
    showroom_id: Optional[str] = None,
    category: Optional[str] = None,
    supplier: Optional[str] = None,
    limit: int = Query(50, le=200)
):
    """
    Analyze inventory and suggest products that need reordering based on:
    - Current stock levels
    - Average daily sales velocity
    - Days of stock remaining
    - Historical order patterns
    """
    db = get_db()
    
    # Calculate date range for sales analysis
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days_lookback)
    
    # Build invoice query
    invoice_query = {
        "created_at": {"$gte": start_date.isoformat()}
    }
    if showroom_id:
        invoice_query["showroom_id"] = showroom_id
    
    # Get all invoices in the period
    invoices = await db.invoices.find(invoice_query).to_list(None)
    
    # Aggregate sales by product
    product_sales = {}
    for invoice in invoices:
        for item in invoice.get("items", []):
            product_id = item.get("product_id")
            if not product_id:
                continue
            
            qty = float(item.get("quantity", 0) or item.get("qty", 0) or 0)
            if product_id not in product_sales:
                product_sales[product_id] = {
                    "total_qty": 0,
                    "total_revenue": 0,
                    "order_count": 0,
                    "sku": item.get("sku", ""),
                    "name": item.get("product_name", item.get("name", ""))
                }
            
            product_sales[product_id]["total_qty"] += qty
            product_sales[product_id]["total_revenue"] += float(item.get("total", 0) or 0)
            product_sales[product_id]["order_count"] += 1
    
    # Get current stock levels for products with sales
    product_ids = list(product_sales.keys())
    
    # Build product query
    product_query = {"id": {"$in": product_ids}}
    if category:
        product_query["category"] = category
    if supplier:
        product_query["supplier"] = supplier
    
    products = await db.products.find(product_query, {"_id": 0}).to_list(None)
    
    # Also check supplier_products
    supplier_products = await db.supplier_products.find(
        {"id": {"$in": product_ids}},
        {"_id": 0}
    ).to_list(None)
    
    # Merge product data
    product_map = {p["id"]: p for p in products}
    for sp in supplier_products:
        if sp["id"] not in product_map:
            product_map[sp["id"]] = sp
    
    # Generate suggestions
    suggestions = []
    
    for product_id, sales_data in product_sales.items():
        if sales_data["total_qty"] < min_sales:
            continue
        
        product = product_map.get(product_id, {})
        
        # Get stock - check showroom-specific if provided
        if showroom_id and product.get("showroom_stock"):
            current_stock = product["showroom_stock"].get(showroom_id, 0)
        else:
            current_stock = product.get("stock", 0)
        
        # Calculate metrics
        avg_daily_sales = sales_data["total_qty"] / days_lookback
        
        if avg_daily_sales > 0:
            days_of_stock = int(current_stock / avg_daily_sales)
        else:
            days_of_stock = 999  # Effectively infinite
        
        # Determine urgency
        if days_of_stock <= 3:
            urgency = "critical"
            reason = f"Only {days_of_stock} days of stock remaining at current sales rate"
        elif days_of_stock <= 7:
            urgency = "high"
            reason = f"Stock will run out in about a week ({days_of_stock} days)"
        elif days_of_stock <= stock_days_threshold:
            urgency = "medium"
            reason = f"Stock below {stock_days_threshold}-day threshold ({days_of_stock} days remaining)"
        else:
            continue  # Skip products with sufficient stock
        
        # Calculate suggested order quantity (2 weeks of stock + buffer)
        suggested_qty = max(1, int(avg_daily_sales * 30))  # 30 days of stock
        
        # Get cost price if available
        cost_price = product.get("cost_price") or product.get("cost")
        estimated_value = cost_price * suggested_qty if cost_price else None
        
        suggestions.append({
            "product_id": product_id,
            "sku": product.get("sku", sales_data["sku"]),
            "name": product.get("name", sales_data["name"]),
            "current_stock": current_stock,
            "avg_daily_sales": round(avg_daily_sales, 2),
            "days_of_stock_remaining": days_of_stock,
            "suggested_order_qty": suggested_qty,
            "urgency": urgency,
            "reason": reason,
            "supplier": product.get("supplier"),
            "cost_price": cost_price,
            "estimated_order_value": round(estimated_value, 2) if estimated_value else None,
            "sales_last_30_days": sales_data["total_qty"],
            "revenue_last_30_days": round(sales_data["total_revenue"], 2)
        })
    
    # Sort by urgency (critical first) then by days remaining
    urgency_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    suggestions.sort(key=lambda x: (urgency_order.get(x["urgency"], 4), x["days_of_stock_remaining"]))
    
    # Calculate summary stats
    critical_count = sum(1 for s in suggestions if s["urgency"] == "critical")
    high_count = sum(1 for s in suggestions if s["urgency"] == "high")
    total_order_value = sum(s["estimated_order_value"] or 0 for s in suggestions)
    
    return {
        "suggestions": suggestions[:limit],
        "summary": {
            "total_products_analyzed": len(product_sales),
            "products_needing_reorder": len(suggestions),
            "critical_items": critical_count,
            "high_priority_items": high_count,
            "estimated_total_order_value": round(total_order_value, 2),
            "analysis_period_days": days_lookback
        },
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


@router.get("/top-sellers")
async def get_top_sellers(
    days: int = Query(30, description="Days to analyze"),
    limit: int = Query(20, le=100),
    showroom_id: Optional[str] = None
):
    """Get top selling products to help with reorder decisions"""
    db = get_db()
    
    start_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    query = {"created_at": {"$gte": start_date.isoformat()}}
    if showroom_id:
        query["showroom_id"] = showroom_id
    
    invoices = await db.invoices.find(query).to_list(None)
    
    # Aggregate by product
    product_totals = {}
    for invoice in invoices:
        for item in invoice.get("items", []):
            product_id = item.get("product_id")
            if not product_id:
                continue
            
            if product_id not in product_totals:
                product_totals[product_id] = {
                    "sku": item.get("sku", ""),
                    "name": item.get("product_name", item.get("name", "")),
                    "total_qty": 0,
                    "total_revenue": 0,
                    "order_count": 0
                }
            
            product_totals[product_id]["total_qty"] += float(item.get("quantity", 0) or item.get("qty", 0) or 0)
            product_totals[product_id]["total_revenue"] += float(item.get("total", 0) or 0)
            product_totals[product_id]["order_count"] += 1
    
    # Sort by quantity sold
    sorted_products = sorted(
        product_totals.items(),
        key=lambda x: x[1]["total_qty"],
        reverse=True
    )[:limit]
    
    return {
        "top_sellers": [
            {
                "product_id": pid,
                "sku": data["sku"],
                "name": data["name"],
                "quantity_sold": data["total_qty"],
                "revenue": round(data["total_revenue"], 2),
                "order_count": data["order_count"],
                "avg_qty_per_order": round(data["total_qty"] / data["order_count"], 2) if data["order_count"] > 0 else 0
            }
            for pid, data in sorted_products
        ],
        "period_days": days,
        "showroom_id": showroom_id
    }


@router.get("/slow-movers")
async def get_slow_moving_products(
    days: int = Query(90, description="Days without sales to be considered slow"),
    min_stock: int = Query(5, description="Minimum stock to include"),
    limit: int = Query(50, le=200)
):
    """Identify slow-moving products that might need clearance"""
    db = get_db()
    
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Get all invoices in the period
    invoices = await db.invoices.find({
        "created_at": {"$gte": cutoff_date.isoformat()}
    }).to_list(None)
    
    # Get product IDs that have sold
    sold_product_ids = set()
    for invoice in invoices:
        for item in invoice.get("items", []):
            if item.get("product_id"):
                sold_product_ids.add(item["product_id"])
    
    # Find products with stock but no sales
    slow_movers = await db.products.find({
        "id": {"$nin": list(sold_product_ids)},
        "stock": {"$gte": min_stock}
    }, {"_id": 0}).sort("stock", -1).limit(limit).to_list(limit)
    
    return {
        "slow_moving_products": [
            {
                "product_id": p.get("id"),
                "sku": p.get("sku"),
                "name": p.get("name"),
                "stock": p.get("stock", 0),
                "cost_price": p.get("cost_price") or p.get("cost"),
                "sell_price": p.get("price"),
                "days_without_sale": days,
                "stock_value": round((p.get("cost_price") or p.get("cost") or 0) * p.get("stock", 0), 2)
            }
            for p in slow_movers
        ],
        "analysis_period_days": days,
        "total_found": len(slow_movers)
    }

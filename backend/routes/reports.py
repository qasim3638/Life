"""
Stock Cost Reports routes
"""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends

from config import get_db
from services import get_current_user, is_admin_user

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/stock-cost")
async def get_stock_cost_report(
    current_user: dict = Depends(get_current_user)
):
    """
    Get total stock cost report with breakdown by showroom and grand total.
    
    Returns:
    - Per showroom: total cost value of stock allocated to each showroom
    - Unallocated: cost value of stock not allocated to any showroom
    - Grand total: combined cost value across all stock
    """
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    db = get_db()
    
    # Get all showrooms
    showrooms = await db.showrooms.find({}, {"_id": 0}).to_list(1000)
    showroom_map = {s["id"]: s["name"] for s in showrooms}
    
    # Get all products with cost and stock info
    products = await db.products.find(
        {}, 
        {"_id": 0, "id": 1, "name": 1, "sku": 1, "cost_price": 1, "stock": 1, "showroom_stock": 1}
    ).to_list(100000)
    
    # Initialize showroom cost data
    showroom_costs = {}
    for showroom in showrooms:
        showroom_costs[showroom["id"]] = {
            "showroom_id": showroom["id"],
            "showroom_name": showroom["name"],
            "total_cost": 0,
            "total_quantity": 0,
            "product_count": 0,
            "products_with_cost": 0
        }
    
    # Track unallocated stock
    unallocated = {
        "total_cost": 0,
        "total_quantity": 0,
        "product_count": 0,
        "products_with_cost": 0
    }
    
    # Grand totals
    grand_total_cost = 0
    grand_total_quantity = 0
    total_products = 0
    products_with_cost = 0
    products_without_cost = 0
    
    # Process each product
    for product in products:
        cost_price = product.get("cost_price", 0) or 0
        total_stock = product.get("stock", 0) or 0
        showroom_stock = product.get("showroom_stock", {}) or {}
        
        has_cost = cost_price > 0
        if has_cost:
            products_with_cost += 1
        else:
            products_without_cost += 1
        
        total_products += 1
        
        # Calculate allocated stock per showroom
        total_allocated = 0
        for showroom_id, qty in showroom_stock.items():
            if showroom_id in showroom_costs and qty > 0:
                item_cost = qty * cost_price
                showroom_costs[showroom_id]["total_cost"] += item_cost
                showroom_costs[showroom_id]["total_quantity"] += qty
                showroom_costs[showroom_id]["product_count"] += 1
                if has_cost:
                    showroom_costs[showroom_id]["products_with_cost"] += 1
                total_allocated += qty
                grand_total_cost += item_cost
                grand_total_quantity += qty
        
        # Calculate unallocated stock
        unallocated_qty = max(0, total_stock - total_allocated)
        if unallocated_qty > 0:
            unallocated_cost = unallocated_qty * cost_price
            unallocated["total_cost"] += unallocated_cost
            unallocated["total_quantity"] += unallocated_qty
            unallocated["product_count"] += 1
            if has_cost:
                unallocated["products_with_cost"] += 1
            grand_total_cost += unallocated_cost
            grand_total_quantity += unallocated_qty
    
    # Convert showroom costs to list and sort by total cost
    showroom_list = sorted(
        showroom_costs.values(),
        key=lambda x: x["total_cost"],
        reverse=True
    )
    
    # Round all monetary values
    for item in showroom_list:
        item["total_cost"] = round(item["total_cost"], 2)
    
    unallocated["total_cost"] = round(unallocated["total_cost"], 2)
    
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "showroom_breakdown": showroom_list,
        "unallocated": unallocated,
        "grand_total": {
            "total_cost": round(grand_total_cost, 2),
            "total_quantity": grand_total_quantity,
            "total_products": total_products,
            "products_with_cost": products_with_cost,
            "products_without_cost": products_without_cost
        },
        "notes": "Cost values are calculated as: quantity × cost_price. Products without cost prices are included in quantity counts but contribute £0 to cost totals."
    }

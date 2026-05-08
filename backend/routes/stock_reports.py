"""
Stock Reports API - Low Stock / To Order Reports
"""
import csv
import io
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config import get_db
from services import get_current_user, require_admin_access, log_audit

router = APIRouter(tags=["Stock Reports"])

# Supported suppliers for ordering
ORDERING_SUPPLIERS = ["Tile Rite", "Ultra Tile", "Trimline"]


class ToOrderItem(BaseModel):
    id: str
    sku: str
    name: str
    supplier_name: str
    category_name: str
    current_stock: int
    reorder_level: int
    quantity_to_order: int
    cost_price: float
    order_value: float
    showroom_stock: dict = {}


class ToOrderReport(BaseModel):
    supplier: str
    total_items: int
    total_order_value: float
    items: List[ToOrderItem]


@router.get("/reports/to-order")
async def get_to_order_report(
    supplier: Optional[str] = Query(None, description="Filter by supplier name"),
    include_zero_stock: bool = Query(True, description="Include items with zero stock"),
    min_order_qty: int = Query(1, description="Minimum quantity to order"),
    showroom_id: Optional[str] = Query(None, description="Filter by showroom stock"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get a "To Order" report showing products that need to be reordered.
    Products are included if their stock is at or below their reorder level.
    """
    require_admin_access(current_user)
    db = get_db()
    
    # Build query
    query = {
        "$expr": {"$lte": ["$stock", "$reorder_level"]}
    }
    
    # Filter by supplier if specified
    if supplier:
        query["supplier_name"] = {"$regex": supplier, "$options": "i"}
    else:
        # Default to the three main ordering suppliers
        query["supplier_name"] = {"$in": ORDERING_SUPPLIERS}
    
    # Optionally exclude zero stock items
    if not include_zero_stock:
        query["stock"] = {"$gt": 0}
    
    # Get products needing reorder
    products = await db.products.find(query, {"_id": 0}).to_list(10000)
    
    # Group by supplier
    reports_by_supplier = {}
    
    for product in products:
        supplier_name = product.get("supplier_name", "Unknown")
        current_stock = product.get("stock", 0)
        reorder_level = product.get("reorder_level", 10)
        cost_price = product.get("cost_price", 0) or 0
        
        # Calculate quantity to order (bring stock up to reorder_level + buffer)
        # Order enough to reach reorder_level * 1.5 or at least min_order_qty
        target_stock = int(reorder_level * 1.5)
        quantity_to_order = max(target_stock - current_stock, min_order_qty)
        
        # If showroom filter, check showroom stock
        if showroom_id:
            showroom_stock = product.get("showroom_stock", {})
            if isinstance(showroom_stock, list):
                # Convert list format to dict
                showroom_stock = {s.get("showroom_id"): s.get("quantity", 0) for s in showroom_stock}
            
            showroom_qty = showroom_stock.get(showroom_id, 0)
            if showroom_qty > reorder_level:
                continue  # Skip if this showroom has enough stock
        
        item = ToOrderItem(
            id=product.get("id", ""),
            sku=product.get("sku", ""),
            name=product.get("name", ""),
            supplier_name=supplier_name,
            category_name=product.get("category_name", ""),
            current_stock=current_stock,
            reorder_level=reorder_level,
            quantity_to_order=quantity_to_order,
            cost_price=cost_price,
            order_value=round(cost_price * quantity_to_order, 2),
            showroom_stock=product.get("showroom_stock", {})
        )
        
        if supplier_name not in reports_by_supplier:
            reports_by_supplier[supplier_name] = {
                "items": [],
                "total_value": 0
            }
        
        reports_by_supplier[supplier_name]["items"].append(item)
        reports_by_supplier[supplier_name]["total_value"] += item.order_value
    
    # Format response
    reports = []
    for sup_name in ORDERING_SUPPLIERS:
        if sup_name in reports_by_supplier:
            data = reports_by_supplier[sup_name]
            reports.append(ToOrderReport(
                supplier=sup_name,
                total_items=len(data["items"]),
                total_order_value=round(data["total_value"], 2),
                items=sorted(data["items"], key=lambda x: x.quantity_to_order, reverse=True)
            ))
    
    # Add any other suppliers
    for sup_name, data in reports_by_supplier.items():
        if sup_name not in ORDERING_SUPPLIERS:
            reports.append(ToOrderReport(
                supplier=sup_name,
                total_items=len(data["items"]),
                total_order_value=round(data["total_value"], 2),
                items=sorted(data["items"], key=lambda x: x.quantity_to_order, reverse=True)
            ))
    
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_suppliers": len(reports),
        "total_items": sum(r.total_items for r in reports),
        "total_order_value": round(sum(r.total_order_value for r in reports), 2),
        "reports": reports
    }


@router.get("/reports/to-order/export")
async def export_to_order_report(
    supplier: Optional[str] = Query(None, description="Filter by supplier name"),
    format: str = Query("csv", description="Export format: csv or json"),
    current_user: dict = Depends(get_current_user)
):
    """
    Export the To Order report as CSV or JSON.
    """
    require_admin_access(current_user)
    db = get_db()
    
    # Build query
    query = {
        "$expr": {"$lte": ["$stock", "$reorder_level"]}
    }
    
    if supplier:
        query["supplier_name"] = {"$regex": supplier, "$options": "i"}
    else:
        query["supplier_name"] = {"$in": ORDERING_SUPPLIERS}
    
    products = await db.products.find(query, {"_id": 0}).to_list(10000)
    
    # Process products
    rows = []
    for product in products:
        current_stock = product.get("stock", 0)
        reorder_level = product.get("reorder_level", 10)
        cost_price = product.get("cost_price", 0) or 0
        target_stock = int(reorder_level * 1.5)
        quantity_to_order = max(target_stock - current_stock, 1)
        
        rows.append({
            "Supplier": product.get("supplier_name", "Unknown"),
            "SKU": product.get("sku", ""),
            "Product Name": product.get("name", ""),
            "Category": product.get("category_name", ""),
            "Current Stock": current_stock,
            "Reorder Level": reorder_level,
            "Qty to Order": quantity_to_order,
            "Cost Price": cost_price,
            "Order Value": round(cost_price * quantity_to_order, 2)
        })
    
    # Sort by supplier then by quantity to order
    rows.sort(key=lambda x: (x["Supplier"], -x["Qty to Order"]))
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    supplier_suffix = f"_{supplier.replace(' ', '_')}" if supplier else "_all"
    
    if format == "csv":
        output = io.StringIO()
        if rows:
            writer = csv.DictWriter(output, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        
        output.seek(0)
        filename = f"to_order_report{supplier_suffix}_{timestamp}.csv"
        
        await log_audit(
            action="EXPORT",
            entity_type="to_order_report",
            user=current_user,
            details=f"Exported {len(rows)} items to order for {supplier or 'all suppliers'}"
        )
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    else:
        import json
        filename = f"to_order_report{supplier_suffix}_{timestamp}.json"
        json_data = json.dumps({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "supplier_filter": supplier,
            "total_items": len(rows),
            "items": rows
        }, indent=2)
        
        await log_audit(
            action="EXPORT",
            entity_type="to_order_report",
            user=current_user,
            details=f"Exported {len(rows)} items to order for {supplier or 'all suppliers'}"
        )
        
        return StreamingResponse(
            iter([json_data]),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )


@router.get("/reports/low-stock")
async def get_low_stock_report(
    supplier: Optional[str] = Query(None, description="Filter by supplier"),
    threshold: int = Query(10, description="Stock threshold to consider 'low'"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get products with stock below a specified threshold.
    """
    require_admin_access(current_user)
    db = get_db()
    
    query = {"stock": {"$lte": threshold}}
    
    if supplier:
        query["supplier_name"] = {"$regex": supplier, "$options": "i"}
    
    products = await db.products.find(
        query,
        {"_id": 0, "id": 1, "sku": 1, "name": 1, "supplier_name": 1, 
         "category_name": 1, "stock": 1, "reorder_level": 1, "cost_price": 1}
    ).sort("stock", 1).to_list(10000)
    
    # Group by supplier
    by_supplier = {}
    for product in products:
        sup = product.get("supplier_name", "Unknown")
        if sup not in by_supplier:
            by_supplier[sup] = []
        by_supplier[sup].append(product)
    
    return {
        "threshold": threshold,
        "total_low_stock": len(products),
        "by_supplier": [
            {
                "supplier": sup,
                "count": len(items),
                "items": items
            }
            for sup, items in sorted(by_supplier.items())
        ]
    }


@router.get("/reports/stock-value")
async def get_stock_value_report(
    supplier: Optional[str] = Query(None, description="Filter by supplier"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get total stock value by supplier.
    """
    require_admin_access(current_user)
    db = get_db()
    
    # Aggregation pipeline
    match_stage = {}
    if supplier:
        match_stage["supplier_name"] = {"$regex": supplier, "$options": "i"}
    
    pipeline = [
        {"$match": match_stage} if match_stage else {"$match": {}},
        {
            "$group": {
                "_id": "$supplier_name",
                "total_products": {"$sum": 1},
                "total_stock": {"$sum": "$stock"},
                "total_cost_value": {
                    "$sum": {"$multiply": ["$stock", {"$ifNull": ["$cost_price", 0]}]}
                },
                "total_retail_value": {
                    "$sum": {"$multiply": ["$stock", {"$ifNull": ["$price", 0]}]}
                }
            }
        },
        {"$sort": {"total_cost_value": -1}}
    ]
    
    results = await db.products.aggregate(pipeline).to_list(100)
    
    totals = {
        "total_products": sum(r["total_products"] for r in results),
        "total_stock": sum(r["total_stock"] for r in results),
        "total_cost_value": round(sum(r["total_cost_value"] for r in results), 2),
        "total_retail_value": round(sum(r["total_retail_value"] for r in results), 2)
    }
    
    return {
        "by_supplier": [
            {
                "supplier": r["_id"] or "Unknown",
                "total_products": r["total_products"],
                "total_stock": r["total_stock"],
                "cost_value": round(r["total_cost_value"], 2),
                "retail_value": round(r["total_retail_value"], 2)
            }
            for r in results
        ],
        "totals": totals
    }

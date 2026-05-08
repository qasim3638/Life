"""
Automatic Reorder Points - Set minimum stock levels and auto-generate purchase orders
"""
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Depends, Body
from pydantic import BaseModel
import uuid

from config import get_db
from routes.auth import get_current_user

router = APIRouter(prefix="/reorder-points", tags=["Reorder Points"])


class ReorderPointCreate(BaseModel):
    product_id: str
    min_stock: int  # Reorder when stock falls below this
    reorder_qty: int  # Quantity to order
    max_stock: Optional[int] = None  # Optional max stock level
    supplier: Optional[str] = None
    auto_create_po: bool = False  # Auto-create purchase order
    notes: Optional[str] = None


class ReorderPointUpdate(BaseModel):
    min_stock: Optional[int] = None
    reorder_qty: Optional[int] = None
    max_stock: Optional[int] = None
    auto_create_po: Optional[bool] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class PurchaseOrderItem(BaseModel):
    product_id: str
    sku: str
    name: str
    quantity: int
    unit_cost: Optional[float] = None
    total_cost: Optional[float] = None


class PurchaseOrderCreate(BaseModel):
    supplier: str
    items: List[PurchaseOrderItem]
    notes: Optional[str] = None
    expected_delivery: Optional[str] = None


# ============ REORDER POINTS ============

@router.post("/set")
async def set_reorder_point(
    config: ReorderPointCreate,
    current_user: dict = Depends(get_current_user)
):
    """Set or update reorder point for a product"""
    db = get_db()
    
    # Verify product exists
    product = await db.products.find_one({"id": config.product_id})
    if not product:
        product = await db.supplier_products.find_one({"id": config.product_id})
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    reorder_point = {
        "product_id": config.product_id,
        "sku": product.get("sku", ""),
        "product_name": product.get("name", ""),
        "min_stock": config.min_stock,
        "reorder_qty": config.reorder_qty,
        "max_stock": config.max_stock,
        "supplier": config.supplier or product.get("supplier"),
        "auto_create_po": config.auto_create_po,
        "is_active": True,
        "notes": config.notes,
        "created_by": current_user.get("email"),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    # Upsert
    await db.reorder_points.update_one(
        {"product_id": config.product_id},
        {"$set": reorder_point},
        upsert=True
    )
    
    return {"message": "Reorder point set", "reorder_point": reorder_point}


@router.get("/list")
async def list_reorder_points(
    is_active: Optional[bool] = None,
    supplier: Optional[str] = None,
    triggered_only: bool = False,
    limit: int = Query(100, le=500)
):
    """List all reorder points, optionally filtered"""
    db = get_db()
    
    query = {}
    if is_active is not None:
        query["is_active"] = is_active
    if supplier:
        query["supplier"] = supplier
    
    reorder_points = await db.reorder_points.find(query, {"_id": 0}).limit(limit).to_list(limit)
    
    # Enrich with current stock levels
    result = []
    for rp in reorder_points:
        product = await db.products.find_one({"id": rp["product_id"]}, {"stock": 1, "_id": 0})
        if not product:
            product = await db.supplier_products.find_one({"id": rp["product_id"]}, {"stock": 1, "_id": 0})
        
        current_stock = product.get("stock", 0) if product else 0
        is_triggered = current_stock <= rp["min_stock"]
        
        if triggered_only and not is_triggered:
            continue
        
        result.append({
            **rp,
            "current_stock": current_stock,
            "is_triggered": is_triggered,
            "stock_deficit": max(0, rp["min_stock"] - current_stock)
        })
    
    # Sort by triggered first, then by stock deficit
    result.sort(key=lambda x: (not x["is_triggered"], -x["stock_deficit"]))
    
    return {
        "reorder_points": result,
        "total": len(result),
        "triggered_count": sum(1 for r in result if r["is_triggered"])
    }


@router.get("/check-triggers")
async def check_reorder_triggers():
    """Check which products have triggered their reorder points"""
    db = get_db()
    
    # Get all active reorder points
    reorder_points = await db.reorder_points.find({"is_active": True}, {"_id": 0}).to_list(None)
    
    triggered = []
    for rp in reorder_points:
        product = await db.products.find_one({"id": rp["product_id"]}, {"stock": 1, "_id": 0})
        if not product:
            product = await db.supplier_products.find_one({"id": rp["product_id"]}, {"stock": 1, "_id": 0})
        
        current_stock = product.get("stock", 0) if product else 0
        
        if current_stock <= rp["min_stock"]:
            triggered.append({
                "product_id": rp["product_id"],
                "sku": rp["sku"],
                "product_name": rp["product_name"],
                "current_stock": current_stock,
                "min_stock": rp["min_stock"],
                "reorder_qty": rp["reorder_qty"],
                "supplier": rp["supplier"],
                "auto_create_po": rp["auto_create_po"],
                "deficit": rp["min_stock"] - current_stock
            })
    
    # Sort by deficit (most urgent first)
    triggered.sort(key=lambda x: -x["deficit"])
    
    return {
        "triggered_items": triggered,
        "count": len(triggered),
        "checked_at": datetime.now(timezone.utc).isoformat()
    }


@router.put("/{product_id}")
async def update_reorder_point(
    product_id: str,
    update: ReorderPointUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update a reorder point configuration"""
    db = get_db()
    
    update_data = {k: v for k, v in update.dict().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc)
    update_data["updated_by"] = current_user.get("email")
    
    result = await db.reorder_points.update_one(
        {"product_id": product_id},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Reorder point not found")
    
    return {"message": "Reorder point updated"}


@router.delete("/{product_id}")
async def delete_reorder_point(
    product_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a reorder point"""
    db = get_db()
    
    result = await db.reorder_points.delete_one({"product_id": product_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Reorder point not found")
    
    return {"message": "Reorder point deleted"}


# ============ PURCHASE ORDERS ============

@router.post("/purchase-orders/create")
async def create_purchase_order(
    po: PurchaseOrderCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new purchase order"""
    db = get_db()
    
    # Generate PO number
    count = await db.purchase_orders.count_documents({})
    po_number = f"PO-{datetime.now().strftime('%Y%m')}-{count + 1:04d}"
    
    # Calculate totals
    total_items = len(po.items)
    total_qty = sum(item.quantity for item in po.items)
    total_cost = sum(item.total_cost or 0 for item in po.items)
    
    purchase_order = {
        "id": str(uuid.uuid4()),
        "po_number": po_number,
        "supplier": po.supplier,
        "status": "draft",  # draft, sent, confirmed, received, cancelled
        "items": [item.dict() for item in po.items],
        "total_items": total_items,
        "total_qty": total_qty,
        "total_cost": total_cost,
        "notes": po.notes,
        "expected_delivery": po.expected_delivery,
        "created_by": current_user.get("email"),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    await db.purchase_orders.insert_one(purchase_order)
    
    # Remove _id for response
    purchase_order.pop("_id", None)
    
    return {"message": "Purchase order created", "purchase_order": purchase_order}


@router.post("/purchase-orders/create-from-triggers")
async def create_po_from_triggers(
    supplier: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Auto-create purchase order from triggered reorder points"""
    db = get_db()
    
    # Get triggered items
    query = {"is_active": True}
    if supplier:
        query["supplier"] = supplier
    
    reorder_points = await db.reorder_points.find(query, {"_id": 0}).to_list(None)
    
    items_by_supplier = {}
    
    for rp in reorder_points:
        product = await db.products.find_one({"id": rp["product_id"]}, {"stock": 1, "cost_price": 1, "cost": 1, "_id": 0})
        if not product:
            product = await db.supplier_products.find_one({"id": rp["product_id"]}, {"stock": 1, "cost_price": 1, "cost": 1, "_id": 0})
        
        current_stock = product.get("stock", 0) if product else 0
        
        if current_stock <= rp["min_stock"]:
            supplier_name = rp.get("supplier") or "Unknown"
            cost = product.get("cost_price") or product.get("cost") if product else None
            
            if supplier_name not in items_by_supplier:
                items_by_supplier[supplier_name] = []
            
            items_by_supplier[supplier_name].append({
                "product_id": rp["product_id"],
                "sku": rp["sku"],
                "name": rp["product_name"],
                "quantity": rp["reorder_qty"],
                "unit_cost": cost,
                "total_cost": cost * rp["reorder_qty"] if cost else None
            })
    
    # Create POs
    created_pos = []
    for supp, items in items_by_supplier.items():
        if supplier and supp != supplier:
            continue
        
        count = await db.purchase_orders.count_documents({})
        po_number = f"PO-{datetime.now().strftime('%Y%m')}-{count + 1:04d}"
        
        total_cost = sum(i["total_cost"] or 0 for i in items)
        
        po = {
            "id": str(uuid.uuid4()),
            "po_number": po_number,
            "supplier": supp,
            "status": "draft",
            "items": items,
            "total_items": len(items),
            "total_qty": sum(i["quantity"] for i in items),
            "total_cost": total_cost,
            "notes": "Auto-generated from reorder triggers",
            "created_by": current_user.get("email"),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        
        await db.purchase_orders.insert_one(po)
        po.pop("_id", None)
        created_pos.append(po)
    
    return {
        "message": f"Created {len(created_pos)} purchase orders",
        "purchase_orders": created_pos
    }


@router.get("/purchase-orders")
async def list_purchase_orders(
    status: Optional[str] = None,
    supplier: Optional[str] = None,
    limit: int = Query(50, le=200)
):
    """List purchase orders"""
    db = get_db()
    
    query = {}
    if status:
        query["status"] = status
    if supplier:
        query["supplier"] = supplier
    
    pos = await db.purchase_orders.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    
    return {"purchase_orders": pos, "total": len(pos)}


@router.patch("/purchase-orders/{po_id}/status")
async def update_po_status(
    po_id: str,
    status: str = Body(..., embed=True),
    current_user: dict = Depends(get_current_user)
):
    """Update purchase order status"""
    valid_statuses = ["draft", "sent", "confirmed", "received", "cancelled"]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    
    db = get_db()
    
    update_data = {
        "status": status,
        "updated_at": datetime.now(timezone.utc),
        "updated_by": current_user.get("email")
    }
    
    # If received, update stock
    if status == "received":
        po = await db.purchase_orders.find_one({"id": po_id})
        if po:
            for item in po.get("items", []):
                await db.products.update_one(
                    {"id": item["product_id"]},
                    {"$inc": {"stock": item["quantity"]}}
                )
            update_data["received_at"] = datetime.now(timezone.utc)
    
    result = await db.purchase_orders.update_one(
        {"id": po_id},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    
    return {"message": f"Purchase order status updated to {status}"}

"""
Batch/Lot Tracking - Track products by batch number for quality control
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Depends, Body
from pydantic import BaseModel
import uuid

from config import get_db
from routes.auth import get_current_user

router = APIRouter(prefix="/batch-tracking", tags=["Batch Tracking"])


class BatchCreate(BaseModel):
    product_id: str
    batch_number: str
    quantity: int
    manufacturing_date: Optional[str] = None
    expiry_date: Optional[str] = None
    supplier_batch: Optional[str] = None  # Supplier's batch reference
    supplier: Optional[str] = None
    cost_price: Optional[float] = None
    showroom_id: Optional[str] = None  # Location of batch
    notes: Optional[str] = None


class BatchUpdate(BaseModel):
    quantity: Optional[int] = None
    expiry_date: Optional[str] = None
    showroom_id: Optional[str] = None
    status: Optional[str] = None  # active, depleted, recalled, expired
    notes: Optional[str] = None


class BatchMovement(BaseModel):
    quantity: int
    movement_type: str  # sale, transfer, adjustment, return, writeoff
    reference: Optional[str] = None  # Invoice/transfer number
    notes: Optional[str] = None


@router.post("/batches/create")
async def create_batch(
    batch: BatchCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new batch/lot for a product"""
    db = get_db()
    
    # Verify product exists
    product = await db.products.find_one({"id": batch.product_id})
    if not product:
        product = await db.supplier_products.find_one({"id": batch.product_id})
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Check if batch number already exists for this product
    existing = await db.batches.find_one({
        "product_id": batch.product_id,
        "batch_number": batch.batch_number
    })
    
    if existing:
        raise HTTPException(status_code=400, detail="Batch number already exists for this product")
    
    batch_record = {
        "id": str(uuid.uuid4()),
        "product_id": batch.product_id,
        "sku": product.get("sku", ""),
        "product_name": product.get("name", ""),
        "batch_number": batch.batch_number,
        "initial_quantity": batch.quantity,
        "current_quantity": batch.quantity,
        "manufacturing_date": batch.manufacturing_date,
        "expiry_date": batch.expiry_date,
        "supplier_batch": batch.supplier_batch,
        "supplier": batch.supplier or product.get("supplier"),
        "cost_price": batch.cost_price,
        "showroom_id": batch.showroom_id,
        "status": "active",  # active, depleted, recalled, expired
        "notes": batch.notes,
        "created_by": current_user.get("email"),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    await db.batches.insert_one(batch_record)
    batch_record.pop("_id", None)
    
    return {"message": "Batch created", "batch": batch_record}


@router.get("/batches")
async def list_batches(
    product_id: Optional[str] = None,
    status: Optional[str] = None,
    showroom_id: Optional[str] = None,
    expiring_soon: bool = False,
    days_to_expiry: int = 30,
    limit: int = Query(100, le=500)
):
    """List batches with optional filters"""
    db = get_db()
    
    query = {}
    if product_id:
        query["product_id"] = product_id
    if status:
        query["status"] = status
    if showroom_id:
        query["showroom_id"] = showroom_id
    
    if expiring_soon:
        expiry_cutoff = datetime.now(timezone.utc) + timedelta(days=days_to_expiry)
        query["expiry_date"] = {"$lte": expiry_cutoff.isoformat(), "$ne": None}
        query["status"] = "active"
    
    batches = await db.batches.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    
    return {
        "batches": batches,
        "total": len(batches)
    }


@router.get("/batches/{batch_id}")
async def get_batch(batch_id: str):
    """Get details of a specific batch"""
    db = get_db()
    
    batch = await db.batches.find_one({"id": batch_id}, {"_id": 0})
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Get movement history
    movements = await db.batch_movements.find(
        {"batch_id": batch_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    batch["movements"] = movements
    
    return batch


@router.get("/product/{product_id}/batches")
async def get_product_batches(
    product_id: str,
    include_depleted: bool = False
):
    """Get all batches for a product, useful for FIFO selection"""
    db = get_db()
    
    query = {"product_id": product_id}
    if not include_depleted:
        query["status"] = "active"
        query["current_quantity"] = {"$gt": 0}
    
    batches = await db.batches.find(query, {"_id": 0}).sort("created_at", 1).to_list(None)
    
    total_qty = sum(b["current_quantity"] for b in batches)
    
    return {
        "product_id": product_id,
        "batches": batches,
        "total_batches": len(batches),
        "total_quantity": total_qty
    }


@router.post("/batches/{batch_id}/movement")
async def record_batch_movement(
    batch_id: str,
    movement: BatchMovement,
    current_user: dict = Depends(get_current_user)
):
    """Record a movement (sale, transfer, adjustment) for a batch"""
    db = get_db()
    
    batch = await db.batches.find_one({"id": batch_id})
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Validate quantity for deductions
    if movement.movement_type in ["sale", "transfer", "writeoff"]:
        if movement.quantity > batch["current_quantity"]:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient batch quantity. Available: {batch['current_quantity']}"
            )
        quantity_change = -movement.quantity
    elif movement.movement_type == "return":
        quantity_change = movement.quantity
    elif movement.movement_type == "adjustment":
        quantity_change = movement.quantity  # Can be positive or negative
    else:
        raise HTTPException(status_code=400, detail="Invalid movement type")
    
    new_quantity = batch["current_quantity"] + quantity_change
    
    # Create movement record
    movement_record = {
        "id": str(uuid.uuid4()),
        "batch_id": batch_id,
        "product_id": batch["product_id"],
        "batch_number": batch["batch_number"],
        "movement_type": movement.movement_type,
        "quantity": movement.quantity,
        "quantity_change": quantity_change,
        "quantity_before": batch["current_quantity"],
        "quantity_after": new_quantity,
        "reference": movement.reference,
        "notes": movement.notes,
        "created_by": current_user.get("email"),
        "created_at": datetime.now(timezone.utc)
    }
    
    await db.batch_movements.insert_one(movement_record)
    
    # Update batch quantity and status
    update_data = {
        "current_quantity": new_quantity,
        "updated_at": datetime.now(timezone.utc)
    }
    
    if new_quantity <= 0:
        update_data["status"] = "depleted"
    
    await db.batches.update_one(
        {"id": batch_id},
        {"$set": update_data}
    )
    
    movement_record.pop("_id", None)
    
    return {
        "message": "Movement recorded",
        "movement": movement_record,
        "new_quantity": new_quantity
    }


@router.patch("/batches/{batch_id}")
async def update_batch(
    batch_id: str,
    update: BatchUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update batch information"""
    db = get_db()
    
    update_data = {k: v for k, v in update.dict().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc)
    update_data["updated_by"] = current_user.get("email")
    
    result = await db.batches.update_one(
        {"id": batch_id},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    return {"message": "Batch updated"}


@router.post("/batches/{batch_id}/recall")
async def recall_batch(
    batch_id: str,
    reason: str = Body(..., embed=True),
    current_user: dict = Depends(get_current_user)
):
    """Mark a batch as recalled for quality control"""
    db = get_db()
    
    batch = await db.batches.find_one({"id": batch_id})
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    await db.batches.update_one(
        {"id": batch_id},
        {"$set": {
            "status": "recalled",
            "recall_reason": reason,
            "recalled_at": datetime.now(timezone.utc),
            "recalled_by": current_user.get("email"),
            "updated_at": datetime.now(timezone.utc)
        }}
    )
    
    # Log the recall
    recall_record = {
        "id": str(uuid.uuid4()),
        "batch_id": batch_id,
        "product_id": batch["product_id"],
        "batch_number": batch["batch_number"],
        "reason": reason,
        "quantity_affected": batch["current_quantity"],
        "recalled_by": current_user.get("email"),
        "recalled_at": datetime.now(timezone.utc)
    }
    
    await db.batch_recalls.insert_one(recall_record)
    
    return {
        "message": "Batch recalled",
        "batch_number": batch["batch_number"],
        "quantity_affected": batch["current_quantity"]
    }


@router.get("/expiring")
async def get_expiring_batches(
    days: int = Query(30, description="Days until expiry"),
    showroom_id: Optional[str] = None
):
    """Get batches that are expiring soon"""
    db = get_db()
    
    from datetime import timedelta
    expiry_cutoff = datetime.now(timezone.utc) + timedelta(days=days)
    
    query = {
        "expiry_date": {"$lte": expiry_cutoff.isoformat(), "$ne": None},
        "status": "active",
        "current_quantity": {"$gt": 0}
    }
    
    if showroom_id:
        query["showroom_id"] = showroom_id
    
    batches = await db.batches.find(query, {"_id": 0}).sort("expiry_date", 1).to_list(100)
    
    return {
        "expiring_batches": batches,
        "days_threshold": days,
        "count": len(batches)
    }


@router.get("/recalls")
async def get_recall_history(limit: int = Query(50, le=200)):
    """Get batch recall history"""
    db = get_db()
    
    recalls = await db.batch_recalls.find({}, {"_id": 0}).sort("recalled_at", -1).limit(limit).to_list(limit)
    
    return {
        "recalls": recalls,
        "total": len(recalls)
    }

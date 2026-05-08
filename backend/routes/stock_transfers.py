"""
Stock Transfers Between Locations - Move stock between showrooms with tracking
"""
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Depends, Body
from pydantic import BaseModel
import uuid

from config import get_db
from routes.auth import get_current_user

router = APIRouter(prefix="/stock-transfers", tags=["Stock Transfers"])


class TransferItem(BaseModel):
    product_id: str
    sku: str
    name: str
    quantity: int


class StockTransferCreate(BaseModel):
    from_showroom_id: str
    to_showroom_id: str
    items: List[TransferItem]
    notes: Optional[str] = None
    transfer_date: Optional[str] = None  # If scheduled for future


class TransferStatusUpdate(BaseModel):
    status: str  # pending, in_transit, received, cancelled
    notes: Optional[str] = None


@router.post("/create")
async def create_stock_transfer(
    transfer: StockTransferCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new stock transfer between showrooms"""
    db = get_db()
    
    # Validate showrooms exist
    from_showroom = await db.showrooms.find_one({"id": transfer.from_showroom_id})
    to_showroom = await db.showrooms.find_one({"id": transfer.to_showroom_id})
    
    if not from_showroom:
        raise HTTPException(status_code=404, detail="Source showroom not found")
    if not to_showroom:
        raise HTTPException(status_code=404, detail="Destination showroom not found")
    
    if transfer.from_showroom_id == transfer.to_showroom_id:
        raise HTTPException(status_code=400, detail="Cannot transfer to the same showroom")
    
    # Validate stock availability
    insufficient_stock = []
    for item in transfer.items:
        product = await db.products.find_one({"id": item.product_id})
        if not product:
            product = await db.supplier_products.find_one({"id": item.product_id})
        
        if not product:
            insufficient_stock.append({"product_id": item.product_id, "error": "Product not found"})
            continue
        
        # Check showroom-specific stock
        showroom_stock = product.get("showroom_stock", {}).get(transfer.from_showroom_id, 0)
        if showroom_stock < item.quantity:
            insufficient_stock.append({
                "product_id": item.product_id,
                "sku": item.sku,
                "name": item.name,
                "requested": item.quantity,
                "available": showroom_stock,
                "error": "Insufficient stock"
            })
    
    if insufficient_stock:
        raise HTTPException(
            status_code=400,
            detail={"message": "Insufficient stock for some items", "items": insufficient_stock}
        )
    
    # Generate transfer number
    count = await db.stock_transfers.count_documents({})
    transfer_number = f"TRF-{datetime.now().strftime('%Y%m%d')}-{count + 1:04d}"
    
    # Create transfer record
    stock_transfer = {
        "id": str(uuid.uuid4()),
        "transfer_number": transfer_number,
        "from_showroom_id": transfer.from_showroom_id,
        "from_showroom_name": from_showroom.get("name"),
        "to_showroom_id": transfer.to_showroom_id,
        "to_showroom_name": to_showroom.get("name"),
        "items": [item.dict() for item in transfer.items],
        "total_items": len(transfer.items),
        "total_qty": sum(item.quantity for item in transfer.items),
        "status": "pending",  # pending, in_transit, received, cancelled
        "notes": transfer.notes,
        "transfer_date": transfer.transfer_date or datetime.now(timezone.utc).isoformat(),
        "created_by": current_user.get("email"),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    await db.stock_transfers.insert_one(stock_transfer)
    stock_transfer.pop("_id", None)
    
    return {"message": "Stock transfer created", "transfer": stock_transfer}


@router.get("/list")
async def list_stock_transfers(
    status: Optional[str] = None,
    from_showroom_id: Optional[str] = None,
    to_showroom_id: Optional[str] = None,
    limit: int = Query(50, le=200)
):
    """List stock transfers with optional filters"""
    db = get_db()
    
    query = {}
    if status:
        query["status"] = status
    if from_showroom_id:
        query["from_showroom_id"] = from_showroom_id
    if to_showroom_id:
        query["to_showroom_id"] = to_showroom_id
    
    transfers = await db.stock_transfers.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    
    return {
        "transfers": transfers,
        "total": len(transfers)
    }


@router.get("/{transfer_id}")
async def get_stock_transfer(transfer_id: str):
    """Get details of a specific stock transfer"""
    db = get_db()
    
    transfer = await db.stock_transfers.find_one({"id": transfer_id}, {"_id": 0})
    if not transfer:
        raise HTTPException(status_code=404, detail="Stock transfer not found")
    
    return transfer


@router.patch("/{transfer_id}/dispatch")
async def dispatch_transfer(
    transfer_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Mark transfer as dispatched (in transit) and deduct stock from source"""
    db = get_db()
    
    transfer = await db.stock_transfers.find_one({"id": transfer_id})
    if not transfer:
        raise HTTPException(status_code=404, detail="Stock transfer not found")
    
    if transfer["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"Cannot dispatch transfer with status: {transfer['status']}")
    
    # Deduct stock from source showroom
    for item in transfer["items"]:
        # Update showroom-specific stock
        await db.products.update_one(
            {"id": item["product_id"]},
            {"$inc": {f"showroom_stock.{transfer['from_showroom_id']}": -item["quantity"]}}
        )
        # Also try supplier_products
        await db.supplier_products.update_one(
            {"id": item["product_id"]},
            {"$inc": {f"showroom_stock.{transfer['from_showroom_id']}": -item["quantity"]}}
        )
    
    # Update transfer status
    await db.stock_transfers.update_one(
        {"id": transfer_id},
        {"$set": {
            "status": "in_transit",
            "dispatched_at": datetime.now(timezone.utc),
            "dispatched_by": current_user.get("email"),
            "updated_at": datetime.now(timezone.utc)
        }}
    )
    
    return {"message": "Transfer dispatched", "status": "in_transit"}


@router.patch("/{transfer_id}/receive")
async def receive_transfer(
    transfer_id: str,
    notes: Optional[str] = Body(None),
    current_user: dict = Depends(get_current_user)
):
    """Mark transfer as received and add stock to destination"""
    db = get_db()
    
    transfer = await db.stock_transfers.find_one({"id": transfer_id})
    if not transfer:
        raise HTTPException(status_code=404, detail="Stock transfer not found")
    
    if transfer["status"] not in ["pending", "in_transit"]:
        raise HTTPException(status_code=400, detail=f"Cannot receive transfer with status: {transfer['status']}")
    
    # If still pending (direct receive), deduct from source first
    if transfer["status"] == "pending":
        for item in transfer["items"]:
            await db.products.update_one(
                {"id": item["product_id"]},
                {"$inc": {f"showroom_stock.{transfer['from_showroom_id']}": -item["quantity"]}}
            )
            await db.supplier_products.update_one(
                {"id": item["product_id"]},
                {"$inc": {f"showroom_stock.{transfer['from_showroom_id']}": -item["quantity"]}}
            )
    
    # Add stock to destination showroom
    for item in transfer["items"]:
        await db.products.update_one(
            {"id": item["product_id"]},
            {"$inc": {f"showroom_stock.{transfer['to_showroom_id']}": item["quantity"]}}
        )
        await db.supplier_products.update_one(
            {"id": item["product_id"]},
            {"$inc": {f"showroom_stock.{transfer['to_showroom_id']}": item["quantity"]}}
        )
    
    # Update transfer status
    await db.stock_transfers.update_one(
        {"id": transfer_id},
        {"$set": {
            "status": "received",
            "received_at": datetime.now(timezone.utc),
            "received_by": current_user.get("email"),
            "received_notes": notes,
            "updated_at": datetime.now(timezone.utc)
        }}
    )
    
    return {"message": "Transfer received and stock updated", "status": "received"}


@router.patch("/{transfer_id}/cancel")
async def cancel_transfer(
    transfer_id: str,
    reason: str = Body(..., embed=True),
    current_user: dict = Depends(get_current_user)
):
    """Cancel a stock transfer"""
    db = get_db()
    
    transfer = await db.stock_transfers.find_one({"id": transfer_id})
    if not transfer:
        raise HTTPException(status_code=404, detail="Stock transfer not found")
    
    if transfer["status"] == "received":
        raise HTTPException(status_code=400, detail="Cannot cancel a received transfer")
    
    # If in_transit, return stock to source
    if transfer["status"] == "in_transit":
        for item in transfer["items"]:
            await db.products.update_one(
                {"id": item["product_id"]},
                {"$inc": {f"showroom_stock.{transfer['from_showroom_id']}": item["quantity"]}}
            )
            await db.supplier_products.update_one(
                {"id": item["product_id"]},
                {"$inc": {f"showroom_stock.{transfer['from_showroom_id']}": item["quantity"]}}
            )
    
    # Update status
    await db.stock_transfers.update_one(
        {"id": transfer_id},
        {"$set": {
            "status": "cancelled",
            "cancelled_at": datetime.now(timezone.utc),
            "cancelled_by": current_user.get("email"),
            "cancellation_reason": reason,
            "updated_at": datetime.now(timezone.utc)
        }}
    )
    
    return {"message": "Transfer cancelled", "status": "cancelled"}


@router.get("/showroom/{showroom_id}/history")
async def get_showroom_transfer_history(
    showroom_id: str,
    direction: Optional[str] = Query(None, description="'in', 'out', or None for both"),
    limit: int = Query(50, le=200)
):
    """Get transfer history for a specific showroom"""
    db = get_db()
    
    if direction == "in":
        query = {"to_showroom_id": showroom_id}
    elif direction == "out":
        query = {"from_showroom_id": showroom_id}
    else:
        query = {"$or": [
            {"from_showroom_id": showroom_id},
            {"to_showroom_id": showroom_id}
        ]}
    
    transfers = await db.stock_transfers.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    
    # Add direction indicator
    for t in transfers:
        if t["from_showroom_id"] == showroom_id:
            t["direction"] = "outgoing"
        else:
            t["direction"] = "incoming"
    
    return {
        "showroom_id": showroom_id,
        "transfers": transfers,
        "total": len(transfers)
    }

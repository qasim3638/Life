"""
Supplier Management Routes
CRUD operations for suppliers
"""
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
import uuid

from config import get_db
from services import get_current_user, require_admin_access, log_audit

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])


class SupplierCreate(BaseModel):
    name: str
    code: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    payment_terms: Optional[str] = None
    lead_time_days: Optional[int] = None
    notes: Optional[str] = None
    is_active: bool = True


class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    payment_terms: Optional[str] = None
    lead_time_days: Optional[int] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("")
async def get_suppliers(
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all suppliers"""
    db = get_db()
    
    query = {}
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"code": {"$regex": search, "$options": "i"}},
            {"contact_name": {"$regex": search, "$options": "i"}}
        ]
    if is_active is not None:
        query["is_active"] = is_active
    
    suppliers = await db.suppliers.find(query, {"_id": 0}).sort("name", 1).to_list(1000)
    
    # Get product counts for each supplier
    for supplier in suppliers:
        count = await db.products.count_documents({
            "supplier_name": {"$regex": f"^{supplier['name']}$", "$options": "i"}
        })
        supplier["product_count"] = count
    
    return suppliers


@router.get("/{supplier_id}")
async def get_supplier(supplier_id: str, current_user: dict = Depends(get_current_user)):
    """Get a single supplier by ID"""
    db = get_db()
    
    supplier = await db.suppliers.find_one({"id": supplier_id}, {"_id": 0})
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    
    # Get product count
    product_count = await db.products.count_documents({
        "supplier_name": {"$regex": f"^{supplier['name']}$", "$options": "i"}
    })
    supplier["product_count"] = product_count
    
    return supplier


@router.post("")
async def create_supplier(data: SupplierCreate, current_user: dict = Depends(get_current_user)):
    """Create a new supplier"""
    require_admin_access(current_user)
    db = get_db()
    
    # Check for duplicate name
    existing = await db.suppliers.find_one({"name": {"$regex": f"^{data.name}$", "$options": "i"}})
    if existing:
        raise HTTPException(status_code=400, detail="A supplier with this name already exists")
    
    supplier_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    
    # Generate code if not provided
    code = data.code
    if not code:
        # Create code from first 3 letters of name
        code = data.name[:3].upper().replace(" ", "")
        # Check uniqueness
        existing_code = await db.suppliers.find_one({"code": code})
        if existing_code:
            code = f"{code}{str(uuid.uuid4())[:4].upper()}"
    
    supplier = {
        "id": supplier_id,
        "name": data.name,
        "code": code,
        "contact_name": data.contact_name,
        "email": data.email,
        "phone": data.phone,
        "address": data.address,
        "website": data.website,
        "payment_terms": data.payment_terms,
        "lead_time_days": data.lead_time_days,
        "notes": data.notes,
        "is_active": data.is_active,
        "created_at": now,
        "updated_at": now,
        "created_by": current_user.get("name", "Unknown")
    }
    
    await db.suppliers.insert_one(supplier)
    
    await log_audit(
        action="CREATE",
        entity_type="supplier",
        entity_id=supplier_id,
        user=current_user,
        after_data={"name": data.name}
    )
    
    return {"message": "Supplier created", "supplier": {**supplier, "_id": None}}


@router.put("/{supplier_id}")
async def update_supplier(
    supplier_id: str, 
    data: SupplierUpdate, 
    current_user: dict = Depends(get_current_user)
):
    """Update a supplier"""
    require_admin_access(current_user)
    db = get_db()
    
    supplier = await db.suppliers.find_one({"id": supplier_id})
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    
    # Check for duplicate name if name is being updated
    if data.name and data.name.lower() != supplier.get("name", "").lower():
        existing = await db.suppliers.find_one({
            "name": {"$regex": f"^{data.name}$", "$options": "i"},
            "id": {"$ne": supplier_id}
        })
        if existing:
            raise HTTPException(status_code=400, detail="A supplier with this name already exists")
    
    # Build update dict
    update_data = {"updated_at": datetime.now(timezone.utc)}
    
    for field in ["name", "code", "contact_name", "email", "phone", "address", 
                  "website", "payment_terms", "lead_time_days", "notes", "is_active"]:
        value = getattr(data, field, None)
        if value is not None:
            update_data[field] = value
    
    # If name is being updated, update products with old supplier name
    if data.name and data.name != supplier.get("name"):
        old_name = supplier.get("name")
        await db.products.update_many(
            {"supplier_name": {"$regex": f"^{old_name}$", "$options": "i"}},
            {"$set": {"supplier_name": data.name}}
        )
    
    await db.suppliers.update_one({"id": supplier_id}, {"$set": update_data})
    
    await log_audit(
        action="UPDATE",
        entity_type="supplier",
        entity_id=supplier_id,
        user=current_user,
        before_data={"name": supplier.get("name")},
        after_data=update_data
    )
    
    updated = await db.suppliers.find_one({"id": supplier_id}, {"_id": 0})
    return {"message": "Supplier updated", "supplier": updated}


@router.delete("/{supplier_id}")
async def delete_supplier(supplier_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a supplier (soft delete - mark as inactive)"""
    require_admin_access(current_user)
    db = get_db()
    
    supplier = await db.suppliers.find_one({"id": supplier_id})
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    
    # Check if supplier has products
    product_count = await db.products.count_documents({
        "supplier_name": {"$regex": f"^{supplier['name']}$", "$options": "i"}
    })
    
    if product_count > 0:
        # Soft delete - mark as inactive
        await db.suppliers.update_one(
            {"id": supplier_id},
            {"$set": {"is_active": False, "updated_at": datetime.now(timezone.utc)}}
        )
        
        await log_audit(
            action="DEACTIVATE",
            entity_type="supplier",
            entity_id=supplier_id,
            user=current_user,
            details=f"Supplier deactivated (has {product_count} products)"
        )
        
        return {"message": f"Supplier deactivated (has {product_count} associated products)"}
    else:
        # Hard delete - no products associated
        await db.suppliers.delete_one({"id": supplier_id})
        
        await log_audit(
            action="DELETE",
            entity_type="supplier",
            entity_id=supplier_id,
            user=current_user,
            details="Supplier permanently deleted"
        )
        
        return {"message": "Supplier deleted permanently"}


@router.get("/stats/summary")
async def get_supplier_stats(current_user: dict = Depends(get_current_user)):
    """Get supplier statistics"""
    db = get_db()
    
    # Count suppliers
    total_suppliers = await db.suppliers.count_documents({})
    active_suppliers = await db.suppliers.count_documents({"is_active": True})
    
    # Get product counts by supplier
    pipeline = [
        {"$group": {
            "_id": "$supplier_name",
            "product_count": {"$sum": 1},
            "total_stock": {"$sum": "$stock"},
            "stock_value": {"$sum": {"$multiply": ["$stock", {"$ifNull": ["$cost_price", 0]}]}}
        }},
        {"$sort": {"product_count": -1}}
    ]
    
    by_supplier = await db.products.aggregate(pipeline).to_list(100)
    
    return {
        "total_suppliers": total_suppliers,
        "active_suppliers": active_suppliers,
        "inactive_suppliers": total_suppliers - active_suppliers,
        "products_by_supplier": [
            {
                "supplier": r["_id"] or "Unknown",
                "product_count": r["product_count"],
                "total_stock": r["total_stock"],
                "stock_value": round(r["stock_value"], 2)
            }
            for r in by_supplier
        ]
    }

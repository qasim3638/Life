"""
Store management routes
"""
import uuid
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, HTTPException, Depends

from config import get_db
from models import Store, StoreCreate
from services import get_current_user, is_admin_user, log_audit

router = APIRouter(prefix="/showrooms", tags=["Stores"])


@router.get("", response_model=List[dict])
async def get_showrooms(current_user: dict = Depends(get_current_user)):
    """Get all showrooms (all authenticated users can view)"""
    # All authenticated users can view showrooms (needed for day lock feature)
    db = get_db()
    raw = await db.showrooms.find({}).to_list(100000)
    # Normalise: every showroom MUST expose a stable `id` (frontend uses it as
    # React list key). A handful of legacy records lack `id`, so fall back to
    # the Mongo `_id`. Strip `_id` before returning (not JSON-serialisable).
    showrooms = []
    for s in raw:
        if not s.get("id"):
            s["id"] = str(s.get("_id"))
        s.pop("_id", None)
        showrooms.append(s)
    return showrooms


@router.post("")
async def create_showroom(input: StoreCreate, current_user: dict = Depends(get_current_user)):
    """Create a new showroom (admin only)"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    db = get_db()
    showroom_id = str(uuid.uuid4())
    
    showroom_dict = {
        "id": showroom_id,
        "name": input.name,
        "address": input.address,
        "phone": input.phone,
        "email": input.email,
        "lat": input.lat,
        "lng": input.lng,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.showrooms.insert_one(showroom_dict)
    
    # Audit log
    await log_audit(
        action="CREATE",
        entity_type="store",
        user=current_user,
        entity_id=showroom_id,
        entity_name=input.name,
        after_data={"name": input.name, "address": input.address, "phone": input.phone, "email": input.email},
        details=f"Store created: {input.name}"
    )
    
    # Return without _id
    showroom = await db.showrooms.find_one({"id": showroom_id}, {"_id": 0})
    return showroom


@router.put("/{showroom_id}")
async def update_showroom(showroom_id: str, input: StoreCreate, current_user: dict = Depends(get_current_user)):
    """Update a showroom (admin only)"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    db = get_db()
    
    # Get existing showroom for audit
    existing = await db.showrooms.find_one({"id": showroom_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Store not found")
    
    await db.showrooms.update_one(
        {"id": showroom_id},
        {"$set": {
            "name": input.name,
            "address": input.address,
            "phone": input.phone,
            "email": input.email,
            "lat": input.lat,
            "lng": input.lng
        }}
    )
    
    # Audit log
    await log_audit(
        action="UPDATE",
        entity_type="store",
        user=current_user,
        entity_id=showroom_id,
        entity_name=input.name,
        before_data={"name": existing.get("name"), "address": existing.get("address")},
        after_data={"name": input.name, "address": input.address},
        details=f"Store updated: {existing.get('name')} -> {input.name}"
    )
    
    showroom = await db.showrooms.find_one({"id": showroom_id}, {"_id": 0})
    return showroom


@router.delete("/{showroom_id}")
async def delete_showroom(showroom_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a showroom (admin only)"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    db = get_db()
    
    # Get existing showroom for audit
    existing = await db.showrooms.find_one({"id": showroom_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Store not found")
    
    await db.showrooms.delete_one({"id": showroom_id})
    
    # Remove showroom association from customers
    await db.users.update_many(
        {"showroom_id": showroom_id},
        {"$set": {"showroom_id": None}}
    )
    
    # Audit log
    await log_audit(
        action="DELETE",
        entity_type="store",
        user=current_user,
        entity_id=showroom_id,
        entity_name=existing.get("name"),
        before_data={"name": existing.get("name"), "address": existing.get("address")},
        details=f"Store deleted: {existing.get('name')}"
    )
    
    return {"message": "Store deleted successfully"}

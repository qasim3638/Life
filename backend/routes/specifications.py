"""
Specifications Management Routes
Product specifications system (Material, Finish, Size, Color, etc.)
"""
from fastapi import APIRouter, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel
from bson import ObjectId
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/specifications", tags=["Specifications"])

# Database connection
MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME", "tile_station")
client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]


# ============ MODELS ============

class SpecificationGroupCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = ""
    icon: Optional[str] = "Layers"
    color: Optional[str] = "#6b7280"
    display_order: Optional[int] = 0
    is_active: Optional[bool] = True


class SpecificationTypeCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = ""
    group_slug: Optional[str] = "general"
    field_name: str  # The actual field name in products (e.g., "material", "finish")
    display_order: Optional[int] = 0
    is_active: Optional[bool] = True
    auto_populate: Optional[bool] = True
    values: Optional[List[dict]] = []
    product_groups: Optional[List[str]] = []  # Which product groups this spec belongs to


class SpecificationValueCreate(BaseModel):
    value: str
    label: Optional[str] = ""
    description: Optional[str] = ""
    is_active: Optional[bool] = True
    product_groups: Optional[List[str]] = []


# ============ SPECIFICATION GROUPS ============

@router.get("/groups")
async def get_specification_groups():
    """Get all specification groups"""
    groups = await db.specification_groups.find().sort("display_order", 1).to_list(100)
    for g in groups:
        g["id"] = str(g.pop("_id"))
    return groups


@router.post("/groups")
async def create_specification_group(data: SpecificationGroupCreate):
    """Create a new specification group"""
    existing = await db.specification_groups.find_one({"slug": data.slug})
    if existing:
        raise HTTPException(status_code=400, detail="Group with this slug already exists")
    
    doc = {
        **data.dict(),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    result = await db.specification_groups.insert_one(doc)
    return {"id": str(result.inserted_id), "message": "Group created"}


@router.put("/groups/{group_id}")
async def update_specification_group(group_id: str, data: SpecificationGroupCreate):
    """Update a specification group"""
    result = await db.specification_groups.update_one(
        {"_id": ObjectId(group_id)},
        {"$set": {**data.dict(), "updated_at": datetime.now(timezone.utc)}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Group not found")
    return {"message": "Group updated"}


@router.delete("/groups/{group_id}")
async def delete_specification_group(group_id: str):
    """Delete a specification group"""
    # Check if there are specs in this group
    group = await db.specification_groups.find_one({"_id": ObjectId(group_id)})
    if group:
        specs_count = await db.specification_types.count_documents({"group_slug": group["slug"]})
        if specs_count > 0:
            raise HTTPException(status_code=400, detail=f"Cannot delete group with {specs_count} specifications")
    
    result = await db.specification_groups.delete_one({"_id": ObjectId(group_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Group not found")
    return {"message": "Group deleted"}


@router.post("/groups/reorder")
async def reorder_specification_groups(group_ids: List[str]):
    """Reorder specification groups"""
    for i, group_id in enumerate(group_ids):
        await db.specification_groups.update_one(
            {"_id": ObjectId(group_id)},
            {"$set": {"display_order": i}}
        )
    return {"message": "Groups reordered"}


# ============ SPECIFICATION TYPES ============

@router.get("/types")
async def get_specification_types():
    """Get all specification types"""
    types = await db.specification_types.find().sort("display_order", 1).to_list(100)
    for t in types:
        t["id"] = str(t.pop("_id"))
    return types


@router.get("/types/by-group")
async def get_specification_types_by_group():
    """Get specification types organized by group"""
    groups = await db.specification_groups.find().sort("display_order", 1).to_list(100)
    spec_types = await db.specification_types.find().sort("display_order", 1).to_list(100)
    
    for t in spec_types:
        t["id"] = str(t.pop("_id"))
    
    result = []
    for group in groups:
        group["id"] = str(group.pop("_id"))
        group["specifications"] = [t for t in spec_types if t.get("group_slug") == group["slug"]]
        result.append(group)
    
    # Add ungrouped specs
    ungrouped = [t for t in spec_types if not t.get("group_slug") or t.get("group_slug") == "general"]
    if ungrouped:
        result.append({
            "id": "ungrouped",
            "name": "General",
            "slug": "general",
            "icon": "Layers",
            "color": "#6b7280",
            "specifications": ungrouped
        })
    
    return result


@router.post("/types")
async def create_specification_type(data: SpecificationTypeCreate):
    """Create a new specification type"""
    existing = await db.specification_types.find_one({"slug": data.slug})
    if existing:
        raise HTTPException(status_code=400, detail="Specification type with this slug already exists")
    
    doc = {
        **data.dict(),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    result = await db.specification_types.insert_one(doc)
    return {"id": str(result.inserted_id), "message": "Specification type created"}


@router.put("/types/{type_id}")
async def update_specification_type(type_id: str, data: SpecificationTypeCreate):
    """Update a specification type - preserves values from DB if not explicitly changed"""
    update_data = {**data.dict(), "updated_at": datetime.now(timezone.utc)}
    
    # Get current spec from DB to preserve values
    current_spec = await db.specification_types.find_one({"_id": ObjectId(type_id)})
    if not current_spec:
        raise HTTPException(status_code=404, detail="Specification type not found")
    
    # MERGE strategy: preserve ALL existing values and only ADD new ones from incoming.
    # Values can only be deleted via the dedicated DELETE endpoint, not via PUT.
    incoming_values = update_data.get("values", [])
    existing_values = current_spec.get("values", [])
    
    if incoming_values:
        existing_map = {v.get("value"): v for v in existing_values}
        incoming_map = {v.get("value"): v for v in incoming_values}
        
        merged_values = []
        # Keep ALL existing values, update metadata from incoming if present
        for slug, existing_val in existing_map.items():
            if slug in incoming_map:
                # Merge: incoming updates metadata, but preserve product_groups
                merged = {**existing_val, **incoming_map[slug]}
                if "product_groups" in existing_val and "product_groups" not in incoming_map[slug]:
                    merged["product_groups"] = existing_val["product_groups"]
                merged_values.append(merged)
            else:
                # Value exists in DB but not in incoming — KEEP it (don't delete via PUT)
                merged_values.append(existing_val)
        
        # Add truly new values (in incoming but not in DB)
        for slug, incoming_val in incoming_map.items():
            if slug not in existing_map:
                merged_values.append(incoming_val)
        
        update_data["values"] = merged_values
    else:
        # No values in update — preserve existing values entirely
        update_data.pop("values", None)
    
    result = await db.specification_types.update_one(
        {"_id": ObjectId(type_id)},
        {"$set": update_data}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Specification type not found")
    return {"message": "Specification type updated"}


@router.delete("/types/{type_id}")
async def delete_specification_type(type_id: str):
    """Delete a specification type"""
    result = await db.specification_types.delete_one({"_id": ObjectId(type_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Specification type not found")
    return {"message": "Specification type deleted"}


@router.patch("/types/{type_id}/toggle-group")
async def toggle_spec_type_group(type_id: str, data: dict):
    """Add or remove a product group from a spec type"""
    product_group = data.get("product_group")
    action = data.get("action", "add")
    
    if not product_group:
        raise HTTPException(status_code=400, detail="product_group is required")
    
    spec = await db.specification_types.find_one({"_id": ObjectId(type_id)})
    if not spec:
        raise HTTPException(status_code=404, detail="Specification type not found")
    
    current_groups = spec.get("product_groups", [])
    
    if action == "add":
        if product_group not in current_groups:
            current_groups.append(product_group)
    elif action == "remove":
        current_groups = [g for g in current_groups if g != product_group]
    
    await db.specification_types.update_one(
        {"_id": ObjectId(type_id)},
        {"$set": {"product_groups": current_groups}}
    )
    return {"message": f"Spec type {'added to' if action == 'add' else 'removed from'} {product_group}", "product_groups": current_groups}


@router.post("/types/bulk-assign-group")
async def bulk_assign_spec_type_group(data: dict):
    """Bulk add or remove a product group from multiple spec types at once.
    Body: {"type_ids": ["id1","id2",...], "product_group": "tiles", "action": "add"|"remove"}
    """
    type_ids = data.get("type_ids", [])
    product_group = data.get("product_group")
    action = data.get("action", "add")

    if not type_ids or not product_group:
        raise HTTPException(status_code=400, detail="type_ids and product_group are required")

    updated = 0
    for tid in type_ids:
        try:
            spec = await db.specification_types.find_one({"_id": ObjectId(tid)})
            if not spec:
                continue
            current = spec.get("product_groups", [])
            if action == "add" and product_group not in current:
                current.append(product_group)
            elif action == "remove":
                current = [g for g in current if g != product_group]
            await db.specification_types.update_one(
                {"_id": ObjectId(tid)},
                {"$set": {"product_groups": current, "updated_at": datetime.now(timezone.utc)}}
            )
            updated += 1
        except Exception:
            continue

    return {"message": f"{updated} spec types updated", "updated": updated}





@router.post("/types/{type_id}/values")
async def add_specification_value(type_id: str, data: SpecificationValueCreate):
    """Add a value to a specification type"""
    spec_type = await db.specification_types.find_one({"_id": ObjectId(type_id)})
    if not spec_type:
        raise HTTPException(status_code=404, detail="Specification type not found")
    
    values = spec_type.get("values", [])
    
    # Check if value already exists
    if any(v.get("value") == data.value for v in values):
        raise HTTPException(status_code=400, detail="Value already exists")
    
    new_val = {
        "value": data.value,
        "label": data.label or data.value,
        "description": data.description,
        "is_active": data.is_active
    }
    if data.product_groups:
        new_val["product_groups"] = data.product_groups
    values.append(new_val)
    
    await db.specification_types.update_one(
        {"_id": ObjectId(type_id)},
        {"$set": {"values": values, "updated_at": datetime.now(timezone.utc)}}
    )
    
    # Sync to filter_types if this is a shared attribute
    try:
        from utils.attribute_sync import sync_on_spec_value_add
        sync_result = await sync_on_spec_value_add(db, spec_type["slug"], data.value, data.label or data.value)
        logger.info(f"Attribute sync result: {sync_result}")
    except Exception as e:
        logger.warning(f"Failed to sync spec value to filters: {e}")
    
    return {"message": "Value added"}


@router.delete("/types/{type_id}/values/{value}")
async def remove_specification_value(type_id: str, value: str):
    """Remove a value from a specification type"""
    spec_type = await db.specification_types.find_one({"_id": ObjectId(type_id)})
    if not spec_type:
        raise HTTPException(status_code=404, detail="Specification type not found")
    
    values = [v for v in spec_type.get("values", []) if v.get("value") != value]
    
    await db.specification_types.update_one(
        {"_id": ObjectId(type_id)},
        {"$set": {"values": values, "updated_at": datetime.now(timezone.utc)}}
    )
    
    # Sync deletion to filter_types if this is a shared attribute
    try:
        from utils.attribute_sync import sync_on_spec_value_delete
        sync_result = await sync_on_spec_value_delete(db, spec_type["slug"], value)
        logger.info(f"Attribute sync deletion result: {sync_result}")
    except Exception as e:
        logger.warning(f"Failed to sync spec value deletion to filters: {e}")
    
    return {"message": "Value removed"}


@router.patch("/types/{type_id}/toggle-type-visibility")
async def toggle_spec_type_visibility(type_id: str, data: dict):
    """Hide or show an entire spec type for a specific product group.
    Body: {"product_group": "materials", "action": "hide" | "show"}
    """
    product_group = data.get("product_group")
    action = data.get("action", "hide")
    
    if not product_group:
        raise HTTPException(status_code=400, detail="product_group is required")
    
    spec_type = await db.specification_types.find_one({"_id": ObjectId(type_id)})
    if not spec_type:
        raise HTTPException(status_code=404, detail="Specification type not found")
    
    hidden_groups = spec_type.get("hidden_groups", [])
    
    if action == "hide":
        if product_group not in hidden_groups:
            hidden_groups.append(product_group)
    elif action == "show":
        hidden_groups = [g for g in hidden_groups if g != product_group]
    
    await db.specification_types.update_one(
        {"_id": ObjectId(type_id)},
        {"$set": {"hidden_groups": hidden_groups, "updated_at": datetime.now(timezone.utc)}}
    )
    
    return {
        "message": f"Specification '{spec_type.get('name')}' {'hidden from' if action == 'hide' else 'shown in'} {product_group}",
        "hidden_groups": hidden_groups
    }


@router.patch("/types/{type_id}/values/{value_slug}/toggle-group")
async def toggle_spec_value_group(type_id: str, value_slug: str, data: dict):
    """Toggle a product group's visibility for a specific spec value.
    Body: {"product_group": "flooring", "action": "remove" | "add"}
    """
    product_group = data.get("product_group")
    action = data.get("action", "remove")
    
    if not product_group:
        raise HTTPException(status_code=400, detail="product_group is required")
    
    spec_type = await db.specification_types.find_one({"_id": ObjectId(type_id)})
    if not spec_type:
        raise HTTPException(status_code=404, detail="Specification type not found")
    
    values = spec_type.get("values", [])
    target_value = None
    for v in values:
        if v.get("value") == value_slug:
            target_value = v
            break
    
    if not target_value:
        raise HTTPException(status_code=404, detail=f"Value '{value_slug}' not found")
    
    current_groups = target_value.get("product_groups", [])
    
    if action == "remove":
        if not current_groups:
            all_groups = await db.category_groups.distinct("slug")
            if not all_groups:
                all_groups = ["tiles", "flooring", "bathroom", "outdoor"]
            current_groups = [g for g in all_groups if g != product_group]
        else:
            current_groups = [g for g in current_groups if g != product_group]
    elif action == "add":
        if product_group not in current_groups:
            current_groups.append(product_group)
        all_groups = await db.category_groups.distinct("slug")
        if all_groups and set(current_groups) >= set(all_groups):
            current_groups = []
    
    await db.specification_types.update_one(
        {"_id": ObjectId(type_id), "values.value": value_slug},
        {
            "$set": {
                "values.$.product_groups": current_groups,
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )
    
    return {
        "message": f"Value '{value_slug}' {'removed from' if action == 'remove' else 'added to'} {product_group}",
        "value": value_slug,
        "product_groups": current_groups
    }




# ============ AUTO-POPULATE FROM PRODUCTS ============

@router.post("/types/{type_id}/sync")
async def sync_specification_values(type_id: str, source: str = "tiles"):
    """Sync values from products for a specification type"""
    spec_type = await db.specification_types.find_one({"_id": ObjectId(type_id)})
    if not spec_type:
        raise HTTPException(status_code=404, detail="Specification type not found")
    
    field_name = spec_type.get("field_name")
    if not field_name:
        raise HTTPException(status_code=400, detail="No field_name configured for this specification. Edit the spec and set a field name first.")
    
    # Get collection to query
    collection = db.tiles if source == "tiles" else db.supplier_products
    
    # Get distinct values from products
    product_values = await collection.distinct(field_name)
    
    # Filter out empty values
    product_values = [v for v in product_values if v and str(v).strip()]
    
    # Get existing values
    existing_values = {v.get("value"): v for v in spec_type.get("values", [])}
    
    # Add new values
    new_count = 0
    for val in product_values:
        if val not in existing_values:
            existing_values[val] = {
                "value": val,
                "label": val,
                "description": "",
                "is_active": True
            }
            new_count += 1
    
    await db.specification_types.update_one(
        {"_id": ObjectId(type_id)},
        {"$set": {"values": list(existing_values.values()), "updated_at": datetime.now(timezone.utc)}}
    )
    
    return {"message": f"Synced {new_count} new values", "total": len(existing_values)}


@router.post("/sync-all")
async def sync_all_specifications(source: str = "tiles"):
    """Sync all auto-populate specifications from products"""
    spec_types = await db.specification_types.find({"auto_populate": True}).to_list(100)
    
    results = []
    for spec_type in spec_types:
        field_name = spec_type.get("field_name")
        if not field_name:
            continue
        
        collection = db.tiles if source == "tiles" else db.supplier_products
        product_values = await collection.distinct(field_name)
        product_values = [v for v in product_values if v and str(v).strip()]
        
        existing_values = {v.get("value"): v for v in spec_type.get("values", [])}
        
        new_count = 0
        for val in product_values:
            if val not in existing_values:
                existing_values[val] = {
                    "value": val,
                    "label": val,
                    "description": "",
                    "is_active": True
                }
                new_count += 1
        
        await db.specification_types.update_one(
            {"_id": spec_type["_id"]},
            {"$set": {"values": list(existing_values.values()), "updated_at": datetime.now(timezone.utc)}}
        )
        
        results.append({
            "name": spec_type["name"],
            "new_values": new_count,
            "total": len(existing_values)
        })
    
    return {"results": results}


# ============ SEED DEFAULT SPECIFICATIONS ============

@router.post("/seed-defaults")
async def seed_default_specifications():
    """Seed default specification groups and types"""
    # Create default groups
    default_groups = [
        {"name": "Physical Properties", "slug": "physical", "icon": "Box", "color": "#3b82f6", "display_order": 0},
        {"name": "Appearance", "slug": "appearance", "icon": "Palette", "color": "#8b5cf6", "display_order": 1},
        {"name": "Technical", "slug": "technical", "icon": "Settings", "color": "#10b981", "display_order": 2},
    ]
    
    for group in default_groups:
        existing = await db.specification_groups.find_one({"slug": group["slug"]})
        if not existing:
            group["created_at"] = datetime.now(timezone.utc)
            group["updated_at"] = datetime.now(timezone.utc)
            group["is_active"] = True
            await db.specification_groups.insert_one(group)
    
    # Create default specification types
    default_types = [
        {"name": "Material", "slug": "material", "field_name": "material", "group_slug": "physical", "auto_populate": True, "display_order": 0},
        {"name": "Size", "slug": "size", "field_name": "size", "group_slug": "physical", "auto_populate": True, "display_order": 1},
        {"name": "Finish", "slug": "finish", "field_name": "finish", "group_slug": "appearance", "auto_populate": True, "display_order": 0},
        {"name": "Color", "slug": "color", "field_name": "color", "group_slug": "appearance", "auto_populate": True, "display_order": 1},
    ]
    
    created = 0
    for spec_type in default_types:
        existing = await db.specification_types.find_one({"slug": spec_type["slug"]})
        if not existing:
            spec_type["created_at"] = datetime.now(timezone.utc)
            spec_type["updated_at"] = datetime.now(timezone.utc)
            spec_type["is_active"] = True
            spec_type["values"] = []
            spec_type["description"] = ""
            await db.specification_types.insert_one(spec_type)
            created += 1
    
    return {"message": f"Seeded {len(default_groups)} groups and {created} specification types"}


# ============ PUBLIC ENDPOINTS ============

@router.get("/public")
async def get_public_specifications():
    """Get active specifications for the public shop"""
    spec_types = await db.specification_types.find({"is_active": True}).sort("display_order", 1).to_list(100)
    
    result = []
    for t in spec_types:
        active_values = [v for v in t.get("values", []) if v.get("is_active", True)]
        if active_values:
            result.append({
                "name": t["name"],
                "slug": t["slug"],
                "field_name": t.get("field_name"),
                "values": active_values
            })
    
    return result

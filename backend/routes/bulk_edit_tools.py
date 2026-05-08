"""
Bulk Edit Tools - History/Audit Log, Presets, Undo, and Snapshot endpoints
for the Bulk Category Editor in SupplierProducts admin page.
"""
from fastapi import APIRouter, HTTPException
from pymongo import MongoClient
from datetime import datetime, timezone
import logging
import uuid
import os

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/bulk-edit-tools", tags=["bulk-edit-tools"])

def get_db():
    mongo_url = os.environ.get('MONGO_URL')
    if not mongo_url:
        raise ValueError("MONGO_URL environment variable is required")
    client = MongoClient(mongo_url)
    return client[os.environ.get('DB_NAME', 'tile_station')]


# ============ HISTORY / AUDIT LOG ============

@router.post("/history")
def save_edit_history(data: dict):
    db = get_db()
    entry = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user": data.get("user", "admin"),
        "action": data.get("action", "bulk_update"),
        "product_count": data.get("product_count", 0),
        "product_ids": data.get("product_ids", []),
        "id_field": data.get("id_field", "sku"),
        "changes_summary": data.get("changes_summary", {}),
        "before_snapshot": data.get("before_snapshot", []),
        "updates_applied": data.get("updates_applied", {}),
        "mode": data.get("mode", "replace"),
        "supplier": data.get("supplier", ""),
        "undone": False,
    }
    db.bulk_edit_history.insert_one(entry)
    return {"id": entry["id"], "status": "saved"}


@router.get("/history")
def get_edit_history(limit: int = 50, supplier: str = None):
    db = get_db()
    query = {}
    if supplier:
        query["supplier"] = supplier
    entries = list(
        db.bulk_edit_history.find(query, {"_id": 0})
        .sort("timestamp", -1)
        .limit(limit)
    )
    return entries


@router.post("/history/{history_id}/undo")
def undo_edit(history_id: str):
    db = get_db()
    entry = db.bulk_edit_history.find_one({"id": history_id}, {"_id": 0})
    if not entry:
        raise HTTPException(status_code=404, detail="History entry not found")
    if entry.get("undone"):
        raise HTTPException(status_code=400, detail="This edit has already been undone")

    before_snapshot = entry.get("before_snapshot", [])
    if not before_snapshot:
        raise HTTPException(status_code=400, detail="No snapshot available for undo")

    id_field = entry.get("id_field", "sku")
    updates_applied = entry.get("updates_applied", {})
    restored_count = 0

    for product_snap in before_snapshot:
        product_id = product_snap.get(id_field)
        if not product_id:
            continue

        restore_update = {}
        for field in updates_applied.keys():
            if field in product_snap:
                restore_update[field] = product_snap[field]
            else:
                restore_update[field] = None

        if not restore_update:
            continue

        set_ops = {k: v for k, v in restore_update.items() if v is not None}
        unset_ops = {k: "" for k, v in restore_update.items() if v is None}

        for collection in [db.sync_staging, db.supplier_products, db.products, db.tiles]:
            update_doc = {}
            if set_ops:
                update_doc["$set"] = set_ops
            if unset_ops:
                update_doc["$unset"] = unset_ops
            if update_doc:
                collection.update_many({id_field: product_id}, update_doc)

        restored_count += 1

    db.bulk_edit_history.update_one(
        {"id": history_id},
        {"$set": {"undone": True, "undone_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"status": "undone", "restored_count": restored_count}


# ============ SNAPSHOT ============

@router.post("/snapshot")
def take_snapshot(data: dict):
    db = get_db()
    product_ids = data.get("product_ids", [])
    id_field = data.get("id_field", "sku")
    fields = data.get("fields", [])

    if not product_ids:
        return {"snapshot": []}

    projection = {"_id": 0, id_field: 1, "product_name": 1, "name": 1}
    for f in fields:
        projection[f] = 1

    products = list(
        db.supplier_products.find({id_field: {"$in": product_ids}}, projection)
    )
    return {"snapshot": products}


# ============ PRESETS ============

@router.get("/presets")
def get_presets(product_group: str = None):
    db = get_db()
    query = {}
    if product_group:
        query["$or"] = [{"product_group": product_group}, {"product_group": ""}]
    presets = list(
        db.bulk_edit_presets.find(query, {"_id": 0}).sort("created_at", -1)
    )
    return presets


@router.post("/presets")
def save_preset(data: dict):
    db = get_db()
    name = data.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Preset name is required")

    existing = db.bulk_edit_presets.find_one({"name": name})
    if existing:
        raise HTTPException(status_code=409, detail=f"Preset '{name}' already exists")

    preset = {
        "id": str(uuid.uuid4()),
        "name": name,
        "description": data.get("description", ""),
        "selections": data.get("selections", {}),
        "product_group": data.get("product_group", ""),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    db.bulk_edit_presets.insert_one(preset)
    return {"id": preset["id"], "name": preset["name"], "status": "saved"}


@router.put("/presets/{preset_id}")
def update_preset(preset_id: str, data: dict):
    db = get_db()
    update = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if "name" in data:
        update["name"] = data["name"]
    if "description" in data:
        update["description"] = data["description"]
    if "selections" in data:
        update["selections"] = data["selections"]
    if "product_group" in data:
        update["product_group"] = data["product_group"]

    result = db.bulk_edit_presets.update_one({"id": preset_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Preset not found")
    return {"status": "updated"}


@router.delete("/presets/{preset_id}")
def delete_preset(preset_id: str):
    db = get_db()
    result = db.bulk_edit_presets.delete_one({"id": preset_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Preset not found")
    return {"status": "deleted"}



# ============ DRAFTS (Auto-save) ============

@router.get("/draft")
def get_draft(user: str = "admin"):
    db = get_db()
    draft = db.bulk_edit_drafts.find_one({"user": user}, {"_id": 0})
    if not draft:
        return None
    return draft


@router.post("/draft")
def save_draft(data: dict):
    db = get_db()
    user = data.get("user", "admin")
    draft = {
        "user": user,
        "selections": data.get("selections", {}),
        "selected_products": data.get("selected_products", []),
        "product_group": data.get("product_group", ""),
        "supplier": data.get("supplier", ""),
        "per_attribute_scopes": data.get("per_attribute_scopes", {}),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    db.bulk_edit_drafts.update_one(
        {"user": user},
        {"$set": draft},
        upsert=True,
    )
    return {"status": "saved", "updated_at": draft["updated_at"]}


@router.delete("/draft")
def delete_draft(user: str = "admin"):
    db = get_db()
    db.bulk_edit_drafts.delete_many({"user": user})
    return {"status": "cleared"}

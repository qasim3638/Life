"""
Bathroom Page Routes - Manages the bathroom landing page content,
catalogue downloads with auth gating, and download analytics.
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
from config import get_db
import uuid
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/bathroom", tags=["bathroom"])
db = get_db()


# ============ MODELS ============

class BathroomPageContent(BaseModel):
    hero_title: Optional[str] = None
    hero_subtitle: Optional[str] = None
    hero_description: Optional[str] = None
    hero_image_url: Optional[str] = None
    video_url: Optional[str] = None
    video_thumbnail_url: Optional[str] = None
    public_discount: Optional[str] = None
    trade_discount: Optional[str] = None
    catalogue_path: Optional[str] = None
    catalogue_filename: Optional[str] = None
    features: Optional[List[dict]] = None
    how_to_order_title: Optional[str] = None
    how_to_order_intro: Optional[str] = None
    how_to_order_channels: Optional[List[dict]] = None
    trade_credit_back_text: Optional[str] = None
    content_sections: Optional[List[dict]] = None
    review_quote: Optional[str] = None
    review_author: Optional[str] = None
    cta_title: Optional[str] = None
    cta_description: Optional[str] = None


# ============ HELPER ============

def deep_merge(base: dict, updates: dict) -> dict:
    merged = dict(base)
    for k, v in updates.items():
        if isinstance(v, dict) and isinstance(merged.get(k), dict):
            merged[k] = deep_merge(merged[k], v)
        else:
            merged[k] = v
    return merged


# ============ PUBLIC ENDPOINTS ============

@router.get("/page")
async def get_bathroom_page():
    """Public endpoint - get bathroom page content"""
    doc = await db.page_content.find_one({"page_key": "bathroom"}, {"_id": 0})
    return doc.get("content", {}) if doc else {}


@router.get("/catalogue/download")
async def download_catalogue(user_id: str = None, user_type: str = "public"):
    """Download catalogue - tracks the download"""
    doc = await db.page_content.find_one({"page_key": "bathroom"}, {"_id": 0})
    content = doc.get("content", {}) if doc else {}
    catalogue_path = content.get("catalogue_path")

    if not catalogue_path:
        raise HTTPException(status_code=404, detail="No catalogue available")

    # Track download
    await db.bathroom_downloads.insert_one({
        "user_id": user_id,
        "user_type": user_type,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
    })

    from services.object_storage import get_object
    from fastapi.responses import Response

    try:
        data, content_type = get_object(catalogue_path)
        filename = content.get("catalogue_filename", "bathroom-catalogue.pdf")
        return Response(
            content=data,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        logger.error(f"Failed to serve catalogue: {e}")
        raise HTTPException(status_code=500, detail="Failed to download catalogue")


# ============ ADMIN ENDPOINTS ============

@router.put("/page")
async def update_bathroom_page(content: BathroomPageContent):
    """Admin - update bathroom page content"""
    data = {k: v for k, v in content.dict().items() if v is not None}
    existing = await db.page_content.find_one({"page_key": "bathroom"}, {"_id": 0})
    merged = deep_merge(existing.get("content", {}) if existing else {}, data)

    await db.page_content.update_one(
        {"page_key": "bathroom"},
        {"$set": {"page_key": "bathroom", "content": merged, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return {"message": "Bathroom page updated"}


@router.post("/catalogue/upload")
async def upload_catalogue(file: UploadFile = File(...)):
    """Admin - upload bathroom catalogue PDF"""
    from services.object_storage import put_object

    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    data = await file.read()
    if len(data) > 250 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Maximum 250MB.")

    path = f"tile-station/bathroom/catalogue/{uuid.uuid4()}.pdf"
    put_object(path, data, "application/pdf")

    # Save path to page content
    existing = await db.page_content.find_one({"page_key": "bathroom"}, {"_id": 0})
    merged = deep_merge(existing.get("content", {}) if existing else {}, {
        "catalogue_path": path,
        "catalogue_filename": file.filename,
    })
    await db.page_content.update_one(
        {"page_key": "bathroom"},
        {"$set": {"page_key": "bathroom", "content": merged, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )

    return {"path": path, "filename": file.filename, "size": len(data)}


@router.get("/downloads/stats")
async def get_download_stats():
    """Admin - get download analytics"""
    pipeline = [
        {"$group": {
            "_id": "$user_type",
            "count": {"$sum": 1},
        }}
    ]
    results = await db.bathroom_downloads.aggregate(pipeline).to_list(100)
    stats = {r["_id"]: r["count"] for r in results}

    total = await db.bathroom_downloads.count_documents({})
    recent = await db.bathroom_downloads.find(
        {}, {"_id": 0}
    ).sort("downloaded_at", -1).limit(10).to_list(10)

    return {
        "total": total,
        "public": stats.get("public", 0),
        "trade": stats.get("trade", 0),
        "recent": recent,
    }

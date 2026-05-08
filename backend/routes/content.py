"""
Content management routes for editable page content
"""
from fastapi import APIRouter
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
import os

router = APIRouter(prefix="/content", tags=["Content"])

# MongoDB connection
mongo_url = os.environ.get('MONGO_URL')
db_name = os.environ.get('DB_NAME', 'tile_epos_db')
client = AsyncIOMotorClient(mongo_url)
db = client[db_name]


@router.get("/{page_key}")
async def get_page_content(page_key: str):
    """Get editable content for a specific page"""
    doc = await db.page_content.find_one({"page_key": page_key}, {"_id": 0})
    if doc:
        return doc.get("content", {})
    return {}


@router.put("/{page_key}")
async def update_page_content(page_key: str, content: dict):
    """Update editable content for a specific page (admin only)"""
    await db.page_content.update_one(
        {"page_key": page_key},
        {"$set": {
            "page_key": page_key, 
            "content": content, 
            "updated_at": datetime.utcnow()
        }},
        upsert=True
    )
    return {"success": True, "message": f"Content for {page_key} updated"}

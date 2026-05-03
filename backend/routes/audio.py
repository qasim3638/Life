"""Audio library: wisdom stories, sleep stories, meditation music."""
from fastapi import APIRouter
from typing import Optional
from db import db

router = APIRouter()


@router.get("/audio")
async def list_audio(category: Optional[str] = None):
    q: dict = {}
    if category:
        q["category"] = category
    return await db.audio_library.find(q, {"_id": 0}).to_list(500)

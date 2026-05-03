"""Curated content: quotes, podcasts, meditations, affirmations. Also allows user-added YouTube items."""
import re
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from db import db
from models import new_id

router = APIRouter()
logger = logging.getLogger(__name__)


# Capture id from all common YouTube URL forms.
_YT_PATTERNS = [
    r"youtube\.com/watch\?v=([A-Za-z0-9_-]{11})",
    r"youtu\.be/([A-Za-z0-9_-]{11})",
    r"youtube\.com/embed/([A-Za-z0-9_-]{11})",
    r"youtube\.com/shorts/([A-Za-z0-9_-]{11})",
    r"^([A-Za-z0-9_-]{11})$",
]


def extract_youtube_id(value: str) -> Optional[str]:
    v = (value or "").strip()
    if not v:
        return None
    for p in _YT_PATTERNS:
        m = re.search(p, v)
        if m:
            return m.group(1)
    return None


class PodcastCreate(BaseModel):
    title: str
    url_or_id: str
    host: str = ""
    category: str = "Wisdom"
    duration: str = ""


class MeditationCreate(BaseModel):
    title: str
    url_or_id: str
    category: str = "Guided"
    duration: str = ""
    description: str = ""


@router.get("/quotes")
async def list_quotes():
    return await db.quotes.find({}, {"_id": 0}).to_list(500)


@router.get("/podcasts")
async def list_podcasts():
    return await db.podcasts.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)


@router.post("/podcasts")
async def create_podcast(payload: PodcastCreate):
    yid = extract_youtube_id(payload.url_or_id)
    if not yid:
        raise HTTPException(400, "Paste a valid YouTube URL or 11-char video ID")
    doc = {
        "id": new_id(),
        "title": payload.title.strip() or "Untitled",
        "youtube_id": yid,
        "host": payload.host.strip(),
        "category": payload.category.strip() or "Wisdom",
        "duration": payload.duration.strip(),
        "is_custom": True,
        "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    }
    await db.podcasts.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


@router.delete("/podcasts/{pid}")
async def delete_podcast(pid: str):
    # Only allow deleting user-added entries
    res = await db.podcasts.delete_one({"id": pid, "is_custom": True})
    if res.deleted_count == 0:
        raise HTTPException(404, "Not found or not deletable")
    return {"ok": True}


@router.get("/meditations")
async def list_meditations():
    return await db.meditations.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)


@router.post("/meditations")
async def create_meditation(payload: MeditationCreate):
    yid = extract_youtube_id(payload.url_or_id)
    if not yid:
        raise HTTPException(400, "Paste a valid YouTube URL or 11-char video ID")
    doc = {
        "id": new_id(),
        "title": payload.title.strip() or "Untitled",
        "youtube_id": yid,
        "category": payload.category.strip() or "Guided",
        "duration": payload.duration.strip(),
        "description": payload.description.strip(),
        "is_custom": True,
        "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    }
    await db.meditations.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


@router.delete("/meditations/{mid}")
async def delete_meditation(mid: str):
    res = await db.meditations.delete_one({"id": mid, "is_custom": True})
    if res.deleted_count == 0:
        raise HTTPException(404, "Not found or not deletable")
    return {"ok": True}


@router.get("/affirmations")
async def list_affirmations():
    return await db.affirmations.find({}, {"_id": 0}).to_list(500)

"""Sobriety / Addictions tracking + AI compassionate support."""
import logging
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from db import db
from models import new_id, now_iso
from ai_helper import run_ai, AI_SYSTEM_MSG

router = APIRouter()
logger = logging.getLogger(__name__)


def _days_between(iso_a: str, iso_b: str) -> int:
    try:
        a = datetime.fromisoformat(iso_a.replace("Z", "+00:00"))
        b = datetime.fromisoformat(iso_b.replace("Z", "+00:00"))
        return max(0, (b - a).days)
    except Exception:
        return 0


class Addiction(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str
    started_clean: str = Field(default_factory=now_iso)
    longest_streak_days: int = 0
    reset_count: int = 0
    notes: str = ""
    created_at: str = Field(default_factory=now_iso)


class AddictionCreate(BaseModel):
    name: str
    notes: str = ""


class AddictionUpdate(BaseModel):
    name: Optional[str] = None
    notes: Optional[str] = None


class Slip(BaseModel):
    id: str = Field(default_factory=new_id)
    addiction_id: str
    at: str = Field(default_factory=now_iso)
    note: str = ""
    streak_days_before: int = 0


class SlipCreate(BaseModel):
    note: str = ""


@router.post("/addictions", response_model=Addiction)
async def create_addiction(payload: AddictionCreate):
    a = Addiction(**payload.model_dump())
    await db.addictions.insert_one(a.model_dump())
    return a


@router.get("/addictions", response_model=List[Addiction])
async def list_addictions():
    return await db.addictions.find({}, {"_id": 0}).sort("created_at", 1).to_list(50)


@router.put("/addictions/{addiction_id}", response_model=Addiction)
async def update_addiction(addiction_id: str, payload: AddictionUpdate):
    update = {k: v for k, v in payload.model_dump().items() if v is not None}
    if update:
        res = await db.addictions.update_one({"id": addiction_id}, {"$set": update})
        if res.matched_count == 0:
            raise HTTPException(404, "Not found")
    item = await db.addictions.find_one({"id": addiction_id}, {"_id": 0})
    if not item:
        raise HTTPException(404, "Not found")
    return item


@router.delete("/addictions/{addiction_id}")
async def delete_addiction(addiction_id: str):
    await db.addictions.delete_one({"id": addiction_id})
    await db.slips.delete_many({"addiction_id": addiction_id})
    return {"ok": True}


@router.post("/addictions/{addiction_id}/slip", response_model=Slip)
async def log_slip(addiction_id: str, payload: SlipCreate):
    a = await db.addictions.find_one({"id": addiction_id}, {"_id": 0})
    if not a:
        raise HTTPException(404, "Not found")
    streak_before = _days_between(a["started_clean"], now_iso())
    longest = max(a.get("longest_streak_days", 0), streak_before)
    slip = Slip(addiction_id=addiction_id, note=payload.note, streak_days_before=streak_before)
    await db.slips.insert_one(slip.model_dump())
    await db.addictions.update_one(
        {"id": addiction_id},
        {
            "$set": {
                "started_clean": now_iso(),
                "longest_streak_days": longest,
            },
            "$inc": {"reset_count": 1},
        },
    )
    return slip


@router.get("/addictions/{addiction_id}/slips", response_model=List[Slip])
async def list_slips(addiction_id: str):
    return await db.slips.find({"addiction_id": addiction_id}, {"_id": 0}).sort("at", -1).to_list(200)


@router.post("/ai/sobriety-support/{addiction_id}")
async def ai_sobriety_support(addiction_id: str):
    a = await db.addictions.find_one({"id": addiction_id}, {"_id": 0})
    if not a:
        raise HTTPException(404, "Not found")
    streak = _days_between(a["started_clean"], now_iso())
    slips = await db.slips.find({"addiction_id": addiction_id}, {"_id": 0}).sort("at", -1).to_list(5)
    recent_notes = [s.get("note", "") for s in slips if s.get("note")]

    prompt = (
        "The user is working to stay free from a habit. Write 90-120 words of warm, compassionate "
        "support — not advice, not lecture. Acknowledge effort. Name one small grounding action they "
        "can take in the next 30 minutes. Never moralise. Never use the word 'just'. "
        f"Habit: {a['name']}. Current sober streak: {streak} day(s). "
        f"Longest streak ever: {a.get('longest_streak_days', 0)} days. "
        f"Total resets: {a.get('reset_count', 0)}. "
        f"Recent slip context: {recent_notes[:3] if recent_notes else 'none shared'}."
    )
    try:
        text = await run_ai(AI_SYSTEM_MSG, prompt)
        return {"text": text, "data": {"streak_days": streak, "longest": a.get("longest_streak_days", 0)}}
    except Exception as e:
        logger.error(f"sobriety support error: {e}")
        return {"text": "You're still here. That counts. Drink a glass of water and step outside for two minutes.", "error": str(e)}

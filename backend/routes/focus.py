"""Focus / Time-management endpoints: sessions, distractions, AI focus tips."""
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field

from db import db
from models import new_id, now_iso, AIPrompt
from ai_helper import run_ai, AI_SYSTEM_MSG

router = APIRouter()
logger = logging.getLogger(__name__)


class FocusSession(BaseModel):
    id: str = Field(default_factory=new_id)
    task: str = ""
    planned_min: int = 25
    actual_min: int = 0
    started_at: str = Field(default_factory=now_iso)
    ended_at: Optional[str] = ""
    completed: bool = False
    note: str = ""


class FocusSessionCreate(BaseModel):
    task: str = ""
    planned_min: int = 25
    actual_min: int = 0
    completed: bool = False
    note: str = ""


class Distraction(BaseModel):
    id: str = Field(default_factory=new_id)
    at: str = Field(default_factory=now_iso)
    trigger: str = ""  # phone, notification, hunger, person, thought, other
    note: str = ""
    session_id: Optional[str] = ""


class DistractionCreate(BaseModel):
    trigger: str = ""
    note: str = ""
    session_id: Optional[str] = ""


@router.post("/focus-sessions", response_model=FocusSession)
async def create_session(payload: FocusSessionCreate):
    s = FocusSession(**payload.model_dump(), ended_at=now_iso())
    await db.focus_sessions.insert_one(s.model_dump())
    return s


@router.get("/focus-sessions", response_model=List[FocusSession])
async def list_sessions():
    return await db.focus_sessions.find({}, {"_id": 0}).sort("started_at", -1).to_list(200)


@router.post("/distractions", response_model=Distraction)
async def create_distraction(payload: DistractionCreate):
    d = Distraction(**payload.model_dump())
    await db.distractions.insert_one(d.model_dump())
    return d


@router.get("/distractions", response_model=List[Distraction])
async def list_distractions():
    return await db.distractions.find({}, {"_id": 0}).sort("at", -1).to_list(500)


@router.get("/focus-stats")
async def focus_stats():
    today = datetime.now(timezone.utc).date().isoformat()
    sessions = await db.focus_sessions.find(
        {"started_at": {"$gte": today}}, {"_id": 0}
    ).to_list(200)
    distractions = await db.distractions.find(
        {"at": {"$gte": today}}, {"_id": 0}
    ).to_list(500)
    return {
        "today_focus_min": sum(s.get("actual_min") or 0 for s in sessions),
        "today_sessions": len(sessions),
        "today_completed_sessions": sum(1 for s in sessions if s.get("completed")),
        "today_distractions": len(distractions),
    }


@router.post("/ai/focus-tips")
async def ai_focus_tips(_: AIPrompt | None = None):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    distractions = await db.distractions.find(
        {"at": {"$gte": cutoff}}, {"_id": 0}
    ).sort("at", -1).to_list(100)
    sessions = await db.focus_sessions.find(
        {"started_at": {"$gte": cutoff}}, {"_id": 0}
    ).to_list(100)

    triggers = {}
    for d in distractions:
        t = (d.get("trigger") or "other").lower()
        triggers[t] = triggers.get(t, 0) + 1
    top = sorted(triggers.items(), key=lambda x: -x[1])[:5]
    summary = (
        f"Past 7 days: {len(sessions)} focus sessions, "
        f"{sum(1 for s in sessions if s.get('completed'))} completed, "
        f"{len(distractions)} distractions logged. "
        f"Top triggers: {', '.join(f'{k}({v})' for k,v in top) if top else 'none'}."
    )

    prompt = (
        "Based on the user's recent focus pattern below, write 3 specific, doable, kind suggestions "
        "for protecting attention. Be concrete (not 'try meditating') — name the actual trigger and "
        "the specific countermeasure. 150 words max. No bullets longer than 2 lines.\n\n"
        f"Data: {summary}"
    )
    try:
        text = await run_ai(AI_SYSTEM_MSG, prompt)
        return {"text": text, "data": {"sessions": len(sessions), "distractions": len(distractions), "top_triggers": top}}
    except Exception as e:
        logger.error(f"focus-tips error: {e}")
        return {"text": "Phone in another room. One task at a time. Forgive yourself, then begin again.", "error": str(e)}

"""Reminders + Yaar Whisper Mode.

Reminder lifecycle:
  status: scheduled → due (frontend polled) → summoning (chime cycle) →
          acknowledged | snoozed | dismissed | failed

Whisper config stored at two levels:
  • global default:   db.whisper_config (single doc, _id="default")
  • per-reminder:     reminder.whisper override fields

Frontend WhisperEngine polls /api/reminders/poll every 30s. When a reminder
is due, it starts the chime/summon sequence locally; once user responds (or
max attempts hit), it POSTs the resolution back.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import List, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from db import db
from models import new_id, now_iso

router = APIRouter(prefix="/reminders", tags=["reminders"])

WHISPER_DOC_ID = "default"


# ---------- Models ----------
SummonStyle = Literal["chime", "chime_name", "name"]
FallbackAction = Literal["badge", "vibrate", "silent"]
ReminderStatus = Literal[
    "scheduled", "summoning", "acknowledged", "snoozed", "dismissed", "failed",
]


class WhisperDefaults(BaseModel):
    summon_style: SummonStyle = "chime"
    summon_name: str = "Qasim"
    gap_seconds: int = Field(default=30, ge=5, le=600)
    max_attempts: int = Field(default=5, ge=1, le=15)
    fallback: FallbackAction = "badge"


class Reminder(BaseModel):
    id: str = Field(default_factory=new_id)
    title: str
    body: str = ""
    fire_at: str  # ISO 8601 UTC
    status: ReminderStatus = "scheduled"
    # Whisper override (None means use global default)
    summon_style: Optional[SummonStyle] = None
    summon_name: Optional[str] = None
    gap_seconds: Optional[int] = None
    max_attempts: Optional[int] = None
    fallback: Optional[FallbackAction] = None
    # Result tracking
    attempts_made: int = 0
    acknowledged_at: Optional[str] = None
    snoozed_until: Optional[str] = None
    created_at: str = Field(default_factory=now_iso)


class ReminderCreate(BaseModel):
    title: str
    body: str = ""
    fire_at: str
    summon_style: Optional[SummonStyle] = None
    summon_name: Optional[str] = None
    gap_seconds: Optional[int] = Field(default=None, ge=5, le=600)
    max_attempts: Optional[int] = Field(default=None, ge=1, le=15)
    fallback: Optional[FallbackAction] = None


class ReminderResolve(BaseModel):
    status: ReminderStatus
    snooze_minutes: Optional[int] = None
    attempts_made: Optional[int] = None


class WhisperEnvelope(BaseModel):
    """Reminder + effective whisper config (merged) for frontend WhisperEngine."""
    reminder: Reminder
    whisper: WhisperDefaults


# ---------- Settings ----------
@router.get("/whisper/settings", response_model=WhisperDefaults)
async def get_whisper_settings() -> WhisperDefaults:
    doc = await db.whisper_config.find_one({"_id": WHISPER_DOC_ID}, {"_id": 0})
    return WhisperDefaults(**doc) if doc else WhisperDefaults()


@router.put("/whisper/settings", response_model=WhisperDefaults)
async def set_whisper_settings(body: WhisperDefaults) -> WhisperDefaults:
    await db.whisper_config.update_one(
        {"_id": WHISPER_DOC_ID},
        {"$set": body.model_dump()},
        upsert=True,
    )
    return body


# ---------- CRUD ----------
@router.post("", response_model=Reminder)
async def create_reminder(body: ReminderCreate) -> Reminder:
    r = Reminder(**body.model_dump())
    await db.reminders.insert_one(r.model_dump())
    return r


@router.get("", response_model=List[Reminder])
async def list_reminders(include_done: bool = False) -> List[Reminder]:
    q = {} if include_done else {"status": {"$nin": ["acknowledged", "dismissed"]}}
    docs = await db.reminders.find(q, {"_id": 0}).sort("fire_at", 1).to_list(500)
    return [Reminder(**d) for d in docs]


@router.delete("/{rid}")
async def delete_reminder(rid: str) -> dict:
    res = await db.reminders.delete_one({"id": rid})
    if res.deleted_count == 0:
        raise HTTPException(404, "not found")
    return {"ok": True}


@router.put("/{rid}", response_model=Reminder)
async def update_reminder(rid: str, body: ReminderCreate) -> Reminder:
    res = await db.reminders.update_one(
        {"id": rid},
        {"$set": body.model_dump()},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "not found")
    doc = await db.reminders.find_one({"id": rid}, {"_id": 0})
    return Reminder(**doc)


# ---------- Polling + resolution ----------
@router.get("/poll", response_model=List[WhisperEnvelope])
async def poll_due() -> List[WhisperEnvelope]:
    """Frontend WhisperEngine polls this. Returns due reminders + merged whisper config."""
    now = datetime.now(timezone.utc).isoformat()
    cursor = db.reminders.find(
        {
            "status": {"$in": ["scheduled", "snoozed"]},
            "$or": [
                {"fire_at": {"$lte": now}, "snoozed_until": None},
                {"snoozed_until": {"$ne": None, "$lte": now}},
            ],
        },
        {"_id": 0},
    )
    due = await cursor.to_list(50)
    if not due:
        return []
    defaults_doc = await db.whisper_config.find_one({"_id": WHISPER_DOC_ID}, {"_id": 0}) or {}
    defaults = WhisperDefaults(**defaults_doc)
    out: List[WhisperEnvelope] = []
    for d in due:
        r = Reminder(**d)
        merged = WhisperDefaults(
            summon_style=r.summon_style or defaults.summon_style,
            summon_name=r.summon_name or defaults.summon_name,
            gap_seconds=r.gap_seconds or defaults.gap_seconds,
            max_attempts=r.max_attempts or defaults.max_attempts,
            fallback=r.fallback or defaults.fallback,
        )
        # Mark as summoning so we don't fire again on the next poll
        await db.reminders.update_one(
            {"id": r.id},
            {"$set": {"status": "summoning"}},
        )
        r.status = "summoning"
        out.append(WhisperEnvelope(reminder=r, whisper=merged))
    return out


@router.post("/{rid}/resolve", response_model=Reminder)
async def resolve_reminder(rid: str, body: ReminderResolve) -> Reminder:
    update: dict = {"status": body.status}
    if body.attempts_made is not None:
        update["attempts_made"] = body.attempts_made
    if body.status == "acknowledged":
        update["acknowledged_at"] = now_iso()
        update["snoozed_until"] = None
    elif body.status == "snoozed" and body.snooze_minutes:
        until = datetime.now(timezone.utc) + timedelta(minutes=body.snooze_minutes)
        update["snoozed_until"] = until.isoformat()
        update["status"] = "snoozed"
    res = await db.reminders.update_one({"id": rid}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "not found")
    doc = await db.reminders.find_one({"id": rid}, {"_id": 0})
    return Reminder(**doc)

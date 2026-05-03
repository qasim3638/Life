"""Family endpoints: members, memories, holidays, AI helpers."""
import logging
from fastapi import APIRouter, HTTPException
from typing import List
from db import db
from family_models import (
    FamilyMember, FamilyMemberCreate,
    FamilyMemory, FamilyMemoryCreate,
    Holiday, HolidayCreate,
)
from models import AIPrompt
from ai_helper import run_ai, AI_SYSTEM_MSG

router = APIRouter()
logger = logging.getLogger(__name__)


# ---- Members ----
@router.get("/family/members", response_model=List[FamilyMember])
async def list_members():
    return await db.family_members.find({}, {"_id": 0}).sort("created_at", 1).to_list(200)


@router.post("/family/members", response_model=FamilyMember)
async def create_member(payload: FamilyMemberCreate):
    m = FamilyMember(**payload.model_dump())
    await db.family_members.insert_one(m.model_dump())
    return m


@router.put("/family/members/{member_id}", response_model=FamilyMember)
async def update_member(member_id: str, payload: FamilyMemberCreate):
    res = await db.family_members.update_one({"id": member_id}, {"$set": payload.model_dump()})
    if res.matched_count == 0:
        raise HTTPException(404, "Member not found")
    return await db.family_members.find_one({"id": member_id}, {"_id": 0})


@router.delete("/family/members/{member_id}")
async def delete_member(member_id: str):
    await db.family_members.delete_one({"id": member_id})
    return {"ok": True}


# ---- Memories ----
@router.get("/family/memories", response_model=List[FamilyMemory])
async def list_memories():
    return await db.family_memories.find({}, {"_id": 0}).sort("date", -1).to_list(500)


@router.post("/family/memories", response_model=FamilyMemory)
async def create_memory(payload: FamilyMemoryCreate):
    m = FamilyMemory(**payload.model_dump())
    await db.family_memories.insert_one(m.model_dump())
    return m


@router.put("/family/memories/{memory_id}", response_model=FamilyMemory)
async def update_memory(memory_id: str, payload: FamilyMemoryCreate):
    res = await db.family_memories.update_one({"id": memory_id}, {"$set": payload.model_dump()})
    if res.matched_count == 0:
        raise HTTPException(404, "Memory not found")
    return await db.family_memories.find_one({"id": memory_id}, {"_id": 0})


@router.delete("/family/memories/{memory_id}")
async def delete_memory(memory_id: str):
    await db.family_memories.delete_one({"id": memory_id})
    return {"ok": True}


# ---- Holidays ----
@router.get("/family/holidays", response_model=List[Holiday])
async def list_holidays():
    return await db.holidays.find({}, {"_id": 0}).sort("start_date", -1).to_list(200)


@router.post("/family/holidays", response_model=Holiday)
async def create_holiday(payload: HolidayCreate):
    h = Holiday(**payload.model_dump())
    await db.holidays.insert_one(h.model_dump())
    return h


@router.put("/family/holidays/{holiday_id}", response_model=Holiday)
async def update_holiday(holiday_id: str, payload: HolidayCreate):
    res = await db.holidays.update_one({"id": holiday_id}, {"$set": payload.model_dump()})
    if res.matched_count == 0:
        raise HTTPException(404, "Holiday not found")
    return await db.holidays.find_one({"id": holiday_id}, {"_id": 0})


@router.delete("/family/holidays/{holiday_id}")
async def delete_holiday(holiday_id: str):
    await db.holidays.delete_one({"id": holiday_id})
    return {"ok": True}


# ---- AI helpers ----
@router.post("/ai/holiday-planner")
async def ai_holiday_planner(body: AIPrompt):
    prompt = (
        "Plan a thoughtful family holiday. The user shares destination/dates/preferences below. "
        "Return: a 4-6 day light itinerary with morning/afternoon/evening highlights, "
        "one local food they should try, and one calm moment they shouldn't miss. "
        "Halal-friendly options where possible. 220 words max. "
        f"User notes: {body.prompt}"
    )
    try:
        text = await run_ai(AI_SYSTEM_MSG, prompt)
        return {"text": text}
    except Exception as e:
        logger.error(f"AI holiday planner error: {e}")
        return {"text": "Let's keep it simple — pick one anchor day, one slow day, one wonder day.", "error": str(e)}


@router.post("/ai/memory-weave")
async def ai_memory_weave(body: AIPrompt):
    prompt = (
        "The user shares a family memory below. Write a tender 80-110 word reflection in second person, "
        "as if their future self looks back on this moment. Specific, sensory, no cliches. "
        f"Memory: {body.prompt}"
    )
    try:
        text = await run_ai(AI_SYSTEM_MSG, prompt)
        return {"text": text}
    except Exception as e:
        logger.error(f"AI memory weave error: {e}")
        return {"text": "Some moments only become full when you remember them.", "error": str(e)}


@router.post("/ai/family-ritual")
async def ai_family_ritual(body: AIPrompt):
    prompt = (
        "Suggest 3 small, specific, doable family rituals to deepen connection — one daily, one weekly, one monthly. "
        "Each in 1-2 sentences. Practical, not preachy. "
        f"Family context: {body.prompt}"
    )
    try:
        text = await run_ai(AI_SYSTEM_MSG, prompt)
        return {"text": text}
    except Exception as e:
        logger.error(f"AI family ritual error: {e}")
        return {"text": "Daily: one shared meal without phones. Weekly: a long Sunday walk. Monthly: a story night.", "error": str(e)}

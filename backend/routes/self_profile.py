"""Self-profile (appearance, personality, mind, style, gear) + AI suggestions and daily brief."""
import logging
from typing import Optional
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter
from pydantic import BaseModel, Field

from db import db
from models import AIPrompt, now_iso
from ai_helper import run_ai, AI_SYSTEM_MSG

router = APIRouter()
logger = logging.getLogger(__name__)


class SelfProfile(BaseModel):
    id: str = "default"
    appearance: str = ""
    personality: str = ""
    mind: str = ""
    style: str = ""
    gear: str = ""
    updated_at: str = Field(default_factory=now_iso)


class SelfProfileUpdate(BaseModel):
    appearance: Optional[str] = None
    personality: Optional[str] = None
    mind: Optional[str] = None
    style: Optional[str] = None
    gear: Optional[str] = None


class DailyBriefRequest(BaseModel):
    note: Optional[str] = ""


async def _get_or_create_profile() -> dict:
    item = await db.self_profile.find_one({"id": "default"}, {"_id": 0})
    if not item:
        p = SelfProfile()
        await db.self_profile.insert_one(p.model_dump())
        return p.model_dump()
    return item


@router.get("/self-profile")
async def get_profile():
    return await _get_or_create_profile()


@router.put("/self-profile")
async def update_profile(payload: SelfProfileUpdate):
    await _get_or_create_profile()
    update = {k: v for k, v in payload.model_dump().items() if v is not None}
    update["updated_at"] = now_iso()
    await db.self_profile.update_one({"id": "default"}, {"$set": update})
    return await db.self_profile.find_one({"id": "default"}, {"_id": 0})


DIMENSION_PROMPTS = {
    "appearance": (
        "Based on the user's described appearance, suggest 3-4 concrete, kind, doable refinements "
        "for grooming, skincare, posture, or self-presentation that suit a 40-year-old man "
        "wanting to age with grace, not vanity. Specific products or routines welcome but no brand pushing. "
        "150 words max."
    ),
    "personality": (
        "Based on the user's described personality, offer 2-3 gentle observations and 2 small "
        "growth invitations — never preachy, never therapy-speak. Acknowledge what is already strong. "
        "150 words max."
    ),
    "mind": (
        "Based on the user's described mind/interests/beliefs, suggest 3 things this week to feed it: "
        "one book, one practice, one conversation worth having. Specific. Halal-friendly when relevant. "
        "150 words max."
    ),
    "style": (
        "Based on the user's described style preferences, suggest 3 wardrobe ideas tailored to a "
        "40-year-old man — one everyday refinement, one weekend look, one elevated piece worth investing in. "
        "Color, fit, fabric. No fast-fashion brand pushing. 150 words max."
    ),
    "gear": (
        "Based on the user's described gear/gadget preferences, suggest 2-3 thoughtful additions or upgrades "
        "that would actually improve daily life — durable, beautiful, useful. One accessibility/wellness pick. "
        "150 words max."
    ),
}


@router.post("/ai/self-suggestion/{dimension}")
async def ai_self_suggestion(dimension: str, body: DailyBriefRequest = DailyBriefRequest()):
    if dimension not in DIMENSION_PROMPTS:
        return {"text": "Unknown dimension.", "error": "invalid_dimension"}
    profile = await _get_or_create_profile()
    desc = profile.get(dimension, "")
    if not desc.strip():
        return {"text": "Tell me a bit about yourself in this section first."}
    extra = body.note or ""
    full_prompt = f"{DIMENSION_PROMPTS[dimension]}\n\nUser describes themselves as: {desc}\n\nExtra context: {extra}"
    try:
        text = await run_ai(AI_SYSTEM_MSG, full_prompt)
        return {"text": text}
    except Exception as e:
        logger.error(f"self-suggestion error: {e}")
        return {"text": "Let's revisit this in a moment.", "error": str(e)}


@router.post("/ai/daily-brief")
async def ai_daily_brief(_: DailyBriefRequest = DailyBriefRequest()):
    """Generate a personalised daily brief from profile + day plan + memories + events."""
    today = datetime.now(timezone.utc).date()
    today_iso = today.isoformat()
    tomorrow_iso = (today + timedelta(days=1)).isoformat()

    profile = await _get_or_create_profile()
    companion = await db.companion.find_one({"id": "default"}, {"_id": 0})
    memories = await db.companion_memories.find({}, {"_id": 0}).sort("created_at", -1).to_list(20)
    plan = await db.day_plans.find_one({"date": today_iso}, {"_id": 0}) or \
           await db.day_plans.find_one({"date": tomorrow_iso}, {"_id": 0}) or {}
    events = await db.events.find(
        {"date": {"$gte": today_iso, "$lte": (today + timedelta(days=14)).isoformat()}},
        {"_id": 0}
    ).sort("date", 1).to_list(5)

    companion_name = (companion or {}).get("name", "Najm")
    user_name = (companion or {}).get("user_name", "friend")

    profile_summary = []
    for k in ("appearance", "personality", "mind", "style", "gear"):
        v = (profile.get(k) or "").strip()
        if v:
            profile_summary.append(f"{k}: {v[:200]}")

    memory_summary = "; ".join((m.get("content") or "")[:120] for m in memories[:8])

    plan_summary = ""
    if plan:
        priorities = [p for p in (plan.get("priorities") or []) if p]
        gym = plan.get("gym_workout_name") or ("a workout" if plan.get("gym_planned") else "rest day")
        plan_summary = f"priorities: {priorities}; movement: {gym}"

    upcoming = "; ".join(f"{e.get('title')} ({e.get('date')})" for e in events[:3])

    prompt = (
        f"You are {companion_name}, the user's companion. Write today's brief to {user_name}. "
        "Five short sections, each a single tight sentence. Use the user's profile and memories to make "
        "every suggestion personal — never generic. Format STRICTLY as:\n"
        "GROOMING: ...\n"
        "STYLE: ...\n"
        "FOCUS: ...\n"
        "CONNECT: ...\n"
        "GEAR: ...\n\n"
        "Reflect their actual described traits. If a section has no usable input, write a gentle "
        "placeholder asking them to fill that part of their profile. No emojis. No preamble.\n\n"
        f"Profile: {' | '.join(profile_summary) or 'empty'}\n"
        f"Memories: {memory_summary or 'none yet'}\n"
        f"Today's plan: {plan_summary or 'none set'}\n"
        f"Upcoming: {upcoming or 'none'}"
    )
    try:
        text = await run_ai(AI_SYSTEM_MSG, prompt)
        return {"text": text}
    except Exception as e:
        logger.error(f"daily brief error: {e}")
        return {"text": "GROOMING: hydrate.\nSTYLE: wear what feels honest.\nFOCUS: one important thing.\nCONNECT: one message to someone you love.\nGEAR: tidy your desk.", "error": str(e)}

"""Echo of yesterday: a short reflection of yesterday's logged activity."""
import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from db import db
from ai_helper import run_ai, AI_SYSTEM_MSG

router = APIRouter()
logger = logging.getLogger(__name__)


class EchoRequest(BaseModel):
    note: Optional[str] = ""


@router.post("/ai/echo-yesterday")
async def ai_echo_yesterday(_: EchoRequest = EchoRequest()):
    today = datetime.now(timezone.utc).date()
    yesterday = (today - timedelta(days=1)).isoformat()

    workout = await db.workout_logs.find({"date": yesterday}, {"_id": 0}).to_list(20)
    journal = await db.journal_entries.find({"date": yesterday}, {"_id": 0}).to_list(20)
    plan = await db.day_plans.find_one({"date": yesterday}, {"_id": 0})

    bits = []
    if workout:
        names = ", ".join(w.get("workout_name", "") for w in workout if w.get("workout_name"))
        total = sum(w.get("duration_min", 0) for w in workout)
        bits.append(f"workout: {names} ({total} min)")
    if journal:
        moods = [j.get("mood", 3) for j in journal]
        avg = sum(moods) / len(moods) if moods else 3
        sample = next((j.get("reflection") for j in journal if j.get("reflection")), "")
        bits.append(f"journal mood {avg:.1f}/5{', noted: ' + sample[:120] if sample else ''}")
    if plan:
        done_chores = sum(
            1 for arr_key in ("morning_routine", "house_chores", "work_chores")
            for c in (plan.get(arr_key) or []) if c.get("done")
        )
        total_chores = sum(
            len(plan.get(arr_key) or [])
            for arr_key in ("morning_routine", "house_chores", "work_chores")
        )
        if total_chores:
            bits.append(f"plan: {done_chores}/{total_chores} items done")
        priorities = [p for p in (plan.get("priorities") or []) if p]
        if priorities:
            bits.append(f"priorities were: {', '.join(priorities)}")

    if not bits:
        return {"text": "Yesterday left no marks in the logs. A blank page is also an honest page."}

    prompt = (
        "Write ONE short sentence (max 22 words) that mirrors back what the user did yesterday. "
        "Warm, observational, not preachy. Second person. Avoid 'great', 'amazing'. "
        "Never make data up — only reflect what's given.\n\n"
        f"Yesterday data: {' | '.join(bits)}"
    )
    try:
        text = await run_ai(AI_SYSTEM_MSG, prompt)
        return {"text": text}
    except Exception as e:
        logger.error(f"echo error: {e}")
        return {"text": f"Yesterday: {bits[0] if bits else 'a quiet day'}.", "error": str(e)}

"""AI endpoints: motivation, reflection, meal/workout suggestions, weekly letter."""
import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter
from db import db
from models import AIPrompt, WeeklyLetterRequest
from ai_helper import run_ai, AI_SYSTEM_MSG

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/ai/motivation")
async def ai_motivation(body: AIPrompt):
    prompt = (
        "Write a single short, powerful motivational reflection (80-120 words) "
        "for today. Ground it in stoic wisdom or Rumi-like poetry. "
        f"Context from the user: {body.context or 'Starting a new week'}."
    )
    try:
        text = await run_ai(AI_SYSTEM_MSG, prompt)
        return {"text": text}
    except Exception as e:
        logger.error(f"AI motivation error: {e}")
        return {"text": "The path forward is made by walking it. Take one honest step today.", "error": str(e)}


@router.post("/ai/reflect")
async def ai_reflect(body: AIPrompt):
    prompt = (
        f"The user shared this reflection: '{body.prompt}'. "
        "Respond as a wise, compassionate coach. 100-150 words. "
        "Acknowledge what you hear, offer one gentle insight, and one small "
        "action they can take within 24 hours."
    )
    try:
        text = await run_ai(AI_SYSTEM_MSG, prompt)
        return {"text": text}
    except Exception as e:
        logger.error(f"AI reflect error: {e}")
        return {"text": "Your words matter. Sit with them gently today.", "error": str(e)}


@router.post("/ai/meal-suggestion")
async def ai_meal(body: AIPrompt):
    prompt = (
        "Suggest ONE specific halal, low-carb high-protein meal idea suited for a "
        "40-year-old wanting to stay lean and energetic. Prefer Pakistani, Indian, "
        "or Arab cuisine. No pork or bacon. Include: meal name, 5-8 ingredients, "
        "brief 3-step method, and estimated macros. 150 words max. "
        f"User context: {body.prompt}"
    )
    try:
        text = await run_ai(AI_SYSTEM_MSG, prompt)
        return {"text": text}
    except Exception as e:
        logger.error(f"AI meal error: {e}")
        return {"text": "Try grilled chicken with cucumber-yogurt salad and mint.", "error": str(e)}


@router.post("/ai/workout-suggestion")
async def ai_workout(body: AIPrompt):
    prompt = (
        "Design a single 30-40 minute workout for a 40-year-old man wanting "
        "sustainable strength, mobility, and longevity (not bro-gym). "
        "Return a name, 5-6 exercises with sets/reps/rest, and a short note on "
        "form/breath. 180 words max. "
        f"User focus: {body.prompt}"
    )
    try:
        text = await run_ai(AI_SYSTEM_MSG, prompt)
        return {"text": text}
    except Exception as e:
        logger.error(f"AI workout error: {e}")
        return {"text": "Try: squats, push-ups, rows, planks. 3 rounds of 10 reps.", "error": str(e)}


@router.post("/ai/weekly-letter")
async def ai_weekly_letter(body: WeeklyLetterRequest = WeeklyLetterRequest()):
    today = datetime.now(timezone.utc).date()
    week_ago = (today - timedelta(days=7)).isoformat()

    logs = await db.workout_logs.find({"date": {"$gte": week_ago}}, {"_id": 0}).to_list(100)
    journal = await db.journal_entries.find({"date": {"$gte": week_ago}}, {"_id": 0}).to_list(100)
    events = await db.events.find({"date": {"$gte": today.isoformat()}}, {"_id": 0}).sort("date", 1).to_list(10)

    summary = []
    if logs:
        summary.append(f"workouts this week: {len(logs)} ({', '.join(w.get('workout_name', '') for w in logs[:5])})")
    else:
        summary.append("no workouts logged this week")
    if journal:
        moods = [e.get("mood", 3) for e in journal]
        avg = sum(moods) / len(moods)
        summary.append(f"journal entries: {len(journal)}, average mood {avg:.1f}/5")
        latest_reflection = next((j.get("reflection") for j in journal if j.get("reflection")), "")
        if latest_reflection:
            summary.append(f"latest reflection: '{latest_reflection[:200]}'")
    else:
        summary.append("no journal entries this week")
    if events:
        summary.append(f"upcoming: {events[0].get('title')} on {events[0].get('date')}")

    prompt = (
        "Write a short, tender 'letter to future me' (140-180 words) from the user's present self "
        "based on the past 7 days. Address the reader warmly. Acknowledge what they did and felt. "
        "Offer one gentle observation and one small intention for the coming week. "
        "No bullet lists. Sign off simply. "
        f"Data from the past week: {' | '.join(summary)}"
        + (f" | extra note from user: {body.note[:300]}" if body.note else "")
    )
    try:
        text = await run_ai(AI_SYSTEM_MSG, prompt)
        return {"text": text, "data": {"workouts": len(logs), "journal_entries": len(journal)}}
    except Exception as e:
        logger.error(f"AI weekly letter error: {e}")
        return {"text": "Dear you - be gentle with yourself this week.", "error": str(e)}

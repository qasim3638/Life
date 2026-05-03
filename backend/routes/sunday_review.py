"""Sunday rhythm review — weekly reflection AI generator."""
import logging
from datetime import datetime, timezone, timedelta, date as date_cls
from typing import List, Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field

from db import db
from models import new_id, now_iso
from ai_helper import run_ai, AI_SYSTEM_MSG

router = APIRouter()
logger = logging.getLogger(__name__)


class WeeklyReview(BaseModel):
    id: str = Field(default_factory=new_id)
    week_start: str  # Monday ISO date
    week_end: str    # Sunday ISO date
    text: str = ""
    data: dict = {}
    created_at: str = Field(default_factory=now_iso)


def _week_bounds(today: date_cls) -> tuple[date_cls, date_cls]:
    """Return (Monday, Sunday) of the week containing `today`."""
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


async def _aggregate_week(monday: date_cls, sunday: date_cls) -> dict:
    monday_iso = monday.isoformat()
    sunday_iso = sunday.isoformat()
    next_monday_iso = (sunday + timedelta(days=1)).isoformat()

    # Workouts (date is YYYY-MM-DD string)
    workouts = await db.workout_logs.find(
        {"date": {"$gte": monday_iso, "$lte": sunday_iso}}, {"_id": 0}
    ).to_list(200)

    # Journal entries
    journal = await db.journal_entries.find(
        {"date": {"$gte": monday_iso, "$lte": sunday_iso}}, {"_id": 0}
    ).to_list(200)
    moods = [j.get("mood", 3) for j in journal]
    avg_mood = round(sum(moods) / len(moods), 1) if moods else None

    # Focus sessions (started_at is ISO datetime)
    sessions = await db.focus_sessions.find(
        {"started_at": {"$gte": monday_iso, "$lt": next_monday_iso}}, {"_id": 0}
    ).to_list(500)
    focus_min = sum(s.get("actual_min") or 0 for s in sessions)
    completed_sessions = sum(1 for s in sessions if s.get("completed"))

    distractions = await db.distractions.find(
        {"at": {"$gte": monday_iso, "$lt": next_monday_iso}}, {"_id": 0}
    ).to_list(500)

    # Sobriety: snapshot of each addiction's current streak + slips this week
    addictions = await db.addictions.find({}, {"_id": 0}).to_list(50)
    addiction_summary = []
    for a in addictions:
        try:
            start = datetime.fromisoformat(a["started_clean"].replace("Z", "+00:00"))
            days = max(0, (datetime.now(timezone.utc) - start).days)
        except Exception:
            days = 0
        slips_this_week = await db.slips.count_documents({
            "addiction_id": a["id"],
            "at": {"$gte": monday_iso, "$lt": next_monday_iso},
        })
        addiction_summary.append({
            "name": a.get("name", ""),
            "days_clean": days,
            "slips_this_week": slips_this_week,
            "longest": a.get("longest_streak_days", 0),
        })

    # Family memories saved this week (filter by created_at)
    fam_memories = await db.family_memories.find(
        {"created_at": {"$gte": monday_iso, "$lt": next_monday_iso}}, {"_id": 0}
    ).to_list(50)

    # Achieved life goals snapshot
    goals = await db.life_goals.find({"status": "achieved"}, {"_id": 0}).to_list(200)

    # Day plans completion this week
    plans = await db.day_plans.find(
        {"date": {"$gte": monday_iso, "$lte": sunday_iso}}, {"_id": 0}
    ).to_list(20)
    chores_done = 0
    chores_total = 0
    for p in plans:
        for k in ("morning_routine", "house_chores", "work_chores"):
            for c in (p.get(k) or []):
                chores_total += 1
                if c.get("done"):
                    chores_done += 1

    return {
        "workout_count": len(workouts),
        "workout_minutes": sum(w.get("duration_min", 0) for w in workouts),
        "workout_names": [w.get("workout_name", "") for w in workouts if w.get("workout_name")][:6],
        "journal_count": len(journal),
        "average_mood": avg_mood,
        "sample_reflections": [j.get("reflection", "")[:240] for j in journal if j.get("reflection")][:3],
        "focus_minutes": focus_min,
        "focus_sessions": len(sessions),
        "focus_completed": completed_sessions,
        "distraction_count": len(distractions),
        "addictions": addiction_summary,
        "family_memories_saved": [m.get("title", "") for m in fam_memories],
        "achieved_goals_total": len(goals),
        "plan_chores_done": chores_done,
        "plan_chores_total": chores_total,
    }


@router.post("/ai/sunday-review")
async def ai_sunday_review(regenerate: bool = False):
    today = datetime.now(timezone.utc).date()
    monday, sunday = _week_bounds(today)

    if not regenerate:
        existing = await db.weekly_reviews.find_one(
            {"week_start": monday.isoformat()}, {"_id": 0}
        )
        if existing:
            return existing

    data = await _aggregate_week(monday, sunday)

    # If no data at all, return a gentle empty-week response without burning a Claude call
    if (data["workout_count"] == 0 and data["journal_count"] == 0
            and data["focus_minutes"] == 0 and not data["family_memories_saved"]
            and data["plan_chores_total"] == 0
            and not any(a["slips_this_week"] for a in data["addictions"])):
        text = (
            "This was a quiet week in the logs. Sometimes the work is happening below the surface "
            "— in conversations, in waiting, in rest. Let next week be one small thing written down."
        )
    else:
        addiction_lines = "; ".join(
            f"{a['name']}: {a['days_clean']}d clean ({a['slips_this_week']} slips this week)"
            for a in data["addictions"]
        ) or "no habits being tracked"

        prompt = (
            "Write a single-page Sunday reflection (210-280 words) titled 'What your week said about you.' "
            "Use the data below — never invent. Speak to the user warmly, in second person. "
            "Open with one observation that names the actual shape of the week. "
            "Then 2-3 paragraphs that weave together what was tended (movement, stillness, focus, "
            "the people, the inner work) and what slipped through. Acknowledge effort honestly — "
            "no false praise, no scolding. Close with one small invitation for the coming week, "
            "named specifically. Do not list bullets. Do not use the word 'journey'. "
            "Avoid 'amazing', 'incredible', 'great'. No emojis.\n\n"
            "DATA:\n"
            f"- Movement: {data['workout_count']} workouts ({data['workout_minutes']} min total). "
            f"Names: {', '.join(data['workout_names']) if data['workout_names'] else 'none'}.\n"
            f"- Journal: {data['journal_count']} entries"
            + (f", average mood {data['average_mood']}/5" if data['average_mood'] else "")
            + ".\n"
            f"- Sample reflections: {data['sample_reflections'] if data['sample_reflections'] else 'none shared'}.\n"
            f"- Focus: {data['focus_minutes']} min across {data['focus_sessions']} sessions "
            f"({data['focus_completed']} completed); {data['distraction_count']} distractions noted.\n"
            f"- Sobriety: {addiction_lines}.\n"
            f"- Family memories saved: {data['family_memories_saved'] or 'none'}.\n"
            f"- Day-plan items checked off: {data['plan_chores_done']}/{data['plan_chores_total']}.\n"
            f"- Total achieved life-goals to date: {data['achieved_goals_total']}.\n"
        )
        try:
            text = await run_ai(AI_SYSTEM_MSG, prompt)
        except Exception as e:
            logger.error(f"sunday-review AI failed: {e}")
            text = "The week is closed. Begin again on Monday with one honest thing."

    review = WeeklyReview(
        week_start=monday.isoformat(),
        week_end=sunday.isoformat(),
        text=text,
        data=data,
    )
    # Upsert by week_start so multiple regenerations replace
    await db.weekly_reviews.update_one(
        {"week_start": monday.isoformat()},
        {"$set": review.model_dump()},
        upsert=True,
    )
    return review.model_dump()


@router.get("/sunday-reviews", response_model=List[WeeklyReview])
async def list_reviews():
    return await db.weekly_reviews.find({}, {"_id": 0}).sort("week_start", -1).to_list(60)


@router.get("/sunday-reviews/latest")
async def latest_review():
    item = await db.weekly_reviews.find_one(
        {}, {"_id": 0}, sort=[("week_start", -1)]
    )
    return item or {}

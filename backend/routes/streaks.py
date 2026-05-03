"""Streaks computation."""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter
from db import db

router = APIRouter()


@router.get("/streaks")
async def streaks():
    today = datetime.now(timezone.utc).date()
    logs = await db.workout_logs.find({}, {"_id": 0, "date": 1}).to_list(1000)
    journal = await db.journal_entries.find({}, {"_id": 0, "date": 1}).to_list(1000)

    def streak(dates: set) -> int:
        d = today
        n = 0
        while d.isoformat() in dates:
            n += 1
            d = d - timedelta(days=1)
        return n

    workout_dates = {w["date"] for w in logs}
    journal_dates = {j["date"] for j in journal}
    today_iso = today.isoformat()

    return {
        "workout_streak": streak(workout_dates),
        "workout_total_days": len(workout_dates),
        "workout_today": today_iso in workout_dates,
        "journal_streak": streak(journal_dates),
        "journal_total_days": len(journal_dates),
        "journal_today": today_iso in journal_dates,
    }

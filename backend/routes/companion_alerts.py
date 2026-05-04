"""Proactive Companion alerts — cheap, rule-based signals surfaced on Today.
No AI calls; just pattern-matching on the user's live data."""
import logging
from datetime import datetime, timedelta, timezone
from typing import List
from fastapi import APIRouter
from db import db
from companion_tools import prayer_times
from weather import forecast

router = APIRouter()
logger = logging.getLogger(__name__)


def _today_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _ago_iso(days: int):
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")


def _fmt_hm(hhmm: str, now: datetime) -> datetime | None:
    try:
        h, m = hhmm.split(":")
        return now.replace(hour=int(h), minute=int(m), second=0, microsecond=0)
    except Exception:
        return None


@router.get("/companion/alerts")
async def companion_alerts():
    """Return a small list of contextual nudges to display on Today."""
    alerts: List[dict] = []
    now = datetime.now(timezone.utc)
    today = _today_iso()

    # ----- 1. Workout gap -----
    latest_workout = await db.workouts.find_one(
        {},
        {"_id": 0, "date": 1, "name": 1},
        sort=[("date", -1)],
    )
    if not latest_workout:
        alerts.append({
            "id": "no-workout-ever",
            "tone": "nudge",
            "title": "Let's start moving",
            "body": "You haven't logged a workout yet. Even 10 minutes today is a beginning.",
            "cta": {"label": "Open fitness", "href": "/fitness"},
        })
    else:
        try:
            last_dt = datetime.strptime(latest_workout["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            gap = (now - last_dt).days
            if gap >= 4:
                alerts.append({
                    "id": "workout-gap",
                    "tone": "nudge",
                    "title": f"{gap} days since you moved",
                    "body": f"Your last session was '{latest_workout.get('name', 'a workout')}'. Want me to block 30 minutes tomorrow?",
                    "cta": {"label": "Plan one", "href": "/fitness"},
                })
        except Exception:
            pass

    # ----- 2. Journal gap -----
    latest_journal = await db.journal_entries.find_one(
        {},
        {"_id": 0, "date": 1},
        sort=[("date", -1)],
    )
    if latest_journal:
        try:
            last_dt = datetime.strptime(latest_journal["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            gap = (now - last_dt).days
            if gap >= 3:
                alerts.append({
                    "id": "journal-gap",
                    "tone": "soft",
                    "title": "Your journal's been quiet",
                    "body": "One sentence about today is enough. The good ones, the hard ones — both matter.",
                    "cta": {"label": "Write one", "href": "/self-care"},
                })
        except Exception:
            pass

    # ----- 3. Prayer reminder (within 30 min) -----
    companion = await db.companion.find_one({"id": "default"}, {"_id": 0})
    if companion and companion.get("latitude") is not None and companion.get("longitude") is not None:
        times = await prayer_times(companion["latitude"], companion["longitude"])
        if times:
            for key in ("Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"):
                t = times.get(key)
                if not t:
                    continue
                pt = _fmt_hm(t.split()[0], now)
                if not pt:
                    continue
                mins = (pt - now.replace(tzinfo=None) if pt.tzinfo is None else pt - now).total_seconds() / 60
                if 0 < mins <= 30:
                    alerts.append({
                        "id": f"prayer-{key.lower()}",
                        "tone": "spiritual",
                        "title": f"{key} in {int(mins)} min",
                        "body": f"Azan at {t.split()[0]} ({companion.get('location_name', 'your city')}).",
                    })
                    break

    # ----- 4. Rain incoming (next 3 hours) -----
    if companion and companion.get("latitude") is not None:
        data = await forecast(companion["latitude"], companion["longitude"], days=1)
        if data:
            daily = data.get("daily") or {}
            pprob = daily.get("precipitation_probability_max") or []
            if pprob and pprob[0] is not None and pprob[0] >= 60:
                alerts.append({
                    "id": "rain-today",
                    "tone": "practical",
                    "title": f"Rain likely today ({pprob[0]}%)",
                    "body": "Grab a jacket before you head out.",
                })

    # ----- 5. Event tomorrow -----
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    next_events = await db.events.find(
        {"date": tomorrow},
        {"_id": 0, "title": 1, "type": 1},
    ).limit(3).to_list(3)
    for e in next_events:
        title = e.get("title") or "an event"
        alerts.append({
            "id": f"event-{title}",
            "tone": "soft",
            "title": f"Tomorrow: {title}",
            "body": "Worth a small note of prep the night before.",
            "cta": {"label": "See calendar", "href": "/events"},
        })

    # ----- 6. Sunday nudge (morning/early afternoon) -----
    if now.weekday() == 6 and 8 <= now.hour <= 14:
        # Only if this week's review hasn't been generated yet
        mon = (now - timedelta(days=6)).strftime("%Y-%m-%d")
        existing = await db.weekly_reviews.find_one({"week_start": mon}, {"_id": 0})
        if not existing:
            alerts.append({
                "id": "sunday-review",
                "tone": "spiritual",
                "title": "Sunday reflection is waiting",
                "body": "Your week, written from your actual days. Takes about 20 seconds.",
                "cta": {"label": "Open review", "href": "/review"},
            })

    # ----- 7. Plan-drift (afternoon, today's priorities still all empty) -----
    if now.hour >= 14:
        plan = await db.day_plans.find_one({"date": today}, {"_id": 0})
        if plan:
            pri = [p for p in (plan.get("priorities") or []) if p and p.strip()]
            if len(pri) == 0:
                alerts.append({
                    "id": "no-priorities",
                    "tone": "soft",
                    "title": "No priorities set for today",
                    "body": "Even one clear intention changes the next hour.",
                    "cta": {"label": "Set them", "href": "/tomorrow"},
                })

    # Cap to 4 most relevant (prayer/rain first, then gaps, then reminders)
    priority_order = ["prayer-", "rain-", "workout-", "journal-", "sunday-", "event-", "no-priorities"]
    alerts.sort(key=lambda a: next((i for i, p in enumerate(priority_order) if a["id"].startswith(p)), 99))
    return alerts[:4]

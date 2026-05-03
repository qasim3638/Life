"""Companion action executor — applies proposed actions to the app's data."""
import re
from datetime import datetime, timezone
from db import db
from models import (
    TimeBlock, DayPlan, Event, ChoreItem,
    new_id, now_iso,
)

ALLOWED_ACTIONS = {"add_time_block", "add_event", "add_priority", "add_chore"}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_HOUR_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def validate_action(a: dict) -> tuple[bool, str]:
    """Return (ok, reason). Cheap validation so Apply can't break the DB."""
    if not isinstance(a, dict):
        return False, "not an object"
    t = a.get("type")
    if t not in ALLOWED_ACTIONS:
        return False, f"unknown type: {t}"
    if t in ("add_time_block", "add_event", "add_priority"):
        if not _DATE_RE.match(str(a.get("date", ""))):
            return False, "invalid date (need YYYY-MM-DD)"
    if t == "add_time_block":
        if not _HOUR_RE.match(str(a.get("hour", ""))):
            return False, "invalid hour (need HH:MM)"
        if not (a.get("text") or "").strip():
            return False, "missing text"
    if t == "add_event":
        if not (a.get("title") or "").strip():
            return False, "missing title"
    if t == "add_priority":
        if not (a.get("text") or "").strip():
            return False, "missing text"
    if t == "add_chore":
        if a.get("kind") not in ("house", "work", "morning"):
            return False, "kind must be house|work|morning"
        if not (a.get("text") or "").strip():
            return False, "missing text"
    return True, ""


async def _get_or_init_plan(date: str) -> dict:
    item = await db.day_plans.find_one({"date": date}, {"_id": 0})
    if item:
        return item
    plan = DayPlan(date=date).model_dump()
    await db.day_plans.insert_one({**plan})
    return plan


async def execute_action(a: dict) -> dict:
    """Run a validated action. Returns a short summary of what happened."""
    t = a["type"]

    if t == "add_time_block":
        date = a["date"]
        block = TimeBlock(hour=a["hour"], text=a["text"].strip()[:80]).model_dump()
        plan = await _get_or_init_plan(date)
        blocks = list(plan.get("time_blocks") or [])
        # Insert in order
        blocks.append(block)
        blocks.sort(key=lambda b: b["hour"])
        await db.day_plans.update_one(
            {"date": date},
            {"$set": {"time_blocks": blocks, "updated_at": now_iso()}},
        )
        return {"ok": True, "message": f"Added '{block['text']}' at {block['hour']} on {date}"}

    if t == "add_event":
        evt = Event(
            title=a["title"].strip()[:120],
            date=a["date"],
            type=a.get("event_type", "event"),
            notes=(a.get("notes") or "")[:500],
            recurring=bool(a.get("recurring")),
        ).model_dump()
        await db.events.insert_one({**evt})
        return {"ok": True, "message": f"Added event '{evt['title']}' on {evt['date']}"}

    if t == "add_priority":
        date = a["date"]
        text = a["text"].strip()[:120]
        plan = await _get_or_init_plan(date)
        priorities = list(plan.get("priorities") or ["", "", ""])
        # Fill the first empty slot; if all full, replace the 3rd one
        placed = False
        for i in range(3):
            if i >= len(priorities):
                priorities.append("")
            if not priorities[i].strip():
                priorities[i] = text
                placed = True
                break
        if not placed:
            priorities = priorities[:2] + [text]
        await db.day_plans.update_one(
            {"date": date},
            {"$set": {"priorities": priorities[:3], "updated_at": now_iso()}},
        )
        return {"ok": True, "message": f"Added priority: {text}"}

    if t == "add_chore":
        kind = a["kind"]
        text = a["text"].strip()[:120]
        # Chores live on "today" by default, unless a date is given
        date = a.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        field = {"house": "house_chores", "work": "work_chores", "morning": "morning_routine"}[kind]
        plan = await _get_or_init_plan(date)
        items = list(plan.get(field) or [])
        items.append(ChoreItem(text=text).model_dump())
        await db.day_plans.update_one(
            {"date": date},
            {"$set": {field: items, "updated_at": now_iso()}},
        )
        return {"ok": True, "message": f"Added {kind} chore: {text}"}

    return {"ok": False, "message": f"Unknown action: {t}"}

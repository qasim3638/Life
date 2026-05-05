"""Companion action executor — applies proposed actions to the app's data."""
import re
from datetime import datetime, timezone
from db import db
from models import (
    TimeBlock, DayPlan, Event, ChoreItem, Supplement,
    LifeGoal, JournalEntry,
    new_id, now_iso,
)

ALLOWED_ACTIONS = {
    # Existing
    "add_time_block", "add_event", "add_priority", "add_chore",
    "log_workout", "log_journal",
    # New — day plan
    "tick_priority", "tick_chore", "set_meal", "add_supplement",
    # New — self-care
    "add_gratitude", "log_mood",
    # New — blueprint
    "add_life_goal",
    # New — family
    "add_family_memory",
}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_HOUR_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

_MEAL_SLOTS = {"breakfast", "lunch", "dinner", "snack"}
_CHORE_KINDS = {"house", "work", "morning"}


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
        if a.get("kind") not in _CHORE_KINDS:
            return False, "kind must be house|work|morning"
        if not (a.get("text") or "").strip():
            return False, "missing text"
    if t == "log_workout":
        if not (a.get("name") or "").strip():
            return False, "missing workout name"
        try:
            dur = int(a.get("duration_min", 0))
            if dur <= 0 or dur > 600:
                return False, "duration_min must be 1..600"
        except Exception:
            return False, "duration_min must be an integer"
    if t == "log_journal":
        if not (a.get("entry") or a.get("gratitude") or "").strip():
            return False, "need entry or gratitude text"
        if a.get("mood") is not None:
            try:
                m = int(a["mood"])
                if m < 1 or m > 5:
                    return False, "mood must be 1..5"
            except Exception:
                return False, "mood must be integer 1..5"

    # --- NEW ACTION VALIDATION ---
    if t == "tick_priority":
        if not _DATE_RE.match(str(a.get("date", ""))):
            return False, "invalid date"
        idx = a.get("index")
        text = (a.get("text") or "").strip()
        if idx is None and not text:
            return False, "need `index` (0/1/2) or `text` to match"
        if idx is not None:
            try:
                i = int(idx)
                if i < 0 or i > 2:
                    return False, "index must be 0..2"
            except Exception:
                return False, "index must be integer"
    if t == "tick_chore":
        if a.get("kind") not in _CHORE_KINDS:
            return False, "kind must be house|work|morning"
        if not (a.get("text") or "").strip():
            return False, "missing chore text to match"
    if t == "set_meal":
        if not _DATE_RE.match(str(a.get("date", ""))):
            return False, "invalid date"
        if a.get("slot") not in _MEAL_SLOTS:
            return False, "slot must be breakfast|lunch|dinner|snack"
        if not (a.get("text") or "").strip():
            return False, "missing meal text"
    if t == "add_supplement":
        if not _DATE_RE.match(str(a.get("date", ""))):
            return False, "invalid date"
        if not (a.get("name") or "").strip():
            return False, "missing supplement name"
    if t == "add_gratitude":
        if not _DATE_RE.match(str(a.get("date", ""))):
            return False, "invalid date"
        if not (a.get("text") or "").strip():
            return False, "missing gratitude text"
    if t == "log_mood":
        if not _DATE_RE.match(str(a.get("date", ""))):
            return False, "invalid date"
        try:
            m = int(a.get("mood", 0))
            if m < 1 or m > 5:
                return False, "mood must be 1..5"
        except Exception:
            return False, "mood must be integer 1..5"
    if t == "add_life_goal":
        if not (a.get("title") or "").strip():
            return False, "missing title"
        try:
            yr = int(a.get("year", 0))
            age = int(a.get("age", 0))
            if yr < 2020 or yr > 2100:
                return False, "year out of range"
            if age < 1 or age > 120:
                return False, "age out of range"
        except Exception:
            return False, "year and age must be integers"
    if t == "add_family_memory":
        if not (a.get("title") or "").strip():
            return False, "missing title"
        if not _DATE_RE.match(str(a.get("date", ""))):
            return False, "invalid date"
    return True, ""


async def _get_or_init_plan(date: str) -> dict:
    item = await db.day_plans.find_one({"date": date}, {"_id": 0})
    if item:
        return item
    plan = DayPlan(date=date).model_dump()
    await db.day_plans.insert_one({**plan})
    return plan


async def _get_or_init_journal(date: str) -> dict:
    item = await db.journal_entries.find_one({"date": date}, {"_id": 0})
    if item:
        return item
    j = JournalEntry(date=date).model_dump()
    await db.journal_entries.insert_one({**j})
    return j


def _fuzzy_match_index(items: list, text: str, key: str = "text") -> int:
    """Return index of the first item whose text contains or is contained in the query (case-insensitive)."""
    q = (text or "").strip().lower()
    if not q:
        return -1
    # Exact first
    for i, it in enumerate(items):
        if (it.get(key) or "").strip().lower() == q:
            return i
    # Contains
    for i, it in enumerate(items):
        t = (it.get(key) or "").strip().lower()
        if t and (q in t or t in q):
            return i
    return -1


async def execute_action(a: dict) -> dict:
    """Run a validated action. Returns a short summary of what happened."""
    t = a["type"]

    if t == "add_time_block":
        date = a["date"]
        block = TimeBlock(hour=a["hour"], text=a["text"].strip()[:80]).model_dump()
        plan = await _get_or_init_plan(date)
        blocks = list(plan.get("time_blocks") or [])
        blocks.append(block)
        blocks.sort(key=lambda b: b["hour"])
        await db.day_plans.update_one({"date": date}, {"$set": {"time_blocks": blocks, "updated_at": now_iso()}})
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
        await db.day_plans.update_one({"date": date}, {"$set": {"priorities": priorities[:3], "updated_at": now_iso()}})
        return {"ok": True, "message": f"Added priority: {text}"}

    if t == "add_chore":
        kind = a["kind"]
        text = a["text"].strip()[:120]
        date = a.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        field = {"house": "house_chores", "work": "work_chores", "morning": "morning_routine"}[kind]
        plan = await _get_or_init_plan(date)
        items = list(plan.get(field) or [])
        items.append(ChoreItem(text=text).model_dump())
        await db.day_plans.update_one({"date": date}, {"$set": {field: items, "updated_at": now_iso()}})
        return {"ok": True, "message": f"Added {kind} chore: {text}"}

    if t == "log_workout":
        from models import WorkoutLog
        name = a["name"].strip()[:120]
        dur = int(a["duration_min"])
        date = a.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log = WorkoutLog(
            workout_id="", workout_name=name, date=date,
            duration_min=dur,
            intensity=(a.get("intensity") or "moderate"),
            notes=(a.get("notes") or "")[:500],
        ).model_dump()
        await db.workout_logs.insert_one({**log})
        return {"ok": True, "message": f"Logged workout: {name} ({dur} min) on {date}"}

    if t == "log_journal":
        date = a.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        mood = int(a.get("mood", 3)) if a.get("mood") is not None else 3
        grat = (a.get("gratitude") or "").strip()
        entry_text = (a.get("entry") or "").strip()
        j = await _get_or_init_journal(date)
        gratitude = list(j.get("gratitude") or [])
        if grat:
            gratitude.append(grat[:160])
        reflection = (j.get("reflection") or "")
        if entry_text:
            reflection = (reflection + ("\n\n" if reflection else "") + entry_text).strip()[:4000]
        await db.journal_entries.update_one(
            {"date": date},
            {"$set": {"mood": mood, "gratitude": gratitude, "reflection": reflection}},
        )
        return {"ok": True, "message": f"Logged journal for {date}"}

    # --------- NEW ACTIONS ---------
    if t == "tick_priority":
        date = a["date"]
        plan = await _get_or_init_plan(date)
        priorities = list(plan.get("priorities") or ["", "", ""])
        status = list(plan.get("priority_status") or [
            {"done": False, "completed_at": None},
            {"done": False, "completed_at": None},
            {"done": False, "completed_at": None},
        ])
        while len(status) < 3:
            status.append({"done": False, "completed_at": None})

        idx = a.get("index")
        if idx is None:
            # Match by text
            query = (a.get("text") or "").strip().lower()
            for i, p in enumerate(priorities[:3]):
                if p.strip().lower() == query or (query and (query in p.lower() or p.lower() in query)):
                    idx = i
                    break
        if idx is None:
            return {"ok": False, "message": "Couldn't find a matching priority"}
        i = int(idx)
        done = not status[i].get("done", False) if a.get("toggle") else bool(a.get("done", True))
        status[i] = {"done": done, "completed_at": now_iso() if done else None}
        await db.day_plans.update_one({"date": date}, {"$set": {"priority_status": status[:3], "updated_at": now_iso()}})
        label = priorities[i] or f"priority {i + 1}"
        return {"ok": True, "message": f"{'Ticked' if done else 'Un-ticked'}: {label}"}

    if t == "tick_chore":
        kind = a["kind"]
        text = a["text"].strip()
        date = a.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        field = {"house": "house_chores", "work": "work_chores", "morning": "morning_routine"}[kind]
        plan = await _get_or_init_plan(date)
        items = list(plan.get(field) or [])
        i = _fuzzy_match_index(items, text)
        if i < 0:
            return {"ok": False, "message": f"Couldn't find a {kind} chore matching '{text}'"}
        done = not items[i].get("done", False) if a.get("toggle") else bool(a.get("done", True))
        items[i] = {**items[i], "done": done}
        await db.day_plans.update_one({"date": date}, {"$set": {field: items, "updated_at": now_iso()}})
        return {"ok": True, "message": f"{'Ticked' if done else 'Un-ticked'} {kind} chore: {items[i].get('text', '')}"}

    if t == "set_meal":
        date = a["date"]
        slot = a["slot"]
        text = a["text"].strip()[:160]
        plan = await _get_or_init_plan(date)
        meals = dict(plan.get("meals") or {})
        current = dict(meals.get(slot) or {"text": "", "recipe_id": ""})
        current["text"] = text
        meals[slot] = current
        await db.day_plans.update_one({"date": date}, {"$set": {"meals": meals, "updated_at": now_iso()}})
        return {"ok": True, "message": f"Set {slot}: {text}"}

    if t == "add_supplement":
        date = a["date"]
        name = a["name"].strip()[:80]
        plan = await _get_or_init_plan(date)
        supplements = list(plan.get("supplements") or [])
        supplements.append(Supplement(name=name, taken=False).model_dump())
        await db.day_plans.update_one({"date": date}, {"$set": {"supplements": supplements, "updated_at": now_iso()}})
        return {"ok": True, "message": f"Added supplement: {name}"}

    if t == "add_gratitude":
        date = a["date"]
        text = a["text"].strip()[:160]
        j = await _get_or_init_journal(date)
        gratitude = list(j.get("gratitude") or [])
        gratitude.append(text)
        await db.journal_entries.update_one({"date": date}, {"$set": {"gratitude": gratitude}})
        return {"ok": True, "message": f"Added gratitude: {text}"}

    if t == "log_mood":
        date = a["date"]
        mood = int(a["mood"])
        j = await _get_or_init_journal(date)
        await db.journal_entries.update_one({"date": date}, {"$set": {"mood": mood}})
        mood_label = {1: "rough", 2: "low", 3: "okay", 4: "good", 5: "great"}.get(mood, str(mood))
        return {"ok": True, "message": f"Logged mood: {mood_label} ({mood}/5) for {date}"}

    if t == "add_life_goal":
        goal = LifeGoal(
            year=int(a["year"]),
            age=int(a["age"]),
            category=(a.get("category") or "Life").strip()[:40],
            title=a["title"].strip()[:140],
            description=(a.get("description") or "").strip()[:600],
            status=a.get("status", "planned"),
        ).model_dump()
        await db.life_goals.insert_one({**goal})
        return {"ok": True, "message": f"Added life goal for {goal['year']} (age {goal['age']}): {goal['title']}"}

    if t == "add_family_memory":
        from family_models import FamilyMemory
        mem = FamilyMemory(
            title=a["title"].strip()[:140],
            date=a["date"],
            location=(a.get("location") or "").strip()[:120],
            story=(a.get("story") or "").strip()[:2000],
            tags=[t for t in (a.get("tags") or []) if isinstance(t, str)][:10],
        ).model_dump()
        await db.family_memories.insert_one({**mem})
        return {"ok": True, "message": f"Added family memory: {mem['title']} ({mem['date']})"}

    return {"ok": False, "message": f"Unknown action: {t}"}

"""Companion app-awareness: fetch compact summaries of the user's current state
so Claude can reason like an actual secretary/friend who knows what's going on."""
import re
from datetime import datetime, timedelta, timezone
from db import db

_YES = re.compile(r"\b(my|today|tomorrow|this week|schedule|day|plan|workout|gym|run|walk|training|mood|journal|feeling|stats|progress|streak|sober|focus|priorit|events?|birthday|weekend|meeting|appointment)\b", re.IGNORECASE)


def wants_user_context(msg: str) -> bool:
    """Cheap heuristic — if the message seems self-referential about plans/state."""
    return bool(_YES.search(msg or ""))


async def build_user_context() -> str:
    """Return a compact, reading-friendly summary of the user's current state."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

    blocks = []

    # Today's plan
    plan_today = await db.day_plans.find_one({"date": today}, {"_id": 0})
    plan_tom = await db.day_plans.find_one({"date": tomorrow}, {"_id": 0})
    if plan_today:
        pri = [p for p in (plan_today.get("priorities") or []) if p]
        tblocks = plan_today.get("time_blocks") or []
        parts = []
        if pri:
            parts.append("priorities: " + " · ".join(pri[:3]))
        if tblocks:
            parts.append("schedule: " + "; ".join(f"{b['hour']} {b['text']}" for b in tblocks[:8]))
        if plan_today.get("gym"):
            parts.append(f"gym: {plan_today['gym']}")
        if parts:
            blocks.append(f"Today's plan ({today}): " + " | ".join(parts))

    if plan_tom:
        tb = plan_tom.get("time_blocks") or []
        pri = [p for p in (plan_tom.get("priorities") or []) if p]
        parts = []
        if pri:
            parts.append("priorities: " + " · ".join(pri[:3]))
        if tb:
            parts.append("schedule: " + "; ".join(f"{b['hour']} {b['text']}" for b in tb[:6]))
        if parts:
            blocks.append(f"Tomorrow's plan ({tomorrow}): " + " | ".join(parts))

    # Upcoming events (next 14 days)
    future = (datetime.now(timezone.utc) + timedelta(days=14)).strftime("%Y-%m-%d")
    events = await db.events.find(
        {"date": {"$gte": today, "$lte": future}},
        {"_id": 0, "date": 1, "title": 1, "type": 1},
    ).sort("date", 1).to_list(10)
    if events:
        blocks.append("Coming up: " + "; ".join(f"{e['date']} {e['title']}" for e in events))

    # Recent workouts (this week)
    workouts = await db.workouts.find(
        {"date": {"$gte": week_ago}},
        {"_id": 0, "date": 1, "name": 1, "duration_min": 1},
    ).sort("date", -1).to_list(10)
    if workouts:
        total_min = sum(w.get("duration_min") or 0 for w in workouts)
        names = ", ".join(w.get("name", "session") for w in workouts[:4])
        blocks.append(f"Workouts (7d): {len(workouts)} sessions · {total_min} min — {names}")

    # Journal mood average + latest line
    entries = await db.journal_entries.find(
        {"date": {"$gte": week_ago}},
        {"_id": 0, "date": 1, "mood": 1, "entry": 1, "gratitude": 1},
    ).sort("date", -1).to_list(20)
    if entries:
        moods = [e.get("mood") for e in entries if isinstance(e.get("mood"), (int, float))]
        avg = round(sum(moods) / len(moods), 1) if moods else None
        parts = [f"{len(entries)} entries"]
        if avg is not None:
            parts.append(f"avg mood {avg}/5")
        last = entries[0].get("entry") or entries[0].get("gratitude") or ""
        if last:
            parts.append(f'last note: "{last[:120]}"')
        blocks.append("Journal (7d): " + " · ".join(parts))

    # Focus stats this week
    focus_sessions = await db.focus_sessions.find(
        {"completed": True, "ended_at": {"$gte": week_ago}},
        {"_id": 0, "duration_min": 1},
    ).to_list(100)
    if focus_sessions:
        total = sum(s.get("duration_min") or 0 for s in focus_sessions)
        blocks.append(f"Focus (7d): {total} min across {len(focus_sessions)} sessions")

    # Addictions — clean streak(s)
    addictions = await db.addictions.find({}, {"_id": 0, "name": 1, "started_clean": 1}).to_list(10)
    if addictions:
        now = datetime.now(timezone.utc)
        lines = []
        for a in addictions:
            try:
                sc = datetime.fromisoformat(a["started_clean"].replace("Z", "+00:00"))
                days = max(0, (now - sc).days)
                lines.append(f"{a['name']}: {days}d clean")
            except Exception:
                continue
        if lines:
            blocks.append("Streaks: " + " · ".join(lines))

    # Self profile (short summary)
    profile = await db.self_profile.find_one({"id": "default"}, {"_id": 0})
    if profile:
        bits = []
        for k in ("goal", "style", "gear", "personality"):
            v = (profile.get(k) or "").strip()
            if v:
                bits.append(f"{k}: {v[:80]}")
        if bits:
            blocks.append("You know about them: " + " | ".join(bits[:3]))

    if not blocks:
        return ""
    return "\n\n=== WHAT'S GOING ON IN THEIR LIFE RIGHT NOW ===\n" + "\n".join(f"- {b}" for b in blocks)

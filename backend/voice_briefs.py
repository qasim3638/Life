"""Spoken brief generators.
- Deterministic English for morning/evening/midday (faster, predictable, no LLM cost).
- AI-driven for `custom` briefs where the user provides a free-form prompt.
"""
from datetime import datetime, timedelta, timezone
from db import db


_WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_MONTHS = ["January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November", "December"]


def _say_date(d: datetime) -> str:
    return f"{_WEEKDAYS[d.weekday()]} the {d.day}{_ordinal(d.day)} of {_MONTHS[d.month - 1]}"


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def _say_time(t: str) -> str:
    """24h '17:30' -> 'half past five in the afternoon'-ish; keep simple: '5:30 PM'."""
    try:
        h, m = t.split(":")
        h = int(h)
        m = int(m)
        suffix = "AM" if h < 12 else "PM"
        h12 = h % 12 or 12
        return f"{h12}:{m:02d} {suffix}" if m else f"{h12} {suffix}"
    except Exception:
        return t


async def generate_brief(kind: str) -> str:
    """Build a short (~25-45s spoken) brief based on live data."""
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")

    companion = await db.companion.find_one({"id": "default"}, {"_id": 0}) or {}
    user_name = (companion.get("user_name") or "").strip() or "there"
    plan = await db.day_plans.find_one({"date": today}, {"_id": 0}) or {}
    plan_tom = await db.day_plans.find_one({"date": tomorrow}, {"_id": 0}) or {}
    journal = await db.journal_entries.find_one({"date": today}, {"_id": 0}) or {}

    priorities = [p.strip() for p in (plan.get("priorities") or []) if p and p.strip()]
    pri_status = plan.get("priority_status") or [{"done": False}] * 3
    done_count = sum(1 for i, p in enumerate(priorities) if i < len(pri_status) and pri_status[i].get("done"))

    chores_total = (
        len(plan.get("morning_routine") or [])
        + len(plan.get("house_chores") or [])
        + len(plan.get("work_chores") or [])
    )
    chores_done = (
        sum(1 for c in (plan.get("morning_routine") or []) if c.get("done"))
        + sum(1 for c in (plan.get("house_chores") or []) if c.get("done"))
        + sum(1 for c in (plan.get("work_chores") or []) if c.get("done"))
    )

    events_today_cur = db.events.find({"date": today}, {"_id": 0})
    events_today = await events_today_cur.to_list(20)
    events_tom_cur = db.events.find({"date": tomorrow}, {"_id": 0})
    events_tom = await events_tom_cur.to_list(20)

    if kind == "morning":
        lines = [f"Good morning, {user_name}.", f"Today is {_say_date(now)}."]
        if priorities:
            n = len(priorities)
            label = "priority" if n == 1 else "priorities"
            lines.append(f"You've got {n} {label} on the board today.")
            for i, p in enumerate(priorities):
                lines.append(f"Number {i + 1}: {p}.")
        else:
            lines.append("You haven't set any priorities yet — pick three when you're ready.")

        if plan.get("gym_planned"):
            name = (plan.get("gym_workout_name") or "your workout").strip()
            lines.append(f"Gym is on the cards today — {name}.")

        if events_today:
            n = len(events_today)
            lines.append(f"You have {n} event{'s' if n != 1 else ''} in the calendar today.")
            for ev in events_today[:3]:
                lines.append(f"{ev.get('title', '')}.")

        # Gaps (gentle nudges)
        # Last journal & last workout
        last_j = await db.journal_entries.find_one(sort=[("date", -1)], projection={"_id": 0})
        if last_j:
            try:
                ld = datetime.strptime(last_j.get("date", ""), "%Y-%m-%d")
                gap = (now.replace(tzinfo=None) - ld).days
                if gap >= 3:
                    lines.append(f"It's been {gap} days since you journaled — even a sentence helps.")
            except Exception:
                pass

        lines.append("Make it a good one.")
        return " ".join(lines)

    if kind == "midday":
        remaining = [p for i, p in enumerate(priorities) if i < len(pri_status) and not pri_status[i].get("done")]
        lines = [f"Quick check-in, {user_name}."]
        if priorities:
            if done_count == len(priorities):
                lines.append("All three priorities ticked off — that's a win.")
            elif done_count > 0:
                lines.append(f"You've finished {done_count} of {len(priorities)} priorities.")
                if remaining:
                    lines.append(f"Still on the list: {remaining[0]}.")
            else:
                lines.append("None of your priorities are ticked yet.")
                if remaining:
                    lines.append(f"Easy first move: {remaining[0]}.")
        if chores_total > 0:
            lines.append(f"Chores: {chores_done} of {chores_total} done.")
        if not priorities and chores_total == 0:
            lines.append("Nothing on the board today. If that's deliberate, good. If not, set one thing.")
        lines.append("Half the day's still yours.")
        return " ".join(lines)

    if kind == "evening":
        lines = [f"Wind-down time, {user_name}."]
        if priorities:
            if done_count == len(priorities):
                lines.append(f"All {len(priorities)} priorities done — that's a complete day.")
            elif done_count > 0:
                lines.append(f"You finished {done_count} of {len(priorities)} priorities today.")
            else:
                lines.append("None of today's priorities got ticked. Worth a thought before bed.")
        if chores_total > 0:
            lines.append(f"You ticked {chores_done} of {chores_total} chores.")
        # Mood already logged?
        if journal.get("mood"):
            mood = journal["mood"]
            label = {1: "rough", 2: "low", 3: "okay", 4: "good", 5: "great"}.get(mood, "")
            lines.append(f"You logged today as {label}.")
        else:
            lines.append("You haven't logged a mood for today yet — one to five, how was it?")
        # Tomorrow's first move
        tom_pri = [p for p in (plan_tom.get("priorities") or []) if p and p.strip()]
        if tom_pri:
            lines.append(f"Tomorrow's first priority: {tom_pri[0]}.")
        elif events_tom:
            lines.append(f"Tomorrow you have {events_tom[0].get('title', 'something on')}.")
        else:
            lines.append("Nothing's planned for tomorrow yet — set one thing tonight, future-you will thank you.")
        lines.append("Sleep well.")
        return " ".join(lines)

    return ""  # unknown kind handled by caller

"""AI Companion: settings, memories, messages, chat (with background memory auto-extract)."""
import json
import re
import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, BackgroundTasks, HTTPException
from db import db
from models import (
    Companion, CompanionUpdate, CompanionMemory, CompanionMemoryCreate,
    CompanionMemoryUpdate, CompanionMessage, ChatRequest, new_id,
)
from ai_helper import run_ai, PERSONA_PROMPTS
from companion_actions import validate_action, execute_action

router = APIRouter()
logger = logging.getLogger(__name__)

AUTO_MEMORY_CAP = 200  # max non-pinned auto memories


def _tokens(s: str) -> set:
    # Light stemming: strip trailing 's' on tokens to merge years/year, loves/love
    raw = re.findall(r"[a-z0-9]+", (s or "").lower())
    return {t[:-1] if len(t) > 3 and t.endswith("s") else t for t in raw}


def _jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


DEDUPE_THRESHOLD = 0.55


async def get_or_create_companion() -> dict:
    item = await db.companion.find_one({"id": "default"}, {"_id": 0})
    if not item:
        c = Companion()
        await db.companion.insert_one(c.model_dump())
        return c.model_dump()
    return item


@router.get("/companion")
async def get_companion():
    return await get_or_create_companion()


@router.put("/companion")
async def update_companion(payload: CompanionUpdate):
    await get_or_create_companion()
    update = {k: v for k, v in payload.model_dump().items() if v is not None}
    if update:
        await db.companion.update_one({"id": "default"}, {"$set": update})
    return await db.companion.find_one({"id": "default"}, {"_id": 0})


@router.get("/companion/memories")
async def list_memories():
    return await db.companion_memories.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)


@router.post("/companion/memories")
async def add_memory(payload: CompanionMemoryCreate):
    m = CompanionMemory(**payload.model_dump())
    await db.companion_memories.insert_one(m.model_dump())
    return m


@router.delete("/companion/memories/{memory_id}")
async def delete_memory(memory_id: str):
    await db.companion_memories.delete_one({"id": memory_id})
    return {"ok": True}


@router.patch("/companion/memories/{memory_id}")
async def update_memory(memory_id: str, payload: CompanionMemoryUpdate):
    update = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not update:
        return {"ok": True}
    await db.companion_memories.update_one({"id": memory_id}, {"$set": update})
    item = await db.companion_memories.find_one({"id": memory_id}, {"_id": 0})
    return item or {"ok": True}


@router.get("/companion/messages")
async def list_messages():
    return await db.companion_messages.find({}, {"_id": 0}).sort("created_at", 1).to_list(2000)


@router.delete("/companion/messages")
async def clear_messages():
    await db.companion_messages.delete_many({})
    return {"ok": True}


async def _prune_auto_memories():
    """Evict oldest non-pinned auto memories above AUTO_MEMORY_CAP."""
    try:
        total_auto = await db.companion_memories.count_documents(
            {"category": "auto", "pinned": {"$ne": True}}
        )
        if total_auto > AUTO_MEMORY_CAP:
            evict_count = total_auto - AUTO_MEMORY_CAP
            old = await db.companion_memories.find(
                {"category": "auto", "pinned": {"$ne": True}}, {"_id": 0, "id": 1}
            ).sort("created_at", 1).to_list(evict_count)
            for o in old:
                await db.companion_memories.delete_one({"id": o["id"]})
    except Exception as e:
        logger.warning(f"Auto-memory prune failed: {e}")


async def _auto_extract_memories(user_message: str):
    """Background task: extract 0-3 memorable facts from a user message and save them."""
    # Always run TTL prune so it cannot be skipped by an AI parse failure
    try:
        if len(user_message.strip()) >= 80:
            recent_auto = await db.companion_memories.find(
                {"category": "auto"}, {"_id": 0, "content": 1}
            ).sort("created_at", -1).to_list(50)
            recent_contents = [m.get("content", "") for m in recent_auto]

            system = (
                "You extract durable facts to remember about the user from a single message. "
                "Return ONLY a JSON array of 0-3 short third-person sentences (max 18 words each), "
                "no commentary. Empty array [] if nothing memorable. Do NOT extract feelings of the moment, "
                "questions, or generic statements. Only personal facts (relationships, jobs, places, "
                "preferences, beliefs, milestones, hopes)."
            )
            try:
                text = await run_ai(system, user_message)
                match = re.search(r"\[.*\]", text, re.DOTALL)
                if match:
                    items = json.loads(match.group(0))
                    if isinstance(items, list):
                        for fact in items:
                            if not isinstance(fact, str):
                                continue
                            fact = fact.strip()
                            if not fact or len(fact) > 240:
                                continue
                            if any(_jaccard(fact, prev) >= DEDUPE_THRESHOLD for prev in recent_contents):
                                continue
                            mem = CompanionMemory(content=fact, category="auto")
                            await db.companion_memories.insert_one(mem.model_dump())
                            recent_contents.append(fact)
            except Exception as e:
                logger.warning(f"Auto-extract LLM step failed: {e}")
    finally:
        await _prune_auto_memories()


@router.post("/companion/chat")
async def companion_chat(req: ChatRequest, background: BackgroundTasks):
    companion = await get_or_create_companion()
    persona = companion.get("persona", "friend")
    name = companion.get("name", "Najm")
    user_name = companion.get("user_name", "friend")

    memories = await db.companion_memories.find({}, {"_id": 0}).sort("created_at", -1).to_list(50)
    history = await db.companion_messages.find({}, {"_id": 0}).sort("created_at", -1).to_list(20)
    history.reverse()

    persona_msg = PERSONA_PROMPTS.get(persona, PERSONA_PROMPTS["friend"])
    memory_block = ""
    if memories:
        memory_block = "\n\nThings you remember about the user:\n" + "\n".join(
            f"- ({m.get('category', 'general')}) {(m.get('content', '') or '')[:240]}"
            for m in memories[:30]
        )

    history_block = ""
    if history:
        lines = []
        for m in history[-12:]:
            role = "User" if m["role"] == "user" else "You"
            lines.append(f"{role}: {m['content']}")
        history_block = "\n\nRecent conversation:\n" + "\n".join(lines)

    # Action envelope: today + tomorrow dates so Claude can resolve "tomorrow", "Friday", etc.
    today = datetime.now(timezone.utc)
    today_iso = today.strftime("%Y-%m-%d")
    tomorrow_iso = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    weekday_name = today.strftime("%A")
    action_instructions = (
        "\n\n=== ACTION PROTOCOL ===\n"
        f"Today is {weekday_name} {today_iso}. Tomorrow is {tomorrow_iso}.\n"
        "If the user is asking you to actually DO something in the app "
        "(add to schedule, add event, add priority, add chore), respond with ONLY a JSON "
        "object in this exact shape — no prose outside the JSON, no code fences:\n"
        '{"reply": "<friendly 1-sentence confirmation>", "actions": [ <action>, ... ]}\n'
        "Allowed action shapes:\n"
        '  {"type": "add_time_block", "date": "YYYY-MM-DD", "hour": "HH:MM", "text": "<≤80 chars>"}\n'
        '  {"type": "add_event", "date": "YYYY-MM-DD", "title": "<title>", "notes": "<optional>"}\n'
        '  {"type": "add_priority", "date": "YYYY-MM-DD", "text": "<≤120 chars>"}\n'
        '  {"type": "add_chore", "kind": "house"|"work"|"morning", "text": "<≤120 chars>", "date": "YYYY-MM-DD"}\n'
        "Use 24h hours. If user says 'tomorrow', resolve to the date above. "
        "If the user is NOT asking for an action (chatting, venting, asking a question), "
        "respond with plain prose — NOT the JSON shape."
    )

    system_msg = (
        f"Your name is {name}. You are speaking to {user_name}. "
        f"{persona_msg} "
        "Keep replies under 180 words unless asked for more. Never use bullet lists longer than 3 items. "
        "Refer back to the user's memories naturally when relevant - you genuinely remember them. "
        "Never use emojis."
        f"{memory_block}{history_block}{action_instructions}"
    )

    user_msg = CompanionMessage(role="user", content=req.message, persona=persona)
    await db.companion_messages.insert_one(user_msg.model_dump())

    try:
        raw_reply = await run_ai(system_msg, req.message)
    except Exception as e:
        logger.error(f"Companion chat error: {e}")
        raw_reply = "I'm here. Let's try that again in a moment."

    # Try to parse the action envelope. Fall back to plain text.
    reply_text, actions = _parse_action_envelope(raw_reply)

    assistant_msg = CompanionMessage(
        role="assistant",
        content=reply_text,
        persona=persona,
        actions=actions,
    )
    await db.companion_messages.insert_one(assistant_msg.model_dump())

    # Fire-and-forget background memory extraction
    background.add_task(_auto_extract_memories, req.message)

    return {
        "user_message": user_msg.model_dump(),
        "reply": assistant_msg.model_dump(),
    }


def _parse_action_envelope(text: str) -> tuple[str, list]:
    """Try to parse `{reply, actions}` envelope. Return (reply_text, [actions_with_status])."""
    if not text or "actions" not in text or "{" not in text:
        return text, []
    # Strip code fences if Claude used them despite instructions
    stripped = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    # Grab the first JSON object
    m = re.search(r"\{.*\}", stripped, re.DOTALL)
    if not m:
        return text, []
    try:
        obj = json.loads(m.group(0))
    except Exception:
        return text, []
    if not isinstance(obj, dict) or not isinstance(obj.get("actions"), list):
        return text, []
    reply = str(obj.get("reply") or "").strip() or "Here's what I've got:"
    actions_out = []
    for raw in obj["actions"]:
        ok, reason = validate_action(raw)
        if not ok:
            continue
        # Whitelist only allowed keys by type; don't trust extras
        cleaned = {k: v for k, v in raw.items() if k in {
            "type", "date", "hour", "text", "title", "notes", "kind", "event_type", "recurring"
        }}
        cleaned["status"] = "pending"
        cleaned["id"] = new_id()
        actions_out.append(cleaned)
    return reply, actions_out


@router.post("/companion/messages/{mid}/actions/{aid}/apply")
async def apply_action(mid: str, aid: str):
    msg = await db.companion_messages.find_one({"id": mid}, {"_id": 0})
    if not msg:
        raise HTTPException(404, "Message not found")
    actions = list(msg.get("actions") or [])
    idx = next((i for i, a in enumerate(actions) if a.get("id") == aid), -1)
    if idx < 0:
        raise HTTPException(404, "Action not found on this message")
    action = actions[idx]
    if action.get("status") != "pending":
        return {"ok": True, "already": action.get("status")}
    ok, reason = validate_action(action)
    if not ok:
        raise HTTPException(400, f"Invalid action: {reason}")
    try:
        result = await execute_action(action)
    except Exception as e:
        logger.exception("Action execution failed")
        raise HTTPException(500, f"Couldn't apply: {e}")
    actions[idx] = {**action, "status": "applied", "result": result.get("message", "")}
    await db.companion_messages.update_one({"id": mid}, {"$set": {"actions": actions}})
    return {"ok": True, "action": actions[idx]}


@router.post("/companion/messages/{mid}/actions/{aid}/cancel")
async def cancel_action(mid: str, aid: str):
    msg = await db.companion_messages.find_one({"id": mid}, {"_id": 0})
    if not msg:
        raise HTTPException(404, "Message not found")
    actions = list(msg.get("actions") or [])
    idx = next((i for i, a in enumerate(actions) if a.get("id") == aid), -1)
    if idx < 0:
        raise HTTPException(404, "Action not found")
    if actions[idx].get("status") == "pending":
        actions[idx] = {**actions[idx], "status": "cancelled"}
        await db.companion_messages.update_one({"id": mid}, {"$set": {"actions": actions}})
    return {"ok": True, "action": actions[idx]}


# Local import no longer needed; new_id imported at top of module via models in companion_actions usage

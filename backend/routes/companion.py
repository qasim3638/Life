"""AI Companion: settings, memories, messages, chat (with background memory auto-extract)."""
import json
import re
import logging
from fastapi import APIRouter, BackgroundTasks
from db import db
from models import (
    Companion, CompanionUpdate, CompanionMemory, CompanionMemoryCreate,
    CompanionMemoryUpdate, CompanionMessage, ChatRequest,
)
from ai_helper import run_ai, PERSONA_PROMPTS

router = APIRouter()
logger = logging.getLogger(__name__)

AUTO_MEMORY_CAP = 200  # max non-pinned auto memories


def _tokens(s: str) -> set:
    return set(re.findall(r"[a-z0-9]+", (s or "").lower()))


def _jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


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


async def _auto_extract_memories(user_message: str):
    """Background task: extract 0-3 memorable facts from a user message and save them."""
    if len(user_message.strip()) < 80:
        return
    try:
        # Pull recent auto memories for dedupe
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
        text = await run_ai(system, user_message)
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            return
        items = json.loads(match.group(0))
        if not isinstance(items, list):
            return

        for fact in items:
            if not isinstance(fact, str):
                continue
            fact = fact.strip()
            if not fact or len(fact) > 240:
                continue
            # Jaccard dedupe vs recent auto memories
            if any(_jaccard(fact, prev) >= 0.7 for prev in recent_contents):
                continue
            mem = CompanionMemory(content=fact, category="auto")
            await db.companion_memories.insert_one(mem.model_dump())
            recent_contents.append(fact)

        # TTL prune: if non-pinned auto memories exceed cap, evict oldest
        total_auto = await db.companion_memories.count_documents({"category": "auto", "pinned": {"$ne": True}})
        if total_auto > AUTO_MEMORY_CAP:
            evict_count = total_auto - AUTO_MEMORY_CAP
            old = await db.companion_memories.find(
                {"category": "auto", "pinned": {"$ne": True}}, {"_id": 0, "id": 1}
            ).sort("created_at", 1).to_list(evict_count)
            for o in old:
                await db.companion_memories.delete_one({"id": o["id"]})
    except Exception as e:
        logger.warning(f"Auto-extract memory failed: {e}")


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

    system_msg = (
        f"Your name is {name}. You are speaking to {user_name}. "
        f"{persona_msg} "
        "Keep replies under 180 words unless asked for more. Never use bullet lists longer than 3 items. "
        "Refer back to the user's memories naturally when relevant - you genuinely remember them. "
        "Never use emojis."
        f"{memory_block}{history_block}"
    )

    user_msg = CompanionMessage(role="user", content=req.message, persona=persona)
    await db.companion_messages.insert_one(user_msg.model_dump())

    try:
        reply_text = await run_ai(system_msg, req.message)
    except Exception as e:
        logger.error(f"Companion chat error: {e}")
        reply_text = "I'm here. Let's try that again in a moment."

    assistant_msg = CompanionMessage(role="assistant", content=reply_text, persona=persona)
    await db.companion_messages.insert_one(assistant_msg.model_dump())

    # Fire-and-forget background memory extraction
    background.add_task(_auto_extract_memories, req.message)

    return {
        "user_message": user_msg.model_dump(),
        "reply": assistant_msg.model_dump(),
    }

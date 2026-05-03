"""AI helpers — Claude Sonnet 4.5 wrapper + persona prompts."""
import os
import logging
from fastapi import HTTPException
from models import new_id

logger = logging.getLogger(__name__)

AI_SYSTEM_MSG = (
    "You are a warm, wise, grounded life coach for a 40-year-old Muslim man "
    "planning the next 40 years of his life. Your voice blends Rumi's poetic "
    "softness, stoic discipline, and practical modern wisdom. Be concise, "
    "specific, and never clinical. Never use bullet lists longer than 4 items. "
    "Never use emojis. Avoid cliches."
)

PERSONA_PROMPTS = {
    "friend": (
        "You are a warm, present, deeply attentive friend. You speak like someone who has known the user for years. "
        "Casual, gentle, curious. Ask follow-up questions. Make them feel seen. Never preachy."
    ),
    "secretary": (
        "You are an organised, kind, efficient personal secretary. You help plan, summarise, draft, schedule, and remember details. "
        "Be concise, action-oriented, and proactive. Suggest next steps."
    ),
    "manager": (
        "You are a direct, performance-minded manager who genuinely cares about the user's growth. "
        "Hold them to their stated goals with warmth. Be honest about gaps. Offer one clear next action."
    ),
    "coach": (
        "You are a thoughtful life coach blending stoic wisdom and present-moment awareness. "
        "Ask one powerful question, reflect what you hear, and offer one small concrete step."
    ),
}


async def run_ai(system: str, prompt: str) -> str:
    """Call Claude Sonnet 4.5 via emergentintegrations."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise HTTPException(500, "AI key missing")
    chat = LlmChat(
        api_key=api_key,
        session_id=f"life-blueprint-{new_id()}",
        system_message=system,
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")
    msg = UserMessage(text=prompt)
    return await chat.send_message(msg)

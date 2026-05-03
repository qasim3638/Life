from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime, timezone, timedelta

from seed_data import (
    RECIPES_SEED,
    QUOTES_SEED,
    PODCASTS_SEED,
    MEDITATIONS_SEED,
    AFFIRMATIONS_SEED,
)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Seed on startup (idempotent)
    try:
        if await db.recipes.count_documents({"is_custom": False}) == 0:
            for r in RECIPES_SEED:
                doc = Recipe(**r, is_custom=False).model_dump()
                await db.recipes.insert_one(doc)
        if await db.quotes.count_documents({}) == 0:
            for q in QUOTES_SEED:
                await db.quotes.insert_one({"id": new_id(), **q})
        if await db.podcasts.count_documents({}) == 0:
            for p in PODCASTS_SEED:
                await db.podcasts.insert_one({"id": new_id(), **p})
        if await db.meditations.count_documents({}) == 0:
            for m in MEDITATIONS_SEED:
                await db.meditations.insert_one({"id": new_id(), **m})
        if await db.affirmations.count_documents({}) == 0:
            for a in AFFIRMATIONS_SEED:
                await db.affirmations.insert_one({"id": new_id(), "text": a})
        logger.info("Seed data ready.")
    except Exception as e:
        logger.error(f"Seeding error: {e}")
    yield
    client.close()


app = FastAPI(title="Life Blueprint API", lifespan=lifespan)
api_router = APIRouter(prefix="/api")

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# ============ UTIL ============
def new_id() -> str:
    return str(uuid.uuid4())


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ============ MODELS ============
class Workout(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str
    category: str = "Strength"  # Strength, Cardio, Mobility, Yoga, HIIT
    notes: Optional[str] = ""
    exercises: List[dict] = []  # [{name, sets, reps, rest, weight}]
    created_at: str = Field(default_factory=now_iso)


class WorkoutCreate(BaseModel):
    name: str
    category: str = "Strength"
    notes: Optional[str] = ""
    exercises: List[dict] = []


class WorkoutLog(BaseModel):
    id: str = Field(default_factory=new_id)
    workout_id: str
    workout_name: str
    date: str
    duration_min: int = 0
    notes: str = ""
    created_at: str = Field(default_factory=now_iso)


class WorkoutLogCreate(BaseModel):
    workout_id: str
    workout_name: str
    date: str
    duration_min: int = 0
    notes: str = ""


class Recipe(BaseModel):
    id: str = Field(default_factory=new_id)
    title: str
    cuisine: str
    meal_type: str
    prep_time: int
    servings: int
    calories: int
    protein: int
    carbs: int
    fat: int
    ingredients: List[str]
    instructions: List[str]
    tags: List[str] = []
    image: Optional[str] = ""
    is_custom: bool = False
    created_at: str = Field(default_factory=now_iso)


class RecipeCreate(BaseModel):
    title: str
    cuisine: str
    meal_type: str
    prep_time: int
    servings: int
    calories: int
    protein: int
    carbs: int
    fat: int
    ingredients: List[str]
    instructions: List[str]
    tags: List[str] = []
    image: Optional[str] = ""


class JournalEntry(BaseModel):
    id: str = Field(default_factory=new_id)
    date: str  # YYYY-MM-DD
    mood: int = 3  # 1-5
    gratitude: List[str] = []
    reflection: str = ""
    created_at: str = Field(default_factory=now_iso)


class JournalEntryCreate(BaseModel):
    date: str
    mood: int = 3
    gratitude: List[str] = []
    reflection: str = ""


class Event(BaseModel):
    id: str = Field(default_factory=new_id)
    title: str
    date: str  # YYYY-MM-DD
    type: str = "event"  # birthday, anniversary, goal, reminder, event
    recurring: bool = False
    notes: str = ""
    created_at: str = Field(default_factory=now_iso)


class EventCreate(BaseModel):
    title: str
    date: str
    type: str = "event"
    recurring: bool = False
    notes: str = ""


class LifeGoal(BaseModel):
    id: str = Field(default_factory=new_id)
    year: int  # Target year (e.g., 2026-2065)
    age: int  # Age at target (40-80)
    category: str = "Life"  # Health, Career, Family, Spiritual, Financial, Adventure
    title: str
    description: str = ""
    status: str = "planned"  # planned, in_progress, achieved
    created_at: str = Field(default_factory=now_iso)


class LifeGoalCreate(BaseModel):
    year: int
    age: int
    category: str = "Life"
    title: str
    description: str = ""
    status: str = "planned"


class AIPrompt(BaseModel):
    prompt: str
    context: Optional[str] = ""


class DayPlan(BaseModel):
    date: str  # YYYY-MM-DD (also the unique key)
    priorities: List[str] = ["", "", ""]
    gym_planned: bool = False
    gym_workout_id: Optional[str] = ""
    gym_workout_name: Optional[str] = ""
    meals: dict = Field(default_factory=lambda: {
        "breakfast": {"text": "", "recipe_id": ""},
        "lunch": {"text": "", "recipe_id": ""},
        "dinner": {"text": "", "recipe_id": ""},
        "snack": {"text": "", "recipe_id": ""},
    })
    supplements: List[dict] = []  # [{name, taken}]
    house_chores: List[dict] = []  # [{text, done}]
    work_chores: List[dict] = []
    sleep_target: str = "23:00"
    wake_target: str = "06:30"
    hydration_oz: int = 80
    notes: str = ""
    updated_at: str = Field(default_factory=now_iso)


class Companion(BaseModel):
    id: str = "default"
    name: str = "Najm"
    user_name: str = "friend"
    persona: str = "friend"  # friend, secretary, manager, coach
    created_at: str = Field(default_factory=now_iso)


class CompanionUpdate(BaseModel):
    name: Optional[str] = None
    user_name: Optional[str] = None
    persona: Optional[str] = None


class CompanionMemory(BaseModel):
    id: str = Field(default_factory=new_id)
    content: str
    category: str = "general"  # general, family, work, health, dream, story
    created_at: str = Field(default_factory=now_iso)


class CompanionMemoryCreate(BaseModel):
    content: str
    category: str = "general"


class CompanionMessage(BaseModel):
    id: str = Field(default_factory=new_id)
    role: str  # user | assistant
    content: str
    persona: str = "friend"
    created_at: str = Field(default_factory=now_iso)


class ChatRequest(BaseModel):
    message: str


# ============ ROOT ============
@api_router.get("/")
async def root():
    return {"message": "Life Blueprint API", "status": "ok"}


# ============ WORKOUTS ============
@api_router.post("/workouts", response_model=Workout)
async def create_workout(payload: WorkoutCreate):
    w = Workout(**payload.model_dump())
    await db.workouts.insert_one(w.model_dump())
    return w


@api_router.get("/workouts", response_model=List[Workout])
async def list_workouts():
    items = await db.workouts.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return items


@api_router.get("/workouts/{workout_id}", response_model=Workout)
async def get_workout(workout_id: str):
    item = await db.workouts.find_one({"id": workout_id}, {"_id": 0})
    if not item:
        raise HTTPException(404, "Workout not found")
    return item


@api_router.put("/workouts/{workout_id}", response_model=Workout)
async def update_workout(workout_id: str, payload: WorkoutCreate):
    res = await db.workouts.update_one({"id": workout_id}, {"$set": payload.model_dump()})
    if res.matched_count == 0:
        raise HTTPException(404, "Workout not found")
    item = await db.workouts.find_one({"id": workout_id}, {"_id": 0})
    return item


@api_router.delete("/workouts/{workout_id}")
async def delete_workout(workout_id: str):
    await db.workouts.delete_one({"id": workout_id})
    return {"ok": True}


@api_router.post("/workout-logs", response_model=WorkoutLog)
async def create_workout_log(payload: WorkoutLogCreate):
    log = WorkoutLog(**payload.model_dump())
    await db.workout_logs.insert_one(log.model_dump())
    return log


@api_router.get("/workout-logs", response_model=List[WorkoutLog])
async def list_workout_logs():
    items = await db.workout_logs.find({}, {"_id": 0}).sort("date", -1).to_list(500)
    return items


# ============ RECIPES ============
@api_router.get("/recipes", response_model=List[Recipe])
async def list_recipes(cuisine: Optional[str] = None, meal_type: Optional[str] = None):
    q: dict = {}
    if cuisine:
        q["cuisine"] = cuisine
    if meal_type:
        q["meal_type"] = meal_type
    items = await db.recipes.find(q, {"_id": 0}).to_list(500)
    return items


@api_router.get("/recipes/{recipe_id}", response_model=Recipe)
async def get_recipe(recipe_id: str):
    item = await db.recipes.find_one({"id": recipe_id}, {"_id": 0})
    if not item:
        raise HTTPException(404, "Recipe not found")
    return item


@api_router.post("/recipes", response_model=Recipe)
async def create_recipe(payload: RecipeCreate):
    r = Recipe(**payload.model_dump(), is_custom=True)
    await db.recipes.insert_one(r.model_dump())
    return r


@api_router.delete("/recipes/{recipe_id}")
async def delete_recipe(recipe_id: str):
    await db.recipes.delete_one({"id": recipe_id, "is_custom": True})
    return {"ok": True}


# ============ JOURNAL ============
@api_router.post("/journal-entries", response_model=JournalEntry)
async def create_journal(payload: JournalEntryCreate):
    j = JournalEntry(**payload.model_dump())
    await db.journal_entries.insert_one(j.model_dump())
    return j


@api_router.get("/journal-entries", response_model=List[JournalEntry])
async def list_journal():
    items = await db.journal_entries.find({}, {"_id": 0}).sort("date", -1).to_list(500)
    return items


@api_router.delete("/journal-entries/{entry_id}")
async def delete_journal(entry_id: str):
    await db.journal_entries.delete_one({"id": entry_id})
    return {"ok": True}


# ============ EVENTS ============
@api_router.post("/events", response_model=Event)
async def create_event(payload: EventCreate):
    e = Event(**payload.model_dump())
    await db.events.insert_one(e.model_dump())
    return e


@api_router.get("/events", response_model=List[Event])
async def list_events():
    items = await db.events.find({}, {"_id": 0}).sort("date", 1).to_list(500)
    return items


@api_router.put("/events/{event_id}", response_model=Event)
async def update_event(event_id: str, payload: EventCreate):
    res = await db.events.update_one({"id": event_id}, {"$set": payload.model_dump()})
    if res.matched_count == 0:
        raise HTTPException(404, "Event not found")
    item = await db.events.find_one({"id": event_id}, {"_id": 0})
    return item


@api_router.delete("/events/{event_id}")
async def delete_event(event_id: str):
    await db.events.delete_one({"id": event_id})
    return {"ok": True}


# ============ LIFE GOALS ============
@api_router.post("/life-goals", response_model=LifeGoal)
async def create_life_goal(payload: LifeGoalCreate):
    g = LifeGoal(**payload.model_dump())
    await db.life_goals.insert_one(g.model_dump())
    return g


@api_router.get("/life-goals", response_model=List[LifeGoal])
async def list_life_goals():
    items = await db.life_goals.find({}, {"_id": 0}).sort("year", 1).to_list(500)
    return items


@api_router.put("/life-goals/{goal_id}", response_model=LifeGoal)
async def update_life_goal(goal_id: str, payload: LifeGoalCreate):
    res = await db.life_goals.update_one({"id": goal_id}, {"$set": payload.model_dump()})
    if res.matched_count == 0:
        raise HTTPException(404, "Goal not found")
    item = await db.life_goals.find_one({"id": goal_id}, {"_id": 0})
    return item


@api_router.delete("/life-goals/{goal_id}")
async def delete_life_goal(goal_id: str):
    await db.life_goals.delete_one({"id": goal_id})
    return {"ok": True}


# ============ CURATED CONTENT ============
@api_router.get("/quotes")
async def list_quotes():
    items = await db.quotes.find({}, {"_id": 0}).to_list(500)
    return items


@api_router.get("/podcasts")
async def list_podcasts():
    items = await db.podcasts.find({}, {"_id": 0}).to_list(500)
    return items


@api_router.get("/meditations")
async def list_meditations():
    items = await db.meditations.find({}, {"_id": 0}).to_list(500)
    return items


@api_router.get("/affirmations")
async def list_affirmations():
    items = await db.affirmations.find({}, {"_id": 0}).to_list(500)
    return items


# ============ AI (Claude Sonnet 4.5) ============
AI_SYSTEM_MSG = (
    "You are a warm, wise, grounded life coach for a 40-year-old Muslim man "
    "planning the next 40 years of his life. Your voice blends Rumi's poetic "
    "softness, stoic discipline, and practical modern wisdom. Be concise, "
    "specific, and never clinical. Never use bullet lists longer than 4 items. "
    "Never use emojis. Avoid cliches."
)


async def _run_ai(system: str, prompt: str) -> str:
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


@api_router.post("/ai/motivation")
async def ai_motivation(body: AIPrompt):
    prompt = (
        "Write a single short, powerful motivational reflection (80-120 words) "
        "for today. Ground it in stoic wisdom or Rumi-like poetry. "
        f"Context from the user: {body.context or 'Starting a new week'}."
    )
    try:
        text = await _run_ai(AI_SYSTEM_MSG, prompt)
        return {"text": text}
    except Exception as e:
        logger.error(f"AI motivation error: {e}")
        return {"text": "The path forward is made by walking it. Take one honest step today.", "error": str(e)}


@api_router.post("/ai/reflect")
async def ai_reflect(body: AIPrompt):
    prompt = (
        f"The user shared this reflection: '{body.prompt}'. "
        "Respond as a wise, compassionate coach. 100-150 words. "
        "Acknowledge what you hear, offer one gentle insight, and one small "
        "action they can take within 24 hours."
    )
    try:
        text = await _run_ai(AI_SYSTEM_MSG, prompt)
        return {"text": text}
    except Exception as e:
        logger.error(f"AI reflect error: {e}")
        return {"text": "Your words matter. Sit with them gently today.", "error": str(e)}


@api_router.post("/ai/meal-suggestion")
async def ai_meal(body: AIPrompt):
    prompt = (
        "Suggest ONE specific halal, low-carb high-protein meal idea suited for a "
        "40-year-old wanting to stay lean and energetic. Prefer Pakistani, Indian, "
        "or Arab cuisine. No pork or bacon. Include: meal name, 5-8 ingredients, "
        "brief 3-step method, and estimated macros. 150 words max. "
        f"User context: {body.prompt}"
    )
    try:
        text = await _run_ai(AI_SYSTEM_MSG, prompt)
        return {"text": text}
    except Exception as e:
        logger.error(f"AI meal error: {e}")
        return {"text": "Try grilled chicken with cucumber-yogurt salad and mint.", "error": str(e)}


@api_router.post("/ai/workout-suggestion")
async def ai_workout(body: AIPrompt):
    prompt = (
        "Design a single 30-40 minute workout for a 40-year-old man wanting "
        "sustainable strength, mobility, and longevity (not bro-gym). "
        "Return a name, 5-6 exercises with sets/reps/rest, and a short note on "
        "form/breath. 180 words max. "
        f"User focus: {body.prompt}"
    )
    try:
        text = await _run_ai(AI_SYSTEM_MSG, prompt)
        return {"text": text}
    except Exception as e:
        logger.error(f"AI workout error: {e}")
        return {"text": "Try: squats, push-ups, rows, planks. 3 rounds of 10 reps.", "error": str(e)}


# ============ STREAKS ============
@api_router.get("/streaks")
async def streaks():
    today = datetime.now(timezone.utc).date()
    # workout streak (consecutive days)
    logs = await db.workout_logs.find({}, {"_id": 0, "date": 1}).to_list(1000)
    journal = await db.journal_entries.find({}, {"_id": 0, "date": 1}).to_list(1000)

    def streak(dates: set) -> int:
        d = today
        n = 0
        while d.isoformat() in dates:
            n += 1
            d = d - timedelta(days=1)
        return n

    workout_dates = {log["date"] for log in logs}
    journal_dates = {j["date"] for j in journal}

    return {
        "workout_streak": streak(workout_dates),
        "workout_total_days": len(workout_dates),
        "journal_streak": streak(journal_dates),
        "journal_total_days": len(journal_dates),
    }


class WeeklyLetterRequest(BaseModel):
    note: Optional[str] = ""


# ============ AI WEEKLY LETTER ============
@api_router.post("/ai/weekly-letter")
async def ai_weekly_letter(body: WeeklyLetterRequest = WeeklyLetterRequest()):
    today = datetime.now(timezone.utc).date()
    week_ago = (today - timedelta(days=7)).isoformat()

    logs = await db.workout_logs.find(
        {"date": {"$gte": week_ago}}, {"_id": 0}
    ).to_list(100)
    journal = await db.journal_entries.find(
        {"date": {"$gte": week_ago}}, {"_id": 0}
    ).to_list(100)
    events = await db.events.find(
        {"date": {"$gte": today.isoformat()}}, {"_id": 0}
    ).sort("date", 1).to_list(10)

    summary = []
    if logs:
        summary.append(f"workouts this week: {len(logs)} ({', '.join(w.get('workout_name', '') for w in logs[:5])})")
    else:
        summary.append("no workouts logged this week")
    if journal:
        moods = [e.get("mood", 3) for e in journal]
        avg = sum(moods) / len(moods)
        summary.append(f"journal entries: {len(journal)}, average mood {avg:.1f}/5")
        latest_reflection = next((j.get("reflection") for j in journal if j.get("reflection")), "")
        if latest_reflection:
            summary.append(f"latest reflection: '{latest_reflection[:200]}'")
    else:
        summary.append("no journal entries this week")
    if events:
        summary.append(f"upcoming: {events[0].get('title')} on {events[0].get('date')}")

    prompt = (
        "Write a short, tender 'letter to future me' (140–180 words) from the user's present self "
        "based on the past 7 days. Address the reader warmly. Acknowledge what they did and felt. "
        "Offer one gentle observation and one small intention for the coming week. "
        "No bullet lists. Sign off simply. "
        f"Data from the past week: {' | '.join(summary)}"
        + (f" | extra note from user: {body.note[:300]}" if body.note else "")
    )
    try:
        text = await _run_ai(AI_SYSTEM_MSG, prompt)
        return {"text": text, "data": {"workouts": len(logs), "journal_entries": len(journal)}}
    except Exception as e:
        logger.error(f"AI weekly letter error: {e}")
        return {"text": "Dear you — be gentle with yourself this week.", "error": str(e)}


# ============ DAY PLANS ============
@api_router.get("/day-plans/{date}")
async def get_day_plan(date: str):
    item = await db.day_plans.find_one({"date": date}, {"_id": 0})
    if not item:
        return DayPlan(date=date).model_dump()
    return item


@api_router.put("/day-plans/{date}")
async def upsert_day_plan(date: str, payload: DayPlan):
    doc = payload.model_dump()
    doc["date"] = date
    doc["updated_at"] = now_iso()
    await db.day_plans.update_one({"date": date}, {"$set": doc}, upsert=True)
    return doc


@api_router.get("/day-plans")
async def list_day_plans():
    items = await db.day_plans.find({}, {"_id": 0}).sort("date", -1).to_list(60)
    return items


# ============ COMPANION ============
async def _get_or_create_companion() -> dict:
    item = await db.companion.find_one({"id": "default"}, {"_id": 0})
    if not item:
        c = Companion()
        await db.companion.insert_one(c.model_dump())
        return c.model_dump()
    return item


@api_router.get("/companion")
async def get_companion():
    return await _get_or_create_companion()


@api_router.put("/companion")
async def update_companion(payload: CompanionUpdate):
    await _get_or_create_companion()
    update = {k: v for k, v in payload.model_dump().items() if v is not None}
    if update:
        await db.companion.update_one({"id": "default"}, {"$set": update})
    item = await db.companion.find_one({"id": "default"}, {"_id": 0})
    return item


@api_router.get("/companion/memories")
async def list_memories():
    items = await db.companion_memories.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return items


@api_router.post("/companion/memories")
async def add_memory(payload: CompanionMemoryCreate):
    m = CompanionMemory(**payload.model_dump())
    await db.companion_memories.insert_one(m.model_dump())
    return m


@api_router.delete("/companion/memories/{memory_id}")
async def delete_memory(memory_id: str):
    await db.companion_memories.delete_one({"id": memory_id})
    return {"ok": True}


@api_router.get("/companion/messages")
async def list_messages():
    items = await db.companion_messages.find({}, {"_id": 0}).sort("created_at", 1).to_list(2000)
    return items


@api_router.delete("/companion/messages")
async def clear_messages():
    await db.companion_messages.delete_many({})
    return {"ok": True}


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


@api_router.post("/companion/chat")
async def companion_chat(req: ChatRequest):
    companion = await _get_or_create_companion()
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
            f"- ({m.get('category', 'general')}) {m.get('content', '')}" for m in memories[:30]
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
        "Refer back to the user's memories naturally when relevant — you genuinely remember them. "
        "Never use emojis."
        f"{memory_block}{history_block}"
    )

    # Save user message immediately
    user_msg = CompanionMessage(role="user", content=req.message, persona=persona)
    await db.companion_messages.insert_one(user_msg.model_dump())

    try:
        reply_text = await _run_ai(system_msg, req.message)
    except Exception as e:
        logger.error(f"Companion chat error: {e}")
        reply_text = "I'm here. Let's try that again in a moment."

    assistant_msg = CompanionMessage(role="assistant", content=reply_text, persona=persona)
    await db.companion_messages.insert_one(assistant_msg.model_dump())

    return {
        "user_message": user_msg.model_dump(),
        "reply": assistant_msg.model_dump(),
    }


# ============ REGISTER ============
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ END ============

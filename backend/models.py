"""All Pydantic models for Life Blueprint API."""
from datetime import datetime, timezone
from typing import List, Optional, Literal
from pydantic import BaseModel, Field
import uuid


def new_id() -> str:
    return str(uuid.uuid4())


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ============ WORKOUTS ============
class Workout(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str
    category: str = "Strength"
    notes: Optional[str] = ""
    exercises: List[dict] = []
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


# ============ RECIPES ============
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
    thumb: Optional[str] = ""
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
    thumb: Optional[str] = ""


# ============ JOURNAL ============
class JournalEntry(BaseModel):
    id: str = Field(default_factory=new_id)
    date: str
    mood: int = 3
    gratitude: List[str] = []
    reflection: str = ""
    created_at: str = Field(default_factory=now_iso)


class JournalEntryCreate(BaseModel):
    date: str
    mood: int = 3
    gratitude: List[str] = []
    reflection: str = ""


# ============ EVENTS ============
class Event(BaseModel):
    id: str = Field(default_factory=new_id)
    title: str
    date: str
    type: str = "event"
    recurring: bool = False
    notes: str = ""
    created_at: str = Field(default_factory=now_iso)


class EventCreate(BaseModel):
    title: str
    date: str
    type: str = "event"
    recurring: bool = False
    notes: str = ""


# ============ LIFE GOALS ============
class LifeGoal(BaseModel):
    id: str = Field(default_factory=new_id)
    year: int
    age: int
    category: str = "Life"
    title: str
    description: str = ""
    status: str = "planned"
    created_at: str = Field(default_factory=now_iso)


class LifeGoalCreate(BaseModel):
    year: int
    age: int
    category: str = "Life"
    title: str
    description: str = ""
    status: str = "planned"


# ============ AI ============
class AIPrompt(BaseModel):
    prompt: str
    context: Optional[str] = ""


class WeeklyLetterRequest(BaseModel):
    note: Optional[str] = ""


# ============ DAY PLAN (typed sub-models) ============
class MealSlot(BaseModel):
    text: str = ""
    recipe_id: str = ""


class Supplement(BaseModel):
    name: str = ""
    taken: bool = False


class ChoreItem(BaseModel):
    text: str = ""
    done: bool = False


class TimeBlock(BaseModel):
    hour: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    text: str = ""


class DayPlanMeals(BaseModel):
    breakfast: MealSlot = Field(default_factory=MealSlot)
    lunch: MealSlot = Field(default_factory=MealSlot)
    dinner: MealSlot = Field(default_factory=MealSlot)
    snack: MealSlot = Field(default_factory=MealSlot)


class DayPlan(BaseModel):
    date: str
    priorities: List[str] = ["", "", ""]
    gym_planned: bool = False
    gym_workout_id: Optional[str] = ""
    gym_workout_name: Optional[str] = ""
    morning_routine: List[ChoreItem] = []
    meals: DayPlanMeals = Field(default_factory=DayPlanMeals)
    supplements: List[Supplement] = []
    house_chores: List[ChoreItem] = []
    work_chores: List[ChoreItem] = []
    time_blocks: List[TimeBlock] = Field(default_factory=list, max_length=24)
    sleep_target: str = "23:00"
    wake_target: str = "06:30"
    hydration_oz: int = 80
    notes: str = ""
    updated_at: str = Field(default_factory=now_iso)


# ============ COMPANION ============
PERSONA_VALUES = ("friend", "secretary", "manager", "coach")
PersonaLiteral = Literal["friend", "secretary", "manager", "coach"]


class Companion(BaseModel):
    id: str = "default"
    name: str = "Najm"
    user_name: str = "friend"
    persona: PersonaLiteral = "friend"
    created_at: str = Field(default_factory=now_iso)


class CompanionUpdate(BaseModel):
    name: Optional[str] = None
    user_name: Optional[str] = None
    persona: Optional[PersonaLiteral] = None


class CompanionMemory(BaseModel):
    id: str = Field(default_factory=new_id)
    content: str
    category: str = "general"
    pinned: bool = False
    created_at: str = Field(default_factory=now_iso)


class CompanionMemoryCreate(BaseModel):
    content: str
    category: str = "general"
    pinned: bool = False


class CompanionMemoryUpdate(BaseModel):
    pinned: Optional[bool] = None
    content: Optional[str] = None
    category: Optional[str] = None


class CompanionMessage(BaseModel):
    id: str = Field(default_factory=new_id)
    role: str
    content: str
    persona: str = "friend"
    actions: List[dict] = Field(default_factory=list)  # proposed actions, each with status
    created_at: str = Field(default_factory=now_iso)


class ChatRequest(BaseModel):
    message: str

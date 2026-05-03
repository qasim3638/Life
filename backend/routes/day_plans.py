"""Day plans (Plan Tomorrow)."""
from fastapi import APIRouter
from db import db
from models import DayPlan, now_iso

router = APIRouter()


@router.get("/day-plans/{date}")
async def get_day_plan(date: str):
    item = await db.day_plans.find_one({"date": date}, {"_id": 0})
    if not item:
        return DayPlan(date=date).model_dump()
    return item


@router.put("/day-plans/{date}")
async def upsert_day_plan(date: str, payload: DayPlan):
    doc = payload.model_dump()
    doc["date"] = date
    doc["updated_at"] = now_iso()
    await db.day_plans.update_one({"date": date}, {"$set": doc}, upsert=True)
    return doc


@router.get("/day-plans")
async def list_day_plans():
    return await db.day_plans.find({}, {"_id": 0}).sort("date", -1).to_list(60)

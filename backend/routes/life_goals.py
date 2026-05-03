"""Life goals (40-year blueprint)."""
from fastapi import APIRouter, HTTPException
from typing import List
from db import db
from models import LifeGoal, LifeGoalCreate

router = APIRouter()


@router.post("/life-goals", response_model=LifeGoal)
async def create_life_goal(payload: LifeGoalCreate):
    g = LifeGoal(**payload.model_dump())
    await db.life_goals.insert_one(g.model_dump())
    return g


@router.get("/life-goals", response_model=List[LifeGoal])
async def list_life_goals():
    return await db.life_goals.find({}, {"_id": 0}).sort("year", 1).to_list(500)


@router.put("/life-goals/{goal_id}", response_model=LifeGoal)
async def update_life_goal(goal_id: str, payload: LifeGoalCreate):
    res = await db.life_goals.update_one({"id": goal_id}, {"$set": payload.model_dump()})
    if res.matched_count == 0:
        raise HTTPException(404, "Goal not found")
    return await db.life_goals.find_one({"id": goal_id}, {"_id": 0})


@router.delete("/life-goals/{goal_id}")
async def delete_life_goal(goal_id: str):
    await db.life_goals.delete_one({"id": goal_id})
    return {"ok": True}

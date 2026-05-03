"""Workouts + workout logs."""
from fastapi import APIRouter, HTTPException
from typing import List
from db import db
from models import Workout, WorkoutCreate, WorkoutLog, WorkoutLogCreate

router = APIRouter()


@router.post("/workouts", response_model=Workout)
async def create_workout(payload: WorkoutCreate):
    w = Workout(**payload.model_dump())
    await db.workouts.insert_one(w.model_dump())
    return w


@router.get("/workouts", response_model=List[Workout])
async def list_workouts():
    items = await db.workouts.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return items


@router.get("/workouts/{workout_id}", response_model=Workout)
async def get_workout(workout_id: str):
    item = await db.workouts.find_one({"id": workout_id}, {"_id": 0})
    if not item:
        raise HTTPException(404, "Workout not found")
    return item


@router.put("/workouts/{workout_id}", response_model=Workout)
async def update_workout(workout_id: str, payload: WorkoutCreate):
    res = await db.workouts.update_one({"id": workout_id}, {"$set": payload.model_dump()})
    if res.matched_count == 0:
        raise HTTPException(404, "Workout not found")
    return await db.workouts.find_one({"id": workout_id}, {"_id": 0})


@router.delete("/workouts/{workout_id}")
async def delete_workout(workout_id: str):
    await db.workouts.delete_one({"id": workout_id})
    return {"ok": True}


@router.post("/workout-logs", response_model=WorkoutLog)
async def create_workout_log(payload: WorkoutLogCreate):
    log = WorkoutLog(**payload.model_dump())
    await db.workout_logs.insert_one(log.model_dump())
    return log


@router.get("/workout-logs", response_model=List[WorkoutLog])
async def list_workout_logs():
    return await db.workout_logs.find({}, {"_id": 0}).sort("date", -1).to_list(500)

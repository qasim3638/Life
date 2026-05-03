"""Events / reminders."""
from fastapi import APIRouter, HTTPException
from typing import List
from db import db
from models import Event, EventCreate

router = APIRouter()


@router.post("/events", response_model=Event)
async def create_event(payload: EventCreate):
    e = Event(**payload.model_dump())
    await db.events.insert_one(e.model_dump())
    return e


@router.get("/events", response_model=List[Event])
async def list_events():
    return await db.events.find({}, {"_id": 0}).sort("date", 1).to_list(500)


@router.put("/events/{event_id}", response_model=Event)
async def update_event(event_id: str, payload: EventCreate):
    res = await db.events.update_one({"id": event_id}, {"$set": payload.model_dump()})
    if res.matched_count == 0:
        raise HTTPException(404, "Event not found")
    return await db.events.find_one({"id": event_id}, {"_id": 0})


@router.delete("/events/{event_id}")
async def delete_event(event_id: str):
    await db.events.delete_one({"id": event_id})
    return {"ok": True}

"""Journal entries."""
from fastapi import APIRouter
from typing import List
from db import db
from models import JournalEntry, JournalEntryCreate

router = APIRouter()


@router.post("/journal-entries", response_model=JournalEntry)
async def create_journal(payload: JournalEntryCreate):
    j = JournalEntry(**payload.model_dump())
    await db.journal_entries.insert_one(j.model_dump())
    return j


@router.get("/journal-entries", response_model=List[JournalEntry])
async def list_journal():
    return await db.journal_entries.find({}, {"_id": 0}).sort("date", -1).to_list(500)


@router.delete("/journal-entries/{entry_id}")
async def delete_journal(entry_id: str):
    await db.journal_entries.delete_one({"id": entry_id})
    return {"ok": True}

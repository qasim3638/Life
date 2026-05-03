"""Curated content: quotes, podcasts, meditations, affirmations (read-only)."""
from fastapi import APIRouter
from db import db

router = APIRouter()


@router.get("/quotes")
async def list_quotes():
    return await db.quotes.find({}, {"_id": 0}).to_list(500)


@router.get("/podcasts")
async def list_podcasts():
    return await db.podcasts.find({}, {"_id": 0}).to_list(500)


@router.get("/meditations")
async def list_meditations():
    return await db.meditations.find({}, {"_id": 0}).to_list(500)


@router.get("/affirmations")
async def list_affirmations():
    return await db.affirmations.find({}, {"_id": 0}).to_list(500)

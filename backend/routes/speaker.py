"""Speaker voiceprint storage — single-user.

Stores the Picovoice Eagle profile bytes the user enrolls so that
"Hi Yaar" only triggers when it's actually them speaking.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from db import db

router = APIRouter(prefix="/speaker", tags=["speaker"])

PROFILE_DOC_ID = "primary"  # single-user app


class ProfileIn(BaseModel):
    profile_base64: str = Field(..., min_length=16, max_length=4_000_000)
    threshold: float = Field(default=0.6, ge=0.3, le=0.95)


class ProfileOut(BaseModel):
    profile_base64: str
    threshold: float
    created_at: str
    updated_at: str


class ProfileStatus(BaseModel):
    enrolled: bool
    threshold: float = 0.6
    updated_at: str | None = None


@router.put("/profile", response_model=dict)
async def save_profile(body: ProfileIn) -> dict:
    try:
        base64.b64decode(body.profile_base64)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid base64: {e}")
    now = datetime.now(timezone.utc)
    existing = await db.speaker_profile.find_one({"_id": PROFILE_DOC_ID})
    doc = {
        "profile_base64": body.profile_base64,
        "threshold": body.threshold,
        "updated_at": now,
    }
    if existing:
        await db.speaker_profile.update_one({"_id": PROFILE_DOC_ID}, {"$set": doc})
        return {"status": "updated"}
    doc["created_at"] = now
    await db.speaker_profile.insert_one({"_id": PROFILE_DOC_ID, **doc})
    return {"status": "created"}


@router.get("/profile", response_model=ProfileOut)
async def get_profile() -> ProfileOut:
    doc = await db.speaker_profile.find_one({"_id": PROFILE_DOC_ID}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="No voiceprint enrolled")
    return ProfileOut(
        profile_base64=doc["profile_base64"],
        threshold=doc.get("threshold", 0.6),
        created_at=(doc.get("created_at") or doc["updated_at"]).isoformat(),
        updated_at=doc["updated_at"].isoformat(),
    )


@router.get("/status", response_model=ProfileStatus)
async def status() -> ProfileStatus:
    doc = await db.speaker_profile.find_one({"_id": PROFILE_DOC_ID}, {"_id": 0})
    if not doc:
        return ProfileStatus(enrolled=False)
    return ProfileStatus(
        enrolled=True,
        threshold=doc.get("threshold", 0.6),
        updated_at=doc["updated_at"].isoformat(),
    )


@router.delete("/profile")
async def delete_profile() -> dict:
    res = await db.speaker_profile.delete_one({"_id": PROFILE_DOC_ID})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="No voiceprint enrolled")
    return {"status": "deleted"}

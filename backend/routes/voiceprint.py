"""Voiceprint biometric verification using Resemblyzer.

Single-user app. Provides:
- POST /voiceprint/enroll  - record N audio samples, store averaged 256-d embedding
- POST /voiceprint/verify  - compute embedding for new sample, return cosine similarity
- GET  /voiceprint/status  - is enrolled? what is the threshold?
- DELETE /voiceprint/delete - clear the enrolled voiceprint

Audio expected as WAV (16kHz mono recommended). Resemblyzer handles resampling.
"""
from __future__ import annotations

import io
import logging
import tempfile
import os
from datetime import datetime, timezone
from typing import Optional

import numpy as np
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

from db import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voiceprint", tags=["voiceprint"])

DOC_ID = "primary"  # single-user
DEFAULT_THRESHOLD = 0.75  # cosine similarity threshold (tight for security)

# Lazy-load encoder so module import doesn't fail if torch is missing in some env
_encoder = None
def _get_encoder():
    global _encoder
    if _encoder is None:
        from resemblyzer import VoiceEncoder
        _encoder = VoiceEncoder()
    return _encoder


def _audio_to_embedding(file_bytes: bytes) -> np.ndarray:
    """Convert raw audio bytes (WAV preferred) to a 256-d speaker embedding."""
    from resemblyzer import preprocess_wav
    # preprocess_wav accepts a filepath. Write to a temp file.
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    try:
        wav = preprocess_wav(tmp_path)
        enc = _get_encoder()
        emb = enc.embed_utterance(wav)
        return emb  # shape (256,), float32
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


class EnrollResponse(BaseModel):
    enrolled: bool
    samples_used: int
    threshold: float
    enrollment_quality: float  # avg pairwise similarity of enrollment samples (>0.8 = consistent)
    created_at: str


class VerifyResponse(BaseModel):
    match: bool
    score: float
    threshold: float


class StatusResponse(BaseModel):
    enrolled: bool
    threshold: float = DEFAULT_THRESHOLD
    updated_at: Optional[str] = None
    enrollment_quality: Optional[float] = None


@router.post("/enroll", response_model=EnrollResponse)
async def enroll(
    sample1: UploadFile = File(...),
    sample2: UploadFile = File(...),
    sample3: UploadFile = File(...),
) -> EnrollResponse:
    """Enroll voiceprint from 3 audio takes.

    Computes embedding per sample, then stores the MEAN embedding. Also returns
    an "enrollment_quality" score (avg pairwise cosine between the 3 takes) so
    the frontend can warn if the user wasn't consistent.
    """
    samples = [sample1, sample2, sample3]
    embeddings = []
    for i, s in enumerate(samples):
        raw = await s.read()
        if len(raw) < 4000:
            raise HTTPException(400, f"Sample {i+1} too short (< 4KB).")
        try:
            emb = _audio_to_embedding(raw)
        except Exception as e:
            logger.exception("Voiceprint enroll: embedding failed for sample %d", i+1)
            raise HTTPException(400, f"Couldn't process sample {i+1}: {str(e)[:120]}")
        embeddings.append(emb)

    # Quality: avg pairwise similarity between the 3 takes (security signal)
    quality = float(np.mean([
        _cosine(embeddings[0], embeddings[1]),
        _cosine(embeddings[0], embeddings[2]),
        _cosine(embeddings[1], embeddings[2]),
    ]))

    if quality < 0.65:
        raise HTTPException(
            400,
            f"Samples sound too different (quality={quality:.2f}). "
            "Try again — speak the same way each time.",
        )

    mean_emb = np.mean(np.stack(embeddings, axis=0), axis=0)
    # Re-normalize
    norm = np.linalg.norm(mean_emb)
    if norm > 0:
        mean_emb = mean_emb / norm

    now = datetime.now(timezone.utc)
    doc = {
        "embedding": mean_emb.astype(float).tolist(),  # 256 floats
        "threshold": DEFAULT_THRESHOLD,
        "enrollment_quality": quality,
        "samples_used": len(samples),
        "updated_at": now,
    }
    existing = await db.voiceprints.find_one({"_id": DOC_ID})
    if existing:
        await db.voiceprints.update_one({"_id": DOC_ID}, {"$set": doc})
        created_at = existing.get("created_at", now)
    else:
        doc["created_at"] = now
        doc["_id"] = DOC_ID
        await db.voiceprints.insert_one(doc)
        created_at = now

    return EnrollResponse(
        enrolled=True,
        samples_used=len(samples),
        threshold=DEFAULT_THRESHOLD,
        enrollment_quality=quality,
        created_at=created_at.isoformat() if isinstance(created_at, datetime) else str(created_at),
    )


@router.post("/verify", response_model=VerifyResponse)
async def verify(audio: UploadFile = File(...)) -> VerifyResponse:
    """Verify a new audio sample against the enrolled voiceprint."""
    existing = await db.voiceprints.find_one({"_id": DOC_ID}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "No voiceprint enrolled.")
    stored = np.array(existing["embedding"], dtype=np.float32)
    threshold = float(existing.get("threshold", DEFAULT_THRESHOLD))

    raw = await audio.read()
    if len(raw) < 4000:
        raise HTTPException(400, "Audio too short.")
    try:
        emb = _audio_to_embedding(raw)
    except Exception as e:
        logger.exception("Voiceprint verify: embedding failed")
        raise HTTPException(400, f"Couldn't process audio: {str(e)[:120]}")

    score = _cosine(emb, stored)
    return VerifyResponse(
        match=bool(score >= threshold),
        score=score,
        threshold=threshold,
    )


@router.get("/status", response_model=StatusResponse)
async def status() -> StatusResponse:
    doc = await db.voiceprints.find_one({"_id": DOC_ID}, {"_id": 0})
    if not doc:
        return StatusResponse(enrolled=False)
    upd = doc.get("updated_at")
    return StatusResponse(
        enrolled=True,
        threshold=float(doc.get("threshold", DEFAULT_THRESHOLD)),
        updated_at=(upd.isoformat() if isinstance(upd, datetime) else str(upd) if upd else None),
        enrollment_quality=float(doc.get("enrollment_quality")) if doc.get("enrollment_quality") is not None else None,
    )


@router.delete("/delete")
async def delete_voiceprint() -> dict:
    res = await db.voiceprints.delete_one({"_id": DOC_ID})
    return {"deleted": res.deleted_count > 0}

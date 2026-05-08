"""
Marketing Videos — Sora 2 text-to-video generation.

Routes:

    POST   /api/admin/marketing-studio/videos/cost-estimate
    POST   /api/admin/marketing-studio/videos/generate
    GET    /api/admin/marketing-studio/videos/jobs
    GET    /api/admin/marketing-studio/videos/jobs/{job_id}
    POST   /api/admin/marketing-studio/videos/jobs/{job_id}/cancel
    GET    /api/admin/marketing-studio/videos/assets
    DELETE /api/admin/marketing-studio/videos/{video_id}
    GET    /api/admin/marketing-studio/videos/stats

    GET    /api/website/marketing-video/{path:path}   (public byte-range-capable)
"""
from __future__ import annotations

import logging
import os
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from services import get_current_user
from services import video_generation as vg
from services.object_storage import get_object

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/marketing-studio/videos", tags=["Marketing Studio Videos"])
public_router = APIRouter(prefix="/website", tags=["Marketing Videos (public)"])


def _require_admin(user: dict):
    role = (user or {}).get("role") or ""
    if role not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")


# ---- Request models ----------------------------------------------

class CostEstimateReq(BaseModel):
    model: str = Field("sora-2")
    duration: int = Field(4)


class GenerateReq(BaseModel):
    prompt: str
    model: str = Field("sora-2")
    size: str = Field("1024x1792")       # default vertical
    duration: int = Field(4)
    source_asset_id: Optional[str] = None  # future: image-to-video


# ---- Catalogue -----------------------------------------------------

@router.get("/catalogue")
async def catalogue(current_user: dict = Depends(get_current_user)):
    """Return the models/sizes/durations + per-second pricing the UI
    should render. One endpoint so the admin UI always stays in sync
    with the backend's supported values + env-overridable pricing."""
    _require_admin(current_user)
    return {
        "models": sorted(vg.SUPPORTED_MODELS),
        "sizes": vg.SIZE_PRESETS,
        "durations": sorted(vg.SUPPORTED_DURATIONS),
        "pricing": {
            m: {"per_second_usd": vg._cost_per_second(m)}
            for m in sorted(vg.SUPPORTED_MODELS)
        },
    }


@router.post("/cost-estimate")
async def cost_estimate(req: CostEstimateReq, current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    if req.model not in vg.SUPPORTED_MODELS:
        raise HTTPException(status_code=400, detail=f"Unknown model '{req.model}'")
    if int(req.duration) not in vg.SUPPORTED_DURATIONS:
        raise HTTPException(status_code=400, detail=f"Duration must be one of {sorted(vg.SUPPORTED_DURATIONS)}")
    return {
        "model": req.model,
        "duration": req.duration,
        "estimated_cost_usd": vg.estimate_cost(req.model, req.duration),
        "per_second_usd": vg._cost_per_second(req.model),
    }


# ---- Generate / jobs -----------------------------------------------

@router.post("/generate")
async def generate(req: GenerateReq, current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    try:
        job = await vg.enqueue_job(
            prompt=req.prompt,
            model=req.model,
            size=req.size,
            duration=req.duration,
            admin_email=(current_user or {}).get("email"),
            source_asset_id=req.source_asset_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "job": job}


@router.get("/jobs")
async def list_jobs(
    status: Optional[str] = Query(None, description="Filter by status (queued,running,succeeded,failed,cancelled)"),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    statuses = [s.strip() for s in status.split(",")] if status else None
    return {"jobs": await vg.list_jobs(limit=limit, include_statuses=statuses)}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    job = await vg.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job": job}


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str, current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    try:
        job = await vg.cancel_job(job_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"ok": True, "job": job}


# ---- Assets / stats ------------------------------------------------

@router.get("/assets")
async def list_assets(
    limit: int = Query(40, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    return {"videos": await vg.list_assets(limit=limit)}


@router.delete("/{video_id}")
async def delete_video(video_id: str, current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    try:
        return await vg.delete_asset(video_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/stats")
async def stats(current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    return await vg.stats()


# ---- Public video proxy --------------------------------------------

@public_router.get("/marketing-video/{path:path}")
async def serve_marketing_video(path: str, download: int = Query(0)):
    """Serve an MP4 from R2. Supports `?download=1` to force a file
    download via `Content-Disposition: attachment`."""
    # Guard path traversal
    if ".." in path or path.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid path")
    r2_path = f"tile-station/marketing-videos/{path}"
    try:
        data, content_type = get_object(r2_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Video not found")
    except Exception as exc:
        logger.exception("R2 get_object failed")
        raise HTTPException(status_code=502, detail=f"Storage error: {str(exc)[:120]}")

    headers = {
        "Cache-Control": "public, max-age=31536000, immutable",
        "Accept-Ranges": "bytes",
    }
    if download:
        filename = f"tilestation-video-{path}"
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return Response(
        content=data,
        media_type=content_type or "video/mp4",
        headers=headers,
    )

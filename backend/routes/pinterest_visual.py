"""
Pinterest Visual Engine — admin routes
─────────────────────────────────────

  • Boards config:
      GET  /api/admin/pinterest/visual/boards
      PATCH /api/admin/pinterest/visual/boards/{slug}
      POST /api/admin/pinterest/visual/boards/seed

  • Queue ops:
      GET  /api/admin/pinterest/visual/queue?status=pending&limit=50
      GET  /api/admin/pinterest/visual/queue/summary
      POST /api/admin/pinterest/visual/queue/generate (manual trigger)
      POST /api/admin/pinterest/visual/queue/{id}/approve
      POST /api/admin/pinterest/visual/queue/{id}/skip
      POST /api/admin/pinterest/visual/queue/{id}/block
      PATCH /api/admin/pinterest/visual/queue/{id}

  • Blocklist:
      GET    /api/admin/pinterest/visual/blocklist
      DELETE /api/admin/pinterest/visual/blocklist/{image_url_b64}

All routes require admin/super_admin. The router is namespaced under
`/admin/pinterest/visual/` so it doesn't collide with the existing
single-board pinterest router at `/admin/pinterest/`.
"""
from __future__ import annotations

import base64
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from services import get_current_user
from services import pinterest_engine as engine
from services import pinterest_queue as queue

router = APIRouter(prefix="/admin/pinterest/visual", tags=["Pinterest Visual Engine"])


def _require_admin(user: dict):
    if (user or {}).get("role") not in ("admin", "super_admin", "manager"):
        raise HTTPException(status_code=403, detail="Admin access required")


# ───── Boards ─────

@router.get("/boards")
async def get_boards(current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    await engine.init_default_boards()
    return {"boards": await engine.list_boards_config()}


class BoardUpdateReq(BaseModel):
    auto_approve: Optional[bool] = None
    pinterest_board_id: Optional[str] = None
    is_active: Optional[bool] = None
    name: Optional[str] = None
    description: Optional[str] = None


@router.patch("/boards/{slug}")
async def patch_board(
    slug: str, payload: BoardUpdateReq,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    res = await engine.update_board_config(slug, updates)
    if not res:
        raise HTTPException(status_code=404, detail="Board not found")
    return res


@router.post("/boards/seed")
async def seed_boards(current_user: dict = Depends(get_current_user)):
    """Manual force-seed in case the admin wants to re-add boards
    they accidentally deleted."""
    _require_admin(current_user)
    inserted = await engine.init_default_boards()
    return {"inserted": inserted, "boards": await engine.list_boards_config()}


# ───── Queue ─────

@router.get("/queue/summary")
async def queue_summary(current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    return await queue.queue_summary()


@router.get("/queue")
async def list_queue(
    status: Optional[str] = None,
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    rows = await queue.list_candidates(status=status, limit=min(max(limit, 1), 200))
    return {"rows": rows, "count": len(rows)}


class GenerateReq(BaseModel):
    target_count: int = Field(12, ge=1, le=50)


@router.post("/queue/generate")
async def trigger_generate(
    payload: GenerateReq = GenerateReq(),
    current_user: dict = Depends(get_current_user),
):
    """Manual generation trigger — runs the same logic the daily
    cron uses but on demand. Useful for the admin's first run."""
    _require_admin(current_user)
    return await queue.generate_candidates(target_count=payload.target_count)


@router.post("/queue/{candidate_id}/approve")
async def approve(candidate_id: str, current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    res = await queue.approve_candidate(candidate_id)
    if not res:
        raise HTTPException(status_code=404, detail="Candidate not found or not pending")
    return res


@router.post("/queue/{candidate_id}/skip")
async def skip(candidate_id: str, current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    res = await queue.skip_candidate(candidate_id)
    if not res:
        raise HTTPException(status_code=404, detail="Candidate not found or not pending")
    return res


@router.post("/queue/{candidate_id}/block")
async def block(candidate_id: str, current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    res = await queue.block_candidate(candidate_id)
    if not res:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return res


class CandidatePatchReq(BaseModel):
    title: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    board_slug: Optional[str] = None
    link_url: Optional[str] = None
    image_url: Optional[str] = None
    alt_text: Optional[str] = Field(None, max_length=200)


@router.patch("/queue/{candidate_id}")
async def patch_candidate(
    candidate_id: str, payload: CandidatePatchReq,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    fields = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="No editable fields supplied")
    res = await queue.update_candidate(candidate_id, fields)
    if not res:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return res


# ───── Blocklist ─────

@router.get("/blocklist")
async def get_blocklist(current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    rows = await queue.list_blocklist()
    return {"rows": rows, "count": len(rows)}


@router.delete("/blocklist/{image_url_b64}")
async def delete_blocklist_entry(
    image_url_b64: str, current_user: dict = Depends(get_current_user),
):
    """Image URL passed base64url-encoded so slashes/colons don't break
    the route. `btoa` on the frontend handles the encoding."""
    _require_admin(current_user)
    try:
        url = base64.urlsafe_b64decode(image_url_b64.encode() + b"=" * (-len(image_url_b64) % 4)).decode()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 image URL")
    ok = await queue.unblock_image(url)
    if not ok:
        raise HTTPException(status_code=404, detail="Not in blocklist")
    return {"ok": True, "image_url": url}


# ───── Performance feedback loop (Phase 2) ─────

@router.get("/performance")
async def get_performance(current_user: dict = Depends(get_current_user)):
    """Return aggregate Pinterest performance — top Pins by clicks,
    board-level scores from the last 30 days. Empty until Pinterest
    integration connects + first sync runs."""
    _require_admin(current_user)
    from services import pinterest_engine_phase2 as p2
    from config import get_db
    db = get_db()
    cutoff_ago = 30
    cur = db.pinterest_pin_candidates.find(
        {
            "status": "posted",
            "performance": {"$exists": True},
        },
        {
            "_id": 0, "id": 1, "product_name": 1, "board_name": 1,
            "title": 1, "image_url": 1, "pinterest_pin_url": 1,
            "performance": 1, "posted_at": 1,
        },
    ).sort([("performance.clicks", -1)]).limit(20)
    top = await cur.to_list(20)
    for r in top:
        if hasattr(r.get("posted_at"), "isoformat"):
            r["posted_at"] = r["posted_at"].isoformat()
    return {
        "top_pins": top,
        "board_scores": await p2.board_performance_score(),
        "window_days": cutoff_ago,
    }


@router.post("/performance/sync")
async def trigger_performance_sync(current_user: dict = Depends(get_current_user)):
    """Manual trigger for the performance sync (otherwise runs daily
    at 04:00 BST). Pulls Pin click/save/impression metrics from
    Pinterest."""
    _require_admin(current_user)
    from services import pinterest_engine_phase2 as p2
    return await p2.sync_pin_performance()


@router.post("/repin/run")
async def trigger_repin_scheduler(current_user: dict = Depends(get_current_user)):
    """Manual trigger of the weekly repin scheduler. Posts the top N
    performing Pins from 30+ days ago to a fresh board."""
    _require_admin(current_user)
    from services import pinterest_engine_phase2 as p2
    return await p2.schedule_repins()


@router.get("/lifestyle-renders")
async def get_lifestyle_renders(
    status: str | None = None,
    limit: int = 30,
    current_user: dict = Depends(get_current_user),
):
    """Status of Nano Banana lifestyle renders — useful for debugging
    why a particular product hasn't yet got a Tier-2 image."""
    _require_admin(current_user)
    from config import get_db
    db = get_db()
    q: dict = {}
    if status:
        q["status"] = status
    cur = db.pinterest_lifestyle_renders.find(q, {"_id": 0}).sort("created_at", -1).limit(min(max(limit, 1), 200))
    rows = await cur.to_list(limit)
    for r in rows:
        for k in ("created_at", "rendering_started_at", "rendered_at", "failed_at"):
            v = r.get(k)
            if hasattr(v, "isoformat"):
                r[k] = v.isoformat()
    return {"rows": rows, "count": len(rows)}


@router.post("/lifestyle-renders/run-batch")
async def trigger_lifestyle_render_batch(
    batch_size: int = 3,
    current_user: dict = Depends(get_current_user),
):
    """Manual trigger of a Nano Banana batch (otherwise runs every
    2h via the scheduler). Cap default at 3 so it doesn't bill £30."""
    _require_admin(current_user)
    from services import pinterest_engine_phase2 as p2
    return await p2.render_lifestyle_tick(batch_size=min(max(batch_size, 1), 10))

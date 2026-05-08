"""
Admin SEO Command Centre — admin-only endpoints surfacing Ahrefs data
inside the new /admin/seo dashboard.

Endpoints (all admin-gated):
  GET  /api/admin/seo/health        — confirm API key works + show quota
  GET  /api/admin/seo/snapshot      — last cached pull (instant render)
  POST /api/admin/seo/refresh       — force-refresh snapshot
  GET  /api/admin/seo/keyword-gap?competitor=X — live competitor gap report
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from config import get_db
from services import get_current_user
from services import ahrefs as ah

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/seo", tags=["SEO Command"])


def _is_admin(user: dict) -> bool:
    return (user or {}).get("role") in {"super_admin", "admin", "manager"}


@router.get("/health")
async def health(current_user: dict = Depends(get_current_user)):
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    return await ah.health_check()


@router.get("/snapshot")
async def get_snapshot(current_user: dict = Depends(get_current_user)):
    """Return the last cached Ahrefs snapshot. Cheap — never hits Ahrefs."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    db = get_db()
    your = await db.ahrefs_snapshots.find_one({"_id": "your_domain"}, {"_id": 0})
    competitors = await db.ahrefs_snapshots.find_one({"_id": "competitors"}, {"_id": 0})
    return {
        "your_domain": your,
        "competitors": competitors,
        "last_snapshotted": (
            your.get("snapshotted_at").isoformat() if your and your.get("snapshotted_at")
            else None
        ),
    }


@router.post("/refresh")
async def refresh(current_user: dict = Depends(get_current_user)):
    """Manually trigger a snapshot pull. Costs ~50-100 units of Ahrefs
    quota — safe given our 1M/month allowance."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    return await ah.snapshot_seo_data(get_db())


@router.get("/keyword-gap")
async def keyword_gap(
    competitor: str = Query(..., min_length=4, max_length=100),
    your_domain: str = Query(default=ah.YOUR_DOMAIN),
    country: str = Query(default="gb"),
    limit: int = Query(default=100, ge=10, le=500),
    current_user: dict = Depends(get_current_user),
):
    """Live keyword-gap report. Returns keywords the competitor ranks for
    that you don't, sorted by traffic potential descending."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    return await ah.keyword_gap(your_domain, competitor, country=country, limit=limit)


@router.get("/organic-keywords")
async def organic_keywords(
    target: str = Query(default=ah.YOUR_DOMAIN),
    country: str = Query(default="gb"),
    limit: int = Query(default=200, ge=10, le=1000),
    current_user: dict = Depends(get_current_user),
):
    """Organic keywords for any domain — used for the 'You currently rank
    for' table on the SEO Command Centre."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    return await ah.organic_keywords(target, country=country, limit=limit)

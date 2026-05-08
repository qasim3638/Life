"""Admin endpoints for the uptime sparkline widget."""
from fastapi import APIRouter, Depends, HTTPException, Query

from services import get_current_user
from services.uptime import (
    get_30_day_uptime, get_day_incidents, get_recent_incidents, run_uptime_probe_tick,
)

router = APIRouter(prefix="/admin/uptime", tags=["Uptime"])


def _is_admin(user: dict) -> bool:
    return (user or {}).get("role") in {"super_admin", "admin", "manager"}


@router.get("/rollup")
async def rollup(
    days: int = Query(30, ge=1, le=90),
    current_user: dict = Depends(get_current_user),
):
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    return await get_30_day_uptime(days=days)


@router.get("/incidents")
async def incidents(
    limit: int = Query(20, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
):
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    return {"incidents": await get_recent_incidents(limit=limit)}


@router.post("/probe-now")
async def probe_now(current_user: dict = Depends(get_current_user)):
    """Manual trigger for the smoke-test panel (and end-to-end tests)."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    return await run_uptime_probe_tick()


@router.get("/day")
async def day_incidents(
    date: str = Query(..., description="UTC date YYYY-MM-DD"),
    service: str | None = Query(None, description="Optional filter — single service name"),
    limit: int = Query(200, ge=1, le=2000),
    current_user: dict = Depends(get_current_user),
):
    """Drilldown payload behind a clicked sparkline cell.
    Returns the failed probe rows for that day plus a total-probes count
    so the UI can show 'X failed of Y probes'.
    """
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    return await get_day_incidents(date=date, service=service, limit=limit)

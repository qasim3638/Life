"""Admin endpoint for the conversion funnel card."""
from fastapi import APIRouter, Depends, HTTPException, Query

from services import get_current_user
from services.conversion_funnel import get_funnel

router = APIRouter(prefix="/admin/conversion", tags=["Conversion"])


def _is_admin(user: dict) -> bool:
    return (user or {}).get("role") in {"super_admin", "admin", "manager"}


@router.get("/funnel")
async def funnel(
    days: int = Query(28, ge=1, le=365),
    current_user: dict = Depends(get_current_user),
):
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    return await get_funnel(days=days)

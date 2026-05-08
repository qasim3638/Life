"""
Pinterest auto-pin admin routes.

Flow:
  1. Admin clicks "Connect Pinterest" → frontend GET /authorize-url
  2. Backend returns the Pinterest OAuth URL
  3. Frontend opens it in a new tab; admin clicks Allow
  4. Pinterest redirects to /api/admin/pinterest/callback?code=…
  5. Backend exchanges the code for tokens, stores in DB, redirects
     the browser to /admin/seo?pinterest=connected
  6. Admin picks a board from the dropdown → POST /board
  7. Editorial Autopilot now auto-pins on every new article publish.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from services import get_current_user
from services import pinterest as pin

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/admin/pinterest", tags=["Pinterest Auto-Pin"])
public_router = APIRouter(prefix="/admin/pinterest", tags=["Pinterest OAuth callback"])


def _require_admin(user: dict):
    if (user or {}).get("role") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")


@router.get("/status")
async def status(current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    return await pin.status()


@router.get("/authorize-url")
async def authorize_url(current_user: dict = Depends(get_current_user)):
    """Return the Pinterest OAuth URL the frontend opens in a new tab."""
    _require_admin(current_user)
    try:
        return {"url": pin.authorize_url(state=(current_user or {}).get("email") or "tilestation")}
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/boards")
async def boards(current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    return {"boards": await pin.list_boards()}


class SetBoardReq(BaseModel):
    board_id: str
    board_name: Optional[str] = None


@router.post("/board")
async def set_board(payload: SetBoardReq, current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    if not payload.board_id:
        raise HTTPException(status_code=400, detail="board_id is required")
    return await pin.set_board(payload.board_id, payload.board_name)


@router.post("/disconnect")
async def disconnect(current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    await pin.disconnect()
    return {"ok": True}


# ──────── Public OAuth callback (no auth — Pinterest redirects here) ────────

@public_router.get("/callback")
async def callback(
    code: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
):
    """Pinterest redirects the BROWSER here after the user clicks
    Allow. Pinterest's authorize endpoint can't carry a Bearer token
    so this route is unauthenticated — but we never trust input. We
    only do the token swap then bounce back to /admin/seo.

    The `state` we sent earlier is the admin email; we can pass it
    through as `connected_by` for the audit log.
    """
    import os
    base = (os.environ.get("FRONTEND_BASE_URL") or "https://tilestation.co.uk").rstrip("/")
    if error:
        return RedirectResponse(f"{base}/admin/seo?pinterest=denied&error={error}")
    if not code:
        return RedirectResponse(f"{base}/admin/seo?pinterest=missing_code")
    try:
        await pin.exchange_code_for_tokens(code, connected_by_email=state)
    except Exception as exc:
        logger.exception("Pinterest OAuth callback failed")
        from urllib.parse import quote
        return RedirectResponse(f"{base}/admin/seo?pinterest=failed&detail={quote(str(exc)[:200])}")
    return RedirectResponse(f"{base}/admin/seo?pinterest=connected")


# ──────── Manual pin trigger (handy for the admin UI "Test pin" button) ────────

class TestPinReq(BaseModel):
    title: str
    description: str
    image_url: str
    link: str


@router.post("/test-pin")
async def test_pin(payload: TestPinReq, current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    return await pin.create_pin(
        title=payload.title,
        description=payload.description,
        image_url=payload.image_url,
        link=payload.link,
    )

"""
Google Business Profile — admin OAuth + read endpoints.

Mirrors `routes/gsc_auth.py` so the same Express proxy + same admin
panel UX patterns apply.

Routes (mounted under /api):
  GET  /admin/gbp/status          → connection status
  GET  /admin/gbp/connect         → returns Google consent URL
  GET  /admin/gbp/callback        → public OAuth redirect target
  POST /admin/gbp/disconnect      → wipe stored tokens
  GET  /admin/gbp/locations       → list business locations
  GET  /admin/gbp/reviews         → reviews for a location_id
  GET  /admin/gbp/insights        → 30-day performance for a location
"""
from __future__ import annotations

import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from config import get_db
from services import get_current_user
from services import gbp as gbp_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/gbp", tags=["GBP OAuth"])

DEFAULT_RETURN_PATH = "/admin/gbp"
STATE_TTL_MINUTES = 15
STATE_COLLECTION = "gbp_oauth_states"


def _is_admin(user: dict) -> bool:
    return (user or {}).get("role") in {"super_admin", "admin", "manager"}


def _frontend_origin() -> str:
    explicit = (
        os.environ.get("GBP_FRONTEND_ORIGIN")
        or os.environ.get("GSC_FRONTEND_ORIGIN")
        or os.environ.get("FRONTEND_URL")
        or ""
    ).rstrip("/")
    if explicit:
        return explicit
    redirect_uri = (
        os.environ.get("GBP_OAUTH_REDIRECT_URI")
        or os.environ.get("GOOGLE_OAUTH_REDIRECT_URI")
        or ""
    ).strip()
    if redirect_uri:
        parsed = urlparse(redirect_uri)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
    return (
        os.environ.get("SHOP_WEBSITE_URL")
        or os.environ.get("PUBLIC_SITE_URL")
        or ""
    ).rstrip("/")


def _admin_id(user: dict) -> str:
    return str(user.get("id") or user.get("_id") or user.get("email"))


@router.get("/status")
async def status(current_user: dict = Depends(get_current_user)):
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    return await gbp_service.get_status(_admin_id(current_user))


@router.get("/connect")
async def connect(
    return_to: str = Query(DEFAULT_RETURN_PATH),
    current_user: dict = Depends(get_current_user),
):
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    if not gbp_service.is_configured():
        raise HTTPException(
            status_code=503,
            detail=(
                "Google Business Profile OAuth is not configured. Set "
                "GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET and "
                "GBP_OAUTH_REDIRECT_URI in backend env."
            ),
        )
    state = secrets.token_urlsafe(32)
    auth_url, _verifier = gbp_service.build_authorization_url(state=state)

    db = get_db()
    await db[STATE_COLLECTION].insert_one({
        "_id": state,
        "admin_user_id": _admin_id(current_user),
        "return_to": return_to or DEFAULT_RETURN_PATH,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=STATE_TTL_MINUTES),
    })
    return {"authorization_url": auth_url}


@router.get("/callback", include_in_schema=False)
async def callback(
    request: Request,
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
):
    front = _frontend_origin()

    def _redirect(path: str, **params) -> RedirectResponse:
        qs = "&".join(f"{k}={quote(str(v), safe='')}" for k, v in params.items() if v is not None)
        target = f"{front}{path}" if front else path
        if qs:
            target = f"{target}?{qs}"
        return RedirectResponse(url=target, status_code=303)

    if error:
        return _redirect(DEFAULT_RETURN_PATH, gbp="error", reason=error)
    if not code or not state:
        return _redirect(DEFAULT_RETURN_PATH, gbp="error", reason="missing_code")

    db = get_db()
    state_row = await db[STATE_COLLECTION].find_one({"_id": state})
    if not state_row:
        return _redirect(DEFAULT_RETURN_PATH, gbp="error", reason="invalid_state")
    await db[STATE_COLLECTION].delete_one({"_id": state})

    expires_at = state_row.get("expires_at")
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at and expires_at < datetime.now(timezone.utc):
        return _redirect(DEFAULT_RETURN_PATH, gbp="error", reason="state_expired")

    admin_id = state_row.get("admin_user_id")
    return_to = state_row.get("return_to") or DEFAULT_RETURN_PATH

    try:
        result = await gbp_service.exchange_code_and_store(
            admin_user_id=admin_id, code=code, state=state
        )
    except HTTPException as exc:
        logger.warning("GBP token exchange failed: %s", exc.detail)
        return _redirect(DEFAULT_RETURN_PATH, gbp="error", reason="exchange_failed")
    except Exception:
        logger.exception("GBP token exchange unexpected failure")
        return _redirect(DEFAULT_RETURN_PATH, gbp="error", reason="server_error")

    return _redirect(
        return_to,
        gbp="connected",
        email=result.get("google_account_email") or "",
    )


@router.post("/disconnect")
async def disconnect(current_user: dict = Depends(get_current_user)):
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    return await gbp_service.disconnect(_admin_id(current_user))


@router.get("/locations")
async def list_locations(current_user: dict = Depends(get_current_user)):
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    return await gbp_service.list_locations(_admin_id(current_user))


@router.get("/reviews")
async def get_reviews(
    location_id: str = Query(..., description="GBP location id"),
    page_size: int = Query(50, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
):
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    return await gbp_service.get_reviews(
        _admin_id(current_user), location_id=location_id, page_size=page_size,
    )


@router.get("/insights")
async def get_insights(
    location_id: str = Query(..., description="GBP location id"),
    days: int = Query(30, ge=1, le=540),
    current_user: dict = Depends(get_current_user),
):
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    return await gbp_service.get_insights(
        _admin_id(current_user), location_id=location_id, days=days,
    )

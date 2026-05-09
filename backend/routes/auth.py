"""Auth router — /api/auth/login, /api/auth/me, /api/auth/setup, /api/auth/disable, /api/auth/status."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, EmailStr, Field

from auth_utils import (
    verify_password,
    hash_password,
    create_token,
    require_auth,
    check_lockout,
    record_failure,
    clear_failures,
    is_auth_configured,
    invalidate_auth_cache,
)
from db import db

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    token: str
    email: str


class SetupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=4, max_length=128)
    current_password: str | None = None  # required if a user already exists


class DisableRequest(BaseModel):
    current_password: str


class StatusResponse(BaseModel):
    configured: bool
    email: str | None = None


@router.get("/status", response_model=StatusResponse)
async def status() -> StatusResponse:
    """Tells the frontend whether the lock screen should appear."""
    configured = await is_auth_configured()
    if not configured:
        return StatusResponse(configured=False)
    user = await db.auth_users.find_one({}, {"_id": 0, "email": 1})
    return StatusResponse(configured=True, email=user.get("email") if user else None)


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request) -> LoginResponse:
    if not await is_auth_configured():
        raise HTTPException(status_code=400, detail="Login not set up yet")
    email = body.email.lower().strip()
    ip = request.client.host if request.client else "unknown"
    key = f"{ip}:{email}"

    await check_lockout(key)

    user = await db.auth_users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        await record_failure(key)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    await clear_failures(key)
    token = await create_token(email)
    return LoginResponse(token=token, email=email)


@router.get("/me")
async def me(email: str = Depends(require_auth)) -> dict:
    return {"email": email, "authenticated": True}


@router.post("/setup", response_model=LoginResponse)
async def setup(body: SetupRequest) -> LoginResponse:
    """Create or change the owner password.

    First time (no user yet): just send {email, password} → creates user, logs in.
    After that: must include {current_password} of the existing user.
    """
    new_email = body.email.lower().strip()
    existing = await db.auth_users.find_one({})
    if existing:
        # require current_password to change anything
        if not body.current_password or not verify_password(
            body.current_password, existing["password_hash"]
        ):
            raise HTTPException(status_code=401, detail="Current password is wrong")
        await db.auth_users.update_one(
            {"email": existing["email"]},
            {
                "$set": {
                    "email": new_email,
                    "password_hash": hash_password(body.password),
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
    else:
        await db.auth_users.insert_one(
            {
                "email": new_email,
                "password_hash": hash_password(body.password),
                "created_at": datetime.now(timezone.utc),
            }
        )
    invalidate_auth_cache()
    token = await create_token(new_email)
    return LoginResponse(token=token, email=new_email)


@router.post("/disable")
async def disable(body: DisableRequest) -> dict:
    """Wipe the auth user and effectively turn the lock screen off."""
    existing = await db.auth_users.find_one({})
    if not existing:
        return {"ok": True, "already_disabled": True}
    if not verify_password(body.current_password, existing["password_hash"]):
        raise HTTPException(status_code=401, detail="Current password is wrong")
    await db.auth_users.delete_many({})
    await db.login_attempts.delete_many({})
    invalidate_auth_cache()
    return {"ok": True, "disabled": True}


@router.get("/_diag")
async def diag() -> dict:
    """Quick diagnostic: which critical env vars are set on this deployment.
    Returns booleans only (never values). No auth required so we can curl it."""
    import os as _os
    keys = [
        "MONGO_URL",
        "DB_NAME",
        "EMERGENT_LLM_KEY",
        "ELEVENLABS_API_KEY",
        "JWT_SECRET",
        "AUTH_EMAIL",
        "AUTH_PASSWORD",
        "CORS_ORIGINS",
    ]
    env_set = {k: bool(_os.environ.get(k)) for k in keys}
    # MongoDB ping
    try:
        await db.command("ping")
        mongo_ok = True
    except Exception:
        mongo_ok = False
    # auth users count (doesn't expose any data)
    try:
        users = await db.auth_users.count_documents({})
    except Exception:
        users = -1
    return {
        "env_set": env_set,
        "mongo_ok": mongo_ok,
        "auth_users_count": users,
    }


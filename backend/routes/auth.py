"""Auth router — /api/auth/login, /api/auth/me."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, EmailStr

from auth_utils import (
    verify_password,
    create_token,
    require_auth,
    check_lockout,
    record_failure,
    clear_failures,
)
from db import db

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    token: str
    email: str


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request) -> LoginResponse:
    email = body.email.lower().strip()
    ip = request.client.host if request.client else "unknown"
    key = f"{ip}:{email}"

    await check_lockout(key)

    user = await db.auth_users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        await record_failure(key)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    await clear_failures(key)
    return LoginResponse(token=create_token(email), email=email)


@router.get("/me")
async def me(email: str = Depends(require_auth)) -> dict:
    return {"email": email, "authenticated": True}

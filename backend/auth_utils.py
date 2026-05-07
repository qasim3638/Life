"""JWT + bcrypt auth utilities for Life Blueprint.

Single-user app:
- Owner's email + password come from Railway env vars (AUTH_EMAIL, AUTH_PASSWORD)
- Seeded into MongoDB on startup
- Login returns a 30-day JWT
- Bearer token in Authorization header protects every /api/* route except
  /api/, /api/auth/*, /api/uploads/* (static uploads served directly)
"""
from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from typing import Optional

import bcrypt
import jwt
from fastapi import HTTPException, Request

from db import db

JWT_ALG = "HS256"
TOKEN_TTL_DAYS = 30
LOCKOUT_ATTEMPTS = 5
LOCKOUT_MIN = 15


def _secret() -> str:
    val = os.environ.get("JWT_SECRET")
    if not val:
        raise RuntimeError("JWT_SECRET env var missing")
    return val


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def create_token(email: str) -> str:
    payload = {
        "sub": email,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_TTL_DAYS),
        "type": "access",
    }
    return jwt.encode(payload, _secret(), algorithm=JWT_ALG)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, _secret(), algorithms=[JWT_ALG])
    except jwt.PyJWTError:
        return None


def _bearer(request: Request) -> Optional[str]:
    h = request.headers.get("Authorization", "")
    if h.startswith("Bearer "):
        return h[7:]
    return None


async def require_auth(request: Request) -> str:
    """FastAPI dependency — raises 401 if token invalid, returns email.

    If AUTH_EMAIL/AUTH_PASSWORD env vars aren't set (dev/preview), auth is
    treated as disabled and we return "anonymous" without any check. This
    matches the middleware in server.py.
    """
    if not (os.environ.get("AUTH_EMAIL") and os.environ.get("AUTH_PASSWORD")):
        return "anonymous"
    token = _bearer(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    email = payload.get("sub")
    user = await db.auth_users.find_one({"email": email}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return email


# ---- Brute-force tracking ----
async def check_lockout(key: str) -> None:
    rec = await db.login_attempts.find_one({"_id": key}) or {}
    count = rec.get("count", 0)
    locked_until = rec.get("locked_until")
    if locked_until and datetime.now(timezone.utc) < locked_until:
        mins = int((locked_until - datetime.now(timezone.utc)).total_seconds() / 60) + 1
        raise HTTPException(status_code=429, detail=f"Too many attempts. Try again in {mins} min.")
    if count >= LOCKOUT_ATTEMPTS:
        until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MIN)
        await db.login_attempts.update_one(
            {"_id": key},
            {"$set": {"locked_until": until}},
            upsert=True,
        )
        raise HTTPException(status_code=429, detail=f"Too many attempts. Try again in {LOCKOUT_MIN} min.")


async def record_failure(key: str) -> None:
    await db.login_attempts.update_one(
        {"_id": key},
        {"$inc": {"count": 1}, "$set": {"last_failure": datetime.now(timezone.utc)}},
        upsert=True,
    )


async def clear_failures(key: str) -> None:
    await db.login_attempts.delete_one({"_id": key})


# ---- Admin seeding ----
async def seed_auth_user() -> None:
    email = os.environ.get("AUTH_EMAIL")
    password = os.environ.get("AUTH_PASSWORD")
    if not email or not password:
        # Auth simply disabled until env vars are set
        return
    email = email.lower().strip()
    existing = await db.auth_users.find_one({"email": email})
    if existing is None:
        await db.auth_users.insert_one({
            "email": email,
            "password_hash": hash_password(password),
            "created_at": datetime.now(timezone.utc),
        })
    elif not verify_password(password, existing["password_hash"]):
        await db.auth_users.update_one(
            {"email": email},
            {"$set": {"password_hash": hash_password(password)}},
        )

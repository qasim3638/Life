"""JWT + bcrypt auth utilities for Life Blueprint.

Single-user app:
- Owner sets their own email + password from in-app Settings → Account
- Auth is "active" iff at least one user exists in db.auth_users
- Login returns a 30-day JWT
- Bearer token in Authorization header protects every /api/* route except
  /api/, /api/auth/*, /api/uploads/* (static uploads served directly)

Backwards-compat:
- `AUTH_EMAIL` + `AUTH_PASSWORD` env vars on Railway still seed an admin user
  on startup (`seed_auth_user`), but in-app Settings is now the recommended
  flow.
"""
from __future__ import annotations

import os
import secrets
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

_AUTH_CONFIGURED_CACHE: Optional[bool] = None


def invalidate_auth_cache() -> None:
    global _AUTH_CONFIGURED_CACHE
    _AUTH_CONFIGURED_CACHE = None


async def is_auth_configured() -> bool:
    """True if any user is registered. Cached to avoid hitting DB on every request."""
    global _AUTH_CONFIGURED_CACHE
    if _AUTH_CONFIGURED_CACHE is not None:
        return _AUTH_CONFIGURED_CACHE
    count = await db.auth_users.count_documents({})
    _AUTH_CONFIGURED_CACHE = count > 0
    return _AUTH_CONFIGURED_CACHE


async def get_jwt_secret() -> str:
    env = os.environ.get("JWT_SECRET")
    if env:
        return env
    # Persist a generated secret so JWTs survive restarts
    doc = await db.auth_config.find_one({"_id": "primary"}, {"_id": 0})
    if doc and doc.get("jwt_secret"):
        return doc["jwt_secret"]
    new_secret = secrets.token_urlsafe(48)
    await db.auth_config.update_one(
        {"_id": "primary"},
        {"$set": {"jwt_secret": new_secret}},
        upsert=True,
    )
    return new_secret


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


async def create_token(email: str) -> str:
    payload = {
        "sub": email,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_TTL_DAYS),
        "type": "access",
    }
    secret = await get_jwt_secret()
    return jwt.encode(payload, secret, algorithm=JWT_ALG)


async def decode_token(token: str) -> Optional[dict]:
    try:
        secret = await get_jwt_secret()
        return jwt.decode(token, secret, algorithms=[JWT_ALG])
    except jwt.PyJWTError:
        return None


def _bearer(request: Request) -> Optional[str]:
    h = request.headers.get("Authorization", "")
    if h.startswith("Bearer "):
        return h[7:]
    return None


async def require_auth(request: Request) -> str:
    """FastAPI dependency — 401 if token invalid, returns email.

    If no user is configured (db.auth_users empty), auth is disabled and
    we return 'anonymous' without checking. Mirrors the global middleware.
    """
    if not await is_auth_configured():
        return "anonymous"
    token = _bearer(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = await decode_token(token)
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


# ---- Admin seeding (env-var fallback for Railway) ----
async def seed_auth_user() -> None:
    email = os.environ.get("AUTH_EMAIL")
    password = os.environ.get("AUTH_PASSWORD")
    if not email or not password:
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
    invalidate_auth_cache()

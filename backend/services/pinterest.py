"""
Pinterest auto-publish — creates a Pin on the TileStation board every
time the Editorial Autopilot publishes a new article.

Connection state lives in `pinterest_settings` (a singleton document
keyed by id="main"):
  {
    id: "main",
    access_token, refresh_token,
    token_expires_at: datetime,
    user_id,
    board_id, board_name,
    connected_at, connected_by_email,
  }

Why a DB row instead of env vars? The user clicks "Connect Pinterest"
in the admin UI, completes Pinterest's OAuth, and Pinterest redirects
back with a code we exchange for tokens. We persist the result so it
survives restarts and they never copy-paste anything. Only the App ID
and App Secret (the dev-app credentials) come from env — those are
permanent.

Failure mode is ALWAYS graceful — if Pinterest is unreachable, the
token expired, or the integration was never connected, we log a
warning and return a "skipped" result. The Editorial Autopilot never
fails an article publish over a Pinterest hiccup.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import httpx

from config import get_db

logger = logging.getLogger(__name__)


# ──────── Pinterest endpoint constants ────────

API_BASE = "https://api.pinterest.com/v5"
OAUTH_AUTHORIZE_URL = "https://www.pinterest.com/oauth/"
OAUTH_TOKEN_URL = f"{API_BASE}/oauth/token"

# Scopes we need: read user accounts + boards, create pins
SCOPES = "user_accounts:read,boards:read,pins:read,pins:write"


def _app_creds() -> tuple[Optional[str], Optional[str]]:
    return (
        os.environ.get("PINTEREST_APP_ID"),
        os.environ.get("PINTEREST_APP_SECRET"),
    )


def _redirect_uri() -> str:
    """Where Pinterest sends the user after they click Allow.

    In production this should be `https://tilestation.co.uk/api/admin/pinterest/callback`.
    On preview we use the preview backend URL so the OAuth dance works
    end-to-end without redeploying. Override via `PINTEREST_REDIRECT_URI`.
    """
    explicit = (os.environ.get("PINTEREST_REDIRECT_URI") or "").strip()
    if explicit:
        return explicit
    base = (os.environ.get("FRONTEND_BASE_URL") or "https://tilestation.co.uk").rstrip("/")
    return f"{base}/api/admin/pinterest/callback"


# ──────── Persistence ────────

async def get_settings() -> dict:
    db = get_db()
    doc = await db.pinterest_settings.find_one({"id": "main"}, {"_id": 0}) or {}
    return doc


async def save_tokens(
    *, access_token: str, refresh_token: Optional[str],
    expires_in_seconds: int, user_id: Optional[str] = None,
    connected_by_email: Optional[str] = None,
) -> dict:
    """Upsert the singleton settings doc with fresh tokens. Preserves
    the saved board_id so a token refresh doesn't lose the user's
    board pick."""
    db = get_db()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=int(expires_in_seconds or 30 * 86400))
    set_doc = {
        "id": "main",
        "access_token": access_token,
        "token_expires_at": expires_at,
        "updated_at": now,
    }
    if refresh_token:
        set_doc["refresh_token"] = refresh_token
    if user_id:
        set_doc["user_id"] = user_id
    if connected_by_email:
        set_doc["connected_by_email"] = connected_by_email
        set_doc["connected_at"] = now
    await db.pinterest_settings.update_one(
        {"id": "main"}, {"$set": set_doc}, upsert=True,
    )
    return await get_settings()


async def disconnect() -> None:
    """Remove all Pinterest creds from the DB. App ID / Secret in env
    stay — admin can reconnect with one click."""
    db = get_db()
    await db.pinterest_settings.delete_one({"id": "main"})


async def set_board(board_id: str, board_name: Optional[str] = None) -> dict:
    db = get_db()
    await db.pinterest_settings.update_one(
        {"id": "main"},
        {"$set": {"board_id": board_id, "board_name": board_name or board_id}},
    )
    return await get_settings()


# ──────── OAuth flow ────────

def authorize_url(state: str = "tilestation") -> str:
    """Build the Pinterest authorize URL the admin's browser opens."""
    app_id, _ = _app_creds()
    if not app_id:
        raise RuntimeError("PINTEREST_APP_ID is not set on the backend")
    params = {
        "client_id": app_id,
        "redirect_uri": _redirect_uri(),
        "response_type": "code",
        "scope": SCOPES,
        "state": state,
    }
    return f"{OAUTH_AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code_for_tokens(code: str, *, connected_by_email: Optional[str] = None) -> dict:
    """Exchange the auth code Pinterest sent us for an access token +
    refresh token. Pinterest expects HTTP Basic auth with App ID/Secret
    + form-encoded body."""
    app_id, app_secret = _app_creds()
    if not app_id or not app_secret:
        raise RuntimeError("Pinterest app credentials are not configured")
    async with httpx.AsyncClient(timeout=20.0) as cli:
        r = await cli.post(
            OAUTH_TOKEN_URL,
            auth=(app_id, app_secret),
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": _redirect_uri(),
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if r.status_code != 200:
        raise RuntimeError(f"Pinterest token exchange failed: HTTP {r.status_code} — {r.text[:300]}")
    data = r.json()
    access = data.get("access_token")
    if not access:
        raise RuntimeError(f"Pinterest token response missing access_token: {data}")
    saved = await save_tokens(
        access_token=access,
        refresh_token=data.get("refresh_token"),
        expires_in_seconds=int(data.get("expires_in") or 30 * 86400),
        connected_by_email=connected_by_email,
    )
    # Best-effort: stash user_id for reference
    try:
        async with httpx.AsyncClient(timeout=15.0) as cli:
            r2 = await cli.get(
                f"{API_BASE}/user_account",
                headers={"Authorization": f"Bearer {access}"},
            )
        if r2.status_code == 200:
            uid = r2.json().get("username")
            if uid:
                db = get_db()
                await db.pinterest_settings.update_one(
                    {"id": "main"}, {"$set": {"user_id": uid}}
                )
                saved["user_id"] = uid
    except Exception:
        pass
    return saved


async def _refresh_if_needed(force: bool = False) -> Optional[str]:
    """Returns a valid access token or None if connection is broken.
    Refreshes proactively when the current token has <5 days left."""
    settings = await get_settings()
    access = settings.get("access_token")
    refresh = settings.get("refresh_token")
    if not access:
        return None
    expires_at = settings.get("token_expires_at")
    if isinstance(expires_at, str):
        try:
            expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        except Exception:
            expires_at = None
    if isinstance(expires_at, datetime) and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    needs_refresh = force or (
        expires_at is not None
        and (expires_at - datetime.now(timezone.utc)) < timedelta(days=5)
    )
    if not needs_refresh or not refresh:
        return access
    # Refresh
    app_id, app_secret = _app_creds()
    if not app_id or not app_secret:
        return access  # fall back to whatever we have
    try:
        async with httpx.AsyncClient(timeout=20.0) as cli:
            r = await cli.post(
                OAUTH_TOKEN_URL,
                auth=(app_id, app_secret),
                data={"grant_type": "refresh_token", "refresh_token": refresh,
                      "scope": SCOPES},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        if r.status_code != 200:
            logger.warning(f"Pinterest token refresh failed: HTTP {r.status_code} — {r.text[:200]}")
            return access
        data = r.json()
        new_access = data.get("access_token") or access
        await save_tokens(
            access_token=new_access,
            refresh_token=data.get("refresh_token") or refresh,
            expires_in_seconds=int(data.get("expires_in") or 30 * 86400),
        )
        return new_access
    except Exception:
        logger.exception("Pinterest token refresh crashed")
        return access


# ──────── Boards ────────

async def list_boards() -> list[dict]:
    """Return the boards owned by the connected account so the admin
    can pick one in a dropdown."""
    token = await _refresh_if_needed()
    if not token:
        return []
    try:
        async with httpx.AsyncClient(timeout=20.0) as cli:
            r = await cli.get(
                f"{API_BASE}/boards",
                headers={"Authorization": f"Bearer {token}"},
                params={"page_size": 50},
            )
        if r.status_code != 200:
            logger.warning(f"Pinterest list_boards failed: HTTP {r.status_code} — {r.text[:200]}")
            return []
        items = r.json().get("items") or []
        return [{"id": b.get("id"), "name": b.get("name"), "description": b.get("description")} for b in items]
    except Exception:
        logger.exception("Pinterest list_boards crashed")
        return []


# ──────── Status & connectivity ────────

async def status() -> dict:
    """Compact status object for the admin UI."""
    app_id, app_secret = _app_creds()
    settings = await get_settings()
    expires_at = settings.get("token_expires_at")
    if isinstance(expires_at, datetime) and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return {
        "app_credentials_set": bool(app_id and app_secret),
        "connected": bool(settings.get("access_token")),
        "user_id": settings.get("user_id"),
        "board_id": settings.get("board_id"),
        "board_name": settings.get("board_name"),
        "connected_at": settings.get("connected_at").isoformat() if isinstance(settings.get("connected_at"), datetime) else settings.get("connected_at"),
        "connected_by_email": settings.get("connected_by_email"),
        "token_expires_at": expires_at.isoformat() if isinstance(expires_at, datetime) else None,
        "redirect_uri": _redirect_uri(),
    }


# ──────── Create a Pin ────────

async def create_pin(
    *, title: str, description: str, image_url: str, link: str,
    alt_text: Optional[str] = None,
) -> dict:
    """Publish a Pin. Returns a dict with `success`, `pin_id` (on
    success), `pin_url` (https://pinterest.com/pin/<id>), or `error`.

    Truncates description to 500 chars and title to 100 chars to stay
    inside Pinterest's limits — the API will reject longer values."""
    settings = await get_settings()
    board_id = settings.get("board_id")
    if not board_id:
        return {"success": False, "error": "no_board_set", "pin_id": None}

    token = await _refresh_if_needed()
    if not token:
        return {"success": False, "error": "not_connected", "pin_id": None}

    payload = {
        "board_id": board_id,
        "title": title[:100],
        "description": description[:500],
        "media_source": {"source_type": "image_url", "url": image_url},
        "link": link,
    }
    if alt_text:
        payload["alt_text"] = alt_text[:500]

    try:
        async with httpx.AsyncClient(timeout=30.0) as cli:
            r = await cli.post(
                f"{API_BASE}/pins",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        if r.status_code == 201:
            data = r.json()
            pin_id = data.get("id")
            return {
                "success": True,
                "pin_id": pin_id,
                "pin_url": f"https://pinterest.com/pin/{pin_id}" if pin_id else None,
            }
        # Specific error codes — see playbook for full list
        body = r.text[:300]
        if r.status_code == 401:
            # Token rejected — try ONE forced refresh then give up
            token = await _refresh_if_needed(force=True)
            if token:
                async with httpx.AsyncClient(timeout=30.0) as cli:
                    r2 = await cli.post(
                        f"{API_BASE}/pins",
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                if r2.status_code == 201:
                    data = r2.json()
                    pin_id = data.get("id")
                    return {
                        "success": True,
                        "pin_id": pin_id,
                        "pin_url": f"https://pinterest.com/pin/{pin_id}" if pin_id else None,
                    }
                body = r2.text[:300]
            return {"success": False, "error": f"auth_failed: {body}", "pin_id": None, "error_code": 401}
        if r.status_code == 429:
            return {"success": False, "error": f"rate_limited: {body}", "pin_id": None, "error_code": 429}
        if r.status_code == 400:
            return {"success": False, "error": f"bad_request: {body}", "pin_id": None, "error_code": 400}
        if r.status_code == 403:
            return {"success": False, "error": f"forbidden: {body}", "pin_id": None, "error_code": 403}
        return {"success": False, "error": f"http_{r.status_code}: {body}", "pin_id": None, "error_code": r.status_code}
    except httpx.TimeoutException:
        return {"success": False, "error": "timeout", "pin_id": None}
    except Exception as exc:
        logger.exception("Pinterest create_pin crashed")
        return {"success": False, "error": str(exc)[:200], "pin_id": None}

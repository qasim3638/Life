"""
Web Push Notifications service
──────────────────────────────

Thin wrapper around `pywebpush` so the rest of the codebase doesn't
care about the protocol. Stores subscriptions in the
`web_push_subscriptions` collection keyed on the (browser-supplied)
endpoint URL — the endpoint is unique per browser/device/site so it's
the natural primary key.

Settings live in a singleton doc at
`web_push_settings.{id: "main"}` for the admin UI to read/write
(opt-in copy, broadcast history, etc.).
"""
from __future__ import annotations

import json
import logging
import os
import secrets
from datetime import datetime, timezone
from typing import Any, Optional

from pywebpush import WebPushException, webpush

from config import get_db

logger = logging.getLogger(__name__)


_SUBS = "web_push_subscriptions"
_HISTORY = "web_push_broadcasts"


def _vapid_public_key() -> str:
    return os.environ.get("VAPID_PUBLIC_KEY", "")


def _vapid_private_key() -> str:
    return os.environ.get("VAPID_PRIVATE_KEY", "")


def _vapid_subject() -> str:
    return os.environ.get("VAPID_SUBJECT", "mailto:admin@tilestation.co.uk")


def is_configured() -> bool:
    return bool(_vapid_public_key() and _vapid_private_key())


# ───────── subscription CRUD ─────────

async def upsert_subscription(
    subscription: dict,
    user_agent: Optional[str] = None,
    visitor_id: Optional[str] = None,
) -> dict:
    """Idempotent — same endpoint = same row. Reactivates an
    inactive row if the same endpoint resubscribes."""
    db = get_db()
    endpoint = (subscription or {}).get("endpoint")
    keys = (subscription or {}).get("keys") or {}
    if not endpoint or not keys.get("p256dh") or not keys.get("auth"):
        raise ValueError("Invalid subscription object — missing endpoint or keys")

    now = datetime.now(timezone.utc)
    update = {
        "endpoint": endpoint,
        "p256dh": keys["p256dh"],
        "auth": keys["auth"],
        "user_agent": user_agent,
        "visitor_id": visitor_id,
        "is_active": True,
        "updated_at": now,
        "last_error": None,
    }
    res = await db[_SUBS].find_one_and_update(
        {"endpoint": endpoint},
        {"$set": update, "$setOnInsert": {"created_at": now}},
        upsert=True,
        return_document=True,
        projection={"_id": 0},
    )
    return res or update


async def remove_subscription(endpoint: str) -> bool:
    db = get_db()
    res = await db[_SUBS].update_one(
        {"endpoint": endpoint},
        {"$set": {"is_active": False, "deactivated_at": datetime.now(timezone.utc)}},
    )
    return res.matched_count > 0


async def stats() -> dict[str, Any]:
    db = get_db()
    total = await db[_SUBS].count_documents({})
    active = await db[_SUBS].count_documents({"is_active": True})
    last_broadcast = await db[_HISTORY].find_one(
        {}, {"_id": 0}, sort=[("sent_at", -1)],
    )
    return {
        "configured": is_configured(),
        "public_key": _vapid_public_key() if is_configured() else None,
        "active_subscribers": active,
        "total_subscribers_lifetime": total,
        "last_broadcast": last_broadcast,
    }


# ───────── send a push ─────────

async def _send_one(sub: dict, payload: str) -> dict:
    """Send to a single subscription; on 410/404 mark inactive.
    Returns {ok, status, error?}."""
    db = get_db()
    try:
        webpush(
            subscription_info={
                "endpoint": sub["endpoint"],
                "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]},
            },
            data=payload,
            vapid_private_key=_vapid_private_key(),
            vapid_claims={"sub": _vapid_subject()},
            ttl=43200,  # 12 hours — most browsers will cache + retry
        )
        await db[_SUBS].update_one(
            {"endpoint": sub["endpoint"]},
            {"$set": {"last_notified_at": datetime.now(timezone.utc), "last_error": None}},
        )
        return {"ok": True, "status": 201}
    except WebPushException as exc:
        status = exc.response.status_code if exc.response is not None else None
        if status in (404, 410):
            await db[_SUBS].update_one(
                {"endpoint": sub["endpoint"]},
                {"$set": {
                    "is_active": False,
                    "deactivated_at": datetime.now(timezone.utc),
                    "last_error": f"expired_{status}",
                }},
            )
        else:
            await db[_SUBS].update_one(
                {"endpoint": sub["endpoint"]},
                {"$set": {"last_error": str(exc)[:200]}},
            )
        return {"ok": False, "status": status, "error": str(exc)[:200]}
    except Exception as exc:  # noqa: BLE001
        logger.exception("web push delivery error")
        return {"ok": False, "status": None, "error": str(exc)[:200]}


async def send_broadcast(
    title: str,
    body: str,
    url: Optional[str] = None,
    icon: Optional[str] = None,
    image: Optional[str] = None,
    tag: Optional[str] = None,
    actor_email: Optional[str] = None,
) -> dict[str, Any]:
    """Send to every active subscriber. Returns aggregate stats and
    persists a history row so admin can see what was sent."""
    if not is_configured():
        return {
            "ok": False, "reason": "not_configured",
            "sent": 0, "failed": 0, "expired": 0,
        }

    db = get_db()
    payload = json.dumps({
        "title": (title or "")[:120],
        "body": (body or "")[:240],
        "url": url or "/",
        "icon": icon or "/icon-192.png",
        "image": image,
        "tag": tag or f"ts-{secrets.token_hex(4)}",
    })

    sent = 0
    failed = 0
    expired = 0
    cursor = db[_SUBS].find({"is_active": True}, {"_id": 0})
    async for sub in cursor:
        res = await _send_one(sub, payload)
        if res["ok"]:
            sent += 1
        elif res.get("status") in (404, 410):
            expired += 1
        else:
            failed += 1

    history = {
        "id": secrets.token_urlsafe(12),
        "title": title, "body": body, "url": url,
        "sent": sent, "failed": failed, "expired": expired,
        "actor_email": actor_email,
        "sent_at": datetime.now(timezone.utc),
    }
    await db[_HISTORY].insert_one({**history})

    return {
        "ok": True,
        "sent": sent, "failed": failed, "expired": expired,
        "total_targets": sent + failed + expired,
        "id": history["id"],
    }


async def list_history(limit: int = 20) -> list[dict]:
    db = get_db()
    cur = db[_HISTORY].find({}, {"_id": 0}).sort("sent_at", -1).limit(limit)
    rows = []
    async for r in cur:
        if isinstance(r.get("sent_at"), datetime):
            r["sent_at"] = r["sent_at"].isoformat()
        rows.append(r)
    return rows

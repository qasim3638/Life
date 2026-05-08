"""Web push notification routes.

  • Public:
      GET  /api/push/config           — VAPID public key (cacheable)
      POST /api/push/subscribe        — store browser subscription
      POST /api/push/unsubscribe      — flag subscription inactive

  • Admin:
      GET  /api/admin/push/stats      — subscribers + last broadcast
      POST /api/admin/push/broadcast  — push to every active sub
      GET  /api/admin/push/history    — last N broadcasts
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from services import get_current_user
from services import web_push

router = APIRouter(tags=["Web Push"])
admin_router = APIRouter(prefix="/admin/push", tags=["Web Push Admin"])
public_router = APIRouter(prefix="/push", tags=["Web Push Public"])


def _require_admin(user: dict):
    if (user or {}).get("role") not in ("admin", "super_admin", "manager"):
        raise HTTPException(status_code=403, detail="Admin access required")


# ───────── Public ─────────

@public_router.get("/config")
async def get_push_config():
    if not web_push.is_configured():
        raise HTTPException(status_code=503, detail="Web push not configured on server")
    return {
        "public_key": web_push._vapid_public_key(),
        "subject": web_push._vapid_subject(),
    }


class SubscribeReq(BaseModel):
    subscription: dict
    visitor_id: Optional[str] = None


@public_router.post("/subscribe")
async def subscribe(req: SubscribeReq, request: Request):
    user_agent = request.headers.get("User-Agent", "")[:300]
    try:
        await web_push.upsert_subscription(
            req.subscription, user_agent=user_agent, visitor_id=req.visitor_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True}


class UnsubscribeReq(BaseModel):
    endpoint: str


@public_router.post("/unsubscribe")
async def unsubscribe(req: UnsubscribeReq):
    await web_push.remove_subscription(req.endpoint)
    return {"ok": True}


# ───────── Admin ─────────

@admin_router.get("/stats")
async def admin_stats(current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    return await web_push.stats()


class BroadcastReq(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    body: str = Field(..., min_length=1, max_length=240)
    url: Optional[str] = "/"
    icon: Optional[str] = None
    image: Optional[str] = None
    tag: Optional[str] = None


@admin_router.post("/broadcast")
async def admin_broadcast(
    req: BroadcastReq,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    return await web_push.send_broadcast(
        title=req.title, body=req.body, url=req.url,
        icon=req.icon, image=req.image, tag=req.tag,
        actor_email=(current_user or {}).get("email"),
    )


@admin_router.get("/history")
async def admin_history(
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    rows = await web_push.list_history(limit=limit)
    return {"rows": rows, "count": len(rows)}


# include the two sub-routers under one combined export
router.include_router(admin_router)
router.include_router(public_router)

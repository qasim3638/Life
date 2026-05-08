"""
Editorial Autopilot — admin + public read endpoints.

Admin:
  GET    /api/admin/editorial-autopilot/status
  POST   /api/admin/editorial-autopilot/settings
  POST   /api/admin/editorial-autopilot/run-now
  GET    /api/admin/editorial-autopilot/articles
  DELETE /api/admin/editorial-autopilot/articles/{slug}

Public storefront:
  GET    /api/shop/blog
  GET    /api/shop/blog/{slug}
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from services import get_current_user
from services import editorial_autopilot as eap

logger = logging.getLogger(__name__)


admin_router = APIRouter(prefix="/admin/editorial-autopilot", tags=["Editorial Autopilot"])
public_router = APIRouter(prefix="/shop", tags=["Blog (public)"])


def _require_admin(user: dict):
    if (user or {}).get("role") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")


# ───── Admin ─────

@admin_router.get("/status")
async def status(current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    settings = await eap.get_settings()
    spent = await eap.monthly_spend_usd()

    # Next scheduled run — read from APScheduler so the admin knows
    # when the cron will actually fire (helps debug "why hasn't it run
    # yet" questions after a deploy)
    next_run_iso = None
    try:
        from services.scheduler import scheduler as _sched
        if _sched is not None:
            job = _sched.get_job("editorial_autopilot_weekly")
            if job and job.next_run_time:
                next_run_iso = job.next_run_time.isoformat()
    except Exception:
        pass

    return {
        **settings,
        "spent_this_month_usd": round(spent, 2),
        "cap_remaining_usd": round(max(0, settings["monthly_cap_usd"] - spent), 2),
        "would_run": (not settings["paused"]) and spent < settings["monthly_cap_usd"],
        "next_run_at": next_run_iso,
        "last_run_diagnostic": settings.get("last_run_diagnostic"),
    }


class SettingsReq(BaseModel):
    paused: Optional[bool] = None
    monthly_cap_usd: Optional[float] = Field(None, ge=1, le=1000)
    articles_per_run: Optional[int] = Field(None, ge=1, le=10)


@admin_router.post("/settings")
async def update_settings(
    payload: SettingsReq,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    return await eap.update_settings(
        paused=payload.paused,
        monthly_cap_usd=payload.monthly_cap_usd,
        articles_per_run=payload.articles_per_run,
        admin_email=(current_user or {}).get("email"),
    )


class RunNowReq(BaseModel):
    max_articles: Optional[int] = Field(None, ge=1, le=5)


@admin_router.post("/run-now")
async def run_now(
    payload: RunNowReq,
    current_user: dict = Depends(get_current_user),
):
    """Kick off a manual autopilot run. Returns IMMEDIATELY (the actual
    Claude calls take 1-3 min per article and would otherwise blow
    past the 60s ingress timeout). Frontend polls /status to know when
    it's done."""
    _require_admin(current_user)
    import asyncio
    asyncio.create_task(eap.run_weekly_autopilot(force=True, max_articles=payload.max_articles))
    return {"ok": True, "status": "started", "polling": True}


@admin_router.get("/articles")
async def list_articles(
    limit: int = Query(30, ge=1, le=100),
    source: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    return {"articles": await eap.list_articles(limit=limit, source=source)}


@admin_router.delete("/articles/{slug}")
async def delete_article(
    slug: str,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    return await eap.delete_article(slug)


# ───── Public storefront ─────

@public_router.get("/blog")
async def blog_index(limit: int = Query(50, ge=1, le=100)):
    """List published blog articles for the storefront /blog page.
    Body markdown is omitted from the listing for payload size."""
    rows = await eap.list_articles(limit=limit)
    out = [
        {
            "slug": r["slug"],
            "title": r.get("title"),
            "meta_description": r.get("meta_description"),
            "primary_keyword": r.get("primary_keyword"),
            "hero_image_url": r.get("hero_image_url"),
            "published_at": r.get("published_at"),
        }
        for r in rows
        if r.get("status") == "published" or "status" not in r
    ]
    return {"articles": out, "count": len(out)}


@public_router.get("/blog/{slug}")
async def blog_article(slug: str):
    article = await eap.get_article(slug)
    if not article or (article.get("status") and article["status"] != "published"):
        raise HTTPException(status_code=404, detail="Article not found")
    # Drop fields not useful to the public reader
    article.pop("topic_key", None)
    article.pop("source_url", None)
    article.pop("source_competitor", None)
    article.pop("score", None)
    article.pop("cost_usd", None)
    article.pop("hero_prompt", None)
    return article

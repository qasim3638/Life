"""
Daily auto-generation tick for AI City Landing Pages.

Goal
----
Drain the `city_landing_pages` queue automatically: every morning we pull
the next N rows that are still `pending` and run the same LLM generation
the admin "Batch generate" button uses. When the queue is fully drained
(no pending rows left), email the admins so they know it's review time.

Design
------
* Settings live in `website_settings` (`_id="city_pages_autogen"`) so the
  admin can toggle / change the daily count without a redeploy.
* Defaults: enabled=True, daily_count=5, hour_utc=4 (just after the
  04:30 SEO drafts scan and before the 06:15 Ahrefs snapshot — keeps the
  morning LLM bursts staggered).
* Idempotent: a `last_run_date` marker stops a hourly probe firing twice
  on the same UTC day even if we add a redeploy or the scheduler restarts.
* Queue-drained alert: only sent ONCE per drain — a flag in the same
  settings doc gets reset whenever new rows enter `pending`.

Output: returns a dict with the run summary so admin can show "last run"
in the UI later.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from config import get_db
from services.email import send_simple_email_if_possible
from services.seo_digest import _admin_emails  # reuse role-based recipient pull

logger = logging.getLogger(__name__)

SETTINGS_ID = "city_pages_autogen"

DEFAULT_SETTINGS = {
    "enabled": True,
    "daily_count": 5,        # LLM calls per day
    "hour_utc": 4,           # 04:00 UTC ≈ 05:00 BST / 04:00 GMT
    "drain_email_sent": False,
    "last_run_date": None,
    "last_run_succeeded": 0,
    "last_run_failed": 0,
    "last_run_message": None,
    # Auto-approve: opt-in safety switch. When enabled, any newly-generated
    # page that scores ≥ `auto_approve_threshold` is promoted to
    # `approved` in the same tick without waiting for admin review.
    "auto_approve_enabled": False,
    "auto_approve_threshold": 90,
    "last_run_auto_approved": 0,
}


async def _load_settings(db) -> dict:
    doc = await db.website_settings.find_one({"_id": SETTINGS_ID}, {"_id": 0}) or {}
    return {**DEFAULT_SETTINGS, **doc}


async def _save_settings(db, patch: dict) -> None:
    await db.website_settings.update_one(
        {"_id": SETTINGS_ID},
        {"$set": {**patch, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )


async def _send_drain_email(db, total_approved_or_generated: int) -> None:
    recipients = await _admin_emails(db)
    if not recipients:
        logger.info("city-pages auto-gen drain: no admin recipients, skipping email")
        return
    base = (os.environ.get("ADMIN_BASE_URL") or os.environ.get("SHOP_WEBSITE_URL") or "https://tilestation.co.uk").rstrip("/")
    review_url = f"{base}/admin/seo"
    html = f"""
    <div style="font-family: -apple-system, Segoe UI, Roboto, sans-serif; line-height: 1.55; color: #0f172a; max-width: 580px; margin: 0 auto;">
      <h2 style="margin: 0 0 12px; font-size: 20px;">🏘️ City Landing Pages — queue fully generated</h2>
      <p>The daily auto-generator has finished drafting AI copy for every pending town × intent
      page in your queue. <strong>{total_approved_or_generated}</strong> pages are now sitting in
      <em>generated</em> status, waiting for your review.</p>
      <p style="margin: 18px 0;">
        <a href="{review_url}"
           style="display:inline-block;background:#059669;color:#fff;text-decoration:none;
                  padding:10px 18px;border-radius:8px;font-weight:600;">
          Review &amp; approve in SEO Command Centre →
        </a>
      </p>
      <p style="font-size: 13px; color: #475569; margin-top: 24px;">
        You'll only get this email once per drain. If you seed new towns later, the daily job
        will start working through the new batch and send another one of these when it's done.
      </p>
    </div>
    """
    res = await send_simple_email_if_possible(
        to=recipients,
        subject=f"🏘️ {total_approved_or_generated} city pages ready to review",
        html=html,
    )
    logger.info(f"city-pages auto-gen drain email: {res}")


async def run_city_pages_autogen_tick(force: bool = False) -> dict:
    """Hourly probe — only generates when:

    * settings.enabled is True,
    * the current UTC hour matches settings.hour_utc (or `force=True`),
    * we haven't already run today.

    Returns a small dict with the outcome so the admin UI / logs can show
    what happened on the last tick.
    """
    db = get_db()
    settings = await _load_settings(db)

    if not settings.get("enabled", True) and not force:
        return {"skipped": True, "reason": "disabled"}

    now_utc = datetime.now(timezone.utc)
    today = now_utc.date().isoformat()

    if not force:
        if now_utc.hour != int(settings.get("hour_utc", 4)):
            return {"skipped": True, "reason": "wrong_hour"}
        if settings.get("last_run_date") == today:
            return {"skipped": True, "reason": "already_ran_today"}

    # Re-arm drain email if there ARE new pending rows since the last drain.
    pending_count = await db.city_landing_pages.count_documents({"status": "pending"})
    if pending_count > 0 and settings.get("drain_email_sent"):
        await _save_settings(db, {"drain_email_sent": False})
        settings["drain_email_sent"] = False

    if pending_count == 0:
        # Nothing to do. If we haven't sent the "all done" email for this
        # drain yet, send it now so the admin knows the queue is drained.
        if not settings.get("drain_email_sent"):
            generated_or_approved = await db.city_landing_pages.count_documents({
                "status": {"$in": ["generated", "approved"]}
            })
            await _send_drain_email(db, generated_or_approved)
            await _save_settings(db, {
                "drain_email_sent": True,
                "last_run_date": today,
                "last_run_succeeded": 0,
                "last_run_failed": 0,
                "last_run_message": "queue empty — drain email sent",
            })
            return {"ran": True, "succeeded": 0, "failed": 0, "drain_email_sent": True}
        await _save_settings(db, {
            "last_run_date": today,
            "last_run_succeeded": 0,
            "last_run_failed": 0,
            "last_run_message": "queue empty — no work to do",
        })
        return {"ran": True, "succeeded": 0, "failed": 0, "queue_empty": True}

    # Pull the next N pending rows and run the same per-row generator the
    # batch endpoint uses. We import lazily to avoid a circular import at
    # scheduler init time.
    from routes.city_landing_pages import _generate_for_row  # noqa: PLC0415

    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        msg = "EMERGENT_LLM_KEY not configured — skipping"
        logger.warning(f"city-pages auto-gen: {msg}")
        await _save_settings(db, {"last_run_date": today, "last_run_message": msg})
        return {"ran": False, "error": msg}

    daily_count = max(1, min(int(settings.get("daily_count", 5)), 25))
    rows = await db.city_landing_pages.find(
        {"status": "pending"}, {"_id": 0}
    ).sort("tier", 1).limit(daily_count).to_list(daily_count)

    succeeded = 0
    failed = 0
    auto_approved = 0
    auto_approve_enabled = bool(settings.get("auto_approve_enabled"))
    threshold = int(settings.get("auto_approve_threshold", 90))

    for row in rows:
        ok, _msg = await _generate_for_row(db, row, api_key)
        if not ok:
            failed += 1
            continue
        succeeded += 1
        if auto_approve_enabled:
            fresh = await db.city_landing_pages.find_one(
                {"slug": row["slug"]},
                {"_id": 0, "confidence_score": 1},
            ) or {}
            if int(fresh.get("confidence_score", 0)) >= threshold:
                await db.city_landing_pages.update_one(
                    {"slug": row["slug"]},
                    {"$set": {
                        "status": "approved",
                        "approved_at": datetime.now(timezone.utc),
                        "approved_by": "auto-approve",
                    }},
                )
                auto_approved += 1
                # Log the publish for the daily digest. Sitemap re-submit
                # is handled in batch below to avoid hammering GSC once
                # per page (10 pages/day = 10 redundant calls otherwise).
                try:
                    from services.seo_autonomous import on_city_page_published
                    await on_city_page_published(row["slug"])
                except Exception:
                    logger.exception("[seo-autopilot] log city publish failed")

    await _save_settings(db, {
        "last_run_date": today,
        "last_run_succeeded": succeeded,
        "last_run_failed": failed,
        "last_run_auto_approved": auto_approved,
        "last_run_message": (
            f"generated {succeeded}/{len(rows)} (failed {failed})"
            + (f", auto-approved {auto_approved}" if auto_approve_enabled else "")
        ),
    })

    # If any pages were auto-approved (= now publicly visible), nudge
    # Google Search Console to recrawl the sitemap so they're picked up
    # in hours instead of weeks. The helper is throttled internally so
    # multiple drainer runs in the same day don't spam Google.
    if auto_approved:
        try:
            from services import gsc as gsc_service  # local import to avoid circular
            await gsc_service.maybe_auto_submit_sitemap(reason="city_pages_drained")
        except Exception:
            logger.exception("auto-submit sitemap after city-pages drain failed")

    logger.info(
        f"city-pages auto-gen tick: ran={len(rows)} ok={succeeded} fail={failed} auto_approved={auto_approved}"
    )
    return {
        "ran": True,
        "attempted": len(rows),
        "succeeded": succeeded,
        "failed": failed,
        "auto_approved": auto_approved,
    }

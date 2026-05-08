"""
Weekly SEO quality digest for AI City Landing Pages.

What it does
------------
Every Monday morning, after the daily auto-generator has been chewing
through the queue all week, this digest emails admins a one-glance audit
of the AI machine: what got auto-approved, what got rejected by the
confidence checklist, and the most common reasons drafts didn't make it.

Why a separate digest from the existing weekly SEO digest?
The existing `seo_digest.py` is about search-query insights (what users
are typing into the storefront search box). This one is about the AI
content factory — completely different audience signal, would clutter
the other email.

Pipeline
--------
1. Pull every `city_landing_pages` row touched in the last 7 days
   (approved_at, ai_generated_at within window).
2. Bucket them: auto-approved · manually approved · low-confidence
   (still in `generated` after a generation attempt).
3. Aggregate per-check failure counts so the email can show "top
   reasons drafts failed: missing real_phone (4×), word_count_ok (2×)".
4. Render a single HTML email with summary stats + 3 bullet sections +
   one CTA back to /admin/seo.
5. Idempotency: writes `last_sent_iso_week` into a dedicated settings
   doc so a redeploy can't double-send.
"""
from __future__ import annotations

import logging
import os
from collections import Counter
from datetime import datetime, timedelta, timezone

from config import get_db
from services.email import send_simple_email_if_possible
from services.seo_digest import _admin_emails

logger = logging.getLogger(__name__)

SETTINGS_ID = "seo_quality_digest"


def _admin_url() -> str:
    return (
        os.environ.get("ADMIN_BASE_URL")
        or os.environ.get("SHOP_WEBSITE_URL")
        or "https://tilestation.co.uk"
    ).rstrip("/")


async def _gather_last_7d(db) -> dict:
    """Read every city_landing_pages doc updated in the last 7 days and
    bucket them. Pure read — no side effects."""
    since = datetime.now(timezone.utc) - timedelta(days=7)

    # Approved this week (split by manual vs auto).
    approved_rows = await db.city_landing_pages.find(
        {"status": "approved", "approved_at": {"$gte": since}},
        {"_id": 0},
    ).to_list(2000)

    auto_approved = [r for r in approved_rows if (r.get("approved_by") == "auto-approve")]
    manual_approved = [r for r in approved_rows if r.get("approved_by") != "auto-approve"]

    # Drafts generated this week but NOT promoted — i.e. low-confidence
    # rejects waiting on human review.
    low_conf = await db.city_landing_pages.find(
        {"status": "generated", "ai_generated_at": {"$gte": since}},
        {"_id": 0},
    ).to_list(2000)

    # Aggregate the most common failed checks across rejected drafts AND
    # auto-approved pages (so admin sees "we let these through but they
    # had X imperfection").
    failure_counter: Counter[str] = Counter()
    for r in low_conf:
        for c in r.get("confidence_failed") or []:
            failure_counter[c] += 1

    # Score distribution for auto-approved pages (sanity check).
    auto_scores = [int(r.get("confidence_score") or 0) for r in auto_approved]

    return {
        "since": since,
        "auto_approved": auto_approved,
        "manual_approved": manual_approved,
        "low_conf": low_conf,
        "totals": {
            "auto_approved_count": len(auto_approved),
            "manual_approved_count": len(manual_approved),
            "low_conf_count": len(low_conf),
            "auto_score_avg": (round(sum(auto_scores) / len(auto_scores), 1) if auto_scores else None),
            "auto_score_min": (min(auto_scores) if auto_scores else None),
        },
        "top_failures": failure_counter.most_common(6),
    }


def _row_li(row: dict, base_url: str) -> str:
    """Render one row into a single-line bullet for the email."""
    score = row.get("confidence_score")
    score_html = (
        f'<span style="background:#dcfce7;color:#065f46;padding:1px 6px;border-radius:4px;font-family:monospace;font-size:11px">{score}%</span>'
        if isinstance(score, int) and score >= 90
        else f'<span style="background:#fef3c7;color:#92400e;padding:1px 6px;border-radius:4px;font-family:monospace;font-size:11px">{score}%</span>'
        if isinstance(score, int) and score >= 75
        else f'<span style="background:#fee2e2;color:#991b1b;padding:1px 6px;border-radius:4px;font-family:monospace;font-size:11px">{score or 0}%</span>'
    )
    failed = row.get("confidence_failed") or []
    failed_html = (
        f' <span style="color:#94a3b8;font-size:11px">— failed: {", ".join(failed[:3])}{"…" if len(failed) > 3 else ""}</span>'
        if failed
        else ""
    )
    public_url = f"{base_url}{row.get('url') or ('/tiles/' + row.get('slug', ''))}"
    return (
        f'<li style="margin:4px 0;line-height:1.4">'
        f'  {score_html} '
        f'  <a href="{public_url}" style="color:#0f172a;text-decoration:none">{row.get("h1") or row.get("slug")}</a>'
        f'  {failed_html}'
        f'</li>'
    )


def _render_html(payload: dict) -> str:
    base = _admin_url()
    review_url = f"{base}/admin/seo"
    t = payload["totals"]

    auto_html = (
        "".join(_row_li(r, base) for r in payload["auto_approved"][:8])
        or '<li style="color:#94a3b8">Nothing auto-approved this week.</li>'
    )
    manual_html = (
        "".join(_row_li(r, base) for r in payload["manual_approved"][:8])
        or '<li style="color:#94a3b8">No manual approvals this week.</li>'
    )
    low_html = (
        "".join(_row_li(r, base) for r in payload["low_conf"][:8])
        or '<li style="color:#94a3b8">No low-confidence drafts pending.</li>'
    )

    failures_html = (
        "".join(
            f'<li><code style="background:#f1f5f9;padding:1px 4px;border-radius:3px">{name}</code> · '
            f'<strong>{count}×</strong></li>'
            for name, count in payload["top_failures"]
        )
        or '<li style="color:#94a3b8">No check failed this week.</li>'
    )

    score_chip = (
        f'avg <strong>{t["auto_score_avg"]}%</strong>, min <strong>{t["auto_score_min"]}%</strong>'
        if t["auto_score_avg"] is not None
        else "no auto-approvals"
    )

    return f"""
    <div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:620px;margin:0 auto;color:#0f172a">
      <div style="background:linear-gradient(135deg,#059669,#0d9488);color:#fff;padding:22px 24px">
        <h1 style="margin:0;font-size:22px">🤖 SEO Quality · Last 7 Days</h1>
        <p style="margin:6px 0 0;opacity:.9;font-size:13px">
          AI city landing pages — what shipped, what got held back, and why.
        </p>
      </div>

      <div style="padding:22px 24px;background:#fff">
        <div style="display:flex;gap:10px;flex-wrap:wrap;font-size:12px;color:#475569;margin-bottom:18px">
          <span style="background:#ecfdf5;color:#065f46;padding:6px 10px;border-radius:6px">
            ✅ {t["auto_approved_count"]} auto-approved · {score_chip}
          </span>
          <span style="background:#eff6ff;color:#1e40af;padding:6px 10px;border-radius:6px">
            ✋ {t["manual_approved_count"]} manually approved
          </span>
          <span style="background:#fef3c7;color:#92400e;padding:6px 10px;border-radius:6px">
            ⏳ {t["low_conf_count"]} low-confidence drafts waiting
          </span>
        </div>

        <h2 style="margin:18px 0 8px;font-size:15px;color:#065f46">✅ Auto-approved this week</h2>
        <ul style="padding-left:18px;margin:0;font-size:13px">{auto_html}</ul>

        <h2 style="margin:22px 0 8px;font-size:15px;color:#1e40af">✋ Approved manually this week</h2>
        <ul style="padding-left:18px;margin:0;font-size:13px">{manual_html}</ul>

        <h2 style="margin:22px 0 8px;font-size:15px;color:#92400e">⏳ Low-confidence drafts — your review queue</h2>
        <ul style="padding-left:18px;margin:0;font-size:13px">{low_html}</ul>

        <h2 style="margin:22px 0 8px;font-size:15px;color:#9f1239">🩹 Top reasons drafts failed</h2>
        <ul style="padding-left:18px;margin:0;font-size:13px">{failures_html}</ul>
        <p style="font-size:12px;color:#64748b;margin:8px 0 0">
          Use these to refine the AI prompt or the confidence rubric. A repeating
          failure usually means the prompt isn't being explicit enough.
        </p>

        <div style="text-align:center;margin:28px 0 4px">
          <a href="{review_url}" style="display:inline-block;background:#059669;color:#fff;text-decoration:none;padding:10px 22px;border-radius:8px;font-weight:600;font-size:14px">
            Open SEO Command Centre →
          </a>
        </div>
      </div>

      <div style="background:#0f172a;color:#94a3b8;padding:12px;text-align:center;font-size:11px">
        You're receiving this because you're an admin on Tile Station.<br/>
        Cron: every Monday 09:30 Europe/London.
      </div>
    </div>
    """


async def run_seo_quality_digest_tick(force: bool = False) -> dict:
    """Top-level scheduler entry. Returns a small status dict so the
    admin's manual-trigger button can render the outcome."""
    db = get_db()
    settings = await db.website_settings.find_one({"_id": SETTINGS_ID}) or {}
    iso_week = datetime.now(timezone.utc).strftime("%G-W%V")
    if not force and settings.get("last_sent_iso_week") == iso_week:
        return {"ok": True, "skipped": True, "reason": "already sent this iso week"}

    payload = await _gather_last_7d(db)
    t = payload["totals"]

    # Skip empty digest unless forced — no point in mailing zero activity.
    if not force and (t["auto_approved_count"] + t["manual_approved_count"] + t["low_conf_count"]) == 0:
        return {"ok": True, "skipped": True, "reason": "no city-page activity in window"}

    recipients = await _admin_emails(db)
    if not recipients:
        return {"ok": False, "skipped": True, "reason": "no admin recipients"}

    # Apply super-admin-managed allowlist (same channel as daily SEO digest).
    from services.notification_prefs import get_authorized_recipients
    authorised = set(await get_authorized_recipients("seo_quality_digest"))
    recipients = [e for e in recipients if e in authorised]
    if not recipients:
        return {"ok": False, "skipped": True, "reason": "no_authorized_recipients"}

    subject = (
        f"[Tile Station] SEO quality · "
        f"{t['auto_approved_count']} auto-approved, {t['low_conf_count']} pending"
    )
    res = await send_simple_email_if_possible(
        to=recipients,
        subject=subject,
        html=_render_html(payload),
    )
    if not res.get("success"):
        logger.warning(f"seo-quality-digest send failed: {res}")
        return {"ok": False, "error": res.get("error")}

    await db.website_settings.update_one(
        {"_id": SETTINGS_ID},
        {"$set": {
            "last_sent_iso_week": iso_week,
            "last_sent_at": datetime.now(timezone.utc),
            "last_totals": t,
            "recipients_count": len(recipients),
        }},
        upsert=True,
    )
    return {"ok": True, "recipients": len(recipients), **t}

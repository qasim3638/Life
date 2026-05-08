"""
Weekly SEO impact digest — emailed every Monday 09:00 Europe/London.

Bundles last 7 days of search-insight data into a single admin email so the
team has eyes on the SEO loop even when no one's logged into /admin/marketing.

Sections:
  • Headline — total searches, zero-result count, plug-in count
  • Plugged this week — keywords with `products_targeting > 0`
  • Still open — top missed queries with no targeting yet
  • Top hits — searches that ARE converting (reinforce these)

Each row deep-links straight into the Search Insights card so the admin can
take action with one click.

Idempotency: writes a `_id="seo_digest"` doc into `website_settings` with
`last_sent_iso_week` so the same week never goes out twice if the scheduler
double-fires (e.g. after a redeploy).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta

from config import get_db

logger = logging.getLogger(__name__)


def _admin_origin() -> str:
    """Best-effort URL for deep links inside the email. Falls back to the
    public storefront URL if no admin URL is configured."""
    return (
        os.environ.get("ADMIN_BASE_URL")
        or os.environ.get("SHOP_WEBSITE_URL")
        or "https://tilestation.co.uk"
    ).rstrip("/")


async def _admin_emails(db) -> list:
    cursor = db.users.find(
        {"role": {"$in": ["admin", "super_admin"]}, "email": {"$ne": None}},
        {"_id": 0, "email": 1},
    )
    out = [u.get("email") async for u in cursor]
    return [e for e in out if e]


async def _gather_last_7d(db) -> dict:
    """Run the same aggregation the admin Search Insights card runs, with a
    fixed 7-day window. We inline the aggregation rather than calling the
    HTTP endpoint to keep this scheduler-friendly + auth-free."""
    since = datetime.now(timezone.utc) - timedelta(days=7)

    async def _top(stage_match: dict, limit: int = 25) -> list:
        pipeline = [
            {"$match": {"created_at": {"$gte": since}, **stage_match}},
            {"$group": {
                "_id": "$q_lower",
                "query": {"$first": "$q"},
                "count": {"$sum": 1},
                "sample_suggestions": {"$first": "$suggestions_offered"},
            }},
            {"$sort": {"count": -1}},
            {"$limit": limit},
        ]
        out = []
        async for d in db.search_query_log.aggregate(pipeline):
            out.append({
                "query": d.get("query"),
                "count": int(d.get("count", 0)),
                "sample_suggestions": d.get("sample_suggestions") or [],
            })
        return out

    missed = await _top({"is_zero_result": True})
    hits = await _top({"is_zero_result": False}, limit=10)

    # Annotate missed rows with the per-keyword targeting count.
    keywords_lower = [(r["query"] or "").lower() for r in missed if r.get("query")]
    targeting: dict = {}
    if keywords_lower:
        cur = db.seo_description_drafts.aggregate([
            {"$match": {
                "status": "approved",
                "approved_for_keyword_lower": {"$in": keywords_lower},
            }},
            {"$group": {"_id": "$approved_for_keyword_lower", "count": {"$sum": 1}}},
        ])
        async for d in cur:
            targeting[d["_id"]] = int(d.get("count", 0))
    for r in missed:
        r["products_targeting"] = targeting.get((r.get("query") or "").lower(), 0)

    plugged = [r for r in missed if r["products_targeting"] > 0]
    still_open = [r for r in missed if r["products_targeting"] == 0]

    totals = {
        "total_searches": await db.search_query_log.count_documents({"created_at": {"$gte": since}}),
        "zero_result_searches": await db.search_query_log.count_documents({
            "created_at": {"$gte": since}, "is_zero_result": True,
        }),
        "unique_zero_queries": len({r["query"].lower() for r in missed if r.get("query")}),
    }

    return {
        "totals": totals,
        "plugged": plugged,
        "still_open": still_open[:10],
        "hits": hits,
    }


def _render_html(payload: dict, origin: str) -> str:
    t = payload["totals"]
    plugged = payload["plugged"]
    still_open = payload["still_open"]
    hits = payload["hits"]

    insights_url = f"{origin}/admin/marketing?tab=seo"

    def _row_missed(r):
        kw = r["query"]
        deep = f"{origin}/admin/marketing?tab=seo-drafts&target={kw}"
        sugg = ", ".join((r.get("sample_suggestions") or [])[:2])
        sugg_html = f"<div style='color:#94a3b8;font-size:12px'>→ did-you-mean: {sugg}</div>" if sugg else ""
        return (
            f"<tr><td style='padding:6px 8px;border-bottom:1px solid #f1f5f9'>"
            f"<a href='{deep}' style='color:#7c3aed;text-decoration:none;font-family:ui-monospace,monospace'>{kw}</a>"
            f"{sugg_html}"
            f"</td><td style='padding:6px 8px;border-bottom:1px solid #f1f5f9;text-align:right;font-variant-numeric:tabular-nums'>"
            f"<strong>{r['count']}×</strong></td></tr>"
        )

    def _row_plugged(r):
        kw = r["query"]
        return (
            f"<tr><td style='padding:6px 8px;border-bottom:1px solid #f1f5f9;font-family:ui-monospace,monospace'>{kw}</td>"
            f"<td style='padding:6px 8px;border-bottom:1px solid #f1f5f9;text-align:right'>"
            f"<span style='background:#dcfce7;color:#166534;padding:2px 6px;border-radius:4px;font-size:11px;font-weight:bold'>"
            f"✓ {r['products_targeting']} targeting</span></td></tr>"
        )

    def _row_hit(r):
        return (
            f"<tr><td style='padding:6px 8px;border-bottom:1px solid #f1f5f9;font-family:ui-monospace,monospace'>{r['query']}</td>"
            f"<td style='padding:6px 8px;border-bottom:1px solid #f1f5f9;text-align:right;font-variant-numeric:tabular-nums'>"
            f"{r['count']}×</td></tr>"
        )

    plugged_html = "".join(_row_plugged(r) for r in plugged) if plugged else (
        "<tr><td colspan='2' style='padding:12px 8px;color:#94a3b8;font-style:italic'>"
        "Nothing plugged this week — open the SEO Drafts queue and target one or two of the missed phrases below.</td></tr>"
    )
    open_html = "".join(_row_missed(r) for r in still_open) if still_open else (
        "<tr><td colspan='2' style='padding:12px 8px;color:#94a3b8;font-style:italic'>"
        "No open gaps in the last 7 days. Nice work!</td></tr>"
    )
    hits_html = "".join(_row_hit(r) for r in hits) if hits else (
        "<tr><td colspan='2' style='padding:12px 8px;color:#94a3b8;font-style:italic'>"
        "No successful searches yet — needs traffic.</td></tr>"
    )

    return f"""
    <div style="font-family:Inter,Arial,sans-serif;max-width:640px;margin:0 auto;color:#0f172a">
      <div style="background:linear-gradient(135deg,#1a1a2e,#312e81);color:#fff;padding:24px;text-align:left">
        <div style="color:#f0c14b;font-weight:bold;letter-spacing:1px;font-size:12px">TILE STATION · SEO IMPACT</div>
        <h1 style="margin:8px 0 0;font-size:22px">Weekly digest — last 7 days</h1>
        <p style="margin:6px 0 0;color:#cbd5e1;font-size:14px">
          {t['total_searches']} searches · <strong style='color:#fda4af'>{t['zero_result_searches']} zero-result</strong>
          ({t['unique_zero_queries']} unique queries) ·
          <strong style='color:#86efac'>{len(plugged)} keyword{'' if len(plugged) == 1 else 's'} plugged</strong>
        </p>
      </div>

      <div style="padding:24px;background:#f8fafc">
        <h2 style="margin:0 0 12px;color:#166534;font-size:16px">✓ Plugged this week</h2>
        <table style="width:100%;border-collapse:collapse;background:#fff;border:1px solid #e2e8f0;border-radius:6px;overflow:hidden">
          {plugged_html}
        </table>

        <h2 style="margin:24px 0 12px;color:#9f1239;font-size:16px">⚠ Still open · top SEO gaps</h2>
        <table style="width:100%;border-collapse:collapse;background:#fff;border:1px solid #e2e8f0;border-radius:6px;overflow:hidden">
          {open_html}
        </table>
        <p style="font-size:12px;color:#64748b;margin:8px 0 0">
          Click any keyword to open the SEO Drafts queue with that phrase pre-targeted —
          pick a relevant product, click <strong>Regenerate</strong>, then <strong>Save &amp; publish</strong>.
        </p>

        <h2 style="margin:24px 0 12px;color:#065f46;font-size:16px">📈 Proven intent · top hits</h2>
        <table style="width:100%;border-collapse:collapse;background:#fff;border:1px solid #e2e8f0;border-radius:6px;overflow:hidden">
          {hits_html}
        </table>

        <div style="text-align:center;margin:28px 0 0">
          <a href="{insights_url}" style="display:inline-block;background:#7c3aed;color:#fff;text-decoration:none;padding:10px 22px;border-radius:6px;font-weight:600;font-size:14px">
            Open Search Insights →
          </a>
        </div>
      </div>

      <div style="background:#1a1a2e;color:#94a3b8;padding:14px;text-align:center;font-size:12px">
        You're receiving this because you're an admin on Tile Station.
        Cron: every Monday 09:00 Europe/London.
      </div>
    </div>
    """


async def run_seo_digest_tick(force: bool = False) -> dict:
    """Top-level entry called by the APScheduler job. Returns a status
    dict for logging / manual-trigger UIs."""
    db = get_db()
    settings = await db.website_settings.find_one({"_id": "seo_digest"}) or {}
    iso_week = datetime.now(timezone.utc).strftime("%G-W%V")
    if not force and settings.get("last_sent_iso_week") == iso_week:
        return {"ok": True, "skipped": True, "reason": "already sent this iso week"}

    payload = await _gather_last_7d(db)
    # Skip empty digest unless the admin forces it (no point spamming).
    if not force and payload["totals"]["total_searches"] == 0:
        return {"ok": True, "skipped": True, "reason": "no searches in window"}

    recipients = await _admin_emails(db)
    if not recipients:
        return {"ok": False, "skipped": True, "reason": "no admin recipients"}

    # Apply super-admin-managed allowlist for the daily SEO digest channel.
    from services.notification_prefs import get_authorized_recipients
    authorised = set(await get_authorized_recipients("seo_quality_digest"))
    recipients = [e for e in recipients if e in authorised]
    if not recipients:
        return {"ok": False, "skipped": True, "reason": "no_authorized_recipients"}

    html = _render_html(payload, _admin_origin())
    subject = (
        f"[Tile Station] SEO digest · {payload['totals']['zero_result_searches']} zero-result, "
        f"{len(payload['plugged'])} plugged"
    )
    try:
        from services.email import send_email_notification
        await send_email_notification(
            to_emails=recipients,
            subject=subject,
            html_content=html,
            from_name="Tile Station SEO",
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"SEO digest email send failed: {e}")
        return {"ok": False, "error": str(e)}

    await db.website_settings.update_one(
        {"_id": "seo_digest"},
        {"$set": {
            "last_sent_iso_week": iso_week,
            "last_sent_at": datetime.now(timezone.utc),
            "last_payload_summary": payload["totals"],
            "recipients_count": len(recipients),
        }},
        upsert=True,
    )
    return {
        "ok": True,
        "recipients": len(recipients),
        "totals": payload["totals"],
        "plugged_count": len(payload["plugged"]),
        "still_open_count": len(payload["still_open"]),
    }

"""
Weekly SEO Autopilot summary — Mondays @ 08:30 Europe/London.

Counts what the autopilot did over the last 7 days (canonicals, redirects,
stale refreshes, alerts) and emails a peace-of-mind summary to anyone
authorised for `seo_quality_digest`. Different from the monthly P&L
because it focuses on *maintenance* — silent reassurance that the
machinery is running.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from config import get_db

logger = logging.getLogger(__name__)


async def run_seo_autopilot_weekly_summary() -> dict:
    db = get_db()
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=7)

    # Idempotency — don't double-send within the same ISO week.
    iso_week = f"{now.isocalendar().year}-W{now.isocalendar().week:02d}"
    settings = await db.website_settings.find_one({"_id": "autopilot_weekly_summary"}) or {}
    if settings.get("last_sent_iso_week") == iso_week:
        return {"ok": True, "skipped": True, "reason": "already_sent_this_week"}

    # Aggregate the audit log by action_type.
    pipeline = [
        {"$match": {"ts": {"$gte": since}}},
        {"$group": {"_id": "$action_type", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    by_type = await db.seo_autopilot_actions.aggregate(pipeline).to_list(length=50)
    total = sum(r["count"] for r in by_type)

    # Sample of the most recent 10 actions for the email body.
    recent = await db.seo_autopilot_actions.find(
        {"ts": {"$gte": since}}, {"_id": 0},
        sort=[("ts", -1)], limit=10,
    ).to_list(length=10)

    # Other living counters
    canonicals_total = await db.seo_canonical_overrides.count_documents({})
    redirects_total = await db.seo_redirects.count_documents({})
    snapshots_total = await db.brand_serp_history.count_documents({})

    # Recipients via the super-admin allowlist.
    from services.notification_prefs import get_authorized_recipients
    recipients = await get_authorized_recipients("seo_quality_digest")
    if not recipients:
        return {"ok": False, "skipped": True, "reason": "no_authorized_recipients"}

    # If literally nothing happened, still send a one-line "all quiet"
    # heartbeat — that's the whole point of peace-of-mind.
    if total == 0:
        html = f"""
        <div style="font-family:-apple-system,system-ui,sans-serif;background:#f8fafc;padding:32px 16px">
          <div style="max-width:600px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;border:1px solid #e2e8f0">
            <div style="background:#0f172a;color:#fff;padding:20px 24px">
              <div style="font-size:11px;letter-spacing:2px;color:#a7f3d0;font-weight:700;text-transform:uppercase">SEO Autopilot · Weekly summary</div>
              <h1 style="margin:6px 0 0;font-size:20px">All quiet — nothing needed fixing this week</h1>
            </div>
            <div style="padding:22px 24px;font-size:14px;color:#334155;line-height:1.6">
              <p style="margin:0 0 12px">No cannibalization, no 404s worth redirecting, no stale pages, no algorithm shifts. The site's running clean.</p>
              <p style="margin:0;color:#64748b;font-size:12px">Total auto-fixes since launch: <strong>{canonicals_total + redirects_total}</strong>
                · Brand SERP snapshots: <strong>{snapshots_total}</strong></p>
            </div>
          </div>
        </div>
        """
        subject = "[Tile Station] SEO Autopilot — all quiet this week"
    else:
        type_rows = "".join(
            f"<tr><td style='padding:8px 12px;border-bottom:1px solid #f1f5f9'>{_human_action(r['_id'])}</td>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #f1f5f9;text-align:right;font-weight:700;color:#047857'>{r['count']}</td></tr>"
            for r in by_type
        )
        recent_rows = "".join(
            f"<li style='font-size:12px;color:#475569;margin:4px 0'>"
            f"<span style='color:#94a3b8'>{(r.get('ts').strftime('%a %d %b') if hasattr(r.get('ts'), 'strftime') else '—')}</span> · "
            f"<strong>{_human_action(r['action_type'])}</strong> "
            f"{_summary_for(r)}</li>"
            for r in recent
        )
        html = f"""
        <div style="font-family:-apple-system,system-ui,sans-serif;background:#f8fafc;padding:32px 16px">
          <div style="max-width:640px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;border:1px solid #e2e8f0">
            <div style="background:linear-gradient(135deg,#064e3b,#047857);color:#fff;padding:24px">
              <div style="font-size:11px;letter-spacing:2px;color:#a7f3d0;font-weight:700;text-transform:uppercase">SEO Autopilot · Weekly summary</div>
              <h1 style="margin:6px 0 4px;font-size:22px">The autopilot fixed {total} thing{'s' if total != 1 else ''} for you this week</h1>
              <p style="margin:0;font-size:13px;color:#d1fae5">{since.strftime('%d %b')} → {now.strftime('%d %b %Y')}</p>
            </div>
            <div style="padding:24px">
              <table style="width:100%;border-collapse:collapse;font-size:14px;margin-bottom:18px">
                <thead><tr style="background:#f8fafc;color:#475569;text-transform:uppercase;font-size:11px;letter-spacing:1px">
                  <th style="text-align:left;padding:8px 12px">Action</th>
                  <th style="text-align:right;padding:8px 12px">Count</th>
                </tr></thead>
                <tbody>{type_rows}</tbody>
              </table>
              <h3 style="font-size:13px;color:#0f172a;margin:20px 0 6px">Recent actions</h3>
              <ul style="list-style:disc;padding-left:18px;margin:0">{recent_rows}</ul>
              <p style="margin:18px 0 0;font-size:11px;color:#94a3b8;line-height:1.6">
                Lifetime totals — Canonical fixes: <strong>{canonicals_total}</strong>
                · 301 redirects: <strong>{redirects_total}</strong>
                · Brand SERP snapshots: <strong>{snapshots_total}</strong>.
                Full audit at /admin/seo-autopilot.
              </p>
            </div>
          </div>
        </div>
        """
        subject = f"[Tile Station] SEO Autopilot — {total} auto-fix{'es' if total != 1 else ''} this week"

    try:
        from services.email import send_simple_email_if_possible
        result = await send_simple_email_if_possible(
            to=recipients, subject=subject, html=html,
        )
    except Exception as exc:
        logger.warning("autopilot weekly summary send failed: %s", exc)
        return {"ok": False, "error": str(exc)}

    if not (result or {}).get("success"):
        return {"ok": False, "error": (result or {}).get("error", "send_failed")}

    await db.website_settings.update_one(
        {"_id": "autopilot_weekly_summary"},
        {"$set": {
            "last_sent_iso_week": iso_week,
            "last_sent_at": now,
            "last_total_actions": total,
            "recipients_count": len(recipients),
        }},
        upsert=True,
    )
    return {
        "ok": True, "iso_week": iso_week, "recipients": len(recipients),
        "total_actions": total, "subject": subject,
    }


def _human_action(action_type: str) -> str:
    return {
        "cannibalization_canonical": "Cannibalization fix (canonical)",
        "stale_page_refresh": "Stale page refreshed",
        "stale_page_marked": "Stale page flagged",
        "auto_redirect_created": "Auto 301 redirect created",
        "algorithm_alert": "Algorithm update alert",
        "brand_serp_drop": "Brand SERP drop detected",
    }.get(action_type, action_type.replace("_", " ").title())


def _summary_for(action: dict) -> str:
    a = action
    if a.get("from_path"):
        return f"<span style='font-family:monospace;color:#64748b'>{a['from_path']} → {a.get('to_path', '')}</span>"
    if a.get("loser_path"):
        return f"<span style='font-family:monospace;color:#64748b'>{a['loser_path']}</span> → {a.get('winner_url', '')}"
    if a.get("query"):
        return f"on “<strong>{a['query']}</strong>”"
    if a.get("slug"):
        return f"slug <code>{a['slug']}</code>"
    if a.get("delta_pct") is not None:
        return f"<strong>{a['delta_pct']:+}%</strong> ({a.get('direction', '')})"
    return ""

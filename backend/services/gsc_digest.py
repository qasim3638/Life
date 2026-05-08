"""
GSC weekly digest + CTR-drop alerts (Phase 4).

Two scheduled jobs share this file:
  • run_gsc_weekly_digest()  → email every Monday 09:30 Europe/London
  • run_gsc_ctr_drop_check() → daily, fires Telegram alerts when a city
                               page's 7-day CTR collapses vs its baseline

Both are no-ops when no admin has connected GSC yet, so the scheduler
can register them at boot regardless of connection state.

Idempotency:
  • Digest stamps `gsc_weekly_digest.last_sent_iso_week` so the same
    Monday never goes out twice if the scheduler double-fires.
  • CTR alerts dedupe on (page_url, iso_week) — at most one alert per
    page per week so a flapping URL doesn't spam Telegram.

Why a separate digest from `seo_digest.py`?
  • That one is fed by storefront search queries (zero-result intents,
    plugged keywords, etc) — internal data only.
  • This one is fed by Google Search Console — external SEO signals.
  • Keeping them separate means each can iterate independently.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta

from config import get_db

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────────────
# Shared helpers
# ────────────────────────────────────────────────────────────────────────


def _admin_origin() -> str:
    return (
        os.environ.get("ADMIN_BASE_URL")
        or os.environ.get("SHOP_WEBSITE_URL")
        or "https://tilestation.co.uk"
    ).rstrip("/")


async def _admin_emails(db) -> list[str]:
    cursor = db.users.find(
        {"role": {"$in": ["admin", "super_admin"]}, "email": {"$ne": None}},
        {"_id": 0, "email": 1},
    )
    out = [u.get("email") async for u in cursor]
    return [e for e in out if e]


async def _connected_admin_id(db) -> str | None:
    """Pick the most-recently-active admin token. Mirrors the helper
    in services.gsc but kept local so this module can be called even
    when the Search Analytics endpoints aren't hot.
    """
    doc = await db["gsc_oauth_tokens"].find_one(
        {}, sort=[("last_used_at", -1)], projection={"_id": 1},
    )
    return doc.get("_id") if doc else None


# ────────────────────────────────────────────────────────────────────────
# Weekly digest — Monday 09:30 Europe/London
# ────────────────────────────────────────────────────────────────────────


def _fmt_int(n) -> str:
    n = int(n or 0)
    return f"{n:,}"


def _fmt_pct(p) -> str:
    if p is None:
        return "—"
    return f"{p * 100:.2f}%"


def _delta_chip(prev: float, curr: float, *, lower_is_better: bool = False) -> str:
    """Render a simple ▲/▼ delta chip. Designed for inline HTML — keeps
    colours minimal so it works in plain-text email clients too.
    """
    if not prev and not curr:
        return ""
    if not prev:
        return ' <span style="color:#059669;font-weight:600">NEW</span>'
    pct = (curr - prev) / prev * 100
    arrow = "▲" if pct >= 0 else "▼"
    is_good = (pct >= 0) ^ lower_is_better
    color = "#059669" if is_good else "#dc2626"
    return f' <span style="color:{color};font-weight:600">{arrow}{abs(pct):.0f}%</span>'


async def _gather_week_payload(admin_id: str) -> dict:
    """Pull this-week vs prior-week numbers from GSC for the digest.
    Wrapped in try/except per call so a partial GSC outage still
    yields a useful (if reduced) email.
    """
    from services.gsc import (
        get_overview, get_top_queries, get_top_pages,
    )
    out: dict = {}
    try:
        out["this_week"] = await get_overview(admin_id, days=7)
    except Exception as e:
        logger.warning("digest: this_week fetch failed — %s", e)
        out["this_week"] = {"totals": {"clicks": 0, "impressions": 0, "ctr": 0, "avg_position": 0}}
    try:
        out["last_week"] = await get_overview(admin_id, days=14)
        # this is days 1-14, so "prior 7" = totals - this_week (rough)
        tw = out["this_week"]["totals"]
        lw = out["last_week"]["totals"]
        out["prior_week"] = {
            "clicks": max(0, lw["clicks"] - tw["clicks"]),
            "impressions": max(0, lw["impressions"] - tw["impressions"]),
        }
    except Exception as e:
        logger.warning("digest: last_week fetch failed — %s", e)
        out["prior_week"] = {"clicks": 0, "impressions": 0}
    try:
        tq = await get_top_queries(admin_id, days=7, limit=10)
        out["top_queries"] = tq.get("rows", [])
    except Exception as e:
        logger.warning("digest: top_queries fetch failed — %s", e)
        out["top_queries"] = []
    try:
        tp = await get_top_pages(admin_id, days=7, limit=10)
        out["top_pages"] = tp.get("rows", [])
    except Exception as e:
        logger.warning("digest: top_pages fetch failed — %s", e)
        out["top_pages"] = []
    return out


def _render_digest_html(payload: dict, admin_origin: str) -> str:
    tw = payload["this_week"]["totals"]
    pw = payload.get("prior_week", {"clicks": 0, "impressions": 0})

    rows_q = "".join(
        f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #f1f5f9">{(r.get('query') or '—')[:60]}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f1f5f9;text-align:right;font-variant-numeric:tabular-nums">{_fmt_int(r['clicks'])}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f1f5f9;text-align:right;color:#64748b;font-variant-numeric:tabular-nums">{_fmt_int(r['impressions'])}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f1f5f9;text-align:right;color:#64748b">{_fmt_pct(r['ctr'])}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f1f5f9;text-align:right;color:#64748b">{r['position']:.1f}</td>
        </tr>
        """
        for r in payload["top_queries"][:10]
    ) or '<tr><td colspan="5" style="padding:14px;text-align:center;color:#94a3b8">No queries this week.</td></tr>'

    rows_p = "".join(
        f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #f1f5f9"><a href="{r.get('page','#')}" style="color:#2563eb;text-decoration:none">{(r.get('page') or '').replace(admin_origin, '')[:80]}</a></td>
          <td style="padding:8px 12px;border-bottom:1px solid #f1f5f9;text-align:right;font-variant-numeric:tabular-nums">{_fmt_int(r['clicks'])}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f1f5f9;text-align:right;color:#64748b;font-variant-numeric:tabular-nums">{_fmt_int(r['impressions'])}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f1f5f9;text-align:right;color:#64748b">{_fmt_pct(r['ctr'])}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f1f5f9;text-align:right;color:#64748b">{r['position']:.1f}</td>
        </tr>
        """
        for r in payload["top_pages"][:10]
    ) or '<tr><td colspan="5" style="padding:14px;text-align:center;color:#94a3b8">No pages reported impressions.</td></tr>'

    return f"""
    <div style="font-family:-apple-system,system-ui,sans-serif;background:#0f172a;color:#e2e8f0;padding:24px">
      <div style="max-width:680px;margin:0 auto;background:#fff;color:#0f172a;border-radius:14px;overflow:hidden">
        <div style="background:linear-gradient(135deg,#1e293b,#0f172a);padding:24px;color:#fff">
          <div style="font-size:11px;letter-spacing:2px;color:#60a5fa;font-weight:600;text-transform:uppercase">Tile Station SEO digest</div>
          <h1 style="margin:6px 0 0;font-size:22px">Last 7 days on Google</h1>
        </div>

        <div style="padding:24px">
          <table style="width:100%;border-collapse:collapse;margin-bottom:18px">
            <tr>
              <td style="padding:12px;background:#f0fdf4;border-radius:10px;width:50%;vertical-align:top">
                <div style="font-size:11px;color:#15803d;letter-spacing:1px;text-transform:uppercase;font-weight:600">Clicks</div>
                <div style="font-size:28px;font-weight:700;margin-top:4px">{_fmt_int(tw['clicks'])}{_delta_chip(pw['clicks'], tw['clicks'])}</div>
                <div style="font-size:12px;color:#64748b">vs {_fmt_int(pw['clicks'])} prior week</div>
              </td>
              <td style="width:8px"></td>
              <td style="padding:12px;background:#eff6ff;border-radius:10px;width:50%;vertical-align:top">
                <div style="font-size:11px;color:#1d4ed8;letter-spacing:1px;text-transform:uppercase;font-weight:600">Impressions</div>
                <div style="font-size:28px;font-weight:700;margin-top:4px">{_fmt_int(tw['impressions'])}{_delta_chip(pw['impressions'], tw['impressions'])}</div>
                <div style="font-size:12px;color:#64748b">vs {_fmt_int(pw['impressions'])} prior week</div>
              </td>
            </tr>
          </table>

          <h3 style="margin:20px 0 8px;font-size:14px;color:#0f172a">Top queries this week</h3>
          <table style="width:100%;border-collapse:collapse;font-size:13px">
            <thead>
              <tr style="background:#f8fafc;color:#475569;text-transform:uppercase;font-size:11px;letter-spacing:1px">
                <th style="text-align:left;padding:8px 12px">Query</th>
                <th style="text-align:right;padding:8px 12px">Clicks</th>
                <th style="text-align:right;padding:8px 12px">Impr.</th>
                <th style="text-align:right;padding:8px 12px">CTR</th>
                <th style="text-align:right;padding:8px 12px">Pos</th>
              </tr>
            </thead>
            <tbody>{rows_q}</tbody>
          </table>

          <h3 style="margin:24px 0 8px;font-size:14px;color:#0f172a">Top pages this week</h3>
          <table style="width:100%;border-collapse:collapse;font-size:13px">
            <thead>
              <tr style="background:#f8fafc;color:#475569;text-transform:uppercase;font-size:11px;letter-spacing:1px">
                <th style="text-align:left;padding:8px 12px">URL</th>
                <th style="text-align:right;padding:8px 12px">Clicks</th>
                <th style="text-align:right;padding:8px 12px">Impr.</th>
                <th style="text-align:right;padding:8px 12px">CTR</th>
                <th style="text-align:right;padding:8px 12px">Pos</th>
              </tr>
            </thead>
            <tbody>{rows_p}</tbody>
          </table>

          <div style="margin-top:24px;text-align:center">
            <a href="{admin_origin}/admin/seo" style="background:#2563eb;color:#fff;padding:10px 20px;border-radius:8px;text-decoration:none;font-weight:600;font-size:13px">Open Search Console panel →</a>
          </div>
        </div>

        <div style="background:#f8fafc;color:#64748b;padding:14px;text-align:center;font-size:11px">
          You're receiving this because you're an admin on Tile Station. Cron: daily 09:30 Europe/London.<br>
          Data from Google Search Console (sc-domain:tilestation.co.uk) · ~2-day delay.
        </div>
      </div>
    </div>
    """


async def run_gsc_weekly_digest(force: bool = False) -> dict:
    db = get_db()
    settings = await db.website_settings.find_one({"_id": "gsc_weekly_digest"}) or {}
    iso_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if not force and settings.get("last_sent_iso_date") == iso_date:
        return {"ok": True, "skipped": True, "reason": "already_sent_today"}

    admin_id = await _connected_admin_id(db)
    if not admin_id:
        return {"ok": True, "skipped": True, "reason": "no_connected_admin"}

    payload = await _gather_week_payload(admin_id)
    if not force and payload["this_week"]["totals"]["impressions"] == 0:
        return {"ok": True, "skipped": True, "reason": "no_data_yet"}

    recipients = await _admin_emails(db)
    if not recipients:
        return {"ok": False, "skipped": True, "reason": "no_admin_recipients"}

    # Apply super-admin-managed allowlist for the GSC weekly digest channel.
    from services.notification_prefs import get_authorized_recipients
    authorised = set(await get_authorized_recipients("gsc_weekly_digest"))
    recipients = [e for e in recipients if e in authorised]
    if not recipients:
        return {"ok": False, "skipped": True, "reason": "no_authorized_recipients"}

    html = _render_digest_html(payload, _admin_origin())
    tw = payload["this_week"]["totals"]
    subject = f"[Tile Station] SEO daily · {_fmt_int(tw['clicks'])} clicks · {_fmt_int(tw['impressions'])} impressions (last 7d)"

    try:
        from services.email import send_email_notification
        await send_email_notification(
            to_emails=recipients,
            subject=subject,
            html_content=html,
            from_name="Tile Station SEO",
        )
    except Exception as e:
        logger.warning("GSC weekly digest email send failed: %s", e)
        return {"ok": False, "error": str(e)}

    await db.website_settings.update_one(
        {"_id": "gsc_weekly_digest"},
        {"$set": {
            "last_sent_iso_date": iso_date,
            "last_sent_at": datetime.now(timezone.utc),
            "last_payload_summary": tw,
            "recipients_count": len(recipients),
        }},
        upsert=True,
    )
    return {"ok": True, "recipients": len(recipients), "totals": tw}


# ────────────────────────────────────────────────────────────────────────
# CTR-drop Telegram alerts — daily 08:00 Europe/London
# ────────────────────────────────────────────────────────────────────────

# Thresholds — picked to surface real regressions, not noise:
#   • Page must have ≥50 impressions in the last 7 days (filter weak signals)
#   • CTR must have dropped ≥50% vs prior 28-day baseline
#   • Each page can fire at most once per ISO week
CTR_DROP_MIN_IMPRESSIONS = 50
CTR_DROP_RATIO_THRESHOLD = 0.5   # current CTR < baseline CTR * (1 - this)


async def _baseline_pages(admin_id: str) -> dict[str, dict]:
    """28-day per-page baseline from GSC. Returns dict keyed on URL."""
    from services.gsc import get_top_pages
    res = await get_top_pages(admin_id, days=28, limit=500)
    return {r["page"]: r for r in res.get("rows", []) if r.get("page")}


async def _current_pages(admin_id: str) -> dict[str, dict]:
    from services.gsc import get_top_pages
    res = await get_top_pages(admin_id, days=7, limit=500)
    return {r["page"]: r for r in res.get("rows", []) if r.get("page")}


async def run_gsc_ctr_drop_check(force: bool = False) -> dict:
    db = get_db()
    admin_id = await _connected_admin_id(db)
    if not admin_id:
        return {"ok": True, "skipped": True, "reason": "no_connected_admin"}

    try:
        baseline = await _baseline_pages(admin_id)
        current = await _current_pages(admin_id)
    except Exception as e:
        logger.warning("CTR-drop check fetch failed: %s", e)
        return {"ok": False, "error": str(e)}

    iso_week = datetime.now(timezone.utc).strftime("%G-W%V")
    drops: list[dict] = []
    for url, c in current.items():
        if c["impressions"] < CTR_DROP_MIN_IMPRESSIONS:
            continue
        b = baseline.get(url)
        if not b or b["ctr"] <= 0:
            continue
        if c["ctr"] >= b["ctr"] * (1 - CTR_DROP_RATIO_THRESHOLD):
            continue  # not enough of a drop
        drops.append({
            "url": url,
            "current_ctr": c["ctr"],
            "baseline_ctr": b["ctr"],
            "current_impressions": c["impressions"],
            "current_clicks": c["clicks"],
            "current_position": c["position"],
            "baseline_position": b["position"],
        })

    # Dedupe: skip pages we already alerted this week unless `force`.
    fired_col = db["gsc_ctr_drop_alerts_fired"]
    fresh: list[dict] = []
    for d in drops:
        if not force:
            seen = await fired_col.find_one({"url": d["url"], "iso_week": iso_week})
            if seen:
                continue
        fresh.append(d)

    if not fresh:
        return {"ok": True, "drops_detected": len(drops), "fresh_alerts": 0}

    # Build a single Telegram message with up to 10 drops
    lines = [f"🚨 *CTR drop detected on {len(fresh)} page" + ("s" if len(fresh) != 1 else "") + "*", ""]
    for d in fresh[:10]:
        path = d["url"].replace(_admin_origin(), "")
        drop_pct = (1 - d["current_ctr"] / d["baseline_ctr"]) * 100
        lines.append(
            f"• `{path[:60]}`\n"
            f"  CTR `{_fmt_pct(d['current_ctr'])}` ← was `{_fmt_pct(d['baseline_ctr'])}` ({drop_pct:.0f}% drop)\n"
            f"  pos `{d['current_position']:.1f}` ← was `{d['baseline_position']:.1f}` · {_fmt_int(d['current_impressions'])} impressions"
        )
    if len(fresh) > 10:
        lines.append(f"… and {len(fresh) - 10} more.")
    lines.append("")
    lines.append(f"🔍 [Open SEO panel]({_admin_origin()}/admin/seo)")
    text = "\n".join(lines)

    try:
        from services.telegram_notify import send_telegram
        await send_telegram(text)
    except Exception as e:
        logger.warning("CTR-drop Telegram send failed: %s", e)
        return {"ok": False, "error": str(e), "would_have_alerted": len(fresh)}

    # Mark these as fired so we don't re-alert in the same ISO week.
    now = datetime.now(timezone.utc)
    await fired_col.insert_many([
        {"url": d["url"], "iso_week": iso_week, "fired_at": now, "drop_pct": (1 - d["current_ctr"] / d["baseline_ctr"]) * 100}
        for d in fresh
    ])
    return {"ok": True, "fresh_alerts": len(fresh), "drops_detected": len(drops)}

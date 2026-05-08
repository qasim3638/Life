"""
Monthly SEO P&L digest — sent on the 1st of each month at 08:00
Europe/London.

What it does
------------
Translates the last 28 days of Search Console data into pound-equivalent
"saved Google Ads spend", compares it to the previous month's snapshot,
and surfaces:

  1. Headline £/month with month-on-month % delta.
  2. Top 5 saved-spend keywords (the ones paying the bills).
  3. Up to 3 keywords that *fell off page 1* this month — i.e. went from
     position ≤ 10 to position > 10. These are the "rescue these first"
     items the owner wants to skim with their morning coffee.

Idempotency
-----------
Stamps `seo_pnl_digest.last_sent_iso_month` (YYYY-MM) so the email
goes out exactly once per calendar month even if the scheduler
double-fires.

Why a separate digest from `gsc_digest.py`?
-------------------------------------------
That one is the *operations* digest (clicks, impressions, CTR, top
pages) — daily/weekly cadence, granular, owner-skim.
This one is the *finance* digest (£ saved, MoM trend) — monthly
cadence, board-meeting framing, owner-celebrate.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from config import get_db

logger = logging.getLogger(__name__)


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
    doc = await db["gsc_oauth_tokens"].find_one(
        {}, sort=[("last_used_at", -1)], projection={"_id": 1},
    )
    return doc.get("_id") if doc else None


def _fmt_gbp(n) -> str:
    n = float(n or 0)
    return f"£{n:,.2f}"


def _fmt_int(n) -> str:
    return f"{int(n or 0):,}"


def _delta_chip(prev: float | None, curr: float) -> str:
    """Render an inline ▲/▼ % chip. Email-safe (no JS, no images)."""
    if prev is None or prev <= 0:
        return ' <span style="color:#059669;font-weight:600">NEW</span>'
    pct = ((curr - prev) / prev) * 100
    if abs(pct) < 0.5:
        return ' <span style="color:#64748b;font-weight:600">±0%</span>'
    arrow = "▲" if pct >= 0 else "▼"
    color = "#059669" if pct >= 0 else "#dc2626"
    return f' <span style="color:{color};font-weight:600">{arrow}{abs(pct):.0f}%</span>'


# ────────────────────────────────────────────────────────────────────────
# Payload construction
# ────────────────────────────────────────────────────────────────────────


async def _gather_pnl_payload(admin_id: str) -> dict:
    """Compute current-month overview + top keywords + fell-off-page-1
    list + previous-month comparison from snapshots.
    """
    from routes.ads_savings import _estimate_cpc_gbp
    from services import gsc as gsc_service

    # 1) Current 28-day window — drives "this month's saved spend"
    current = await gsc_service.get_top_queries(admin_id, days=28, limit=500)
    rows = current.get("rows", []) or []

    # Decorate rows with CPC + value
    decorated = []
    total_value = 0.0
    for r in rows:
        clicks = int(r.get("clicks") or 0)
        cpc = _estimate_cpc_gbp(r.get("query") or "")
        value = clicks * cpc
        total_value += value
        decorated.append({
            "query": r.get("query") or "",
            "clicks": clicks,
            "impressions": int(r.get("impressions") or 0),
            "position": float(r.get("position") or 0.0),
            "estimated_cpc_gbp": cpc,
            "estimated_value_gbp": round(value, 2),
        })

    # Project 28-day window to ~30-day month for the headline
    monthly_value = round(total_value * (30.0 / 28.0), 2)

    # 2) Top 5 saved-spend
    decorated.sort(key=lambda x: x["estimated_value_gbp"], reverse=True)
    top5 = decorated[:5]

    # 3) Fell-off-page-1 — compare current 28-day position vs prior 28-day
    # for the SAME query. Threshold: prev_pos <= 10 AND curr_pos > 10.
    prior = await gsc_service.get_top_queries(admin_id, days=56, limit=500)
    # Note: the GSC service window is days from end-2; the 56-day query
    # captures both periods. To get a true "prior 28d only", we'd need a
    # second range query. For v1 we approximate by using the 56-day
    # average position as the "baseline" — a position that improves
    # to <11 in current means it was previously ≥11 in the average.
    prior_by_q = {r.get("query"): float(r.get("position") or 0.0) for r in (prior.get("rows", []) or [])}
    fell_off = []
    new_wins = []
    for r in decorated:
        curr_pos = r["position"]
        prev_pos = prior_by_q.get(r["query"])
        if prev_pos is None or r["impressions"] < 30:
            continue
        # Fell off page 1: was ≤ 10.5 in baseline, now > 11
        if prev_pos <= 10.5 and curr_pos > 11.0:
            fell_off.append({
                **r,
                "prev_position": round(prev_pos, 1),
                "delta_positions": round(curr_pos - prev_pos, 1),
            })
        # Broke INTO page 1: was > 11 in baseline, now ≤ 10
        elif prev_pos > 11.0 and curr_pos <= 10.0:
            new_wins.append({
                **r,
                "prev_position": round(prev_pos, 1),
                "delta_positions": round(prev_pos - curr_pos, 1),  # positive = improvement
            })
    fell_off.sort(key=lambda x: x["delta_positions"], reverse=True)
    fell_off = fell_off[:3]
    # Wins ranked by saved-spend value — show the queries that pay the most.
    new_wins.sort(key=lambda x: x["estimated_value_gbp"], reverse=True)
    new_wins = new_wins[:3]

    # 4) Previous month figure from snapshots collection
    db = get_db()
    snapshots = await db["ads_savings_snapshots"].find(
        {}, sort=[("_id", -1)], projection={"_id": 1, "totals": 1}, limit=2,
    ).to_list(length=2)
    # Most recent doc could be THIS month (just-captured); skip it for the
    # MoM compare and use the one before it.
    now = datetime.now(timezone.utc)
    this_month_id = f"{now.year:04d}-{now.month:02d}"
    prev_monthly: float | None = None
    prev_month_label: str | None = None
    for s in snapshots:
        if s.get("_id") and s["_id"] != this_month_id:
            prev_monthly = float((s.get("totals") or {}).get("estimated_monthly_value_gbp") or 0.0)
            prev_month_label = s["_id"]
            break

    return {
        "month_label": this_month_id,
        "monthly_value_gbp": monthly_value,
        "annual_value_gbp": round(monthly_value * 12, 2),
        "prev_monthly_value_gbp": prev_monthly,
        "prev_month_label": prev_month_label,
        "keywords_ranked": len(decorated),
        "total_clicks": sum(r["clicks"] for r in decorated),
        "top5": top5,
        "new_page_1_wins": new_wins,
        "fell_off_page_1": fell_off,
    }


# ────────────────────────────────────────────────────────────────────────
# HTML rendering
# ────────────────────────────────────────────────────────────────────────


def _render_pnl_html(payload: dict, admin_origin: str) -> str:
    monthly = payload["monthly_value_gbp"]
    annual = payload["annual_value_gbp"]
    prev = payload["prev_monthly_value_gbp"]
    prev_label = payload["prev_month_label"]
    delta = _delta_chip(prev, monthly)

    # Top 5 rows
    top5_rows = "".join(
        f"""
        <tr>
          <td style="padding:10px 12px;border-bottom:1px solid #f1f5f9;font-weight:600">{i+1}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #f1f5f9">{r['query'][:60]}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #f1f5f9;text-align:right;font-variant-numeric:tabular-nums">{_fmt_int(r['clicks'])}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #f1f5f9;text-align:right;color:#64748b;font-variant-numeric:tabular-nums">{r['position']:.1f}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #f1f5f9;text-align:right;color:#059669;font-weight:700;font-variant-numeric:tabular-nums">{_fmt_gbp(r['estimated_value_gbp'])}</td>
        </tr>
        """ for i, r in enumerate(payload["top5"])
    ) or '<tr><td colspan="5" style="padding:14px;text-align:center;color:#94a3b8">No keyword data yet — Search Console needs more time.</td></tr>'

    # Fell-off-page-1 rows
    fell_rows = "".join(
        f"""
        <tr>
          <td style="padding:10px 12px;border-bottom:1px solid #fee2e2">{r['query'][:60]}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #fee2e2;text-align:right;color:#991b1b;font-weight:700;font-variant-numeric:tabular-nums">#{r['prev_position']:.0f} → #{r['position']:.0f}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #fee2e2;text-align:right;color:#dc2626;font-weight:700;font-variant-numeric:tabular-nums">{_fmt_gbp(r['estimated_value_gbp'])}/mo at risk</td>
        </tr>
        """ for r in payload["fell_off_page_1"]
    )

    # New-page-1-wins rows (symmetric to fell_off — celebrates ranking gains)
    win_rows = "".join(
        f"""
        <tr>
          <td style="padding:10px 12px;border-bottom:1px solid #d1fae5">{r['query'][:60]}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #d1fae5;text-align:right;color:#065f46;font-weight:700;font-variant-numeric:tabular-nums">#{r['prev_position']:.0f} → #{r['position']:.0f}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #d1fae5;text-align:right;color:#059669;font-weight:700;font-variant-numeric:tabular-nums">+{_fmt_gbp(r['estimated_value_gbp'])}/mo locked in</td>
        </tr>
        """ for r in payload["new_page_1_wins"]
    )

    wins_section = f"""
    <h3 style="margin:24px 0 8px;font-size:14px;color:#065f46">✨ New page-1 wins this month</h3>
    <p style="margin:0 0 8px;font-size:13px;color:#64748b">Keywords that climbed onto page 1 — the saved-spend they unlock now compounds month after month.</p>
    <table style="width:100%;border-collapse:collapse;font-size:13px;background:#ecfdf5;border-radius:8px;overflow:hidden">
      <thead>
        <tr style="background:#d1fae5;color:#064e3b;text-transform:uppercase;font-size:11px;letter-spacing:1px">
          <th style="text-align:left;padding:10px 12px">Keyword</th>
          <th style="text-align:right;padding:10px 12px">Position</th>
          <th style="text-align:right;padding:10px 12px">New monthly value</th>
        </tr>
      </thead>
      <tbody>{win_rows}</tbody>
    </table>
    """ if payload["new_page_1_wins"] else ""

    fell_section = f"""
    <h3 style="margin:24px 0 8px;font-size:14px;color:#991b1b">⚠ Fell off page 1 this month</h3>
    <p style="margin:0 0 8px;font-size:13px;color:#64748b">These were ranking on page 1 — defending them brings the saved-spend back fastest.</p>
    <table style="width:100%;border-collapse:collapse;font-size:13px;background:#fef2f2;border-radius:8px;overflow:hidden">
      <thead>
        <tr style="background:#fee2e2;color:#7f1d1d;text-transform:uppercase;font-size:11px;letter-spacing:1px">
          <th style="text-align:left;padding:10px 12px">Keyword</th>
          <th style="text-align:right;padding:10px 12px">Position</th>
          <th style="text-align:right;padding:10px 12px">Value at risk</th>
        </tr>
      </thead>
      <tbody>{fell_rows}</tbody>
    </table>
    """ if payload["fell_off_page_1"] else """
    <h3 style="margin:24px 0 8px;font-size:14px;color:#059669">✓ No keywords fell off page 1 this month</h3>
    <p style="margin:0;font-size:13px;color:#64748b">Rankings held — momentum intact.</p>
    """

    prev_compare_line = (
        f"vs {_fmt_gbp(prev)} in {prev_label}" if prev is not None
        else "first full month — baseline established"
    )

    return f"""
    <div style="font-family:-apple-system,system-ui,'Segoe UI',Roboto,sans-serif;background:#0f172a;padding:32px 16px">
      <div style="max-width:680px;margin:0 auto;background:#fff;color:#0f172a;border-radius:14px;overflow:hidden;box-shadow:0 10px 40px rgba(0,0,0,0.2)">

        <div style="background:linear-gradient(135deg,#064e3b,#047857);padding:32px 28px;color:#fff">
          <div style="font-size:11px;letter-spacing:2px;color:#a7f3d0;font-weight:600;text-transform:uppercase">Tile Station · monthly SEO P&amp;L</div>
          <h1 style="margin:8px 0 4px;font-size:24px">{payload['month_label']} — your SEO scoreboard</h1>
          <p style="margin:0;font-size:13px;color:#d1fae5;line-height:1.5">
            What you'd be paying Google Ads to buy the traffic SEO is sending you for free.
          </p>
        </div>

        <div style="padding:28px">

          <div style="background:linear-gradient(135deg,#ecfdf5,#fff);border:1px solid #d1fae5;border-radius:12px;padding:24px;text-align:center;margin-bottom:24px">
            <div style="font-size:11px;color:#047857;letter-spacing:1.5px;text-transform:uppercase;font-weight:600">Saved ad spend this month</div>
            <div style="font-size:42px;font-weight:800;color:#0f172a;margin-top:6px;line-height:1">{_fmt_gbp(monthly)}{delta}</div>
            <div style="font-size:13px;color:#64748b;margin-top:6px">{prev_compare_line}</div>
            <div style="font-size:13px;color:#0f172a;margin-top:14px;padding-top:14px;border-top:1px dashed #d1fae5">
              That's <strong>{_fmt_gbp(annual)}</strong> a year you're not paying Google Ads.
            </div>
          </div>

          <table style="width:100%;border-collapse:collapse;margin-bottom:18px">
            <tr>
              <td style="padding:14px;background:#f8fafc;border-radius:10px;width:50%;vertical-align:top">
                <div style="font-size:11px;color:#475569;letter-spacing:1px;text-transform:uppercase;font-weight:600">Keywords ranking</div>
                <div style="font-size:24px;font-weight:700;margin-top:4px">{_fmt_int(payload['keywords_ranked'])}</div>
              </td>
              <td style="width:8px"></td>
              <td style="padding:14px;background:#f8fafc;border-radius:10px;width:50%;vertical-align:top">
                <div style="font-size:11px;color:#475569;letter-spacing:1px;text-transform:uppercase;font-weight:600">Organic clicks (28d)</div>
                <div style="font-size:24px;font-weight:700;margin-top:4px">{_fmt_int(payload['total_clicks'])}</div>
              </td>
            </tr>
          </table>

          <h3 style="margin:24px 0 8px;font-size:14px;color:#0f172a">Top 5 keywords paying the bills</h3>
          <p style="margin:0 0 8px;font-size:13px;color:#64748b">These are the queries returning the most ad-equivalent value. Defend rankings here first.</p>
          <table style="width:100%;border-collapse:collapse;font-size:13px">
            <thead>
              <tr style="background:#f8fafc;color:#475569;text-transform:uppercase;font-size:11px;letter-spacing:1px">
                <th style="text-align:left;padding:10px 12px;width:32px">#</th>
                <th style="text-align:left;padding:10px 12px">Keyword</th>
                <th style="text-align:right;padding:10px 12px">Clicks</th>
                <th style="text-align:right;padding:10px 12px">Pos</th>
                <th style="text-align:right;padding:10px 12px">Saved</th>
              </tr>
            </thead>
            <tbody>{top5_rows}</tbody>
          </table>

          {wins_section}

          {fell_section}

          <div style="margin-top:32px;text-align:center">
            <a href="{admin_origin}/admin/ads-savings" style="background:#047857;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;font-size:13px;display:inline-block">
              Open the SEO ↔ Ads dashboard →
            </a>
          </div>

        </div>

        <div style="background:#0f172a;color:#94a3b8;padding:18px 28px;text-align:center;font-size:11px;line-height:1.6">
          You're getting this because you're an admin on Tile Station.<br>
          Sent automatically on the 1st of every month · Data from Google Search Console (28-day window).
        </div>

      </div>
    </div>
    """


# ────────────────────────────────────────────────────────────────────────
# Public entrypoint — called by the scheduler + admin "Send now" button.
# ────────────────────────────────────────────────────────────────────────


async def run_seo_pnl_monthly_digest(force: bool = False) -> dict:
    db = get_db()
    settings = await db.website_settings.find_one({"_id": "seo_pnl_digest"}) or {}
    now = datetime.now(timezone.utc)
    iso_month = f"{now.year:04d}-{now.month:02d}"
    if not force and settings.get("last_sent_iso_month") == iso_month:
        return {"ok": True, "skipped": True, "reason": "already_sent_this_month"}

    admin_id = await _connected_admin_id(db)
    if not admin_id:
        return {"ok": True, "skipped": True, "reason": "no_connected_admin"}

    payload = await _gather_pnl_payload(admin_id)
    # Don't send a "you saved £0" email — wait until there's signal.
    if not force and payload["monthly_value_gbp"] <= 0:
        return {"ok": True, "skipped": True, "reason": "no_savings_yet"}

    # Filter through the per-admin notification authorisations table.
    # Anyone not explicitly authorised by a super-admin gets nothing.
    from services.notification_prefs import get_authorized_recipients
    recipients = await get_authorized_recipients("monthly_pnl")
    if not recipients:
        return {"ok": False, "skipped": True, "reason": "no_authorized_recipients"}

    html = _render_pnl_html(payload, _admin_origin())
    delta_str = ""
    if payload["prev_monthly_value_gbp"]:
        pct = ((payload["monthly_value_gbp"] - payload["prev_monthly_value_gbp"])
               / payload["prev_monthly_value_gbp"]) * 100
        delta_str = f" ({'+' if pct >= 0 else ''}{pct:.0f}% MoM)"
    subject = (
        f"[Tile Station] {iso_month} SEO P&L — {_fmt_gbp(payload['monthly_value_gbp'])} "
        f"saved this month{delta_str}"
    )

    try:
        from services.email import send_email_notification
        await send_email_notification(
            to_emails=recipients,
            subject=subject,
            html_content=html,
            from_name="Tile Station SEO",
        )
    except Exception as e:
        logger.warning("SEO P&L monthly digest send failed: %s", e)
        return {"ok": False, "error": str(e)}

    await db.website_settings.update_one(
        {"_id": "seo_pnl_digest"},
        {"$set": {
            "last_sent_iso_month": iso_month,
            "last_sent_at": now,
            "last_payload_summary": {
                "monthly_value_gbp": payload["monthly_value_gbp"],
                "prev_monthly_value_gbp": payload["prev_monthly_value_gbp"],
                "keywords_ranked": payload["keywords_ranked"],
                "fell_off_count": len(payload["fell_off_page_1"]),
                "new_wins_count": len(payload["new_page_1_wins"]),
            },
            "recipients_count": len(recipients),
        }},
        upsert=True,
    )
    return {
        "ok": True,
        "month": iso_month,
        "recipients": len(recipients),
        "subject": subject,
        "monthly_value_gbp": payload["monthly_value_gbp"],
        "fell_off_count": len(payload["fell_off_page_1"]),
        "new_wins_count": len(payload["new_page_1_wins"]),
    }

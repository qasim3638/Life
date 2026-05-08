"""
Weekly Stealth-Keyword Performance Digest
──────────────────────────────────────────

Emails the admin a plain-English summary every Monday 08:00 BST:
  • This-week stealth clicks vs last-week (delta %)
  • Top 5 winning supplier names (by attributed clicks)
  • NEW missed wins since last week (queries that weren't in last
    week's missed list — these are the supplier names to add)
  • Underperformer count (informational, not actionable in email)

Why this matters: the performance widget on /admin/seo is pull-only —
admin has to open the dashboard to see gains. The digest flips it to
push-only: you KNOW each Monday whether the stealth-keyword experiment
is working and where to double down.

Storage:
  • `seo_stealth_digest_settings` — enabled flag, recipients list,
    `last_sent_at`, `last_sent_snapshot`. Upserted singleton at id="main".
  • `seo_stealth_digest_history` — one row per send for audit (not
    currently surfaced in UI but useful for debugging delivery).

Idempotency:
  • Weekly cron calls `run_weekly_digest_if_due()` — skips if
    `enabled=False`, if last send was <6 days ago (safety), or if the
    performance report has zero stealth AND zero missed-wins (nothing
    to report yet — avoids inbox pollution while Google is still
    crawling fresh stealth keywords).
  • Manual admin "Send now" always fires regardless.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from config import get_db

logger = logging.getLogger(__name__)


# ───────── Settings ─────────

DEFAULT_SETTINGS = {
    "enabled": True,
    "recipients": [],  # falls back to ADMIN_EMAIL env var
    "last_sent_at": None,
    "last_sent_snapshot": None,
    # Auto-promote: when enabled, the Monday cron promotes the top
    # NEW missed-win query into a matching collection's stealth
    # keywords — if and only if the query has >= min_impressions
    # AND cleanly matches an existing collection name. Admin can undo
    # via a token link in the digest email for 30 days. Default OFF.
    "auto_promote_enabled": False,
    "auto_promote_min_impressions": 20,
    # Batch mode: when enabled, each weekly run promotes up to N (2-10)
    # queries instead of 1, BUT every batched query must clear 2× the
    # base impressions threshold (stricter bar compensates for volume).
    # Default OFF — stays single-promotion until admin opts in.
    "auto_promote_batch_mode": False,
    "auto_promote_batch_max": 5,
    # Local seed: companion feature — targets city-landing-pages
    # instead of collections. When a new missed-win query contains a
    # recognised UK town name, the seeder injects it into that town's
    # city-page `hidden_seo_keywords`. Requires `auto_promote_enabled`
    # to be True (piggy-backs on the same weekly cron).
    "auto_local_seed_enabled": False,
}


async def get_settings() -> dict:
    db = get_db()
    doc = await db.seo_stealth_digest_settings.find_one({"id": "main"}, {"_id": 0})
    if not doc:
        return {**DEFAULT_SETTINGS, "id": "main"}
    return {**DEFAULT_SETTINGS, **doc, "id": "main"}


async def update_settings(patch: dict, *, admin_email: Optional[str] = None) -> dict:
    db = get_db()
    # Whitelist: admin can only change these fields. last_sent_* is
    # set by the sender, not by the UI.
    allowed = {}
    if "enabled" in patch:
        allowed["enabled"] = bool(patch["enabled"])
    if "recipients" in patch:
        raw = patch.get("recipients")
        if isinstance(raw, str):
            raw = [s.strip() for s in raw.replace(",", "\n").split("\n")]
        recipients = [r for r in (raw or []) if isinstance(r, str) and "@" in r][:10]
        allowed["recipients"] = recipients
    if "auto_promote_enabled" in patch:
        allowed["auto_promote_enabled"] = bool(patch["auto_promote_enabled"])
    if "auto_promote_min_impressions" in patch:
        try:
            v = int(patch["auto_promote_min_impressions"])
            allowed["auto_promote_min_impressions"] = max(5, min(v, 500))
        except (TypeError, ValueError):
            pass
    if "auto_promote_batch_mode" in patch:
        allowed["auto_promote_batch_mode"] = bool(patch["auto_promote_batch_mode"])
    if "auto_promote_batch_max" in patch:
        try:
            v = int(patch["auto_promote_batch_max"])
            allowed["auto_promote_batch_max"] = max(2, min(v, 10))
        except (TypeError, ValueError):
            pass
    if "auto_local_seed_enabled" in patch:
        allowed["auto_local_seed_enabled"] = bool(patch["auto_local_seed_enabled"])
    if not allowed:
        return await get_settings()
    allowed["updated_at"] = datetime.now(timezone.utc)
    if admin_email:
        allowed["updated_by"] = admin_email
    await db.seo_stealth_digest_settings.update_one(
        {"id": "main"},
        {"$set": {"id": "main", **allowed}},
        upsert=True,
    )
    return await get_settings()


def _resolve_recipients(settings: dict) -> list[str]:
    recipients = settings.get("recipients") or []
    if recipients:
        return recipients
    admin_email = os.environ.get("ADMIN_EMAIL")
    if admin_email:
        return [admin_email]
    return []


# ───────── Digest body ─────────

async def _build_digest(days: int = 7) -> dict:
    """Pull this-week and last-week performance reports, diff the
    missed-wins sets, compute deltas. Returns the data structure the
    email template consumes.

    Shape:
      {
        this: {clicks, impressions, ctr, queries_count},
        last: {clicks, impressions, ctr, queries_count},
        delta_pct: {clicks, impressions},
        top_winners: [{keyword, clicks, ...}, ...5],
        new_missed: [{query, clicks, impressions, ctr, position}, ...],
        underperformer_count: int,
        gsc_connected: bool,
        start_date, end_date,
      }
    """
    from services import stealth_seo_performance as perf

    # This week + last fortnight (covers the "last week" comparison
    # window because the report aggregates the trailing N days ending
    # today; we re-query for days=14 and subtract).
    this_week = await perf.get_performance(days=days, force_refresh=True)

    # Previous N-day window — pull a 2N window and subtract this-week
    # totals. Approximate but accurate enough for a direction-of-travel
    # digest; exact per-day splits require the row-level GSC response
    # which we don't retain.
    fortnight = await perf.get_performance(days=days * 2, force_refresh=True)

    def _sub(a: dict, b: dict) -> dict:
        c = max(0, (a.get("clicks") or 0) - (b.get("clicks") or 0))
        i = max(0, (a.get("impressions") or 0) - (b.get("impressions") or 0))
        q = max(0, (a.get("queries_count") or 0) - (b.get("queries_count") or 0))
        return {
            "clicks": c, "impressions": i, "queries_count": q,
            "ctr": (c / i) if i else 0.0,
        }

    last_week = _sub(fortnight.get("stealth") or {}, this_week.get("stealth") or {})
    this_stealth = this_week.get("stealth") or {"clicks": 0, "impressions": 0, "queries_count": 0, "ctr": 0}

    def _delta_pct(this_v: float, last_v: float) -> int:
        if last_v == 0:
            return 100 if this_v > 0 else 0
        return round(((this_v - last_v) / last_v) * 100)

    delta = {
        "clicks": _delta_pct(this_stealth.get("clicks") or 0, last_week["clicks"]),
        "impressions": _delta_pct(this_stealth.get("impressions") or 0, last_week["impressions"]),
    }

    # Diff missed-wins sets — queries in this-week that didn't appear
    # in the previous fortnight's top-20 missed are "new" this week
    this_missed = {m["query"].lower() for m in this_week.get("missed_wins") or []}
    fortnight_missed = {m["query"].lower() for m in fortnight.get("missed_wins") or []}
    new_qs = this_missed - fortnight_missed
    new_missed = [m for m in (this_week.get("missed_wins") or []) if m["query"].lower() in new_qs][:10]

    # Pull any auto-promotions from the last 8 days so the digest
    # can surface "auto-promoted last week" callouts with [Undo] links.
    from services import stealth_seo_auto_promote as ap
    cutoff = datetime.now(timezone.utc) - timedelta(days=8)
    recent_promotes = await ap.list_since(cutoff)

    return {
        "this": this_stealth,
        "last": last_week,
        "delta_pct": delta,
        "top_winners": (this_week.get("top_winners") or [])[:5],
        "new_missed": new_missed,
        "underperformer_count": len(this_week.get("underperformers") or []),
        "gsc_connected": this_week.get("gsc_connected", False),
        "reason": this_week.get("reason"),
        "start_date": this_week.get("start_date"),
        "end_date": this_week.get("end_date"),
        "recent_auto_promotes": recent_promotes,
    }


def _fmt(n) -> str:
    try:
        return f"{int(n):,}"
    except Exception:
        return "0"


def _fmt_delta(pct: int) -> str:
    if pct == 0:
        return '<span style="color:#64748b">flat</span>'
    if pct > 0:
        return f'<span style="color:#059669"><strong>↑ {pct}%</strong></span>'
    return f'<span style="color:#dc2626"><strong>↓ {abs(pct)}%</strong></span>'


def _format_target(row: dict) -> str:
    """Render the promotion target ('→ Spanish collection' vs '→
    Gravesend local page') for the digest email callout."""
    if row.get("scope") == "city_page":
        town = row.get("town") or row.get("city_slug") or "city page"
        return f'<em>{town}</em> local page'
    return f'<em>{row.get("collection") or "collection"}</em> collection'


def _render_html(digest: dict) -> str:
    base = os.environ.get("FRONTEND_BASE_URL", "https://tilestation.co.uk").rstrip("/")
    this = digest["this"]
    last = digest["last"]
    dd = digest["delta_pct"]

    if not digest["gsc_connected"]:
        return f"""
        <h2 style="font-family:system-ui">Stealth-Keyword digest — paused</h2>
        <p>Google Search Console isn't connected, so there's nothing to attribute.</p>
        <p><a href="{base}/admin/seo">Connect Google Search Console</a> to start tracking
        which supplier names drive traffic.</p>
        """

    winners_html = "".join(
        f'<tr><td style="padding:6px 10px;font-family:monospace;color:#065f46">'
        f'<strong>{w["keyword"]}</strong></td>'
        f'<td style="padding:6px 10px;font-size:12px;color:#64748b">'
        f'{w.get("scope")}: {w.get("product_name") or w.get("collection") or "—"}</td>'
        f'<td style="padding:6px 10px;text-align:right;font-family:monospace">'
        f'<strong>{_fmt(w.get("clicks"))}</strong></td>'
        f'<td style="padding:6px 10px;text-align:right;font-family:monospace;color:#64748b">'
        f'{_fmt(w.get("impressions"))}</td></tr>'
        for w in digest["top_winners"]
    ) or (
        '<tr><td colspan="4" style="padding:14px;text-align:center;color:#64748b;font-style:italic">'
        'No stealth keywords have driven clicks yet this week — give Google 2-4 weeks '
        'after enabling auto-fill.</td></tr>'
    )

    missed_html = "".join(
        f'<tr><td style="padding:6px 10px">{m["query"]}</td>'
        f'<td style="padding:6px 10px;text-align:right;font-family:monospace">{_fmt(m.get("impressions"))}</td>'
        f'<td style="padding:6px 10px;text-align:right;font-family:monospace">{_fmt(m.get("clicks"))}</td>'
        f'<td style="padding:6px 10px;text-align:right;font-family:monospace">'
        f'pos {m.get("position")}</td></tr>'
        for m in digest["new_missed"]
    )
    missed_block = f"""
    <h3 style="font-family:system-ui;margin-top:24px">New missed wins this week</h3>
    <p style="color:#64748b;font-size:13px">High-impression searches that DON'T yet match any stealth keyword. Click "Add" in the dashboard to promote them.</p>
    <table style="width:100%;border-collapse:collapse;border:1px solid #e2e8f0;font-size:14px">
      <thead style="background:#fef3c7;text-align:left">
        <tr>
          <th style="padding:8px 10px;border-bottom:1px solid #e2e8f0">Query</th>
          <th style="padding:8px 10px;border-bottom:1px solid #e2e8f0;text-align:right">Impressions</th>
          <th style="padding:8px 10px;border-bottom:1px solid #e2e8f0;text-align:right">Clicks</th>
          <th style="padding:8px 10px;border-bottom:1px solid #e2e8f0;text-align:right">Position</th>
        </tr>
      </thead>
      <tbody>{missed_html}</tbody>
    </table>
    """ if digest["new_missed"] else ""

    # Auto-promote callout — prepended at the top of the email when
    # any promotions happened in the trailing 8-day window. Each row
    # gets a tokenised undo link.
    ap_rows = digest.get("recent_auto_promotes") or []
    ap_block = ""
    if ap_rows:
        items = []
        for r in ap_rows:
            if r.get("undone_at"):
                badge = '<span style="background:#e2e8f0;color:#475569;padding:2px 6px;border-radius:4px;font-size:10px">UNDONE</span>'
                action = ""
            else:
                badge = ""
                undo_url = f'{base}/api/shop/seo/stealth-keywords/auto-promote/undo/{r["token"]}'
                action = (
                    f'<a href="{undo_url}" style="color:#dc2626;font-size:12px;text-decoration:underline">'
                    f'[Undo]</a>'
                )
            items.append(
                f'<li style="margin-bottom:6px">'
                f'<strong>{r["query"]}</strong> → '
                f'{_format_target(r)} '
                f'<span style="color:#64748b;font-size:11px">({_fmt(r.get("impressions"))} impr)</span> {badge} {action}'
                f'</li>'
            )
        ap_block = f"""
        <div style="background:#eef2ff;border:2px solid #c7d2fe;border-radius:8px;padding:14px;margin-bottom:20px">
          <div style="font-size:12px;text-transform:uppercase;color:#3730a3;font-weight:700;letter-spacing:0.05em;margin-bottom:6px">
            ✨ Auto-promoted this week
          </div>
          <ul style="margin:0;padding-left:20px;font-size:14px;line-height:1.5">{"".join(items)}</ul>
          <div style="font-size:11px;color:#64748b;margin-top:8px">
            Unhappy with any of these? Click [Undo] above — removes the keyword and re-opens the query in next week's missed-wins list.
          </div>
        </div>
        """

    return f"""
    <div style="font-family:system-ui,-apple-system,sans-serif;max-width:640px;margin:0 auto;padding:20px;color:#0f172a">
      <h2 style="margin:0 0 4px 0">Stealth-Keyword weekly digest</h2>
      <p style="color:#64748b;margin:0 0 20px 0;font-size:13px">
        {digest.get("start_date")} → {digest.get("end_date")} · tilestation.co.uk
      </p>

      {ap_block}
      <div style="background:#f0fdf4;border:2px solid #86efac;border-radius:8px;padding:16px;margin-bottom:20px">
        <div style="display:flex;gap:20px;flex-wrap:wrap">
          <div>
            <div style="font-size:11px;text-transform:uppercase;color:#065f46;font-weight:700;letter-spacing:0.05em">Stealth clicks</div>
            <div style="font-size:28px;font-weight:800;font-family:monospace;color:#065f46">{_fmt(this.get("clicks"))}</div>
            <div style="font-size:12px;color:#64748b">vs {_fmt(last.get("clicks"))} last week · {_fmt_delta(dd["clicks"])}</div>
          </div>
          <div>
            <div style="font-size:11px;text-transform:uppercase;color:#065f46;font-weight:700;letter-spacing:0.05em">Impressions</div>
            <div style="font-size:28px;font-weight:800;font-family:monospace;color:#065f46">{_fmt(this.get("impressions"))}</div>
            <div style="font-size:12px;color:#64748b">vs {_fmt(last.get("impressions"))} last week · {_fmt_delta(dd["impressions"])}</div>
          </div>
        </div>
      </div>

      <h3 style="font-family:system-ui">Top winning supplier names</h3>
      <table style="width:100%;border-collapse:collapse;border:1px solid #e2e8f0;font-size:14px">
        <thead style="background:#ecfdf5;text-align:left">
          <tr>
            <th style="padding:8px 10px;border-bottom:1px solid #e2e8f0">Keyword</th>
            <th style="padding:8px 10px;border-bottom:1px solid #e2e8f0">Attributed to</th>
            <th style="padding:8px 10px;border-bottom:1px solid #e2e8f0;text-align:right">Clicks</th>
            <th style="padding:8px 10px;border-bottom:1px solid #e2e8f0;text-align:right">Impressions</th>
          </tr>
        </thead>
        <tbody>{winners_html}</tbody>
      </table>

      {missed_block}

      <p style="color:#64748b;font-size:12px;margin-top:24px">
        {digest["underperformer_count"]} stealth keyword{"s are" if digest["underperformer_count"] != 1 else " is"}
        set but haven't driven traffic — not necessarily a problem, but worth auditing if the number grows.
      </p>

      <p style="color:#64748b;font-size:12px;margin-top:24px;padding-top:12px;border-top:1px solid #e2e8f0">
        Open the full dashboard at <a href="{base}/admin/seo">/admin/seo</a> ·
        Pause these emails in the Stealth Performance card.
      </p>
    </div>
    """


# ───────── Runners ─────────

async def send_digest_now(*, recipients: Optional[list[str]] = None) -> dict:
    """Always-on entrypoint — sends the digest regardless of enabled
    flag / last-sent timing. Used by the admin "Send now" button.
    """
    from services.email import send_email_notification

    settings = await get_settings()
    recips = recipients or _resolve_recipients(settings)
    if not recips:
        return {"ok": False, "reason": "no_recipients"}

    digest = await _build_digest(days=7)
    html = _render_html(digest)
    subject_clicks = digest["this"].get("clicks") or 0
    subject = (
        f"Stealth digest · {subject_clicks} clicks · {len(digest['new_missed'])} new missed wins"
    )

    sent = await send_email_notification(
        to_emails=recips,
        subject=subject,
        html_content=html,
    )
    now = datetime.now(timezone.utc)
    db = get_db()
    snapshot = {
        "clicks": digest["this"].get("clicks") or 0,
        "impressions": digest["this"].get("impressions") or 0,
        "top_winner": (digest["top_winners"][0]["keyword"] if digest["top_winners"] else None),
        "new_missed_count": len(digest["new_missed"]),
        "gsc_connected": digest["gsc_connected"],
    }
    await db.seo_stealth_digest_settings.update_one(
        {"id": "main"},
        {"$set": {"last_sent_at": now, "last_sent_snapshot": snapshot,
                   "last_sent_ok": bool(sent), "last_sent_recipients": recips}},
        upsert=True,
    )
    await db.seo_stealth_digest_history.insert_one({
        "at": now, "ok": bool(sent), "recipients": recips,
        "subject": subject, "snapshot": snapshot,
    })
    return {
        "ok": bool(sent),
        "recipients": recips,
        "subject": subject,
        "snapshot": snapshot,
    }


async def run_weekly_digest_if_due() -> dict:
    """Invoked by the cron. Respects the enabled flag, skips when no
    stealth wins AND no missed wins (nothing to report), and has a
    6-day throttle so a mis-configured cron can't spam the admin.
    """
    settings = await get_settings()
    if not settings.get("enabled", True):
        return {"skipped": True, "reason": "disabled"}

    last = settings.get("last_sent_at")
    last_ok = settings.get("last_sent_ok", True)  # default True for backward-compat
    if isinstance(last, datetime) and last_ok:
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if (datetime.now(timezone.utc) - last) < timedelta(days=6):
            return {"skipped": True, "reason": "throttled", "last_sent_at": last.isoformat()}

    # Pre-check: anything worth reporting?
    digest = await _build_digest(days=7)
    has_signal = (
        (digest["this"].get("clicks") or 0) > 0
        or len(digest["new_missed"]) > 0
        or len(digest["top_winners"]) > 0
    )
    if not has_signal and digest["gsc_connected"]:
        return {"skipped": True, "reason": "no_signal"}

    # Run LOCAL seeder first (targets city-pages) — consumes from the
    # same weekly budget as collection auto-promote. Then run the
    # collection auto-promote with the REMAINING budget so the two
    # flows combined never exceed batch_max promotions/week.
    from services import stealth_seo_auto_promote as ap
    from services import stealth_seo_local_seed as lp
    local_promotions = await lp.run_once(digest, settings)

    ap_settings = dict(settings)
    if settings.get("auto_promote_batch_mode", False) and local_promotions:
        remaining = max(0, int(settings.get("auto_promote_batch_max") or 5) - len(local_promotions))
        # Shrink the collection auto-promote quota accordingly
        ap_settings["auto_promote_batch_max"] = remaining
    elif local_promotions and not settings.get("auto_promote_batch_mode", False):
        # In single-mode, 1 local seed consumes the single slot — skip
        # the collection auto-promote entirely this week
        ap_settings["auto_promote_enabled"] = False
    collection_promotions = await ap.run_once(digest, ap_settings)
    promotions = local_promotions + collection_promotions

    if promotions:
        logger.info(
            "Auto-promote ran: %d promotion(s) applied (local=%d, collection=%d): %s",
            len(promotions), len(local_promotions), len(collection_promotions),
            ", ".join(f"{p['query']} → {p.get('city_slug') or p.get('collection')}" for p in promotions),
        )

    result = await send_digest_now()
    if promotions:
        result["auto_promoted"] = [
            {
                "query": p["query"],
                "collection": p.get("collection"),
                "city_slug": p.get("city_slug"),
                "scope": p.get("scope", "collection"),
                "token": p["token"],
            }
            for p in promotions
        ]
    return result

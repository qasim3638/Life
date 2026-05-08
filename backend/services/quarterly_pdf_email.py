"""
Quarterly board-deck auto-email — fires on Jan 1st / Apr 1st / Jul 1st /
Oct 1st at 09:00 Europe/London with the freshly-rendered PDF attached.

Pattern mirrors `seo_pnl_digest.py`:
  • Idempotent: stamps `quarterly_pdf_email.last_sent_quarter_label` so
    the email goes out exactly once per quarter even if the scheduler
    double-fires.
  • Skip-safe: degrades silently if no admins are connected, no GSC
    data, or no Chromium binary on the host.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from config import get_db
from services.quarterly_pdf import (
    _months_in_quarter,
    _parse_quarter,
    _quarter_of_month,
    render_quarter_pdf,
)

logger = logging.getLogger(__name__)


async def _admin_emails(db) -> list[str]:
    cursor = db.users.find(
        {"role": {"$in": ["admin", "super_admin"]}, "email": {"$ne": None}},
        {"_id": 0, "email": 1},
    )
    return [u.get("email") async for u in cursor if u.get("email")]


def _previous_quarter() -> tuple[int, int]:
    """The quarter we're reporting on — i.e. the one that JUST FINISHED.
    On April 1st we report on Q1; on July 1st we report on Q2; etc.
    """
    now = datetime.now(timezone.utc)
    q = _quarter_of_month(now.month)
    if q == 1:
        return now.year - 1, 4
    return now.year, q - 1


def _render_email_body(quarter_label: str, prev_quarter_label: str, summary: dict) -> str:
    total = float(summary.get("quarter_total_gbp") or 0)
    annual = float(summary.get("annualised_run_rate_gbp") or 0)
    months_with_data = int(summary.get("months_with_data") or 0)
    return f"""
    <div style="font-family:-apple-system,system-ui,'Segoe UI',Roboto,sans-serif;background:#0f172a;padding:32px 16px">
      <div style="max-width:600px;margin:0 auto;background:#fff;color:#0f172a;border-radius:14px;overflow:hidden;box-shadow:0 10px 40px rgba(0,0,0,0.2)">
        <div style="background:linear-gradient(135deg,#064e3b,#047857);padding:28px;color:#fff">
          <div style="font-size:11px;letter-spacing:2px;color:#a7f3d0;font-weight:600;text-transform:uppercase">Tile Station · quarterly board deck</div>
          <h1 style="margin:8px 0 4px;font-size:22px">Your {quarter_label} SEO board deck is attached</h1>
          <p style="margin:0;font-size:13px;color:#d1fae5;line-height:1.5">
            Drop the PDF straight into your Monday-morning quarterly review — everything you need on one page.
          </p>
        </div>
        <div style="padding:24px">
          <p style="font-size:14px;line-height:1.6;margin:0 0 16px">
            <strong>£{total:,.2f}</strong> saved in Google Ads spend over the {months_with_data}-month
            window — equivalent to a <strong>£{annual:,.2f}</strong> annualised run rate at current ranking momentum.
          </p>
          <div style="background:#ecfdf5;border:1px solid #d1fae5;border-radius:10px;padding:14px;font-size:13px;color:#065f46;line-height:1.6">
            The attached PDF includes the monthly trajectory, top 10 paying-the-bills keywords, and the
            full prior-quarter comparison — formatted for A4 landscape so it prints cleanly to a single page.
          </div>
          <p style="margin:18px 0 0;font-size:12px;color:#64748b">
            Sent automatically on the 1st of every quarter · Reporting period: {quarter_label} (compared against {prev_quarter_label}).
          </p>
        </div>
        <div style="background:#0f172a;color:#94a3b8;padding:14px 28px;text-align:center;font-size:11px">
          Tile Station · SEO P&amp;L automation · You can also download this PDF anytime from /admin/ads-savings
        </div>
      </div>
    </div>
    """


async def run_quarterly_pdf_email(force: bool = False, target_quarter: str | None = None) -> dict:
    """Render the previous-quarter PDF and email it to all admins.

    Args:
      force: bypass the once-per-quarter idempotency guard
      target_quarter: e.g. "Q1-2026" — overrides the auto-detected
        previous quarter, useful for back-fill / manual sends.
    """
    db = get_db()
    settings = await db.website_settings.find_one({"_id": "quarterly_pdf_email"}) or {}

    if target_quarter:
        year, q = _parse_quarter(target_quarter)
    else:
        year, q = _previous_quarter()
    quarter_label = f"Q{q}-{year}"

    if not force and settings.get("last_sent_quarter_label") == quarter_label:
        return {"ok": True, "skipped": True, "reason": "already_sent_this_quarter"}

    recipients = await _admin_emails(db)
    if not recipients:
        return {"ok": False, "skipped": True, "reason": "no_admin_recipients"}

    # Filter through the super-admin-managed authorisation table — only
    # send to admins that have been explicitly opted-in for quarterly decks.
    from services.notification_prefs import get_authorized_recipients
    authorised = set(await get_authorized_recipients("quarterly_deck"))
    recipients = [e for e in recipients if e in authorised]
    if not recipients:
        return {"ok": False, "skipped": True, "reason": "no_authorized_recipients"}

    # Render the PDF (this also computes the summary payload).
    try:
        pdf_bytes, summary = await render_quarter_pdf(year, q)
    except Exception as exc:  # noqa: BLE001
        logger.warning("quarterly PDF email — render failed: %s", exc)
        return {"ok": False, "skipped": True, "reason": f"render_failed: {exc}"}

    # Don't send a "you saved £0" deck — wait until snapshots have data.
    if not force and (summary.get("quarter_total_gbp") or 0) <= 0:
        return {"ok": True, "skipped": True, "reason": "no_data_for_quarter"}

    # Build email + attach PDF.
    prev_year, prev_q = (year - 1, 4) if q == 1 else (year, q - 1)
    prev_quarter_label = f"Q{prev_q}-{prev_year}"
    months = _months_in_quarter(year, q)

    subject = (
        f"[Tile Station] {quarter_label} SEO board deck — £{summary['quarter_total_gbp']:,.2f} saved"
    )
    html = _render_email_body(quarter_label, prev_quarter_label, summary)
    filename = f"tile-station-seo-pnl-{quarter_label}.pdf"

    from services.email import send_simple_email_if_possible
    result = await send_simple_email_if_possible(
        to=recipients,
        subject=subject,
        html=html,
        attachments=[{
            "filename": filename,
            "content": pdf_bytes,
            "content_type": "application/pdf",
        }],
    )

    if not result.get("success"):
        return {"ok": False, "error": result.get("error", "unknown email error")}

    now = datetime.now(timezone.utc)
    await db.website_settings.update_one(
        {"_id": "quarterly_pdf_email"},
        {"$set": {
            "last_sent_quarter_label": quarter_label,
            "last_sent_at": now,
            "last_payload_summary": {
                "quarter_total_gbp": summary["quarter_total_gbp"],
                "annualised_run_rate_gbp": summary["annualised_run_rate_gbp"],
                "months_in_quarter": months,
                "recipients_count": len(recipients),
                "pdf_bytes": len(pdf_bytes),
            },
        }},
        upsert=True,
    )
    return {
        "ok": True,
        "quarter": quarter_label,
        "recipients": len(recipients),
        "subject": subject,
        "pdf_bytes": len(pdf_bytes),
        "quarter_total_gbp": summary["quarter_total_gbp"],
    }

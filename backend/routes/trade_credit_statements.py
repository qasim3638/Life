"""
Monthly Trade Credit-Back Statement
-----------------------------------
A quiet, bank-statement-style email that goes out on the 1st of each month
to trade customers WHO HAD CREDIT MOVEMENT IN THE MONTH JUST CLOSED. Builds
the ritual that the trader has an asset with us — even in months they
didn't buy.

Core behaviours:
  • Aggregates `credit_transactions` for the prior calendar month per trade
    customer (`type in {earned_in_store, earned_online, redeemed_in_store,
    redeem, reverse_*}`).
  • Skips silently for any customer with zero movement (no spam).
  • Idempotent — a marker doc in `website_settings.monthly_credit_statements`
    pins the last YYYY-MM that was sent; the scheduler tick reads/writes it.
  • Admin-trigger endpoint for manual re-runs and testing.

Endpoints:
  POST /api/admin/trade-credit/statements/send-monthly  (admin-only)
       Body: {"year": 2026, "month": 4, "dry_run": false, "limit": null,
              "force": false}
       Returns: counts of (eligible / sent / skipped / failed)
  GET  /api/admin/trade-credit/statements/preview       (admin-only)
       Query: ?email=... (single trade customer preview HTML, current month)

Scheduler hook:
  `run_monthly_credit_statements_tick()` — hourly probe; fires on day 1
  at 10:00 UTC, once per month.
"""
from __future__ import annotations

import calendar
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from config import get_db
from services import get_current_user, is_admin_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/trade-credit", tags=["trade-credit-statements"])

# Movement-bucket mapping. Anything with a positive amount that isn't a
# redemption goes to "earned"; redemptions go to "redeemed".
EARNED_TYPES = {"earned_in_store", "earned_online", "manual_credit"}
REDEEMED_TYPES = {"redeemed_in_store", "redeem"}


# ---------- helpers ----------------------------------------------------------

def _month_window(year: int, month: int) -> tuple[datetime, datetime, str]:
    """Returns (start_inclusive, end_exclusive, period_label) in UTC."""
    if month < 1 or month > 12:
        raise ValueError(f"Invalid month {month}")
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    last_day = calendar.monthrange(year, month)[1]
    end = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc) + timedelta(seconds=1)
    label = start.strftime("%B %Y")
    return start, end, label


def _previous_month(now: datetime) -> tuple[int, int]:
    """Returns (year, month) for the calendar month immediately before `now`."""
    first_of_this = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_of_prev = first_of_this - timedelta(days=1)
    return last_of_prev.year, last_of_prev.month


async def _build_customer_statement(
    db, customer: dict, year: int, month: int
) -> Optional[dict]:
    """Aggregate ledger movement for one customer over a calendar month.

    Returns None if there was zero movement (caller should skip the email).
    Otherwise returns a dict ready to be passed to the email render helper.
    """
    start, end, label = _month_window(year, month)
    customer_id = customer.get("id")
    if not customer_id:
        return None

    cursor = db.credit_transactions.find(
        {
            "customer_id": customer_id,
            "created_at": {"$gte": start.isoformat(), "$lt": end.isoformat()},
        },
        {"_id": 0, "type": 1, "amount": 1, "balance_after": 1, "invoice_no": 1,
         "order_number": 1, "description": 1, "created_at": 1, "source": 1},
    ).sort("created_at", 1)
    txns = await cursor.to_list(length=500)

    if not txns:
        return None

    earned_total = 0.0
    redeemed_total = 0.0
    earn_lines: list[dict] = []
    redeem_lines: list[dict] = []
    last_balance: Optional[float] = None

    for t in txns:
        t_type = (t.get("type") or "").lower()
        amt = float(t.get("amount") or 0)
        bal = t.get("balance_after")
        if bal is not None:
            last_balance = float(bal)
        if t_type in EARNED_TYPES and amt > 0:
            earned_total += amt
            earn_lines.append(t)
        elif t_type in REDEEMED_TYPES:
            # redeem amounts are negative in the ledger, but we display as positive
            redeemed_total += abs(amt)
            redeem_lines.append(t)
        # other / reverse_* types are ignored for the headline summary

    # Final balance — prefer the live customer record (newest), else last txn's balance_after, else 0
    closing_balance = (
        float(customer.get("credit_balance") or 0)
        if customer.get("credit_balance") is not None
        else (last_balance if last_balance is not None else 0.0)
    )

    return {
        "customer_id": customer_id,
        "customer_email": customer.get("email"),
        "customer_name": customer.get("name") or customer.get("business_name") or "there",
        "business_name": customer.get("business_name") or "",
        "trade_account_number": customer.get("trade_account_number") or "",
        "period_label": label,
        "year": year,
        "month": month,
        "earned_total": round(earned_total, 2),
        "redeemed_total": round(redeemed_total, 2),
        "closing_balance": round(closing_balance, 2),
        "txns_count": len(txns),
        "earn_lines": earn_lines[:5],
        "redeem_lines": redeem_lines[:5],
    }


# ---------- HTML render ------------------------------------------------------

def _format_gbp(v: float) -> str:
    return f"£{float(v or 0):.2f}"


def render_monthly_statement_html(stmt: dict) -> str:
    company_website = os.environ.get("COMPANY_WEBSITE") or os.environ.get("SHOP_WEBSITE_URL") or "https://tilestation.co.uk"
    first_name = (stmt.get("customer_name") or "there").split(" ")[0]
    period = stmt["period_label"]
    earned = stmt["earned_total"]
    redeemed = stmt["redeemed_total"]
    balance = stmt["closing_balance"]
    t_ref = stmt.get("trade_account_number") or ""
    spend_url = f"{company_website}/shop/trade/account"

    # Compose mini-statement rows
    def _row(label: str, value: str, color: str = "#1a1a2e", bold: bool = False) -> str:
        weight = "700" if bold else "500"
        return (
            f'<tr><td style="padding:10px 0; color:#525252; font-size:14px;">{label}</td>'
            f'<td style="padding:10px 0; text-align:right; color:{color}; font-size:15px; font-weight:{weight}; font-family:ui-monospace,SFMono-Regular,monospace;">{value}</td></tr>'
        )

    summary_rows = ""
    if earned > 0:
        summary_rows += _row("Credit earned this month", f"+ {_format_gbp(earned)}", color="#047857", bold=True)
    if redeemed > 0:
        summary_rows += _row("Credit redeemed this month", f"– {_format_gbp(redeemed)}", color="#9f1239", bold=True)
    summary_rows += (
        '<tr><td colspan="2" style="padding:6px 0;"><div style="height:1px; background:#e5e7eb;"></div></td></tr>'
    )
    summary_rows += _row("Closing balance", _format_gbp(balance), color="#1a1a2e", bold=True)

    # Recent activity (max 5 of each)
    def _txn_table(rows: list[dict], heading: str, sign: str, color: str) -> str:
        if not rows:
            return ""
        body = ""
        for t in rows:
            try:
                d = datetime.fromisoformat(str(t.get("created_at") or "").replace("Z", "+00:00")).strftime("%d %b")
            except Exception:
                d = ""
            ref = t.get("invoice_no") or t.get("order_number") or ""
            descr = (t.get("description") or "").strip()
            short = ref or (descr[:50] + ("…" if len(descr) > 50 else ""))
            body += (
                f'<tr><td style="padding:6px 8px; color:#737373; font-size:12px; white-space:nowrap;">{d}</td>'
                f'<td style="padding:6px 8px; color:#1a1a2e; font-size:12px;">{short}</td>'
                f'<td style="padding:6px 8px; text-align:right; color:{color}; font-size:12px; font-family:ui-monospace,monospace; white-space:nowrap;">{sign}{_format_gbp(abs(float(t.get("amount") or 0)))}</td></tr>'
            )
        return (
            f'<div style="margin-top:18px;">'
            f'<div style="font-size:11px; font-weight:700; letter-spacing:0.08em; text-transform:uppercase; color:#737373; margin-bottom:6px;">{heading}</div>'
            f'<table role="presentation" style="width:100%; border-collapse:collapse; background:#fafaf9; border:1px solid #e7e5e4; border-radius:8px;">{body}</table>'
            f'</div>'
        )

    earn_html = _txn_table(stmt.get("earn_lines") or [], "Earned", "+ ", "#047857")
    redeem_html = _txn_table(stmt.get("redeem_lines") or [], "Redeemed", "– ", "#9f1239")

    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; max-width: 620px; margin: 0 auto; color: #1a1a2e; background: #f9fafb;">
      <div style="background:#1C1917; padding:20px 24px;">
        <h1 style="color:#F7EA1C; margin:0; font-size:22px; letter-spacing:-0.3px;">Tile Station</h1>
        <p style="color:#a8a29e; margin:4px 0 0; font-size:12px;">Trade Credit Statement — {period}</p>
      </div>

      <div style="background:#fff; padding:28px 24px;">
        <p style="margin:0 0 16px 0; font-size:15px; color:#1a1a2e;">Hi {first_name},</p>
        <p style="margin:0 0 22px 0; font-size:14px; line-height:1.55; color:#525252;">
          Here's your trade-credit statement for <strong>{period}</strong>{f' on account {t_ref}' if t_ref else ''}.
        </p>

        <div style="background:#fafaf9; border:1px solid #e7e5e4; border-radius:12px; padding:16px 20px;">
          <table role="presentation" style="width:100%; border-collapse:collapse;">{summary_rows}</table>
        </div>

        {earn_html}
        {redeem_html}

        {'<p style="margin:28px 0 0; text-align:center;"><a href="' + spend_url + '" style="display:inline-block; background:#1a1a2e; color:#f0c14b; padding:14px 28px; border-radius:8px; text-decoration:none; font-weight:700; font-size:14px;">View my trade account →</a></p>' if balance > 0 else ''}

        <p style="margin:32px 0 0; font-size:12px; color:#a8a29e; line-height:1.55;">
          Your credit sits on your account ready to redeem against any future purchase — in store or online.
          Statements arrive on the 1st of each month, and only when there's been activity.
          Any questions, just reply to this email.
        </p>
      </div>

      <div style="text-align:center; padding:14px 24px; color:#a8a29e; font-size:11px;">
        Tile Station · Unit 3 Trade City, Coldharbour Road, Northfleet, Gravesend DA11 8AB<br/>
        Company No: 11982550 · VAT No: 324 251 828
      </div>
    </div>
    """


# ---------- send -------------------------------------------------------------

async def _send_one_statement(stmt: dict) -> dict:
    """Sends one statement via Resend. Returns {sent: bool, error: str|None}."""
    if not stmt.get("customer_email"):
        return {"sent": False, "error": "no_email"}
    try:
        # Lazy import to avoid pulling Resend SDK when not configured
        import resend
        from services.email import RESEND_AVAILABLE, RESEND_API_KEY, COMPANY_NAME
    except Exception as exc:  # noqa: BLE001
        return {"sent": False, "error": f"import:{exc}"}
    if not RESEND_AVAILABLE or not RESEND_API_KEY:
        return {"sent": False, "error": "resend_not_configured"}

    html = render_monthly_statement_html(stmt)
    subject = f"Your trade credit statement — {stmt['period_label']}"
    sender = os.environ.get("SENDER_EMAIL", "online@tilestation.co.uk")
    try:
        import asyncio as _asyncio
        resend.api_key = RESEND_API_KEY
        await _asyncio.to_thread(resend.Emails.send, {
            "from": f"{COMPANY_NAME} - Tile Station <{sender}>",
            "to": [stmt["customer_email"]],
            "reply_to": "online@tilestation.co.uk",
            "subject": subject,
            "html": html,
        })
        return {"sent": True, "error": None}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Monthly statement email failed for %s: %s", stmt.get("customer_email"), exc)
        return {"sent": False, "error": str(exc)[:200]}


# ---------- core dispatch loop ----------------------------------------------

async def dispatch_monthly_statements(
    db, year: int, month: int, *, dry_run: bool = False, limit: Optional[int] = None
) -> dict:
    """Iterate trade customers; build per-customer statement; send if movement.

    Returns a summary {eligible, sent, skipped_no_movement, failed, errors}.
    """
    start, end, label = _month_window(year, month)

    # Pull only customers who have a credit_transaction in the window — this
    # is the cheapest way to find candidates and skips dormant accounts entirely.
    candidate_ids = await db.credit_transactions.distinct(
        "customer_id",
        {"created_at": {"$gte": start.isoformat(), "$lt": end.isoformat()}},
    )

    eligible = 0
    sent = 0
    skipped = 0
    failed = 0
    errors: list[dict] = []

    if not candidate_ids:
        return {
            "eligible": 0, "sent": 0, "skipped_no_movement": 0, "failed": 0,
            "errors": [], "period_label": label, "year": year, "month": month, "dry_run": dry_run,
        }

    # Process in batches of 50 to keep memory steady
    batch = 50
    for i in range(0, len(candidate_ids), batch):
        ids = [cid for cid in candidate_ids[i : i + batch] if cid]
        if not ids:
            continue
        custs = await db.shop_customers.find(
            {"id": {"$in": ids}, "is_trade": True, "email": {"$ne": None}},
            {"_id": 0, "id": 1, "email": 1, "name": 1, "business_name": 1,
             "trade_account_number": 1, "credit_balance": 1, "is_trade": 1},
        ).to_list(length=batch)
        for cust in custs:
            if limit is not None and sent + skipped + failed >= limit:
                break
            eligible += 1
            stmt = await _build_customer_statement(db, cust, year, month)
            if not stmt:
                skipped += 1
                continue
            if dry_run:
                sent += 1
                continue
            res = await _send_one_statement(stmt)
            if res.get("sent"):
                sent += 1
            else:
                failed += 1
                errors.append({"email": cust.get("email"), "error": res.get("error")})

    return {
        "eligible": eligible,
        "sent": sent,
        "skipped_no_movement": skipped,
        "failed": failed,
        "errors": errors[:25],  # cap so the response stays small
        "period_label": label,
        "year": year,
        "month": month,
        "dry_run": dry_run,
    }


# ---------- scheduler tick ---------------------------------------------------

async def run_monthly_credit_statements_tick():
    """Hourly probe — fires the dispatch only on day 1 of each month at the
    configured UTC hour (default 10:00). Idempotent via marker doc."""
    db = get_db()
    now = datetime.now(timezone.utc)
    settings = await db.website_settings.find_one({"_id": "monthly_credit_statements"}) or {}
    if not settings.get("enabled", True):
        return
    target_hour = int(settings.get("hour_utc", 10))
    if now.day != 1 or now.hour != target_hour:
        return
    period_key = now.strftime("%Y-%m")  # the month we're STARTING — so we send the prior month's
    if settings.get("last_period") == period_key:
        return  # already sent for this run

    py, pm = _previous_month(now)
    result = await dispatch_monthly_statements(db, py, pm)

    await db.website_settings.update_one(
        {"_id": "monthly_credit_statements"},
        {"$set": {
            "last_period": period_key,
            "last_run_at": now.isoformat(),
            "last_result": result,
            "hour_utc": target_hour,
            "enabled": settings.get("enabled", True),
        }},
        upsert=True,
    )
    logger.info(
        "[monthly-credit-statements] period=%s eligible=%s sent=%s skipped=%s failed=%s",
        result.get("period_label"), result.get("eligible"),
        result.get("sent"), result.get("skipped_no_movement"), result.get("failed"),
    )


# ---------- API endpoints ----------------------------------------------------

class MonthlyDispatchInput(BaseModel):
    year: int = Field(..., ge=2024, le=2100)
    month: int = Field(..., ge=1, le=12)
    dry_run: bool = False
    limit: Optional[int] = Field(default=None, ge=1, le=10000)
    force: bool = False  # Bypass duplicate-period guard for re-runs


@router.post("/statements/send-monthly")
async def admin_send_monthly_statements(
    body: MonthlyDispatchInput,
    current_user: dict = Depends(get_current_user),
):
    """Admin-trigger the monthly statement run. Useful for manual re-runs and
    catching up if the cron probe missed a window."""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    db = get_db()
    period_key = f"{body.year:04d}-{(body.month % 12 + 1):02d}"  # the run-month following body's window
    settings = await db.website_settings.find_one({"_id": "monthly_credit_statements"}) or {}
    if not body.force and settings.get("last_period") == period_key and not body.dry_run:
        raise HTTPException(
            status_code=409,
            detail=f"Statements for {body.year}-{body.month:02d} already dispatched. Pass force=true to re-run.",
        )
    result = await dispatch_monthly_statements(
        db, body.year, body.month, dry_run=body.dry_run, limit=body.limit,
    )
    if not body.dry_run:
        await db.website_settings.update_one(
            {"_id": "monthly_credit_statements"},
            {"$set": {
                "last_period": period_key,
                "last_run_at": datetime.now(timezone.utc).isoformat(),
                "last_run_by": current_user.get("email"),
                "last_result": result,
            }},
            upsert=True,
        )
    return result


@router.get("/statements/preview")
async def admin_preview_monthly_statement(
    email: str = Query(..., description="Trade customer email"),
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    """Return the rendered HTML preview for a single trade customer for the
    specified month (defaults to the previous calendar month)."""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    db = get_db()
    cust = await db.shop_customers.find_one(
        {"email": email.lower().strip()},
        {"_id": 0, "id": 1, "email": 1, "name": 1, "business_name": 1,
         "trade_account_number": 1, "credit_balance": 1, "is_trade": 1},
    )
    if not cust or not cust.get("is_trade"):
        raise HTTPException(status_code=404, detail="Trade customer not found for that email.")
    if not year or not month:
        py, pm = _previous_month(datetime.now(timezone.utc))
        year, month = py, pm
    stmt = await _build_customer_statement(db, cust, year, month)
    if not stmt:
        return {
            "has_movement": False,
            "period_label": _month_window(year, month)[2],
            "html": "",
            "message": "No credit movement in this month — statement would not be sent.",
        }
    return {
        "has_movement": True,
        "period_label": stmt["period_label"],
        "summary": {
            "earned_total": stmt["earned_total"],
            "redeemed_total": stmt["redeemed_total"],
            "closing_balance": stmt["closing_balance"],
            "txns_count": stmt["txns_count"],
        },
        "html": render_monthly_statement_html(stmt),
    }


@router.get("/statements/last-run")
async def admin_last_run_status(current_user: dict = Depends(get_current_user)):
    """Read the marker doc so admins can see when the last batch went out."""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    db = get_db()
    doc = await db.website_settings.find_one({"_id": "monthly_credit_statements"}, {"_id": 0})
    return doc or {"enabled": True, "hour_utc": 10, "last_period": None, "last_run_at": None}


class SendOneInput(BaseModel):
    email: str = Field(..., min_length=3)
    year: Optional[int] = Field(default=None, ge=2024, le=2100)
    month: Optional[int] = Field(default=None, ge=1, le=12)


@router.post("/statements/send-one")
async def admin_send_one_statement(
    body: SendOneInput,
    current_user: dict = Depends(get_current_user),
):
    """On-demand send for a single trade customer (e.g. when the trader is on
    the phone). Looks up the customer, builds the statement for the requested
    month (defaults to previous calendar month), and dispatches via Resend.
    Returns 400 if there's no movement to send."""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    db = get_db()
    cust = await db.shop_customers.find_one(
        {"email": body.email.lower().strip()},
        {"_id": 0, "id": 1, "email": 1, "name": 1, "business_name": 1,
         "trade_account_number": 1, "credit_balance": 1, "is_trade": 1},
    )
    if not cust or not cust.get("is_trade"):
        raise HTTPException(status_code=404, detail="Trade customer not found for that email.")

    year, month = body.year, body.month
    if not year or not month:
        py, pm = _previous_month(datetime.now(timezone.utc))
        year, month = py, pm

    stmt = await _build_customer_statement(db, cust, year, month)
    if not stmt:
        raise HTTPException(
            status_code=400,
            detail=f"No credit movement in {_month_window(year, month)[2]} — nothing to send.",
        )
    res = await _send_one_statement(stmt)
    if not res.get("sent"):
        raise HTTPException(
            status_code=502,
            detail=f"Email dispatch failed: {res.get('error') or 'unknown error'}",
        )
    # Audit trail — admin override of the cron schedule
    await db.credit_statement_sends.insert_one({
        "customer_id": cust.get("id"),
        "customer_email": cust.get("email"),
        "period_label": stmt["period_label"],
        "year": year,
        "month": month,
        "earned_total": stmt["earned_total"],
        "redeemed_total": stmt["redeemed_total"],
        "closing_balance": stmt["closing_balance"],
        "sent_by": current_user.get("email"),
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "trigger": "admin_on_demand",
    })
    return {
        "sent": True,
        "customer_email": cust.get("email"),
        "period_label": stmt["period_label"],
        "summary": {
            "earned_total": stmt["earned_total"],
            "redeemed_total": stmt["redeemed_total"],
            "closing_balance": stmt["closing_balance"],
        },
    }

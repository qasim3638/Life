"""
Admin failed-payments dashboard.

Surfaces every order Stripe has reported as a failed payment over a
rolling window, lets the admin see at a glance:

  • how many declines came in (and what they totalled)
  • the top decline reasons (so you can spot a pattern — e.g. lots of
    insufficient_funds → offer Klarna; lots of card_declined →
    pre-auth issue with the gateway)
  • each individual decline with the customer's contact details and
    a recovery-status badge (recovered / pending / abandoned)

All data is already persisted on `shop_orders` rows by:
  • the failed-payment Stripe webhook branch (sets payment_failed_at,
    payment_failed_reason, payment_failed_code, payment_status='failed')
  • the payment-recovery service (sets recovery_email_sent_at,
    recovery_token_expires_at)
  • the success path (sets payment_status='paid', paid_at)

Recovery-status decision (in priority order):
  • "recovered" — payment_status='paid' AND paid_at > payment_failed_at
  • "pending"   — recovery_email_sent_at within RECOVERY_WINDOW_DAYS
                  (still has time to click the link)
  • "abandoned" — recovery email sent or window expired and still unpaid
"""
from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from config import get_db
from services import get_current_user
from services.payment_recovery import RECOVERY_WINDOW_DAYS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/failed-payments", tags=["Admin · Failed Payments"])


def _is_admin(u: dict) -> bool:
    """Same gate the rest of the admin SEO routes use."""
    role = (u or {}).get("role")
    return role in ("admin", "super_admin", "manager")


def _parse_dt(value) -> Optional[datetime]:
    """Tolerate the mix of ISO strings and aware datetimes we have on
    shop_orders (created_at is ISO string, paid_at can be either)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:  # noqa: BLE001
            return None
    return None


def _recovery_status(row: dict, now_utc: datetime) -> str:
    """Pure helper. Decide which badge a row gets in the admin UI."""
    failed_at = _parse_dt(row.get("payment_failed_at"))
    paid_at = _parse_dt(row.get("paid_at"))
    if (
        row.get("payment_status") == "paid"
        and paid_at and failed_at
        and paid_at > failed_at
    ):
        return "recovered"
    if row.get("recovery_email_sent_at"):
        sent_at = _parse_dt(row["recovery_email_sent_at"])
        if sent_at and (now_utc - sent_at).days < RECOVERY_WINDOW_DAYS:
            return "pending"
    return "abandoned"


@router.get("")
async def list_failed_payments(
    current_user: dict = Depends(get_current_user),
    days: int = Query(default=30, ge=1, le=180),
    status: Optional[str] = Query(
        default=None,
        pattern="^(recovered|pending|abandoned)$",
    ),
):
    """Return the failed-payment dashboard payload.

    Response shape:
      {
        "window_days": int,
        "since": iso,
        "totals": {
          "count": int,
          "amount": float,           # sum of order.total across all declines
          "recovered_count": int,
          "pending_count": int,
          "abandoned_count": int,
          "recovered_amount": float, # how much we won back
        },
        "top_decline_codes": [(code, count), ...]  # top 6
        "rows": [{ ... per-order summary ... }]
      }
    """
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")

    db = get_db()
    now_utc = datetime.now(timezone.utc)
    since = now_utc - timedelta(days=days)

    # Stripe webhook stamps payment_failed_at as ISO string. Mongo's
    # comparison on ISO strings sorts lexicographically the same as
    # chronologically because the format is fixed, so $gte string works.
    cursor = db.shop_orders.find(
        {"payment_failed_at": {"$gte": since.isoformat()}},
        {
            "_id": 0,
            "id": 1, "order_number": 1, "total": 1,
            "customer_email": 1, "customer_name": 1, "customer_phone": 1,
            "payment_status": 1, "payment_failed_at": 1, "paid_at": 1,
            "payment_failed_reason": 1, "payment_failed_code": 1,
            "recovery_email_sent_at": 1, "recovery_token_expires_at": 1,
        },
    ).sort("payment_failed_at", -1).limit(500)

    raw_rows = await cursor.to_list(500)
    rows = []
    code_counter: Counter = Counter()
    recovered_count = pending_count = abandoned_count = 0
    total_amount = 0.0
    recovered_amount = 0.0

    for r in raw_rows:
        st = _recovery_status(r, now_utc)
        if status and st != status:
            # In-memory filter so the totals row above remains accurate
            # for the FULL window even when the admin narrows the table.
            continue
        amount = float(r.get("total") or 0)
        code = (r.get("payment_failed_code") or "unknown")[:32]
        rows.append({
            "id": r.get("id"),
            "order_number": r.get("order_number"),
            "customer_name": r.get("customer_name"),
            "customer_email": r.get("customer_email"),
            "customer_phone": r.get("customer_phone"),
            "total": amount,
            "payment_failed_at": r.get("payment_failed_at"),
            "payment_failed_code": code,
            "payment_failed_reason": (r.get("payment_failed_reason") or "")[:200],
            "recovery_email_sent_at": r.get("recovery_email_sent_at"),
            "recovery_status": st,
            "paid_at": r.get("paid_at"),
        })

    # Aggregate totals over the *unfiltered* window so the dashboard
    # cards don't change when the admin clicks a status filter chip.
    for r in raw_rows:
        st = _recovery_status(r, now_utc)
        amount = float(r.get("total") or 0)
        total_amount += amount
        code_counter[(r.get("payment_failed_code") or "unknown")[:32]] += 1
        if st == "recovered":
            recovered_count += 1
            recovered_amount += amount
        elif st == "pending":
            pending_count += 1
        else:
            abandoned_count += 1

    return {
        "window_days": days,
        "since": since.isoformat(),
        "totals": {
            "count": len(raw_rows),
            "amount": round(total_amount, 2),
            "recovered_count": recovered_count,
            "pending_count": pending_count,
            "abandoned_count": abandoned_count,
            "recovered_amount": round(recovered_amount, 2),
            "recovery_rate_pct": (
                round(100 * recovered_count / len(raw_rows), 1)
                if raw_rows else 0.0
            ),
        },
        "top_decline_codes": code_counter.most_common(6),
        "rows": rows,
    }

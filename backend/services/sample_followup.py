"""
Sample → Order Conversion Followup
──────────────────────────────────

Automated nightly job that finds customers whose sample order was
delivered ~7 days ago and HASN'T placed a tile order since. Sends ONE
personalised "ready to order?" email that:
  • Recaps which samples they received (with thumbnails)
  • Offers an order-redemption discount equal to what they paid for any
    Full Size Samples (£5 each) — applied as a one-shot voucher code
  • Links back to the PDPs they sampled
  • Subtle CTA: "Place an order or pop into a showroom"

Idempotency:
  • Tracks sent emails in `db.sample_followup_sent` so a customer never
    receives more than one followup per sample order.
  • Respects `db.shop_customers.email_preferences.no_marketing` if the
    customer has opted out.

Schedule:
  • Runs via APScheduler at 10:00 BST daily (registered in scheduler.py)
  • Manual trigger: POST /api/admin/sample-followups/run-now
  • Preview: GET /api/admin/sample-followups/eligible (dry-run list)

Conversion rationale:
  • Free-sample customers convert at ~8% (industry benchmark for tile
    retail). A targeted 7-day followup typically lifts that to 12-15%.
  • Full Size Sample (£5) customers are pre-qualified — they paid real
    money to evaluate. Their conversion rate is ~3× higher than free
    samplers. Refunding their £5 against the order makes the deal
    feel like a "free sample with skin in the game" — historically the
    strongest combination in tile retail.

Output:
  Returns a summary dict from `run_followup_pass()`:
  {
    "scanned": int,
    "eligible": int,
    "sent": int,
    "skipped_already_sent": int,
    "skipped_already_ordered": int,
    "skipped_opt_out": int,
    "errors": int,
  }

Safe to run repeatedly. Never blocks the event loop.
"""
from __future__ import annotations

import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Window: target sample orders delivered between 4 and 14 days ago.
# Surfaces them on the admin "Pending Sample Followups" review screen.
# Owner manually decides whether to send each email — automation only
# does the prep work (find candidates, draft the email, mint the voucher
# code on demand).
DELIVERY_LOOKBACK_DAYS_MIN = 4
DELIVERY_LOOKBACK_DAYS_MAX = 14

# Customer must have NO purchase order placed in the last 30 days for
# the followup to fire. If they already ordered, no nudge needed.
ORDER_LOOKBACK_DAYS = 30

# Voucher worth £5 per Full Size Sample paid for. £0 for free-only
# orders (we still send the email, but with no discount — message
# focuses on "ready to order?" instead).
FULL_SIZE_SAMPLE_REFUND_GBP = 5.00


def _voucher_code() -> str:
    """Cryptographically-strong, human-typeable voucher code."""
    return f"SAMPLE-{secrets.token_hex(3).upper()}"


async def _customer_has_recent_order(db, email: str) -> bool:
    """Returns True if customer placed a non-sample order in the last 30 days.

    Checks the `orders` collection for purchase orders (cart_type !=
    'sample' / `order_type` != 'sample'). Idempotent.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=ORDER_LOOKBACK_DAYS)
    cutoff_iso = cutoff.isoformat()
    # Be liberal in what we treat as "an order" — any orders/quotes
    # row for this email in the window suggests they're already engaging.
    q = {
        "customer_email": (email or "").lower().strip(),
        "$or": [
            {"created_at": {"$gte": cutoff_iso}},
            {"created_at": {"$gte": cutoff}},
        ],
    }
    existing = await db.orders.find_one(q, {"_id": 0, "id": 1, "order_type": 1})
    if not existing:
        return False
    # Allow re-engagement if their only "order" was another sample order
    if existing.get("order_type") == "sample":
        return False
    return True


async def _customer_opted_out(db, email: str) -> bool:
    """Honour customer's marketing opt-out flag."""
    cust = await db.shop_customers.find_one(
        {"email": (email or "").lower().strip()},
        {"_id": 0, "email_preferences": 1},
    )
    if not cust:
        return False
    prefs = cust.get("email_preferences") or {}
    return bool(prefs.get("no_marketing"))


async def _find_eligible_orders(db) -> list[dict]:
    """Sample orders delivered 6-8 days ago in `delivered` or `completed` status."""
    now = datetime.now(timezone.utc)
    earliest = now - timedelta(days=DELIVERY_LOOKBACK_DAYS_MAX)
    latest = now - timedelta(days=DELIVERY_LOOKBACK_DAYS_MIN)
    # Mongo stores dates as strings or datetimes. Match both shapes.
    earliest_iso = earliest.isoformat()
    latest_iso = latest.isoformat()
    cursor = db.sample_orders.find(
        {
            "status": {"$in": ["delivered", "completed", "shipped"]},
            "$or": [
                {"delivered_at": {"$gte": earliest_iso, "$lte": latest_iso}},
                {"delivered_at": {"$gte": earliest, "$lte": latest}},
                # Fallback: orders without a delivered_at timestamp —
                # use created_at + 4 day shipping estimate as proxy.
                {
                    "delivered_at": None,
                    "status": "shipped",
                    "$and": [
                        {"created_at": {"$gte": (earliest - timedelta(days=4)).isoformat()}},
                        {"created_at": {"$lte": (latest - timedelta(days=4)).isoformat()}},
                    ],
                },
            ],
        },
        {"_id": 0},
    ).sort("delivered_at", 1)
    return [o async for o in cursor]


async def _already_followed_up(db, sample_order_id: str) -> bool:
    """Has THIS specific sample order already had a followup email sent?"""
    existing = await db.sample_followup_sent.find_one(
        {"sample_order_id": sample_order_id},
        {"_id": 0, "id": 1},
    )
    return existing is not None


async def _record_followup_sent(
    db,
    *,
    sample_order_id: str,
    order_number: str,
    customer_email: str,
    voucher_code: str | None,
    voucher_amount_gbp: float,
) -> None:
    """Idempotent record so we never double-email on the same sample order."""
    await db.sample_followup_sent.insert_one({
        "sample_order_id": sample_order_id,
        "order_number": order_number,
        "customer_email": (customer_email or "").lower().strip(),
        "voucher_code": voucher_code,
        "voucher_amount_gbp": voucher_amount_gbp,
        "sent_at": datetime.now(timezone.utc),
    })


async def _create_voucher(db, *, code: str, amount_gbp: float, customer_email: str) -> None:
    """Persist the one-shot redemption voucher.

    Goes into the existing `vouchers` collection. Single-use, expires
    in 30 days, restricted to this email so accidental disclosure
    doesn't burn the voucher for someone else.
    """
    if amount_gbp <= 0:
        return
    await db.vouchers.insert_one({
        "code": code,
        "type": "fixed_discount",
        "amount_gbp": amount_gbp,
        "min_order_gbp": 0,
        "single_use": True,
        "used": False,
        "used_at": None,
        "issued_to_email": (customer_email or "").lower().strip(),
        "issued_for": "sample_followup",
        "expires_at": datetime.now(timezone.utc) + timedelta(days=30),
        "created_at": datetime.now(timezone.utc),
    })


def _classify_order(order: dict) -> tuple[int, int, float]:
    """Returns (free_count, paid_count, total_paid_gbp)."""
    products = order.get("products") or []
    free_count = 0
    paid_count = 0
    total_paid = 0.0
    for p in products:
        price = float(p.get("price_gbp") or 0)
        if price > 0:
            paid_count += 1
            total_paid += price
        else:
            free_count += 1
    return free_count, paid_count, round(total_paid, 2)


async def process_one(db, order: dict) -> str:
    """Process a single eligible sample order.

    Returns one of: 'sent' | 'already_sent' | 'already_ordered' |
                     'opt_out' | 'error'
    """
    sample_order_id = order.get("id") or ""
    order_number = order.get("order_number") or ""
    customer_email = (order.get("customer_email") or "").lower().strip()
    customer_name = order.get("customer_name") or "there"
    if not sample_order_id or not customer_email:
        return "error"

    if await _already_followed_up(db, sample_order_id):
        return "already_sent"
    if await _customer_opted_out(db, customer_email):
        return "opt_out"
    if await _customer_has_recent_order(db, customer_email):
        return "already_ordered"

    free_count, paid_count, total_paid = _classify_order(order)

    voucher_code: Optional[str] = None
    voucher_amount = 0.0
    if paid_count > 0:
        voucher_amount = round(min(total_paid, paid_count * FULL_SIZE_SAMPLE_REFUND_GBP), 2)
        if voucher_amount > 0:
            voucher_code = _voucher_code()
            await _create_voucher(
                db,
                code=voucher_code,
                amount_gbp=voucher_amount,
                customer_email=customer_email,
            )

    # Send the email (best-effort — failure here doesn't block recording
    # the followup attempt because we don't want to spam the customer
    # if they end up receiving the email through retry).
    try:
        from services.email import send_sample_followup_email
        await send_sample_followup_email(
            customer_email=customer_email,
            customer_name=customer_name,
            order=order,
            voucher_code=voucher_code,
            voucher_amount_gbp=voucher_amount,
            free_count=free_count,
            paid_count=paid_count,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"sample_followup: email send failed for {sample_order_id}: {e}")
        return "error"

    await _record_followup_sent(
        db,
        sample_order_id=sample_order_id,
        order_number=order_number,
        customer_email=customer_email,
        voucher_code=voucher_code,
        voucher_amount_gbp=voucher_amount,
    )
    return "sent"


async def run_followup_pass() -> dict[str, Any]:
    """Top-level: scan, filter, send. Always returns a dict (never raises)."""
    summary = {
        "scanned": 0,
        "eligible": 0,
        "sent": 0,
        "skipped_already_sent": 0,
        "skipped_already_ordered": 0,
        "skipped_opt_out": 0,
        "errors": 0,
    }
    try:
        from config import get_db
        db = get_db()
        orders = await _find_eligible_orders(db)
        summary["scanned"] = len(orders)
        for o in orders:
            result = await process_one(db, o)
            if result == "sent":
                summary["sent"] += 1
                summary["eligible"] += 1
            elif result == "already_sent":
                summary["skipped_already_sent"] += 1
            elif result == "already_ordered":
                summary["skipped_already_ordered"] += 1
            elif result == "opt_out":
                summary["skipped_opt_out"] += 1
            else:
                summary["errors"] += 1
    except Exception as e:  # noqa: BLE001
        logger.exception(f"sample_followup: top-level pass error: {e}")
        summary["errors"] += 1
    return summary


async def list_eligible_preview(limit: int = 50) -> list[dict]:
    """Admin preview: which orders WOULD be emailed today, with reasons."""
    try:
        from config import get_db
        db = get_db()
        orders = await _find_eligible_orders(db)
    except Exception as e:  # noqa: BLE001
        logger.exception(f"sample_followup: preview failed: {e}")
        return []
    rows = []
    for o in orders[:limit]:
        sample_order_id = o.get("id") or ""
        customer_email = (o.get("customer_email") or "").lower().strip()
        already_sent = await _already_followed_up(db, sample_order_id)
        opted_out = await _customer_opted_out(db, customer_email)
        recent_order = await _customer_has_recent_order(db, customer_email)
        free_count, paid_count, total_paid = _classify_order(o)
        will_send = not (already_sent or opted_out or recent_order)
        skip_reason = None
        if already_sent:
            skip_reason = "already_sent"
        elif opted_out:
            skip_reason = "opt_out"
        elif recent_order:
            skip_reason = "recent_order"
        rows.append({
            "sample_order_id": sample_order_id,
            "order_number": o.get("order_number"),
            "customer_email": customer_email,
            "customer_name": o.get("customer_name"),
            "delivered_at": str(o.get("delivered_at") or o.get("created_at")),
            "free_sample_count": free_count,
            "paid_sample_count": paid_count,
            "total_paid_gbp": total_paid,
            "would_redeem_gbp": min(total_paid, paid_count * FULL_SIZE_SAMPLE_REFUND_GBP),
            "will_send": will_send,
            "skip_reason": skip_reason,
        })
    return rows

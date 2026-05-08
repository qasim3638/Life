"""
Payment-recovery email + recovery-link.

When a customer's card declines mid-checkout, Stripe gives us:
  • last_payment_error.message  — the human-readable reason
  • The original PaymentIntent / Checkout Session
  • The order metadata.order_id we set during checkout

This service sends a friendly "we noticed your payment didn't go
through — here's a one-click link to try again with the same cart"
email within 60 seconds of the decline. Stacks with the human phone
call (Telegram alert side) for compounded recovery.

Recovery-link mechanics
-----------------------
We mint a short-lived `recovery_token` (uuid4, 96-bit random) and store
it on the `shop_orders` row. The customer-facing link is:

    {SHOP_WEBSITE_URL}/checkout/recover/{token}

The frontend route hits `GET /api/shop/checkout/recover/{token}` which:
  1. Looks up the order by recovery_token.
  2. Verifies it's still within the recovery window (default 7 days).
  3. Restores the customer's cart from order.items.
  4. Returns the order_id + items so the storefront can navigate the
     customer back to the checkout page with everything pre-filled.

Why a token instead of just order_id? Because order_id is leakable from
the failed-payment Telegram alert — anyone who saw the alert could
otherwise visit the URL and see the customer's cart.

Idempotency
-----------
Each order can only have ONE recovery email sent. After sending we
stamp `recovery_email_sent_at` + the token. Re-running the webhook (or
manually triggering the recovery email a second time) is a no-op.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# Window during which a recovery link remains valid. After 7 days the
# customer's card details are likely stale anyway and the cart pricing
# may have drifted, so we expire and force them to start fresh.
RECOVERY_WINDOW_DAYS = 7


def _shop_url() -> str:
    return (
        os.environ.get("SHOP_WEBSITE_URL")
        or os.environ.get("ADMIN_BASE_URL")
        or "https://tilestation.co.uk"
    ).rstrip("/")


def _render_html(*, customer_name: str, recovery_url: str, total: float,
                 decline_message: str, items_count: int) -> str:
    safe_msg = (decline_message or "").strip()[:200] or "Your card was declined."
    return f"""
    <div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:560px;margin:0 auto;color:#0f172a;line-height:1.55">
      <div style="background:#1a1a2e;color:#fff;padding:22px 26px">
        <div style="font-size:13px;letter-spacing:.18em;color:#f0c14b;font-weight:700">TILE STATION</div>
        <h1 style="margin:6px 0 0;font-size:22px">We noticed your payment didn't go through</h1>
      </div>
      <div style="padding:24px 26px;background:#fff;border:1px solid #e2e8f0;border-top:0">
        <p>Hi {customer_name},</p>
        <p>We tried to take payment for your Tile Station order
        (<strong>£{total:.2f}</strong> · {items_count} item{'s' if items_count != 1 else ''})
        but the bank declined it:</p>
        <div style="background:#fef2f2;border-left:3px solid #dc2626;padding:10px 14px;border-radius:4px;color:#7f1d1d;font-size:14px;margin:16px 0">
          {safe_msg}
        </div>
        <p>Your basket is still saved exactly as you left it. Click the
        button below to pick up where you left off — no need to re-add
        anything or start over.</p>
        <div style="text-align:center;margin:26px 0">
          <a href="{recovery_url}"
             style="display:inline-block;background:#059669;color:#fff;text-decoration:none;
                    padding:13px 28px;border-radius:8px;font-weight:600;font-size:15px">
            Try payment again →
          </a>
        </div>
        <p style="font-size:13px;color:#475569">
          Common fixes: try a different card, contact your bank to authorise the transaction,
          or use Apple Pay / Google Pay at checkout.
        </p>
        <p style="font-size:13px;color:#475569">
          Need help? Reply to this email or call us on <a href="tel:+441474878989" style="color:#0f172a">01474 878 989</a> — we'll
          take payment over the phone for you.
        </p>
        <p style="font-size:12px;color:#94a3b8;margin-top:24px">
          This recovery link is valid for {RECOVERY_WINDOW_DAYS} days. Your card details are
          never stored by Tile Station — payment is processed securely by Stripe.
        </p>
      </div>
      <div style="background:#0f172a;color:#94a3b8;padding:14px;text-align:center;font-size:11px">
        Tile Station · Unit 3 Trade City, Coldharbour Road, Northfleet, Gravesend DA11 8AB<br/>
        Company No: 11982550 · VAT No: 324 251 828
      </div>
    </div>
    """


async def send_payment_recovery_email(db, order: dict) -> dict:
    """Send the recovery email for `order`. Returns a small status dict
    describing what happened (sent / skipped / error). Idempotent:
    won't send twice for the same order."""
    customer_email = order.get("customer_email")
    order_id = order.get("id")
    if not customer_email or not order_id:
        return {"ok": False, "reason": "missing_email_or_order_id"}

    # Idempotency — refresh the row from DB so a parallel webhook retry
    # can't race past this guard.
    fresh = await db.shop_orders.find_one({"id": order_id}, {"_id": 0})
    if not fresh:
        return {"ok": False, "reason": "order_not_found"}
    if fresh.get("recovery_email_sent_at"):
        return {"ok": True, "skipped": "already_sent_at",
                "value": fresh["recovery_email_sent_at"]}

    # Mint a fresh, single-use recovery token. We persist BEFORE sending
    # so a Resend outage doesn't leave us with an email referencing a
    # token we never wrote.
    token = uuid.uuid4().hex
    expires = datetime.now(timezone.utc) + timedelta(days=RECOVERY_WINDOW_DAYS)
    now = datetime.now(timezone.utc).isoformat()
    await db.shop_orders.update_one(
        {"id": order_id, "recovery_email_sent_at": {"$exists": False}},
        {"$set": {
            "recovery_token": token,
            "recovery_token_expires_at": expires.isoformat(),
            "recovery_email_sent_at": now,
            "updated_at": now,
        }},
    )

    # Send via the same Resend pathway the rest of the app uses.
    try:
        from services.email import RESEND_AVAILABLE, RESEND_API_KEY  # noqa: PLC0415
    except Exception:  # noqa: BLE001
        return {"ok": False, "reason": "email_module_unavailable"}
    if not RESEND_AVAILABLE or not RESEND_API_KEY:
        logger.info("[payment-recovery] Resend not configured; persisted token but skipping send")
        return {"ok": True, "skipped": "resend_not_configured", "token": token}

    import asyncio  # noqa: PLC0415
    import resend  # noqa: PLC0415

    recovery_url = f"{_shop_url()}/shop/checkout/recover/{token}"
    customer_name = (order.get("customer_name") or "").split(" ")[0] or "there"
    items_count = len(order.get("items") or [])
    total = float(order.get("total") or 0)
    decline_message = order.get("payment_failed_reason") or ""

    html = _render_html(
        customer_name=customer_name,
        recovery_url=recovery_url,
        total=total,
        decline_message=decline_message,
        items_count=items_count,
    )

    resend.api_key = RESEND_API_KEY
    payload = {
        "from": "Tile Station <orders@tilestation.co.uk>",
        "to": [customer_email],
        "subject": "Your payment didn't go through — your cart is saved",
        "html": html,
        "reply_to": ["orders@tilestation.co.uk"],
    }
    try:
        await asyncio.to_thread(resend.Emails.send, payload)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[payment-recovery] Resend send failed for {order_id}: {e}")
        return {"ok": False, "reason": "resend_send_failed", "error": str(e),
                "token": token, "recovery_url": recovery_url}

    logger.info(f"[payment-recovery] Sent to {customer_email} for order {order_id}")
    return {"ok": True, "sent": True, "token": token, "recovery_url": recovery_url}


async def lookup_recovery_token(db, token: str) -> dict | None:
    """Return the order linked to `token` if it's still valid, else
    None. Used by the public storefront recovery route."""
    if not token or not isinstance(token, str) or len(token) < 16:
        return None
    order = await db.shop_orders.find_one(
        {"recovery_token": token}, {"_id": 0}
    )
    if not order:
        return None
    expires = order.get("recovery_token_expires_at")
    if expires:
        try:
            exp_dt = datetime.fromisoformat(expires.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) > exp_dt:
                return None
        except Exception:  # noqa: BLE001
            return None
    # Don't leak the token back out — the customer doesn't need it
    # again and it shouldn't appear in any client-side state.
    order.pop("recovery_token", None)
    return order

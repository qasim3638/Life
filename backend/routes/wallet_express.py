"""
Wallet Express Checkout — native Apple Pay + Google Pay on the cart page.

Unlike Klarna/PayPal Express (which redirect to Stripe's hosted checkout),
Apple Pay and Google Pay render as in-page buttons via Stripe's
ExpressCheckoutElement and settle via PaymentIntent (not Checkout Session).

Flow:
    1. Cart fetches a PaymentIntent client_secret from
       POST /api/shop/wallet-express/create-intent
    2. Stripe Elements mounts ExpressCheckoutElement; browser shows Apple Pay
       on Safari/iOS or Google Pay on Chrome/Android. Button is auto-hidden
       if no supported wallet is present.
    3. Customer authenticates with their device (Face ID, Touch ID, etc.) —
       Stripe confirms the PaymentIntent in-page.
    4. Frontend POSTs the wallet's shipping/contact details to
       POST /api/shop/wallet-express/confirm which finalizes the order.
    5. PaymentIntent webhook marks payment_status = paid independently.

Apple Pay domain verification is handled automatically via
`stripe.ApplePayDomain.create` on first enablement.
"""
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import stripe
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict, EmailStr

from config import get_db
from routes.shop import CartItem  # reuse the same cart-item shape

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/shop", tags=["wallet-express"])

# ---------------------------------------------------------------------------
# Admin toggle helpers
# ---------------------------------------------------------------------------

async def is_wallet_express_enabled() -> bool:
    """True when admin has flipped on Apple Pay + Google Pay at checkout."""
    try:
        db = get_db()
        doc = await db.website_settings.find_one({"key": "checkout_settings"}, {"_id": 0})
        return bool(
            (doc or {}).get("value", {}).get("payments", {}).get("wallet_express_enabled")
        )
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class WalletExpressIntentRequest(BaseModel):
    """Initial basket → PaymentIntent creation."""
    model_config = ConfigDict(extra="ignore")

    items: List[CartItem]
    origin_url: str
    customer_email: Optional[EmailStr] = None


class WalletExpressConfirmRequest(BaseModel):
    """Post-payment: the client sends back the wallet's shipping + contact
    metadata from ExpressCheckoutElement's `onConfirm` payload so we can
    store a usable order record even before the webhook arrives."""
    model_config = ConfigDict(extra="ignore")

    order_id: str
    payment_intent_id: str
    email: Optional[str] = ""
    name: Optional[str] = ""
    phone: Optional[str] = ""
    shipping_address: Optional[dict] = None


# ---------------------------------------------------------------------------
# Create PaymentIntent — opens the wallet flow
# ---------------------------------------------------------------------------

@router.post("/wallet-express/create-intent")
async def create_wallet_express_intent(request: Request, data: WalletExpressIntentRequest):
    """Creates a Stripe PaymentIntent restricted to Apple Pay + Google Pay
    (both delivered via the 'card' payment method in Stripe's API).

    Returns ``client_secret`` + ``order_id`` so the frontend ExpressCheckout
    can confirm payment in-page without redirecting."""
    if not await is_wallet_express_enabled():
        raise HTTPException(status_code=400, detail="Wallet Express is not enabled by the store")

    if not data.items:
        raise HTTPException(status_code=400, detail="Basket is empty")

    api_key = os.environ.get("STRIPE_API_KEY")
    if not api_key:
        logger.error("[wallet-express] STRIPE_API_KEY missing")
        raise HTTPException(status_code=500, detail="Payment service not configured")
    stripe.api_key = api_key

    # Server-compute totals (NEVER trust frontend)
    db = get_db()
    subtotal = 0.0
    cleaned_items = []
    for item in data.items:
        if (item.quantity or 0) <= 0 or (item.price or 0) <= 0:
            continue
        line_total = round(item.price * item.quantity, 2)
        subtotal += line_total
        cleaned_items.append(item.model_dump())
    subtotal = round(subtotal, 2)

    if not cleaned_items:
        raise HTTPException(status_code=400, detail="No valid items in basket")

    settings_doc = await db.website_settings.find_one({"key": "checkout_settings"}, {"_id": 0})
    delivery_cfg = (settings_doc or {}).get("value", {}).get("delivery", {})
    free_threshold = float(delivery_cfg.get("free_threshold", 1000) or 1000)
    standard_fee = float(delivery_cfg.get("standard_fee", 49.99) or 49.99)
    delivery_fee = 0.0 if subtotal >= free_threshold else standard_fee
    total = round(subtotal + delivery_fee, 2)
    if total <= 0:
        raise HTTPException(status_code=400, detail="Invalid basket total")

    # Placeholder order — customer/address filled in by /confirm or webhook
    now = datetime.now(timezone.utc)
    order_id = str(uuid.uuid4())
    order_number = f"WE-{int(now.timestamp())}"[-12:]  # WE = Wallet Express

    order_doc = {
        "id": order_id,
        "order_number": order_number,
        "customer_name": "",
        "customer_email": data.customer_email or "",
        "customer_phone": "",
        "delivery_method": "delivery",
        "delivery_address": {},
        "notes": "",
        "items": cleaned_items,
        "subtotal": subtotal,
        "delivery_fee": delivery_fee,
        "congestion_charge": 0.0,
        "express_fee": 0.0,
        "total": total,
        "status": "pending",
        "payment_status": "pending",
        "payment_method": "wallet",
        "source": "wallet_express",
        "is_express_wallet": True,
        "is_guest_order": True,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
    await db.shop_orders.insert_one(order_doc)

    try:
        intent = stripe.PaymentIntent.create(
            amount=int(total * 100),  # pence
            currency="gbp",
            # 'card' in Stripe's API covers Apple Pay + Google Pay
            automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
            metadata={
                "order_id": order_id,
                "order_number": order_number,
                "source": "wallet_express",
            },
        )
    except stripe.error.StripeError as e:
        logger.exception(f"[wallet-express] PaymentIntent failed | order={order_id} total={total}")
        raise HTTPException(status_code=502, detail=f"Stripe rejected the payment: {str(e)[:200]}")

    await db.shop_orders.update_one(
        {"id": order_id},
        {"$set": {
            "stripe_payment_intent_id": intent.id,
            "payment_status": "initiated",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )

    return {
        "client_secret": intent.client_secret,
        "payment_intent_id": intent.id,
        "order_id": order_id,
        "total": total,
    }


# ---------------------------------------------------------------------------
# Confirm — store customer details & shipping from the wallet payload
# ---------------------------------------------------------------------------

@router.post("/wallet-express/confirm")
async def confirm_wallet_express_order(data: WalletExpressConfirmRequest):
    """Called immediately after Stripe confirms the PaymentIntent in-browser
    so the order has a usable shipping address even before the webhook
    catches up. Idempotent — safe to replay."""
    db = get_db()
    order = await db.shop_orders.find_one({"id": data.order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Defence: this endpoint must never confirm an order unless Stripe agrees
    api_key = os.environ.get("STRIPE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Payment service not configured")
    stripe.api_key = api_key

    try:
        intent = stripe.PaymentIntent.retrieve(data.payment_intent_id)
    except stripe.error.StripeError as e:
        logger.exception(f"[wallet-express] confirm lookup failed | pi={data.payment_intent_id}")
        raise HTTPException(status_code=502, detail=f"Stripe lookup failed: {str(e)[:200]}")

    # Extract shipping from wallet or fallback to request
    ship = data.shipping_address or {}
    update = {
        "customer_email": data.email or order.get("customer_email", ""),
        "customer_name": data.name or order.get("customer_name", ""),
        "customer_phone": data.phone or order.get("customer_phone", ""),
        "delivery_address": ship or order.get("delivery_address", {}),
        "stripe_payment_intent_status": intent.status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Only mark paid if Stripe says so (webhook will also do this)
    if intent.status == "succeeded" and order.get("payment_status") != "paid":
        update["payment_status"] = "paid"
        update["status"] = "confirmed"

    await db.shop_orders.update_one({"id": data.order_id}, {"$set": update})
    return {
        "order_id": data.order_id,
        "status": update.get("status", order.get("status")),
        "payment_status": update.get("payment_status", order.get("payment_status")),
    }


# ---------------------------------------------------------------------------
# Apple Pay domain auto-registration
# ---------------------------------------------------------------------------

@router.post("/wallet-express/register-apple-domain")
async def register_apple_pay_domain(request: Request):
    """Registers the backend's public host with Stripe for Apple Pay.

    Called automatically when admin flips ``wallet_express_enabled`` to ON.
    Stripe requires the merchant to enable Apple Pay in their Dashboard AND
    serve the domain-association file — we do both (the route below).

    Idempotent: Stripe returns the existing record if the domain was already
    registered. Safe to call multiple times."""
    if not await is_wallet_express_enabled():
        raise HTTPException(status_code=400, detail="Enable Wallet Express first")

    api_key = os.environ.get("STRIPE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Payment service not configured")
    stripe.api_key = api_key

    # Derive the domain from the request — prefer the client-facing Host
    # header (so when the admin triggers this from the browser, the actual
    # public domain is registered, not the internal cluster URL). Falls back
    # to the request hostname if the header is missing.
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.hostname
    # Strip port if present
    host = (host or "").split(":")[0]
    if not host:
        raise HTTPException(status_code=400, detail="Could not determine request host")

    try:
        domain = stripe.ApplePayDomain.create(domain_name=host)
        logger.info(f"[wallet-express] Apple Pay domain registered: {host}")
        return {"domain_name": host, "id": domain.id, "status": "registered"}
    except stripe.error.InvalidRequestError as e:
        # Likely already registered — Stripe returns an error. Treat as success.
        msg = str(e).lower()
        if "already" in msg:
            return {"domain_name": host, "status": "already_registered"}
        logger.exception(f"[wallet-express] Apple Pay domain registration failed: {host}")
        raise HTTPException(status_code=502, detail=f"Domain registration failed: {str(e)[:200]}")
    except stripe.error.StripeError as e:
        logger.exception(f"[wallet-express] Apple Pay domain registration error: {host}")
        raise HTTPException(status_code=502, detail=f"Stripe error: {str(e)[:200]}")


# ---------------------------------------------------------------------------
# Apple Pay .well-known domain verification file
# ---------------------------------------------------------------------------
# NOTE: The actual ``/.well-known/apple-developer-merchantid-domain-association``
# route is registered directly on the main FastAPI app in server.py — Apple
# requires the file exactly at the domain root, not under /api/....
# The file lives at /app/backend/apple-pay-domain-association (bundled from
# Stripe's CDN). ``serve_apple_pay_association`` below is imported by
# server.py to attach the route.

APPLE_PAY_FILE_PATH = Path(__file__).resolve().parent.parent / "apple-pay-domain-association"


async def serve_apple_pay_association():
    """Serves the Apple Pay domain association file required for Apple Pay
    on web. Stripe fetches this to verify the domain before registering."""
    if APPLE_PAY_FILE_PATH.exists():
        return PlainTextResponse(APPLE_PAY_FILE_PATH.read_text())
    raise HTTPException(status_code=404, detail="Apple Pay domain association file not set")

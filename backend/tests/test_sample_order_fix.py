"""Test the sample-order Stripe-checkout fix.

Apr 30, 2026 — production reported 8 failed sample orders in 24h. Root causes:
  • `thirty_days_ago` calc was actually `today` (literal bug)
  • `pending_payment` orders counted toward the 2-per-month limit (so any
    error retry permanently locked the customer out)
  • Stripe checkout endpoint was never wired to the frontend; "Pay £2.99"
    button just navigated to a fake "Thanks, Paid!" page without charging
  • Frontend swallowed backend `detail` field, showing generic "Failed to
    create sample order" toast that gave the customer no actionable info

These tests lock in the regressions so the bugs can't return silently.
"""
import os
import sys
import asyncio
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from motor.motor_asyncio import AsyncIOMotorClient


def _db():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return client[os.environ["DB_NAME"]], client


@pytest.mark.asyncio
async def test_sample_order_30_day_window_is_actually_30_days():
    """The pre-fix code used `now()[:10]` which is *today*, not 30 days
    ago. A customer with 2 orders 35 days old should NOT be blocked today."""
    db, client = _db()
    email = f"old-{uuid.uuid4().hex[:6]}@example.com"
    pid = f"prod-{uuid.uuid4().hex[:6]}"

    # Seed product so the order can be created
    await db.products.insert_one({"id": pid, "name": "Test Tile"})
    # Seed 2 PAID orders from 35 days ago (outside 30-day window)
    old = (datetime.now(timezone.utc) - timedelta(days=35)).isoformat()
    for _ in range(2):
        await db.sample_orders.insert_one({
            "id": str(uuid.uuid4()), "customer_email": email,
            "status": "paid", "created_at": old,
        })

    try:
        from routes.shop import create_sample_order, SampleOrderCreate
        payload = SampleOrderCreate(
            customer_name="Old Customer", customer_email=email,
            delivery_address={"line1": "1 Test St", "city": "London", "postcode": "AB1 2CD"},
            product_ids=[pid],
        )
        # Should succeed because the 2 paid orders are outside the 30d window
        res = await create_sample_order(payload)
        assert res["order_number"].startswith("SMP-")
    finally:
        await db.products.delete_one({"id": pid})
        await db.sample_orders.delete_many({"customer_email": email})
        client.close()


@pytest.mark.asyncio
async def test_sample_order_pending_payment_does_not_count_to_limit():
    """A customer who hits errors retries and ends up with multiple
    `pending_payment` rows. Those must NOT block them — the limit is for
    completed orders only."""
    db, client = _db()
    email = f"retry-{uuid.uuid4().hex[:6]}@example.com"
    pid = f"prod-{uuid.uuid4().hex[:6]}"
    await db.products.insert_one({"id": pid, "name": "Test Tile"})
    # Seed 5 dangling pending_payment rows from earlier in the day
    now = datetime.now(timezone.utc).isoformat()
    for _ in range(5):
        await db.sample_orders.insert_one({
            "id": str(uuid.uuid4()), "customer_email": email,
            "status": "pending_payment", "created_at": now,
        })

    try:
        from routes.shop import create_sample_order, SampleOrderCreate
        payload = SampleOrderCreate(
            customer_name="Retry Customer", customer_email=email,
            delivery_address={"line1": "1 Test St", "city": "London", "postcode": "AB1 2CD"},
            product_ids=[pid],
        )
        # Should succeed — pending_payment rows don't count
        res = await create_sample_order(payload)
        assert res["order_number"].startswith("SMP-")
    finally:
        await db.products.delete_one({"id": pid})
        await db.sample_orders.delete_many({"customer_email": email})
        client.close()


@pytest.mark.asyncio
async def test_sample_order_blocks_on_2_paid_within_30_days():
    """Limit is intact: 2 PAID orders within 30 days does block."""
    db, client = _db()
    email = f"block-{uuid.uuid4().hex[:6]}@example.com"
    pid = f"prod-{uuid.uuid4().hex[:6]}"
    await db.products.insert_one({"id": pid, "name": "Test Tile"})
    recent = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    for _ in range(2):
        await db.sample_orders.insert_one({
            "id": str(uuid.uuid4()), "customer_email": email,
            "status": "paid", "created_at": recent,
        })

    try:
        from routes.shop import create_sample_order, SampleOrderCreate
        from fastapi import HTTPException
        payload = SampleOrderCreate(
            customer_name="Block Test", customer_email=email,
            delivery_address={"line1": "1 Test St", "city": "London", "postcode": "AB1 2CD"},
            product_ids=[pid],
        )
        with pytest.raises(HTTPException) as exc:
            await create_sample_order(payload)
        assert exc.value.status_code == 400
        # Must surface a useful reason, not a generic message
        assert "month" in exc.value.detail.lower()
    finally:
        await db.products.delete_one({"id": pid})
        await db.sample_orders.delete_many({"customer_email": email})
        client.close()


@pytest.mark.asyncio
async def test_sample_checkout_status_marks_order_paid_idempotently():
    """When Stripe confirms paid, the order flips to `paid` exactly once."""
    db, client = _db()
    sid = f"cs_test_{uuid.uuid4().hex[:12]}"
    order_id = str(uuid.uuid4())
    await db.sample_orders.insert_one({
        "id": order_id, "order_number": "SMP-T-1",
        "stripe_session_id": sid, "status": "pending_payment",
        "customer_email": "verify@x.com", "total": 2.99,
        "sample_count": 1,
    })

    try:
        # Mock STRIPE_API_KEY env + StripeCheckout.get_checkout_status
        with patch.dict(os.environ, {"STRIPE_API_KEY": "sk_test_x"}):
            mock_status = MagicMock(payment_status="paid")
            mock_checkout_inst = MagicMock()
            mock_checkout_inst.get_checkout_status = AsyncMock(return_value=mock_status)
            with patch("routes.shop.StripeCheckout", return_value=mock_checkout_inst):
                from routes.shop import get_sample_checkout_status
                r1 = await get_sample_checkout_status(sid)
                assert r1["payment_status"] == "paid"
                # Second call short-circuits without re-hitting Stripe
                r2 = await get_sample_checkout_status(sid)
                assert r2["payment_status"] == "paid"
                # Stripe API was called exactly once
                assert mock_checkout_inst.get_checkout_status.await_count == 1

        doc = await db.sample_orders.find_one({"id": order_id}, {"_id": 0})
        assert doc["status"] == "paid"
        assert "paid_at" in doc
    finally:
        await db.sample_orders.delete_one({"id": order_id})
        client.close()


@pytest.mark.asyncio
async def test_sample_checkout_status_reflects_unpaid_state_honestly():
    """If Stripe says unpaid/cancelled, the success page must NOT see 'paid'.
    This was the trust-hole pre-fix — the UI claimed paid without ever asking
    Stripe."""
    db, client = _db()
    sid = f"cs_test_{uuid.uuid4().hex[:12]}"
    order_id = str(uuid.uuid4())
    await db.sample_orders.insert_one({
        "id": order_id, "order_number": "SMP-T-2",
        "stripe_session_id": sid, "status": "pending_payment",
        "customer_email": "v2@x.com", "total": 2.99, "sample_count": 1,
    })

    try:
        with patch.dict(os.environ, {"STRIPE_API_KEY": "sk_test_x"}):
            mock_status = MagicMock(payment_status="unpaid")
            mock_checkout_inst = MagicMock()
            mock_checkout_inst.get_checkout_status = AsyncMock(return_value=mock_status)
            with patch("routes.shop.StripeCheckout", return_value=mock_checkout_inst):
                from routes.shop import get_sample_checkout_status
                r = await get_sample_checkout_status(sid)
                assert r["payment_status"] == "unpaid"
                # Order must NOT be flipped to paid
                doc = await db.sample_orders.find_one({"id": order_id}, {"_id": 0})
                assert doc["status"] == "pending_payment"
                assert "paid_at" not in doc
    finally:
        await db.sample_orders.delete_one({"id": order_id})
        client.close()

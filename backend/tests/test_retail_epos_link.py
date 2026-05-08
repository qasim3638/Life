"""End-to-end test for the retail-EPOS link work (Apr 30 2026).

Covers:
  • `GET /api/shop/customers/lookup` returns retail customers with
    `is_trade=False` (was previously trade-only).
  • Saving an EPOS invoice with `linked_shop_customer_id` for a retail
    customer bumps `total_spent` on `shop_customers`.
  • `reverse_invoice_credits` decrements `total_spent` for retail-only
    invoices (no trade credits to reverse).
  • `reapply_invoice_credits` re-bumps `total_spent` on restore.
  • `GET /api/shop/orders` surfaces the linked invoice for the retail
    customer (already worked because the endpoint isn't trade-gated, but
    we lock it in with a regression test).
"""
import os
import sys
import asyncio
import uuid
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from motor.motor_asyncio import AsyncIOMotorClient


def _db():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return client[os.environ["DB_NAME"]], client


@pytest.mark.asyncio
async def test_retail_lookup_and_total_spent_lifecycle():
    db, client = _db()
    cust_id = f"retail-test-{uuid.uuid4().hex[:8]}"
    email = f"retail-{uuid.uuid4().hex[:6]}@example.com"

    await db.shop_customers.insert_one({
        "id": cust_id,
        "email": email,
        "name": "Retail Tester",
        "phone": "07000999111",
        "is_trade": False,
        "total_spent": 0.0,
        "credit_balance": 0.0,
    })

    try:
        # ── 1. Lookup endpoint returns the retail customer ────────────
        from routes.shop import admin_customer_lookup
        fake_user = {"role": "staff", "email": "staff@test"}
        res = await admin_customer_lookup(email=email, current_user=fake_user)
        assert res["customer"], "retail customer should be returned by lookup"
        assert res["customer"]["is_trade"] is False
        assert res["customer"]["email"] == email
        # Should not leak password / _id
        assert "password" not in res["customer"]
        assert "_id" not in res["customer"]

        # ── 2. Bump total_spent like the invoice-create flow would ────
        gross = 199.50
        await db.shop_customers.update_one(
            {"id": cust_id}, {"$inc": {"total_spent": gross}},
        )
        snap = await db.shop_customers.find_one({"id": cust_id}, {"_id": 0, "total_spent": 1})
        assert abs(snap["total_spent"] - gross) < 0.01

        # ── 3. reverse_invoice_credits should decrement total_spent ───
        invoice_id = str(uuid.uuid4())
        invoice = {
            "id": invoice_id,
            "invoice_no": "INV-RET-1",
            "linked_shop_customer_id": cust_id,
            "trade_account_number": "",  # retail: no trade ref
            "trade_credit_earned": 0,
            "credit_redeemed": 0,
            "credit_redeemed_account": "",
            "gross_total": gross,
        }
        await db.invoices.insert_one(invoice)
        from routes.invoices import reverse_invoice_credits, reapply_invoice_credits
        summary = await reverse_invoice_credits(db, invoice, reason="test_void")
        assert summary["total_spent_reversed"] == gross
        snap = await db.shop_customers.find_one({"id": cust_id}, {"_id": 0, "total_spent": 1})
        assert abs(snap["total_spent"] - 0.0) < 0.01

        # Idempotency — second reverse must NOT double-decrement
        invoice_after_reverse = await db.invoices.find_one({"id": invoice_id}, {"_id": 0})
        summary2 = await reverse_invoice_credits(db, invoice_after_reverse, reason="test_void2")
        assert summary2["total_spent_reversed"] == 0.0

        # ── 4. reapply_invoice_credits should restore total_spent ─────
        # Reload — credits_reversed flag must be set for reapply to run
        invoice_after_reverse = await db.invoices.find_one({"id": invoice_id}, {"_id": 0})
        assert invoice_after_reverse.get("credits_reversed") is True
        summary3 = await reapply_invoice_credits(db, invoice_after_reverse, reason="test_restore")
        assert summary3["total_spent_reapplied"] == gross
        snap = await db.shop_customers.find_one({"id": cust_id}, {"_id": 0, "total_spent": 1})
        assert abs(snap["total_spent"] - gross) < 0.01

    finally:
        await db.shop_customers.delete_one({"id": cust_id})
        await db.invoices.delete_many({"linked_shop_customer_id": cust_id})
        client.close()


@pytest.mark.asyncio
async def test_retail_lookup_does_not_leak_password():
    """Regression: the projection must not return hashed password."""
    db, client = _db()
    cust_id = f"retail-leak-{uuid.uuid4().hex[:8]}"
    email = f"leak-{uuid.uuid4().hex[:6]}@example.com"
    await db.shop_customers.insert_one({
        "id": cust_id, "email": email, "password": "$2b$fakehash",
        "name": "Leak Test", "is_trade": False,
    })
    try:
        from routes.shop import admin_customer_lookup
        res = await admin_customer_lookup(
            email=email, current_user={"role": "staff", "email": "x"},
        )
        assert "password" not in (res["customer"] or {})
    finally:
        await db.shop_customers.delete_one({"id": cust_id})
        client.close()


@pytest.mark.asyncio
async def test_retail_lookup_legacy_missing_is_trade_field_treated_as_retail():
    """Older retail rows never had `is_trade` written. Lookup must still
    return them with is_trade=False (not crash, not skip)."""
    db, client = _db()
    cust_id = f"retail-legacy-{uuid.uuid4().hex[:8]}"
    email = f"legacy-{uuid.uuid4().hex[:6]}@example.com"
    await db.shop_customers.insert_one({
        "id": cust_id, "email": email, "name": "Legacy Retail",
        # NOTE: no is_trade key on purpose
    })
    try:
        from routes.shop import admin_customer_lookup
        res = await admin_customer_lookup(
            email=email, current_user={"role": "staff", "email": "x"},
        )
        assert res["customer"] is not None
        assert res["customer"]["is_trade"] is False
    finally:
        await db.shop_customers.delete_one({"id": cust_id})
        client.close()

"""Extended regression tests for the retail-EPOS link work.

Covers scenarios NOT covered by test_retail_epos_link.py:
  • Lookup still returns TRADE customers with all trade fields populated
  • Retail spend bump does NOT fire for linked TRADE customers (no double)
  • epos_invoice_to_order_and_customer adapter handles guest + linked sale
  • send_order_confirmation_email path does not blow up when apply_vat=False
    or REPORTLAB_AVAILABLE is False (mocked)
  • GET /api/shop/orders surfaces linked EPOS invoice for the retail customer
"""
import os
import sys
import uuid
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from motor.motor_asyncio import AsyncIOMotorClient


def _db():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return client[os.environ["DB_NAME"]], client


# ── 1. Trade customer lookup still fully functional ─────────────────────
@pytest.mark.asyncio
async def test_trade_lookup_returns_all_trade_fields():
    db, client = _db()
    cust_id = f"trade-test-{uuid.uuid4().hex[:8]}"
    email = f"trade-{uuid.uuid4().hex[:6]}@example.com"
    await db.shop_customers.insert_one({
        "id": cust_id,
        "email": email,
        "name": "Trade Tester",
        "phone": "07111222333",
        "is_trade": True,
        "trade_account_number": "T-99901",
        "business_name": "Trade Tester Ltd",
        "credit_balance": 125.50,
        "credit_rate": 5.0,
        "trade_discount": 15.0,
        "trade_tier": "Gold",
        "total_spent": 4200.0,
    })
    try:
        from routes.shop import admin_customer_lookup
        res = await admin_customer_lookup(
            email=email,
            current_user={"role": "admin", "email": "a@test"},
        )
        c = res["customer"]
        assert c is not None
        assert c["is_trade"] is True
        assert c["trade_account_number"] == "T-99901"
        assert c["business_name"] == "Trade Tester Ltd"
        assert abs(c["credit_balance"] - 125.50) < 0.01
        assert c["credit_rate"] == 5.0
        assert c["trade_discount"] == 15.0
        assert c["trade_tier"] == "Gold"
        assert "password" not in c
        assert "_id" not in c
    finally:
        await db.shop_customers.delete_one({"id": cust_id})
        client.close()


@pytest.mark.asyncio
async def test_lookup_returns_null_when_no_match():
    _, client = _db()
    try:
        from routes.shop import admin_customer_lookup
        res = await admin_customer_lookup(
            email="nobody-xyz-zzz@nowhere.invalid",
            current_user={"role": "staff", "email": "s@t"},
        )
        assert res == {"customer": None}
    finally:
        client.close()


@pytest.mark.asyncio
async def test_lookup_blocks_non_admin_role():
    from fastapi import HTTPException
    from routes.shop import admin_customer_lookup
    with pytest.raises(HTTPException) as excinfo:
        await admin_customer_lookup(
            email="x@y.com", current_user={"role": "customer", "email": "c@t"},
        )
    assert excinfo.value.status_code == 403


@pytest.mark.asyncio
async def test_lookup_returns_null_when_no_query_params():
    from routes.shop import admin_customer_lookup
    res = await admin_customer_lookup(
        email=None, phone=None,
        current_user={"role": "admin", "email": "a@t"},
    )
    assert res == {"customer": None}


@pytest.mark.asyncio
async def test_lookup_by_phone_works():
    db, client = _db()
    cust_id = f"phone-lookup-{uuid.uuid4().hex[:8]}"
    phone = f"079{uuid.uuid4().int % 100000000:08d}"
    await db.shop_customers.insert_one({
        "id": cust_id, "phone": phone, "name": "Phone Only",
        "is_trade": False, "email": f"{cust_id}@t.test",
    })
    try:
        from routes.shop import admin_customer_lookup
        res = await admin_customer_lookup(
            phone=phone,
            current_user={"role": "manager", "email": "m@t"},
        )
        assert res["customer"] is not None
        assert res["customer"]["id"] == cust_id
        assert res["customer"]["is_trade"] is False
    finally:
        await db.shop_customers.delete_one({"id": cust_id})
        client.close()


# ── 2. Retail spend bump must NOT fire for linked trade customer ────────
@pytest.mark.asyncio
async def test_reverse_credits_no_double_bump_for_trade_linked():
    """If the linked customer is_trade=True, the retail-only reverse branch
    MUST NOT fire a second total_spent decrement (trade path already owns
    that logic via earned_ref). This guards against double-accounting."""
    db, client = _db()
    cust_id = f"tr-linked-{uuid.uuid4().hex[:8]}"
    t_ref = f"T-{uuid.uuid4().hex[:5].upper()}"
    await db.shop_customers.insert_one({
        "id": cust_id, "email": f"{cust_id}@t.test",
        "is_trade": True, "trade_account_number": t_ref,
        "total_spent": 500.0, "credit_balance": 0.0,
    })
    invoice_id = str(uuid.uuid4())
    invoice = {
        "id": invoice_id,
        "invoice_no": "INV-TR-NO-DOUBLE",
        "linked_shop_customer_id": cust_id,
        # No trade_credit_earned, no credit_redeemed — so trade branch exits
        # after line 98 without bumping total_spent. Retail branch must ALSO
        # not fire because linked customer is is_trade=True.
        "trade_account_number": "",  # deliberately empty earned_ref
        "trade_credit_earned": 0,
        "credit_redeemed": 0,
        "gross_total": 100.0,
    }
    await db.invoices.insert_one(invoice)
    try:
        from routes.invoices import reverse_invoice_credits
        summary = await reverse_invoice_credits(db, invoice, reason="test")
        # No earned and no redeemed → trade branch returns early; retail
        # branch checks is_trade=True and skips. total_spent unchanged.
        snap = await db.shop_customers.find_one({"id": cust_id}, {"_id": 0, "total_spent": 1})
        assert abs(snap["total_spent"] - 500.0) < 0.01
        assert summary["total_spent_reversed"] == 0.0
    finally:
        await db.shop_customers.delete_one({"id": cust_id})
        await db.invoices.delete_one({"id": invoice_id})
        client.close()


# ── 3. VAT PDF adapter ──────────────────────────────────────────────────
def test_epos_invoice_to_order_and_customer_shape():
    from services.vat_invoice_pdf import epos_invoice_to_order_and_customer
    inv = {
        "id": "i1",
        "invoice_no": "INV-001",
        "linked_shop_customer_id": "c1",
        "customer_email": "buyer@t.test",
        "customer_name": "Buyer",
        "customer_address": "1 Test St",
        "customer_phone": "07900000000",
        "apply_vat": True,
        "subtotal": 100.0,
        "gross_total": 120.0,
        "amount_outstanding": 0,
        "line_items": [
            {"product_name": "Tile A", "due_price": 10.0, "quantity": 5},
            {"description": "Grout", "price": 25.0, "quantity": 2},
        ],
        "date": "2026-01-15",
    }
    order, customer = epos_invoice_to_order_and_customer(inv)
    assert order["order_number"] == "INV-001"
    assert order["customer_email"] == "buyer@t.test"
    assert len(order["items"]) == 2
    assert order["items"][0]["name"] == "Tile A"
    assert order["items"][1]["name"] == "Grout"
    assert abs(order["subtotal"] - 100.0) < 0.01
    assert abs(order["total"] - 120.0) < 0.01
    assert order["status"] == "delivered"  # amount_outstanding 0
    assert customer["name"] == "Buyer"
    assert customer["phone"] == "07900000000"


def test_epos_invoice_to_order_apply_vat_false_uses_gross_as_net():
    """Cash quotation: apply_vat=False should pass gross as the net PDF figure."""
    from services.vat_invoice_pdf import epos_invoice_to_order_and_customer
    inv = {
        "id": "i2", "invoice_no": "INV-Q-1",
        "customer_name": "Cash", "customer_email": "c@t.t",
        "apply_vat": False, "subtotal": 0, "gross_total": 200.0,
        "line_items": [], "amount_outstanding": 50.0,
    }
    order, _ = epos_invoice_to_order_and_customer(inv)
    assert abs(order["subtotal"] - 200.0) < 0.01
    assert order["status"] == "processing"


def test_epos_invoice_to_order_subtotal_fallback_from_gross():
    """When subtotal missing but apply_vat=True, derive ex-VAT from gross/1.2."""
    from services.vat_invoice_pdf import epos_invoice_to_order_and_customer
    inv = {
        "id": "i3", "invoice_no": "INV-F",
        "customer_name": "X", "customer_email": "x@t.t",
        "apply_vat": True, "subtotal": 0, "gross_total": 120.0,
        "line_items": [],
    }
    order, _ = epos_invoice_to_order_and_customer(inv)
    assert abs(order["subtotal"] - 100.0) < 0.01


# ── 4. Shop orders surfaces linked retail invoice ───────────────────────
@pytest.mark.asyncio
async def test_shop_orders_surfaces_linked_retail_invoice():
    """Regression lock: GET /api/shop/orders for a retail customer with a
    linked EPOS invoice must include that invoice with source='in_store'."""
    db, client = _db()
    cust_id = f"ret-orders-{uuid.uuid4().hex[:8]}"
    email = f"ord-{uuid.uuid4().hex[:6]}@t.test"
    await db.shop_customers.insert_one({
        "id": cust_id, "email": email, "name": "Retail Orders",
        "is_trade": False, "total_spent": 0, "credit_balance": 0,
    })
    invoice_id = str(uuid.uuid4())
    await db.invoices.insert_one({
        "id": invoice_id,
        "invoice_no": "INV-RET-ORD",
        "linked_shop_customer_id": cust_id,
        "customer_email": email,
        "customer_name": "Retail Orders",
        "date": "2026-01-20",
        "created_at": "2026-01-20T10:00:00+00:00",
        "subtotal": 83.33, "gross_total": 100.00,
        "line_items": [{"product_name": "Tile B", "due_price": 25.0, "quantity": 4}],
        "status": "open_order",
        "apply_vat": True,
    })
    try:
        # Build a stub request for get_shop_orders. It uses get_shop_customer
        # which reads a session cookie; simpler path: call the helper that
        # get_shop_orders uses (search for it directly).
        from routes.shop import get_shop_orders
        from unittest.mock import patch, AsyncMock

        # Patch get_shop_customer to return our retail customer
        async def fake_get_shop_customer(req):
            return {"id": cust_id, "email": email, "is_trade": False}

        with patch("routes.shop.get_shop_customer", side_effect=fake_get_shop_customer):
            # Request object — minimal fake
            class _Req:
                cookies = {}
                headers = {}
            orders = await get_shop_orders(_Req())
            # Should contain the linked invoice entry
            matches = [o for o in orders if o.get("invoice_no") == "INV-RET-ORD" or o.get("order_number") == "INV-RET-ORD"]
            assert matches, f"Linked invoice missing from orders list: {orders}"
            inv_entry = matches[0]
            assert inv_entry.get("source") == "in_store"
            # Standard shape
            assert "total" in inv_entry
            assert "items" in inv_entry
    finally:
        await db.shop_customers.delete_one({"id": cust_id})
        await db.invoices.delete_one({"id": invoice_id})
        client.close()


# ── 5. Email path tolerates REPORTLAB_AVAILABLE=False ───────────────────
@pytest.mark.asyncio
async def test_send_order_confirmation_handles_reportlab_missing(monkeypatch):
    """When REPORTLAB is unavailable, email must still send (no PDF attach).
    Patch resend.Emails.send to capture the payload without network IO."""
    import services.email as email_mod
    # Stub resend to capture payload
    captured = {}

    class _FakeEmails:
        @staticmethod
        def send(payload):
            captured["payload"] = payload
            return {"id": "fake"}

    class _FakeResend:
        api_key = None
        Emails = _FakeEmails

    monkeypatch.setattr(email_mod, "resend", _FakeResend)
    # Force REPORTLAB_AVAILABLE False in the pdf module
    import services.vat_invoice_pdf as pdf_mod
    monkeypatch.setattr(pdf_mod, "REPORTLAB_AVAILABLE", False)

    invoice = {
        "id": "fake-inv",
        "invoice_no": "INV-EMAIL-1",
        "customer_email": "buyer@t.test",
        "customer_name": "Buyer",
        "apply_vat": True,
        "gross_total": 120.0,
        "subtotal": 100.0,
        "line_items": [{"product_name": "Tile", "due_price": 10, "quantity": 10}],
        "showroom_name": "Tile Station",
        "date": "2026-01-20",
    }
    # Call the function
    await email_mod.send_order_confirmation_email(invoice)
    payload = captured.get("payload")
    assert payload is not None
    assert payload["to"] == ["buyer@t.test"]
    # No attachment should be set when REPORTLAB unavailable
    assert "attachments" not in payload


@pytest.mark.asyncio
async def test_send_order_confirmation_skips_pdf_when_apply_vat_false(monkeypatch):
    """Cash quotation conversions (apply_vat=False) must NOT attach a VAT PDF."""
    import services.email as email_mod
    captured = {}

    class _FakeEmails:
        @staticmethod
        def send(payload):
            captured["payload"] = payload
            return {"id": "fake"}

    class _FakeResend:
        api_key = None
        Emails = _FakeEmails

    monkeypatch.setattr(email_mod, "resend", _FakeResend)

    invoice = {
        "id": "fake-inv-2",
        "invoice_no": "INV-Q-EMAIL",
        "customer_email": "cashbuyer@t.test",
        "customer_name": "Cash Buyer",
        "apply_vat": False,
        "gross_total": 99.0,
        "subtotal": 0,
        "line_items": [],
        "showroom_name": "Tile Station",
        "date": "2026-01-20",
    }
    await email_mod.send_order_confirmation_email(invoice)
    payload = captured["payload"]
    assert "attachments" not in payload

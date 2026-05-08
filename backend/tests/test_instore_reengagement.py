"""Test the in-store re-engagement voucher endpoint.

`/api/shop/account/instore-reengagement` mints (or reuses) a 5%-off voucher
for retail customers with a stale (>30-day-old) IN-STORE EPOS invoice and
no fresh online orders. Drives the "Running low?" amber nudge under each
qualifying IN-STORE row in CustomerAccountPage.
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
async def test_eligible_when_stale_invoice_and_no_recent_online_orders():
    db, client = _db()
    cust_id = f"reeng-{uuid.uuid4().hex[:8]}"
    email = f"reeng-{uuid.uuid4().hex[:6]}@example.com"
    inv_id = str(uuid.uuid4())
    old = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()

    await db.shop_customers.insert_one({
        "id": cust_id, "email": email, "name": "Re-eng", "is_trade": False,
    })
    await db.invoices.insert_one({
        "id": inv_id, "invoice_no": "INV-OLD",
        "linked_shop_customer_id": cust_id,
        "created_at": old,
        "line_items": [],
    })

    try:
        from routes.shop import instore_reengagement
        with patch("routes.shop.get_shop_customer",
                   AsyncMock(return_value={"id": cust_id, "email": email})):
            res = await instore_reengagement(MagicMock())
        assert res["eligible"] is True
        assert res["voucher_code"]
        assert res["voucher_code"].startswith("TILE5-")
        assert res["percent_off"] == 5
        assert inv_id in res["qualifying_invoice_ids"]

        # Voucher persisted in DB
        doc = await db.shop_discount_codes.find_one({"code": res["voucher_code"]})
        assert doc
        assert doc["email"] == email.lower()
        assert doc["source"] == "instore_reengagement"
        assert doc["max_uses"] == 1
        assert doc["used_count"] == 0
    finally:
        await db.shop_customers.delete_one({"id": cust_id})
        await db.invoices.delete_one({"id": inv_id})
        await db.shop_discount_codes.delete_many({"email": email.lower()})
        client.close()


@pytest.mark.asyncio
async def test_not_eligible_when_recent_online_order_exists():
    """A customer who placed a fresh online order in the last 30 days is
    already engaged — no nudge needed."""
    db, client = _db()
    cust_id = f"reeng-engaged-{uuid.uuid4().hex[:8]}"
    email = f"engaged-{uuid.uuid4().hex[:6]}@example.com"
    old = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    recent = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()

    await db.shop_customers.insert_one({
        "id": cust_id, "email": email, "is_trade": False,
    })
    await db.invoices.insert_one({
        "id": str(uuid.uuid4()), "linked_shop_customer_id": cust_id,
        "created_at": old, "line_items": [],
    })
    online_id = str(uuid.uuid4())
    await db.shop_orders.insert_one({
        "id": online_id, "customer_id": cust_id, "created_at": recent,
        "items": [], "total": 50.0,
    })

    try:
        from routes.shop import instore_reengagement
        with patch("routes.shop.get_shop_customer",
                   AsyncMock(return_value={"id": cust_id, "email": email})):
            res = await instore_reengagement(MagicMock())
        assert res["eligible"] is False
        assert res["voucher_code"] is None
        assert res["qualifying_invoice_ids"] == []
        # No voucher minted
        doc = await db.shop_discount_codes.find_one({"email": email.lower()})
        assert doc is None
    finally:
        await db.shop_customers.delete_one({"id": cust_id})
        await db.invoices.delete_many({"linked_shop_customer_id": cust_id})
        await db.shop_orders.delete_one({"id": online_id})
        client.close()


@pytest.mark.asyncio
async def test_not_eligible_when_invoice_is_recent():
    """A 5-day-old in-store invoice is too fresh to nudge."""
    db, client = _db()
    cust_id = f"reeng-fresh-{uuid.uuid4().hex[:8]}"
    email = f"fresh-{uuid.uuid4().hex[:6]}@example.com"
    fresh = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    await db.shop_customers.insert_one({"id": cust_id, "email": email, "is_trade": False})
    await db.invoices.insert_one({
        "id": str(uuid.uuid4()), "linked_shop_customer_id": cust_id,
        "created_at": fresh, "line_items": [],
    })
    try:
        from routes.shop import instore_reengagement
        with patch("routes.shop.get_shop_customer",
                   AsyncMock(return_value={"id": cust_id, "email": email})):
            res = await instore_reengagement(MagicMock())
        assert res["eligible"] is False
    finally:
        await db.shop_customers.delete_one({"id": cust_id})
        await db.invoices.delete_many({"linked_shop_customer_id": cust_id})
        client.close()


@pytest.mark.asyncio
async def test_voucher_is_idempotent_across_calls():
    """Calling the endpoint twice should return the SAME unused voucher,
    not mint a duplicate."""
    db, client = _db()
    cust_id = f"reeng-idem-{uuid.uuid4().hex[:8]}"
    email = f"idem-{uuid.uuid4().hex[:6]}@example.com"
    old = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    await db.shop_customers.insert_one({"id": cust_id, "email": email, "is_trade": False})
    await db.invoices.insert_one({
        "id": str(uuid.uuid4()), "linked_shop_customer_id": cust_id,
        "created_at": old, "line_items": [],
    })

    try:
        from routes.shop import instore_reengagement
        with patch("routes.shop.get_shop_customer",
                   AsyncMock(return_value={"id": cust_id, "email": email})):
            res1 = await instore_reengagement(MagicMock())
            res2 = await instore_reengagement(MagicMock())
        assert res1["voucher_code"] == res2["voucher_code"]
        # Only one voucher in DB
        count = await db.shop_discount_codes.count_documents({
            "email": email.lower(), "source": "instore_reengagement",
        })
        assert count == 1
    finally:
        await db.shop_customers.delete_one({"id": cust_id})
        await db.invoices.delete_many({"linked_shop_customer_id": cust_id})
        await db.shop_discount_codes.delete_many({"email": email.lower()})
        client.close()


@pytest.mark.asyncio
async def test_deleted_invoices_do_not_qualify():
    """Voided/deleted invoices must NOT trigger the nudge — that would be
    creepy ("we noticed your deleted invoice…")."""
    db, client = _db()
    cust_id = f"reeng-del-{uuid.uuid4().hex[:8]}"
    email = f"del-{uuid.uuid4().hex[:6]}@example.com"
    old = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    await db.shop_customers.insert_one({"id": cust_id, "email": email, "is_trade": False})
    await db.invoices.insert_one({
        "id": str(uuid.uuid4()), "linked_shop_customer_id": cust_id,
        "created_at": old, "deleted_at": old, "line_items": [],
    })
    try:
        from routes.shop import instore_reengagement
        with patch("routes.shop.get_shop_customer",
                   AsyncMock(return_value={"id": cust_id, "email": email})):
            res = await instore_reengagement(MagicMock())
        assert res["eligible"] is False
    finally:
        await db.shop_customers.delete_one({"id": cust_id})
        await db.invoices.delete_many({"linked_shop_customer_id": cust_id})
        client.close()

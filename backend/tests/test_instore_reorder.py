"""Test the in-store reorder fallback added to /api/shop/orders/{id}/reorder-items.

The endpoint used to look up only `shop_orders`. We extended it to fall back
to `invoices` when no online order matches AND the invoice is linked to the
calling customer. This unlocks the "Order again" button on retail in-store
rows in CustomerAccountPage.
"""
import os
import sys
import asyncio
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from motor.motor_asyncio import AsyncIOMotorClient


def _db():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return client[os.environ["DB_NAME"]], client


@pytest.mark.asyncio
async def test_reorder_falls_back_to_linked_invoice():
    db, client = _db()
    cust_id = f"reorder-test-{uuid.uuid4().hex[:8]}"
    inv_id = str(uuid.uuid4())

    # Seed retail customer + linked invoice (no shop_orders row)
    await db.shop_customers.insert_one({
        "id": cust_id, "email": "reorder@example.com", "name": "Reorder Tester",
        "is_trade": False,
    })
    await db.invoices.insert_one({
        "id": inv_id, "invoice_no": "INV-REORD-1",
        "linked_shop_customer_id": cust_id,
        "customer_name": "Reorder Tester",
        "customer_email": "reorder@example.com",
        "line_items": [
            # Free-typed line: no product_id → should come back unavailable
            {"product_name": "Custom 100x100 ceramic", "quantity": 5,
             "due_price": 12.0, "price": 14.0},
            # Product-id line: should resolve via tiles lookup OR products
            {"product_id": "non-existent-sku-xyz",
             "product_name": "Phantom Product", "quantity": 3,
             "due_price": 8.0, "price": 10.0},
        ],
        "subtotal": 60.0, "gross_total": 72.0,
    })

    try:
        from routes.shop import get_reorder_items

        # Mock get_shop_customer to bypass auth
        with patch("routes.shop.get_shop_customer",
                   AsyncMock(return_value={"id": cust_id, "email": "reorder@example.com"})):
            fake_request = MagicMock()
            res = await get_reorder_items(fake_request, inv_id)

        assert res["order_id"] == inv_id
        assert res["order_number"] == "INV-REORD-1"
        assert res["source"] == "in_store"
        assert len(res["items"]) == 2
        # Free-typed line → in_store_custom unavailable
        free_typed = res["items"][0]
        assert free_typed["available"] is False
        assert free_typed["reason"] == "in_store_custom"
        # Phantom-product-id line → delisted (had a product_id but no tile match)
        phantom = res["items"][1]
        assert phantom["available"] is False
        assert phantom["reason"] == "delisted"

    finally:
        await db.shop_customers.delete_one({"id": cust_id})
        await db.invoices.delete_one({"id": inv_id})
        client.close()


@pytest.mark.asyncio
async def test_reorder_404_when_invoice_not_linked_to_caller():
    """Security: a customer must not be able to reorder another customer's
    in-store invoice by guessing the invoice ID."""
    db, client = _db()
    other_cust = f"other-{uuid.uuid4().hex[:8]}"
    me = f"me-{uuid.uuid4().hex[:8]}"
    inv_id = str(uuid.uuid4())

    await db.shop_customers.insert_many([
        {"id": other_cust, "email": "other@x.com", "is_trade": False},
        {"id": me, "email": "me@x.com", "is_trade": False},
    ])
    await db.invoices.insert_one({
        "id": inv_id, "invoice_no": "INV-OTHER",
        "linked_shop_customer_id": other_cust,  # NOT me
        "line_items": [],
    })

    try:
        from routes.shop import get_reorder_items
        from fastapi import HTTPException
        with patch("routes.shop.get_shop_customer",
                   AsyncMock(return_value={"id": me, "email": "me@x.com"})):
            with pytest.raises(HTTPException) as exc:
                await get_reorder_items(MagicMock(), inv_id)
            assert exc.value.status_code == 404
    finally:
        await db.shop_customers.delete_many({"id": {"$in": [other_cust, me]}})
        await db.invoices.delete_one({"id": inv_id})
        client.close()


@pytest.mark.asyncio
async def test_reorder_skips_deleted_invoice():
    """Voided/deleted invoices must not be reorderable."""
    db, client = _db()
    cust = f"del-{uuid.uuid4().hex[:8]}"
    inv_id = str(uuid.uuid4())
    from datetime import datetime, timezone

    await db.shop_customers.insert_one({"id": cust, "email": "del@x.com", "is_trade": False})
    await db.invoices.insert_one({
        "id": inv_id, "invoice_no": "INV-DEL",
        "linked_shop_customer_id": cust,
        "deleted_at": datetime.now(timezone.utc).isoformat(),
        "line_items": [],
    })
    try:
        from routes.shop import get_reorder_items
        from fastapi import HTTPException
        with patch("routes.shop.get_shop_customer",
                   AsyncMock(return_value={"id": cust, "email": "del@x.com"})):
            with pytest.raises(HTTPException) as exc:
                await get_reorder_items(MagicMock(), inv_id)
            assert exc.value.status_code == 404
    finally:
        await db.shop_customers.delete_one({"id": cust})
        await db.invoices.delete_one({"id": inv_id})
        client.close()

"""
End-to-end regression: confirm that send_order_status_notification still
delivers successfully AND that the trade-credit banner HTML is included
in the rendered body when the customer is a trade with positive balance.

We don't actually verify the email was received (would require Resend webhook
introspection) — we just confirm send returns success and the rendered HTML
contains the banner string for a trade customer.
"""
import os, sys, asyncio, uuid
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


async def run():
    sys.path.insert(0, "/app/backend")
    from services.email import (
        _render_trade_credit_balance_banner_html,
        generate_order_status_email_html,
        send_order_status_notification,
    )

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    test_email = f"e2e-banner-{uuid.uuid4().hex[:6]}@example.com"
    cust_id = f"e2e-banner-{uuid.uuid4().hex[:8]}"
    await db.shop_customers.insert_one({
        "id": cust_id, "email": test_email, "is_trade": True,
        "credit_balance": 42.75, "trade_account_number": "T-E2E1",
        "business_name": "E2E Test Ltd", "name": "E2E",
    })

    fake_order = {
        "id": "test-order-1",
        "order_number": "TS-TEST-12345",
        "customer_email": test_email,
        "customer_name": "E2E Test",
        "items": [{"name": "Demo Tile", "quantity": 1, "price": 100.0}],
        "subtotal": 100.0, "vat": 20.0, "total": 120.0, "delivery_fee": 0,
        "delivery_method": "delivery",
        "created_at": "2026-04-29T12:00:00Z",
    }

    # 1. Render check — must include £42.75 banner
    banner = await _render_trade_credit_balance_banner_html(test_email)
    rendered = generate_order_status_email_html(
        order=fake_order, status="confirmed", trade_credit_banner_html=banner,
    )
    assert "£42.75" in rendered, f"Banner not in rendered HTML"
    assert "Spend now" in rendered
    print(f"[1] Render check: banner injected ({len(banner)} chars) ✓")

    # 2. Real send (Resend) — should succeed
    result = await send_order_status_notification(fake_order, "confirmed")
    print(f"[2] Send result: {result}")
    assert result.get("success") is True, f"Email send failed: {result}"

    # Cleanup
    await db.shop_customers.delete_one({"id": cust_id})
    print("\nAll Banner E2E assertions PASSED ✅")
    client.close()


asyncio.run(run())

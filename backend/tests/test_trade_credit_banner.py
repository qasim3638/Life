"""
Regression test for the personalised trade-credit balance banner injected
into transactional emails.

Verifies:
  1. _render_trade_credit_balance_banner_html returns banner HTML for a
     trade customer with positive balance.
  2. Returns "" for a trade customer with £0 balance (per user request).
  3. Returns "" for a non-trade customer (ordinary shop account).
  4. Returns "" when the email isn't recognised (graceful no-op).
  5. Returns "" if email is None/empty.
"""
import os
import asyncio
import uuid
from motor.motor_asyncio import AsyncIOMotorClient

# These envs are loaded by the parent test runner via `set -a; . .env`
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


async def run():
    # Make config.get_db() resolve to the same connection
    import sys
    sys.path.insert(0, "/app/backend")
    from services.email import _render_trade_credit_balance_banner_html

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # Seed customers
    trade_with_balance = f"banner-trade-{uuid.uuid4().hex[:6]}@example.com"
    trade_zero_balance = f"banner-trade-zero-{uuid.uuid4().hex[:6]}@example.com"
    non_trade_with_balance = f"banner-shop-{uuid.uuid4().hex[:6]}@example.com"

    cust_ids = [f"banner-{uuid.uuid4().hex[:8]}" for _ in range(3)]
    await db.shop_customers.insert_many([
        {"id": cust_ids[0], "email": trade_with_balance, "is_trade": True,
         "credit_balance": 87.50, "trade_account_number": "T-BANNER1",
         "business_name": "Banner Test Ltd", "name": "Banner Test"},
        {"id": cust_ids[1], "email": trade_zero_balance, "is_trade": True,
         "credit_balance": 0.0, "trade_account_number": "T-BANNER2",
         "business_name": "Zero Test Ltd", "name": "Zero Test"},
        # Non-trade customer with a stale credit_balance field — banner must NOT render
        {"id": cust_ids[2], "email": non_trade_with_balance, "is_trade": False,
         "credit_balance": 25.0, "name": "Shop Test"},
    ])

    # 1. Trade with balance → banner present
    h1 = await _render_trade_credit_balance_banner_html(trade_with_balance)
    assert "£87.50" in h1, f"Expected £87.50 in banner, got: {h1[:200]}"
    assert "Spend now" in h1
    assert "T-BANNER1" in h1
    print(f"[1] Trade w/£87.50 → banner rendered ({len(h1)} chars) ✓")

    # 2. Trade with £0 balance → empty (per user request)
    h2 = await _render_trade_credit_balance_banner_html(trade_zero_balance)
    assert h2 == "", f"Expected empty for £0 balance, got: {h2[:200]}"
    print(f"[2] Trade w/£0 → empty ✓")

    # 3. Non-trade → empty
    h3 = await _render_trade_credit_balance_banner_html(non_trade_with_balance)
    assert h3 == "", f"Expected empty for non-trade, got: {h3[:200]}"
    print(f"[3] Non-trade → empty ✓")

    # 4. Unknown email → empty
    h4 = await _render_trade_credit_balance_banner_html(f"never-seen-{uuid.uuid4().hex}@example.com")
    assert h4 == ""
    print(f"[4] Unknown email → empty ✓")

    # 5. None/empty email → empty
    h5a = await _render_trade_credit_balance_banner_html(None)
    h5b = await _render_trade_credit_balance_banner_html("")
    assert h5a == "" and h5b == ""
    print(f"[5] None/empty email → empty ✓")

    # Cleanup
    await db.shop_customers.delete_many({"id": {"$in": cust_ids}})
    print("\nAll Trade-Credit-Banner assertions PASSED ✅")
    client.close()


asyncio.run(run())

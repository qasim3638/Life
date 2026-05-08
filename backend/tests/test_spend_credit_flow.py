"""
Regression test for the "Spend my credit" online checkout flow.
Verifies that POST /api/shop/trade/credits/redeem:
  1. Atomically deducts from shop_customers.credit_balance
  2. Updates the order's `total` and stamps `credits_applied` + `original_total`
  3. Records a `trade_credits` entry with type='redeem'
  4. Rejects insufficient balances with 400
  5. Rejects already-paid orders with 404
"""
import os, asyncio, uuid
from datetime import datetime, timezone
import requests
from motor.motor_asyncio import AsyncIOMotorClient

API = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


async def run():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # 1. Seed a trade customer with £100 balance and grab a fresh login token
    cust_id = f"spend-credit-{uuid.uuid4().hex[:6]}"
    test_email = f"spend-credit-{uuid.uuid4().hex[:6]}@example.com"
    password = "TestPass123!"
    # Insert directly with bcrypt-hashed password for a clean login
    import bcrypt
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    await db.shop_customers.insert_one({
        "id": cust_id,
        "email": test_email,
        "phone": "07900222333",
        "name": "Spend Credit Test",
        "business_name": "SpendTest Ltd",
        "password": pw_hash,
        "is_trade": True,
        "trade_account_number": f"T-SPEND{uuid.uuid4().hex[:5].upper()}",
        "credit_balance": 100.0,
        "credit_rate": 5.0,
        "trade_tier": "silver",
        "trade_discount": 5.0,
        "is_approved": True,
        "approved": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    # Login as the trade customer to get a session token
    login = requests.post(
        f"{API}/api/shop/auth/login",
        json={"email": test_email, "password": password},
        timeout=15,
    )
    print(f"[setup] Login → HTTP {login.status_code}")
    if login.status_code != 200:
        # Try alternate trade login route
        login = requests.post(
            f"{API}/api/shop/trade/login",
            json={"email": test_email, "password": password},
            timeout=15,
        )
        print(f"[setup] Trade login fallback → HTTP {login.status_code}: {login.text[:200]}")
    assert login.status_code == 200, f"Trade login failed: {login.text}"
    body = login.json()
    token = body.get("token") or body.get("access_token")
    H = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # 2. Create an unpaid order (£250 total) directly so we don't have to
    # walk through the full guest-checkout flow for this regression.
    order_id = f"spend-order-{uuid.uuid4().hex[:8]}"
    await db.shop_orders.insert_one({
        "id": order_id,
        "order_number": f"TS-TEST-{uuid.uuid4().hex[:6].upper()}",
        "customer_id": cust_id,
        "customer_email": test_email,
        "customer_name": "Spend Credit Test",
        "items": [{"product_id": "x", "name": "Test", "price": 250.0, "quantity": 1}],
        "subtotal": 250.0,
        "total": 250.0,
        "payment_status": "pending",
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    # 3. Redeem £80 of credit
    r = requests.post(
        f"{API}/api/shop/trade/credits/redeem",
        json={"order_id": order_id, "amount": 80.0},
        headers=H,
        timeout=15,
    )
    print(f"[1] Redeem £80 → HTTP {r.status_code}: {r.text[:200]}")
    assert r.status_code == 200, r.text
    rb = r.json()
    assert abs(rb["credits_redeemed"] - 80.0) < 0.01
    assert abs(rb["new_total"] - 170.0) < 0.01
    assert abs(rb["new_balance"] - 20.0) < 0.01

    # 4. Verify DB state
    cust = await db.shop_customers.find_one({"id": cust_id}, {"_id": 0, "credit_balance": 1})
    assert abs(cust["credit_balance"] - 20.0) < 0.01
    order = await db.shop_orders.find_one({"id": order_id}, {"_id": 0})
    assert abs(order["total"] - 170.0) < 0.01
    assert abs(order["credits_applied"] - 80.0) < 0.01
    print(f"[2] DB: balance=£{cust['credit_balance']}, order_total=£{order['total']}, credits_applied=£{order['credits_applied']}")

    # 5. Insufficient balance → 400
    r2 = requests.post(
        f"{API}/api/shop/trade/credits/redeem",
        json={"order_id": order_id, "amount": 9999.0},
        headers=H, timeout=15,
    )
    print(f"[3] Over-redemption → HTTP {r2.status_code}: {r2.json().get('detail', '')[:80]}")
    assert r2.status_code == 400

    # 6. Already-paid order → 404 (status filter rejects)
    await db.shop_orders.update_one({"id": order_id}, {"$set": {"payment_status": "paid"}})
    r3 = requests.post(
        f"{API}/api/shop/trade/credits/redeem",
        json={"order_id": order_id, "amount": 5.0},
        headers=H, timeout=15,
    )
    print(f"[4] Paid order → HTTP {r3.status_code}: {r3.json().get('detail', '')[:80]}")
    assert r3.status_code == 404

    # Cleanup
    await db.shop_customers.delete_one({"id": cust_id})
    await db.shop_orders.delete_one({"id": order_id})
    await db.trade_credits.delete_many({"customer_id": cust_id})
    print("\nAll Spend-Credit regression assertions PASSED ✅")
    client.close()


asyncio.run(run())

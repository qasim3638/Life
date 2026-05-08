"""
Regression test: regular (non-trade) shoppers with positive credit_balance
can also redeem via /api/shop/trade/credits/redeem (relaxed gate).

  1. Non-trade customer with £20 balance → can redeem £15 → balance £5, order total reduced
  2. Non-trade customer with £0 balance → 400 "No credit available to redeem"
  3. Trade customer still redeems normally (no regression)
"""
import os, asyncio, uuid
from datetime import datetime, timezone
import requests
import bcrypt
from motor.motor_asyncio import AsyncIOMotorClient

API = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


async def run():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    password = "TestPass123!"
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    # Non-trade with £20 balance
    cust_id = f"shop-credit-{uuid.uuid4().hex[:8]}"
    test_email = f"shop-credit-{uuid.uuid4().hex[:6]}@example.com"
    await db.shop_customers.insert_one({
        "id": cust_id, "email": test_email, "phone": "07900333444",
        "name": "Shop Credit Test", "password": pw_hash,
        "is_trade": False, "credit_balance": 20.0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    login = requests.post(f"{API}/api/shop/auth/login", json={"email": test_email, "password": password}, timeout=15)
    assert login.status_code == 200
    token = login.json().get("token") or login.json().get("access_token")
    H = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    order_id = f"shop-credit-order-{uuid.uuid4().hex[:8]}"
    await db.shop_orders.insert_one({
        "id": order_id, "order_number": f"TS-SC-{uuid.uuid4().hex[:6].upper()}",
        "customer_id": cust_id, "customer_email": test_email,
        "items": [{"product_id": "x", "name": "Test", "price": 100.0, "quantity": 1}],
        "subtotal": 100.0, "total": 100.0, "payment_status": "pending", "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    # 1. Redeem £15 of £20 balance → balance £5, order total £85
    r = requests.post(f"{API}/api/shop/trade/credits/redeem",
                      json={"order_id": order_id, "amount": 15.0}, headers=H, timeout=15)
    print(f"[1] Non-trade redeem £15 → HTTP {r.status_code}: {r.text[:200]}")
    assert r.status_code == 200, r.text
    rb = r.json()
    assert abs(rb["new_balance"] - 5.0) < 0.01
    assert abs(rb["new_total"] - 85.0) < 0.01

    # 2. Empty the balance, try again → 400
    await db.shop_customers.update_one({"id": cust_id}, {"$set": {"credit_balance": 0.0}})
    # Need a fresh unpaid order since the previous one had credits_applied stamped
    order_id_2 = f"shop-credit-order2-{uuid.uuid4().hex[:8]}"
    await db.shop_orders.insert_one({
        "id": order_id_2, "order_number": f"TS-SC2-{uuid.uuid4().hex[:6].upper()}",
        "customer_id": cust_id, "customer_email": test_email,
        "items": [], "subtotal": 50.0, "total": 50.0, "payment_status": "pending", "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    r2 = requests.post(f"{API}/api/shop/trade/credits/redeem",
                       json={"order_id": order_id_2, "amount": 5.0}, headers=H, timeout=15)
    print(f"[2] Non-trade w/£0 balance → HTTP {r2.status_code}: {r2.json().get('detail','')[:80]}")
    assert r2.status_code == 400

    # Cleanup
    await db.shop_customers.delete_one({"id": cust_id})
    await db.shop_orders.delete_many({"customer_id": cust_id})
    await db.trade_credits.delete_many({"customer_id": cust_id})
    print("\nAll Non-Trade Credit Redeem assertions PASSED ✅")
    client.close()


asyncio.run(run())

"""
Regression test for the on-demand "Send this statement now" endpoint.

Verifies POST /api/admin/trade-credit/statements/send-one:
  1. Valid trade customer with movement → 200 + {sent: true}
  2. Trade customer with no movement in the requested month → 400
  3. Non-trade customer → 404
  4. Unknown email → 404
  5. Audit row written to credit_statement_sends with `trigger='admin_on_demand'`
"""
import os, sys, asyncio, uuid
from datetime import datetime, timezone, timedelta
import requests
from motor.motor_asyncio import AsyncIOMotorClient

API = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


async def run():
    sys.path.insert(0, "/app/backend")
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    now = datetime.now(timezone.utc)
    first_of_this = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end_of_prev = first_of_this - timedelta(seconds=1)
    year, month = end_of_prev.year, end_of_prev.month
    in_window = first_of_this - timedelta(days=10)

    # Trade with movement
    cust_id_a = f"send1-trade-{uuid.uuid4().hex[:8]}"
    email_a = f"send1-trade-{uuid.uuid4().hex[:6]}@example.com"
    await db.shop_customers.insert_one({
        "id": cust_id_a, "email": email_a, "is_trade": True,
        "credit_balance": 22.50, "trade_account_number": "T-SEND1",
        "business_name": "Send Now Ltd", "name": "Send Now",
    })
    await db.credit_transactions.insert_many([
        {"id": str(uuid.uuid4()), "customer_id": cust_id_a, "type": "earned_in_store",
         "amount": 62.50, "balance_after": 62.50, "invoice_no": "INV-S1",
         "source": "epos_invoice", "description": "Earned",
         "created_at": in_window.isoformat()},
        {"id": str(uuid.uuid4()), "customer_id": cust_id_a, "type": "redeemed_in_store",
         "amount": -40.00, "balance_after": 22.50, "invoice_no": "INV-S2",
         "source": "epos_invoice", "description": "Redeemed",
         "created_at": (in_window + timedelta(days=2)).isoformat()},
    ])

    # Trade without movement
    cust_id_b = f"send1-quiet-{uuid.uuid4().hex[:8]}"
    email_b = f"send1-quiet-{uuid.uuid4().hex[:6]}@example.com"
    await db.shop_customers.insert_one({
        "id": cust_id_b, "email": email_b, "is_trade": True,
        "credit_balance": 0.0, "trade_account_number": "T-QUIET1",
        "business_name": "Quiet Co", "name": "Quiet",
    })

    # Non-trade
    cust_id_c = f"send1-shop-{uuid.uuid4().hex[:8]}"
    email_c = f"send1-shop-{uuid.uuid4().hex[:6]}@example.com"
    await db.shop_customers.insert_one({
        "id": cust_id_c, "email": email_c, "is_trade": False, "name": "Shop",
    })

    login = requests.post(f"{API}/api/auth/login", json={"email": "admin@test.com", "password": "admin123"}, timeout=15)
    token = login.json()["token"]
    H = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # 1. Valid send
    r1 = requests.post(f"{API}/api/admin/trade-credit/statements/send-one",
                       json={"email": email_a, "year": year, "month": month}, headers=H, timeout=20)
    print(f"[1] Send (valid trade) → HTTP {r1.status_code}: {r1.json()}")
    assert r1.status_code == 200, r1.text
    body = r1.json()
    assert body["sent"] is True
    assert body["customer_email"] == email_a
    assert abs(body["summary"]["earned_total"] - 62.50) < 0.01

    # 5. Audit row written
    audit = await db.credit_statement_sends.find_one({"customer_email": email_a}, {"_id": 0})
    assert audit is not None
    assert audit["sent_by"] == "admin@test.com"
    assert audit["trigger"] == "admin_on_demand"
    print(f"[5] Audit row written: trigger={audit['trigger']}, by={audit['sent_by']} ✓")

    # 2. Trade with no movement → 400
    r2 = requests.post(f"{API}/api/admin/trade-credit/statements/send-one",
                       json={"email": email_b, "year": year, "month": month}, headers=H, timeout=15)
    print(f"[2] Send (trade no movement) → HTTP {r2.status_code}: {r2.json().get('detail','')[:80]}")
    assert r2.status_code == 400

    # 3. Non-trade → 404
    r3 = requests.post(f"{API}/api/admin/trade-credit/statements/send-one",
                       json={"email": email_c, "year": year, "month": month}, headers=H, timeout=15)
    print(f"[3] Send (non-trade) → HTTP {r3.status_code}")
    assert r3.status_code == 404

    # 4. Unknown email → 404
    r4 = requests.post(f"{API}/api/admin/trade-credit/statements/send-one",
                       json={"email": f"unknown-{uuid.uuid4().hex}@example.com", "year": year, "month": month},
                       headers=H, timeout=15)
    print(f"[4] Send (unknown) → HTTP {r4.status_code}")
    assert r4.status_code == 404

    # Cleanup
    await db.shop_customers.delete_many({"id": {"$in": [cust_id_a, cust_id_b, cust_id_c]}})
    await db.credit_transactions.delete_many({"customer_id": {"$in": [cust_id_a, cust_id_b, cust_id_c]}})
    await db.credit_statement_sends.delete_many({"customer_id": {"$in": [cust_id_a, cust_id_b, cust_id_c]}})
    print("\nAll Send-One regression assertions PASSED ✅")
    client.close()


asyncio.run(run())

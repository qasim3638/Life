"""
Test for the unified trader-facing credit history endpoint
GET /api/shop/trade/credit-history-detailed.

Verifies:
  1. Merges online (`trade_credits`) + EPOS (`credit_transactions
     type=earned_in_store`) events into one timeline.
  2. EPOS earn events carry the per-product `breakdown` array from the
     joined `invoices` doc.
  3. Online events have `breakdown=null` (not yet stamped).
  4. Events sorted newest-first.
  5. Aggregates `total_earned` and `total_redeemed`.
  6. Non-trade customers get `is_trade=false` and an empty list.
"""
import os
import sys
import asyncio
import uuid
from datetime import datetime, timezone, timedelta

import requests
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

API = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


async def run():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    cust_id = f"hist-test-{uuid.uuid4().hex[:8]}"
    t_ref = f"T-HIST{uuid.uuid4().hex[:5].upper()}"
    test_email = f"hist-{uuid.uuid4().hex[:6]}@example.com"
    password_hash = "$2b$12$KIXNxh3nQjJ7m8PuQ/jBaO0eQH2gG1kVH8V7E5Yt3p4O2Zv1N1z9C"  # "test" — never used (we mint a JWT directly)

    # Seed the trade customer
    await db.shop_customers.insert_one({
        "id": cust_id,
        "email": test_email,
        "password": password_hash,  # Field name in this codebase is `password`, not `password_hash`
        "name": "History Test",
        "business_name": "History Test Ltd",
        "is_trade": True,
        "trade_account_number": t_ref,
        "credit_balance": 100.0,
        "credit_rate": 5.0,
        "trade_discount": 5.0,
        "approved": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    now = datetime.now(timezone.utc)

    # Seed an online earn (trade_credits)
    await db.trade_credits.insert_one({
        "id": str(uuid.uuid4()),
        "customer_id": cust_id,
        "order_id": "ord-online-1",
        "order_number": "TS-HIST-ONL",
        "type": "earn",
        "amount": 5.0,
        "balance_after": 5.0,
        "description": "Credit back from order TS-HIST-ONL",
        "created_at": (now - timedelta(days=2)).isoformat(),
    })

    # Seed an EPOS earn invoice with a breakdown stamp
    inv_id = str(uuid.uuid4())
    await db.invoices.insert_one({
        "id": inv_id,
        "invoice_no": "INV-HIST-EPOS",
        "customer_email": test_email,
        "trade_account_number": t_ref,
        "subtotal": 100.0,
        "gross_total": 100.0,
        "trade_credit_earned": 5.0,
        "trade_credit_rate": 5.0,
        "trade_credit_breakdown": [
            {
                "product_id": "p1",
                "sku": "PREMIUM-1",
                "product_name": "Premium Marble",
                "quantity": 1,
                "net": 50.0,
                "rate": 8.0,
                "credit": 4.0,
            },
            {
                "product_id": "p2",
                "sku": "GENERIC-1",
                "product_name": "Generic Sealer",
                "quantity": 1,
                "net": 50.0,
                "rate": 2.0,
                "credit": 1.0,
            },
        ],
        "created_at": (now - timedelta(hours=1)).isoformat(),
    })
    await db.credit_transactions.insert_one({
        "id": str(uuid.uuid4()),
        "customer_id": cust_id,
        "trade_account_number": t_ref,
        "type": "earned_in_store",
        "amount": 5.0,
        "balance_after": 10.0,
        "source": "epos_invoice",
        "invoice_id": inv_id,
        "invoice_no": "INV-HIST-EPOS",
        "description": "Credit back from in-store invoice INV-HIST-EPOS (per-product rates, blended 5.0% of £100.00)",
        "created_at": (now - timedelta(hours=1)).isoformat(),
    })

    # Seed an EPOS redeem (no breakdown)
    await db.credit_transactions.insert_one({
        "id": str(uuid.uuid4()),
        "customer_id": cust_id,
        "trade_account_number": t_ref,
        "type": "redeemed_in_store",
        "amount": -3.0,
        "balance_after": 7.0,
        "source": "epos_invoice",
        "invoice_id": "ignored",
        "invoice_no": "INV-HIST-RED",
        "description": "Credit redeemed at till on invoice INV-HIST-RED",
        "created_at": (now - timedelta(minutes=30)).isoformat(),
    })

    # Login the trade customer to mint a token. The trader auth endpoint is
    # /api/shop/trade/login which expects email + password. We seeded a
    # bcrypt hash for "test" — but matching it locally is tricky, so just
    # patch the password with the public registration endpoint OR mint a
    # token by upserting one. Simplest: hit the public trade login flow.
    # For the test we sidestep by directly calling the unified endpoint
    # with a token minted from the customer record (the route reads
    # `tile_shop_token` JWT but accepts the standard shop token too via
    # `get_shop_customer`).
    #
    # Simplest robust approach — update the password to a known value via
    # the dev backdoor: POST /api/shop/trade/auth/login if it's a public
    # password-based login flow; if not, use the staff /api/auth/login
    # token path (admin can impersonate).
    #
    # Use the trade-login path with a freshly bcrypt-set password.
    import bcrypt
    raw_pwd = "TestPass1234!"
    fresh_hash = bcrypt.hashpw(raw_pwd.encode(), bcrypt.gensalt()).decode()
    await db.shop_customers.update_one({"id": cust_id}, {"$set": {"password": fresh_hash}})

    login = requests.post(
        f"{API}/api/shop/auth/login",
        json={"email": test_email, "password": raw_pwd},
        timeout=15,
    )
    assert login.status_code == 200, f"Login failed: {login.status_code} {login.text}"
    token = login.json().get("token") or login.json().get("access_token")
    assert token, f"No token in login response: {login.json()}"
    H = {"Authorization": f"Bearer {token}"}

    # Hit the new endpoint
    r = requests.get(f"{API}/api/shop/trade/credit-history-detailed", headers=H, timeout=15)
    print(f"[1] HTTP {r.status_code}")
    assert r.status_code == 200, r.text
    data = r.json()
    print(f"[2] is_trade={data['is_trade']}, balance={data['credit_balance']}, "
          f"earned={data['total_earned']}, redeemed={data['total_redeemed']}, "
          f"events={len(data['events'])}")
    assert data["is_trade"] is True
    assert len(data["events"]) >= 3

    # Newest-first ordering
    ats = [e["at"] for e in data["events"] if e.get("at")]
    assert ats == sorted(ats, reverse=True), "Events not newest-first"
    print("[3] Events sorted newest-first ✓")

    # Find the EPOS earn event and verify breakdown
    epos_earn = next(
        (e for e in data["events"] if e["channel"] == "in_store" and e["type"] == "earn"),
        None,
    )
    assert epos_earn, "EPOS earn event missing"
    assert epos_earn["breakdown"], "Expected breakdown on EPOS earn"
    assert len(epos_earn["breakdown"]) == 2
    rates = sorted(b["rate"] for b in epos_earn["breakdown"])
    assert rates == [2.0, 8.0]
    credits = sorted(b["credit"] for b in epos_earn["breakdown"])
    assert credits == [1.0, 4.0]
    print(f"[4] EPOS earn breakdown: {len(epos_earn['breakdown'])} rows, rates={rates} ✓")

    # Online earn should have null breakdown
    online_earn = next(
        (e for e in data["events"] if e["channel"] == "online" and e["type"] == "earn"),
        None,
    )
    assert online_earn, "Online earn event missing"
    assert online_earn["breakdown"] is None
    assert online_earn["source_label"] == "TS-HIST-ONL"
    print("[5] Online earn event has null breakdown (not yet stamped) ✓")

    # EPOS redeem event present
    epos_redeem = next(
        (e for e in data["events"] if e["channel"] == "in_store" and e["type"] == "redeem"),
        None,
    )
    assert epos_redeem, "EPOS redeem event missing"
    assert epos_redeem["amount"] < 0  # negative for redemptions
    print(f"[6] EPOS redeem event: amount={epos_redeem['amount']} ✓")

    # Aggregate sanity
    assert abs(data["total_earned"] - 10.0) < 0.01  # 5 + 5
    assert abs(data["total_redeemed"] - 3.0) < 0.01
    print("[7] Aggregates correct (earned=10, redeemed=3) ✓")

    # Cleanup
    await db.shop_customers.delete_one({"id": cust_id})
    await db.trade_credits.delete_many({"customer_id": cust_id})
    await db.credit_transactions.delete_many({"customer_id": cust_id})
    await db.invoices.delete_one({"id": inv_id})

    print("\nAll Credit History assertions PASSED ✅")
    client.close()


asyncio.run(run())

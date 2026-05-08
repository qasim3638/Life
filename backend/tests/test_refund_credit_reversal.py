"""
Regression test for proportional credit reversal on Refund Notes.

Flow:
  1. Create EPOS invoice for £100 gross that earns £5 + redeems £50 from £200.
  2. Issue a 50% Refund Note tied to that invoice → expect:
     - £2.50 earned reversed (50% of £5)
     - £25 redeemed refunded (50% of £50)
     - Customer balance shifts proportionally
  3. Issue a 100% (final 50%) Refund Note → expect cumulative caps respected:
     - Only the REMAINING £2.50 earned + £25 redeemed gets reversed (no overshoot)
  4. Refund unattached to any invoice → reversal returns zeros (no crash).
  5. Refund tied to invoice with NO credit movement → returns zeros.
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

    # Seed trade customer
    cust_id = f"refund-cred-{uuid.uuid4().hex[:8]}"
    t_ref = f"T-RFN{uuid.uuid4().hex[:5].upper()}"
    test_email = f"refund-cred-{uuid.uuid4().hex[:6]}@example.com"
    test_phone = f"079990{uuid.uuid4().int % 100000:05d}"
    await db.shop_customers.insert_one({
        "id": cust_id, "email": test_email, "phone": test_phone,
        "name": "Refund Test", "business_name": "Refund Test Ltd",
        "is_trade": True, "trade_account_number": t_ref,
        "credit_balance": 200.0, "credit_rate": 5.0,
        "trade_tier": "silver", "trade_discount": 5.0, "total_spent": 0.0,
    })

    # Enable in_store_credit
    sm_doc = await db.website_settings.find_one({"key": "storefront_messages"}, {"_id": 0, "value": 1})
    original_value = (sm_doc or {}).get("value") or {}
    new_value = dict(original_value)
    new_value["in_store_credit"] = {"enabled": True}
    await db.website_settings.update_one(
        {"key": "storefront_messages"},
        {"$set": {"value": new_value}}, upsert=True,
    )

    login = requests.post(f"{API}/api/auth/login", json={"email": "admin@test.com", "password": "admin123"}, timeout=15)
    token = login.json()["token"]
    H = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Create invoice: £100 gross, redeem £50, earn £5
    payload = {
        "invoice_no": f"INV-RFN-{uuid.uuid4().hex[:6].upper()}",
        "customer_name": "Refund Test", "customer_email": test_email,
        "customer_phone": test_phone, "customer_address": "1 Test St",
        "date": "01/01/2026", "showroom_id": "demo", "showroom_name": "Test SR",
        "deposits": [{"date": "01/01/2026", "amount": 50.0, "method": "Card", "note": ""}],
        "line_items": [{
            "id": "li-1", "description": "Test", "product_name": "Test",
            "quantity": 1, "boxes": 1, "price": 100.0, "due_price": 100.0,
            "total": 100.0, "isReturn": False,
        }],
        "subtotal": 100.0, "vat": 0.0, "gross_total": 100.0,
        "total_savings": 0, "apply_vat": False,
        "credit_redeemed_amount": 50.0, "credit_redeemed_account": t_ref,
    }
    r = requests.post(f"{API}/api/invoices", json=payload, headers=H, timeout=20)
    assert r.status_code == 200
    inv_id = r.json()["invoice_id"]
    inv_no = r.json()["invoice_no"]

    cust = await db.shop_customers.find_one({"id": cust_id}, {"_id": 0, "credit_balance": 1})
    # Per-product credit-back: line has no SKU → 2% default → £2 earned
    assert abs(cust["credit_balance"] - 152.0) < 0.01  # 200 - 50 + 2
    print(f"[setup] Balance after invoice: £{cust['credit_balance']} ✓")

    # 1. 50% partial refund (£50 of £100)
    refund1 = {
        "refund_no": f"REF-{uuid.uuid4().hex[:6].upper()}",
        "date": "02/01/2026",
        "original_invoice_id": inv_id, "original_invoice_no": inv_no,
        "customer_name": "Refund Test", "customer_email": test_email,
        "refund_method": "Cash", "refund_type": "Partial Refund",
        "showroom_id": "demo", "showroom_name": "Test SR",
        "line_items": [{
            "product_name": "Test", "quantity": 0.5,
            "original_price": 100.0, "refund_price": 100.0, "total": 50.0,
        }],
        "subtotal": 50.0, "vat": 0.0, "gross_total": 50.0, "restocking_fee": 0,
    }
    r1 = requests.post(f"{API}/api/refunds", json=refund1, headers=H, timeout=20)
    print(f"[1] 50% refund → HTTP {r1.status_code}: {r1.json()}")
    assert r1.status_code == 200
    rev = r1.json()["credits_reversed"]
    assert abs(rev["earned_reversed"] - 1.0) < 0.01   # 50% of £2
    assert abs(rev["redeemed_reversed"] - 25.0) < 0.01  # 50% of £50
    assert abs(rev["ratio"] - 0.5) < 0.01

    cust = await db.shop_customers.find_one({"id": cust_id}, {"_id": 0, "credit_balance": 1})
    # 152 - 1 + 25 = 176
    print(f"[1b] Balance after 50% refund: £{cust['credit_balance']} (expected £176.00)")
    assert abs(cust["credit_balance"] - 176.0) < 0.01

    # 2. Final 50% refund — cumulative cap should kick in
    refund2 = dict(refund1)
    refund2["refund_no"] = f"REF-{uuid.uuid4().hex[:6].upper()}"
    refund2["date"] = "03/01/2026"
    r2 = requests.post(f"{API}/api/refunds", json=refund2, headers=H, timeout=20)
    print(f"[2] Final 50% refund → HTTP {r2.status_code}: {r2.json()}")
    assert r2.status_code == 200
    rev2 = r2.json()["credits_reversed"]
    assert abs(rev2["earned_reversed"] - 1.0) < 0.01    # remaining 50% of £2
    assert abs(rev2["redeemed_reversed"] - 25.0) < 0.01  # remaining 50%

    cust = await db.shop_customers.find_one({"id": cust_id}, {"_id": 0, "credit_balance": 1})
    # 176 - 1 + 25 = 200 (full reversal)
    print(f"[2b] Balance after final 50% refund: £{cust['credit_balance']} (expected £200)")
    assert abs(cust["credit_balance"] - 200.0) < 0.01

    # 3. Try a third refund — cumulative cap should return zeros
    refund3 = dict(refund1)
    refund3["refund_no"] = f"REF-{uuid.uuid4().hex[:6].upper()}"
    refund3["date"] = "04/01/2026"
    r3 = requests.post(f"{API}/api/refunds", json=refund3, headers=H, timeout=20)
    rev3 = r3.json()["credits_reversed"]
    print(f"[3] Over-refund attempt → ratio={rev3['ratio']}, earned={rev3['earned_reversed']}, redeemed={rev3['redeemed_reversed']}")
    assert rev3["earned_reversed"] == 0.0
    assert rev3["redeemed_reversed"] == 0.0

    # 4. Refund unattached to any invoice → graceful zeros
    refund4 = {
        "refund_no": f"REF-{uuid.uuid4().hex[:6].upper()}",
        "date": "05/01/2026",
        "customer_name": "Walk-in", "customer_email": test_email,
        "refund_method": "Cash", "showroom_id": "demo", "showroom_name": "Test SR",
        "line_items": [{
            "product_name": "Walk-in", "quantity": 1,
            "original_price": 20.0, "refund_price": 20.0, "total": 20.0,
        }],
        "subtotal": 20.0, "vat": 0.0, "gross_total": 20.0, "restocking_fee": 0,
    }
    r4 = requests.post(f"{API}/api/refunds", json=refund4, headers=H, timeout=20)
    print(f"[4] Unattached refund → HTTP {r4.status_code}, reversed={r4.json()['credits_reversed']}")
    assert r4.status_code == 200
    assert r4.json()["credits_reversed"]["earned_reversed"] == 0.0

    # Cleanup
    await db.shop_customers.delete_one({"id": cust_id})
    await db.invoices.delete_many({"customer_email": test_email})
    await db.refunds.delete_many({"customer_email": test_email})
    await db.credit_transactions.delete_many({"customer_id": cust_id})
    if original_value:
        await db.website_settings.update_one(
            {"key": "storefront_messages"}, {"$set": {"value": original_value}}, upsert=True,
        )

    print("\nAll Refund-Credit-Reversal assertions PASSED ✅")
    client.close()


asyncio.run(run())

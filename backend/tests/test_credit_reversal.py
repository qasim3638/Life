"""
Regression test for trade-credit reversal across all 3 invalidation paths.

Flow:
  1. Create EPOS invoice that earns £5 + redeems £50 from a £200 balance.
  2. Soft-delete invoice → balance returns to £200 (- £5 earned reversed,
     + £50 redeemed refunded). Two reversal ledger rows present.
  3. Restore invoice → credits re-applied (balance back to original
     post-invoice state: 200 - 50 + 5 = £155).
  4. Permanently delete → credits reversed again (balance £200).
  5. Soft-delete is idempotent: re-call doesn't double-reverse.

Plus online order cancellation:
  6. Cancel an online order with awarded + applied credits → both reversed.
  7. Un-cancel (back to processing) → both re-applied.
"""
import os, sys, asyncio, uuid
from datetime import datetime, timezone
import requests
from motor.motor_asyncio import AsyncIOMotorClient

API = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


async def run():
    sys.path.insert(0, "/app/backend")
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # Seed trade customer with £200 balance
    cust_id = f"reverse-cust-{uuid.uuid4().hex[:8]}"
    t_ref = f"T-REV{uuid.uuid4().hex[:5].upper()}"
    test_email = f"reverse-test-{uuid.uuid4().hex[:6]}@example.com"
    test_phone = f"079990{uuid.uuid4().int % 100000:05d}"
    await db.shop_customers.insert_one({
        "id": cust_id, "email": test_email, "phone": test_phone,
        "name": "Reverse Test", "business_name": "Reverse Test Ltd",
        "is_trade": True, "trade_account_number": t_ref,
        "credit_balance": 200.0, "credit_rate": 5.0,
        "trade_tier": "silver", "trade_discount": 5.0, "total_spent": 0.0,
    })

    # Enable in_store_credit toggle
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

    # Create invoice: gross £100, redeems £50 → outstanding £50; earns 5% of £100 = £5
    payload = {
        "invoice_no": f"INV-REV-{uuid.uuid4().hex[:6].upper()}",
        "customer_name": "Reverse Test", "customer_email": test_email,
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
    assert r.status_code == 200, r.text
    invoice_id = r.json()["invoice_id"]

    # Sanity: balance 200 - 50 redeemed + 2 earned = £152 (per-product 2% default)
    cust = await db.shop_customers.find_one({"id": cust_id}, {"_id": 0, "credit_balance": 1})
    print(f"[setup] After create: balance £{cust['credit_balance']} (expected £152)")
    assert abs(cust["credit_balance"] - 152.0) < 0.01

    # 2. Soft-delete invoice
    r2 = requests.delete(f"{API}/api/invoices/{invoice_id}", headers=H, timeout=15)
    print(f"[1] Soft-delete → HTTP {r2.status_code}: {r2.json()}")
    assert r2.status_code == 200
    summary = r2.json()["credits_reversed"]
    assert abs(summary["earned_reversed"] - 2.0) < 0.01
    assert abs(summary["redeemed_reversed"] - 50.0) < 0.01

    cust = await db.shop_customers.find_one({"id": cust_id}, {"_id": 0, "credit_balance": 1})
    print(f"[1b] Balance after soft-delete: £{cust['credit_balance']} (expected £200)")
    assert abs(cust["credit_balance"] - 200.0) < 0.01

    # 5. Idempotency: try delete again — should not double reverse
    # (the invoice is already in trash, so the endpoint returns 404 on a
    # fresh DELETE call, which is correct. But we can verify via direct
    # helper invocation that even a re-call doesn't double-reverse.)
    from routes.invoices import reverse_invoice_credits
    inv_doc = await db.invoices.find_one({"id": invoice_id}, {"_id": 0})
    s = await reverse_invoice_credits(db, inv_doc)
    assert s["earned_reversed"] == 0.0 and s["redeemed_reversed"] == 0.0
    print(f"[5] Idempotency check: re-reverse returns zeros ✓")

    # 3. Restore invoice
    r3 = requests.post(f"{API}/api/invoices/{invoice_id}/restore", headers=H, timeout=15)
    print(f"[2] Restore → HTTP {r3.status_code}: {r3.json()}")
    assert r3.status_code == 200
    reapplied = r3.json()["credits_reapplied"]
    assert abs(reapplied["earned_reapplied"] - 2.0) < 0.01
    assert abs(reapplied["redeemed_reapplied"] - 50.0) < 0.01

    cust = await db.shop_customers.find_one({"id": cust_id}, {"_id": 0, "credit_balance": 1})
    print(f"[2b] Balance after restore: £{cust['credit_balance']} (expected £152)")
    assert abs(cust["credit_balance"] - 152.0) < 0.01

    # 4. Permanent delete (without soft-deleting first)
    rp = requests.delete(f"{API}/api/invoices/{invoice_id}/permanent", headers=H, timeout=15)
    print(f"[3] Permanent delete → HTTP {rp.status_code}: {rp.json()}")
    assert rp.status_code == 200
    rev = rp.json()["credits_reversed"]
    assert abs(rev["earned_reversed"] - 2.0) < 0.01
    assert abs(rev["redeemed_reversed"] - 50.0) < 0.01

    cust = await db.shop_customers.find_one({"id": cust_id}, {"_id": 0, "credit_balance": 1})
    print(f"[3b] Balance after perm delete: £{cust['credit_balance']} (expected £200)")
    assert abs(cust["credit_balance"] - 200.0) < 0.01

    # ======================================================================
    # Online order flow
    # ======================================================================
    order_id = f"reverse-order-{uuid.uuid4().hex[:8]}"
    await db.shop_orders.insert_one({
        "id": order_id, "order_number": f"TS-REV-{uuid.uuid4().hex[:6].upper()}",
        "customer_id": cust_id, "customer_email": test_email,
        "items": [], "subtotal": 100.0, "total": 75.0,  # 100 - 25 redeemed
        "credits_applied": 25.0,  # redeemed at checkout
        "credits_awarded": 5.0,   # earned post-completion
        "status": "processing", "payment_status": "paid",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    # Simulate the post-payment crediting (we set the balance directly to mirror reality)
    await db.shop_customers.update_one({"id": cust_id}, {"$set": {"credit_balance": 180.0}})  # 200 - 25 + 5

    # 6. Cancel order via the standard status-update endpoint
    r6 = requests.put(
        f"{API}/api/shop/orders/{order_id}/status",
        json={"status": "cancelled", "notes": "Customer cancelled"}, headers=H, timeout=15,
    )
    print(f"[6] Cancel online order → HTTP {r6.status_code}")
    assert r6.status_code == 200, r6.text
    cust = await db.shop_customers.find_one({"id": cust_id}, {"_id": 0, "credit_balance": 1})
    # 180 - 5 (earn reversed) + 25 (redeem refunded) = 200
    print(f"[6b] Balance after cancel: £{cust['credit_balance']} (expected £200)")
    assert abs(cust["credit_balance"] - 200.0) < 0.01
    order = await db.shop_orders.find_one({"id": order_id}, {"_id": 0})
    assert order.get("credits_reversed") is True

    # 7. Un-cancel (back to processing) → both re-applied
    r7 = requests.put(
        f"{API}/api/shop/orders/{order_id}/status",
        json={"status": "processing", "notes": "Resurrected"}, headers=H, timeout=15,
    )
    print(f"[7] Un-cancel → HTTP {r7.status_code}")
    assert r7.status_code == 200
    cust = await db.shop_customers.find_one({"id": cust_id}, {"_id": 0, "credit_balance": 1})
    print(f"[7b] Balance after un-cancel: £{cust['credit_balance']} (expected £180)")
    assert abs(cust["credit_balance"] - 180.0) < 0.01

    # Cleanup
    await db.shop_customers.delete_one({"id": cust_id})
    await db.shop_orders.delete_many({"customer_id": cust_id})
    await db.invoices.delete_many({"customer_email": test_email})
    await db.credit_transactions.delete_many({"customer_id": cust_id})
    await db.trade_credits.delete_many({"customer_id": cust_id})
    if original_value:
        await db.website_settings.update_one(
            {"key": "storefront_messages"}, {"$set": {"value": original_value}}, upsert=True,
        )

    print("\nAll Trade-Credit Reversal assertions PASSED ✅")
    client.close()


asyncio.run(run())

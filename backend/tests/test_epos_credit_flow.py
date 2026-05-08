"""
End-to-end smoke test for the EPOS Trade Credit redemption + accrual flow.

Verifies:
  1. Creating an invoice with `credit_redeemed_amount` deducts atomically
     from the trade customer's `credit_balance` and logs a
     `redeemed_in_store` credit_transaction.
  2. amount_outstanding = gross_total - deposits - credit_redeemed
  3. With the in_store_credit master toggle ON, the invoice ALSO accrues
     credit-back at PER-PRODUCT `credit_back_rate` (line-by-line) AND logs
     an `earned_in_store` credit_transaction. Products without a matching
     SKU in supplier_products/tiles fall back to the global default (2%).
  4. Per-line breakdown is stamped on the invoice doc for audit.
  5. Cleanup leaves the DB at baseline.
"""
import os
import asyncio
import uuid
import requests
from motor.motor_asyncio import AsyncIOMotorClient

API = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


async def run():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # Login
    login = requests.post(f"{API}/api/auth/login", json={"email": "admin@test.com", "password": "admin123"}, timeout=15)
    login.raise_for_status()
    token = login.json()["token"]
    H = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Seed a trade customer with £200 credit. Under per-product credit-back
    # the customer-level `credit_rate` is no longer used as the multiplier —
    # rates come from the catalogue. We still seed it for ledger compat.
    cust_id = f"test-credit-{uuid.uuid4().hex[:8]}"
    t_ref = f"T-CRED{uuid.uuid4().hex[:5].upper()}"
    test_email = f"credit-test-{uuid.uuid4().hex[:6]}@example.com"
    test_phone = f"079990{uuid.uuid4().int % 100000:05d}"
    await db.shop_customers.insert_one({
        "id": cust_id, "email": test_email, "phone": test_phone,
        "name": "Credit Test", "business_name": "Credit Test Ltd",
        "is_trade": True, "trade_account_number": t_ref,
        "credit_balance": 200.0, "credit_rate": 5.0,
        "trade_tier": "silver", "trade_discount": 5.0, "total_spent": 0.0,
    })

    # Seed a supplier_products row with a specific 8% credit-back rate so we
    # can verify the per-product lookup actually wins over the global default.
    test_sku_hi = f"TEST-SKU-HI-{uuid.uuid4().hex[:6].upper()}"
    await db.supplier_products.insert_one({
        "id": f"sp-{uuid.uuid4().hex[:8]}",
        "sku": test_sku_hi,
        "credit_back_rate": 8.0,
        "name": "Test Premium Tile (per-product test fixture)",
    })

    # Enable in_store_credit master toggle (snapshot original first)
    sm_doc = await db.website_settings.find_one({"key": "storefront_messages"}, {"_id": 0, "value": 1})
    original_value = (sm_doc or {}).get("value") or {}
    new_value = dict(original_value)
    new_value["in_store_credit"] = {"enabled": True}
    await db.website_settings.update_one(
        {"key": "storefront_messages"},
        {"$set": {"value": new_value}},
        upsert=True,
    )

    # Create invoice: gross £100, deposits £20, credit_redeemed £50 → outstanding £30
    # Line item carries no SKU → falls back to 2% default → £2 earned.
    invoice_payload = {
        "invoice_no": f"INV-TEST-{uuid.uuid4().hex[:6].upper()}",
        "customer_name": "Credit Test",
        "customer_email": test_email,
        "customer_phone": test_phone,
        "customer_address": "1 Test St",
        "date": "01/01/2026",
        "showroom_id": "demo",
        "showroom_name": "Test Showroom",
        "deposits": [{"date": "01/01/2026", "amount": 20.0, "method": "Card", "note": ""}],
        "line_items": [{
            "id": "li-1", "description": "Test Tile", "product_name": "Test Tile",
            "quantity": 1, "boxes": 1, "price": 100.0, "due_price": 100.0,
            "total": 100.0, "isReturn": False,
        }],
        "subtotal": 100.0,
        "vat": 0.0,
        "gross_total": 100.0,
        "total_savings": 0,
        "apply_vat": False,
        "credit_redeemed_amount": 50.0,
        "credit_redeemed_account": t_ref,
    }
    r = requests.post(f"{API}/api/invoices", json=invoice_payload, headers=H, timeout=20)
    print(f"[1] Create invoice → HTTP {r.status_code}")
    assert r.status_code in (200, 201), r.text
    invoice = r.json()
    invoice_id = invoice["invoice_id"]
    invoice_no = invoice["invoice_no"]

    # Re-read the invoice doc to verify all stamped fields
    inv_doc = await db.invoices.find_one({"id": invoice_id}, {"_id": 0})
    print(f"[2] Invoice no={invoice_no}, status={inv_doc['status']}, outstanding={inv_doc['amount_outstanding']}, credit_redeemed={inv_doc.get('credit_redeemed')}, trade_credit_earned={inv_doc.get('trade_credit_earned')}")
    assert abs(inv_doc["amount_outstanding"] - 30.0) < 0.01, f"Expected outstanding £30, got {inv_doc['amount_outstanding']}"
    assert inv_doc["status"] == "deposit_order", f"Expected deposit_order, got {inv_doc['status']}"
    assert abs(float(inv_doc.get("credit_redeemed") or 0) - 50.0) < 0.01
    assert inv_doc.get("credit_redeemed_account") == t_ref
    # No-SKU line falls back to 2% default → £2 of £100 ex-VAT
    assert abs(float(inv_doc.get("trade_credit_earned") or 0) - 2.0) < 0.01, f"Expected earned £2 (2% default), got {inv_doc.get('trade_credit_earned')}"
    # Per-line breakdown stamped for audit
    breakdown = inv_doc.get("trade_credit_breakdown") or []
    assert len(breakdown) == 1, f"Expected 1 line in breakdown, got {len(breakdown)}"
    assert abs(breakdown[0]["rate"] - 2.0) < 0.01, f"Expected line rate 2%, got {breakdown[0]['rate']}"
    assert abs(breakdown[0]["credit"] - 2.0) < 0.01
    # Credit-earned re-engagement email dispatched (may succeed or fail
    # depending on Resend config in env — we just assert the flag was stamped).
    assert "credit_email_sent" in inv_doc, "Expected credit_email_sent flag on invoice"
    print(f"    credit_email_sent={inv_doc['credit_email_sent']} error={inv_doc.get('credit_email_error')}")

    # Verify customer balance: 200 - 50 redeemed + 2 earned = 152
    cust = await db.shop_customers.find_one({"id": cust_id}, {"_id": 0, "credit_balance": 1})
    print(f"[3] Customer balance after = £{cust['credit_balance']} (expected £152)")
    # Print transactions BEFORE asserting balance for diagnostics
    txns_pre = await db.credit_transactions.find({"customer_id": cust_id}, {"_id": 0}).to_list(10)
    print(f"    txns_pre: {[(t['type'], t['amount'], t.get('balance_after')) for t in txns_pre]}")
    assert abs(cust["credit_balance"] - 152.0) < 0.01

    # Verify credit_transactions: 1 redeemed_in_store and 1 earned_in_store
    txns = await db.credit_transactions.find({"invoice_id": invoice_id}, {"_id": 0}).to_list(10)
    types = sorted(t["type"] for t in txns)
    print(f"[4] Credit transactions: {types}")
    print(f"    Details: {[(t['type'], t['amount'], t.get('balance_after')) for t in txns]}")
    assert types == ["earned_in_store", "redeemed_in_store"]

    # ── Per-product rate test ─────────────────────────────────────────────
    # Mixed-rate invoice: one premium-SKU line (8%) + one no-SKU line (2%
    # default). Expect blended math: (8% of £50) + (2% of £50) = £5.00.
    mixed_payload = dict(invoice_payload)
    mixed_payload["invoice_no"] = f"INV-MIX-{uuid.uuid4().hex[:6].upper()}"
    mixed_payload["credit_redeemed_amount"] = 0  # keep this test focused on accrual
    mixed_payload["deposits"] = [{"date": "01/01/2026", "amount": 100.0, "method": "Card", "note": ""}]
    mixed_payload["line_items"] = [
        {
            "id": "li-mix-1", "description": "Premium Tile", "product_name": "Premium Tile",
            "sku": test_sku_hi, "quantity": 1, "boxes": 1,
            "price": 50.0, "due_price": 50.0, "total": 50.0, "isReturn": False,
        },
        {
            "id": "li-mix-2", "description": "Generic Tile", "product_name": "Generic Tile",
            "quantity": 1, "boxes": 1,
            "price": 50.0, "due_price": 50.0, "total": 50.0, "isReturn": False,
        },
    ]
    mixed_payload["subtotal"] = 100.0
    mixed_payload["gross_total"] = 100.0
    mr = requests.post(f"{API}/api/invoices", json=mixed_payload, headers=H, timeout=20)
    assert mr.status_code in (200, 201), mr.text
    mixed_inv_id = mr.json()["invoice_id"]
    mixed_doc = await db.invoices.find_one({"id": mixed_inv_id}, {"_id": 0})
    print(f"[6] Mixed-rate invoice earned={mixed_doc.get('trade_credit_earned')} blended={mixed_doc.get('trade_credit_rate')}")
    assert abs(float(mixed_doc.get("trade_credit_earned") or 0) - 5.0) < 0.01, \
        f"Expected mixed £5 (8% of £50 + 2% of £50), got {mixed_doc.get('trade_credit_earned')}"
    mb = mixed_doc.get("trade_credit_breakdown") or []
    rates = sorted(line["rate"] for line in mb)
    assert rates == [2.0, 8.0], f"Expected per-line rates [2,8], got {rates}"
    # Blended rate should be 5% (£5 ÷ £100 × 100)
    assert abs(float(mixed_doc.get("trade_credit_rate") or 0) - 5.0) < 0.1

    # ── Credit-back-rates preview endpoint (frontend live preview) ────────
    preview = requests.post(
        f"{API}/api/invoices/credit-back-rates",
        json={"line_items": [
            {"sku": test_sku_hi, "quantity": 2, "price": 50, "due_price": 50},
            {"sku": "DOES-NOT-EXIST", "quantity": 1, "price": 100, "due_price": 100},
        ]},
        headers=H, timeout=15,
    )
    assert preview.status_code == 200, preview.text
    pjson = preview.json()
    # 8% × £100 + 2% × £100 = £10 total
    print(f"[7] Preview endpoint total={pjson['total_credit']} blended={pjson['blended_rate']}")
    assert abs(pjson["total_credit"] - 10.0) < 0.01
    assert abs(pjson["default_rate"] - 2.0) < 0.01

    # Now test atomic guard — try redeeming more than balance
    over_payload = dict(invoice_payload)
    over_payload["invoice_no"] = f"INV-OVER-{uuid.uuid4().hex[:6].upper()}"
    over_payload["credit_redeemed_amount"] = 9999.0
    over_payload["line_items"] = [{
        "id": "li-2", "description": "Over", "product_name": "Over",
        "quantity": 1, "boxes": 1, "price": 100.0, "due_price": 100.0,
        "total": 100.0, "isReturn": False,
    }]
    r2 = requests.post(f"{API}/api/invoices", json=over_payload, headers=H, timeout=20)
    print(f"[5] Over-redemption attempt → HTTP {r2.status_code}: {r2.json().get('detail', '')[:120]}")
    assert r2.status_code == 400

    # Cleanup
    await db.invoices.delete_one({"id": invoice_id})
    await db.invoices.delete_one({"id": mixed_inv_id})
    # Also clean up over-redemption side-effects (if any invoice doc was created before the credit guard)
    await db.invoices.delete_many({"customer_email": test_email})
    await db.credit_transactions.delete_many({"customer_id": cust_id})
    await db.shop_customers.delete_one({"id": cust_id})
    await db.supplier_products.delete_one({"sku": test_sku_hi})
    # Restore original storefront_messages
    if original_value:
        await db.website_settings.update_one(
            {"key": "storefront_messages"},
            {"$set": {"value": original_value}},
            upsert=True,
        )
    else:
        # If the doc didn't exist before, just remove our toggle
        await db.website_settings.update_one(
            {"key": "storefront_messages"},
            {"$unset": {"value.in_store_credit": ""}},
        )

    print("\nAll EPOS Trade Credit assertions PASSED ✅")
    client.close()


asyncio.run(run())

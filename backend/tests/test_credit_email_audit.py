"""
Smoke test for the Recent Credit-Earned Emails admin endpoints + UI.
- Seeds 1 SENT + 1 FAILED entry (no real Resend call — we just stamp the
  flags directly on test invoices).
- Hits the listing endpoint.
- Hits the resend endpoint on the failed entry.
- Cleans up.
"""
import os
import asyncio
import uuid
from datetime import datetime, timezone, timedelta
import requests
from motor.motor_asyncio import AsyncIOMotorClient

API = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


async def run():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    login = requests.post(f"{API}/api/auth/login", json={"email": "admin@test.com", "password": "admin123"}, timeout=15)
    token = login.json()["token"]
    H = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Seed a trade customer
    cust_id = f"creditlog-cust-{uuid.uuid4().hex[:6]}"
    t_ref = f"T-LOG{uuid.uuid4().hex[:5].upper()}"
    test_email = f"creditlog-{uuid.uuid4().hex[:6]}@example.com"
    await db.shop_customers.insert_one({
        "id": cust_id, "email": test_email, "phone": "07900111222",
        "name": "Log Test", "business_name": "LogTest Ltd",
        "is_trade": True, "trade_account_number": t_ref,
        "credit_balance": 100.0, "credit_rate": 5.0,
    })

    # Seed two invoices manually — one sent OK, one failed
    sent_id = f"creditlog-inv-{uuid.uuid4().hex[:6]}"
    failed_id = f"creditlog-inv-{uuid.uuid4().hex[:6]}"
    now = datetime.now(timezone.utc)
    await db.invoices.insert_many([
        {
            "id": sent_id, "invoice_no": f"INV-LOG-{uuid.uuid4().hex[:4].upper()}",
            "customer_email": test_email, "customer_name": "Log Test",
            "trade_account_number": t_ref, "trade_business_name": "LogTest Ltd",
            "trade_credit_earned": 12.50, "trade_credit_rate": 5.0,
            "gross_total": 300.0, "subtotal": 250.0,
            "showroom_name": "Chingford",
            "credit_email_sent": True, "credit_email_error": None,
            "credit_email_at": (now - timedelta(minutes=2)).isoformat(),
            "created_at": (now - timedelta(minutes=2)).isoformat(),
            "line_items": [], "deposits": [],
        },
        {
            "id": failed_id, "invoice_no": f"INV-LOG-{uuid.uuid4().hex[:4].upper()}",
            "customer_email": test_email, "customer_name": "Log Test",
            "trade_account_number": t_ref, "trade_business_name": "LogTest Ltd",
            "trade_credit_earned": 7.25, "trade_credit_rate": 5.0,
            "gross_total": 175.0, "subtotal": 145.0,
            "showroom_name": "Chingford",
            "credit_email_sent": False,
            "credit_email_error": "Rate limit exceeded (test stub)",
            "credit_email_at": (now - timedelta(hours=1)).isoformat(),
            "created_at": (now - timedelta(hours=1)).isoformat(),
            "line_items": [], "deposits": [],
        },
    ])

    # 1. Listing endpoint
    r = requests.get(f"{API}/api/invoices/credit-emails/recent?limit=20", headers=H, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    print(f"[1] Listing → {data['total']} rows ({data['sent_count']} sent, {data['failed_count']} failed)")
    ours = [row for row in data["rows"] if row["id"] in (sent_id, failed_id)]
    assert len(ours) == 2
    sent_row = next(row for row in ours if row["id"] == sent_id)
    failed_row = next(row for row in ours if row["id"] == failed_id)
    assert sent_row["credit_email_sent"] is True
    assert failed_row["credit_email_sent"] is False
    assert failed_row["credit_email_error"] == "Rate limit exceeded (test stub)"
    print(f"    Sent row: {sent_row['invoice_no']} £{sent_row['trade_credit_earned']}")
    print(f"    Failed row: {failed_row['invoice_no']} error={failed_row['credit_email_error']}")

    # 2. Resend endpoint on the failed row
    r2 = requests.post(f"{API}/api/invoices/{failed_id}/credit-emails/resend", headers=H, timeout=20)
    print(f"[2] Resend failed row → HTTP {r2.status_code} body={r2.json()}")
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert "ok" in body and "invoice_no" in body
    # The resend re-stamps the timestamp + sent flag on the doc
    inv_doc = await db.invoices.find_one({"id": failed_id}, {"_id": 0})
    print(f"    After resend: sent={inv_doc['credit_email_sent']} resent_by={inv_doc.get('credit_email_resent_by')}")
    assert inv_doc.get("credit_email_resent_by") == "admin@test.com"

    # 3. Resend on a non-credit invoice → 400
    no_credit_id = f"creditlog-zero-{uuid.uuid4().hex[:6]}"
    await db.invoices.insert_one({
        "id": no_credit_id, "invoice_no": "INV-ZERO",
        "customer_email": test_email, "trade_credit_earned": 0,
        "credit_email_at": now.isoformat(), "credit_email_sent": False,
        "line_items": [], "deposits": [],
    })
    r3 = requests.post(f"{API}/api/invoices/{no_credit_id}/credit-emails/resend", headers=H, timeout=15)
    print(f"[3] Resend no-credit invoice → HTTP {r3.status_code}: {r3.json().get('detail', '')[:80]}")
    assert r3.status_code == 400

    # 4. Resend on bogus invoice → 404
    r4 = requests.post(f"{API}/api/invoices/does-not-exist-xyz/credit-emails/resend", headers=H, timeout=15)
    print(f"[4] Resend bogus id → HTTP {r4.status_code}")
    assert r4.status_code == 404

    # Cleanup
    await db.invoices.delete_many({"id": {"$in": [sent_id, failed_id, no_credit_id]}})
    await db.shop_customers.delete_one({"id": cust_id})
    print("\nAll Credit-Email Audit assertions PASSED ✅")
    client.close()


asyncio.run(run())

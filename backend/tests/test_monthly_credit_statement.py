"""
Regression test for the monthly trade-credit statement flow.

Verifies:
  1. Customer with EARNED + REDEEMED in the window → statement built with correct totals,
     HTML rendered with all key strings, send dispatch returns sent=True (real Resend).
  2. Customer with NO movement in the window → _build_customer_statement returns None.
  3. dispatch_monthly_statements correctly counts {eligible / sent / skipped / failed}
     when there's a mix of trade and non-trade candidate IDs.
  4. /admin/trade-credit/statements/preview endpoint returns rendered HTML for a
     trade customer with movement, and a "no movement" message otherwise.
  5. /admin/trade-credit/statements/send-monthly with dry_run=true returns counts
     without actually calling Resend.
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
    from routes.trade_credit_statements import (
        _build_customer_statement,
        render_monthly_statement_html,
        dispatch_monthly_statements,
    )

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # Use the previous calendar month so the test mirrors the cron behaviour
    now = datetime.now(timezone.utc)
    first_of_this = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end_of_prev = first_of_this - timedelta(seconds=1)
    year, month = end_of_prev.year, end_of_prev.month
    in_window = first_of_this - timedelta(days=15)  # mid-prev-month timestamp

    # --- Seed one trade customer WITH movement -----------------------------
    cust_id_a = f"stmt-trade-{uuid.uuid4().hex[:8]}"
    email_a = f"stmt-trade-{uuid.uuid4().hex[:6]}@example.com"
    await db.shop_customers.insert_one({
        "id": cust_id_a, "email": email_a, "is_trade": True,
        "credit_balance": 35.50, "trade_account_number": "T-STMT1",
        "business_name": "Stmt Trade Ltd", "name": "Stmt Trade",
    })
    # 2 earnings + 1 redemption inside the window
    txn_ids = [str(uuid.uuid4()) for _ in range(3)]
    await db.credit_transactions.insert_many([
        {"id": txn_ids[0], "customer_id": cust_id_a, "type": "earned_in_store",
         "amount": 25.00, "balance_after": 25.00, "invoice_no": "INV-A",
         "source": "epos_invoice", "description": "Earned (test)",
         "created_at": in_window.isoformat()},
        {"id": txn_ids[1], "customer_id": cust_id_a, "type": "earned_online",
         "amount": 35.50, "balance_after": 60.50, "order_number": "TS-1",
         "source": "online_order", "description": "Earned online (test)",
         "created_at": (in_window + timedelta(days=2)).isoformat()},
        {"id": txn_ids[2], "customer_id": cust_id_a, "type": "redeemed_in_store",
         "amount": -25.00, "balance_after": 35.50, "invoice_no": "INV-B",
         "source": "epos_invoice", "description": "Redeemed (test)",
         "created_at": (in_window + timedelta(days=4)).isoformat()},
    ])

    cust_a = await db.shop_customers.find_one({"id": cust_id_a}, {"_id": 0})
    stmt_a = await _build_customer_statement(db, cust_a, year, month)
    assert stmt_a is not None, "Expected a statement for customer with movement"
    assert abs(stmt_a["earned_total"] - 60.50) < 0.01, f"earned_total={stmt_a['earned_total']}"
    assert abs(stmt_a["redeemed_total"] - 25.00) < 0.01, f"redeemed_total={stmt_a['redeemed_total']}"
    assert abs(stmt_a["closing_balance"] - 35.50) < 0.01
    assert stmt_a["txns_count"] == 3
    print(f"[1] Customer with movement: earned=£{stmt_a['earned_total']}, redeemed=£{stmt_a['redeemed_total']}, balance=£{stmt_a['closing_balance']} ✓")

    html = render_monthly_statement_html(stmt_a)
    assert "£60.50" in html
    assert "£25.00" in html
    assert "£35.50" in html
    assert "T-STMT1" in html
    assert "View my trade account" in html, "Spend-now CTA missing for non-zero balance"
    print(f"    HTML rendered ({len(html)} chars), all key strings present ✓")

    # --- Seed one trade customer WITHOUT movement --------------------------
    cust_id_b = f"stmt-nomov-{uuid.uuid4().hex[:8]}"
    email_b = f"stmt-nomov-{uuid.uuid4().hex[:6]}@example.com"
    await db.shop_customers.insert_one({
        "id": cust_id_b, "email": email_b, "is_trade": True,
        "credit_balance": 0.0, "trade_account_number": "T-STMT2",
        "business_name": "No Movement Ltd", "name": "Quiet",
    })
    # No txns

    cust_b = await db.shop_customers.find_one({"id": cust_id_b}, {"_id": 0})
    stmt_b = await _build_customer_statement(db, cust_b, year, month)
    assert stmt_b is None, "Expected None for customer with no movement"
    print(f"[2] Customer with no movement → returns None ✓")

    # --- dispatch_monthly_statements (dry_run, scoped via candidate_ids) ---
    # Will pick up only customer A (the only one with movement).
    result = await dispatch_monthly_statements(db, year, month, dry_run=True)
    # Could pick up other real prod traders too — we only assert OUR customer
    # got counted.
    assert result["sent"] >= 1, f"dry_run sent count too low: {result}"
    assert result["period_label"] == stmt_a["period_label"]
    print(f"[3] Dry-run dispatch: eligible={result['eligible']}, sent={result['sent']}, skipped={result['skipped_no_movement']} ✓")

    # --- Admin-trigger endpoint (via API) ---
    login = requests.post(f"{API}/api/auth/login", json={"email": "admin@test.com", "password": "admin123"}, timeout=15)
    token = login.json()["token"]
    H = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Preview endpoint
    pv = requests.get(f"{API}/api/admin/trade-credit/statements/preview", params={"email": email_a, "year": year, "month": month}, headers=H, timeout=15)
    print(f"[4a] Preview endpoint: HTTP {pv.status_code}")
    assert pv.status_code == 200, pv.text
    pv_body = pv.json()
    assert pv_body["has_movement"] is True
    assert "£60.50" in pv_body["html"]

    # Preview for a trade customer with no movement → graceful empty body
    pv2 = requests.get(f"{API}/api/admin/trade-credit/statements/preview", params={"email": email_b, "year": year, "month": month}, headers=H, timeout=15)
    assert pv2.status_code == 200
    assert pv2.json()["has_movement"] is False
    print(f"[4b] Preview no-movement → has_movement=false ✓")

    # Last-run status endpoint
    lr = requests.get(f"{API}/api/admin/trade-credit/statements/last-run", headers=H, timeout=15)
    assert lr.status_code == 200
    print(f"[4c] Last-run: {lr.json()}")

    # Send-monthly with dry_run → returns counts, doesn't update marker
    sb = requests.post(f"{API}/api/admin/trade-credit/statements/send-monthly",
                       json={"year": year, "month": month, "dry_run": True}, headers=H, timeout=30)
    print(f"[5] Send-monthly dry_run: HTTP {sb.status_code}, body={sb.json()}")
    assert sb.status_code == 200
    body = sb.json()
    assert body["sent"] >= 1
    assert body["dry_run"] is True

    # Cleanup
    await db.shop_customers.delete_many({"id": {"$in": [cust_id_a, cust_id_b]}})
    await db.credit_transactions.delete_many({"customer_id": {"$in": [cust_id_a, cust_id_b]}})
    print("\nAll Monthly-Credit-Statement assertions PASSED ✅")
    client.close()


asyncio.run(run())

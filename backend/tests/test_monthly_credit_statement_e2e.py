"""End-to-end: verify the monthly statement actually sends via Resend."""
import os, sys, asyncio, uuid
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


async def run():
    sys.path.insert(0, "/app/backend")
    from routes.trade_credit_statements import _send_one_statement, _build_customer_statement

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    now = datetime.now(timezone.utc)
    first_of_this = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end_of_prev = first_of_this - timedelta(seconds=1)
    year, month = end_of_prev.year, end_of_prev.month
    in_window = first_of_this - timedelta(days=10)

    cust_id = f"stmt-e2e-{uuid.uuid4().hex[:8]}"
    email = f"stmt-e2e-{uuid.uuid4().hex[:6]}@example.com"
    await db.shop_customers.insert_one({
        "id": cust_id, "email": email, "is_trade": True,
        "credit_balance": 22.50, "trade_account_number": "T-E2E1",
        "business_name": "E2E Trade Ltd", "name": "E2E",
    })
    await db.credit_transactions.insert_many([
        {"id": str(uuid.uuid4()), "customer_id": cust_id, "type": "earned_in_store",
         "amount": 62.50, "balance_after": 62.50, "invoice_no": "INV-E2E-A",
         "source": "epos_invoice", "description": "Earned (e2e test)",
         "created_at": in_window.isoformat()},
        {"id": str(uuid.uuid4()), "customer_id": cust_id, "type": "redeemed_in_store",
         "amount": -40.00, "balance_after": 22.50, "invoice_no": "INV-E2E-B",
         "source": "epos_invoice", "description": "Redeemed (e2e test)",
         "created_at": (in_window + timedelta(days=3)).isoformat()},
    ])

    cust = await db.shop_customers.find_one({"id": cust_id}, {"_id": 0})
    stmt = await _build_customer_statement(db, cust, year, month)
    assert stmt is not None
    print(f"[setup] Statement built: earned £{stmt['earned_total']}, redeemed £{stmt['redeemed_total']}, balance £{stmt['closing_balance']}")

    res = await _send_one_statement(stmt)
    print(f"[1] Real Resend dispatch → {res}")
    assert res.get("sent") is True, f"Expected sent=True, got {res}"

    # Cleanup
    await db.shop_customers.delete_one({"id": cust_id})
    await db.credit_transactions.delete_many({"customer_id": cust_id})
    print("\nMonthly statement E2E PASS ✅")
    client.close()


asyncio.run(run())

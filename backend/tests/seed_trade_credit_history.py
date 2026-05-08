"""
Seed a trade customer + 3 credit events for frontend testing and print the
login credentials. Does NOT clean up (frontend testing will use this data).
"""
import os
import sys
import asyncio
import uuid
from datetime import datetime, timezone, timedelta

import bcrypt
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


async def run():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    cust_id = f"fe-hist-{uuid.uuid4().hex[:8]}"
    t_ref = f"T-FEH{uuid.uuid4().hex[:5].upper()}"
    test_email = f"fe-hist-{uuid.uuid4().hex[:6]}@example.com"
    raw_pwd = "TestPass1234!"
    fresh_hash = bcrypt.hashpw(raw_pwd.encode(), bcrypt.gensalt()).decode()

    await db.shop_customers.insert_one({
        "id": cust_id,
        "email": test_email,
        "password": fresh_hash,
        "name": "FE History Test",
        "business_name": "FE History Test Ltd",
        "is_trade": True,
        "trade_account_number": t_ref,
        "credit_balance": 7.0,
        "credit_rate": 5.0,
        "trade_discount": 5.0,
        "approved": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    now = datetime.now(timezone.utc)

    # Online earn (trade_credits)
    await db.trade_credits.insert_one({
        "id": str(uuid.uuid4()),
        "customer_id": cust_id,
        "order_id": "ord-online-1",
        "order_number": "TS-FE-ONL",
        "type": "earn",
        "amount": 5.0,
        "balance_after": 5.0,
        "description": "Credit back from order TS-FE-ONL",
        "created_at": (now - timedelta(days=2)).isoformat(),
    })

    # EPOS earn with breakdown
    inv_id = str(uuid.uuid4())
    await db.invoices.insert_one({
        "id": inv_id,
        "invoice_no": "INV-FE-EPOS",
        "customer_email": test_email,
        "trade_account_number": t_ref,
        "subtotal": 100.0,
        "gross_total": 100.0,
        "trade_credit_earned": 5.0,
        "trade_credit_rate": 5.0,
        "trade_credit_breakdown": [
            {"product_id": "p1", "sku": "PREMIUM-1", "product_name": "Premium Marble Tile XL", "quantity": 1, "net": 50.0, "rate": 8.0, "credit": 4.0},
            {"product_id": "p2", "sku": "GENERIC-1", "product_name": "Generic Sealer", "quantity": 1, "net": 50.0, "rate": 2.0, "credit": 1.0},
        ],
        "created_at": (now - timedelta(hours=2)).isoformat(),
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
        "invoice_no": "INV-FE-EPOS",
        "description": "Credit back from in-store invoice INV-FE-EPOS",
        "created_at": (now - timedelta(hours=2)).isoformat(),
    })

    # EPOS redeem
    await db.credit_transactions.insert_one({
        "id": str(uuid.uuid4()),
        "customer_id": cust_id,
        "trade_account_number": t_ref,
        "type": "redeemed_in_store",
        "amount": -3.0,
        "balance_after": 7.0,
        "source": "epos_invoice",
        "invoice_id": "ignored",
        "invoice_no": "INV-FE-RED",
        "description": "Credit redeemed at till on invoice INV-FE-RED",
        "created_at": (now - timedelta(minutes=30)).isoformat(),
    })

    print("=== SEED COMPLETE ===")
    print(f"EMAIL={test_email}")
    print(f"PASSWORD={raw_pwd}")
    print(f"CUST_ID={cust_id}")
    print(f"INV_ID={inv_id}")
    client.close()


asyncio.run(run())

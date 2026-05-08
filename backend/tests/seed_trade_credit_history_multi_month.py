"""
Extended seed: trader with 4 credit events spanning 3 months (Feb/Mar/Apr 2026
via days=70/40/40/10 relative offsets). Prints login creds.
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

    cust_id = f"fe-mm-{uuid.uuid4().hex[:8]}"
    t_ref = f"T-FEMM{uuid.uuid4().hex[:4].upper()}"
    test_email = f"fe-mm-{uuid.uuid4().hex[:6]}@example.com"
    raw_pwd = "TestPass1234!"
    fresh_hash = bcrypt.hashpw(raw_pwd.encode(), bcrypt.gensalt()).decode()

    await db.shop_customers.insert_one({
        "id": cust_id,
        "email": test_email,
        "password": fresh_hash,
        "name": "FE MultiMonth",
        "business_name": "FE MultiMonth Ltd",
        "is_trade": True,
        "trade_account_number": t_ref,
        "credit_balance": 8.0,
        "credit_rate": 5.0,
        "trade_discount": 5.0,
        "approved": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    now = datetime.now(timezone.utc)

    # ---- Event A: oldest — ~70 days ago (earn, online)
    await db.trade_credits.insert_one({
        "id": str(uuid.uuid4()),
        "customer_id": cust_id,
        "order_id": "ord-mm-old",
        "order_number": "TS-MM-OLD",
        "type": "earn",
        "amount": 4.0,
        "balance_after": 4.0,
        "description": "Credit back from order TS-MM-OLD",
        "created_at": (now - timedelta(days=70)).isoformat(),
    })

    # ---- Event B: mid — ~40 days ago (EPOS earn w/ breakdown)
    inv_id = str(uuid.uuid4())
    await db.invoices.insert_one({
        "id": inv_id,
        "invoice_no": "INV-MM-MID",
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
        "created_at": (now - timedelta(days=40)).isoformat(),
    })
    await db.credit_transactions.insert_one({
        "id": str(uuid.uuid4()),
        "customer_id": cust_id,
        "trade_account_number": t_ref,
        "type": "earned_in_store",
        "amount": 5.0,
        "balance_after": 9.0,
        "source": "epos_invoice",
        "invoice_id": inv_id,
        "invoice_no": "INV-MM-MID",
        "description": "Credit back from in-store invoice INV-MM-MID",
        "created_at": (now - timedelta(days=40)).isoformat(),
    })

    # ---- Event C: mid — ~38 days ago (EPOS redeem, same month as B)
    await db.credit_transactions.insert_one({
        "id": str(uuid.uuid4()),
        "customer_id": cust_id,
        "trade_account_number": t_ref,
        "type": "redeemed_in_store",
        "amount": -2.0,
        "balance_after": 7.0,
        "source": "epos_invoice",
        "invoice_id": "ignored-mm",
        "invoice_no": "INV-MM-RED",
        "description": "Credit redeemed at till on invoice INV-MM-RED",
        "created_at": (now - timedelta(days=38)).isoformat(),
    })

    # ---- Event D: newest — ~10 days ago (earn, online)
    await db.trade_credits.insert_one({
        "id": str(uuid.uuid4()),
        "customer_id": cust_id,
        "order_id": "ord-mm-new",
        "order_number": "TS-MM-NEW",
        "type": "earn",
        "amount": 3.0,
        "balance_after": 8.0,
        "description": "Credit back from order TS-MM-NEW",
        "created_at": (now - timedelta(days=10)).isoformat(),
    })

    print("=== MULTI-MONTH SEED COMPLETE ===")
    print(f"EMAIL={test_email}")
    print(f"PASSWORD={raw_pwd}")
    print(f"CUST_ID={cust_id}")
    print(f"INV_ID={inv_id}")
    client.close()


asyncio.run(run())

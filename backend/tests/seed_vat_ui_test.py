"""Seed a trade customer + order, then print credentials for UI testing."""
import os
import sys
import asyncio
import uuid
from datetime import datetime, timezone

import bcrypt
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


async def run():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    raw_pwd = "VatUiTest123!"
    pwd_hash = bcrypt.hashpw(raw_pwd.encode(), bcrypt.gensalt()).decode()

    cust_id = f"vat-ui-{uuid.uuid4().hex[:8]}"
    test_email = f"vat-ui-{uuid.uuid4().hex[:6]}@example.com"

    await db.shop_customers.insert_one({
        "id": cust_id, "email": test_email, "password": pwd_hash,
        "name": "VAT UI Tester", "business_name": "VAT UI Tester Ltd",
        "is_trade": True, "trade_account_number": "T-VATUI01",
        "approved": True, "credit_balance": 0.0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    # Create 2 orders so we can verify both surfaces
    for i in range(2):
        order_id = str(uuid.uuid4())
        order_no = f"INV-{uuid.uuid4().hex[:6].upper()}"
        await db.shop_orders.insert_one({
            "id": order_id,
            "order_number": order_no,
            "customer_id": cust_id,
            "customer_email": test_email,
            "customer_name": "VAT UI Tester",
            "delivery_method": "delivery",
            "delivery_address": "1 UI Test Lane, London, NW1 1AA",
            "items": [
                {"product_id": "p1", "name": "Premium Marble Tile",
                 "variant": "600x600", "price": 10.0, "quantity": 5},
            ],
            "subtotal": 50.0,
            "delivery_fee": 0.0,
            "total": 60.0,
            "status": "delivered",
            "savings_meta": {"total_saved": 5.0, "lines_with_savings": 1,
                             "percent_off_retail": 10},
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        print(f"Created order {order_no} ({order_id})")

    print(f"\n--- CREDENTIALS ---")
    print(f"EMAIL={test_email}")
    print(f"PASSWORD={raw_pwd}")
    print(f"CUSTID={cust_id}")
    client.close()


asyncio.run(run())

"""Seed fixture for iteration 132 frontend test — creates a trade customer
AND a supplier_products entry with 8% credit_back_rate so /admin/invoice
can render the green "will earn" pill with breakdown + copy button.

Usage:
  python test_epos_credit_breakdown_copy_seed.py seed   -> prints JSON fixture
  python test_epos_credit_breakdown_copy_seed.py cleanup <customer_id> <sp_id>
"""
import os, sys, json, uuid, asyncio
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


async def seed():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    uid = uuid.uuid4().hex[:8]
    sku = f"BD-SKU-{uuid.uuid4().hex[:6].upper()}"
    email = f"bd-{uid}@example.com"
    t_ref = f"T-{uuid.uuid4().hex[:5].upper()}"
    customer_id = f"test-bd-{uid}"
    sp_id = f"sp-{uuid.uuid4().hex[:8]}"

    await db.shop_customers.insert_one({
        "id": customer_id,
        "email": email,
        "name": "Breakdown Copy Tester",
        "business_name": "Acme Tiles Ltd",
        "phone": "+441234567890",
        "is_trade": True,
        "trade_account_number": t_ref,
        "trade_tier": "bronze",
        "credit_balance": 200.0,
        "credit_rate": 2.0,
    })
    await db.supplier_products.insert_one({
        "id": sp_id,
        "sku": sku,
        "credit_back_rate": 8.0,
        "name": "Premium Tile (copy fixture)",
    })
    client.close()
    print(json.dumps({
        "customer_id": customer_id,
        "sp_id": sp_id,
        "email": email,
        "sku": sku,
        "t_ref": t_ref,
    }))


async def cleanup(customer_id, sp_id):
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    await db.shop_customers.delete_one({"id": customer_id})
    await db.supplier_products.delete_one({"id": sp_id})
    client.close()
    print("cleaned")


if __name__ == "__main__":
    if sys.argv[1] == "seed":
        asyncio.run(seed())
    else:
        asyncio.run(cleanup(sys.argv[2], sys.argv[3]))

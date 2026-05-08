"""Cleanup seeded VAT UI test customers + orders."""
import os, asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def run():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    cs = await db.shop_customers.delete_many({"trade_account_number": "T-VATUI01"})
    os_ = await db.shop_orders.delete_many({"customer_email": {"$regex": "^vat-ui-"}})
    print(f"Deleted customers={cs.deleted_count} orders={os_.deleted_count}")
    client.close()
asyncio.run(run())

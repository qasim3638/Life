"""Seed checkout_settings for launch testing (free sample + payments + delivery)."""
import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


async def main():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    existing = await db.website_settings.find_one({"key": "checkout_settings"})
    cur = (existing or {}).get("value", {}) or {}
    delivery = cur.get("delivery", {}) or {}
    delivery.setdefault("free_threshold", 500)
    delivery.setdefault("default_fee", 49.99)

    payments = cur.get("payments", {}) or {}
    payments["paypal_enabled"] = True
    payments["klarna_enabled"] = True
    payments["wallet_express_enabled"] = True

    free_sample = cur.get("free_sample", {}) or {}
    free_sample.update({
        "enabled": True,
        "threshold": 100,
        "fulfillment_mode": "smart",
        "direct_ship_suppliers": ["Ultra Tile"],
        "locked_text": "Spend <strong>£{remaining}</strong> more to unlock a <strong>FREE sample</strong>",
        "unlocked_text_pack": "🎁 You unlocked a FREE sample — add choice in order notes.",
        "unlocked_text_separate": "🎁 FREE sample unlocked — we will post separately. Add choice in order notes.",
    })

    new_value = {**cur, "delivery": delivery, "payments": payments, "free_sample": free_sample}
    await db.website_settings.update_one(
        {"key": "checkout_settings"},
        {"$set": {"key": "checkout_settings", "value": new_value}},
        upsert=True,
    )
    print("Seeded checkout_settings successfully.")
    doc = await db.website_settings.find_one({"key": "checkout_settings"}, {"_id": 0})
    print("payments:", doc["value"].get("payments"))
    print("free_sample:", doc["value"].get("free_sample"))
    print("delivery free_threshold:", doc["value"].get("delivery", {}).get("free_threshold"))
    print("delivery default_fee:", doc["value"].get("delivery", {}).get("default_fee"))


if __name__ == "__main__":
    asyncio.run(main())

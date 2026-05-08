"""Smoke test for POST /api/invoices/credit-back-rates breakdown payload (Iteration 131).

Asserts that the live preview endpoint still returns:
  - total_credit, blended_rate, default_rate top-level fields
  - breakdown[] array with one entry per line item containing
    product_name, sku, rate, net, credit fields used by the EPOS chip
    "Show breakdown" panel.
"""
import os
import uuid
import asyncio
import requests
from motor.motor_asyncio import AsyncIOMotorClient

API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


async def run():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # Login
    r = requests.post(f"{API}/api/auth/login",
                      json={"email": "admin@test.com", "password": "admin123"}, timeout=15)
    r.raise_for_status()
    token = r.json()["token"]
    H = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Seed an 8% credit-back SKU so we can verify per-product lookup wins
    sku_hi = f"BD-SKU-{uuid.uuid4().hex[:6].upper()}"
    sp_id = f"sp-{uuid.uuid4().hex[:8]}"
    await db.supplier_products.insert_one({
        "id": sp_id, "sku": sku_hi, "credit_back_rate": 8.0,
        "name": "Premium Tile (breakdown fixture)",
    })

    try:
        payload = {
            "line_items": [
                {"product_name": "Premium Tile", "sku": sku_hi, "quantity": 1,
                 "price": 50.0},
                {"product_name": "Generic Tile", "sku": "NO-SUCH-SKU", "quantity": 1,
                 "price": 50.0},
            ],
            "apply_vat": False,
        }
        resp = requests.post(f"{API}/api/invoices/credit-back-rates",
                             json=payload, headers=H, timeout=15)
        assert resp.status_code == 200, f"got {resp.status_code}: {resp.text}"
        data = resp.json()

        # Top-level fields
        assert "total_credit" in data, data
        assert "blended_rate" in data, data
        assert "breakdown" in data and isinstance(data["breakdown"], list), data
        assert len(data["breakdown"]) == 2, data

        # Verify per-row fields used by the UI
        b0, b1 = data["breakdown"]
        for row in (b0, b1):
            for key in ("product_name", "sku", "rate", "net", "credit"):
                assert key in row, f"missing {key} in {row}"

        # Premium row: 8% × £50 = £4
        premium = next(r for r in data["breakdown"] if r["sku"] == sku_hi)
        assert abs(premium["rate"] - 8.0) < 0.01, premium
        assert abs(premium["net"] - 50.0) < 0.01, premium
        assert abs(premium["credit"] - 4.0) < 0.01, premium

        # Generic row: 2% × £50 = £1 (global default)
        generic = next(r for r in data["breakdown"] if r["sku"] != sku_hi)
        assert abs(generic["rate"] - 2.0) < 0.01, generic
        assert abs(generic["credit"] - 1.0) < 0.01, generic

        # Total = £5
        assert abs(data["total_credit"] - 5.0) < 0.01, data
        # Blended = (4+1) / 100 = 5%
        assert abs(data["blended_rate"] - 5.0) < 0.01, data

        print("PASS: /credit-back-rates breakdown payload OK")
        print(f"  total_credit=£{data['total_credit']:.2f} blended={data['blended_rate']:.1f}%")
        for row in data["breakdown"]:
            print(f"  - {row['product_name']}: {row['rate']}% × £{row['net']:.2f} = £{row['credit']:.2f}")
    finally:
        await db.supplier_products.delete_one({"id": sp_id})
        client.close()


if __name__ == "__main__":
    asyncio.run(run())

"""
Seed a single £1.50 "Order a Sample" product into the live shop.
Idempotent — safe to re-run; updates if it already exists.

Usage on Railway (or any backend shell):
    python scripts/seed_sample_product.py

Or one-liner inline (paste in Railway's "Run a command" box on the backend
service, all on one line):

    python -c "import asyncio; exec(open('scripts/seed_sample_product.py').read())"

What it creates (visible to customers immediately):
  - SKU: TS-SAMPLE-01
  - Slug: order-a-sample (URL: /shop/tile/order-a-sample)
  - Price: £1.50
  - Stock: 999 (effectively unlimited)
  - Category: Samples
  - Available for free Click & Collect or low-cost delivery

After your launch test, you can:
  - Keep it (it's a real product that converts samples → big orders)
  - Edit price/copy in admin → Products
  - Hide it by setting `is_active=False` in admin
"""
import asyncio
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

SKU = "TS-SAMPLE-01"
SLUG = "order-a-sample"
NAME = "Order a Sample"
DISPLAY_NAME = "Order a Sample"
PRICE = 1.50

PRODUCT = {
    "id": f"tile-{SKU}",
    "sku": SKU,
    "slug": SLUG,
    "name": NAME,
    "display_name": DISPLAY_NAME,
    "website_name": DISPLAY_NAME,
    "original_name": NAME,
    "description": (
        "Order a 100×100mm sample of any tile in our range. We'll cut and post "
        "it to you within 1-2 working days so you can feel the surface, see the "
        "true colour in your home's lighting, and confirm it's the perfect "
        "match before you commit to a full order.\n\n"
        "**How to order**: add this to your basket, then write the tile name "
        "(e.g. 'Heritage Oak 600×600 Matt') in the order notes at checkout. "
        "Your sample will arrive in plain packaging within 2-3 business days.\n\n"
        "Most customers who order a sample come back to place a full order — "
        "and we credit the £1.50 against your first order over £100."
    ),
    "short_description": "100×100mm cut sample posted to you in 1-2 days. "
                         "Tell us in the order notes which tile you'd like to sample.",
    "price": PRICE,
    "cost_price": 0.50,
    "pallet_price": PRICE,
    "room_lot_price": PRICE,
    "stock": 999,
    "is_active": True,
    "is_featured": True,
    "is_manual": True,  # manually-curated, not from supplier sync
    "source": "manual",
    "source_supplier": "Tile Station",
    "supplier_name": "Tile Station",
    "supplier_code": SKU,
    "main_category": "Samples",
    "sub_categories": ["Samples"],
    "category_ids": [],
    "product_group": "samples",
    "color": "",
    "finish": "",
    "material": "",
    "size": "100x100mm",
    "thickness": "",
    "edge": "",
    "slip_rating": "",
    "suitability": "Sample only",
    "series": "",
    "original_series": "",
    "display_code": "TS-SAMPLE",
    "hidden_seo_keywords": "tile sample order a sample free sample tilestation",
    "seo_keywords": "tile sample, order tile sample, sample tile UK",
    "attributes": {
        "size": "100x100mm",
        "purpose": "sample",
    },
    "images": [
        # Use a generic Tile Station tile image as placeholder; replace via admin if you want
        "https://images.tilestation.co.uk/products/leporce/ONYX_WHITE_80x80_Face1.jpg",
    ],
    "tier_pricing_disabled": True,  # samples are flat-priced, no bulk discounts
    "has_custom_tier_pricing": False,
    "sale_active": False,
    "sqm_per_box": None,
    "tiles_per_box": None,
    "tile_width": 100,
    "tile_height": 100,
    "credit_back_rate": None,
    "discount_percentage": None,
    "trade_discount": None,
    "tier_discounts": None,
    "tier_thresholds": None,
    "sale_savings": None,
    "synced_at": None,
}


async def main():
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        raise SystemExit("MONGO_URL and DB_NAME must be set")

    db = AsyncIOMotorClient(mongo_url)[db_name]
    now = datetime.now(timezone.utc)

    existing = await db.tiles.find_one({"sku": SKU}, {"_id": 0, "id": 1, "price": 1})
    PRODUCT["updated_at"] = now.isoformat()
    PRODUCT["bulk_edited_at"] = now.isoformat()
    PRODUCT["last_updated"] = now

    if existing:
        # Update — preserves original created_at
        await db.tiles.update_one(
            {"sku": SKU},
            {"$set": {k: v for k, v in PRODUCT.items() if k != "id"}}
        )
        print(f"✓ Updated existing sample product (sku={SKU}, price=£{PRICE})")
    else:
        PRODUCT["created_at"] = now
        await db.tiles.insert_one(PRODUCT)
        print(f"✓ Created new sample product (sku={SKU}, price=£{PRICE})")

    print(f"\nProduct URL: /shop/tile/{SLUG}")
    print(f"View on storefront: https://YOUR-DOMAIN/shop/tile/{SLUG}")
    print(f"Admin edit: /admin/supplier-products → search '{SKU}'")


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
Full supplier sync script - runs all suppliers
"""
import asyncio
import sys
import json
import os
from datetime import datetime

sys.path.insert(0, '/app/backend')

from services.scrapers.wallcano_scraper import WallcanoScraper
from services.name_generator import get_name_generator

# Sync results file
RESULTS_FILE = "/app/supplier_data/sync_results.json"

async def sync_wallcano():
    """Sync Wallcano products"""
    print("\n" + "=" * 60)
    print("SYNCING WALLCANO (68 products)")
    print("=" * 60)
    
    # Load prices
    with open('/app/supplier_data/wallcano_prices.json') as f:
        price_data = json.load(f)
    
    scraper = WallcanoScraper(
        email="accounts@tilestation.co.uk",
        password=os.environ.get("WALLCANO_PORTAL_PASSWORD", ""),
        price_data=price_data
    )
    
    products = []
    async with scraper:
        if await scraper.login():
            products = await scraper.get_all_products()
    
    # Process and save
    name_gen = get_name_generator()
    output = []
    for p in products:
        unique_name = name_gen.generate_name(p.name, p.material, p.finish)
        output.append({
            "name": unique_name,
            "supplier_name": p.name,
            "supplier": "wallcano",
            "sku": p.supplier_code,
            "stock_sqm": p.stock_sqm,
            "stock_status": p.stock_status,
            "cost": p.room_lot_price,
            "price": round(p.room_lot_price * 1.9, 2),
            "material": p.material,
            "finish": p.finish,
            "size": p.size,
            "images": p.images
        })
    
    with open('/app/supplier_data/wallcano_products.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    return {
        "supplier": "wallcano",
        "products": len(output),
        "in_stock": len([p for p in output if p["stock_status"] == "In Stock"]),
        "low_stock": len([p for p in output if p["stock_status"] == "Low Stock"]),
        "out_of_stock": len([p for p in output if p["stock_status"] == "Out of Stock"])
    }

async def main():
    """Run full sync"""
    print("=" * 60)
    print("STARTING FULL SUPPLIER SYNC")
    print(f"Started at: {datetime.now()}")
    print("=" * 60)
    
    results = {
        "started_at": datetime.now().isoformat(),
        "suppliers": {}
    }
    
    # Sync Wallcano (the only one fully working right now)
    try:
        result = await sync_wallcano()
        results["suppliers"]["wallcano"] = result
        print(f"✓ Wallcano: {result['products']} products")
    except Exception as e:
        print(f"✗ Wallcano error: {e}")
        results["suppliers"]["wallcano"] = {"error": str(e)}
    
    results["completed_at"] = datetime.now().isoformat()
    
    # Save results
    with open(RESULTS_FILE, 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\n" + "=" * 60)
    print("SYNC COMPLETE")
    print(f"Results saved to {RESULTS_FILE}")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())

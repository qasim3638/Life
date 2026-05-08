"""
Update Gravesend Showroom Stock Levels
Using data from:
- Stocktake - Gravesend Trims.xlsx
- Stocktake - Gravesend Adhesive.xlsx
"""
import asyncio
import json
import os
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone

GRAVESEND_SHOWROOM_ID = "7411e9cf-2250-4bdc-a6ce-2dc844e32646"

async def update_gravesend_stock():
    """Update stock levels for Gravesend showroom"""
    
    # Load stocktake data
    with open('artifacts/gravesend_stocktake.json', 'r') as f:
        stocktake_data = json.load(f)
    
    print(f"Loaded {len(stocktake_data)} products from stocktake")
    
    # Connect to database
    mongo_url = os.environ.get('MONGO_URL')
    client = AsyncIOMotorClient(mongo_url)
    db = client['test_database']
    
    # Get all products
    products = await db.products.find({}, {"_id": 0}).to_list(50000)
    print(f"Found {len(products)} products in database")
    
    # Create lookup maps
    # Map by code
    products_by_code = {}
    for p in products:
        if p.get('sku'):
            products_by_code[p['sku'].upper()] = p
    
    # Map by name + size (for products without codes)
    products_by_name_size = {}
    for p in products:
        name_lower = (p.get('name') or '').lower()
        # Extract size from name if present
        products_by_name_size[name_lower] = p
    
    # Process updates
    updates = []
    not_found = []
    
    for item in stocktake_data:
        product_name = item['product']
        size = item['size']
        stock = item['stock']
        code = item.get('code')
        supplier = item['supplier']
        
        # Try to find product
        matched_product = None
        match_method = None
        
        # Method 1: Match by code (if available)
        if code:
            code_upper = str(code).upper()
            if code_upper in products_by_code:
                matched_product = products_by_code[code_upper]
                match_method = 'code'
        
        # Method 2: Match by product name (fuzzy)
        if not matched_product:
            search_name = product_name.lower()
            # Add size to search
            if size:
                search_name_with_size = f"{search_name} {size}".lower()
            
            for db_prod in products:
                db_name = (db_prod.get('name') or '').lower()
                
                # Check if all significant words match
                search_words = [w for w in search_name.lower().split() if len(w) > 2]
                
                # Check for match
                matches = sum(1 for w in search_words if w in db_name)
                
                # If most words match and size matches
                if matches >= len(search_words) * 0.7:
                    # Check size match
                    if size:
                        size_in_name = size.lower().replace('mm', '') in db_name
                        if size_in_name or size.lower() in db_name:
                            matched_product = db_prod
                            match_method = 'name+size'
                            break
                    else:
                        matched_product = db_prod
                        match_method = 'name'
                        break
        
        if matched_product:
            # Prepare update
            updates.append({
                'stocktake': item,
                'db_product': matched_product,
                'match_method': match_method,
                'new_stock': stock
            })
        else:
            not_found.append(item)
    
    print(f"\n=== MATCHING RESULTS ===")
    print(f"Matched: {len(updates)}")
    print(f"Not found: {len(not_found)}")
    
    # Show not found items
    if not_found:
        print(f"\n=== NOT FOUND ({len(not_found)}) ===")
        for item in not_found[:20]:
            print(f"  {item['supplier']} | {item['product']} | {item['size']} | Stock: {item['stock']}")
        if len(not_found) > 20:
            print(f"  ... and {len(not_found) - 20} more")
    
    # Show sample updates
    print(f"\n=== SAMPLE UPDATES (first 10) ===")
    for u in updates[:10]:
        print(f"  DB: {u['db_product'].get('name')[:50]}...")
        print(f"  -> Stocktake: {u['stocktake']['product']} ({u['stocktake']['size']})")
        print(f"  -> New Gravesend Stock: {u['new_stock']} (matched by {u['match_method']})")
        print()
    
    client.close()
    return updates, not_found

if __name__ == "__main__":
    asyncio.run(update_gravesend_stock())

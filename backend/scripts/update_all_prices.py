"""
Script to recalculate and update all product list prices based on new markup.
New formula: List Price = Cost × 2.30 (130% markup) × 1.20 (VAT) → Round to .99p
"""
import os
import sys
import math

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

# Pricing constants
MARKUP_MULTIPLIER = 2.30  # 130% markup
VAT_MULTIPLIER = 1.20     # 20% VAT

def calculate_list_price(cost: float) -> float:
    """Calculate list price with markup, VAT, and round to .99p"""
    if cost and cost > 0:
        raw_price = cost * MARKUP_MULTIPLIER * VAT_MULTIPLIER
        whole = math.ceil(raw_price)
        return whole - 0.01
    return 0

def main():
    # Connect to MongoDB
    mongo_url = os.environ.get('MONGO_URL')
    db_name = os.environ.get('DB_NAME', 'tile_station')
    
    if not mongo_url:
        print("ERROR: MONGO_URL not set")
        return
    
    client = MongoClient(mongo_url)
    db = client[db_name]
    
    # Update supplier_products collection
    print("=" * 60)
    print("UPDATING SUPPLIER PRODUCTS PRICES")
    print(f"New markup: 130% (×2.30)")
    print(f"Formula: Cost × 2.30 × 1.20 → Round to .99p")
    print("=" * 60)
    
    # Get all products with cost_price
    supplier_products = db.supplier_products.find({"cost_price": {"$gt": 0}})
    
    updated_count = 0
    skipped_count = 0
    
    for product in supplier_products:
        cost_price = product.get('cost_price', 0)
        
        if cost_price and cost_price > 0:
            new_list_price = calculate_list_price(cost_price)
            old_list_price = product.get('list_price', 0) or product.get('price', 0)
            
            # Update the product
            db.supplier_products.update_one(
                {"_id": product["_id"]},
                {"$set": {
                    "list_price": new_list_price,
                    "price": new_list_price,
                    "room_lot_price": new_list_price
                }}
            )
            updated_count += 1
            
            if updated_count <= 5:
                print(f"  {product.get('sku', 'N/A')}: Cost £{cost_price:.2f} → Old £{old_list_price:.2f} → New £{new_list_price:.2f}")
        else:
            skipped_count += 1
    
    print(f"\nSupplier Products: Updated {updated_count}, Skipped {skipped_count} (no cost price)")
    
    # Update tiles collection (published products)
    print("\n" + "=" * 60)
    print("UPDATING TILES (PUBLISHED) PRICES")
    print("=" * 60)
    
    tiles = db.tiles.find({"cost_price": {"$gt": 0}})
    
    tiles_updated = 0
    tiles_skipped = 0
    
    for tile in tiles:
        cost_price = tile.get('cost_price', 0)
        
        if cost_price and cost_price > 0:
            new_list_price = calculate_list_price(cost_price)
            old_list_price = tile.get('room_lot_price', 0) or tile.get('price', 0)
            
            db.tiles.update_one(
                {"_id": tile["_id"]},
                {"$set": {
                    "room_lot_price": new_list_price,
                    "price": new_list_price
                }}
            )
            tiles_updated += 1
            
            if tiles_updated <= 5:
                print(f"  {tile.get('sku', 'N/A')}: Cost £{cost_price:.2f} → Old £{old_list_price:.2f} → New £{new_list_price:.2f}")
        else:
            tiles_skipped += 1
    
    print(f"\nTiles: Updated {tiles_updated}, Skipped {tiles_skipped} (no cost price)")
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total supplier_products updated: {updated_count}")
    print(f"Total tiles updated: {tiles_updated}")
    print(f"New markup: 130% (was 90%)")
    print(f"Example: £10 cost → £{calculate_list_price(10):.2f} list price")
    print("=" * 60)
    
    client.close()

if __name__ == "__main__":
    main()

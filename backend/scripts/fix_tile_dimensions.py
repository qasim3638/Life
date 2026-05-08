"""
One-time script to fix tile dimensions that were likely entered in mm instead of cm.
This script will:
1. Find all products where tile dimensions > 200 (likely in mm)
2. Convert them to cm by dividing by 10
3. Update the database

Run with: python scripts/fix_tile_dimensions.py
"""

import os
import sys
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient

def fix_tile_dimensions():
    mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    db_name = 'tile_station'
    
    client = MongoClient(mongo_url)
    db = client[db_name]
    
    collections = ['products', 'supplier_products', 'tiles']
    
    total_fixed = 0
    
    for collection_name in collections:
        collection = db[collection_name]
        
        # Find products with suspicious dimensions (> 200cm = likely mm)
        suspicious = list(collection.find({
            "$or": [
                {"tile_width": {"$gt": 200}},
                {"tile_height": {"$gt": 200}}
            ]
        }))
        
        print(f"\n=== {collection_name} ===")
        print(f"Found {len(suspicious)} products with dimensions > 200cm")
        
        for product in suspicious:
            sku = product.get('sku') or product.get('id', 'N/A')
            name = product.get('name') or product.get('display_name', 'N/A')
            old_width = product.get('tile_width')
            old_height = product.get('tile_height')
            
            new_width = old_width / 10 if old_width and old_width > 200 else old_width
            new_height = old_height / 10 if old_height and old_height > 200 else old_height
            
            # Calculate new m² per piece
            new_m2_per_piece = None
            if new_width and new_height:
                new_m2_per_piece = round((new_width / 100) * (new_height / 100), 4)
            
            print(f"\nFixing: {name[:50]} (SKU: {sku})")
            print(f"  Old: {old_width}x{old_height}cm")
            print(f"  New: {new_width}x{new_height}cm = {new_m2_per_piece}m²/piece")
            
            # Update the document
            update_fields = {"updated_at": datetime.now(timezone.utc)}
            if old_width and old_width > 200:
                update_fields["tile_width"] = new_width
            if old_height and old_height > 200:
                update_fields["tile_height"] = new_height
            if new_m2_per_piece:
                update_fields["tile_m2_per_piece"] = new_m2_per_piece
            
            # Also update box coverage if tiles_per_box exists
            tiles_per_box = product.get('tiles_per_box')
            if tiles_per_box and new_m2_per_piece:
                update_fields["box_m2_coverage"] = round(new_m2_per_piece * tiles_per_box, 3)
            
            collection.update_one(
                {"_id": product["_id"]},
                {"$set": update_fields}
            )
            total_fixed += 1
    
    print(f"\n{'='*50}")
    print(f"TOTAL FIXED: {total_fixed} products across all collections")
    print(f"{'='*50}")

if __name__ == "__main__":
    print("Tile Dimension Fix Script")
    print("=" * 50)
    print("This will convert tile dimensions from mm to cm where needed.")
    
    response = input("\nProceed? (y/n): ").strip().lower()
    if response == 'y':
        fix_tile_dimensions()
        print("\nDone!")
    else:
        print("Aborted.")

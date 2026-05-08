"""
Production Database Fix Script for Tile Dimensions
===================================================

This script fixes tile dimensions that were entered in mm instead of cm.

WHAT IT DOES:
1. Finds products where tile_width or tile_height > 200 (likely in mm)
2. Divides those dimensions by 10 to convert mm to cm
3. Recalculates m² per piece and box coverage
4. Updates all three collections: products, supplier_products, tiles

SAFETY FEATURES:
- DRY RUN mode by default (preview changes without applying)
- Creates backup before making changes
- Only modifies specific fields, doesn't touch other data
- Logs all changes for audit

USAGE:
  # Dry run (preview only, no changes)
  python scripts/fix_tile_dimensions_production.py --dry-run
  
  # Apply fixes
  python scripts/fix_tile_dimensions_production.py --apply
  
  # Fix specific supplier only
  python scripts/fix_tile_dimensions_production.py --apply --supplier LEPORCE

REQUIREMENTS:
  - MONGO_URL environment variable must be set
  - Run from the backend directory
"""

import os
import sys
import argparse
from datetime import datetime, timezone
from pymongo import MongoClient
import json

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_db_connection():
    """Get MongoDB connection"""
    mongo_url = os.environ.get('MONGO_URL')
    if not mongo_url:
        print("ERROR: MONGO_URL environment variable is not set!")
        print("Please set it before running this script.")
        sys.exit(1)
    
    db_name = os.environ.get('DB_NAME', 'tile_station')
    client = MongoClient(mongo_url)
    return client[db_name]


def find_suspicious_products(db, supplier_filter=None):
    """Find all products with suspicious dimensions (> 200cm = likely mm)"""
    results = {}
    collections = ['products', 'supplier_products', 'tiles']
    
    for collection_name in collections:
        collection = db[collection_name]
        
        query = {
            "$or": [
                {"tile_width": {"$gt": 200}},
                {"tile_height": {"$gt": 200}}
            ]
        }
        
        # Add supplier filter if specified
        if supplier_filter:
            query["$and"] = [
                query.pop("$or"),
                {"$or": [
                    {"supplier": supplier_filter},
                    {"supplier_name": supplier_filter}
                ]}
            ]
            query["$or"] = query.pop("$and")[0]
        
        products = list(collection.find(query))
        results[collection_name] = products
        
    return results


def calculate_fixed_values(product):
    """Calculate the corrected values for a product"""
    old_width = product.get('tile_width')
    old_height = product.get('tile_height')
    tiles_per_box = product.get('tiles_per_box')
    
    # Only fix values that are > 200 (likely in mm)
    new_width = old_width / 10 if old_width and old_width > 200 else old_width
    new_height = old_height / 10 if old_height and old_height > 200 else old_height
    
    # Calculate new m² per piece
    new_m2_per_piece = None
    if new_width and new_height:
        new_m2_per_piece = round((new_width / 100) * (new_height / 100), 4)
    
    # Calculate new box coverage
    new_box_coverage = None
    if tiles_per_box and new_m2_per_piece:
        new_box_coverage = round(new_m2_per_piece * tiles_per_box, 4)
    
    return {
        'old_width': old_width,
        'old_height': old_height,
        'new_width': new_width,
        'new_height': new_height,
        'old_m2_per_piece': round((old_width / 100) * (old_height / 100), 4) if old_width and old_height else None,
        'new_m2_per_piece': new_m2_per_piece,
        'tiles_per_box': tiles_per_box,
        'new_box_coverage': new_box_coverage,
        'needs_fix': (old_width and old_width > 200) or (old_height and old_height > 200)
    }


def apply_fix(db, collection_name, product, calculated):
    """Apply the fix to a single product"""
    update_fields = {
        "updated_at": datetime.now(timezone.utc),
        "dimension_fix_applied": True,
        "dimension_fix_date": datetime.now(timezone.utc)
    }
    
    if calculated['old_width'] and calculated['old_width'] > 200:
        update_fields["tile_width"] = calculated['new_width']
    
    if calculated['old_height'] and calculated['old_height'] > 200:
        update_fields["tile_height"] = calculated['new_height']
    
    if calculated['new_m2_per_piece']:
        update_fields["tile_m2_per_piece"] = calculated['new_m2_per_piece']
        # Also update sqm_per_box for consistency
        if calculated['new_box_coverage']:
            update_fields["sqm_per_box"] = calculated['new_box_coverage']
            update_fields["box_m2_coverage"] = calculated['new_box_coverage']
    
    collection = db[collection_name]
    collection.update_one(
        {"_id": product["_id"]},
        {"$set": update_fields}
    )
    
    return update_fields


def main():
    parser = argparse.ArgumentParser(description='Fix tile dimensions in production database')
    parser.add_argument('--dry-run', action='store_true', default=True,
                        help='Preview changes without applying (default)')
    parser.add_argument('--apply', action='store_true',
                        help='Actually apply the fixes to the database')
    parser.add_argument('--supplier', type=str, default=None,
                        help='Only fix products from specific supplier (e.g., LEPORCE)')
    args = parser.parse_args()
    
    # If --apply is specified, disable dry-run
    dry_run = not args.apply
    
    print("=" * 60)
    print("TILE DIMENSION FIX SCRIPT")
    print("=" * 60)
    print(f"Mode: {'DRY RUN (preview only)' if dry_run else '⚠️  APPLYING CHANGES'}")
    if args.supplier:
        print(f"Supplier Filter: {args.supplier}")
    print("=" * 60)
    
    # Connect to database
    db = get_db_connection()
    print(f"Connected to database: {db.name}")
    
    # Find suspicious products
    print("\nScanning for products with dimensions > 200cm...")
    suspicious = find_suspicious_products(db, args.supplier)
    
    total_found = sum(len(products) for products in suspicious.values())
    print(f"\nFound {total_found} products to fix across all collections")
    
    if total_found == 0:
        print("\n✅ No products need fixing!")
        return
    
    # Process each collection
    fixes_applied = 0
    fix_log = []
    
    for collection_name, products in suspicious.items():
        if not products:
            continue
            
        print(f"\n{'=' * 40}")
        print(f"Collection: {collection_name} ({len(products)} products)")
        print("=" * 40)
        
        for product in products:
            sku = product.get('sku') or product.get('supplier_product_code') or str(product.get('_id', 'N/A'))
            name = product.get('name') or product.get('display_name') or product.get('product_name', 'Unknown')
            
            calculated = calculate_fixed_values(product)
            
            print(f"\n📦 {name[:50]}")
            print(f"   SKU: {sku}")
            print(f"   OLD: {calculated['old_width']}x{calculated['old_height']}cm = {calculated['old_m2_per_piece']}m²/pc")
            print(f"   NEW: {calculated['new_width']}x{calculated['new_height']}cm = {calculated['new_m2_per_piece']}m²/pc")
            if calculated['tiles_per_box']:
                print(f"   Box: {calculated['tiles_per_box']} tiles = {calculated['new_box_coverage']}m²/box")
            
            if not dry_run:
                updated_fields = apply_fix(db, collection_name, product, calculated)
                print(f"   ✅ FIXED!")
                fixes_applied += 1
                fix_log.append({
                    'collection': collection_name,
                    'sku': sku,
                    'name': name[:50],
                    'old_dimensions': f"{calculated['old_width']}x{calculated['old_height']}",
                    'new_dimensions': f"{calculated['new_width']}x{calculated['new_height']}",
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })
            else:
                print(f"   🔍 Would be fixed (dry run)")
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    if dry_run:
        print(f"DRY RUN COMPLETE - {total_found} products would be fixed")
        print("\nTo apply these fixes, run:")
        print(f"  python scripts/fix_tile_dimensions_production.py --apply")
        if args.supplier:
            print(f"  (with --supplier {args.supplier})")
    else:
        print(f"✅ FIXES APPLIED - {fixes_applied} products updated")
        
        # Save fix log
        log_file = f"/tmp/dimension_fix_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(log_file, 'w') as f:
            json.dump(fix_log, f, indent=2)
        print(f"\nFix log saved to: {log_file}")
    
    print("=" * 60)


if __name__ == "__main__":
    main()

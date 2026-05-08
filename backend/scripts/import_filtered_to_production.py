"""
Import Filtered Supplier Products to Production Database
=========================================================
This imports ONLY: Verona, Splendour, Wallcano, Ceramica Impex
EXCLUDES: Tile Rite, Ultra Tile, Trimline (and others)

Usage: python import_filtered_to_production.py

Before running:
1. Set your MONGO_URL environment variable
2. Set your DB_NAME environment variable (default: test_database)
3. Place supplier_products_filtered_export.json in same folder
"""

import os
import json
from datetime import datetime, timezone
from pymongo import MongoClient

def import_products():
    # Get MongoDB connection
    mongo_url = os.environ.get('MONGO_URL')
    db_name = os.environ.get('DB_NAME', 'test_database')
    
    if not mongo_url:
        print("ERROR: MONGO_URL environment variable not set")
        return
    
    print(f"Connecting to database: {db_name}")
    client = MongoClient(mongo_url)
    db = client[db_name]
    
    # Load export file
    export_file = 'supplier_products_filtered_export.json'
    if not os.path.exists(export_file):
        print(f"ERROR: {export_file} not found")
        return
    
    with open(export_file, 'r') as f:
        data = json.load(f)
    
    products = data['products']
    print(f"\nLoaded {len(products)} products from export file")
    print(f"Export date: {data['export_date']}")
    print(f"Note: {data.get('note', 'N/A')}")
    print("\nProducts by supplier:")
    for supplier, count in sorted(data['supplier_counts'].items(), key=lambda x: -x[1]):
        print(f"  {supplier}: {count}")
    
    # Check existing counts in database
    print("\n=== Current Production Data ===")
    for supplier in ['Verona', 'Splendour', 'Wallcano', 'Ceramica Impex']:
        count = db.supplier_products.count_documents({"supplier": supplier})
        print(f"  {supplier}: {count} existing")
    
    # Confirm before import
    print("\n⚠️  This will ADD/UPDATE products in the supplier_products collection")
    print("   It will NOT affect your EPOS products collection")
    confirm = input("\nProceed with import? (yes/no): ")
    if confirm.lower() != 'yes':
        print("Import cancelled")
        return
    
    # Import products
    new_count = 0
    updated_count = 0
    skipped_count = 0
    
    for product in products:
        supplier = product.get('supplier')
        sku = product.get('sku')
        
        if not supplier or not sku:
            skipped_count += 1
            continue
        
        # Only import allowed suppliers
        if supplier not in ['Verona', 'Splendour', 'Wallcano', 'Ceramica Impex']:
            skipped_count += 1
            continue
        
        # Add import timestamp
        product['imported_at'] = datetime.now(timezone.utc)
        
        # Upsert product (update if exists, insert if new)
        result = db.supplier_products.update_one(
            {"supplier": supplier, "sku": sku},
            {"$set": product, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}},
            upsert=True
        )
        
        if result.upserted_id:
            new_count += 1
        elif result.modified_count > 0:
            updated_count += 1
    
    print(f"\n=== Import Complete ===")
    print(f"New products added: {new_count}")
    print(f"Existing products updated: {updated_count}")
    print(f"Skipped: {skipped_count}")
    
    # Verify final counts
    print("\n=== Final Production Data ===")
    total = 0
    for supplier in ['Verona', 'Splendour', 'Wallcano', 'Ceramica Impex']:
        count = db.supplier_products.count_documents({"supplier": supplier})
        print(f"  {supplier}: {count}")
        total += count
    print(f"  TOTAL: {total}")

if __name__ == "__main__":
    import_products()

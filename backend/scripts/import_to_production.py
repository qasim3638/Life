"""
Import Supplier Products to Production Database
Usage: python import_to_production.py

This script imports supplier products from the JSON export file
into your MongoDB database.

Before running:
1. Set your MONGO_URL environment variable
2. Set your DB_NAME environment variable (default: test_database)
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
        print("Please set it to your MongoDB connection string")
        return
    
    print(f"Connecting to database: {db_name}")
    client = MongoClient(mongo_url)
    db = client[db_name]
    
    # Load export file
    export_file = 'supplier_products_export.json'
    if not os.path.exists(export_file):
        print(f"ERROR: {export_file} not found")
        print("Please place the export file in the same directory as this script")
        return
    
    with open(export_file, 'r') as f:
        data = json.load(f)
    
    products = data['products']
    print(f"\nLoaded {len(products)} products from export file")
    print(f"Export date: {data['export_date']}")
    print("\nProducts by supplier:")
    for supplier, count in sorted(data['supplier_counts'].items(), key=lambda x: -x[1]):
        print(f"  {supplier}: {count}")
    
    # Confirm before import
    confirm = input("\nProceed with import? (yes/no): ")
    if confirm.lower() != 'yes':
        print("Import cancelled")
        return
    
    # Import products
    new_count = 0
    updated_count = 0
    
    for product in products:
        supplier = product.get('supplier')
        sku = product.get('sku')
        
        if not supplier or not sku:
            continue
        
        # Add import timestamp
        product['imported_at'] = datetime.now(timezone.utc)
        
        # Upsert product
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
    print(f"New products: {new_count}")
    print(f"Updated products: {updated_count}")
    
    # Verify
    total = db.supplier_products.count_documents({})
    print(f"\nTotal products in database: {total}")

if __name__ == "__main__":
    import_products()

"""
Add all supplier products with blue + sign to the main Products database
"""

import requests
import os
import json
from collections import defaultdict

API_URL = "https://tile-station-production.up.railway.app"
EMAIL = "qasim@tilestation.co.uk"
PASSWORD = os.environ.get("TILESTATION_ADMIN_PASSWORD", "")

print("="*60)
print("ADDING ALL BLUE + PRODUCTS TO DATABASE")
print("="*60)

# Login
print("\n[1/3] Logging in...")
login_response = requests.post(
    f"{API_URL}/api/auth/login",
    json={"email": EMAIL, "password": PASSWORD}
)
token = login_response.json()['token']
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
print("       Done!")

# Get all supplier products
print("\n[2/3] Fetching supplier products...")
response = requests.get(f"{API_URL}/api/supplier-sync/products?limit=10000", headers=headers)
data = response.json()
products = data.get('products', [])

# Find products NOT in database (blue + sign)
not_in_db = [p for p in products if not p.get('in_products_db', False)]
print(f"       Total supplier products: {len(products)}")
print(f"       Products to add (blue +): {len(not_in_db)}")

# Count by supplier
by_supplier = defaultdict(int)
for p in not_in_db:
    by_supplier[p.get('supplier', 'Unknown')] += 1
print("       By supplier:")
for supplier, count in sorted(by_supplier.items(), key=lambda x: -x[1]):
    print(f"          {supplier}: {count}")

# Add products to database
print("\n[3/3] Adding products to database...")
added = 0
failed = 0
already_exists = 0

for i, p in enumerate(not_in_db):
    try:
        sku = p.get('sku')
        supplier = p.get('supplier')
        
        # Use the single add-to-database endpoint
        response = requests.post(
            f'{API_URL}/api/supplier-sync/products/{sku}/add-to-database',
            headers=headers,
            params={'supplier': supplier}
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('created'):
                added += 1
            else:
                already_exists += 1
        else:
            failed += 1
            
    except Exception as e:
        failed += 1
    
    if (i + 1) % 100 == 0:
        print(f"       Progress: {i + 1}/{len(not_in_db)} (added: {added})")

print("")
print("="*60)
print("COMPLETE!")
print("="*60)
print(f"Added to database: {added}")
print(f"Already existed: {already_exists}")
print(f"Failed: {failed}")

# Verify
print("\n[Verification]")
response = requests.get(f"{API_URL}/api/supplier-sync/products?limit=10000", headers=headers)
data = response.json()
products = data.get('products', [])
still_not_in_db = sum(1 for p in products if not p.get('in_products_db', False))
print(f"Products still with blue + sign: {still_not_in_db}")

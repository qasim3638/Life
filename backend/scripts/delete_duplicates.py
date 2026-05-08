"""
Delete all duplicate products - keep only ONE of each SKU
"""

import requests
import os
from collections import defaultdict
import time

API_URL = "https://tile-station-production.up.railway.app"
EMAIL = "qasim@tilestation.co.uk"
PASSWORD = os.environ.get("TILESTATION_ADMIN_PASSWORD", "")

print("="*60)
print("DELETING DUPLICATE PRODUCTS")
print("="*60)

# Login
print("\n[1/4] Logging in...")
login_response = requests.post(
    f"{API_URL}/api/auth/login",
    json={"email": EMAIL, "password": PASSWORD}
)
token = login_response.json()['token']
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
print("       Logged in successfully")

# Get all products
print("\n[2/4] Fetching all products...")
products = requests.get(f"{API_URL}/api/products?limit=10000", headers=headers).json()
initial_count = len(products)
print(f"       Found {initial_count} total products")

# Find duplicates
print("\n[3/4] Finding duplicates...")
sku_groups = defaultdict(list)
for p in products:
    sku = (p.get('sku') or '').strip()
    if sku:
        sku_groups[sku].append(p)

# Count duplicates
duplicates_to_delete = []
for sku, prods in sku_groups.items():
    if len(prods) > 1:
        # Keep the first one, mark the rest for deletion
        for p in prods[1:]:
            duplicates_to_delete.append({
                'id': p.get('id'),
                'sku': sku,
                'name': p.get('name', '')[:40]
            })

print(f"       Found {len(duplicates_to_delete)} duplicate entries to delete")

# Delete duplicates
print("\n[4/4] Deleting duplicates...")
deleted = 0
failed = 0
start_time = time.time()

for i, dup in enumerate(duplicates_to_delete):
    try:
        response = requests.delete(
            f"{API_URL}/api/products/{dup['id']}",
            headers=headers
        )
        if response.status_code == 200:
            deleted += 1
        else:
            failed += 1
    except Exception as e:
        failed += 1
    
    # Progress update every 50
    if (i + 1) % 50 == 0:
        elapsed = time.time() - start_time
        rate = (i + 1) / elapsed
        remaining = (len(duplicates_to_delete) - i - 1) / rate
        print(f"       Progress: {i + 1}/{len(duplicates_to_delete)} | Deleted: {deleted} | ETA: {remaining:.0f}s")

print(f"\n" + "="*60)
print("COMPLETE!")
print("="*60)
print(f"✅ Deleted: {deleted} duplicate products")
if failed > 0:
    print(f"❌ Failed: {failed}")

# Verify final count
final_products = requests.get(f"{API_URL}/api/products?limit=10000", headers=headers).json()
print(f"\n📊 Products before: {initial_count}")
print(f"📊 Products after:  {len(final_products)}")
print(f"📊 Removed:         {initial_count - len(final_products)}")

# Write result to file
with open('/app/delete_results.txt', 'w') as f:
    f.write(f"Deletion Complete\n")
    f.write(f"Deleted: {deleted}\n")
    f.write(f"Failed: {failed}\n")
    f.write(f"Before: {initial_count}\n")
    f.write(f"After: {len(final_products)}\n")

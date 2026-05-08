"""
Sync ALL products from main database to Supplier Products
"""

import requests
import os
from collections import defaultdict
import time

API_URL = "https://tile-station-production.up.railway.app"
EMAIL = "qasim@tilestation.co.uk"
PASSWORD = os.environ.get("TILESTATION_ADMIN_PASSWORD", "")

def get_supplier_from_sku(sku):
    """Determine supplier from SKU pattern"""
    if not sku:
        return 'Other'
    
    sku_upper = sku.upper()
    
    # Direct prefix matches (with dash)
    prefix_map = {
        'TIL-': 'Tile Rite',
        'TILE-': 'Tile Rite',
        'TRI-': 'Trimline',
        'ULT-': 'Ultra Tile',
        'VER-': 'Verona',
        'SPL-': 'Splendour',
        'WAL-': 'Wallcano',
        'CER-': 'Ceramica Impex',
        'REG-': 'Regulus',
        'GEN-': 'General',
        'BEA-': 'Beaumont',
        'EAG-': 'Eagle',
        'PRI-': 'Primus',
        'LP-': 'Le Porce',
        'HM-': 'H Martin',
    }
    
    for prefix, supplier in prefix_map.items():
        if sku_upper.startswith(prefix):
            return supplier
    
    # Verona patterns: V + letter combinations
    # VLG, VCG, VLW, VL3, VL6, VLB, VMG, VCW, VIG, VIW, VR, VB, VM, VS, etc.
    if sku_upper.startswith('V'):
        return 'Verona'
    
    # Splendour patterns: S + letter combinations
    # SMW, SMG, SSB, SCG, SSW, SB, SS, SM, SA, SI, SP, SC, SR, SU, SG, SF
    if sku_upper.startswith('S'):
        return 'Splendour'
    
    # Polish/Matt patterns
    if sku_upper.startswith('POL') or sku_upper.startswith('MAT'):
        return 'Splendour'
    
    # Other patterns
    if sku_upper.startswith('W'):  # Wallcano
        return 'Wallcano'
    if sku_upper.startswith('C'):  # Ceramica or other
        return 'Ceramica Impex'
    if sku_upper.startswith('F'):  # Feature tiles
        return 'Verona'
    
    return 'Other'

def main():
    print("="*60)
    print("SYNCING ALL PRODUCTS TO SUPPLIER PRODUCTS")
    print("="*60)
    
    # Login
    print("\n[1/4] Logging in...")
    login_response = requests.post(
        f"{API_URL}/api/auth/login",
        json={"email": EMAIL, "password": PASSWORD}
    )
    token = login_response.json()['token']
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    print("       Done!")
    
    # Get all products from main database
    print("\n[2/4] Fetching all products...")
    products = requests.get(f"{API_URL}/api/products?limit=10000", headers=headers).json()
    print(f"       Found {len(products)} products in main database")
    
    # Get existing supplier products
    print("\n[3/4] Checking existing supplier products...")
    existing = requests.get(f"{API_URL}/api/supplier-sync/products?limit=10000", headers=headers).json()
    existing_skus = set(p.get('sku') for p in existing.get('products', []))
    print(f"       Found {len(existing_skus)} existing supplier products")
    
    # Find products to add
    to_add = []
    supplier_counts = defaultdict(int)
    
    for p in products:
        sku = p.get('sku', '')
        if sku and sku not in existing_skus:
            supplier = get_supplier_from_sku(sku)
            supplier_counts[supplier] += 1
            to_add.append({
                'sku': sku,
                'name': p.get('name'),
                'product_name': p.get('name'),
                'supplier': supplier,
                'price': p.get('price'),
                'cost_price': p.get('cost'),
                'stock_quantity': p.get('stock', 0),
                'in_products_db': True,
                'products_db_id': p.get('id')
            })
    
    print(f"\n       Products to add: {len(to_add)}")
    print("       By supplier:")
    for supplier, count in sorted(supplier_counts.items(), key=lambda x: -x[1]):
        print(f"         {supplier}: {count}")
    
    if not to_add:
        print("\n       All products already synced!")
        return
    
    # Add products in batches
    print("\n[4/4] Adding products to Supplier Products...")
    
    # Group by supplier for batch upload
    by_supplier = defaultdict(list)
    for p in to_add:
        by_supplier[p['supplier']].append(p)
    
    total_added = 0
    for supplier, prods in by_supplier.items():
        print(f"\n       Adding {len(prods)} {supplier} products...")
        
        # Use bulk-upsert endpoint
        response = requests.post(
            f"{API_URL}/api/supplier-sync/bulk-upsert",
            headers=headers,
            json={
                "supplier": supplier,
                "products": prods,
                "match_by": "sku"
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            added = result.get('inserted', 0) + result.get('updated', 0)
            total_added += added
            print(f"         Added: {added}")
        else:
            print(f"         ERROR: {response.text[:100]}")
    
    # Verify final count
    print("\n" + "="*60)
    print("COMPLETE!")
    print("="*60)
    
    final = requests.get(f"{API_URL}/api/supplier-sync/stats", headers=headers).json()
    final_total = sum(final.values())
    
    print(f"\n📊 Supplier Products before: {len(existing_skus)}")
    print(f"📊 Supplier Products after:  {final_total}")
    print(f"📊 Added: {total_added}")
    
    print("\nBy supplier:")
    for supplier, count in sorted(final.items(), key=lambda x: -x[1]):
        print(f"   {supplier}: {count}")

if __name__ == "__main__":
    main()

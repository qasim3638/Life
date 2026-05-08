import requests
import os
import json

PROD_URL = "https://tile-station-production.up.railway.app"
EMAIL = "qasim@tilestation.co.uk"
PASSWORD = os.environ.get("TILESTATION_ADMIN_PASSWORD", "")

def login():
    response = requests.post(f"{PROD_URL}/api/auth/login", 
        json={"email": EMAIL, "password": PASSWORD})
    if response.status_code == 200:
        return response.json().get("token")
    raise Exception(f"Login failed: {response.text}")

def get_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def get_all_products(token):
    response = requests.get(f"{PROD_URL}/api/products?limit=3000", headers=get_headers(token))
    return response.json()

def determine_supplier(product):
    """Determine supplier based on SKU prefix and product name"""
    sku = product.get('sku', '') or ''
    name = product.get('name', '').lower()
    desc = product.get('description', '') or ''
    
    # Already has supplier in description
    if 'Supplier:' in desc:
        return None
    
    # SKU-based detection
    if sku.startswith('TIL-'):
        return 'Tile Rite'
    if sku.startswith('ULT-'):
        return 'Ultra Tile'
    if sku.startswith('TRI-'):
        return 'Trimline'
    
    # Name-based detection for GEN- SKUs (Ultra products)
    if sku.startswith('GEN-'):
        if 'ultra' in name or 'progrout' in name or 'proflex' in name:
            return 'Ultra Tile'
        if 'silicone' in name and 'ultra' in name:
            return 'Ultra Tile'
    
    return None

def update_description_with_supplier(product, supplier):
    """Add supplier to description"""
    desc = product.get('description', '') or ''
    
    # Parse existing description parts
    parts = [p.strip() for p in desc.split('|') if p.strip()]
    
    # Add supplier at the beginning
    new_parts = [f"Supplier: {supplier}"]
    
    # Add other parts (excluding any old supplier info)
    for part in parts:
        if not part.startswith('Supplier:'):
            new_parts.append(part)
    
    return ' | '.join(new_parts)

def main():
    print("=== SUPPLIER UPDATE SCRIPT ===\n")
    
    token = login()
    print("✓ Logged in successfully")
    
    products = get_all_products(token)
    print(f"✓ Found {len(products)} products")
    
    updated = 0
    skipped = 0
    
    for p in products:
        supplier = determine_supplier(p)
        if supplier:
            new_desc = update_description_with_supplier(p, supplier)
            
            # Update product
            update_data = {
                'name': p['name'],
                'sku': p['sku'],
                'description': new_desc,
                'price': p.get('price'),
                'cost': p.get('cost'),
                'stock': p.get('stock', 0),
                'reorder_level': p.get('reorder_level', 10),
                'showroom_stock': p.get('showroom_stock', {}),
            }
            
            response = requests.put(
                f"{PROD_URL}/api/products/{p['id']}",
                headers=get_headers(token),
                json=update_data
            )
            
            if response.status_code == 200:
                updated += 1
                print(f"  ✓ Updated {p['name'][:50]} → Supplier: {supplier}")
            else:
                print(f"  ✗ Failed: {p['name'][:50]} - {response.text[:100]}")
        else:
            skipped += 1
    
    print(f"\n=== SUMMARY ===")
    print(f"Updated: {updated}")
    print(f"Skipped (already has supplier): {skipped}")

if __name__ == "__main__":
    main()

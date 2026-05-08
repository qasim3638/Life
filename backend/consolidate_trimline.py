import requests
import os
import json

PROD_URL = "https://tile-station-production.up.railway.app"
EMAIL = "qasim@tilestation.co.uk"
PASSWORD = os.environ.get("TILESTATION_ADMIN_PASSWORD", "")

def login():
    response = requests.post(f"{PROD_URL}/api/auth/login", 
        json={"email": EMAIL, "password": PASSWORD})
    return response.json().get("token")

def get_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def main():
    token = login()
    print("✓ Logged in")
    
    # Get all products
    response = requests.get(f"{PROD_URL}/api/products?limit=3000", headers=get_headers(token))
    products = response.json()
    
    updated = 0
    for p in products:
        desc = p.get('description', '') or ''
        
        # Check for Trimline variants
        if 'Trimline - Atrim' in desc or 'Trimline - Astrim' in desc:
            # Replace with just "Trimline"
            new_desc = desc.replace('Trimline - Atrim', 'Trimline').replace('Trimline - Astrim', 'Trimline')
            
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
                print(f"  ✓ {p['name'][:50]}")
    
    print(f"\n=== Updated {updated} products to use 'Trimline' ===")

if __name__ == "__main__":
    main()

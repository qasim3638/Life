"""
Push Wallcano Products to Production
=====================================
This script sends the processed Wallcano products directly to the production API.
"""

import json
import requests
from datetime import datetime

PROD_URL = "https://tile-station-production.up.railway.app"

def push_to_production():
    """Push Wallcano products to production via API"""
    
    # Load exported products
    with open('/app/frontend/public/wallcano_products_export.json', 'r') as f:
        products = json.load(f)
    
    print(f"Loaded {len(products)} Wallcano products")
    
    # Convert to API format
    api_products = []
    for p in products:
        api_product = {
            'sku': p.get('sku'),
            'name': p.get('name'),
            'product_name': p.get('product_name'),
            'category': p.get('category'),
            'description': p.get('description'),
            'material': p.get('material'),
            'finish': p.get('finish'),
            'size': p.get('size'),
            'thickness': p.get('thickness'),
            'trade_price': p.get('trade_price'),
            'cost_price': p.get('cost_price'),
            'price': p.get('price'),
            'pallet_price': p.get('pallet_price'),
            'stock_m2': p.get('stock_m2'),
            'in_stock': p.get('in_stock'),
            'images': p.get('images', []),
            'tiles_per_box': p.get('tiles_per_box'),
            'sqm_per_box': p.get('sqm_per_box'),
            'boxes_per_pallet': p.get('boxes_per_pallet')
        }
        api_products.append(api_product)
    
    # Send to production API in batches
    batch_size = 50
    total_sent = 0
    
    for i in range(0, len(api_products), batch_size):
        batch = api_products[i:i + batch_size]
        
        payload = {
            'products': batch,
            'source': 'preview_import'
        }
        
        try:
            response = requests.post(
                f"{PROD_URL}/api/supplier-sync/wallcano/products",
                json=payload,
                timeout=60
            )
            
            if response.ok:
                result = response.json()
                print(f"Batch {i//batch_size + 1}: Sent {len(batch)} products - {result.get('message', 'OK')}")
                total_sent += len(batch)
            else:
                print(f"Batch {i//batch_size + 1}: FAILED - {response.status_code} - {response.text[:200]}")
                
        except Exception as e:
            print(f"Batch {i//batch_size + 1}: ERROR - {e}")
    
    print()
    print("=" * 50)
    print(f"COMPLETE: Sent {total_sent} products to production")
    print("=" * 50)
    
    # Verify by checking status
    try:
        status_response = requests.get(f"{PROD_URL}/api/supplier-sync/wallcano/status", timeout=30)
        if status_response.ok:
            status = status_response.json()
            print(f"Production Wallcano count: {status.get('total_products', 'N/A')}")
    except Exception as e:
        print(f"Could not verify: {e}")

if __name__ == '__main__':
    push_to_production()

"""
Migrate Splendour Products to Production API
=============================================
1. Delete existing Splendour products from production
2. Push all clean products from sync_staging_fresh to production
"""

import requests
import json
import os
import logging
from datetime import datetime, timezone
from pymongo import MongoClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Production API
PROD_URL = "https://tile-station-production.up.railway.app"
PROD_EMAIL = "qasim@tilestation.co.uk"
PROD_PASSWORD = os.environ.get("TILESTATION_ADMIN_PASSWORD", "")

def get_db():
    client = MongoClient(os.environ.get('MONGO_URL', 'mongodb://localhost:27017'))
    return client[os.environ.get('DB_NAME', 'test_database')]


def login_to_production():
    """Login to production API and get token"""
    logger.info(f"Logging in to production as {PROD_EMAIL}...")
    
    response = requests.post(
        f"{PROD_URL}/api/auth/login",
        json={"email": PROD_EMAIL, "password": PROD_PASSWORD},
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 200:
        data = response.json()
        token = data.get('token')
        if token:
            logger.info("Login successful!")
            return token
    
    logger.error(f"Login failed: {response.text}")
    return None


def clear_splendour_staging(token):
    """Clear Splendour staging on production"""
    logger.info("Clearing Splendour staging on production...")
    
    response = requests.delete(
        f"{PROD_URL}/api/sync-staging/clear/Splendour",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code == 200:
        logger.info(f"Staging cleared: {response.json()}")
        return True
    else:
        logger.error(f"Failed to clear staging: {response.text}")
        return False


def get_products_from_fresh():
    """Get all products from sync_staging_fresh"""
    db = get_db()
    
    products = list(db.sync_staging_fresh.find(
        {'supplier': 'Splendour'},
        {'_id': 0}  # Exclude MongoDB _id
    ))
    
    logger.info(f"Retrieved {len(products)} products from sync_staging_fresh")
    return products


def push_products_to_production(token, products, batch_size=50):
    """Push products to production in batches"""
    logger.info(f"Pushing {len(products)} products to production in batches of {batch_size}...")
    
    total_inserted = 0
    total_updated = 0
    errors = []
    
    # Process in batches
    for i in range(0, len(products), batch_size):
        batch = products[i:i+batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (len(products) + batch_size - 1) // batch_size
        
        logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} products)...")
        
        # Prepare products for API
        api_products = []
        for p in batch:
            # Convert datetime to string if present
            synced_at = p.get('synced_at')
            if hasattr(synced_at, 'isoformat'):
                synced_at = synced_at.isoformat()
            
            api_product = {
                "supplier": "Splendour",
                "sku": p.get('sku'),
                "old_sku": p.get('sku'),  # Use same SKU for matching
                "name": p.get('name'),
                "cost_price": p.get('cost_price'),
                "price": p.get('list_price'),  # API uses 'price' not 'list_price'
                "list_price": p.get('list_price'),  # Also send list_price
                "stock_m2": p.get('stock_m2', 0),
                "in_stock": p.get('in_stock', False),
                "image": p.get('image'),
                "images": p.get('images', []),
                "url": p.get('url'),
                "size": p.get('size'),
                "material": p.get('material'),
                "finish": p.get('finish'),
                "synced_at": synced_at,
                "sync_source": "fresh_deep_scan_migration"
            }
            api_products.append(api_product)
        
        # Send to production
        try:
            response = requests.post(
                f"{PROD_URL}/api/supplier-sync/bulk-upsert",
                json={
                    "supplier": "Splendour",
                    "products": api_products,
                    "match_by": "sku"
                },
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                timeout=120
            )
            
            if response.status_code == 200:
                result = response.json()
                inserted = result.get('inserted', 0)
                updated = result.get('updated', 0)
                total_inserted += inserted
                total_updated += updated
                logger.info(f"  Batch {batch_num}: Inserted {inserted}, Updated {updated}")
            else:
                error_msg = f"Batch {batch_num} failed: {response.status_code} - {response.text[:200]}"
                logger.error(error_msg)
                errors.append(error_msg)
                
        except Exception as e:
            error_msg = f"Batch {batch_num} error: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
    
    return {
        "total_inserted": total_inserted,
        "total_updated": total_updated,
        "errors": errors
    }


def verify_production_data(token):
    """Verify the data on production"""
    logger.info("Verifying production data...")
    
    response = requests.get(
        f"{PROD_URL}/api/supplier-sync/splendour/status",
    )
    
    if response.status_code == 200:
        data = response.json()
        logger.info(f"Production status: {json.dumps(data, indent=2)}")
        return data
    else:
        logger.error(f"Failed to get status: {response.text}")
        return None


def run_migration():
    """Main migration function"""
    print("="*80)
    print("SPLENDOUR PRODUCTION MIGRATION")
    print("="*80)
    print(f"Started at: {datetime.now(timezone.utc).isoformat()}")
    print()
    
    # Step 1: Login
    token = login_to_production()
    if not token:
        return {"error": "Login failed"}
    
    # Step 2: Get current production status
    print("\n--- BEFORE MIGRATION ---")
    verify_production_data(token)
    
    # Step 3: Clear staging
    clear_splendour_staging(token)
    
    # Step 4: Get products from fresh scan
    products = get_products_from_fresh()
    
    # Filter to only products with cost_price (exclude non-tile items)
    products_with_price = [p for p in products if p.get('cost_price') is not None]
    logger.info(f"Filtered to {len(products_with_price)} products with pricing")
    
    # Step 5: Push to production
    result = push_products_to_production(token, products_with_price)
    
    # Step 6: Verify
    print("\n--- AFTER MIGRATION ---")
    verify_production_data(token)
    
    # Summary
    print("\n" + "="*80)
    print("MIGRATION COMPLETE")
    print("="*80)
    print(f"Products processed: {len(products_with_price)}")
    print(f"Inserted: {result['total_inserted']}")
    print(f"Updated: {result['total_updated']}")
    print(f"Errors: {len(result['errors'])}")
    
    if result['errors']:
        print("\nErrors:")
        for e in result['errors'][:10]:
            print(f"  - {e}")
    
    return result


if __name__ == "__main__":
    run_migration()

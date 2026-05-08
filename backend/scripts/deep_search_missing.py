"""
Deep Search Missing Products Script
=====================================
This script uses a smarter approach:
1. Search for each "not found" SKU on Splendour website
2. Extract ALL products from search results (even if not exact match)
3. Check if those products are already in our database
4. Add any new products found

This helps discover products that the original sync missed!
"""

import asyncio
import json
import os
import re
import logging
from datetime import datetime, timezone
from pymongo import MongoClient
import pandas as pd

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
BASE_URL = "https://www.splendourtiles.co.uk"
SPLENDOUR_EMAIL = "accounts@tilestation.co.uk"
SPLENDOUR_PASSWORD = os.environ.get("SPLENDOUR_PORTAL_PASSWORD", "")

def get_db():
    client = MongoClient(os.environ.get('MONGO_URL', 'mongodb://localhost:27017'))
    return client[os.environ.get('DB_NAME', 'test_database')]

async def perform_login(page) -> bool:
    """Login to Splendour trade portal"""
    try:
        await page.goto(f'{BASE_URL}/customer/account/login/', timeout=60000)
        await asyncio.sleep(2)
        await page.fill('input[name="email"]', SPLENDOUR_EMAIL)
        await page.fill('input[name="password"]', SPLENDOUR_PASSWORD)
        await page.click('button[type="submit"]:has-text("Login")')
        await asyncio.sleep(3)
        
        if 'login' in page.url:
            return False
        return True
    except Exception as e:
        logger.error(f"Login error: {e}")
        return False

async def extract_product_from_page(page) -> dict:
    """Extract product data from a product detail page"""
    try:
        product = {'url': page.url}
        
        # Get name
        h1 = await page.query_selector('h1')
        if h1:
            product['name'] = (await h1.inner_text()).strip()
        
        if not product.get('name') or 'sorry' in product.get('name', '').lower():
            return None
        
        # Get page text
        page_text = await page.inner_text('body')
        normalized = re.sub(r'\s+', ' ', page_text.replace('\n', ' '))
        
        # SKU / Product ID
        sku_match = re.search(r'SKU[:\s]+([A-Z0-9]+)', normalized, re.I)
        if sku_match:
            product['sku'] = sku_match.group(1)
        
        pid_match = re.search(r'Product ID[:\s]+([A-Z0-9]+)', normalized, re.I)
        if pid_match:
            product['product_id'] = pid_match.group(1)
        
        # Price
        price_match = re.search(r'£\s*([\d.]+)\s*/\s*SQM', normalized, re.I)
        if price_match:
            product['price'] = float(price_match.group(1))
        
        # Stock
        if re.search(r'out\s*of\s*stock', normalized, re.I):
            product['stock_m2'] = 0
            product['in_stock'] = False
        else:
            stock_match = re.search(r'(\d[\d,]*)\s*SQM\s*[Ii]n\s*[Ss]tock', normalized)
            if stock_match:
                product['stock_m2'] = int(stock_match.group(1).replace(',', ''))
                product['in_stock'] = product['stock_m2'] > 0
            else:
                product['stock_m2'] = 0
                product['in_stock'] = False
        
        # Size
        size_match = re.search(r'Size[:\s]+(\d+x\d+(?:x\d+)?(?:x\d+)?mm)', normalized, re.I)
        if size_match:
            product['size'] = size_match.group(1)
        
        # Images
        images = []
        a_elements = await page.query_selector_all('a[href*="m2wholesale"]')
        for a in a_elements:
            href = await a.get_attribute('href')
            if href and 'm2wholesale' in href and ('2300X2300' in href or '650X650' in href):
                if 'video_thumbnail' not in href and '100X100' not in href:
                    clean_url = href.split('?')[0]
                    if clean_url not in images:
                        images.append(clean_url)
        
        if images:
            product['images'] = images[:5]
            product['image'] = images[0]
        
        return product
        
    except Exception as e:
        logger.error(f"Error extracting product: {e}")
        return None

async def search_and_extract_all(page, search_term: str, existing_skus: set, existing_urls: set) -> list:
    """
    Search for a term and extract ALL products from results.
    Returns list of new products not already in database.
    """
    new_products = []
    
    try:
        search_url = f'{BASE_URL}/search?q={search_term}'
        await page.goto(search_url, timeout=30000)
        await asyncio.sleep(2)
        
        # Check if we got results
        page_text = await page.inner_text('body')
        
        # Look for "returned X results"
        results_match = re.search(r'returned\s*(\d+)\s*results?', page_text, re.I)
        if results_match:
            num_results = int(results_match.group(1))
            if num_results == 0:
                return []
            logger.info(f"    Search '{search_term}' returned {num_results} results")
        
        # Get all product links from search results
        product_links = await page.query_selector_all('[data-testid="product-card"] a, .product-card a, .product-item a')
        
        urls_to_visit = set()
        for link in product_links:
            href = await link.get_attribute('href')
            if href:
                full_url = href if href.startswith('http') else BASE_URL + href
                # Skip if already in database
                if full_url not in existing_urls:
                    urls_to_visit.add(full_url)
        
        # Visit each product page and extract data
        for url in urls_to_visit:
            try:
                await page.goto(url, timeout=30000)
                await asyncio.sleep(1)
                
                product = await extract_product_from_page(page)
                
                if product and product.get('name'):
                    # Check if SKU already exists
                    sku = product.get('sku') or product.get('product_id')
                    if sku and sku.upper() not in existing_skus:
                        product['discovered_via_search'] = search_term
                        new_products.append(product)
                        logger.info(f"    NEW PRODUCT: {product.get('name')} (SKU: {sku})")
                    elif not sku:
                        # No SKU found, use URL as identifier
                        product['discovered_via_search'] = search_term
                        new_products.append(product)
                        logger.info(f"    NEW PRODUCT (no SKU): {product.get('name')}")
                        
            except Exception as e:
                logger.error(f"    Error visiting {url}: {e}")
        
    except Exception as e:
        logger.error(f"Search error for '{search_term}': {e}")
    
    return new_products

async def run_deep_search():
    """Main function to run deep search for missing products"""
    
    # Get all "not found" products from previous run
    with open('/app/missing_products_found.json', 'r') as f:
        prev_results = json.load(f)
    
    not_found_skus = [p['sku'] for p in prev_results.get('not_found_products', [])]
    logger.info(f"Loaded {len(not_found_skus)} 'not found' SKUs to deep search")
    
    # Get existing products from database to avoid duplicates
    db = get_db()
    existing_products = list(db.sync_staging.find(
        {'supplier': 'Splendour'},
        {'sku': 1, 'url': 1, '_id': 0}
    ))
    existing_skus = set(str(p.get('sku', '')).upper() for p in existing_products if p.get('sku'))
    existing_urls = set(p.get('url', '') for p in existing_products if p.get('url'))
    
    logger.info(f"Database has {len(existing_skus)} existing SKUs")
    
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("Playwright not installed")
        return {"error": "Playwright not available"}
    
    results = {
        'new_products_found': [],
        'searches_performed': 0,
        'total_new_products': 0,
        'checked_at': datetime.now(timezone.utc).isoformat()
    }
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            # Login
            logger.info("Logging in to Splendour...")
            if not await perform_login(page):
                logger.error("Login failed")
                return {"error": "Login failed"}
            
            logger.info("Login successful. Starting deep search...")
            
            all_new_products = []
            processed_urls = set()  # Track URLs we've already processed
            
            total = len(not_found_skus)
            for i, sku in enumerate(not_found_skus):
                if (i + 1) % 10 == 0 or i == 0:
                    logger.info(f"Progress: {i+1}/{total} | New products found: {len(all_new_products)}")
                
                # Search for this SKU
                new_products = await search_and_extract_all(page, sku, existing_skus, existing_urls | processed_urls)
                results['searches_performed'] += 1
                
                for product in new_products:
                    # Track URL to avoid duplicates
                    if product.get('url'):
                        processed_urls.add(product['url'])
                    
                    # Add to database
                    sku_to_use = product.get('sku') or product.get('product_id') or product['url'].split('/')[-1]
                    
                    product_data = {
                        "supplier": "Splendour",
                        "sku": sku_to_use,
                        "name": product.get('name'),
                        "url": product.get('url'),
                        "price": product.get('price'),
                        "stock_m2": product.get('stock_m2', 0),
                        "in_stock": product.get('in_stock', False),
                        "image": product.get('image'),
                        "images": product.get('images', []),
                        "size": product.get('size'),
                        "synced_at": datetime.now(timezone.utc),
                        "sync_source": "deep_search_recovery",
                        "discovered_via_search": product.get('discovered_via_search')
                    }
                    
                    db.sync_staging.update_one(
                        {"supplier": "Splendour", "sku": sku_to_use},
                        {"$set": product_data},
                        upsert=True
                    )
                    
                    all_new_products.append(product_data)
                    existing_skus.add(sku_to_use.upper())
                
                await asyncio.sleep(0.3)
            
            await browser.close()
            
            results['new_products_found'] = all_new_products
            results['total_new_products'] = len(all_new_products)
    
    except Exception as e:
        logger.error(f"Error: {e}")
        results['error'] = str(e)
    
    # Save results
    output_path = '/app/deep_search_results.json'
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    logger.info(f"Results saved to {output_path}")
    
    # Print summary
    print("\n" + "="*70)
    print("DEEP SEARCH RESULTS - SUMMARY")
    print("="*70)
    print(f"Searches performed: {results['searches_performed']}")
    print(f"NEW products discovered and added: {results['total_new_products']}")
    print("="*70)
    
    if results['new_products_found']:
        print("\nNEW PRODUCTS FOUND:")
        print("-"*70)
        for p in results['new_products_found']:
            print(f"  {p['sku']}: {p['name']}")
            print(f"    Discovered via search: {p.get('discovered_via_search', 'N/A')}")
            if p.get('price'):
                print(f"    Price: £{p['price']}/SQM | Stock: {p.get('stock_m2', 0)} SQM")
            print()
    
    return results

if __name__ == "__main__":
    asyncio.run(run_deep_search())

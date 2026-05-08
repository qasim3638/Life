"""
Splendour Fresh Deep Scan
==========================
This script performs a FRESH deep scan of all Splendour products and saves
to a NEW collection (sync_staging_fresh) to avoid overwriting existing data.

Once verified, the data can be copied to sync_staging.
"""

import asyncio
import re
import os
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List
from pymongo import MongoClient

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration from business rules
BASE_URL = "https://www.splendourtiles.co.uk"
SPLENDOUR_EMAIL = "accounts@tilestation.co.uk"
SPLENDOUR_PASSWORD = os.environ.get("SPLENDOUR_PORTAL_PASSWORD", "")

# Categories to sync (from business rules - excludes adhesive-grout and essentials)
CATEGORIES = [
    '/wall-tiles',
    '/floor-tiles',
    '/outdoor-tiles',
    '/new-collections',
]

# Target collection for fresh scan (NOT sync_staging to preserve existing data)
FRESH_COLLECTION = "sync_staging_fresh"

MAX_PAGINATION_CLICKS = 100
REQUEST_DELAY = 0.8

def get_db():
    client = MongoClient(os.environ.get('MONGO_URL', 'mongodb://localhost:27017'))
    return client[os.environ.get('DB_NAME', 'test_database')]


async def perform_login(page) -> bool:
    """Login to Splendour trade portal"""
    try:
        logger.info(f"Logging in as {SPLENDOUR_EMAIL}...")
        await page.goto(f'{BASE_URL}/customer/account/login/', timeout=60000)
        await asyncio.sleep(2)
        await page.fill('input[name="email"]', SPLENDOUR_EMAIL)
        await page.fill('input[name="password"]', SPLENDOUR_PASSWORD)
        await page.click('button[type="submit"]:has-text("Login")')
        await asyncio.sleep(3)
        
        if 'login' in page.url:
            logger.error("Login failed - still on login page")
            return False
        logger.info("Login successful!")
        return True
    except Exception as e:
        logger.error(f"Login error: {e}")
        return False


async def click_load_more_until_done(page, selector: str, context: str, max_clicks: int = MAX_PAGINATION_CLICKS) -> int:
    """Click a 'load more' button until it disappears or max clicks reached"""
    clicks = 0
    while clicks < max_clicks:
        try:
            button = await page.query_selector(selector)
            if not button:
                break
            is_visible = await button.is_visible()
            if not is_visible:
                break
            await button.click()
            clicks += 1
            await asyncio.sleep(1.5)
        except Exception as e:
            break
    if clicks > 0:
        logger.info(f"  {context}: Clicked load more {clicks} times")
    return clicks


async def get_all_subcategories(page, category_url: str, category_name: str) -> List[str]:
    """Get all subcategories from a main category page"""
    subcategories = []
    
    try:
        await page.goto(category_url, timeout=60000)
        await asyncio.sleep(2)
        
        # Click LOAD NEXT to load all subcategories
        load_next_selectors = [
            'button:has-text("LOAD NEXT")',
            'button:has-text("Load Next")',
            'a:has-text("LOAD NEXT")',
        ]
        for selector in load_next_selectors:
            await click_load_more_until_done(page, selector, f"Subcategories for {category_name}")
        
        # Extract subcategory links
        links = await page.query_selector_all('a')
        cat_path = category_url.replace(BASE_URL, '')
        
        for link in links:
            href = await link.get_attribute('href')
            if href and href.startswith(f'{cat_path}/'):
                full_url = BASE_URL + href if href.startswith('/') else href
                path_parts = full_url.replace(BASE_URL, '').strip('/').split('/')
                if len(path_parts) <= 3 and full_url not in subcategories:
                    subcategories.append(full_url)
        
        logger.info(f"  Found {len(subcategories)} subcategories in {category_name}")
        
    except Exception as e:
        logger.error(f"Error getting subcategories from {category_url}: {e}")
    
    return subcategories


async def get_products_from_subcategory(page, subcategory_url: str, subcategory_name: str) -> List[str]:
    """Get all product URLs from a subcategory page using product cards"""
    product_urls = []
    
    try:
        await page.goto(subcategory_url, timeout=60000)
        await asyncio.sleep(2)
        
        # Click LOAD MORE to load all products
        load_more_selectors = [
            'button:has-text("LOAD MORE")',
            'button:has-text("Load More")',
            'button:has-text("Show More")',
            'a:has-text("LOAD MORE")',
        ]
        for selector in load_more_selectors:
            clicks = await click_load_more_until_done(page, selector, f"Products in {subcategory_name}")
            if clicks > 0:
                break
        
        # Extract product URLs using product card selectors (CORRECT method from business rules)
        product_cards = await page.query_selector_all('[data-testid="product-card"], .product-card, .product-item, article[class*="product"]')
        
        for card in product_cards:
            link = await card.query_selector('a')
            if link:
                href = await link.get_attribute('href')
                if href:
                    if href.startswith('/'):
                        href = BASE_URL + href
                    clean_url = href.split('?')[0]
                    if clean_url not in product_urls and not any(x in clean_url for x in ['/customer/', '/checkout/', '/cart/', '/account/']):
                        product_urls.append(clean_url)
        
        # Fallback: Also check for dimension-pattern URLs
        if not product_urls:
            links = await page.query_selector_all('a')
            for link in links:
                href = await link.get_attribute('href')
                if href and re.search(r'\d+x\d+', href):
                    if href.startswith('/'):
                        href = BASE_URL + href
                    clean_url = href.split('?')[0]
                    if clean_url not in product_urls:
                        product_urls.append(clean_url)
        
        logger.info(f"  Found {len(product_urls)} products in {subcategory_name}")
        
    except Exception as e:
        logger.error(f"Error getting products from {subcategory_url}: {e}")
    
    return product_urls


async def extract_product_data(page) -> Optional[Dict]:
    """Extract ALL product data from a product detail page"""
    try:
        product = {"url": page.url}
        
        # Get name
        h1 = await page.query_selector('h1')
        if h1:
            product['name'] = (await h1.inner_text()).strip()
        
        if not product.get('name') or 'sorry' in product.get('name', '').lower():
            return None
        
        # Get page text for regex extraction
        page_text = await page.inner_text('body')
        normalized = re.sub(r'\s+', ' ', page_text.replace('\n', ' '))
        
        # SKU
        sku_match = re.search(r'SKU[:\s]+([A-Z0-9]+)', normalized, re.I)
        if sku_match:
            product['sku'] = sku_match.group(1)
        else:
            # Try Product ID
            pid_match = re.search(r'Product ID[:\s]+([A-Z0-9]+)', normalized, re.I)
            if pid_match:
                product['sku'] = pid_match.group(1)
            else:
                # Generate from URL
                url_slug = page.url.split('/')[-1].split('?')[0]
                product['sku'] = url_slug.upper().replace('-', '')[:20]
                product['sku_generated'] = True
        
        # Price (per SQM) - this is the COST price from Splendour
        price_match = re.search(r'£\s*([\d.]+)\s*/\s*SQM', normalized, re.I)
        if price_match:
            product['cost_price'] = float(price_match.group(1))
            # Calculate list price using Verona formula (2.3x markup)
            product['list_price'] = round(product['cost_price'] * 2.3, 2)
        
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
        size_match = re.search(r'Size[:\s]+(\d+x\d+(?:x\d+)?(?:mm)?)', normalized, re.I)
        if size_match:
            product['size'] = size_match.group(1)
        
        # Material
        mat_match = re.search(r'Material[:\s]+(\w+)', normalized, re.I)
        if mat_match:
            product['material'] = mat_match.group(1)
        
        # Finish
        finish_match = re.search(r'Finish[:\s]+(\w+)', normalized, re.I)
        if finish_match:
            product['finish'] = finish_match.group(1)
        
        # Images - extract high-res URLs
        images = []
        a_elements = await page.query_selector_all('a[href*="m2wholesale"]')
        for a in a_elements:
            href = await a.get_attribute('href')
            if href and 'm2wholesale' in href:
                if '2300X2300' in href or '650X650' in href:
                    if 'video_thumbnail' not in href and '100X100' not in href:
                        clean_url = href.split('?')[0]
                        if clean_url not in images:
                            images.append(clean_url)
        
        if images:
            product['images'] = images[:10]
            product['image'] = images[0]
        else:
            product['images'] = []
            product['image'] = None
        
        return product
        
    except Exception as e:
        logger.error(f"Error extracting product data: {e}")
        return None


async def discover_via_search(page) -> List[str]:
    """Discover additional products via search (from business rules)"""
    all_products = []
    
    search_terms = [
        'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm',
        'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z',
        '1', '2', '3', '4', '5', '6', '7', '8', '9', '0',
        'marble', 'wood', 'stone', 'metro', 'terrazzo', 'vintage', 'signature'
    ]
    
    logger.info(f"Starting search discovery with {len(search_terms)} terms...")
    
    for i, term in enumerate(search_terms):
        try:
            search_url = f'{BASE_URL}/search?q={term}'
            await page.goto(search_url, timeout=30000)
            await asyncio.sleep(1.5)
            
            # Click load more
            for selector in ['button:has-text("LOAD MORE")', 'button:has-text("Load More")']:
                await click_load_more_until_done(page, selector, f"Search '{term}'", max_clicks=20)
            
            # Extract product URLs
            product_cards = await page.query_selector_all('[data-testid="product-card"], .product-card, .product-item')
            for card in product_cards:
                link = await card.query_selector('a')
                if link:
                    href = await link.get_attribute('href')
                    if href:
                        if href.startswith('/'):
                            href = BASE_URL + href
                        clean_url = href.split('?')[0]
                        if clean_url not in all_products and '/search' not in clean_url:
                            all_products.append(clean_url)
            
            if (i + 1) % 10 == 0:
                logger.info(f"  Search progress: {i+1}/{len(search_terms)} | Found {len(all_products)} products")
            
        except Exception as e:
            logger.error(f"Error searching '{term}': {e}")
    
    logger.info(f"Search discovery complete: {len(all_products)} products found")
    return all_products


async def run_fresh_deep_scan():
    """Main function to run a fresh deep scan"""
    
    logger.info("="*70)
    logger.info("SPLENDOUR FRESH DEEP SCAN")
    logger.info("="*70)
    logger.info(f"Target collection: {FRESH_COLLECTION}")
    logger.info(f"Categories: {CATEGORIES}")
    logger.info("="*70)
    
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("Playwright not installed")
        return {"error": "Playwright not available"}
    
    db = get_db()
    
    # Clear the fresh collection before starting
    db[FRESH_COLLECTION].delete_many({'supplier': 'Splendour'})
    logger.info(f"Cleared {FRESH_COLLECTION} collection")
    
    results = {
        'total_products_found': 0,
        'products_synced': 0,
        'products_failed': 0,
        'has_cost_price': 0,
        'has_list_price': 0,
        'has_images': 0,
        'started_at': datetime.now(timezone.utc).isoformat(),
        'completed_at': None
    }
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            # Login
            if not await perform_login(page):
                return {"error": "Login failed"}
            
            # ============ PHASE 1: DISCOVER ALL PRODUCT URLs ============
            logger.info("\n" + "="*50)
            logger.info("PHASE 1: DISCOVERING ALL PRODUCTS")
            logger.info("="*50)
            
            all_product_urls = []
            
            # Crawl categories
            for category in CATEGORIES:
                category_url = BASE_URL + category
                category_name = category.strip('/')
                logger.info(f"\nCrawling category: {category_name}")
                
                subcategories = await get_all_subcategories(page, category_url, category_name)
                
                for subcat_url in subcategories:
                    subcat_name = subcat_url.split('/')[-1]
                    products = await get_products_from_subcategory(page, subcat_url, subcat_name)
                    all_product_urls.extend(products)
            
            # Deduplicate
            all_product_urls = list(set(all_product_urls))
            logger.info(f"\nFound {len(all_product_urls)} products from category crawling")
            
            # Search discovery
            logger.info("\n" + "="*50)
            logger.info("PHASE 1b: SEARCH DISCOVERY")
            logger.info("="*50)
            
            search_products = await discover_via_search(page)
            all_product_urls.extend(search_products)
            
            # Final dedupe
            all_product_urls = list(set(all_product_urls))
            results['total_products_found'] = len(all_product_urls)
            logger.info(f"\nTOTAL UNIQUE PRODUCTS: {len(all_product_urls)}")
            
            # ============ PHASE 2: EXTRACT DATA FROM EACH PRODUCT ============
            logger.info("\n" + "="*50)
            logger.info("PHASE 2: EXTRACTING PRODUCT DATA")
            logger.info("="*50)
            
            total = len(all_product_urls)
            for i, product_url in enumerate(all_product_urls):
                if (i + 1) % 50 == 0 or i == 0:
                    logger.info(f"Progress: {i+1}/{total} | Synced: {results['products_synced']} | Failed: {results['products_failed']}")
                
                try:
                    await page.goto(product_url, timeout=30000)
                    await asyncio.sleep(REQUEST_DELAY)
                    
                    product = await extract_product_data(page)
                    
                    if product and product.get('name'):
                        product_data = {
                            "supplier": "Splendour",
                            "sku": product.get('sku'),
                            "name": product['name'],
                            "url": product['url'],
                            "cost_price": product.get('cost_price'),
                            "list_price": product.get('list_price'),
                            "stock_m2": product.get('stock_m2', 0),
                            "in_stock": product.get('in_stock', False),
                            "image": product.get('image'),
                            "images": product.get('images', []),
                            "size": product.get('size'),
                            "material": product.get('material'),
                            "finish": product.get('finish'),
                            "synced_at": datetime.now(timezone.utc),
                            "sync_source": "fresh_deep_scan",
                            "sku_generated": product.get('sku_generated', False)
                        }
                        
                        # Save to FRESH collection
                        db[FRESH_COLLECTION].update_one(
                            {"supplier": "Splendour", "sku": product_data['sku']},
                            {"$set": product_data},
                            upsert=True
                        )
                        
                        results['products_synced'] += 1
                        if product.get('cost_price'):
                            results['has_cost_price'] += 1
                        if product.get('list_price'):
                            results['has_list_price'] += 1
                        if product.get('images'):
                            results['has_images'] += 1
                    else:
                        results['products_failed'] += 1
                        
                except Exception as e:
                    results['products_failed'] += 1
                    logger.error(f"Error syncing {product_url}: {e}")
            
            await browser.close()
    
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        results['error'] = str(e)
    
    results['completed_at'] = datetime.now(timezone.utc).isoformat()
    
    # Save results
    with open('/app/fresh_deep_scan_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    # Print summary
    print("\n" + "="*70)
    print("FRESH DEEP SCAN - COMPLETE")
    print("="*70)
    print(f"Total products discovered: {results['total_products_found']}")
    print(f"Products synced: {results['products_synced']}")
    print(f"Products failed: {results['products_failed']}")
    print(f"Has cost_price: {results['has_cost_price']}")
    print(f"Has list_price: {results['has_list_price']}")
    print(f"Has images: {results['has_images']}")
    print(f"\nData saved to collection: {FRESH_COLLECTION}")
    print("="*70)
    
    return results


if __name__ == "__main__":
    asyncio.run(run_fresh_deep_scan())

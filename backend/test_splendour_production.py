#!/usr/bin/env python3
"""
Splendour Production Sync Test Script
- Logs into splendourtiles.co.uk
- Crawls subcategories automatically
- Extracts products with SKU, price, stock
- Syncs to production API
"""

import asyncio
import re
import json
import httpx
from playwright.async_api import async_playwright

# Production API
PRODUCTION_API = "https://tile-station-production.up.railway.app"

# Splendour credentials
SPLENDOUR_EMAIL = "accounts@tilestation.co.uk"
SPLENDOUR_PASSWORD = "Tilestation_133"

async def extract_products_from_page(page):
    """Extract products from current listing page"""
    products = []
    
    # Get all product items
    product_items = await page.query_selector_all('li.product-item, .product-items li')
    
    for item in product_items:
        try:
            product = {}
            
            # Get product link and name
            name_link = await item.query_selector('.product-item-link, .product-name a, a.product-item-link')
            if name_link:
                product['name'] = (await name_link.inner_text()).strip()
                product['url'] = await name_link.get_attribute('href')
            
            # Get image
            img = await item.query_selector('img.product-image-photo, img')
            if img:
                src = await img.get_attribute('src') or await img.get_attribute('data-src')
                if src:
                    product['images'] = [src]
            
            # Try to get price from listing
            price_el = await item.query_selector('.price, [data-price-amount]')
            if price_el:
                price_text = await price_el.inner_text()
                price_match = re.search(r'£([\d.]+)', price_text)
                if price_match:
                    product['price'] = float(price_match.group(1))
            
            # Extract SKU from URL if possible
            if product.get('url'):
                url_match = re.search(r'/([a-z])(\d+)', product['url'], re.I)
                if url_match:
                    product['sku'] = url_match.group(1).upper() + url_match.group(2)
            
            if product.get('name'):
                products.append(product)
                
        except Exception as e:
            print(f"Error extracting product: {e}")
            continue
    
    return products

async def get_product_details(page, url):
    """Visit product detail page and extract full details"""
    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        await asyncio.sleep(1)
        
        product = {'url': url}
        
        # Get name
        name_el = await page.query_selector('h1.page-title, h1[itemprop="name"], .product-info-main h1, h1')
        if name_el:
            product['name'] = (await name_el.inner_text()).strip()
        
        # Get page text for parsing
        page_text = await page.inner_text('body')
        
        # Get SKU from table
        tables = await page.query_selector_all('table')
        for table in tables:
            rows = await table.query_selector_all('tr')
            for row in rows:
                cells = await row.query_selector_all('td, th')
                if len(cells) >= 2:
                    label = (await cells[0].inner_text()).strip().lower()
                    value = (await cells[1].inner_text()).strip()
                    if label == 'code' and value:
                        product['sku'] = value
                        break
            if product.get('sku'):
                break
        
        # Fallback: get SKU from URL
        if not product.get('sku'):
            url_match = re.search(r'/([a-z])(\d+)', url, re.I)
            if url_match:
                product['sku'] = url_match.group(1).upper() + url_match.group(2)
        
        # Get price per m²
        price_patterns = [
            r'£([\d.]+)\s*per\s*m²',
            r'£([\d.]+)\s*per\s*m2',
            r'£([\d.]+)\s*/\s*m²',
            r'£([\d.]+)\s*/m²',
            r'£([\d.]+)\s*m²'
        ]
        for pattern in price_patterns:
            match = re.search(pattern, page_text, re.I)
            if match:
                product['price'] = float(match.group(1))
                break
        
        # Get stock
        if re.search(r'out\s*of\s*stock', page_text, re.I):
            product['in_stock'] = False
            product['stock_m2'] = 0
        else:
            stock_patterns = [
                r'in\s*stock[:\s]+(\d[\d,]*)\s*\((\d+)\s*m²?\)',
                r'in\s*stock[:\s]+(\d[\d,]*)\s*\((\d+)\s*m2?\)',
                r'in\s*stock[:\s]+(\d[\d,]*)'
            ]
            for pattern in stock_patterns:
                match = re.search(pattern, page_text, re.I)
                if match:
                    first_num = int(match.group(1).replace(',', ''))
                    second_num = int(match.group(2)) if match.lastindex >= 2 else None
                    
                    if second_num is not None:
                        product['stock_m2'] = second_num
                    else:
                        product['stock_m2'] = first_num
                    
                    product['in_stock'] = first_num > 0
                    break
        
        return product
        
    except Exception as e:
        print(f"Error getting details from {url}: {e}")
        return None

async def sync_to_production(products):
    """Send products to production API"""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{PRODUCTION_API}/api/supplier-sync/splendour/products",
                json={
                    "products": products,
                    "source": "production_test_crawler"
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Synced {result.get('synced', 0)} products to production")
                return result
            else:
                print(f"❌ API Error: {response.status_code} - {response.text}")
                return None
                
    except Exception as e:
        print(f"❌ Sync error: {e}")
        return None

async def main():
    print("=" * 60)
    print("SPLENDOUR PRODUCTION SYNC TEST")
    print("=" * 60)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        
        # Step 1: Login to Splendour
        print("\n[1/5] Logging in to splendourtiles.co.uk...")
        await page.goto('https://www.splendourtiles.co.uk/customer/account/login/', timeout=60000)
        await asyncio.sleep(3)
        
        # Fill login form - use name attributes since ids are None
        await page.fill('input[name="email"]', SPLENDOUR_EMAIL)
        await page.fill('input[name="password"]', SPLENDOUR_PASSWORD)
        await page.click('button[type="submit"]:has-text("Login")')
        await asyncio.sleep(4)
        
        # Check login success
        current_url = page.url
        if 'login' not in current_url:
            print("✅ Login successful!")
        else:
            print("⚠️ Login may have failed, continuing anyway...")
        
        # Step 2: Navigate to Wall Tiles category
        print("\n[2/5] Navigating to Wall Tiles category...")
        await page.goto('https://www.splendourtiles.co.uk/wall-tiles', timeout=60000)
        await asyncio.sleep(2)
        
        # Step 3: Find all subcategories
        print("\n[3/5] Finding subcategories...")
        subcategory_links = await page.query_selector_all('a[href*="/wall-tiles/"], a[href*="/floor-tiles/"]')
        subcategories = set()
        
        for link in subcategory_links:
            href = await link.get_attribute('href')
            if href:
                # Make URL absolute if relative
                if href.startswith('/'):
                    href = 'https://www.splendourtiles.co.uk' + href
                if '/wall-tiles/' in href:
                    subcategories.add(href.split('?')[0])
        
        # Also check floor tiles
        await page.goto('https://www.splendourtiles.co.uk/floor-tiles', timeout=60000)
        await asyncio.sleep(1)
        
        floor_links = await page.query_selector_all('a[href*="/floor-tiles/"]')
        for link in floor_links:
            href = await link.get_attribute('href')
            if href:
                if href.startswith('/'):
                    href = 'https://www.splendourtiles.co.uk' + href
                if '/floor-tiles/' in href:
                    subcategories.add(href.split('?')[0])
        
        print(f"Found {len(subcategories)} subcategories")
        
        # Step 4: Crawl each subcategory and extract products
        print("\n[4/5] Crawling subcategories...")
        all_products = []
        products_seen = set()
        
        # Limit to first 5 subcategories for quick test
        subcategories_list = list(subcategories)[:5]
        
        for i, subcat_url in enumerate(subcategories_list):
            print(f"\n  [{i+1}/{len(subcategories_list)}] Crawling: {subcat_url}")
            
            try:
                await page.goto(subcat_url, timeout=60000)
                await asyncio.sleep(2)
                
                # Scroll to load all products
                await page.evaluate('''async () => {
                    const totalHeight = document.body.scrollHeight;
                    const step = window.innerHeight;
                    for (let pos = 0; pos < totalHeight; pos += step) {
                        window.scrollTo(0, pos);
                        await new Promise(r => setTimeout(r, 300));
                    }
                }''')
                await asyncio.sleep(1)
                
                # Find all product URLs on this page
                product_links = await page.query_selector_all('a.product-item-link, .product-item a')
                product_urls = set()
                
                for link in product_links:
                    href = await link.get_attribute('href')
                    if href:
                        # Make URL absolute if relative
                        if href.startswith('/'):
                            href = 'https://www.splendourtiles.co.uk' + href
                        if 'tile' in href.lower() or re.search(r'\d+x\d+', href):
                            clean_url = href.split('?')[0]
                            if clean_url not in products_seen:
                                product_urls.add(clean_url)
                                products_seen.add(clean_url)
                
                print(f"    Found {len(product_urls)} unique products")
                
                # Get details for first 10 products from this category
                for j, prod_url in enumerate(list(product_urls)[:10]):
                    product = await get_product_details(page, prod_url)
                    if product and product.get('name'):
                        all_products.append(product)
                        print(f"    ✓ {product.get('sku', 'N/A')}: {product.get('name', 'Unknown')[:40]}... (£{product.get('price', 0)}, Stock: {product.get('stock_m2', 0)}m²)")
                    
                    if j >= 9:  # Limit to 10 products per category for test
                        break
                        
            except Exception as e:
                print(f"    ❌ Error crawling {subcat_url}: {e}")
                continue
        
        print(f"\n  Total products extracted: {len(all_products)}")
        
        # Step 5: Sync to production
        print("\n[5/5] Syncing to production Sync Hub...")
        
        if all_products:
            result = await sync_to_production(all_products)
            
            if result:
                print("\n" + "=" * 60)
                print("SYNC COMPLETE!")
                print("=" * 60)
                print(f"  Products sent: {len(all_products)}")
                print(f"  Synced: {result.get('synced', 0)}")
                print(f"  New: {result.get('new', 0)}")
                print(f"  Updated: {result.get('updated', 0)}")
                print(f"  Errors: {result.get('errors', 0)}")
                print("\n📍 Check results at: https://tile-station-production.up.railway.app")
                print("   Navigate to: Products & Suppliers > Sync Hub > Splendour tab")
        else:
            print("❌ No products to sync")
        
        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())

"""
Fix Missing Prices for Splendour Products
==========================================
This script searches for specific products on Splendour website
and updates their prices in the production database.

Only targets the 37 products identified as missing prices.
"""

import asyncio
import re
import os
import json
from datetime import datetime, timezone
from playwright.async_api import async_playwright
import math

# Production API
PROD_API = "https://tile-station-production.up.railway.app"

# Splendour credentials
BASE_URL = "https://www.splendourtiles.co.uk"
EMAIL = "accounts@tilestation.co.uk"
PASSWORD = os.environ.get("SPLENDOUR_PORTAL_PASSWORD", "")

# Pricing formula from business rules
def calculate_list_price(cost: float) -> float:
    """Calculate list price: (Cost * 1.90) * 1.20, rounded up to .99"""
    if cost and cost > 0:
        raw_price = cost * 1.90 * 1.20
        whole = math.ceil(raw_price)
        return whole - 0.01
    return 0

# Products without prices (from investigation)
PRODUCTS_TO_FIX = [
    {"sku": "802141", "name": "LTP Multipurpose Cleaner 500ml"},
    {"sku": "802033", "name": "Rock-Tite Brush In Grout Blanched Almond"},
    {"sku": "802034", "name": "Kitkat White Mosaic"},
    {"sku": "802035", "name": "Kitkat Blue Mosaic"},
    {"sku": "802036", "name": "Kitkat Blue Two Tone Mosaic"},
    {"sku": "ESCVICBLAMOS", "name": "Victorian Black Mosaic"},
    {"sku": "ESCVICREDBOR", "name": "Victorian Red & Black Border"},
    {"sku": "ESCVICREDCHE", "name": "Victorian Red & Black Chequer Mosaic"},
    {"sku": "ESCVICREDCOR", "name": "Victorian Red & Black Corner"},
    {"sku": "ESCVICREDMOS", "name": "Victorian Red Mosaic"},
    {"sku": "ESCVICWHTBOR", "name": "Victorian White & Black Border"},
    {"sku": "ESCVICWHTCHE", "name": "Victorian White & Black Chequer Mosaic"},
    {"sku": "ESCVICWHTCOR", "name": "Victorian White & Black Corner"},
    {"sku": "ESCVICWHTMOS", "name": "Victorian White Mosaic"},
    {"sku": "800291", "name": "Pixel White Hexagon Gloss 23x23"},
    {"sku": "GREARARED15", "name": "Aragon Red Quarry Flat 15x15"},
    {"sku": "800289", "name": "Pixel White Herringbone Gloss 22x73"},
    {"sku": "800285", "name": "Pixel White Hexagon Gloss 50x50"},
    {"sku": "GREARAFLAMERE", "name": "Aragon Flame Brown Quarry R.E 15x15"},
    {"sku": "400945", "name": "Crossover Mosaic White Tile 300x600"},
    {"sku": "800284", "name": "Pixel White Hexagon Matt 50x50"},
    {"sku": "GREARAREDRE", "name": "Aragon Red Quarry R.E 15x15"},
    {"sku": "800296", "name": "Pixel Sea Blend 25x25"},
    {"sku": "800331", "name": "Pixel Ocean Blend 243 25x25"},
    {"sku": "PERMUMGRYSK", "name": "Mumble G Grey Skirting Wood Effect Tile 7.5x45"},
    {"sku": "800283", "name": "Pixel White Square Gloss 50x50"},
    {"sku": "800288", "name": "Pixel White Herringbone Matt 22x73"},
    {"sku": "800282", "name": "Pixel Pool Blend 241 25x25"},
    {"sku": "800280", "name": "Pixel White Square Gloss 25x25"},
    {"sku": "800292", "name": "Pixel Black Hexagon Matt 23x23"},
    {"sku": "GREARAREDREX", "name": "Aragon Red Quarry R.E.X 15x15"},
    {"sku": "GREARAFLAMEREX22", "name": "Aragon Flame Brown Quarry R.E.X 15x15"},
    {"sku": "800294", "name": "Pixel White Brick Matt 23x48"},
    {"sku": "800330", "name": "Pixel Chequer Hexagon White & Black Matt 23x23"},
    {"sku": "800286", "name": "Pixel Black Hexagon 50x50 Matt"},
    {"sku": "GREARAFLAME15", "name": "Aragon Flame Brown Quarry Flat 15x15"},
    {"sku": "800290", "name": "Pixel White Hexagon Matt 23x23"},
]


async def login(page):
    """Login to Splendour trade account"""
    print("Logging in to Splendour...")
    await page.goto(f"{BASE_URL}/customer/account/login/", wait_until="networkidle")
    await page.fill('input[name="email"], input[type="email"]', EMAIL)
    await page.fill('input[name="password"], input[type="password"]', PASSWORD)
    await page.click('button[type="submit"], input[type="submit"]')
    await asyncio.sleep(3)
    print("Login complete")


async def search_product(page, search_term: str):
    """Search for a product and return results"""
    search_url = f"{BASE_URL}/search?q={search_term.replace(' ', '+')}"
    await page.goto(search_url, wait_until="networkidle")
    await asyncio.sleep(1)
    
    # Get all product links from search results
    product_links = []
    links = await page.query_selector_all('a')
    for link in links:
        href = await link.get_attribute('href')
        if href and BASE_URL in href and '/customer/' not in href and '/cart/' not in href:
            # Check if it's a product page (has dimensions or looks like a product)
            if re.search(r'\d+x\d+', href) or '/tiles' in href.lower():
                if href not in product_links:
                    product_links.append(href)
    
    return product_links[:10]  # Return top 10 results


async def extract_price_from_page(page):
    """Extract cost price from product page"""
    try:
        page_text = await page.inner_text('body')
        normalized = re.sub(r'\s+', ' ', page_text.replace('\n', ' '))
        
        # Get SKU
        sku = None
        sku_match = re.search(r'SKU[:\s]+([A-Z0-9]+)', normalized, re.I)
        if sku_match:
            sku = sku_match.group(1)
        
        # Get cost price (trade price per SQM)
        cost_price = None
        price_match = re.search(r'£\s*([\d.]+)\s*/\s*SQM', normalized, re.I)
        if price_match:
            cost_price = float(price_match.group(1))
        
        # Get name
        name = None
        h1 = await page.query_selector('h1')
        if h1:
            name = await h1.inner_text()
        
        return {
            "sku": sku,
            "cost_price": cost_price,
            "name": name,
            "url": page.url
        }
    except Exception as e:
        print(f"Error extracting price: {e}")
        return None


async def fix_missing_prices():
    """Main function to fix missing prices"""
    results = {
        "found": [],
        "not_found": [],
        "errors": []
    }
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Login first
        await login(page)
        
        # Process each product
        for i, product in enumerate(PRODUCTS_TO_FIX):
            sku = product["sku"]
            name = product["name"]
            print(f"\n[{i+1}/{len(PRODUCTS_TO_FIX)}] Searching for: {sku} - {name}")
            
            try:
                # Try searching by SKU first
                search_results = await search_product(page, sku)
                
                # If no results, try searching by name
                if not search_results:
                    # Extract key words from name
                    search_term = name.split()[0]  # First word
                    search_results = await search_product(page, search_term)
                
                if search_results:
                    # Visit first result and extract price
                    await page.goto(search_results[0], wait_until="networkidle")
                    await asyncio.sleep(1)
                    
                    price_data = await extract_price_from_page(page)
                    
                    if price_data and price_data.get("cost_price"):
                        cost = price_data["cost_price"]
                        list_price = calculate_list_price(cost)
                        
                        results["found"].append({
                            "sku": sku,
                            "name": name,
                            "cost_price": cost,
                            "list_price": list_price,
                            "url": price_data.get("url"),
                            "found_sku": price_data.get("sku")
                        })
                        print(f"  ✅ Found: Cost £{cost} -> List £{list_price}")
                    else:
                        results["not_found"].append({
                            "sku": sku,
                            "name": name,
                            "reason": "No price on page"
                        })
                        print(f"  ❌ No price found on page")
                else:
                    results["not_found"].append({
                        "sku": sku,
                        "name": name,
                        "reason": "No search results"
                    })
                    print(f"  ❌ No search results")
                    
            except Exception as e:
                results["errors"].append({
                    "sku": sku,
                    "name": name,
                    "error": str(e)
                })
                print(f"  ⚠️ Error: {e}")
            
            # Small delay between searches
            await asyncio.sleep(1)
        
        await browser.close()
    
    # Save results
    with open('/tmp/price_fix_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n{'='*50}")
    print(f"RESULTS SUMMARY")
    print(f"{'='*50}")
    print(f"Found: {len(results['found'])}")
    print(f"Not Found: {len(results['not_found'])}")
    print(f"Errors: {len(results['errors'])}")
    print(f"\nResults saved to /tmp/price_fix_results.json")
    
    return results


if __name__ == "__main__":
    asyncio.run(fix_missing_prices())

"""
Wallcano Product Data Processing Script
- Extracts cost prices from wallcano_prices.json  
- Generates unique product names (Range + Color/Description + Size + Finish)
- Calculates list price: Cost × 2.28, rounded to nearest .99
- Updates the supplier_products collection
"""
import json
import os
import re
from pymongo import MongoClient
from datetime import datetime, timezone

# Load price data
PRICES_FILE = "/app/supplier_data/wallcano_prices.json"
PRODUCTS_FILE = "/app/supplier_data/wallcano_products.json"

def load_price_data():
    """Load cost prices from the prices JSON file"""
    with open(PRICES_FILE, 'r') as f:
        return json.load(f)

def load_products_data():
    """Load product details from the products JSON file"""
    with open(PRODUCTS_FILE, 'r') as f:
        return json.load(f)

def extract_size_from_name(name):
    """Extract size like '60X120', '30X45' from product name"""
    # Match patterns like 60X120, 30X45, 80X80, 100X100
    match = re.search(r'(\d+)X(\d+)', name, re.IGNORECASE)
    if match:
        w, h = match.groups()
        return f"{w}x{h}"
    return None

def extract_range_from_name(name):
    """Extract the range/series name (first word or two before size)"""
    # Remove size pattern and "CM"
    clean = re.sub(r'\d+X\d+\s*CM?', '', name, flags=re.IGNORECASE).strip()
    # Remove finish indicators at end
    clean = re.sub(r'\s*(POLISHED|MATT|HIGH-GLOSS|CARVING|ENDLESS)\s*$', '', clean, flags=re.IGNORECASE).strip()
    return clean

def calculate_list_price(cost_price):
    """
    Calculate list price using formula: Cost × 2.28, rounded to nearest .99
    Example: 12.99 × 2.28 = 29.62 → round to 29.99
    """
    if not cost_price or cost_price <= 0:
        return None
    
    raw_price = cost_price * 2.28
    # Round to nearest .99
    whole_part = int(raw_price)
    decimal_part = raw_price - whole_part
    
    if decimal_part >= 0.50:
        # Round up to next .99
        return float(whole_part + 1) - 0.01  # e.g., 30.99
    else:
        # Keep current whole part and add .99
        return float(whole_part) - 0.01  # e.g., 29.99

def generate_unique_name(supplier_name, finish):
    """
    Generate a unique product name from supplier name
    Format: Range/Series + Size + Finish
    Example: "ALLURE GREY POLISHED 60X120 CM" → "Allure Grey 60x120 Polished"
    """
    # Extract size
    size = extract_size_from_name(supplier_name)
    
    # Extract range name (everything except size and finish)
    range_name = extract_range_from_name(supplier_name)
    
    # Title case the range name
    range_name = range_name.title()
    
    # Format finish
    finish_formatted = ""
    if finish:
        finish_lower = finish.lower()
        if 'polished' in finish_lower:
            finish_formatted = "Polished"
        elif 'matt' in finish_lower:
            finish_formatted = "Matt"
        elif 'high' in finish_lower and 'gloss' in finish_lower:
            finish_formatted = "High Gloss"
        elif 'carving' in finish_lower:
            finish_formatted = "Carving"
        elif 'feature' in finish_lower:
            finish_formatted = "Feature"
        else:
            finish_formatted = finish.title()
    
    # Build the unique name
    parts = [range_name]
    if size:
        parts.append(size)
    if finish_formatted:
        parts.append(finish_formatted)
    
    return " ".join(parts)

def process_wallcano_products():
    """Main processing function"""
    # Connect to database
    client = MongoClient(os.environ.get('MONGO_URL'))
    db = client[os.environ.get('DB_NAME', 'test_database')]
    
    # Load data
    prices = load_price_data()
    products_data = load_products_data()
    
    # Create SKU to product data mapping
    products_by_sku = {p['sku']: p for p in products_data if p.get('sku')}
    
    # Get all Wallcano products from database
    db_products = list(db.supplier_products.find({'supplier': 'Wallcano'}))
    
    print(f"Found {len(db_products)} Wallcano products in database")
    print(f"Found {len(prices)} SKUs with price data")
    print(f"Found {len(products_by_sku)} products in JSON file")
    print("\n" + "="*80)
    
    updated = 0
    skipped = 0
    no_price = 0
    
    results = []
    
    for product in db_products:
        sku = product.get('sku')
        current_name = product.get('name', '')
        finish = product.get('finish', '')
        
        # Get cost price from prices file
        price_data = prices.get(sku)
        cost_price = None
        
        if price_data:
            # Use pallet price as cost (wholesale price)
            cost_price = price_data.get('pallet')
        elif sku in products_by_sku:
            # Try to get cost from products file
            cost_price = products_by_sku[sku].get('cost')
        
        # Generate unique product name
        new_name = generate_unique_name(current_name, finish)
        
        # Calculate list price
        list_price = calculate_list_price(cost_price) if cost_price else None
        
        result = {
            'sku': sku,
            'old_name': current_name,
            'new_name': new_name,
            'cost_price': cost_price,
            'list_price': list_price,
            'status': 'updated' if list_price else 'no_price'
        }
        results.append(result)
        
        if not cost_price:
            no_price += 1
            print(f"⚠️  SKU: {sku} - No cost price found")
            continue
        
        # Update the database
        update_data = {
            'product_name': new_name,  # Store generated name separately
            'cost_price': cost_price,
            'price': list_price,  # List price for display
            'last_processed': datetime.now(timezone.utc)
        }
        
        db.supplier_products.update_one(
            {'_id': product['_id']},
            {'$set': update_data}
        )
        
        updated += 1
        print(f"✓ SKU: {sku}")
        print(f"  Name: {current_name} → {new_name}")
        print(f"  Cost: £{cost_price:.2f} → List: £{list_price:.2f}")
        print()
    
    print("="*80)
    print(f"\nSUMMARY:")
    print(f"  Total products: {len(db_products)}")
    print(f"  Updated: {updated}")
    print(f"  No price data: {no_price}")
    
    # Save results to JSON for verification
    with open('/app/supplier_data/wallcano_processing_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to /app/supplier_data/wallcano_processing_results.json")
    
    return {
        'total': len(db_products),
        'updated': updated,
        'no_price': no_price
    }

if __name__ == '__main__':
    process_wallcano_products()

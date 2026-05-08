"""
Apply Complete Product Naming Logic to Splendour Products
==========================================================
Based on business_rules.py:
- Format: {UNIQUE_NAME} {COLOUR} {SIZE} {FINISH} {CHARACTERISTICS}
- Same series = Same unique name
- Avoid duplicates with other suppliers
- Flooring: No finish in name
"""

import requests
import re
import json
from collections import defaultdict
from datetime import datetime

PROD_API = "https://tile-station-production.up.railway.app"

# Series that conflict with other suppliers -> new names
CONFLICTING_SERIES_MAP = {
    "Alaska": "Everest",
    "Borgogna": "Amazon", 
    "Bumpy": "Olympus",
    "Burlington": "Cairo",
    "Calacatta": "Venice",
    "Carrara": "Milan",
    "Cement": "Monaco",
    "Concrete": "Paris",
    "Eternal": "Oslo",
    "Etna": "Geneva",
    "Gloss": "Zurich",
    "Hand": "Tokyo",
    "Imperial": "Sydney",
    "Invisible": "Denver",
    "Loft": "Austin",
    "Lux": "Phoenix",
    "Marshall": "Dallas",
    "Metro": "Miami",
    "Opal": "Aspen",
    "Plaster": "Malibu",
    "Porto": "Riviera",
    "Sahara": "Santorini",
    "Vintage": "Mykonos",
    "White": "Crete"
}

# Finishes from business rules
FINISHES = [
    "Matt", "Gloss", "Polished", "Polish", "Satin", "Satin Matt",
    "Lappato", "Natural", "Textured", "Anti-Slip", "Slate", 
    "Sparkle", "Silk", "Mix", "Rectified", "Honed", "R10", "R11"
]

# Colors to extract
COLORS = [
    "Super White", "Light Grey", "Dark Grey", "Light Beige", "Dark Beige",
    "Light Bone", "Honey Oak", "Dark Walnut", "Silver Grey",
    "White", "Black", "Grey", "Gray", "Beige", "Cream", "Ivory", 
    "Brown", "Taupe", "Bone", "Anthracite", "Charcoal", "Silver",
    "Gold", "Blue", "Green", "Red", "Pink", "Sand", "Natural",
    "Pearl", "Perla", "Blanco", "Gris", "Grafito", "Ceniza", 
    "Marfil", "Negro", "Crema", "Cotto", "Terracotta", "Rust",
    "Graphite", "Chocolate", "Honey", "Oak", "Walnut", "Ash",
    "Sage", "Navy", "Ocean", "Sea", "Sky", "Forest", "Orchid",
    "Marengo", "Bianco", "Grigio", "Nero", "Avorio", "Tortora"
]

# Characteristics (product types)
CHARACTERISTICS = [
    "Outdoor Porcelain Slabs", "20mm Porcelain Slabs", "Porcelain Slabs",
    "Click SPC Rigid Plank Flooring", "Click SPC Tile Flooring",
    "Wall & Floor Tiles", "Wall Tiles", "Floor Tiles",
    "Porcelain Mosaic", "Glass Mosaic", "Marble Mosaic", "Stone Mosaic",
    "Hexagon Tiles", "Chevron Tiles", "Metro Tiles", "Brick Tiles",
    "Wood Effect Tiles", "Stone Effect Tiles", "Marble Effect Tiles",
    "Concrete Effect Tiles", "Patterned Tiles", "Splitface Cladding",
    "Mosaic", "Decor Tiles", "Feature Tiles", "Border Tiles",
    "Outdoor Tiles", "Slabs", "Tiles"
]


def get_series(name):
    """Extract series name from product name"""
    if not name:
        return ""
    words = name.split()
    if not words:
        return ""
    first_word = words[0]
    two_word_prefixes = ["Old", "New", "St", "Le", "La", "K2", "My", "Day", "Night"]
    if first_word in two_word_prefixes and len(words) > 1:
        return f"{first_word} {words[1]}"
    return first_word


def get_unique_name(series):
    """Get unique name for series - rename if conflicts with other suppliers"""
    if series in CONFLICTING_SERIES_MAP:
        return CONFLICTING_SERIES_MAP[series]
    return series


def extract_color(name):
    """Extract color from product name"""
    # Sort by length (longer first) to match "Light Grey" before "Grey"
    for color in sorted(COLORS, key=len, reverse=True):
        pattern = r'\b' + re.escape(color) + r'\b'
        if re.search(pattern, name, re.I):
            return color
    return ""


def extract_size(name, size_field=None):
    """Extract and normalize size to WxH format"""
    # Try from size field first
    if size_field:
        match = re.search(r'(\d{2,4})\s*x\s*(\d{2,4})', str(size_field))
        if match:
            return f"{match.group(1)}x{match.group(2)}"
    
    # Try from name
    match = re.search(r'(\d{2,4})\s*x\s*(\d{2,4})', name)
    if match:
        return f"{match.group(1)}x{match.group(2)}"
    
    return ""


def extract_finish(name, finish_field=None):
    """Extract finish from name or field"""
    # Check field first
    if finish_field:
        finish = str(finish_field).strip()
        if finish.lower() not in ['none', 'type', 'provide', 'and', '', 'nan']:
            for f in FINISHES:
                if f.lower() == finish.lower():
                    return f
    
    # Check name
    for finish in FINISHES:
        pattern = r'\b' + re.escape(finish) + r'\b'
        if re.search(pattern, name, re.I):
            return finish
    
    return ""


def extract_characteristics(name):
    """Extract product type/characteristics"""
    name_lower = name.lower()
    
    # Check for specific patterns
    for char in CHARACTERISTICS:
        if char.lower() in name_lower:
            return char
    
    # Infer from keywords
    if "20mm" in name_lower or "slab" in name_lower:
        if "outdoor" in name_lower:
            return "Outdoor Porcelain Slabs"
        return "Porcelain Slabs"
    if "mosaic" in name_lower:
        return "Mosaic"
    if "outdoor" in name_lower:
        return "Outdoor Tiles"
    if "wood" in name_lower or "oak" in name_lower or "walnut" in name_lower:
        return "Wood Effect Tiles"
    if "marble" in name_lower:
        return "Marble Effect Tiles"
    if "stone" in name_lower:
        return "Stone Effect Tiles"
    if "concrete" in name_lower:
        return "Concrete Effect Tiles"
    if "brick" in name_lower:
        return "Brick Tiles"
    if "hexagon" in name_lower or "hex" in name_lower:
        return "Hexagon Tiles"
    if "metro" in name_lower:
        return "Metro Tiles"
    if "decor" in name_lower:
        return "Decor Tiles"
    if "wall" in name_lower and "floor" in name_lower:
        return "Wall & Floor Tiles"
    if "wall" in name_lower:
        return "Wall Tiles"
    if "floor" in name_lower:
        return "Floor Tiles"
    
    return "Tiles"


def build_new_name(unique_name, color, size, finish, characteristics, is_flooring=False):
    """Build the new product name according to format rules"""
    parts = []
    
    # Unique name (required)
    parts.append(unique_name)
    
    # Color (if not already in unique name)
    if color and color.lower() not in unique_name.lower():
        parts.append(color)
    
    # Size
    if size:
        parts.append(size)
    
    # Finish (skip for flooring)
    if finish and not is_flooring:
        parts.append(finish)
    
    # Characteristics
    if characteristics:
        parts.append(characteristics)
    
    # Join and clean
    name = " ".join(parts)
    
    # Remove duplicate consecutive words
    words = name.split()
    cleaned = []
    for word in words:
        if not cleaned or word.lower() != cleaned[-1].lower():
            cleaned.append(word)
    
    return " ".join(cleaned)


def transform_product_name(product):
    """Transform a single product name according to all rules"""
    current_name = product.get('name', '')
    
    # Extract components
    series = get_series(current_name)
    unique_name = get_unique_name(series)
    color = extract_color(current_name)
    size = extract_size(current_name, product.get('size'))
    finish = extract_finish(current_name, product.get('finish'))
    characteristics = extract_characteristics(current_name)
    
    # Check if flooring
    is_flooring = 'flooring' in current_name.lower() or 'spc' in current_name.lower()
    
    # Build new name
    new_name = build_new_name(unique_name, color, size, finish, characteristics, is_flooring)
    
    return {
        'sku': product.get('sku'),
        'old_name': current_name,
        'new_name': new_name,
        'series': series,
        'unique_name': unique_name,
        'color': color,
        'size': size,
        'finish': finish,
        'characteristics': characteristics,
        'renamed_series': series != unique_name
    }


def analyze_all_products():
    """Analyze all Splendour products and show proposed changes"""
    
    print("="*80)
    print("SPLENDOUR PRODUCT NAMING ANALYSIS")
    print("="*80)
    
    # Get all Splendour products
    all_products = []
    skip = 0
    while True:
        resp = requests.get(f"{PROD_API}/api/supplier-sync/products?supplier=Splendour&skip={skip}&limit=50", timeout=30)
        data = resp.json()
        products = data.get('products', [])
        if not products:
            break
        all_products.extend(products)
        skip += 50
        if len(all_products) >= data.get('total', 0):
            break
    
    print(f"\nTotal Splendour products: {len(all_products)}")
    
    # Transform all names
    results = []
    for p in all_products:
        result = transform_product_name(p)
        results.append(result)
    
    # Statistics
    renamed_series = [r for r in results if r['renamed_series']]
    
    print(f"\nProducts with renamed series: {len(renamed_series)}")
    print(f"Products keeping original series: {len(results) - len(renamed_series)}")
    
    # Show renamed series examples
    print(f"\n{'='*80}")
    print("RENAMED SERIES (conflicting with other suppliers)")
    print(f"{'='*80}")
    
    # Group by series
    by_series = defaultdict(list)
    for r in renamed_series:
        by_series[r['series']].append(r)
    
    for series in sorted(by_series.keys()):
        items = by_series[series]
        new_name = items[0]['unique_name']
        print(f"\n{series} → {new_name} ({len(items)} products)")
        for item in items[:2]:
            print(f"  OLD: {item['old_name'][:60]}")
            print(f"  NEW: {item['new_name'][:60]}")
    
    # Show sample transformations for non-renamed series
    print(f"\n{'='*80}")
    print("SAMPLE TRANSFORMATIONS (keeping original series names)")
    print(f"{'='*80}")
    
    non_renamed = [r for r in results if not r['renamed_series']]
    by_series_nr = defaultdict(list)
    for r in non_renamed:
        by_series_nr[r['series']].append(r)
    
    shown = 0
    for series in sorted(by_series_nr.keys()):
        if shown >= 10:
            break
        items = by_series_nr[series]
        print(f"\n{series} ({len(items)} products)")
        for item in items[:2]:
            print(f"  OLD: {item['old_name'][:60]}")
            print(f"  NEW: {item['new_name'][:60]}")
            print(f"      Color={item['color']}, Size={item['size']}, Finish={item['finish']}")
        shown += 1
    
    # Save full results to JSON
    with open('/tmp/naming_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n{'='*80}")
    print(f"Full results saved to /tmp/naming_results.json")
    print(f"{'='*80}")
    
    return results


if __name__ == "__main__":
    analyze_all_products()

"""
Apply Complete Product Naming Logic to ALL Splendour Products on PRODUCTION
============================================================================
Format: {UNIQUE_NAME} {COLOUR} {SIZE} {FINISH} {CHARACTERISTICS}

- ALL series get unique names from our list
- Avoids duplicates with other suppliers
"""

import requests
import re
import json
import time
from collections import defaultdict

PROD_API = "https://tile-station-production.up.railway.app"

# Extended unique names list (cities/places/landmarks) - 230+ names
TILE_UNIQUE_NAMES = [
    "Atlas", "Everest", "Sahara", "Amazon", "Olympus", "Aurora", "Cairo", "Venice",
    "Milan", "Roma", "Vienna", "Monaco", "Paris", "Oslo", "Geneva", "Zurich",
    "Tokyo", "Sydney", "Denver", "Austin", "Phoenix", "Dallas", "Boston", "Miami",
    "Aspen", "Malibu", "Capri", "Amalfi", "Riviera", "Santorini", "Mykonos", "Crete",
    "Cascade", "Summit", "Ridge", "Canyon", "Mesa", "Terra", "Luna", "Nova",
    "Stella", "Cosmo", "Zenith", "Apex", "Prime", "Elite", "Luxe", "Regal",
    "Crystal", "Onyx", "Pearl", "Ivory", "Obsidian", "Granite", "Quartz", "Slate",
    "Harbor", "Marina", "Cove", "Bay", "Coast", "Shore", "Cliff", "Dune",
    "Horizon", "Eclipse", "Solstice", "Equinox", "Vega", "Orion", "Polaris", "Sirius",
    "Metro", "Urban", "Civic", "Plaza", "Avenue", "Boulevard", "Strada", "Piazza",
    "Artisan", "Studio", "Gallery", "Atelier", "Loft", "Soho", "Chelsea", "Tribeca",
    "Nordic", "Alpine", "Baltic", "Celtic", "Tuscan", "Aegean", "Adriatic", "Pacific",
    "Majestic", "Imperial", "Royal", "Noble", "Grand", "Premier", "Prestige", "Legacy",
    "Essence", "Pure", "Serene", "Tranquil", "Harmony", "Balance", "Zen", "Oasis",
    "Palermo", "Florence", "Siena", "Naples", "Bologna", "Torino", "Genoa",
    "Barcelona", "Madrid", "Seville", "Valencia", "Lisbon", "Porto", "Athens", "Rhodes",
    "Kyoto", "Beijing", "Shanghai", "Mumbai", "Dubai", "Istanbul", "Prague", "Budapest",
    "Warsaw", "Moscow", "Stockholm", "Helsinki", "Copenhagen", "Amsterdam", "Brussels",
    "Edinburgh", "Dublin", "Cork", "Glasgow", "Cardiff", "Belfast", "Manchester", "Liverpool",
    "Berlin", "Munich", "Hamburg", "Frankfurt", "Cologne", "Dusseldorf", "Leipzig", "Dresden",
    "Lyon", "Marseille", "Nice", "Cannes", "Bordeaux", "Toulouse", "Nantes", "Strasbourg",
    "Verona", "Pisa", "Como", "Sorrento", "Positano", "Ravello", "Taormina", "Orvieto",
    "Cordoba", "Granada", "Malaga", "Bilbao", "Santiago", "Pamplona", "Toledo", "Segovia",
    "Sintra", "Cascais", "Braga", "Coimbra", "Faro", "Lagos", "Tavira", "Evora",
    # Additional names to cover all series
    "Luxor", "Petra", "Bali", "Fiji", "Tahiti", "Havana", "Kingston", "Nassau",
    "Bermuda", "Cancun", "Acapulco", "Cabo", "Monterey", "Sedona", "Taos", "Vail",
    "Aspen", "Telluride", "Whistler", "Banff", "Jasper", "Zermatt", "Chamonix", "Verbier",
    "Cortina", "Davos", "Gstaad", "Lucerne", "Interlaken", "Montreux", "Lausanne", "Bern",
    "Salzburg", "Innsbruck", "Bruges", "Ghent", "Antwerp", "Rotterdam", "Delft", "Haarlem"
]

# Finishes
FINISHES = ["Matt", "Gloss", "Polished", "Satin", "Lappato", "Natural", "Textured", 
            "Anti-Slip", "Sparkle", "Silk", "Mix", "Rectified", "Honed", "R10", "R11"]

# Colors (sorted by length for matching)
COLORS = sorted([
    "Super White", "Light Grey", "Dark Grey", "Light Beige", "Dark Beige", "Light Bone",
    "Honey Oak", "Dark Walnut", "Silver Grey", "White", "Black", "Grey", "Gray", 
    "Beige", "Cream", "Ivory", "Brown", "Taupe", "Bone", "Anthracite", "Charcoal", 
    "Silver", "Gold", "Blue", "Green", "Red", "Pink", "Sand", "Natural", "Pearl", 
    "Perla", "Blanco", "Gris", "Grafito", "Ceniza", "Marfil", "Negro", "Crema", 
    "Cotto", "Terracotta", "Rust", "Graphite", "Chocolate", "Honey", "Oak", "Walnut", 
    "Ash", "Sage", "Navy", "Ocean", "Sea", "Sky", "Forest", "Orchid", "Marengo", 
    "Bianco", "Grigio", "Nero", "Avorio", "Tortora", "Turquoise", "Aqua", "Mint"
], key=len, reverse=True)

# Characteristics
CHARACTERISTICS = [
    "Outdoor Porcelain Slabs", "20mm Porcelain Slabs", "Porcelain Slabs",
    "Wall & Floor Tiles", "Wall Tiles", "Floor Tiles",
    "Porcelain Mosaic", "Glass Mosaic", "Marble Mosaic", "Stone Mosaic",
    "Hexagon Tiles", "Chevron Tiles", "Metro Tiles", "Brick Tiles",
    "Wood Effect Tiles", "Stone Effect Tiles", "Marble Effect Tiles",
    "Concrete Effect Tiles", "Patterned Tiles", "Splitface Cladding",
    "Mosaic", "Decor Tiles", "Feature Tiles", "Outdoor Tiles", "Slabs", "Tiles"
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


def extract_color(name):
    """Extract color from product name"""
    for color in COLORS:
        pattern = r'\b' + re.escape(color) + r'\b'
        if re.search(pattern, name, re.I):
            return color
    return ""


def extract_size(name, size_field=None):
    """Extract and normalize size"""
    text = str(size_field) if size_field else name
    match = re.search(r'(\d{2,4})\s*x\s*(\d{2,4})', text)
    if match:
        return f"{match.group(1)}x{match.group(2)}"
    # Try from name if not in field
    if size_field:
        match = re.search(r'(\d{2,4})\s*x\s*(\d{2,4})', name)
        if match:
            return f"{match.group(1)}x{match.group(2)}"
    return ""


def extract_finish(name, finish_field=None):
    """Extract finish"""
    if finish_field:
        finish = str(finish_field).strip()
        if finish.lower() not in ['none', 'type', 'provide', 'and', '', 'nan']:
            for f in FINISHES:
                if f.lower() == finish.lower():
                    return f
    for finish in FINISHES:
        pattern = r'\b' + re.escape(finish) + r'\b'
        if re.search(pattern, name, re.I):
            return finish
    return "Matt"  # Default


def extract_characteristics(name):
    """Extract product type"""
    name_lower = name.lower()
    
    if "20mm" in name_lower or ("slab" in name_lower and "outdoor" in name_lower):
        return "Outdoor Porcelain Slabs"
    if "slab" in name_lower:
        return "Porcelain Slabs"
    if "mosaic" in name_lower:
        if "glass" in name_lower:
            return "Glass Mosaic"
        if "marble" in name_lower:
            return "Marble Mosaic"
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
    """Build new product name"""
    parts = [unique_name]
    
    if color and color.lower() not in unique_name.lower():
        parts.append(color)
    
    if size:
        parts.append(size)
    
    if finish and not is_flooring:
        parts.append(finish)
    
    if characteristics:
        parts.append(characteristics)
    
    # Remove duplicate consecutive words
    name = " ".join(parts)
    words = name.split()
    cleaned = []
    for word in words:
        if not cleaned or word.lower() != cleaned[-1].lower():
            cleaned.append(word)
    
    return " ".join(cleaned)


def apply_naming_to_production():
    """Apply naming logic to all Splendour products on production"""
    
    print("="*80)
    print("APPLYING NAMING LOGIC TO SPLENDOUR PRODUCTS ON PRODUCTION")
    print("="*80)
    
    # Step 1: Get all products to find used names
    print("\nStep 1: Getting all products from production...")
    all_products = []
    skip = 0
    while True:
        resp = requests.get(f"{PROD_API}/api/supplier-sync/products?skip={skip}&limit=100", timeout=30)
        data = resp.json()
        products = data.get('products', [])
        if not products:
            break
        all_products.extend(products)
        skip += 100
        if len(all_products) >= data.get('total', 0):
            break
    
    print(f"Total products: {len(all_products)}")
    
    # Step 2: Find names used by other suppliers
    print("\nStep 2: Finding names used by other suppliers...")
    used_by_others = set()
    for p in all_products:
        supplier = p.get('supplier', '')
        if supplier.lower() == 'splendour':
            continue
        name = p.get('name', '')
        if name:
            first_word = name.split()[0] if name.split() else ''
            if first_word and len(first_word) > 2:
                used_by_others.add(first_word.lower())
    
    print(f"Names used by others: {len(used_by_others)}")
    
    # Step 3: Get available names
    available_names = [n for n in TILE_UNIQUE_NAMES if n.lower() not in used_by_others]
    print(f"Available names: {len(available_names)}")
    
    # Step 4: Get Splendour products and series
    splendour_products = [p for p in all_products if p.get('supplier', '').lower() == 'splendour']
    print(f"\nSplendour products: {len(splendour_products)}")
    
    splendour_series = set()
    for p in splendour_products:
        series = get_series(p.get('name', ''))
        if series and len(series) > 2 and not re.match(r'^[\d.]+', series):
            splendour_series.add(series)
    
    print(f"Splendour series: {len(splendour_series)}")
    
    # Step 5: Create series -> unique name mapping
    print("\nStep 3: Creating series to unique name mapping...")
    series_to_unique = {}
    name_idx = 0
    
    for series in sorted(splendour_series):
        if name_idx < len(available_names):
            series_to_unique[series] = available_names[name_idx]
            name_idx += 1
        else:
            # Fallback - use series name if we run out
            series_to_unique[series] = series
    
    # Step 6: Transform all product names
    print("\nStep 4: Transforming product names...")
    transformations = []
    
    for p in splendour_products:
        sku = p.get('sku')
        old_name = p.get('name', '')
        
        series = get_series(old_name)
        unique_name = series_to_unique.get(series, series)
        color = extract_color(old_name)
        size = extract_size(old_name, p.get('size'))
        finish = extract_finish(old_name, p.get('finish'))
        characteristics = extract_characteristics(old_name)
        is_flooring = 'flooring' in old_name.lower() or 'spc' in old_name.lower()
        
        new_name = build_new_name(unique_name, color, size, finish, characteristics, is_flooring)
        
        transformations.append({
            'sku': sku,
            'old_name': old_name,
            'new_name': new_name,
            'series': series,
            'unique_name': unique_name
        })
    
    # Step 7: Apply changes to production
    print("\nStep 5: Applying changes to production database...")
    
    success = 0
    failed = 0
    
    for i, t in enumerate(transformations):
        if i % 50 == 0:
            print(f"  Processing {i}/{len(transformations)}...")
        
        try:
            # Update the product name via API
            resp = requests.patch(
                f"{PROD_API}/api/supplier-sync/products/{t['sku']}/update-name",
                json={"name": t['new_name']},
                timeout=10
            )
            
            if resp.status_code == 200:
                success += 1
            else:
                # Try alternative endpoint
                resp2 = requests.put(
                    f"{PROD_API}/api/supplier-sync/product/{t['sku']}",
                    json={"name": t['new_name']},
                    timeout=10
                )
                if resp2.status_code == 200:
                    success += 1
                else:
                    failed += 1
                    
        except Exception as e:
            failed += 1
        
        # Small delay to not overwhelm the server
        if i % 10 == 0:
            time.sleep(0.1)
    
    # Save results
    with open('/tmp/naming_transformations.json', 'w') as f:
        json.dump(transformations, f, indent=2)
    
    print(f"\n{'='*80}")
    print("RESULTS")
    print(f"{'='*80}")
    print(f"Total products: {len(transformations)}")
    print(f"Success: {success}")
    print(f"Failed: {failed}")
    print(f"\nTransformations saved to /tmp/naming_transformations.json")
    
    # Show sample transformations
    print(f"\n{'='*80}")
    print("SAMPLE TRANSFORMATIONS")
    print(f"{'='*80}")
    
    for t in transformations[:20]:
        print(f"\nSKU: {t['sku']}")
        print(f"  Series: {t['series']} → {t['unique_name']}")
        print(f"  OLD: {t['old_name'][:60]}")
        print(f"  NEW: {t['new_name'][:60]}")
    
    return transformations, success, failed


if __name__ == "__main__":
    transformations, success, failed = apply_naming_to_production()

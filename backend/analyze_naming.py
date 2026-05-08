"""
Apply Product Naming Logic to Splendour Products on PRODUCTION
==============================================================
Format: {series_name} {colour} {size} {finish} {characteristics}

Rules from business_rules.py:
1. Same series = Same unique name
2. Size MUST come BEFORE finish
3. Remove duplicate words
4. Flooring: NO finish in name
5. Extract characteristics (Wall Tile, Floor Tile, Mosaic, etc.)
"""

import re
import requests
import json
from collections import defaultdict

PROD_API = "https://tile-station-production.up.railway.app"

# Naming rules from business_rules.py
FINISHES = [
    "Matt", "Gloss", "Polished", "Polish", "Satin", "Satin Matt",
    "Lappato", "Natural", "Textured", "Anti-Slip", "Slate", "Sparkle", 
    "Silk", "Mix", "Rectified", "R10", "R11", "Honed", "Outdoor"
]

CHARACTERISTICS = [
    "Click SPC Rigid Plank Flooring", "Click SPC Tile Flooring", 
    "Click SPC Herringbone Flooring", "Outdoor Porcelain Slabs",
    "Wall & Floor Tile", "Wall Tile", "Floor Tile", 
    "Porcelain Mosaic", "Marble Mosaic", "Glass Mosaic", 
    "Stone Mosaic", "Wall Mosaic", "Splitface Cladding", "Mosaic", 
    "Outdoor Paving Slabs", "Outdoor Slabs", "Porcelain Slabs",
    "Wood Effect Tiles", "Stone Effect Tiles", "Marble Effect Tiles",
    "Concrete Effect Tiles", "Patterned Tiles", "Metro Tiles",
    "Brick Effect Tiles", "Hexagon Tiles", "Chevron Tiles",
    "20mm Slabs", "Slabs", "Tiles", "Tile"
]

# Colors to extract - ordered by specificity (longer first)
COLORS = [
    "Light Grey", "Dark Grey", "Light Beige", "Dark Beige", "Light Bone",
    "Honey Oak", "Dark Walnut", "Silver Grey", "Super Bianco",
    "White", "Black", "Grey", "Gray", "Beige", "Cream", "Ivory", 
    "Brown", "Taupe", "Bone", "Anthracite", "Charcoal", "Silver",
    "Gold", "Blue", "Green", "Red", "Pink", "Sand", "Natural",
    "Pearl", "Perla", "Blanco", "Gris", "Grafito", "Ceniza", 
    "Marfil", "Negro", "Crema", "Cotto", "Terracotta", "Rust",
    "Sage", "Navy", "Ocean", "Sea", "Sky", "Orchid", "Forest"
]

# Words to remove from names
REMOVE_WORDS = ["Effect", "Type", "provide", "and", "The"]


def extract_series_name(name):
    """Extract the series/range name (usually first 1-2 words)"""
    if not name:
        return ""
    
    # Remove size patterns first
    clean = re.sub(r'\d+x\d+x?\d*\s*(mm)?', '', name, flags=re.I)
    # Remove thickness patterns
    clean = re.sub(r'\d+mm\b', '', clean, flags=re.I)
    
    # Split and get first word(s)
    words = [w for w in clean.split() if w.strip()]
    if not words:
        return ""
    
    # First word is typically the series name
    series = words[0]
    
    # Some series have two words (e.g., "Old Manor", "New Pietra", "My Space")
    two_word_prefixes = ["Old", "New", "St", "Le", "La", "K2", "My", "Day", "Night"]
    if series in two_word_prefixes and len(words) > 1:
        series = f"{words[0]} {words[1]}"
    
    return series


def extract_color(name, color_field=None):
    """Extract color from name or use color field"""
    if color_field and str(color_field).strip() and str(color_field).strip().lower() != 'none':
        return str(color_field).strip().title()
    
    name_check = name
    
    # Check for colors in name (longer matches first)
    for color in sorted(COLORS, key=len, reverse=True):
        pattern = r'\b' + re.escape(color) + r'\b'
        if re.search(pattern, name_check, re.I):
            return color
    
    return ""


def extract_size(name, size_field=None):
    """Extract and normalize size"""
    size_str = ""
    
    # Try size field first
    if size_field:
        size_str = str(size_field).strip()
    
    # Normalize: extract WxH format
    # Look for patterns like 600x600, 1200x600x20mm, etc.
    match = re.search(r'(\d{2,4})\s*x\s*(\d{2,4})(?:\s*x?\s*\d+)?', size_str or name)
    if match:
        w, h = int(match.group(1)), int(match.group(2))
        return f"{w}x{h}"
    
    return ""


def extract_finish(name, finish_field=None):
    """Extract finish from name or use finish field"""
    # Clean up finish field
    if finish_field:
        finish = str(finish_field).strip()
        if finish.lower() not in ['none', 'type', 'provide', 'and', '', 'nan']:
            # Capitalize properly
            for f in FINISHES:
                if f.lower() == finish.lower():
                    return f
            if finish.title() in FINISHES:
                return finish.title()
    
    # Try extracting from name
    for finish in FINISHES:
        pattern = r'\b' + re.escape(finish) + r'\b'
        if re.search(pattern, name, re.I):
            return finish
    
    return ""


def extract_characteristics(name):
    """Extract product type characteristics"""
    name_lower = name.lower()
    
    # Check for specific patterns first
    for char in CHARACTERISTICS:
        if char.lower() in name_lower:
            return char
    
    # Default based on keywords
    if "mosaic" in name_lower:
        return "Mosaic"
    if "20mm" in name_lower or "outdoor" in name_lower or "slab" in name_lower:
        return "Outdoor Porcelain Slabs"
    if "wood" in name_lower or "oak" in name_lower or "walnut" in name_lower:
        return "Wood Effect Tiles"
    if "marble" in name_lower:
        return "Marble Effect Tiles"
    if "stone" in name_lower:
        return "Stone Effect Tiles"
    if "concrete" in name_lower:
        return "Concrete Effect Tiles"
    if "brick" in name_lower:
        return "Brick Effect Tiles"
    if "hexagon" in name_lower or "hex" in name_lower:
        return "Hexagon Tiles"
    if "metro" in name_lower:
        return "Metro Tiles"
    if "pattern" in name_lower:
        return "Patterned Tiles"
    if "chevron" in name_lower:
        return "Chevron Tiles"
    
    return "Tiles"


def build_product_name(series, color, size, finish, characteristics, is_flooring=False):
    """Build the final product name according to format rules"""
    parts = []
    
    # Series name (required)
    if series:
        parts.append(series)
    
    # Color
    if color:
        # Avoid duplicating if color is in series name
        if color.lower() not in series.lower():
            parts.append(color)
    
    # Size (must come before finish)
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
    
    # Remove words to exclude
    for word in REMOVE_WORDS:
        name = re.sub(r'\b' + re.escape(word) + r'\b', '', name, flags=re.I)
    
    # Remove duplicate consecutive words (case-insensitive)
    words = name.split()
    cleaned = []
    for word in words:
        if not cleaned or word.lower() != cleaned[-1].lower():
            cleaned.append(word)
    
    # Clean up extra spaces
    name = " ".join(cleaned).strip()
    name = re.sub(r'\s+', ' ', name)
    
    return name


def get_all_splendour_products():
    """Get all Splendour products from production"""
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
    return all_products


def analyze_naming():
    """Analyze and show proposed naming changes"""
    
    print("="*80)
    print("ANALYZING SPLENDOUR PRODUCT NAMES")
    print("="*80)
    
    products = get_all_splendour_products()
    print(f"\nTotal Splendour products: {len(products)}")
    
    # Track series for consistency
    series_map = defaultdict(list)
    
    results = []
    
    for p in products:
        sku = p.get('sku')
        current_name = p.get('name', '')
        
        # Extract components
        series = extract_series_name(current_name)
        color = extract_color(current_name, p.get('color'))
        size = extract_size(current_name, p.get('size'))
        finish = extract_finish(current_name, p.get('finish'))
        characteristics = extract_characteristics(current_name)
        
        # Check if flooring
        is_flooring = 'flooring' in current_name.lower() or 'spc' in current_name.lower()
        
        # Build new name
        new_name = build_product_name(series, color, size, finish, characteristics, is_flooring)
        
        series_map[series].append(sku)
        
        results.append({
            'sku': sku,
            'old_name': current_name,
            'new_name': new_name,
            'changed': new_name != current_name,
            'series': series,
            'color': color,
            'size': size,
            'finish': finish,
            'characteristics': characteristics
        })
    
    # Count changes
    changed = [r for r in results if r['changed']]
    unchanged = [r for r in results if not r['changed']]
    
    print(f"\nProposed changes: {len(changed)}")
    print(f"Unchanged: {len(unchanged)}")
    
    # Show sample transformations grouped by series
    print(f"\n{'='*80}")
    print("SAMPLE TRANSFORMATIONS BY SERIES")
    print(f"{'='*80}")
    
    # Get unique series with changes
    series_with_changes = defaultdict(list)
    for r in changed:
        series_with_changes[r['series']].append(r)
    
    # Show first 15 series
    shown = 0
    for series in sorted(series_with_changes.keys()):
        if shown >= 15:
            break
        items = series_with_changes[series][:3]
        print(f"\n[{series}] ({len(series_with_changes[series])} products)")
        for item in items:
            print(f"  OLD: {item['old_name'][:60]}")
            print(f"  NEW: {item['new_name'][:60]}")
            print(f"  Components: color={item['color']}, size={item['size']}, finish={item['finish']}")
            print()
        shown += 1
    
    return results


if __name__ == "__main__":
    results = analyze_naming()
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)
    print("\nThis was an analysis only. No changes were made.")
    print("Review the proposed changes above.")

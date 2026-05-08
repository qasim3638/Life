"""
Apply Product Naming Logic to Splendour Products
=================================================
Format: {series_name} {colour} {size} {finish} {characteristics}

Rules from business_rules.py:
1. Same series = Same unique name
2. Size MUST come BEFORE finish
3. Remove duplicate words
4. Flooring: NO finish in name
5. Extract characteristics (Wall Tile, Floor Tile, Mosaic, etc.)
"""

import re
import os
import sys
from pymongo import MongoClient
from datetime import datetime, timezone
from collections import defaultdict

# Connect to MongoDB
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'tile_station')

client = MongoClient(MONGO_URL)
db = client[DB_NAME]

# Naming rules from business_rules.py
FINISHES = [
    "Matt", "Gloss", "Polished", "Polish", "Satin", "Satin Matt",
    "Lappato", "Natural", "Textured", "Anti-Slip", "Slate", "Sparkle", 
    "Silk", "Mix", "Rectified", "R10", "R11", "Honed", "Outdoor"
]

CHARACTERISTICS = [
    "Click SPC Rigid Plank Flooring", "Click SPC Tile Flooring", 
    "Click SPC Herringbone Flooring", "Wall & Floor Tile", "Wall Tile", 
    "Floor Tile", "Porcelain Mosaic", "Marble Mosaic", "Glass Mosaic", 
    "Stone Mosaic", "Wall Mosaic", "Splitface Cladding", "Mosaic", 
    "Outdoor Paving Slabs", "Outdoor Slabs", "Porcelain Slabs", "Slabs",
    "Wood Effect Tile", "Stone Effect Tile", "Marble Effect Tile",
    "Concrete Effect Tile", "Tiles", "Tile"
]

# Colors to extract
COLORS = [
    "White", "Black", "Grey", "Gray", "Beige", "Cream", "Ivory", 
    "Brown", "Taupe", "Bone", "Anthracite", "Charcoal", "Silver",
    "Gold", "Blue", "Green", "Red", "Pink", "Sand", "Natural",
    "Light Grey", "Dark Grey", "Light Beige", "Dark Beige",
    "Honey Oak", "Dark Walnut", "Pearl", "Perla", "Blanco", "Gris",
    "Grafito", "Ceniza", "Marfil", "Negro", "Crema"
]

# Words to remove
REMOVE_WORDS = ["The", "Effect", "Type", "provide", "and"]


def extract_series_name(name):
    """Extract the series/range name (usually first 1-2 words)"""
    if not name:
        return ""
    
    # Remove size patterns first
    clean = re.sub(r'\d+x\d+x?\d*\s*(mm)?', '', name, flags=re.I)
    
    # Split and get first word(s)
    words = clean.split()
    if not words:
        return ""
    
    # First word is typically the series name
    series = words[0]
    
    # Some series have two words (e.g., "Old Manor", "New Pietra")
    two_word_series = ["Old", "New", "St", "Le", "La", "K2"]
    if series in two_word_series and len(words) > 1:
        series = f"{words[0]} {words[1]}"
    
    return series


def extract_color(name, color_field=None):
    """Extract color from name or use color field"""
    if color_field and color_field.strip():
        return color_field.strip()
    
    name_lower = name.lower()
    
    # Check for colors in name
    for color in sorted(COLORS, key=len, reverse=True):  # Longer matches first
        if color.lower() in name_lower:
            return color
    
    return ""


def extract_size(name, size_field=None):
    """Extract and normalize size"""
    # Try size field first
    if size_field:
        size = str(size_field).strip()
        # Normalize format: remove 'mm', format as WxH
        size = re.sub(r'mm', '', size, flags=re.I).strip()
        # Extract dimensions
        match = re.search(r'(\d+)\s*x\s*(\d+)', size)
        if match:
            return f"{match.group(1)}x{match.group(2)}"
    
    # Try extracting from name
    match = re.search(r'(\d{2,4})\s*x\s*(\d{2,4})', name)
    if match:
        return f"{match.group(1)}x{match.group(2)}"
    
    return ""


def extract_finish(name, finish_field=None):
    """Extract finish from name or use finish field"""
    # Clean up finish field
    if finish_field:
        finish = str(finish_field).strip()
        if finish.lower() not in ['none', 'type', 'provide', 'and', '']:
            # Capitalize properly
            for f in FINISHES:
                if f.lower() == finish.lower():
                    return f
            return finish.title()
    
    # Try extracting from name
    name_lower = name.lower()
    for finish in FINISHES:
        if finish.lower() in name_lower:
            return finish
    
    return ""


def extract_characteristics(name):
    """Extract product type characteristics"""
    name_lower = name.lower()
    
    for char in CHARACTERISTICS:
        if char.lower() in name_lower:
            return char
    
    # Default based on keywords
    if "mosaic" in name_lower:
        return "Mosaic"
    if "slab" in name_lower:
        return "Slabs"
    if "outdoor" in name_lower or "20mm" in name_lower:
        return "Outdoor Porcelain Slabs"
    if "wood" in name_lower:
        return "Wood Effect Tile"
    if "marble" in name_lower:
        return "Marble Effect Tile"
    if "stone" in name_lower:
        return "Stone Effect Tile"
    if "concrete" in name_lower:
        return "Concrete Effect Tile"
    
    return "Tile"


def build_product_name(series, color, size, finish, characteristics, is_flooring=False):
    """Build the final product name according to format rules"""
    parts = []
    
    # Series name (required)
    if series:
        parts.append(series)
    
    # Color
    if color:
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
    
    # Remove duplicate consecutive words
    words = name.split()
    cleaned = []
    for word in words:
        if not cleaned or word.lower() != cleaned[-1].lower():
            cleaned.append(word)
    
    return " ".join(cleaned)


def apply_naming_to_products(dry_run=True):
    """Apply naming logic to all Splendour products"""
    
    print("="*80)
    print(f"APPLYING NAMING LOGIC TO SPLENDOUR PRODUCTS {'(DRY RUN)' if dry_run else '(LIVE)'}")
    print("="*80)
    
    # Get all Splendour products from supplier_products
    products = list(db.supplier_products.find({"supplier": "Splendour"}))
    print(f"\nTotal Splendour products: {len(products)}")
    
    # Track series -> first product mapping for consistency
    series_products = defaultdict(list)
    
    updated = 0
    unchanged = 0
    errors = 0
    
    results = []
    
    for p in products:
        sku = p.get('sku')
        current_name = p.get('name', '')
        
        try:
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
            
            # Track for series consistency
            series_products[series].append({
                'sku': sku,
                'old_name': current_name,
                'new_name': new_name
            })
            
            if new_name != current_name:
                results.append({
                    'sku': sku,
                    'old_name': current_name,
                    'new_name': new_name,
                    'components': {
                        'series': series,
                        'color': color,
                        'size': size,
                        'finish': finish,
                        'characteristics': characteristics
                    }
                })
                
                if not dry_run:
                    # Update supplier_products
                    db.supplier_products.update_one(
                        {"_id": p["_id"]},
                        {"$set": {"name": new_name, "naming_updated_at": datetime.now(timezone.utc)}}
                    )
                    
                    # Also update products collection if linked
                    if p.get('products_db_id'):
                        db.products.update_one(
                            {"id": p['products_db_id']},
                            {"$set": {"name": new_name}}
                        )
                
                updated += 1
            else:
                unchanged += 1
                
        except Exception as e:
            print(f"Error processing {sku}: {e}")
            errors += 1
    
    # Print summary
    print(f"\n{'='*80}")
    print("RESULTS")
    print(f"{'='*80}")
    print(f"Updated: {updated}")
    print(f"Unchanged: {unchanged}")
    print(f"Errors: {errors}")
    
    # Show sample transformations
    print(f"\n{'='*80}")
    print("SAMPLE TRANSFORMATIONS (first 20)")
    print(f"{'='*80}")
    
    for r in results[:20]:
        print(f"\nSKU: {r['sku']}")
        print(f"  OLD: {r['old_name']}")
        print(f"  NEW: {r['new_name']}")
        print(f"  Components: {r['components']}")
    
    return results


if __name__ == "__main__":
    dry_run = "--live" not in sys.argv
    results = apply_naming_to_products(dry_run=dry_run)
    
    if dry_run:
        print("\n" + "="*80)
        print("This was a DRY RUN. No changes were made.")
        print("Run with --live to apply changes.")
        print("="*80)

#!/usr/bin/env python3
"""
Generate unique product names for Tile Station e-commerce.
Creates SEO-friendly, customer-facing names while preserving supplier names for internal use.

Strategy:
1. Parse product attributes (size, finish, color, material)
2. Generate unique collection names (Tile Station branded)
3. Create display_name, slug, and keep original supplier_name
"""
import re
import random
from datetime import datetime, timezone
from pymongo import MongoClient

# Tile Station unique collection prefixes - these make products unique and unGoogleable
COLLECTION_PREFIXES = [
    "Essence", "Signature", "Heritage", "Modern", "Classic", "Luxe", "Prime",
    "Bella", "Vista", "Terra", "Stone", "Urban", "Metro", "Nordic", "Coastal",
    "Milano", "Roma", "Venetian", "Tuscan", "Aegean", "Alpine", "Aurora"
]

# Color synonyms to make names unique
COLOR_SYNONYMS = {
    'white': ['Pearl', 'Ivory', 'Snow', 'Frost', 'Arctic', 'Alabaster'],
    'grey': ['Slate', 'Ash', 'Storm', 'Dove', 'Silver', 'Graphite'],
    'gray': ['Slate', 'Ash', 'Storm', 'Dove', 'Silver', 'Graphite'],
    'black': ['Onyx', 'Midnight', 'Obsidian', 'Charcoal', 'Jet', 'Ebony'],
    'beige': ['Sand', 'Dune', 'Sahara', 'Camel', 'Wheat', 'Taupe'],
    'cream': ['Vanilla', 'Linen', 'Champagne', 'Bisque', 'Ecru'],
    'brown': ['Walnut', 'Chestnut', 'Cocoa', 'Mocha', 'Espresso', 'Umber'],
    'blue': ['Azure', 'Cobalt', 'Ocean', 'Marine', 'Sapphire', 'Navy'],
    'green': ['Sage', 'Olive', 'Emerald', 'Forest', 'Jade', 'Moss'],
    'gold': ['Amber', 'Honey', 'Gilt', 'Aureate', 'Bronze'],
    'pink': ['Blush', 'Rose', 'Coral', 'Salmon', 'Peach'],
    'red': ['Ruby', 'Crimson', 'Burgundy', 'Scarlet', 'Garnet'],
}

# Finish synonyms
FINISH_SYNONYMS = {
    'polished': ['Polished', 'High-Gloss', 'Mirror-Finish'],
    'matt': ['Matt', 'Matte', 'Soft-Touch'],
    'gloss': ['Gloss', 'Lustrous', 'Shine'],
    'satin': ['Satin', 'Silk-Touch', 'Semi-Gloss'],
    'textured': ['Textured', 'Grip', 'Anti-Slip'],
    'carving': ['Carved', 'Embossed', '3D-Relief'],
    'honed': ['Honed', 'Brushed', 'Natural-Finish'],
}

def extract_attributes(name, supplier=None):
    """Extract color, finish, size from product name"""
    name_lower = name.lower()
    
    # Extract size (e.g., 60x120, 30x60)
    size_match = re.search(r'(\d+)\s*[xX×]\s*(\d+)', name)
    size = f"{size_match.group(1)}x{size_match.group(2)}" if size_match else None
    
    # Extract finish
    finish = None
    for f in ['polished', 'matt', 'matte', 'gloss', 'glossy', 'satin', 'textured', 'carving', 'carved', 'honed']:
        if f in name_lower:
            finish = f.replace('matte', 'matt').replace('glossy', 'gloss').replace('carved', 'carving')
            break
    
    # Extract color
    color = None
    for c in ['white', 'grey', 'gray', 'black', 'beige', 'cream', 'brown', 'blue', 'green', 'gold', 'pink', 'red', 'natural', 'mint', 'aqua', 'sky']:
        if c in name_lower:
            color = c.replace('gray', 'grey')
            break
    
    # Extract material hints
    material = 'Porcelain'  # Default
    if any(x in name_lower for x in ['marble', 'marmo']):
        material = 'Marble-Effect'
    elif any(x in name_lower for x in ['wood', 'oak', 'walnut']):
        material = 'Wood-Effect'
    elif any(x in name_lower for x in ['stone', 'slate', 'granite']):
        material = 'Stone-Effect'
    elif any(x in name_lower for x in ['cement', 'concrete']):
        material = 'Cement-Effect'
    elif 'ceramic' in name_lower:
        material = 'Ceramic'
    
    return {
        'size': size,
        'finish': finish,
        'color': color,
        'material': material,
        'original_name': name
    }

def generate_unique_name(attrs, index, supplier):
    """Generate a unique, branded product name"""
    
    # Pick a collection prefix based on supplier and index
    prefix_index = hash(f"{supplier}{index}") % len(COLLECTION_PREFIXES)
    collection = COLLECTION_PREFIXES[prefix_index]
    
    # Get unique color name
    color_name = ""
    if attrs['color']:
        color_key = attrs['color'].lower()
        if color_key in COLOR_SYNONYMS:
            # Pick consistently based on hash
            synonyms = COLOR_SYNONYMS[color_key]
            color_name = synonyms[hash(f"{supplier}{attrs['original_name']}") % len(synonyms)]
        else:
            color_name = attrs['color'].title()
    
    # Get unique finish name
    finish_name = ""
    if attrs['finish']:
        finish_key = attrs['finish'].lower()
        if finish_key in FINISH_SYNONYMS:
            finish_name = FINISH_SYNONYMS[finish_key][0]  # Use primary synonym
        else:
            finish_name = attrs['finish'].title()
    
    # Build the name
    parts = [collection]
    
    if color_name:
        parts.append(color_name)
    
    if attrs['material'] and attrs['material'] != 'Porcelain':
        parts.append(attrs['material'])
    
    if finish_name:
        parts.append(finish_name)
    
    parts.append('Tile')
    
    if attrs['size']:
        parts.append(f"- {attrs['size']}cm")
    
    display_name = ' '.join(parts)
    
    # Generate URL slug
    slug_parts = [p.lower().replace(' ', '-').replace('/', '-') for p in parts if p != '-']
    slug = '-'.join(slug_parts)
    slug = re.sub(r'[^a-z0-9-]', '', slug)
    slug = re.sub(r'-+', '-', slug).strip('-')
    
    # Add unique suffix to ensure uniqueness
    unique_suffix = f"-ts{abs(hash(attrs['original_name'])) % 10000:04d}"
    slug = slug + unique_suffix
    
    return display_name, slug

def update_tile_products():
    """Update all tile products with unique names"""
    
    # Connect to local database (where supplier_products are)
    client = MongoClient('mongodb://localhost:27017')
    db = client['tile_station']
    
    print("=" * 70)
    print("GENERATING UNIQUE PRODUCT NAMES FOR TILE STATION")
    print("=" * 70)
    
    # Process each supplier
    suppliers = db.supplier_products.distinct('supplier_name')
    
    total_updated = 0
    
    for supplier in suppliers:
        products = list(db.supplier_products.find({'supplier_name': supplier}))
        print(f"\n{supplier}: {len(products)} products")
        
        for i, product in enumerate(products):
            original_name = product.get('name', '')
            supplier_code = product.get('supplier_code', '')
            
            # Extract attributes
            attrs = extract_attributes(original_name, supplier)
            
            # Generate unique name
            display_name, slug = generate_unique_name(attrs, i, supplier)
            
            # Update the product
            db.supplier_products.update_one(
                {'_id': product['_id']},
                {'$set': {
                    'display_name': display_name,
                    'slug': slug,
                    'original_supplier_name': original_name,  # Keep original for internal use
                    'attributes': attrs,
                    'name_updated_at': datetime.now(timezone.utc)
                }}
            )
            
            total_updated += 1
            
            # Show samples
            if i < 3:
                print(f"  Original: {original_name[:50]}")
                print(f"  → Display: {display_name}")
                print(f"  → Slug: {slug}")
                print()
    
    print("=" * 70)
    print(f"TOTAL UPDATED: {total_updated} products")
    print("=" * 70)
    
    # Verify
    print("\n=== VERIFICATION ===")
    sample = db.supplier_products.find_one({'display_name': {'$exists': True}})
    if sample:
        print(f"Sample product:")
        print(f"  Supplier Code: {sample.get('supplier_code')}")
        print(f"  Original Name: {sample.get('original_supplier_name')}")
        print(f"  Display Name: {sample.get('display_name')}")
        print(f"  Slug: {sample.get('slug')}")
    
    return total_updated

if __name__ == '__main__':
    update_tile_products()

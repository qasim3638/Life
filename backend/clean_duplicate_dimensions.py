"""
Script to clean up duplicate size/dimension mentions in product names.
Keeps only the bracketed version when the same dimension appears multiple times.

Example: "Straight Edge Chrome Polished Aluminium Tile Trim 10mm 10mm (10mm)"
Becomes: "Straight Edge Chrome Polished Aluminium Tile Trim (10mm)"
"""
import asyncio
import re
import os
from motor.motor_asyncio import AsyncIOMotorClient

# Pattern to match dimensions like 10mm, 2.5m, 600x600, etc.
DIMENSION_PATTERN = r'\b(\d+(?:\.\d+)?(?:mm|cm|m|x\d+)?)\b'


def clean_product_name(name: str) -> str:
    """
    Clean duplicate dimensions from product name.
    Keeps only the bracketed version if present.
    """
    if not name:
        return name
    
    # Find all bracketed dimensions like (10mm), (2.5m), (600x600)
    bracketed_pattern = r'\((\d+(?:\.\d+)?(?:mm|cm|m|x\d+(?:mm|cm|m)?)?)\)'
    bracketed_matches = re.findall(bracketed_pattern, name, re.IGNORECASE)
    
    if not bracketed_matches:
        return name
    
    # For each bracketed dimension, remove unbracketed duplicates
    cleaned_name = name
    for dim in bracketed_matches:
        # Create pattern to match the dimension NOT in brackets
        # Match the dimension with word boundaries, but not when preceded by ( or followed by )
        unbracketed_pattern = rf'(?<!\()(?<!\()\b{re.escape(dim)}\b(?!\))'
        
        # Remove all unbracketed occurrences
        cleaned_name = re.sub(unbracketed_pattern, '', cleaned_name, flags=re.IGNORECASE)
    
    # Clean up multiple spaces
    cleaned_name = re.sub(r'\s+', ' ', cleaned_name).strip()
    
    return cleaned_name


def clean_product_name_v2(name: str) -> str:
    """
    Alternative approach: Find any dimension that appears both bracketed and unbracketed,
    and remove the unbracketed versions.
    """
    if not name:
        return name
    
    # Find all bracketed content like (10mm), (2.5m), (600x600mm)
    bracketed_pattern = r'\(([^)]+)\)'
    bracketed_matches = re.findall(bracketed_pattern, name)
    
    if not bracketed_matches:
        return name
    
    cleaned_name = name
    
    for bracketed_content in bracketed_matches:
        # Extract dimensions/sizes from bracketed content
        # Match patterns like: 10mm, 2.5m, 600x600, 10x10mm, etc.
        dim_pattern = r'(\d+(?:\.\d+)?(?:mm|cm|m)?(?:\s*x\s*\d+(?:\.\d+)?(?:mm|cm|m)?)?)'
        dims_in_bracket = re.findall(dim_pattern, bracketed_content, re.IGNORECASE)
        
        for dim in dims_in_bracket:
            dim_clean = dim.strip()
            if not dim_clean:
                continue
            
            # Remove unbracketed occurrences of this dimension
            # Look for the dimension NOT inside parentheses
            # We need to be careful not to remove the bracketed version
            
            # First, temporarily replace the bracketed version
            bracketed_full = f"({bracketed_content})"
            placeholder = "###BRACKET_PLACEHOLDER###"
            temp_name = cleaned_name.replace(bracketed_full, placeholder)
            
            # Now remove unbracketed occurrences
            unbracketed_pattern = rf'\b{re.escape(dim_clean)}\b'
            temp_name = re.sub(unbracketed_pattern, '', temp_name, flags=re.IGNORECASE)
            
            # Restore the bracketed version
            cleaned_name = temp_name.replace(placeholder, bracketed_full)
    
    # Clean up multiple spaces
    cleaned_name = re.sub(r'\s+', ' ', cleaned_name).strip()
    
    return cleaned_name


async def preview_changes(db, limit=20):
    """Preview what changes would be made without applying them."""
    products = await db.products.find({}).to_list(10000)
    
    changes = []
    for product in products:
        name = product.get('name', '')
        cleaned = clean_product_name_v2(name)
        
        if name != cleaned:
            changes.append({
                'id': product.get('id'),
                'sku': product.get('sku'),
                'original': name,
                'cleaned': cleaned
            })
    
    return changes


async def apply_changes(db, dry_run=True):
    """Apply the cleanup to all products."""
    products = await db.products.find({}).to_list(10000)
    
    updated_count = 0
    changes = []
    
    for product in products:
        name = product.get('name', '')
        cleaned = clean_product_name_v2(name)
        
        if name != cleaned:
            changes.append({
                'sku': product.get('sku'),
                'original': name,
                'cleaned': cleaned
            })
            
            if not dry_run:
                await db.products.update_one(
                    {'id': product.get('id')},
                    {'$set': {'name': cleaned}}
                )
                updated_count += 1
    
    return {
        'total_products': len(products),
        'products_to_update': len(changes),
        'updated': updated_count if not dry_run else 0,
        'dry_run': dry_run,
        'sample_changes': changes[:10]
    }


async def main():
    # Test the cleaning function
    test_names = [
        "Straight Edge Chrome Polished Aluminium Tile Trim 10mm 10mm (10mm)",
        "L Shape Bright Gold Tile Trim 12mm (12mm)",
        "Tile Spacers 3mm 3mm (3mm) Pack of 500",
        "Diamond Drill Bit 10mm (10mm) M14",
        "Pro-Mat 600x600 Uncoupling Mat (600x600)",
        "Adhesive Trowel 10mm x 10mm (10x10mm)",
        "Normal Product Without Duplicates",
        "Product with (10mm) only once"
    ]
    
    print("=== Testing Product Name Cleanup ===\n")
    for name in test_names:
        cleaned = clean_product_name_v2(name)
        if name != cleaned:
            print(f"BEFORE: {name}")
            print(f"AFTER:  {cleaned}")
            print()
        else:
            print(f"NO CHANGE: {name}\n")
    
    # Connect to database and preview changes
    mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    db_name = os.environ.get('DB_NAME', 'test_database')
    
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    print("\n=== Preview Database Changes ===\n")
    result = await apply_changes(db, dry_run=True)
    print(f"Total products: {result['total_products']}")
    print(f"Products to update: {result['products_to_update']}")
    print(f"\nSample changes:")
    for change in result['sample_changes']:
        print(f"  SKU: {change['sku']}")
        print(f"    FROM: {change['original']}")
        print(f"    TO:   {change['cleaned']}")
        print()
    
    client.close()


if __name__ == "__main__":
    asyncio.run(main())

"""
Product Naming Rules Configuration
===================================
These rules MUST be applied when importing products from ANY supplier.

Last Updated: February 2026
"""

# =============================================================================
# PRICING RULES
# =============================================================================
# List Price = Cost × Markup × VAT, then round to .99p
# Default: 90% markup + 20% VAT + round to .99

PRICING_RULES = {
    "markup_percentage": 90,  # 90% markup on cost
    "markup_multiplier": 1.90,  # Cost × 1.90
    "vat_percentage": 20,  # 20% VAT
    "vat_multiplier": 1.20,  # × 1.20
    "round_to_99": True,  # ALWAYS round prices to end in .99p
}

def calculate_list_price(cost: float) -> float:
    """
    Calculate list price with markup, VAT, and round to .99p
    Formula: Cost × 1.90 (markup) × 1.20 (VAT) → round up to .99
    
    Example: £8.95 × 1.90 × 1.20 = £20.41 → £20.99
    
    Args:
        cost: Cost price (either per m² or per each)
    
    Returns:
        List price rounded to .99p
    """
    import math
    
    if cost and cost > 0:
        markup = PRICING_RULES["markup_multiplier"]
        vat = PRICING_RULES["vat_multiplier"]
        raw_price = cost * markup * vat
        
        if PRICING_RULES["round_to_99"]:
            # Round UP to next whole number, then subtract 1p for .99
            whole = math.ceil(raw_price)
            return whole - 0.01
        else:
            return round(raw_price, 2)
    return 0


# =============================================================================
# SKU CODE FORMAT RULES
# =============================================================================
# Format: TS + Supplier Initial + Code Type Letter + Last 4 digits
# Example: P14274 → TSVP4274 (Wall Tile)
#          A14274 → TSVA4274 (Accessory)
#          L10090 → TSVL0090 (Flooring)
#
# This prevents SKU collisions when different product types share the same numbers

SKU_FORMAT = {
    "prefix": "TS",  # Tile Station
    "include_supplier_initial": True,
    "include_code_type_letter": True,  # Include P/A/L etc to avoid collisions
    "last_digits_count": 4,  # Take last 4 digits from supplier code
}

# Supplier initials for SKU generation
SUPPLIER_INITIALS = {
    "Verona": "V",
    "Splendour": "S", 
    "Ceramica Impex": "C",
    "Tiles Direct": "T",
    # Add more suppliers as needed
}

def generate_sku(supplier_code: str, supplier_name: str) -> str:
    """
    Generate standardized SKU code.
    Format: TS + Supplier Initial + Code Type Letter + Last 4 digits
    
    Args:
        supplier_code: Original supplier code (e.g., "P14274", "A14274", "L10090")
        supplier_name: Supplier name (e.g., "Verona")
    
    Returns:
        New SKU (e.g., "TSVP4274", "TSVA4274", "TSVL0090")
    """
    # Get supplier initial
    initial = SUPPLIER_INITIALS.get(supplier_name, supplier_name[0].upper() if supplier_name else "X")
    
    # Extract code part (after dash if present)
    if '-' in supplier_code:
        code_part = supplier_code.split('-')[1]
    else:
        code_part = supplier_code
    
    # Get first letter (code type: P=Product, A=Accessory, L=Flooring, etc.)
    code_type = code_part[0] if code_part else "X"
    
    # Get last 4 digits
    last_digits = code_part[-SKU_FORMAT["last_digits_count"]:]
    if len(last_digits) < SKU_FORMAT["last_digits_count"]:
        last_digits = last_digits.zfill(SKU_FORMAT["last_digits_count"])
    
    return f"{SKU_FORMAT['prefix']}{initial}{code_type}{last_digits}"

# =============================================================================
# PRODUCT NAME FORMAT RULES
# =============================================================================
# Format: {Name} {Size} {Finish} {Characteristics}
# Example: "Mercury 600x600 Polished Prime"

PRODUCT_NAME_FORMAT = {
    # Order of elements in product name
    "format_order": ["name", "size", "finish", "characteristics"],
    
    # 1. Remove "The" from ALL product names
    "remove_words": ["The"],
    
    # 2. Size MUST come BEFORE finish
    "size_before_finish": True,
    
    # 3. Remove duplicate words (case-insensitive)
    "remove_duplicates": True,
    
    # 4. Preserve characteristic words at the end
    "characteristics": [
        "Decor", "Feature", "Gleam", "Radiance", "Classic", "Select",
        "Elegance", "Prime", "Collection", "Range", "Terrace", "Heritage",
        "Universal", "Complete", "Premium", "Luxe", "Total", "Dual",
        "Panel", "Art", "Brilliance", "Accent", "Blend", "Edition"
    ]
}

# =============================================================================
# FINISH OPTIONS
# =============================================================================
FINISH_OPTIONS = [
    "Matt",
    "Gloss", 
    "Polished",
    "Polish",
    "Satin",
    "Satin Matt",  # Added Feb 2026
    "Lappato",
    "Natural",
    "Textured",
    "Anti-Slip",
    "Slate",
    "Sparkle",
    "Silk"
]

# =============================================================================
# UNIQUE NAME RULES (Display Name / Series Name)
# =============================================================================
UNIQUE_NAME_RULES = {
    # 1. ALL products from SAME supplier series get SAME unique name
    "consistent_per_series": True,
    
    # 2. Use supplier's original series/range name
    "use_supplier_series_name": True,
    
    # 3. Remove "The" from unique names too
    "remove_the_prefix": True,
    
    # 4. Preserve product type identifiers
    "preserve_types": [
        "Wall Tile", "Floor Tile", "Wall & Floor Tile",
        "Mosaic", "Hexagon", "Hex", "Marble", "Porcelain", "Stone"
    ]
}

# =============================================================================
# EXCLUDED CATEGORIES (Don't process these)
# =============================================================================
EXCLUDED_CATEGORIES = [
    "Essentials",
    "Flooring Accessories"
]

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
import re

def clean_product_name(name: str, size: str, finish: str) -> str:
    """
    Clean and format a product name according to rules.
    Format: {Name} {Size} {Finish} {Characteristics}
    """
    result = name
    
    # Remove "The " prefix and "The" anywhere
    for word in PRODUCT_NAME_FORMAT["remove_words"]:
        result = re.sub(rf'^{word}\s+', '', result, flags=re.IGNORECASE)
        result = re.sub(rf'\s+{word}\s+', ' ', result, flags=re.IGNORECASE)
    
    # Find size pattern in name
    size_pattern = r'\d+x\d+'
    size_match = re.search(size_pattern, result)
    
    if size_match:
        size_in_name = size_match.group()
        before_size = result[:size_match.start()].strip()
        after_size = result[size_match.end():].strip()
        
        # Extract finish from before_size
        finish_found = None
        name_parts = []
        
        for word in before_size.split():
            if word in FINISH_OPTIONS:
                finish_found = word
            else:
                name_parts.append(word)
        
        base_name = ' '.join(name_parts)
        
        # Extract characteristics from after_size
        char_parts = []
        for word in after_size.split():
            if word in FINISH_OPTIONS:
                if not finish_found:
                    finish_found = word
            else:
                char_parts.append(word)
        
        # Use finish from field if not found
        if not finish_found and finish:
            finish_found = finish
        
        # Build: {Name} {Size} {Finish} {Characteristics}
        parts = [base_name, size_in_name]
        if finish_found:
            parts.append(finish_found)
        parts.extend(char_parts)
        
        result = ' '.join([p for p in parts if p])
    
    # Remove duplicate words
    if PRODUCT_NAME_FORMAT["remove_duplicates"]:
        words = result.split()
        seen = set()
        unique = []
        for word in words:
            if word.lower() not in seen:
                seen.add(word.lower())
                unique.append(word)
        result = ' '.join(unique)
    
    return result.strip()


def get_unique_name_for_series(supplier_series_name: str) -> str:
    """
    Get consistent unique name for a product series.
    All products in the same series MUST have the same unique name.
    """
    result = supplier_series_name
    
    if UNIQUE_NAME_RULES["remove_the_prefix"]:
        if result.startswith("The "):
            result = result[4:]
    
    return result

"""
Unique Product Name Generator
Generates unique, SEO-friendly product names for tiles to prevent
customers from searching for products directly from suppliers.
"""
import random
import re
from typing import Set, Dict, Optional

# City/Location names for different tile styles
MARBLE_CITIES = [
    "Carrara", "Calacatta", "Statuario", "Verona", "Milano", "Firenze", "Roma",
    "Venezia", "Napoli", "Siena", "Parma", "Torino", "Bologna", "Genova"
]

STONE_CITIES = [
    "Athens", "Santorini", "Valencia", "Granada", "Lisbon", "Naples", "Palermo",
    "Seville", "Cordoba", "Malaga", "Porto", "Rhodes", "Crete", "Mykonos"
]

MODERN_CITIES = [
    "Oslo", "Copenhagen", "Stockholm", "Berlin", "Amsterdam", "Vienna", "Zurich",
    "Helsinki", "Geneva", "Munich", "Prague", "Warsaw", "Brussels", "Dublin"
]

COASTAL_CITIES = [
    "Amalfi", "Capri", "Positano", "Monaco", "Riviera", "Marbella", "Ibiza",
    "Cannes", "Nice", "Portofino", "Sorrento", "Sardinia", "Corsica", "Malta"
]

NATURE_NAMES = [
    "Alpine", "Aurora", "Cascade", "Crystal", "Glacier", "Horizon", "Luna",
    "Meadow", "Mist", "Ocean", "Pacific", "Ridge", "River", "Sahara",
    "Sierra", "Summit", "Sunset", "Terra", "Valley", "Zenith", "Dune"
]

# Color-based prefixes
COLOR_WORDS = {
    "white": ["Arctic", "Snow", "Pearl", "Ivory", "Cloud", "Frost", "Luna", "Polar", "Alabaster"],
    "grey": ["Storm", "Ash", "Slate", "Silver", "Graphite", "Steel", "Smoke", "Charcoal", "Pewter"],
    "beige": ["Sand", "Sahara", "Dune", "Cream", "Honey", "Wheat", "Sienna", "Caramel", "Biscuit"],
    "black": ["Midnight", "Ebony", "Noir", "Shadow", "Onyx", "Obsidian", "Jet", "Raven", "Coal"],
    "brown": ["Timber", "Oak", "Walnut", "Chestnut", "Mocha", "Espresso", "Hazel", "Cocoa", "Umber"],
    "blue": ["Ocean", "Azure", "Pacific", "Aegean", "Cobalt", "Indigo", "Marine", "Sapphire", "Teal"],
    "gold": ["Imperial", "Royal", "Amber", "Champagne", "Gilded", "Sovereign", "Noble", "Majestic", "Regal"],
    "green": ["Forest", "Emerald", "Sage", "Moss", "Jade", "Verdant", "Olive", "Fern", "Mint"],
    "pink": ["Blush", "Rose", "Coral", "Salmon", "Peach", "Rouge", "Dusty", "Shell", "Petal"],
    "red": ["Burgundy", "Crimson", "Ruby", "Garnet", "Terracotta", "Rust", "Brick", "Cherry", "Wine"],
}

# Style suffixes
MARBLE_EFFECTS = ["Luxe", "Elite", "Supreme", "Grand", "Royal", "Imperial", "Majestic", "Premier"]
STONE_EFFECTS = ["Natural", "Rustic", "Heritage", "Artisan", "Terra", "Organic", "Classic", "Traditional"]
MODERN_EFFECTS = ["Urban", "Metro", "Prime", "Edge", "Minimal", "Pure", "Essential", "Contemporary"]
WOOD_EFFECTS = ["Grove", "Forest", "Woodland", "Timber", "Lodge", "Cabin", "Ranch", "Estate"]

# Color detection keywords
COLOR_KEYWORDS = {
    "white": ["white", "bianco", "blanco", "snow", "arctic", "ice", "light", "pearl", "ivory", "cream"],
    "grey": ["grey", "gray", "gris", "grigio", "graphite", "anthracite", "charcoal", "steel", "silver", "smoke"],
    "beige": ["beige", "cream", "crema", "sand", "bone", "ivory", "natural", "taupe", "buff"],
    "black": ["black", "nero", "dark", "ebony", "midnight", "jet", "noir", "onyx"],
    "brown": ["brown", "marron", "walnut", "oak", "wood", "chocolate", "cocoa", "coffee", "chestnut"],
    "blue": ["blue", "azure", "ocean", "navy", "sky", "aqua", "turquoise", "teal", "cobalt"],
    "gold": ["gold", "golden", "honey", "amber", "brass", "bronze", "copper", "mustard"],
    "green": ["green", "emerald", "forest", "sage", "olive", "moss", "teal", "jade"],
    "pink": ["pink", "rose", "blush", "coral", "salmon", "peach"],
    "red": ["red", "terracotta", "rust", "burgundy", "crimson", "brick"],
}

# Material detection keywords
MATERIAL_KEYWORDS = {
    "marble": ["marble", "carrara", "calacatta", "statuario", "veined", "marmo", "onyx"],
    "stone": ["stone", "limestone", "sandstone", "slate", "granite", "travertine", "rock"],
    "wood": ["wood", "timber", "oak", "walnut", "pine", "plank", "parquet", "forest"],
    "concrete": ["concrete", "cement", "industrial", "urban", "metro"],
    "terrazzo": ["terrazzo", "speckled", "flecked", "chips"],
}


class UniqueNameGenerator:
    """
    Generates unique product names for tiles based on their characteristics.
    Ensures no duplicate names are generated.
    """
    
    def __init__(self):
        self.used_names: Set[str] = set()
        self.supplier_name_map: Dict[str, str] = {}  # supplier_name -> our_name
    
    def detect_color(self, text: str) -> str:
        """Detect primary color from product name/description"""
        text_lower = text.lower()
        
        for color, keywords in COLOR_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                return color
        
        return "grey"  # Default
    
    def detect_material(self, text: str) -> str:
        """Detect material type from product name/description"""
        text_lower = text.lower()
        
        for material, keywords in MATERIAL_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                return material
        
        return "stone"  # Default
    
    def generate_name(
        self,
        supplier_name: str,
        material: str = "",
        finish: str = "",
        color_hint: str = "",
        size: str = ""
    ) -> str:
        """
        Generate a unique product name based on characteristics.
        
        Args:
            supplier_name: Original supplier product name
            material: Material type (Porcelain, Ceramic, etc.)
            finish: Finish type (Polished, Matt, etc.)
            color_hint: Color hint from product data
            size: Size string (e.g., "60x60")
            
        Returns:
            Unique product name
        """
        # Check if we already have a name for this supplier product
        cache_key = f"{supplier_name}_{material}_{finish}"
        if cache_key in self.supplier_name_map:
            return self.supplier_name_map[cache_key]
        
        # Combine all text for analysis
        combined_text = f"{supplier_name} {material} {finish} {color_hint}"
        
        # Detect characteristics
        color = self.detect_color(combined_text)
        mat_type = self.detect_material(combined_text)
        
        # Select appropriate naming components
        if mat_type == "marble":
            cities = MARBLE_CITIES
            effects = MARBLE_EFFECTS
        elif mat_type in ["stone", "terrazzo"]:
            cities = STONE_CITIES
            effects = STONE_EFFECTS
        elif mat_type == "wood":
            cities = NATURE_NAMES
            effects = WOOD_EFFECTS
        else:
            cities = MODERN_CITIES
            effects = MODERN_EFFECTS
        
        color_words = COLOR_WORDS.get(color, COLOR_WORDS["grey"])
        
        # Generate name patterns to try
        patterns = [
            lambda: f"{random.choice(cities)} {random.choice(color_words)}",
            lambda: f"{random.choice(color_words)} {random.choice(effects)}",
            lambda: f"{random.choice(cities)} {random.choice(effects)}",
            lambda: f"{random.choice(color_words)} {random.choice(cities)}",
            lambda: f"{random.choice(NATURE_NAMES)} {random.choice(color_words)}",
        ]
        
        # Try patterns until we get a unique name
        random.shuffle(patterns)
        for pattern in patterns:
            name = pattern()
            if name not in self.used_names:
                self.used_names.add(name)
                self.supplier_name_map[cache_key] = name
                return name
        
        # If all patterns used, add a number suffix
        base = f"{random.choice(cities)} {random.choice(color_words)}"
        counter = 2
        while f"{base} {counter}" in self.used_names:
            counter += 1
        
        name = f"{base} {counter}"
        self.used_names.add(name)
        self.supplier_name_map[cache_key] = name
        return name
    
    def generate_batch(
        self,
        products: list,
        name_field: str = "name",
        material_field: str = "material",
        finish_field: str = "finish"
    ) -> list:
        """
        Generate unique names for a batch of products.
        
        Args:
            products: List of product dictionaries
            name_field: Key for supplier name in dict
            material_field: Key for material in dict
            finish_field: Key for finish in dict
            
        Returns:
            List of products with 'unique_name' added
        """
        for product in products:
            supplier_name = product.get(name_field, "")
            material = product.get(material_field, "")
            finish = product.get(finish_field, "")
            
            unique_name = self.generate_name(
                supplier_name=supplier_name,
                material=material,
                finish=finish
            )
            
            product["unique_name"] = unique_name
            product["supplier_product_name"] = supplier_name
        
        return products
    
    def get_name_mapping(self) -> Dict[str, str]:
        """Get the full supplier name to unique name mapping"""
        return self.supplier_name_map.copy()
    
    def reset(self):
        """Reset the generator (clear used names)"""
        self.used_names.clear()
        self.supplier_name_map.clear()


# Singleton instance
_generator = None

def get_name_generator() -> UniqueNameGenerator:
    """Get the singleton name generator instance"""
    global _generator
    if _generator is None:
        _generator = UniqueNameGenerator()
    return _generator


# Test function
def test_name_generator():
    """Test the name generator with sample products"""
    generator = UniqueNameGenerator()
    
    test_products = [
        {"name": "Alaska White Gloss Tiles 1200x600", "material": "Porcelain", "finish": "Gloss"},
        {"name": "Carrara Marble Effect 60x60", "material": "Porcelain", "finish": "Polished"},
        {"name": "Grey Stone Matt 30x60", "material": "Porcelain", "finish": "Matt"},
        {"name": "Oak Wood Effect Plank", "material": "Porcelain", "finish": "Matt"},
        {"name": "Black Slate Natural 60x60", "material": "Porcelain", "finish": "Natural"},
        {"name": "Onyx Gold Polished 120x60", "material": "Porcelain", "finish": "Polished"},
        {"name": "Terrazzo Grey Mix 60x60", "material": "Porcelain", "finish": "Matt"},
        {"name": "Cement Anthracite Matt 80x80", "material": "Porcelain", "finish": "Matt"},
        {"name": "Calacatta Veined White 60x120", "material": "Porcelain", "finish": "Polished"},
        {"name": "Travertine Ivory Classic", "material": "Natural Stone", "finish": "Honed"},
    ]
    
    print("=" * 70)
    print("UNIQUE NAME GENERATION TEST")
    print("=" * 70)
    
    results = generator.generate_batch(test_products)
    
    for product in results:
        print(f"\nSupplier: {product['supplier_product_name']}")
        print(f"Our Name: {product['unique_name']}")
    
    print("\n" + "=" * 70)
    print(f"Generated {len(results)} unique names")


if __name__ == "__main__":
    test_name_generator()

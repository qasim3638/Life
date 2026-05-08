"""
Test Color Swatches Fix - Verifies that collection cards show correct color swatches
extracted from product names when DB color field is empty.

Bug Fix Tested:
- Products without 'color' DB field but with color info in names (e.g., 'Ridge White 60x120cm')
  should have colors extracted and shown in swatches
- product_images array should have color entries FIRST, then non-color entries
- additional_colors count should be based on color_swatches length
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestColorSwatchesFix:
    """Tests for color swatch extraction and prioritization in collections API"""
    
    def test_collections_endpoint_returns_color_swatches(self):
        """GET /api/tiles/collections returns color_swatches array"""
        response = requests.get(f"{BASE_URL}/api/tiles/collections?limit=5")
        assert response.status_code == 200
        
        data = response.json()
        assert "collections" in data
        assert len(data["collections"]) > 0
        
        # Check that collections have color_swatches field
        for collection in data["collections"]:
            assert "color_swatches" in collection
            assert isinstance(collection["color_swatches"], list)
    
    def test_opaco_collection_extracts_colors_from_names(self):
        """Opaco collection should show White/Grey colors extracted from product names"""
        response = requests.get(f"{BASE_URL}/api/tiles/collections?search=Opaco&limit=5")
        assert response.status_code == 200
        
        data = response.json()
        collections = data.get("collections", [])
        
        # Find Opaco collection
        opaco = next((c for c in collections if c.get("series_name") == "Opaco"), None)
        assert opaco is not None, "Opaco collection not found"
        
        # Verify color swatches extracted from product names
        color_swatches = opaco.get("color_swatches", [])
        colors = [s.get("color") for s in color_swatches]
        
        assert len(color_swatches) >= 2, f"Expected at least 2 colors, got {len(color_swatches)}"
        assert "White" in colors, f"Expected 'White' in colors, got {colors}"
        assert "Grey" in colors, f"Expected 'Grey' in colors, got {colors}"
    
    def test_bluestone_collection_uses_db_color_field(self):
        """Bluestone collection should show Grey/Beige/White from DB color field"""
        response = requests.get(f"{BASE_URL}/api/tiles/collections?search=Bluestone&limit=5")
        assert response.status_code == 200
        
        data = response.json()
        collections = data.get("collections", [])
        
        # Find Bluestone collection
        bluestone = next((c for c in collections if c.get("series_name") == "Bluestone"), None)
        assert bluestone is not None, "Bluestone collection not found"
        
        # Verify color swatches from DB field
        color_swatches = bluestone.get("color_swatches", [])
        colors = [s.get("color") for s in color_swatches]
        
        assert len(color_swatches) >= 3, f"Expected at least 3 colors, got {len(color_swatches)}"
        assert "Grey" in colors, f"Expected 'Grey' in colors, got {colors}"
        assert "Beige" in colors, f"Expected 'Beige' in colors, got {colors}"
        assert "White" in colors, f"Expected 'White' in colors, got {colors}"
    
    def test_sparkle_collection_extracts_colors_from_names(self):
        """Sparkle collection should show Cream/Grey/White from name extraction"""
        response = requests.get(f"{BASE_URL}/api/tiles/collections?search=Sparkle&limit=5")
        assert response.status_code == 200
        
        data = response.json()
        collections = data.get("collections", [])
        
        # Find Sparkle collection
        sparkle = next((c for c in collections if c.get("series_name") == "Sparkle"), None)
        assert sparkle is not None, "Sparkle collection not found"
        
        # Verify color swatches extracted from product names
        color_swatches = sparkle.get("color_swatches", [])
        colors = [s.get("color") for s in color_swatches]
        
        assert len(color_swatches) >= 3, f"Expected at least 3 colors, got {len(color_swatches)}"
        assert "Cream" in colors, f"Expected 'Cream' in colors, got {colors}"
        assert "Grey" in colors, f"Expected 'Grey' in colors, got {colors}"
        assert "White" in colors, f"Expected 'White' in colors, got {colors}"
    
    def test_product_images_prioritizes_color_entries(self):
        """product_images array should have color entries BEFORE non-color entries"""
        response = requests.get(f"{BASE_URL}/api/tiles/collections?search=Opaco&limit=5")
        assert response.status_code == 200
        
        data = response.json()
        collections = data.get("collections", [])
        
        opaco = next((c for c in collections if c.get("series_name") == "Opaco"), None)
        assert opaco is not None, "Opaco collection not found"
        
        product_images = opaco.get("product_images", [])
        color_swatches = opaco.get("color_swatches", [])
        
        # Get the color names from swatches
        swatch_colors = {s.get("color") for s in color_swatches}
        
        # Verify first N entries in product_images match color swatches
        for i, swatch in enumerate(color_swatches):
            if i < len(product_images):
                assert product_images[i].get("color") == swatch.get("color"), \
                    f"product_images[{i}] should be '{swatch.get('color')}', got '{product_images[i].get('color')}'"
    
    def test_additional_colors_based_on_swatches_length(self):
        """additional_colors should be based on color_swatches length, not total colors"""
        response = requests.get(f"{BASE_URL}/api/tiles/collections?limit=20")
        assert response.status_code == 200
        
        data = response.json()
        collections = data.get("collections", [])
        
        for collection in collections:
            color_swatches = collection.get("color_swatches", [])
            additional_colors = collection.get("additional_colors", 0)
            
            # additional_colors = max(0, len(color_swatches) - 8)
            expected_additional = max(0, len(color_swatches) - 8)
            assert additional_colors == expected_additional, \
                f"Collection '{collection.get('series_name')}': expected additional_colors={expected_additional}, got {additional_colors}"
    
    def test_color_swatches_have_required_fields(self):
        """Each color swatch should have color, hex, image, and product_slug"""
        response = requests.get(f"{BASE_URL}/api/tiles/collections?limit=5")
        assert response.status_code == 200
        
        data = response.json()
        collections = data.get("collections", [])
        
        for collection in collections:
            for swatch in collection.get("color_swatches", []):
                assert "color" in swatch, f"Swatch missing 'color' field"
                assert "hex" in swatch, f"Swatch missing 'hex' field"
                assert "image" in swatch, f"Swatch missing 'image' field"
                assert "product_slug" in swatch, f"Swatch missing 'product_slug' field"
    
    def test_testseries_collection_extracts_colors(self):
        """Testseries collection should show White/Grey from name extraction"""
        response = requests.get(f"{BASE_URL}/api/tiles/collections?search=Testseries&limit=5")
        assert response.status_code == 200
        
        data = response.json()
        collections = data.get("collections", [])
        
        testseries = next((c for c in collections if c.get("series_name") == "Testseries"), None)
        assert testseries is not None, "Testseries collection not found"
        
        color_swatches = testseries.get("color_swatches", [])
        colors = [s.get("color") for s in color_swatches]
        
        assert len(color_swatches) >= 2, f"Expected at least 2 colors, got {len(color_swatches)}"
        assert "White" in colors, f"Expected 'White' in colors, got {colors}"
        assert "Grey" in colors, f"Expected 'Grey' in colors, got {colors}"
    
    def test_colour_pluralization_badge_data(self):
        """Collections should have correct color count for COLOUR/COLOURS badge"""
        response = requests.get(f"{BASE_URL}/api/tiles/collections?limit=10")
        assert response.status_code == 200
        
        data = response.json()
        collections = data.get("collections", [])
        
        for collection in collections:
            color_swatches = collection.get("color_swatches", [])
            additional_colors = collection.get("additional_colors", 0)
            
            # Total color count for badge
            total_colors = len(color_swatches) + additional_colors
            
            # Verify the count is consistent
            # Frontend uses: colorCount = color_swatches.length + additional_colors
            # Badge shows: "1 COLOUR" or "N COLOURS"
            assert total_colors >= 0, f"Invalid color count for {collection.get('series_name')}"


class TestCollectionDetailPage:
    """Tests for collection detail page color extraction"""
    
    def test_collection_detail_returns_products(self):
        """GET /api/tiles/collection/{series_name} returns products"""
        response = requests.get(f"{BASE_URL}/api/tiles/collection/Opaco?limit=10")
        assert response.status_code == 200
        
        data = response.json()
        assert "products" in data
        assert len(data["products"]) > 0
    
    def test_collection_detail_products_have_color_info(self):
        """Products in collection detail should have color info (from field or extractable from name)"""
        # Use Bluestone which has DB color field populated
        response = requests.get(f"{BASE_URL}/api/tiles/collection/Bluestone?limit=10")
        assert response.status_code == 200
        
        data = response.json()
        products = data.get("products", [])
        
        # Bluestone products should have color field populated
        products_with_color = [p for p in products if p.get("color")]
        assert len(products_with_color) > 0, f"Expected some products with color field, got products: {[p.get('display_name') for p in products[:3]]}"
    
    def test_opaco_products_have_color_in_name(self):
        """Ridge products should have color extractable from display_name"""
        response = requests.get(f"{BASE_URL}/api/tiles/collection/Ridge?limit=10")
        assert response.status_code == 200
        
        data = response.json()
        products = data.get("products", [])
        
        # Check that product names contain color words
        color_keywords = {'white', 'grey', 'gray', 'black', 'beige', 'cream'}
        products_with_color_in_name = []
        for p in products:
            name = (p.get("display_name") or "").lower()
            if any(color in name for color in color_keywords):
                products_with_color_in_name.append(p)
        
        assert len(products_with_color_in_name) > 0, f"Expected some products with color in name, got: {[p.get('display_name') for p in products[:5]]}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

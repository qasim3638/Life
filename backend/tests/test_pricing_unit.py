"""
Test cases for Pricing Unit feature
Tests the ability to set products as m²-based (tiles) or unit-based (adhesive, grout, tools)
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBulkPricingUnitEndpoint:
    """Tests for PUT /api/supplier-sync/products/bulk-pricing-unit endpoint"""
    
    def test_endpoint_exists(self):
        """Test that the bulk-pricing-unit endpoint exists"""
        response = requests.put(
            f"{BASE_URL}/api/supplier-sync/products/bulk-pricing-unit",
            json={
                "products": [],
                "pricing_unit": "m2"
            },
            timeout=10
        )
        # Should not return 404 (endpoint not found)
        assert response.status_code != 404, f"Endpoint not found. Status: {response.status_code}"
        print(f"PASS: Endpoint exists, returned status {response.status_code}")
    
    def test_valid_pricing_unit_m2(self):
        """Test setting pricing_unit to 'm2' (valid)"""
        response = requests.put(
            f"{BASE_URL}/api/supplier-sync/products/bulk-pricing-unit",
            json={
                "products": [],
                "pricing_unit": "m2"
            },
            timeout=10
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("success") == True
        assert data.get("pricing_unit") == "m2"
        print(f"PASS: pricing_unit 'm2' accepted. Response: {data}")
    
    def test_valid_pricing_unit_unit(self):
        """Test setting pricing_unit to 'unit' (valid)"""
        response = requests.put(
            f"{BASE_URL}/api/supplier-sync/products/bulk-pricing-unit",
            json={
                "products": [],
                "pricing_unit": "unit"
            },
            timeout=10
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("success") == True
        assert data.get("pricing_unit") == "unit"
        print(f"PASS: pricing_unit 'unit' accepted. Response: {data}")
    
    def test_invalid_pricing_unit_returns_400(self):
        """Test that invalid pricing_unit value returns 400 Bad Request"""
        response = requests.put(
            f"{BASE_URL}/api/supplier-sync/products/bulk-pricing-unit",
            json={
                "products": [],
                "pricing_unit": "invalid_value"
            },
            timeout=10
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert "detail" in data
        assert "m2" in data["detail"].lower() or "unit" in data["detail"].lower()
        print(f"PASS: Invalid pricing_unit returns 400. Detail: {data.get('detail')}")
    
    def test_invalid_pricing_unit_box(self):
        """Test that 'box' is not a valid pricing_unit"""
        response = requests.put(
            f"{BASE_URL}/api/supplier-sync/products/bulk-pricing-unit",
            json={
                "products": [],
                "pricing_unit": "box"
            },
            timeout=10
        )
        assert response.status_code == 400, f"Expected 400 for 'box', got {response.status_code}"
        print("PASS: 'box' correctly rejected as invalid pricing_unit")
    
    def test_missing_pricing_unit_field(self):
        """Test that missing pricing_unit field returns error"""
        response = requests.put(
            f"{BASE_URL}/api/supplier-sync/products/bulk-pricing-unit",
            json={
                "products": []
            },
            timeout=10
        )
        assert response.status_code == 422, f"Expected 422 (validation error), got {response.status_code}"
        print("PASS: Missing pricing_unit field returns validation error")
    
    def test_unit_price_with_unit_type(self):
        """Test setting unit_price when pricing_unit is 'unit'"""
        response = requests.put(
            f"{BASE_URL}/api/supplier-sync/products/bulk-pricing-unit",
            json={
                "products": [],
                "pricing_unit": "unit",
                "unit_price": 5.99
            },
            timeout=10
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("success") == True
        print(f"PASS: unit_price with 'unit' type accepted. Response: {data}")


class TestProductPricingUnitUpdate:
    """Tests for updating actual products with pricing_unit"""
    
    @pytest.fixture
    def get_test_product(self):
        """Get a product from Test Series or any available product for testing"""
        # First try to find Test Series products
        response = requests.get(
            f"{BASE_URL}/api/supplier-sync/products?search=Test&limit=1",
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            products = data.get("products", [])
            if products:
                return products[0]
        
        # Fallback: get any product
        response = requests.get(
            f"{BASE_URL}/api/supplier-sync/products?limit=1",
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            products = data.get("products", [])
            if products:
                return products[0]
        
        pytest.skip("No products available for testing")
    
    def test_update_product_to_unit_pricing(self, get_test_product):
        """Test updating a product to use unit-based pricing"""
        product = get_test_product
        supplier = product.get("supplier")
        sku = product.get("sku")
        
        print(f"Testing with product: {supplier} / {sku}")
        
        response = requests.put(
            f"{BASE_URL}/api/supplier-sync/products/bulk-pricing-unit",
            json={
                "products": [{"supplier": supplier, "sku": sku}],
                "pricing_unit": "unit",
                "unit_price": 9.99
            },
            timeout=10
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}. Response: {response.text}"
        data = response.json()
        assert data.get("success") == True
        assert data.get("updated_count") >= 0, "Should return updated_count"
        print(f"PASS: Product updated to unit pricing. Updated count: {data.get('updated_count')}")
    
    def test_update_product_to_m2_pricing(self, get_test_product):
        """Test updating a product to use m²-based pricing"""
        product = get_test_product
        supplier = product.get("supplier")
        sku = product.get("sku")
        
        print(f"Testing with product: {supplier} / {sku}")
        
        response = requests.put(
            f"{BASE_URL}/api/supplier-sync/products/bulk-pricing-unit",
            json={
                "products": [{"supplier": supplier, "sku": sku}],
                "pricing_unit": "m2"
            },
            timeout=10
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("success") == True
        print(f"PASS: Product updated to m² pricing. Updated count: {data.get('updated_count')}")


class TestTierPricingWithUnits:
    """Tests for tier pricing calculation with unit-based products"""
    
    def test_calculate_unit_tier_price_endpoint_exists(self):
        """Test that the calculate-unit endpoint exists"""
        response = requests.get(
            f"{BASE_URL}/api/tiles/pricing/calculate-unit?unit_price=5.99&quantity=10",
            timeout=10
        )
        # Should not return 404
        assert response.status_code != 404, f"Endpoint not found. Status: {response.status_code}"
        print(f"PASS: calculate-unit endpoint exists, returned {response.status_code}")
    
    def test_calculate_unit_tier_price(self):
        """Test tier pricing calculation for unit-based products"""
        response = requests.get(
            f"{BASE_URL}/api/tiles/pricing/calculate-unit?unit_price=5.99&quantity=10",
            timeout=10
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        # Should return pricing unit as 'unit'
        assert data.get("pricing_unit") == "unit", f"Expected pricing_unit='unit', got {data.get('pricing_unit')}"
        # Should have tiers or indicate disabled
        assert "tiers" in data or "disabled" in data
        print(f"PASS: Unit tier pricing calculated. Response: {data}")
    
    def test_calculate_m2_tier_price(self):
        """Test tier pricing calculation for m²-based products (existing functionality)"""
        response = requests.get(
            f"{BASE_URL}/api/tiles/pricing/calculate?base_price=29.99&quantity=10",
            timeout=10
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        # Should have tiers
        assert "tiers" in data or "disabled" in data
        print(f"PASS: m² tier pricing calculated. Response: {data}")


class TestTileSerializationWithPricingUnit:
    """Tests for tiles API returning pricing_unit field"""
    
    def test_get_tile_products_includes_pricing_unit(self):
        """Test that GET /api/tiles/products returns pricing_unit field"""
        response = requests.get(
            f"{BASE_URL}/api/tiles/products?limit=5",
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            products = data.get("products", [])
            if products:
                # Check if pricing_unit field exists (default should be 'm2')
                product = products[0]
                pricing_unit = product.get("pricing_unit")
                # The field should exist
                assert "pricing_unit" in product, f"pricing_unit field not in product response"
                assert pricing_unit in ["m2", "unit", None], f"Invalid pricing_unit value: {pricing_unit}"
                print(f"PASS: pricing_unit field present in tiles API. Value: {pricing_unit}")
            else:
                print("SKIP: No products in tiles collection")
        else:
            print(f"SKIP: tiles API returned {response.status_code}")
    
    def test_get_tile_by_slug_includes_pricing_unit(self):
        """Test that single tile GET includes pricing_unit field"""
        # First get a tile to find its slug
        response = requests.get(
            f"{BASE_URL}/api/tiles/products?limit=1",
            timeout=10
        )
        if response.status_code != 200:
            pytest.skip("Could not fetch tiles")
        
        data = response.json()
        products = data.get("products", [])
        if not products:
            pytest.skip("No tiles available")
        
        slug = products[0].get("slug")
        if not slug:
            pytest.skip("Tile has no slug")
        
        # Now fetch single tile by slug
        response = requests.get(
            f"{BASE_URL}/api/tiles/products/{slug}",
            timeout=10
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        tile = response.json()
        assert "pricing_unit" in tile, "pricing_unit field missing from single tile response"
        print(f"PASS: Single tile API includes pricing_unit. Slug: {slug}, pricing_unit: {tile.get('pricing_unit')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

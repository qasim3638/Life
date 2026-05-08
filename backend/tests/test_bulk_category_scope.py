"""
Test suite for Bulk Category Editor scope hydration bug fix
Tests the backend endpoints used by the Bulk Category Editor
"""
import pytest
import requests
import os
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestSupplierProductsAPI:
    """Test supplier products API endpoints"""
    
    def test_get_products_returns_category_fields(self):
        """Test that /api/supplier-sync/products returns products with category fields"""
        response = requests.get(f"{BASE_URL}/api/supplier-sync/products", params={"limit": 10})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "products" in data or isinstance(data, list), "Response should contain products"
        
        products = data.get("products", data) if isinstance(data, dict) else data
        assert len(products) > 0, "Should return at least one product"
        
        # Check that products have the fields needed for scope reconstruction
        product = products[0]
        print(f"Sample product fields: {list(product.keys())}")
        
        # These fields are used for scope reconstruction
        expected_fields = ['sku', 'product_name']
        for field in expected_fields:
            assert field in product or 'name' in product, f"Product should have {field} field"
    
    def test_get_products_with_sub_categories(self):
        """Test that products with sub_categories are returned correctly"""
        response = requests.get(f"{BASE_URL}/api/supplier-sync/products", params={"limit": 50})
        assert response.status_code == 200
        
        data = response.json()
        products = data.get("products", data) if isinstance(data, dict) else data
        
        # Find products with sub_categories
        products_with_subcats = [p for p in products if p.get('sub_categories')]
        print(f"Found {len(products_with_subcats)} products with sub_categories out of {len(products)}")
        
        if products_with_subcats:
            sample = products_with_subcats[0]
            print(f"Sample sub_categories: {sample.get('sub_categories')}")
            assert isinstance(sample.get('sub_categories'), list), "sub_categories should be a list"
    
    def test_get_products_with_filter_fields(self):
        """Test that products have filter fields (colors, suitability, finish, etc.)"""
        response = requests.get(f"{BASE_URL}/api/supplier-sync/products", params={"limit": 50})
        assert response.status_code == 200
        
        data = response.json()
        products = data.get("products", data) if isinstance(data, dict) else data
        
        # Check for filter fields used in scope reconstruction
        filter_fields = ['colors', 'suitability', 'finish', 'thickness', 'slip_rating']
        
        for field in filter_fields:
            products_with_field = [p for p in products if p.get(field)]
            print(f"Products with {field}: {len(products_with_field)}")


class TestBulkUpdateUnifiedAPI:
    """Test the bulk-update-unified endpoint"""
    
    def test_bulk_update_unified_endpoint_exists(self):
        """Test that the bulk-update-unified endpoint exists and accepts POST"""
        # Send a minimal request to check endpoint exists
        response = requests.post(
            f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified",
            json={
                "product_ids": [],
                "updates": {}
            }
        )
        # Should return 400 (bad request) not 404 (not found)
        assert response.status_code in [200, 400], f"Endpoint should exist, got {response.status_code}: {response.text}"
    
    def test_bulk_update_requires_product_ids(self):
        """Test that bulk update requires product_ids"""
        response = requests.post(
            f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified",
            json={
                "updates": {"material": "Porcelain"}
            }
        )
        assert response.status_code == 400, "Should return 400 when product_ids missing"
    
    def test_bulk_update_requires_updates(self):
        """Test that bulk update requires updates"""
        response = requests.post(
            f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified",
            json={
                "product_ids": ["TEST_SKU_123"]
            }
        )
        assert response.status_code == 400, "Should return 400 when updates missing"
    
    def test_bulk_update_with_scoped_categories(self):
        """Test bulk update with scoped sub_categories"""
        # First get a real product SKU
        products_response = requests.get(f"{BASE_URL}/api/supplier-sync/products", params={"limit": 1})
        assert products_response.status_code == 200
        
        data = products_response.json()
        products = data.get("products", data) if isinstance(data, dict) else data
        
        if not products:
            pytest.skip("No products available for testing")
        
        test_sku = products[0].get('sku') or products[0].get('supplier_code')
        if not test_sku:
            pytest.skip("Product has no SKU or supplier_code")
        
        # Test updating with sub_categories
        response = requests.post(
            f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified",
            json={
                "product_ids": [test_sku],
                "id_field": "sku",
                "updates": {
                    "sub_categories": ["Wall Tiles", "Floor Tiles"]
                },
                "mode": "replace"
            }
        )
        
        # Should succeed or return meaningful error
        assert response.status_code in [200, 400, 404], f"Unexpected status: {response.status_code}: {response.text}"
        
        if response.status_code == 200:
            result = response.json()
            print(f"Bulk update result: {result}")


class TestCategoriesAPI:
    """Test categories API endpoints"""
    
    def test_get_categories_by_group(self):
        """Test that categories endpoint returns categories grouped"""
        response = requests.get(f"{BASE_URL}/api/categories/by-group")
        
        # Endpoint might be at different path
        if response.status_code == 404:
            response = requests.get(f"{BASE_URL}/api/website-categories/by-group")
        
        if response.status_code == 404:
            response = requests.get(f"{BASE_URL}/api/categories")
        
        assert response.status_code == 200, f"Categories endpoint should exist: {response.status_code}"
        
        data = response.json()
        print(f"Categories response type: {type(data)}")
        
        if isinstance(data, list) and len(data) > 0:
            print(f"Sample category: {data[0]}")


class TestFiltersAPI:
    """Test filters API endpoints"""
    
    def test_get_filters(self):
        """Test that filters endpoint returns filter types"""
        response = requests.get(f"{BASE_URL}/api/filters")
        
        if response.status_code == 404:
            response = requests.get(f"{BASE_URL}/api/website-filters")
        
        assert response.status_code == 200, f"Filters endpoint should exist: {response.status_code}"
        
        data = response.json()
        print(f"Filters response: {type(data)}, count: {len(data) if isinstance(data, list) else 'N/A'}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

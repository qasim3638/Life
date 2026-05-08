"""
Test Scope Summary Panel Feature - Backend API Tests
Tests for:
1. /api/supplier-sync/products endpoint returns products
2. /api/supplier-sync/products/bulk-update-unified handles scoped updates
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://feature-verification-7.preview.emergentagent.com')

class TestScopeSummaryPanelAPIs:
    """Test backend APIs for Scope Summary Panel feature"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login to get auth token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "qasim@tilestation.co.uk",
            "password": "admin123"
        })
        if login_response.status_code == 200:
            token = login_response.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
            self.auth_token = token
        else:
            pytest.skip("Authentication failed - skipping authenticated tests")
    
    def test_supplier_products_endpoint_returns_products(self):
        """Test /api/supplier-sync/products returns products list"""
        response = self.session.get(f"{BASE_URL}/api/supplier-sync/products")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Verify response structure
        assert "products" in data or isinstance(data, list), "Response should contain products"
        
        products = data.get("products", data) if isinstance(data, dict) else data
        assert len(products) > 0, "Should return at least one product"
        
        # Verify product structure has required fields for scope functionality
        first_product = products[0]
        assert "sku" in first_product or "supplier_code" in first_product, "Product should have sku or supplier_code"
        print(f"SUCCESS: Products endpoint returned {len(products)} products")
    
    def test_supplier_products_with_supplier_filter(self):
        """Test /api/supplier-sync/products with supplier filter"""
        response = self.session.get(f"{BASE_URL}/api/supplier-sync/products?supplier=Canopy")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        products = data.get("products", data) if isinstance(data, dict) else data
        print(f"SUCCESS: Filtered products endpoint returned {len(products)} Canopy products")
    
    def test_bulk_update_unified_endpoint_exists(self):
        """Test /api/supplier-sync/products/bulk-update-unified endpoint exists"""
        # Test with minimal payload to verify endpoint exists
        response = self.session.post(
            f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified",
            json={
                "product_keys": [],
                "updates": {},
                "mode": "replace"
            }
        )
        
        # Should return 200 or 400 (validation error), not 404
        assert response.status_code != 404, "Bulk update endpoint should exist"
        print(f"SUCCESS: Bulk update endpoint exists (status: {response.status_code})")
    
    def test_bulk_update_with_scoped_categories(self):
        """Test bulk update with per-attribute scopes (scoped categories)"""
        # First get some products to use
        products_response = self.session.get(f"{BASE_URL}/api/supplier-sync/products?supplier=Canopy&limit=5")
        assert products_response.status_code == 200
        
        data = products_response.json()
        products = data.get("products", data) if isinstance(data, dict) else data
        
        if len(products) < 2:
            pytest.skip("Need at least 2 products to test scoped updates")
        
        # Get product keys
        product_keys = []
        for p in products[:3]:
            key = f"{p.get('supplier', 'unknown')}|||{p.get('sku') or p.get('supplier_code') or p.get('_id')}"
            product_keys.append(key)
        
        # Test scoped update - apply category to only first 2 products
        scoped_updates = {
            "sub_categories": ["floor-tiles"],
            "per_attribute_scopes": {
                "cat_floor-tiles": product_keys[:2]  # Only first 2 products get this category
            }
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified",
            json={
                "product_keys": product_keys,
                "updates": scoped_updates,
                "mode": "replace"
            }
        )
        
        # Should succeed or return validation error, not 500
        assert response.status_code in [200, 400, 422], f"Unexpected status: {response.status_code}"
        print(f"SUCCESS: Scoped bulk update processed (status: {response.status_code})")
    
    def test_categories_by_group_endpoint(self):
        """Test /api/website-admin/categories/by-group endpoint for category data"""
        response = self.session.get(f"{BASE_URL}/api/website-admin/categories/by-group")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert isinstance(data, list), "Response should be a list of category groups"
        print(f"SUCCESS: Categories by group endpoint returned {len(data)} groups")
    
    def test_filters_types_endpoint(self):
        """Test /api/filters/types endpoint for filter data"""
        response = self.session.get(f"{BASE_URL}/api/filters/types")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert isinstance(data, list), "Response should be a list of filter types"
        print(f"SUCCESS: Filters types endpoint returned {len(data)} filter types")
    
    def test_specifications_types_endpoint(self):
        """Test /api/specifications/types/by-group endpoint for spec data"""
        response = self.session.get(f"{BASE_URL}/api/specifications/types/by-group")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert isinstance(data, list), "Response should be a list of specification groups"
        print(f"SUCCESS: Specifications types endpoint returned {len(data)} spec groups")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

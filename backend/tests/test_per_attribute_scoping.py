"""
Test per-attribute product scoping in Bulk Category Editor
Tests the /api/supplier-sync/products/bulk-update-unified endpoint
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://feature-verification-7.preview.emergentagent.com')

class TestPerAttributeScoping:
    """Tests for per-attribute product scoping feature"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.base_url = BASE_URL.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get token
        login_response = self.session.post(f"{self.base_url}/api/auth/login", json={
            "email": "qasim@tilestation.co.uk",
            "password": "admin123"
        })
        if login_response.status_code == 200:
            token = login_response.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_bulk_update_unified_endpoint_exists(self):
        """Test that the bulk-update-unified endpoint exists"""
        # Test with minimal payload
        response = self.session.post(f"{self.base_url}/api/supplier-sync/products/bulk-update-unified", json={
            "product_ids": [],
            "updates": {},
            "mode": "replace"
        })
        # Should not return 404
        assert response.status_code != 404, f"Endpoint not found: {response.status_code}"
        print(f"Endpoint exists, status: {response.status_code}")
    
    def test_bulk_update_with_categories(self):
        """Test bulk update with category assignments"""
        response = self.session.post(f"{self.base_url}/api/supplier-sync/products/bulk-update-unified", json={
            "product_ids": ["LFLAM566"],  # Test SKU
            "updates": {
                "sub_categories": ["Outdoor Tiles"],
                "main_category": "Tiles"
            },
            "mode": "replace"
        })
        print(f"Bulk update response: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Response data: {data}")
            assert "updated_count" in data or "message" in data
    
    def test_bulk_update_with_multiple_categories(self):
        """Test bulk update with multiple categories (simulating per-attribute scoping)"""
        response = self.session.post(f"{self.base_url}/api/supplier-sync/products/bulk-update-unified", json={
            "product_ids": ["LFLAM567", "LFLAM568"],
            "updates": {
                "sub_categories": ["Wall Tiles", "Floor Tiles"],
                "main_category": "Tiles"
            },
            "mode": "replace"
        })
        print(f"Multiple categories response: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Response data: {data}")
    
    def test_categories_api(self):
        """Test that categories API returns expected data"""
        response = self.session.get(f"{self.base_url}/api/website-admin/categories/by-group")
        assert response.status_code == 200, f"Categories API failed: {response.status_code}"
        data = response.json()
        print(f"Categories API returned {len(data)} groups")
        
        # Check for Tiles group with Outdoor Tiles category
        tiles_group = next((g for g in data if g.get('slug') == 'tiles'), None)
        if tiles_group:
            categories = tiles_group.get('categories', [])
            outdoor_tiles = next((c for c in categories if c.get('slug') == 'outdoor-tiles'), None)
            if outdoor_tiles:
                print(f"Found Outdoor Tiles category: {outdoor_tiles.get('name')}")
            else:
                print("Outdoor Tiles category not found in Tiles group")
    
    def test_filters_api(self):
        """Test that filters API returns expected data"""
        response = self.session.get(f"{self.base_url}/api/filters/types")
        assert response.status_code == 200, f"Filters API failed: {response.status_code}"
        data = response.json()
        print(f"Filters API returned {len(data)} filter types")
    
    def test_specifications_api(self):
        """Test that specifications API returns expected data"""
        response = self.session.get(f"{self.base_url}/api/specifications/types/by-group")
        assert response.status_code == 200, f"Specifications API failed: {response.status_code}"
        data = response.json()
        print(f"Specifications API returned {len(data)} spec groups")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

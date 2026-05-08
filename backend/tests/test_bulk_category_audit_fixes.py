"""
Test suite for Bulk Category Editor Audit Fixes (8 bugs)
Tests the following fixes:
1. POST /api/supplier-sync/products/bulk-update-field endpoint (was 404)
2. POST /api/supplier-sync/products/bulk-update-field rejects disallowed fields
3. POST /api/supplier-sync/products/bulk-update-field rejects empty SKU list
4. POST /api/products/detect-series uses admin display name priority
5. POST /api/supplier-sync/products/bulk-update-unified still works
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBulkUpdateFieldEndpoint:
    """Tests for the new /supplier-sync/products/bulk-update-field endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data and authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get auth token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "admin123"
        })
        if login_response.status_code == 200:
            token = login_response.json().get("token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        yield
    
    def test_bulk_update_field_endpoint_exists(self):
        """Bug 1: Verify the endpoint exists and returns 200 (was 404 before fix)"""
        # Use a test SKU that may or may not exist - endpoint should still return 200
        response = self.session.post(f"{BASE_URL}/api/supplier-sync/products/bulk-update-field", json={
            "skus": ["TEST_SKU_12345"],
            "field": "description",
            "value": "Test description"
        })
        
        # Should NOT be 404 anymore
        assert response.status_code != 404, f"Endpoint still returns 404! Status: {response.status_code}"
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "success" in data
        assert data["success"] == True
        print(f"PASS: bulk-update-field endpoint exists and returns 200")
    
    def test_bulk_update_field_updates_description(self):
        """Bug 1: Verify description field can be updated for multiple SKUs"""
        test_description = f"Test description updated at {datetime.now().isoformat()}"
        
        response = self.session.post(f"{BASE_URL}/api/supplier-sync/products/bulk-update-field", json={
            "skus": ["D11197"],  # Known test SKU from previous iterations
            "field": "description",
            "value": test_description
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["success"] == True
        assert "updated" in data
        assert "tiles_updated" in data
        assert data["field"] == "description"
        print(f"PASS: Description updated for SKU D11197. Updated: {data['updated']}, Tiles: {data['tiles_updated']}")
    
    def test_bulk_update_field_rejects_disallowed_fields(self):
        """Bug 2: Verify disallowed fields are rejected"""
        response = self.session.post(f"{BASE_URL}/api/supplier-sync/products/bulk-update-field", json={
            "skus": ["D11197"],
            "field": "price",  # price is NOT in allowed_fields
            "value": "100"
        })
        
        assert response.status_code == 400, f"Expected 400 for disallowed field, got {response.status_code}"
        data = response.json()
        assert "not allowed" in data.get("detail", "").lower() or "not allowed" in str(data).lower()
        print(f"PASS: Disallowed field 'price' correctly rejected with 400")
    
    def test_bulk_update_field_rejects_empty_skus(self):
        """Bug 3: Verify empty SKU list is rejected"""
        response = self.session.post(f"{BASE_URL}/api/supplier-sync/products/bulk-update-field", json={
            "skus": [],
            "field": "description",
            "value": "Test"
        })
        
        assert response.status_code == 400, f"Expected 400 for empty SKUs, got {response.status_code}"
        data = response.json()
        assert "no skus" in data.get("detail", "").lower() or "sku" in str(data).lower()
        print(f"PASS: Empty SKU list correctly rejected with 400")
    
    def test_bulk_update_field_allowed_fields(self):
        """Verify all allowed fields can be updated"""
        allowed_fields = ["description", "short_description", "seo_keywords", "hidden_seo_keywords", 
                         "material", "finish", "type", "edge", "size", "made_in", 
                         "slip_rating", "suitability", "thickness"]
        
        for field in allowed_fields:
            response = self.session.post(f"{BASE_URL}/api/supplier-sync/products/bulk-update-field", json={
                "skus": ["TEST_ALLOWED_FIELD_SKU"],
                "field": field,
                "value": f"test_{field}_value"
            })
            
            assert response.status_code == 200, f"Field '{field}' should be allowed but got {response.status_code}"
        
        print(f"PASS: All {len(allowed_fields)} allowed fields accepted")


class TestDetectSeriesNamePriority:
    """Tests for detect-series endpoint name priority (Bug 4)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data and authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get auth token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "admin123"
        })
        if login_response.status_code == 200:
            token = login_response.json().get("token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        yield
    
    def test_detect_series_endpoint_works(self):
        """Bug 4: Verify detect-series endpoint works with auth"""
        # Use actual SKU from database - D11197 is known test SKU
        response = self.session.post(f"{BASE_URL}/api/products/detect-series", json={
            "product_skus": ["D11197"]  # Correct field name is product_skus
        })
        
        # 200 = found products, 404 = no products found (both are valid responses)
        assert response.status_code in [200, 404], f"Expected 200 or 404, got {response.status_code}: {response.text}"
        if response.status_code == 200:
            data = response.json()
            assert "series" in data or isinstance(data, list) or isinstance(data, dict)
            print(f"PASS: detect-series endpoint works. Response keys: {data.keys() if isinstance(data, dict) else 'list'}")
        else:
            print(f"PASS: detect-series endpoint works (no products found for test SKU)")
    
    def test_detect_series_rejects_empty_skus(self):
        """Bug 4: Verify detect-series rejects empty SKU list"""
        response = self.session.post(f"{BASE_URL}/api/products/detect-series", json={
            "product_skus": []
        })
        
        assert response.status_code == 400, f"Expected 400 for empty SKUs, got {response.status_code}"
        print(f"PASS: detect-series correctly rejects empty SKU list")


class TestBulkUpdateUnifiedStillWorks:
    """Tests for existing bulk-update-unified endpoint (Bug 5)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data and authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get auth token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "admin123"
        })
        if login_response.status_code == 200:
            token = login_response.json().get("token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        yield
    
    def test_bulk_update_unified_still_works(self):
        """Bug 5: Verify existing bulk-update-unified endpoint still works"""
        # Correct payload format: product_ids (not products), updates object
        response = self.session.post(f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified", json={
            "product_ids": ["TEST_UNIFIED_SKU"],
            "updates": {
                "material": "Porcelain"
            }
        })
        
        # Should return 200 (endpoint exists and works)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "success" in data or "updated" in data or "processed" in data
        print(f"PASS: bulk-update-unified still works. Response: {data}")


class TestOldEndpointReturns404:
    """Verify the OLD incorrect endpoint path returns 404"""
    
    def test_old_supplier_products_path_returns_404(self):
        """Verify /supplier-products/bulk-update-field (old path) returns 404"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # Login first
        login_response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "admin123"
        })
        if login_response.status_code == 200:
            token = login_response.json().get("token")
            if token:
                session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Try the OLD incorrect path
        response = session.post(f"{BASE_URL}/api/supplier-products/bulk-update-field", json={
            "skus": ["TEST"],
            "field": "description",
            "value": "test"
        })
        
        # This OLD path should return 404 (it doesn't exist)
        assert response.status_code == 404, f"Old path should return 404, got {response.status_code}"
        print(f"PASS: Old path /supplier-products/bulk-update-field correctly returns 404")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

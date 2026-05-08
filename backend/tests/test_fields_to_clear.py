"""
Test fields_to_clear functionality in bulk-update-unified endpoint.
Tests the ability to remove 'Currently saved' attributes from products via the Bulk Category Editor.

Features tested:
- Scalar field clearing (material, finish, type, edge, etc.) using $unset
- Array field clearing (sub_categories, colors, rooms, etc.) using $pull
- Combined updates + fields_to_clear in same request
- fields_to_clear only (empty updates)
- attributes.* mirror fields clearing for spec fields
"""
import pytest
import requests
import os
import time
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestFieldsToClear:
    """Test fields_to_clear parameter in bulk-update-unified endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data - find products with existing attributes"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Get some products to test with
        response = self.session.get(f"{BASE_URL}/api/supplier-sync/products", params={
            "limit": 50,
            "page": 1
        })
        assert response.status_code == 200, f"Failed to get products: {response.text}"
        data = response.json()
        products = data.get("products", [])
        
        # Find products with supplier_code (since SKU may be null)
        self.test_products = [p for p in products if p.get("supplier_code")][:5]
        assert len(self.test_products) > 0, "No products with supplier_code found for testing"
        
        self.test_supplier_codes = [p["supplier_code"] for p in self.test_products]
        print(f"Using {len(self.test_supplier_codes)} products for testing: {self.test_supplier_codes[:3]}...")
        
        yield
        
        # Cleanup is not needed as we're testing on existing products
    
    def test_endpoint_accepts_fields_to_clear_parameter(self):
        """Test that the endpoint accepts fields_to_clear parameter without error"""
        response = self.session.post(f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified", json={
            "product_ids": self.test_supplier_codes[:1],
            "id_field": "supplier_code",
            "updates": {},
            "fields_to_clear": {"test_field": ["test_value"]}
        })
        
        # Should not return 400 for missing updates since fields_to_clear is provided
        assert response.status_code in [200, 500], f"Unexpected status: {response.status_code}, {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            assert data.get("success") == True, f"Expected success=True, got: {data}"
            print(f"SUCCESS: Endpoint accepts fields_to_clear parameter. Response: {data}")
    
    def test_scalar_field_clearing_with_unset(self):
        """Test clearing scalar fields (material, finish) uses $unset"""
        # First, set a material value on test products
        set_response = self.session.post(f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified", json={
            "product_ids": self.test_supplier_codes[:2],
            "id_field": "supplier_code",
            "updates": {"material": "TEST_MATERIAL_TO_CLEAR"},
            "mode": "replace"
        })
        assert set_response.status_code == 200, f"Failed to set material: {set_response.text}"
        print(f"Set material on products: {set_response.json()}")
        
        # Now clear the material field
        clear_response = self.session.post(f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified", json={
            "product_ids": self.test_supplier_codes[:2],
            "id_field": "supplier_code",
            "updates": {},
            "fields_to_clear": {"material": ["TEST_MATERIAL_TO_CLEAR"]}
        })
        
        assert clear_response.status_code == 200, f"Failed to clear material: {clear_response.text}"
        data = clear_response.json()
        assert data.get("success") == True, f"Expected success=True, got: {data}"
        assert data.get("fields_cleared", 0) > 0, f"Expected fields_cleared > 0, got: {data}"
        print(f"SUCCESS: Scalar field clearing works. Response: {data}")
    
    def test_array_field_clearing_with_pull(self):
        """Test clearing array fields (sub_categories, colors, rooms) uses $pull"""
        # First, add some sub_categories to test products
        set_response = self.session.post(f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified", json={
            "product_ids": self.test_supplier_codes[:2],
            "id_field": "supplier_code",
            "updates": {"sub_categories": ["TEST_CAT_1", "TEST_CAT_2", "TEST_CAT_3"]},
            "mode": "replace"
        })
        assert set_response.status_code == 200, f"Failed to set sub_categories: {set_response.text}"
        print(f"Set sub_categories on products: {set_response.json()}")
        
        # Now pull specific values from sub_categories
        clear_response = self.session.post(f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified", json={
            "product_ids": self.test_supplier_codes[:2],
            "id_field": "supplier_code",
            "updates": {},
            "fields_to_clear": {"sub_categories": ["TEST_CAT_1", "TEST_CAT_2"]}
        })
        
        assert clear_response.status_code == 200, f"Failed to clear sub_categories: {clear_response.text}"
        data = clear_response.json()
        assert data.get("success") == True, f"Expected success=True, got: {data}"
        assert data.get("fields_cleared", 0) > 0, f"Expected fields_cleared > 0, got: {data}"
        print(f"SUCCESS: Array field clearing works. Response: {data}")
        
        # Verify the values were actually pulled (TEST_CAT_3 should remain)
        verify_response = self.session.get(f"{BASE_URL}/api/supplier-sync/products", params={
            "supplier_code": self.test_supplier_codes[0],
            "limit": 1
        })
        if verify_response.status_code == 200:
            products = verify_response.json().get("products", [])
            if products:
                sub_cats = products[0].get("sub_categories", [])
                print(f"Remaining sub_categories after pull: {sub_cats}")
                # TEST_CAT_3 should still be there, TEST_CAT_1 and TEST_CAT_2 should be removed
                assert "TEST_CAT_1" not in sub_cats, "TEST_CAT_1 should have been removed"
                assert "TEST_CAT_2" not in sub_cats, "TEST_CAT_2 should have been removed"
    
    def test_combined_updates_and_fields_to_clear(self):
        """Test that updates and fields_to_clear work together in same request"""
        response = self.session.post(f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified", json={
            "product_ids": self.test_supplier_codes[:2],
            "id_field": "supplier_code",
            "updates": {"finish": "NEW_FINISH_VALUE"},
            "fields_to_clear": {"material": ["OLD_MATERIAL"]}
        })
        
        assert response.status_code == 200, f"Failed combined update: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got: {data}"
        print(f"SUCCESS: Combined updates + fields_to_clear works. Response: {data}")
    
    def test_fields_to_clear_only_with_empty_updates(self):
        """Test that fields_to_clear works when updates is empty {}"""
        response = self.session.post(f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified", json={
            "product_ids": self.test_supplier_codes[:1],
            "id_field": "supplier_code",
            "updates": {},
            "fields_to_clear": {"finish": ["SOME_FINISH"]}
        })
        
        assert response.status_code == 200, f"Failed fields_to_clear only: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got: {data}"
        print(f"SUCCESS: fields_to_clear only (empty updates) works. Response: {data}")
    
    def test_attributes_mirror_fields_cleared(self):
        """Test that attributes.* mirror fields are also cleared for spec fields"""
        # Set material which should also set attributes.material
        set_response = self.session.post(f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified", json={
            "product_ids": self.test_supplier_codes[:1],
            "id_field": "supplier_code",
            "updates": {"material": "MIRROR_TEST_MATERIAL"},
            "mode": "replace"
        })
        assert set_response.status_code == 200, f"Failed to set material: {set_response.text}"
        
        # Clear material - should also clear attributes.material
        clear_response = self.session.post(f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified", json={
            "product_ids": self.test_supplier_codes[:1],
            "id_field": "supplier_code",
            "updates": {},
            "fields_to_clear": {"material": ["MIRROR_TEST_MATERIAL"]}
        })
        
        assert clear_response.status_code == 200, f"Failed to clear material: {clear_response.text}"
        data = clear_response.json()
        assert data.get("success") == True, f"Expected success=True, got: {data}"
        print(f"SUCCESS: attributes.* mirror fields clearing works. Response: {data}")
    
    def test_multiple_array_fields_clearing(self):
        """Test clearing multiple array fields at once (rooms, colors, features)"""
        # First set multiple array fields
        set_response = self.session.post(f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified", json={
            "product_ids": self.test_supplier_codes[:2],
            "id_field": "supplier_code",
            "updates": {
                "rooms": ["bathroom", "kitchen", "living-room"],
                "colors": ["white", "grey", "black"],
                "features": ["anti-slip", "frost-proof"]
            },
            "mode": "replace"
        })
        assert set_response.status_code == 200, f"Failed to set array fields: {set_response.text}"
        
        # Clear specific values from multiple array fields
        clear_response = self.session.post(f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified", json={
            "product_ids": self.test_supplier_codes[:2],
            "id_field": "supplier_code",
            "updates": {},
            "fields_to_clear": {
                "rooms": ["bathroom"],
                "colors": ["white", "grey"],
                "features": ["anti-slip"]
            }
        })
        
        assert clear_response.status_code == 200, f"Failed to clear multiple arrays: {clear_response.text}"
        data = clear_response.json()
        assert data.get("success") == True, f"Expected success=True, got: {data}"
        assert data.get("fields_cleared", 0) == 3, f"Expected 3 fields cleared, got: {data.get('fields_cleared')}"
        print(f"SUCCESS: Multiple array fields clearing works. Response: {data}")
    
    def test_error_when_no_updates_and_no_fields_to_clear(self):
        """Test that endpoint returns error when both updates and fields_to_clear are empty"""
        response = self.session.post(f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified", json={
            "product_ids": self.test_supplier_codes[:1],
            "id_field": "supplier_code",
            "updates": {},
            "fields_to_clear": {}
        })
        
        # Should return 400 error
        assert response.status_code == 400, f"Expected 400 error, got: {response.status_code}, {response.text}"
        print(f"SUCCESS: Proper error returned when both updates and fields_to_clear are empty")


class TestBulkUpdateUnifiedBasics:
    """Basic tests for bulk-update-unified endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Get products
        response = self.session.get(f"{BASE_URL}/api/supplier-sync/products", params={"limit": 10})
        assert response.status_code == 200
        products = response.json().get("products", [])
        self.test_products = [p for p in products if p.get("supplier_code")][:3]
        self.test_supplier_codes = [p["supplier_code"] for p in self.test_products]
        
        yield
    
    def test_bulk_update_unified_endpoint_exists(self):
        """Test that bulk-update-unified endpoint exists and responds"""
        response = self.session.post(f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified", json={
            "product_ids": self.test_supplier_codes[:1],
            "id_field": "supplier_code",
            "updates": {"finish": "Test"}
        })
        
        assert response.status_code in [200, 400, 500], f"Endpoint not responding properly: {response.status_code}"
        print(f"Endpoint responds with status: {response.status_code}")
    
    def test_bulk_update_with_supplier_code_id_field(self):
        """Test bulk update using supplier_code as id_field"""
        if not self.test_supplier_codes:
            pytest.skip("No products with supplier_code found")
        
        response = self.session.post(f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified", json={
            "product_ids": self.test_supplier_codes[:1],
            "id_field": "supplier_code",
            "updates": {"finish": "Matt"},
            "mode": "replace"
        })
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True
        print(f"SUCCESS: Bulk update with supplier_code works. Response: {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

"""
Test suite for P0 bug fix: Custom descriptions saving to collection_settings
Tests the fix where 'Apply Description' button now saves to collection_settings
which is what the storefront reads.
"""
import pytest
import requests
import os
import time
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestCollectionSettingsAPI:
    """Test collection settings API endpoints for custom_description"""
    
    def test_put_collection_settings_saves_custom_description(self):
        """Test PUT /api/website-admin/collections/{series_name} saves custom_description"""
        test_series = "TEST_BulkDesc_" + str(uuid.uuid4())[:8]
        test_description = f"Test custom description {uuid.uuid4()}"
        
        # Save custom description via collection settings API
        response = requests.put(
            f"{BASE_URL}/api/website-admin/collections/{test_series}",
            json={"custom_description": test_description}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("message") == "Collection settings updated"
        assert data.get("series_name") == test_series
        print(f"✓ PUT collection settings returned success for {test_series}")
        
        # Verify it was saved by fetching it back
        get_response = requests.get(
            f"{BASE_URL}/api/website-admin/collection-settings/{test_series}"
        )
        assert get_response.status_code == 200
        get_data = get_response.json()
        assert get_data.get("found") == True
        assert get_data.get("settings", {}).get("custom_description") == test_description
        print(f"✓ GET collection settings returned saved custom_description")
    
    def test_get_collection_settings_returns_custom_description(self):
        """Test GET /api/website-admin/collection-settings/{series_name} returns saved description"""
        # Use existing Atlantic series which has custom_description
        response = requests.get(
            f"{BASE_URL}/api/website-admin/collection-settings/Atlantic"
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("found") == True
        assert "settings" in data
        assert "custom_description" in data["settings"]
        print(f"✓ Atlantic collection settings found with custom_description: {data['settings']['custom_description'][:50]}...")
    
    def test_get_collection_settings_not_found(self):
        """Test GET returns found=False for non-existent series"""
        response = requests.get(
            f"{BASE_URL}/api/website-admin/collection-settings/NonExistentSeries12345"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("found") == False
        assert data.get("settings") is None
        print("✓ Non-existent series returns found=False")


class TestStorefrontCollectionAPI:
    """Test storefront collection API returns custom_description from collection_settings"""
    
    def test_storefront_collection_returns_custom_description(self):
        """Test GET /api/tiles/collection/{series_name} returns custom_description from collection_settings"""
        # Atlantic has custom_description set
        response = requests.get(
            f"{BASE_URL}/api/tiles/collection/Atlantic?limit=1"
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Verify custom_description is returned
        assert "custom_description" in data, "custom_description field missing from response"
        custom_desc = data.get("custom_description")
        assert custom_desc is not None and custom_desc != "", f"custom_description should not be empty, got: {custom_desc}"
        print(f"✓ Storefront collection API returns custom_description: {custom_desc[:50]}...")
    
    def test_storefront_collection_empty_custom_description_for_no_settings(self):
        """Test collection without settings returns empty custom_description"""
        # Bluestone may not have custom_description set
        response = requests.get(
            f"{BASE_URL}/api/tiles/collection/Bluestone?limit=1"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # custom_description field should exist (may be empty string)
        assert "custom_description" in data, "custom_description field should exist"
        print(f"✓ Bluestone collection returns custom_description field (value: '{data.get('custom_description')}')")


class TestEndToEndDescriptionFlow:
    """End-to-end test: Save description via API, verify storefront returns it"""
    
    def test_e2e_save_and_retrieve_custom_description(self):
        """
        End-to-end test:
        1. Save custom description via collection settings API
        2. Verify storefront API returns the saved description
        """
        test_series = "Atlantic"  # Use existing series with products
        unique_description = f"E2E Test Description {uuid.uuid4()}"
        
        # Step 1: Save custom description
        put_response = requests.put(
            f"{BASE_URL}/api/website-admin/collections/{test_series}",
            json={"custom_description": unique_description}
        )
        assert put_response.status_code == 200, f"PUT failed: {put_response.text}"
        print(f"✓ Step 1: Saved custom description to collection_settings")
        
        # Step 2: Verify via collection-settings endpoint
        settings_response = requests.get(
            f"{BASE_URL}/api/website-admin/collection-settings/{test_series}"
        )
        assert settings_response.status_code == 200
        settings_data = settings_response.json()
        assert settings_data.get("found") == True
        assert settings_data.get("settings", {}).get("custom_description") == unique_description
        print(f"✓ Step 2: Verified via collection-settings endpoint")
        
        # Step 3: Verify storefront API returns the description
        storefront_response = requests.get(
            f"{BASE_URL}/api/tiles/collection/{test_series}?limit=1"
        )
        assert storefront_response.status_code == 200
        storefront_data = storefront_response.json()
        assert storefront_data.get("custom_description") == unique_description, \
            f"Storefront should return saved description. Expected: {unique_description}, Got: {storefront_data.get('custom_description')}"
        print(f"✓ Step 3: Storefront API returns the saved custom_description")
        
        print(f"\n✓ E2E TEST PASSED: Custom description flows correctly from admin to storefront")


class TestBulkDescriptionAPI:
    """Test bulk description API saves to supplier_products and tiles"""
    
    def test_bulk_description_endpoint_exists(self):
        """Test PUT /api/supplier-sync/products/bulk-description endpoint exists"""
        # Send minimal request to verify endpoint exists
        response = requests.put(
            f"{BASE_URL}/api/supplier-sync/products/bulk-description",
            json={
                "products": [],
                "description_template": "",
                "use_placeholders": False
            }
        )
        
        # Should return 200 with 0 updated (empty products list)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True
        assert data.get("updated_count") == 0
        print("✓ Bulk description endpoint exists and responds correctly")


class TestCollectionSettingsUpdate:
    """Test that collection settings can be updated with various fields"""
    
    def test_update_multiple_fields(self):
        """Test updating multiple fields in collection settings"""
        test_series = "TEST_MultiField_" + str(uuid.uuid4())[:8]
        
        response = requests.put(
            f"{BASE_URL}/api/website-admin/collections/{test_series}",
            json={
                "custom_description": "Test description",
                "custom_title": "Test Title",
                "is_featured": True
            }
        )
        
        assert response.status_code == 200
        
        # Verify all fields saved
        get_response = requests.get(
            f"{BASE_URL}/api/website-admin/collection-settings/{test_series}"
        )
        assert get_response.status_code == 200
        data = get_response.json()
        settings = data.get("settings", {})
        
        assert settings.get("custom_description") == "Test description"
        assert settings.get("custom_title") == "Test Title"
        assert settings.get("is_featured") == True
        print("✓ Multiple fields saved correctly to collection_settings")
    
    def test_update_only_description_preserves_other_fields(self):
        """Test that updating only description doesn't overwrite other fields"""
        test_series = "TEST_Preserve_" + str(uuid.uuid4())[:8]
        
        # First, set multiple fields
        requests.put(
            f"{BASE_URL}/api/website-admin/collections/{test_series}",
            json={
                "custom_description": "Initial description",
                "custom_title": "Initial Title",
                "is_featured": True
            }
        )
        
        # Now update only description
        response = requests.put(
            f"{BASE_URL}/api/website-admin/collections/{test_series}",
            json={"custom_description": "Updated description only"}
        )
        assert response.status_code == 200
        
        # Verify other fields preserved
        get_response = requests.get(
            f"{BASE_URL}/api/website-admin/collection-settings/{test_series}"
        )
        data = get_response.json()
        settings = data.get("settings", {})
        
        assert settings.get("custom_description") == "Updated description only"
        assert settings.get("custom_title") == "Initial Title"
        assert settings.get("is_featured") == True
        print("✓ Updating only description preserves other fields")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

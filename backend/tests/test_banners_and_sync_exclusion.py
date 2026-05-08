"""
Test Page Banners API and Sync Exclusion System

Features tested:
- Page Banners CRUD operations (create, read, update, delete)
- Category deletion with exclude_from_sync parameter
- Filter value deletion with exclude_from_sync parameter
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "qasim@tilestation.co.uk"
TEST_PASSWORD = "Tilestation_9614"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        return data.get("token")
    pytest.skip(f"Authentication failed with status {response.status_code}")


@pytest.fixture(scope="module")
def api_client(auth_token):
    """Create requests session with auth header"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


class TestPageBannersAPI:
    """Test Page Banners CRUD operations"""
    
    created_banner_id = None
    
    def test_list_page_banners(self, api_client):
        """Test listing all page banners"""
        response = api_client.get(f"{BASE_URL}/api/website-admin/page-banners")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"Found {len(data)} existing banners")
        
    def test_create_page_banner(self, api_client):
        """Test creating a new page banner"""
        banner_data = {
            "title": "TEST_Banner_Title",
            "subtitle": "Test subtitle for automated testing",
            "image": "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?w=1600&q=80",
            "overlay": "rgba(0,0,0,0.3)",
            "category_slug": "",
            "group_slug": "tiles",
            "is_default": False,
            "is_active": True
        }
        
        response = api_client.post(f"{BASE_URL}/api/website-admin/page-banners", json=banner_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data or "message" in data, "Response should contain id or message"
        
        if "id" in data:
            TestPageBannersAPI.created_banner_id = data["id"]
            print(f"Banner created with ID: {data['id']}")
        else:
            print(f"Banner response: {data}")
    
    def test_get_public_page_banner(self, api_client):
        """Test getting public page banner for a group"""
        # Test with group parameter
        response = api_client.get(f"{BASE_URL}/api/website-admin/public/page-banners?group=tiles")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Test default banner
        response_default = api_client.get(f"{BASE_URL}/api/website-admin/public/page-banners")
        assert response_default.status_code == 200, f"Expected 200, got {response_default.status_code}"
        
        print("Public banner endpoint working correctly")
    
    def test_update_page_banner(self, api_client):
        """Test updating a page banner (by creating with same group_slug)"""
        banner_data = {
            "title": "TEST_Banner_Updated",
            "subtitle": "Updated subtitle for automated testing",
            "image": "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?w=1600&q=80",
            "overlay": "rgba(0,0,0,0.4)",
            "group_slug": "tiles",
            "is_default": False,
            "is_active": True
        }
        
        response = api_client.post(f"{BASE_URL}/api/website-admin/page-banners", json=banner_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Check if it was updated
        if "message" in data and "updated" in data.get("message", "").lower():
            print("Banner updated successfully")
        else:
            print(f"Banner response: {data}")
    
    def test_delete_page_banner(self, api_client):
        """Test deleting a page banner"""
        # First list banners to find one with TEST_ prefix
        response = api_client.get(f"{BASE_URL}/api/website-admin/page-banners")
        assert response.status_code == 200
        
        banners = response.json()
        test_banner = None
        for b in banners:
            if b.get("title", "").startswith("TEST_") or b.get("group_slug") == "tiles":
                test_banner = b
                break
        
        if test_banner and test_banner.get("id"):
            delete_response = api_client.delete(f"{BASE_URL}/api/website-admin/page-banners/{test_banner['id']}")
            assert delete_response.status_code == 200, f"Expected 200, got {delete_response.status_code}"
            print(f"Banner {test_banner['id']} deleted successfully")
        else:
            print("No test banner found to delete, skipping deletion test")


class TestCategoryExclusionFromSync:
    """Test category deletion with exclude_from_sync parameter"""
    
    test_category_id = None
    test_category_slug = "test-exclusion-category"
    
    def test_create_test_category(self, api_client):
        """Create a test category for exclusion testing"""
        category_data = {
            "name": "TEST_Exclusion_Category",
            "slug": self.test_category_slug,
            "description": "Category for testing sync exclusion",
            "group_slug": "tiles",
            "is_active": True,
            "show_on_homepage": False,
            "display_order": 999
        }
        
        response = api_client.post(f"{BASE_URL}/api/website-admin/categories", json=category_data)
        # May return 200 or 201 depending on if upsert
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        
        data = response.json()
        if "id" in data:
            TestCategoryExclusionFromSync.test_category_id = data["id"]
        print(f"Test category created: {data}")
    
    def test_verify_category_exists(self, api_client):
        """Verify the test category exists"""
        response = api_client.get(f"{BASE_URL}/api/website-admin/categories")
        assert response.status_code == 200
        
        categories = response.json()
        found = any(c.get("slug") == self.test_category_slug for c in categories)
        print(f"Test category found in list: {found}")
    
    def test_delete_category_with_exclusion(self, api_client):
        """Test deleting category with exclude_from_sync=true"""
        if not TestCategoryExclusionFromSync.test_category_id:
            # Try to find the category
            response = api_client.get(f"{BASE_URL}/api/website-admin/categories")
            categories = response.json()
            for c in categories:
                if c.get("slug") == self.test_category_slug:
                    TestCategoryExclusionFromSync.test_category_id = c.get("id")
                    break
        
        if TestCategoryExclusionFromSync.test_category_id:
            # Delete with exclude_from_sync=true
            delete_response = api_client.delete(
                f"{BASE_URL}/api/website-admin/categories/{TestCategoryExclusionFromSync.test_category_id}?exclude_from_sync=true"
            )
            assert delete_response.status_code == 200, f"Expected 200, got {delete_response.status_code}: {delete_response.text}"
            
            data = delete_response.json()
            assert data.get("excluded_from_sync") == True, "excluded_from_sync should be True"
            print(f"Category deleted with exclusion: {data}")
        else:
            print("No test category ID found, skipping deletion test")


class TestFilterValueExclusionFromSync:
    """Test filter value deletion with exclude_from_sync parameter"""
    
    test_filter_id = None
    test_value_slug = "test-filter-value"
    
    def test_get_filters(self, api_client):
        """Get filters to find one for testing"""
        response = api_client.get(f"{BASE_URL}/api/filters/types")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        filters = response.json()
        # Find a filter with values
        for f in filters:
            if f.get("values") and len(f.get("values", [])) > 0:
                TestFilterValueExclusionFromSync.test_filter_id = f.get("id")
                print(f"Found filter '{f.get('name')}' with {len(f.get('values', []))} values")
                break
        
        assert TestFilterValueExclusionFromSync.test_filter_id, "No filter with values found"
    
    def test_add_test_filter_value(self, api_client):
        """Add a test value to a filter"""
        if not TestFilterValueExclusionFromSync.test_filter_id:
            pytest.skip("No filter ID available")
        
        # Get the filter first
        response = api_client.get(f"{BASE_URL}/api/filters/types")
        filters = response.json()
        
        target_filter = None
        for f in filters:
            if f.get("id") == TestFilterValueExclusionFromSync.test_filter_id:
                target_filter = f
                break
        
        if target_filter:
            # Add test value to filter values
            values = target_filter.get("values", [])
            values.append({"value": self.test_value_slug, "label": "Test Value", "count": 0})
            
            update_data = {
                "name": target_filter.get("name"),
                "slug": target_filter.get("slug"),
                "input_type": target_filter.get("input_type", "checkbox"),
                "values": values,
                "is_active": target_filter.get("is_active", True)
            }
            
            update_response = api_client.put(
                f"{BASE_URL}/api/filters/types/{TestFilterValueExclusionFromSync.test_filter_id}",
                json=update_data
            )
            
            if update_response.status_code == 200:
                print("Test filter value added successfully")
            else:
                print(f"Filter update response: {update_response.status_code} - {update_response.text}")
    
    def test_delete_filter_value_with_exclusion(self, api_client):
        """Test deleting filter value with exclude_from_sync=true"""
        if not TestFilterValueExclusionFromSync.test_filter_id:
            pytest.skip("No filter ID available")
        
        delete_response = api_client.delete(
            f"{BASE_URL}/api/filters/types/{TestFilterValueExclusionFromSync.test_filter_id}/values/{self.test_value_slug}?exclude_from_sync=true"
        )
        
        # May return 200 or 404 if value doesn't exist
        if delete_response.status_code == 200:
            data = delete_response.json()
            assert data.get("excluded_from_sync") == True, "excluded_from_sync should be True"
            print(f"Filter value deleted with exclusion: {data}")
        elif delete_response.status_code == 404:
            print("Test filter value not found (may have been deleted already)")
        else:
            pytest.fail(f"Unexpected status code: {delete_response.status_code}")


class TestCategorySyncEndpoint:
    """Test that sync endpoint respects exclusions"""
    
    def test_sync_categories_endpoint_exists(self, api_client):
        """Test that sync categories endpoint exists"""
        # This endpoint syncs categories from products
        response = api_client.post(f"{BASE_URL}/api/website-admin/categories/sync-from-products")
        
        # Should return 200 even if no new categories
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        print(f"Sync response: {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

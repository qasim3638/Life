"""
Test Collection Custom Description Feature
Tests the custom_description field in Collection Manager (admin panel)
- GET /api/website-admin/collections returns custom_description
- PUT /api/website-admin/collections/{series_name} saves custom_description
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestCollectionDescription:
    """Tests for collection custom_description feature"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "admin123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        self.token = response.json()["token"]
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        yield
        # Cleanup: Clear test description
        requests.put(
            f"{BASE_URL}/api/website-admin/collections/Monaco%20Polished",
            headers=self.headers,
            json={"custom_description": ""}
        )
    
    def test_get_collections_returns_custom_description_field(self):
        """GET /api/website-admin/collections should return custom_description field"""
        response = requests.get(
            f"{BASE_URL}/api/website-admin/collections",
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert "collections" in data
        assert "total" in data
        assert len(data["collections"]) > 0
        
        # Check that custom_description field exists in collection objects
        first_collection = data["collections"][0]
        assert "custom_description" in first_collection, "custom_description field missing from collection"
        assert "series_name" in first_collection
        assert "product_count" in first_collection
    
    def test_put_collection_saves_custom_description(self):
        """PUT /api/website-admin/collections/{series_name} should save custom_description"""
        test_description = "TEST_PYTEST: This is a test description for Monaco Polished."
        
        # Save custom description
        response = requests.put(
            f"{BASE_URL}/api/website-admin/collections/Monaco%20Polished",
            headers=self.headers,
            json={"custom_description": test_description}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Collection settings updated"
        assert data["series_name"] == "Monaco Polished"
        
        # Verify persistence via GET
        get_response = requests.get(
            f"{BASE_URL}/api/website-admin/collections",
            headers=self.headers
        )
        assert get_response.status_code == 200
        
        collections = get_response.json()["collections"]
        monaco = next((c for c in collections if c["series_name"] == "Monaco Polished"), None)
        
        assert monaco is not None, "Monaco Polished collection not found"
        assert monaco["custom_description"] == test_description, \
            f"Expected '{test_description}', got '{monaco['custom_description']}'"
    
    def test_clear_custom_description(self):
        """PUT with empty string should clear custom_description"""
        # First set a description
        requests.put(
            f"{BASE_URL}/api/website-admin/collections/Monaco%20Polished",
            headers=self.headers,
            json={"custom_description": "Temporary description"}
        )
        
        # Clear the description
        response = requests.put(
            f"{BASE_URL}/api/website-admin/collections/Monaco%20Polished",
            headers=self.headers,
            json={"custom_description": ""}
        )
        
        assert response.status_code == 200
        
        # Verify it was cleared
        get_response = requests.get(
            f"{BASE_URL}/api/website-admin/collections",
            headers=self.headers
        )
        collections = get_response.json()["collections"]
        monaco = next((c for c in collections if c["series_name"] == "Monaco Polished"), None)
        
        assert monaco["custom_description"] == "", \
            f"Expected empty string, got '{monaco['custom_description']}'"
    
    def test_custom_description_does_not_affect_other_fields(self):
        """Updating custom_description should not affect other collection fields"""
        # Get initial state
        get_response = requests.get(
            f"{BASE_URL}/api/website-admin/collections",
            headers=self.headers
        )
        collections = get_response.json()["collections"]
        monaco_before = next((c for c in collections if c["series_name"] == "Monaco Polished"), None)
        
        # Update only custom_description
        requests.put(
            f"{BASE_URL}/api/website-admin/collections/Monaco%20Polished",
            headers=self.headers,
            json={"custom_description": "Test description"}
        )
        
        # Get updated state
        get_response = requests.get(
            f"{BASE_URL}/api/website-admin/collections",
            headers=self.headers
        )
        collections = get_response.json()["collections"]
        monaco_after = next((c for c in collections if c["series_name"] == "Monaco Polished"), None)
        
        # Verify other fields unchanged
        assert monaco_after["product_count"] == monaco_before["product_count"]
        assert monaco_after["is_featured"] == monaco_before["is_featured"]
        assert monaco_after["is_hidden"] == monaco_before["is_hidden"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
Test Collection Manager Bulk Description Feature
Tests:
1. GET /api/website-admin/collections - returns collections with custom_description
2. PUT /api/website-admin/collections/{series_name} - updates custom_description
3. Bulk description apply (multiple PUT requests)
4. Clear description (PUT with empty custom_description)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBulkDescriptionAPI:
    """Test Collection Manager Bulk Description API endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - login and get token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "admin123"
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip(f"Login failed: {login_response.status_code}")
    
    def test_01_get_collections_returns_custom_description(self):
        """Test GET /api/website-admin/collections returns custom_description field"""
        response = self.session.get(f"{BASE_URL}/api/website-admin/collections")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "collections" in data, "Response should have 'collections' key"
        assert len(data["collections"]) > 0, "Should have at least one collection"
        
        # Check that collections have the expected fields
        first_collection = data["collections"][0]
        assert "series_name" in first_collection, "Collection should have series_name"
        # custom_description may or may not exist, but the field should be supported
        print(f"Found {len(data['collections'])} collections")
        print(f"First collection: {first_collection.get('series_name')}")
        
    def test_02_put_collection_custom_description(self):
        """Test PUT /api/website-admin/collections/{series_name} with custom_description"""
        # First get a collection to update
        response = self.session.get(f"{BASE_URL}/api/website-admin/collections")
        assert response.status_code == 200
        
        collections = response.json().get("collections", [])
        assert len(collections) > 0, "Need at least one collection to test"
        
        # Use first collection for testing
        test_collection = collections[0]["series_name"]
        test_description = "TEST_BULK_DESC: This is a test description for bulk description feature"
        
        # Update the collection with custom_description
        put_response = self.session.put(
            f"{BASE_URL}/api/website-admin/collections/{requests.utils.quote(test_collection, safe='')}",
            json={"custom_description": test_description}
        )
        
        assert put_response.status_code == 200, f"Expected 200, got {put_response.status_code}: {put_response.text}"
        
        result = put_response.json()
        assert "message" in result, "Response should have message"
        print(f"Updated collection '{test_collection}' with description")
        
        # Verify the description was saved by fetching collections again
        verify_response = self.session.get(f"{BASE_URL}/api/website-admin/collections")
        assert verify_response.status_code == 200
        
        updated_collections = verify_response.json().get("collections", [])
        updated_collection = next((c for c in updated_collections if c["series_name"] == test_collection), None)
        
        assert updated_collection is not None, f"Collection '{test_collection}' not found"
        assert updated_collection.get("custom_description") == test_description, \
            f"Description not saved. Expected '{test_description}', got '{updated_collection.get('custom_description')}'"
        
        print(f"Verified description saved: {updated_collection.get('custom_description')[:50]}...")
        
    def test_03_bulk_apply_description_to_multiple_collections(self):
        """Test applying same description to multiple collections (simulating bulk apply)"""
        # Get collections
        response = self.session.get(f"{BASE_URL}/api/website-admin/collections")
        assert response.status_code == 200
        
        collections = response.json().get("collections", [])
        assert len(collections) >= 2, "Need at least 2 collections to test bulk apply"
        
        # Select first 2 collections for bulk update
        test_collections = [c["series_name"] for c in collections[:2]]
        bulk_description = "TEST_BULK_DESC: Bulk applied description for testing"
        
        success_count = 0
        for series_name in test_collections:
            put_response = self.session.put(
                f"{BASE_URL}/api/website-admin/collections/{requests.utils.quote(series_name, safe='')}",
                json={"custom_description": bulk_description}
            )
            if put_response.status_code == 200:
                success_count += 1
        
        assert success_count == len(test_collections), \
            f"Expected {len(test_collections)} successful updates, got {success_count}"
        
        # Verify all collections have the description
        verify_response = self.session.get(f"{BASE_URL}/api/website-admin/collections")
        updated_collections = verify_response.json().get("collections", [])
        
        for series_name in test_collections:
            collection = next((c for c in updated_collections if c["series_name"] == series_name), None)
            assert collection is not None, f"Collection '{series_name}' not found"
            assert collection.get("custom_description") == bulk_description, \
                f"Bulk description not applied to '{series_name}'"
        
        print(f"Successfully bulk applied description to {len(test_collections)} collections")
        
    def test_04_clear_description(self):
        """Test clearing description by sending empty string"""
        # Get collections
        response = self.session.get(f"{BASE_URL}/api/website-admin/collections")
        assert response.status_code == 200
        
        collections = response.json().get("collections", [])
        # Find a collection with a description to clear
        collection_with_desc = next(
            (c for c in collections if c.get("custom_description")), 
            collections[0] if collections else None
        )
        
        assert collection_with_desc is not None, "Need a collection to test clear"
        
        test_collection = collection_with_desc["series_name"]
        
        # First ensure it has a description
        self.session.put(
            f"{BASE_URL}/api/website-admin/collections/{requests.utils.quote(test_collection, safe='')}",
            json={"custom_description": "TEST_BULK_DESC: Temporary description to clear"}
        )
        
        # Now clear it
        clear_response = self.session.put(
            f"{BASE_URL}/api/website-admin/collections/{requests.utils.quote(test_collection, safe='')}",
            json={"custom_description": ""}
        )
        
        assert clear_response.status_code == 200, f"Expected 200, got {clear_response.status_code}"
        
        # Verify it's cleared
        verify_response = self.session.get(f"{BASE_URL}/api/website-admin/collections")
        updated_collections = verify_response.json().get("collections", [])
        
        updated_collection = next((c for c in updated_collections if c["series_name"] == test_collection), None)
        assert updated_collection is not None
        
        # Description should be empty or None
        desc = updated_collection.get("custom_description", "")
        assert desc == "" or desc is None, f"Description should be cleared, got '{desc}'"
        
        print(f"Successfully cleared description from '{test_collection}'")
        
    def test_05_cleanup_test_descriptions(self):
        """Cleanup - remove all TEST_BULK_DESC descriptions"""
        response = self.session.get(f"{BASE_URL}/api/website-admin/collections")
        if response.status_code != 200:
            return
            
        collections = response.json().get("collections", [])
        
        cleaned = 0
        for collection in collections:
            desc = collection.get("custom_description", "")
            if desc and "TEST_BULK_DESC" in desc:
                self.session.put(
                    f"{BASE_URL}/api/website-admin/collections/{requests.utils.quote(collection['series_name'], safe='')}",
                    json={"custom_description": ""}
                )
                cleaned += 1
        
        print(f"Cleaned up {cleaned} test descriptions")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

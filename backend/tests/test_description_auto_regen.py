"""
Test Suite for Schedule Description Regeneration Feature
Tests the auto-regeneration settings, series tracking, pending regenerations, and history APIs.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "qasim@tilestation.co.uk"
TEST_PASSWORD = "Tilestation_9614"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for admin user"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get headers with auth token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


class TestDescriptionRegenSettings:
    """Tests for GET/POST /api/products/description-regen/settings"""
    
    def test_get_settings_returns_defaults(self, auth_headers):
        """GET /api/products/description-regen/settings - Returns default settings"""
        response = requests.get(
            f"{BASE_URL}/api/products/description-regen/settings",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify default fields exist
        assert "enabled" in data
        assert "frequency_hours" in data
        assert "default_length" in data
        assert "default_seo_keywords" in data
        print(f"✓ Settings returned: enabled={data.get('enabled')}, frequency={data.get('frequency_hours')}h")
    
    def test_get_settings_requires_auth(self):
        """GET /api/products/description-regen/settings - Requires authentication"""
        response = requests.get(f"{BASE_URL}/api/products/description-regen/settings")
        
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Settings endpoint requires authentication")
    
    def test_save_settings_success(self, auth_headers):
        """POST /api/products/description-regen/settings - Save settings successfully"""
        settings = {
            "enabled": True,
            "frequency_hours": 12,
            "default_length": "standard",
            "default_seo_keywords": "tiles, porcelain, ceramic",
            "notify_on_regeneration": True
        }
        
        response = requests.post(
            f"{BASE_URL}/api/products/description-regen/settings",
            headers=auth_headers,
            json=settings
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True
        print("✓ Settings saved successfully")
        
        # Verify settings were saved by fetching them
        get_response = requests.get(
            f"{BASE_URL}/api/products/description-regen/settings",
            headers=auth_headers
        )
        
        assert get_response.status_code == 200
        saved_data = get_response.json()
        assert saved_data.get("enabled") == True
        assert saved_data.get("frequency_hours") == 12
        assert saved_data.get("default_length") == "standard"
        print("✓ Settings verified after save")
    
    def test_save_settings_requires_auth(self):
        """POST /api/products/description-regen/settings - Requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/products/description-regen/settings",
            json={"enabled": True}
        )
        
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Save settings requires authentication")


class TestTrackedSeries:
    """Tests for tracked series CRUD operations"""
    
    def test_get_tracked_series(self, auth_headers):
        """GET /api/products/description-regen/tracked-series - Returns tracked series list"""
        response = requests.get(
            f"{BASE_URL}/api/products/description-regen/tracked-series",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "success" in data
        assert "count" in data
        assert "series" in data
        assert isinstance(data["series"], list)
        print(f"✓ Tracked series returned: {data['count']} series")
    
    def test_track_series_success(self, auth_headers):
        """POST /api/products/description-regen/track-series - Add series to tracking"""
        # Use Burlington series which was mentioned as having 8 products
        response = requests.post(
            f"{BASE_URL}/api/products/description-regen/track-series",
            headers=auth_headers,
            json={
                "series_name": "Burlington",
                "auto_regenerate": True
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True
        assert "Burlington" in data.get("message", "")
        print(f"✓ Series tracked: {data.get('message')}")
    
    def test_track_series_nonexistent(self, auth_headers):
        """POST /api/products/description-regen/track-series - Returns 404 for nonexistent series"""
        response = requests.post(
            f"{BASE_URL}/api/products/description-regen/track-series",
            headers=auth_headers,
            json={
                "series_name": "NonExistentSeriesXYZ123",
                "auto_regenerate": True
            }
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print("✓ Returns 404 for nonexistent series")
    
    def test_track_series_requires_auth(self):
        """POST /api/products/description-regen/track-series - Requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/products/description-regen/track-series",
            json={"series_name": "Test", "auto_regenerate": True}
        )
        
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Track series requires authentication")
    
    def test_track_batch_series(self, auth_headers):
        """POST /api/products/description-regen/track-batch - Add multiple series at once"""
        response = requests.post(
            f"{BASE_URL}/api/products/description-regen/track-batch",
            headers=auth_headers,
            json={
                "series": [
                    {"series_name": "Burlington", "product_count": 8},
                ],
                "auto_regenerate": True
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True
        print(f"✓ Batch tracking: {data.get('message')}")
    
    def test_track_batch_empty_list(self, auth_headers):
        """POST /api/products/description-regen/track-batch - Returns 400 for empty list"""
        response = requests.post(
            f"{BASE_URL}/api/products/description-regen/track-batch",
            headers=auth_headers,
            json={
                "series": [],
                "auto_regenerate": True
            }
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        print("✓ Returns 400 for empty series list")
    
    def test_remove_tracked_series(self, auth_headers):
        """DELETE /api/products/description-regen/track-series/{series_name} - Remove series from tracking"""
        # First ensure Burlington is tracked
        requests.post(
            f"{BASE_URL}/api/products/description-regen/track-series",
            headers=auth_headers,
            json={"series_name": "Burlington", "auto_regenerate": True}
        )
        
        # Now remove it
        response = requests.delete(
            f"{BASE_URL}/api/products/description-regen/track-series/Burlington",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True
        print(f"✓ Series removed: {data.get('message')}")
    
    def test_remove_nonexistent_series(self, auth_headers):
        """DELETE /api/products/description-regen/track-series/{series_name} - Returns 404 for nonexistent"""
        response = requests.delete(
            f"{BASE_URL}/api/products/description-regen/track-series/NonExistentSeriesXYZ123",
            headers=auth_headers
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print("✓ Returns 404 for nonexistent series removal")


class TestPendingRegenerations:
    """Tests for pending regenerations endpoint"""
    
    def test_get_pending_regenerations(self, auth_headers):
        """GET /api/products/description-regen/pending - Returns pending series list"""
        # First add a series to track
        requests.post(
            f"{BASE_URL}/api/products/description-regen/track-series",
            headers=auth_headers,
            json={"series_name": "Burlington", "auto_regenerate": True}
        )
        
        response = requests.get(
            f"{BASE_URL}/api/products/description-regen/pending",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "success" in data
        assert "pending_series" in data
        assert isinstance(data["pending_series"], list)
        
        # Burlington should be pending since it was just added (never generated)
        pending_names = [s.get("series_name") for s in data["pending_series"]]
        print(f"✓ Pending regenerations: {len(data['pending_series'])} series")
        
        if "Burlington" in pending_names:
            burlington = next(s for s in data["pending_series"] if s.get("series_name") == "Burlington")
            print(f"  - Burlington: {burlington.get('total_products')} total, {burlington.get('new_products')} new")
    
    def test_pending_requires_auth(self):
        """GET /api/products/description-regen/pending - Requires authentication"""
        response = requests.get(f"{BASE_URL}/api/products/description-regen/pending")
        
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Pending endpoint requires authentication")


class TestRegenerationHistory:
    """Tests for regeneration history endpoint"""
    
    def test_get_history(self, auth_headers):
        """GET /api/products/description-regen/history - Returns history list"""
        response = requests.get(
            f"{BASE_URL}/api/products/description-regen/history",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "success" in data
        assert "count" in data
        assert "history" in data
        assert isinstance(data["history"], list)
        print(f"✓ History returned: {data['count']} entries")
    
    def test_history_requires_auth(self):
        """GET /api/products/description-regen/history - Requires authentication"""
        response = requests.get(f"{BASE_URL}/api/products/description-regen/history")
        
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ History endpoint requires authentication")


class TestRunNow:
    """Tests for manual regeneration trigger"""
    
    def test_run_now_success(self, auth_headers):
        """POST /api/products/description-regen/run-now - Triggers regeneration"""
        response = requests.post(
            f"{BASE_URL}/api/products/description-regen/run-now",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True
        assert "background" in data.get("message", "").lower()
        print(f"✓ Run now triggered: {data.get('message')}")
    
    def test_run_now_requires_auth(self):
        """POST /api/products/description-regen/run-now - Requires authentication"""
        response = requests.post(f"{BASE_URL}/api/products/description-regen/run-now")
        
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Run now requires authentication")


class TestCleanup:
    """Cleanup test data after tests"""
    
    def test_cleanup_tracked_series(self, auth_headers):
        """Clean up test data - remove Burlington from tracking"""
        # Try to remove Burlington if it exists
        response = requests.delete(
            f"{BASE_URL}/api/products/description-regen/track-series/Burlington",
            headers=auth_headers
        )
        
        # Either 200 (removed) or 404 (already removed) is acceptable
        assert response.status_code in [200, 404], f"Unexpected status: {response.status_code}"
        print("✓ Cleanup completed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

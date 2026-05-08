"""
Test Collection Detail Page Settings API
Tests the admin settings panel endpoints for controlling UI elements on public collection pages.
Features tested:
- GET /api/website-admin/collection-detail-settings (public, no auth)
- POST /api/website-admin/collection-detail-settings (requires auth)
- Trust badges, delivery estimate, share buttons, accordion sections, sticky mobile cart toggles
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "qasim@tilestation.co.uk"
ADMIN_PASSWORD = "Tilestation_9614"


class TestCollectionDetailSettingsAPI:
    """Test Collection Detail Page Settings API endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for admin user"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    
    # ============ GET ENDPOINT TESTS ============
    
    def test_get_settings_public_no_auth(self):
        """GET /api/website-admin/collection-detail-settings should work without auth"""
        response = requests.get(f"{BASE_URL}/api/website-admin/collection-detail-settings")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "settings" in data, "Response should contain 'settings' key"
        # Settings can be empty dict if not configured yet
        assert isinstance(data["settings"], dict), "Settings should be a dictionary"
    
    def test_get_settings_returns_empty_by_default(self):
        """GET should return empty settings if none configured"""
        response = requests.get(f"{BASE_URL}/api/website-admin/collection-detail-settings")
        
        assert response.status_code == 200
        data = response.json()
        # Initially settings may be empty or have saved values
        assert "settings" in data
    
    # ============ POST ENDPOINT TESTS ============
    
    def test_post_settings_requires_no_auth_check(self, auth_headers):
        """POST /api/website-admin/collection-detail-settings - test saving settings"""
        # Note: Based on code review, POST endpoint doesn't require auth (no Depends(get_current_user))
        # This is a potential security issue but we test current behavior
        
        test_settings = {
            "trustBadges": {
                "enabled": True,
                "badges": [
                    {"id": "delivery", "enabled": True, "title": "Free Delivery", "subtitle": "Over £299"}
                ]
            },
            "deliveryEstimate": {
                "enabled": True,
                "showCountdown": True,
                "freeDeliveryThreshold": 299
            },
            "shareButtons": {
                "enabled": True,
                "platforms": {
                    "facebook": True,
                    "twitter": True,
                    "whatsapp": True
                }
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/website-admin/collection-detail-settings",
            json={"settings": test_settings},
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "message" in data, "Response should contain success message"
        assert "settings" in data, "Response should return saved settings"
    
    def test_save_and_retrieve_trust_badges_disabled(self, auth_headers):
        """Test saving trust badges as disabled and verifying retrieval"""
        # Save settings with trust badges disabled
        test_settings = {
            "trustBadges": {
                "enabled": False,
                "badges": []
            }
        }
        
        save_response = requests.post(
            f"{BASE_URL}/api/website-admin/collection-detail-settings",
            json={"settings": test_settings},
            headers=auth_headers
        )
        assert save_response.status_code == 200, f"Save failed: {save_response.text}"
        
        # Retrieve and verify
        get_response = requests.get(f"{BASE_URL}/api/website-admin/collection-detail-settings")
        assert get_response.status_code == 200
        
        data = get_response.json()
        assert data["settings"].get("trustBadges", {}).get("enabled") == False, \
            "Trust badges should be disabled after save"
    
    def test_save_and_retrieve_delivery_estimate_disabled(self, auth_headers):
        """Test saving delivery estimate as disabled and verifying retrieval"""
        test_settings = {
            "deliveryEstimate": {
                "enabled": False,
                "showCountdown": False
            }
        }
        
        save_response = requests.post(
            f"{BASE_URL}/api/website-admin/collection-detail-settings",
            json={"settings": test_settings},
            headers=auth_headers
        )
        assert save_response.status_code == 200
        
        get_response = requests.get(f"{BASE_URL}/api/website-admin/collection-detail-settings")
        assert get_response.status_code == 200
        
        data = get_response.json()
        assert data["settings"].get("deliveryEstimate", {}).get("enabled") == False, \
            "Delivery estimate should be disabled after save"
    
    def test_save_and_retrieve_share_buttons_disabled(self, auth_headers):
        """Test saving share buttons as disabled and verifying retrieval"""
        test_settings = {
            "shareButtons": {
                "enabled": False,
                "platforms": {}
            }
        }
        
        save_response = requests.post(
            f"{BASE_URL}/api/website-admin/collection-detail-settings",
            json={"settings": test_settings},
            headers=auth_headers
        )
        assert save_response.status_code == 200
        
        get_response = requests.get(f"{BASE_URL}/api/website-admin/collection-detail-settings")
        assert get_response.status_code == 200
        
        data = get_response.json()
        assert data["settings"].get("shareButtons", {}).get("enabled") == False, \
            "Share buttons should be disabled after save"
    
    def test_save_and_retrieve_accordion_sections_disabled(self, auth_headers):
        """Test saving accordion sections as disabled"""
        test_settings = {
            "accordionSections": {
                "enabled": False,
                "sections": {}
            }
        }
        
        save_response = requests.post(
            f"{BASE_URL}/api/website-admin/collection-detail-settings",
            json={"settings": test_settings},
            headers=auth_headers
        )
        assert save_response.status_code == 200
        
        get_response = requests.get(f"{BASE_URL}/api/website-admin/collection-detail-settings")
        assert get_response.status_code == 200
        
        data = get_response.json()
        assert data["settings"].get("accordionSections", {}).get("enabled") == False
    
    def test_save_and_retrieve_sticky_mobile_cart_disabled(self, auth_headers):
        """Test saving sticky mobile cart as disabled"""
        test_settings = {
            "stickyMobileCart": {
                "enabled": False,
                "showPrice": False,
                "showTotal": False
            }
        }
        
        save_response = requests.post(
            f"{BASE_URL}/api/website-admin/collection-detail-settings",
            json={"settings": test_settings},
            headers=auth_headers
        )
        assert save_response.status_code == 200
        
        get_response = requests.get(f"{BASE_URL}/api/website-admin/collection-detail-settings")
        assert get_response.status_code == 200
        
        data = get_response.json()
        assert data["settings"].get("stickyMobileCart", {}).get("enabled") == False
    
    def test_save_and_retrieve_frequently_bought_together_disabled(self, auth_headers):
        """Test saving frequently bought together as disabled"""
        test_settings = {
            "frequentlyBoughtTogether": {
                "enabled": False,
                "title": "Frequently Bought Together",
                "subtitle": "Complete your project"
            }
        }
        
        save_response = requests.post(
            f"{BASE_URL}/api/website-admin/collection-detail-settings",
            json={"settings": test_settings},
            headers=auth_headers
        )
        assert save_response.status_code == 200
        
        get_response = requests.get(f"{BASE_URL}/api/website-admin/collection-detail-settings")
        assert get_response.status_code == 200
        
        data = get_response.json()
        assert data["settings"].get("frequentlyBoughtTogether", {}).get("enabled") == False
    
    def test_save_complete_settings_object(self, auth_headers):
        """Test saving a complete settings object with all features enabled"""
        complete_settings = {
            "trustBadges": {
                "enabled": True,
                "badges": [
                    {"id": "delivery", "enabled": True, "title": "Free Delivery", "subtitle": "Over £299", "icon": "truck", "color": "amber"},
                    {"id": "samples", "enabled": True, "title": "Free Samples", "subtitle": "Try before you buy", "icon": "scissors", "color": "green"},
                    {"id": "quality", "enabled": True, "title": "Quality Guaranteed", "subtitle": "Premium tiles only", "icon": "shield", "color": "blue"},
                    {"id": "secure", "enabled": True, "title": "Secure Payment", "subtitle": "100% protected", "icon": "check", "color": "purple"}
                ]
            },
            "deliveryEstimate": {
                "enabled": True,
                "showCountdown": True,
                "cutoffHour": 14,
                "freeDeliveryThreshold": 299,
                "standardDays": "2-3",
                "expressDays": "Next day"
            },
            "shareButtons": {
                "enabled": True,
                "platforms": {
                    "facebook": True,
                    "twitter": True,
                    "whatsapp": True,
                    "pinterest": True,
                    "email": True,
                    "copyLink": True
                }
            },
            "frequentlyBoughtTogether": {
                "enabled": True,
                "title": "Frequently Bought Together",
                "subtitle": "Complete your project with these essential accessories",
                "showBundleTotal": True
            },
            "accordionSections": {
                "enabled": True,
                "sections": {
                    "specifications": {"enabled": True, "defaultOpen": True, "title": "Technical Specifications"},
                    "installation": {"enabled": True, "defaultOpen": False, "title": "Installation Guide"},
                    "maintenance": {"enabled": True, "defaultOpen": False, "title": "Maintenance Tips"}
                }
            },
            "stickyMobileCart": {
                "enabled": True,
                "showPrice": True,
                "showTotal": True
            }
        }
        
        save_response = requests.post(
            f"{BASE_URL}/api/website-admin/collection-detail-settings",
            json={"settings": complete_settings},
            headers=auth_headers
        )
        assert save_response.status_code == 200, f"Save failed: {save_response.text}"
        
        # Verify all settings were saved
        get_response = requests.get(f"{BASE_URL}/api/website-admin/collection-detail-settings")
        assert get_response.status_code == 200
        
        data = get_response.json()
        saved_settings = data["settings"]
        
        # Verify each section
        assert saved_settings.get("trustBadges", {}).get("enabled") == True
        assert saved_settings.get("deliveryEstimate", {}).get("enabled") == True
        assert saved_settings.get("shareButtons", {}).get("enabled") == True
        assert saved_settings.get("frequentlyBoughtTogether", {}).get("enabled") == True
        assert saved_settings.get("accordionSections", {}).get("enabled") == True
        assert saved_settings.get("stickyMobileCart", {}).get("enabled") == True
        
        print("All settings saved and retrieved successfully!")


class TestCollectionPageLoads:
    """Test that collection detail pages load correctly"""
    
    def test_collection_api_returns_products(self):
        """Test that collection API returns products for a valid series"""
        # Try to find a valid series name
        response = requests.get(f"{BASE_URL}/api/tiles/series?limit=5")
        
        if response.status_code == 200:
            data = response.json()
            series_list = data.get("series", [])
            
            if series_list:
                # Get first series name
                series_name = series_list[0].get("series_name") or series_list[0].get("name")
                if series_name:
                    # Test collection endpoint
                    collection_response = requests.get(
                        f"{BASE_URL}/api/tiles/collection/{series_name}?limit=10"
                    )
                    assert collection_response.status_code == 200, \
                        f"Collection API failed: {collection_response.status_code}"
                    
                    collection_data = collection_response.json()
                    assert "products" in collection_data, "Response should contain products"
                    print(f"Collection '{series_name}' has {len(collection_data.get('products', []))} products")
    
    def test_settings_endpoint_accessible_from_frontend(self):
        """Verify settings endpoint is accessible (simulating frontend fetch)"""
        response = requests.get(
            f"{BASE_URL}/api/website-admin/collection-detail-settings",
            headers={"Accept": "application/json"}
        )
        
        assert response.status_code == 200
        assert response.headers.get("content-type", "").startswith("application/json")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

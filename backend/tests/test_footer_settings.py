"""
Test Footer Settings API - Tests for GET/POST /api/website-admin/footer-settings
This tests the new Footer Management feature in the Homepage Manager admin panel.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestFooterSettingsAPI:
    """Test footer settings endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Get auth token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "admin123"
        })
        if login_response.status_code == 200:
            token = login_response.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        yield
    
    def test_get_footer_settings_returns_200(self):
        """GET /api/website-admin/footer-settings should return 200"""
        response = self.session.get(f"{BASE_URL}/api/website-admin/footer-settings")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "settings" in data, "Response should contain 'settings' key"
        print(f"GET footer-settings returned: {data}")
    
    def test_get_footer_settings_initially_empty_or_has_data(self):
        """GET /api/website-admin/footer-settings returns empty settings or existing data"""
        response = self.session.get(f"{BASE_URL}/api/website-admin/footer-settings")
        assert response.status_code == 200
        data = response.json()
        # Settings can be empty {} or have data
        assert isinstance(data.get("settings"), dict), "settings should be a dict"
        print(f"Initial footer settings: {data['settings']}")
    
    def test_post_footer_settings_saves_data(self):
        """POST /api/website-admin/footer-settings should save footer data"""
        test_footer = {
            "description": "TEST: Premium quality tiles for your home.",
            "phone": "01234 567890",
            "email": "test@tilestation.co.uk",
            "quickLinks": [
                {"text": "All Tiles", "url": "/tiles"},
                {"text": "Wall Tiles", "url": "/tiles?type=wall"},
            ],
            "customerServiceLinks": [
                {"text": "Delivery Info", "url": "/shop/delivery"},
                {"text": "Returns", "url": "/shop/returns"},
            ],
            "showrooms": [
                {"name": "Test Showroom", "hours": "Open 7 days"},
            ],
            "copyrightText": "TEST Tile Station Ltd. All rights reserved.",
            "legalLinks": [
                {"text": "Privacy Policy", "url": "/shop/privacy"},
            ],
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/website-admin/footer-settings",
            json={"settings": test_footer}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "message" in data, "Response should contain success message"
        print(f"POST footer-settings response: {data}")
    
    def test_get_footer_settings_returns_saved_data(self):
        """GET /api/website-admin/footer-settings should return previously saved data"""
        # First save some data
        test_footer = {
            "description": "VERIFY: This description was saved.",
            "phone": "09876 543210",
            "email": "verify@test.com",
            "quickLinks": [{"text": "Test Link", "url": "/test"}],
            "customerServiceLinks": [{"text": "Help", "url": "/help"}],
            "showrooms": [{"name": "Verify Showroom", "hours": "Mon-Fri"}],
            "copyrightText": "VERIFY Copyright Text",
            "legalLinks": [{"text": "Terms", "url": "/terms"}],
        }
        
        # Save
        save_response = self.session.post(
            f"{BASE_URL}/api/website-admin/footer-settings",
            json={"settings": test_footer}
        )
        assert save_response.status_code == 200
        
        # Retrieve and verify
        get_response = self.session.get(f"{BASE_URL}/api/website-admin/footer-settings")
        assert get_response.status_code == 200
        data = get_response.json()
        settings = data.get("settings", {})
        
        # Verify saved data
        assert settings.get("description") == test_footer["description"], "Description should match"
        assert settings.get("phone") == test_footer["phone"], "Phone should match"
        assert settings.get("email") == test_footer["email"], "Email should match"
        assert settings.get("copyrightText") == test_footer["copyrightText"], "Copyright should match"
        assert len(settings.get("quickLinks", [])) == 1, "Should have 1 quick link"
        assert len(settings.get("customerServiceLinks", [])) == 1, "Should have 1 customer service link"
        assert len(settings.get("showrooms", [])) == 1, "Should have 1 showroom"
        assert len(settings.get("legalLinks", [])) == 1, "Should have 1 legal link"
        print(f"Verified saved footer settings: {settings}")
    
    def test_footer_settings_public_access(self):
        """GET /api/website-admin/footer-settings should work without auth (public)"""
        # Create a new session without auth
        public_session = requests.Session()
        response = public_session.get(f"{BASE_URL}/api/website-admin/footer-settings")
        assert response.status_code == 200, f"Public GET should return 200, got {response.status_code}"
        data = response.json()
        assert "settings" in data
        print(f"Public access footer settings: {data}")
    
    def test_post_footer_settings_with_all_fields(self):
        """POST /api/website-admin/footer-settings with complete footer data"""
        complete_footer = {
            "description": "Complete test: Premium quality tiles for your home. Visit our showrooms.",
            "phone": "01732 424242",
            "email": "info@tilestation.co.uk",
            "quickLinks": [
                {"text": "All Tiles", "url": "/tiles"},
                {"text": "Wall Tiles", "url": "/tiles?type=wall"},
                {"text": "Floor Tiles", "url": "/tiles?type=floor"},
                {"text": "Store Locations", "url": "/shop/stores"},
                {"text": "Trade Accounts", "url": "/shop/trade/register"},
            ],
            "customerServiceLinks": [
                {"text": "Delivery Information", "url": "/shop/delivery"},
                {"text": "Returns & Refunds", "url": "/shop/returns"},
                {"text": "FAQs", "url": "/shop/faq"},
                {"text": "Contact Us", "url": "/shop/contact"},
                {"text": "Track Order", "url": "/shop/track"},
            ],
            "showrooms": [
                {"name": "Tonbridge", "hours": "Open 7 days a week"},
                {"name": "Gravesend", "hours": "Open 7 days a week"},
                {"name": "Chingford", "hours": "Open 7 days a week"},
            ],
            "copyrightText": "Tile Station Ltd. All rights reserved.",
            "legalLinks": [
                {"text": "Privacy Policy", "url": "/shop/privacy"},
                {"text": "Terms & Conditions", "url": "/shop/terms"},
            ],
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/website-admin/footer-settings",
            json={"settings": complete_footer}
        )
        assert response.status_code == 200
        
        # Verify all fields saved
        get_response = self.session.get(f"{BASE_URL}/api/website-admin/footer-settings")
        assert get_response.status_code == 200
        settings = get_response.json().get("settings", {})
        
        assert len(settings.get("quickLinks", [])) == 5, "Should have 5 quick links"
        assert len(settings.get("customerServiceLinks", [])) == 5, "Should have 5 customer service links"
        assert len(settings.get("showrooms", [])) == 3, "Should have 3 showrooms"
        assert len(settings.get("legalLinks", [])) == 2, "Should have 2 legal links"
        print(f"Complete footer saved and verified: {len(settings)} fields")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

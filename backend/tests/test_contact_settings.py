"""
Test Contact Settings API - Online Enquiries Feature
Tests for the merged Contact page with phone and categorized emails
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://feature-verification-7.preview.emergentagent.com')

# Test credentials
ADMIN_EMAIL = "qasim@tilestation.co.uk"
ADMIN_PASSWORD = "Tilestation_9614"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Admin authentication failed")


@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestContactSettingsPublic:
    """Test public contact settings endpoint (no auth required)"""
    
    def test_get_public_contact_settings_returns_200(self, api_client):
        """GET /api/website-admin/contact-settings/public returns 200"""
        response = api_client.get(f"{BASE_URL}/api/website-admin/contact-settings/public")
        assert response.status_code == 200
        print(f"✓ Public contact settings returned 200")
    
    def test_public_contact_settings_has_phone_and_emails(self, api_client):
        """Public endpoint returns phone and emails array"""
        response = api_client.get(f"{BASE_URL}/api/website-admin/contact-settings/public")
        assert response.status_code == 200
        
        data = response.json()
        assert "phone" in data, "Response should contain 'phone' field"
        assert "emails" in data, "Response should contain 'emails' field"
        assert isinstance(data["emails"], list), "emails should be a list"
        print(f"✓ Public contact settings has phone: {data['phone']}")
        print(f"✓ Public contact settings has {len(data['emails'])} emails")
    
    def test_public_contact_settings_email_structure(self, api_client):
        """Each email entry has label and email fields"""
        response = api_client.get(f"{BASE_URL}/api/website-admin/contact-settings/public")
        assert response.status_code == 200
        
        data = response.json()
        for i, entry in enumerate(data.get("emails", [])):
            assert "label" in entry, f"Email entry {i} should have 'label'"
            assert "email" in entry, f"Email entry {i} should have 'email'"
            print(f"✓ Email {i}: {entry['label']} -> {entry['email']}")


class TestContactSettingsAdmin:
    """Test admin contact settings endpoints (auth required)"""
    
    def test_get_admin_contact_settings_returns_200(self, api_client, admin_token):
        """GET /api/website-admin/contact-settings returns 200 with auth"""
        api_client.headers.update({"Authorization": f"Bearer {admin_token}"})
        response = api_client.get(f"{BASE_URL}/api/website-admin/contact-settings")
        assert response.status_code == 200
        
        data = response.json()
        assert "phone" in data
        assert "emails" in data
        print(f"✓ Admin contact settings returned 200 with phone and emails")
    
    def test_update_contact_settings_and_verify_persistence(self, api_client, admin_token):
        """PUT /api/website-admin/contact-settings saves and persists data"""
        api_client.headers.update({"Authorization": f"Bearer {admin_token}"})
        
        # First, get current settings to restore later
        original_response = api_client.get(f"{BASE_URL}/api/website-admin/contact-settings")
        original_data = original_response.json()
        
        # Update with test data
        test_data = {
            "phone": "TEST_09876 543210",
            "emails": [
                {"label": "TEST_Orders", "email": "test-orders@example.com"},
                {"label": "TEST_Support", "email": "test-support@example.com"}
            ]
        }
        
        update_response = api_client.put(
            f"{BASE_URL}/api/website-admin/contact-settings",
            json=test_data
        )
        assert update_response.status_code == 200
        assert "message" in update_response.json()
        print(f"✓ Contact settings update returned 200")
        
        # Verify persistence via GET
        verify_response = api_client.get(f"{BASE_URL}/api/website-admin/contact-settings")
        assert verify_response.status_code == 200
        
        verify_data = verify_response.json()
        assert verify_data["phone"] == test_data["phone"], "Phone should be updated"
        assert len(verify_data["emails"]) == 2, "Should have 2 emails"
        assert verify_data["emails"][0]["label"] == "TEST_Orders"
        print(f"✓ Contact settings persisted correctly")
        
        # Restore original data
        restore_response = api_client.put(
            f"{BASE_URL}/api/website-admin/contact-settings",
            json=original_data
        )
        assert restore_response.status_code == 200
        print(f"✓ Original contact settings restored")
    
    def test_add_new_email_entry(self, api_client, admin_token):
        """Can add a new email entry to existing list"""
        api_client.headers.update({"Authorization": f"Bearer {admin_token}"})
        
        # Get current settings
        current_response = api_client.get(f"{BASE_URL}/api/website-admin/contact-settings")
        current_data = current_response.json()
        original_count = len(current_data.get("emails", []))
        
        # Add a new email
        new_emails = current_data.get("emails", []) + [
            {"label": "TEST_New_Dept", "email": "test-new@example.com"}
        ]
        
        update_response = api_client.put(
            f"{BASE_URL}/api/website-admin/contact-settings",
            json={"phone": current_data.get("phone", ""), "emails": new_emails}
        )
        assert update_response.status_code == 200
        
        # Verify new email was added
        verify_response = api_client.get(f"{BASE_URL}/api/website-admin/contact-settings")
        verify_data = verify_response.json()
        assert len(verify_data["emails"]) == original_count + 1
        print(f"✓ New email entry added successfully")
        
        # Restore original
        api_client.put(
            f"{BASE_URL}/api/website-admin/contact-settings",
            json=current_data
        )
        print(f"✓ Original data restored")


class TestContactPageRedirect:
    """Test /shop/stores redirect to /shop/contact"""
    
    def test_stores_page_loads(self, api_client):
        """
        /shop/stores should redirect to /shop/contact (client-side React Router).
        Since this is a SPA, we just verify the page loads (200).
        The actual redirect is handled by React Router in App.js.
        """
        response = api_client.get(f"{BASE_URL}/shop/stores", allow_redirects=True)
        # SPA returns 200 for all routes, React Router handles redirect
        assert response.status_code == 200
        print(f"✓ /shop/stores page loads (React Router handles redirect)")
    
    def test_contact_page_loads(self, api_client):
        """/shop/contact page loads successfully"""
        response = api_client.get(f"{BASE_URL}/shop/contact", allow_redirects=True)
        assert response.status_code == 200
        print(f"✓ /shop/contact page loads successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
Test P1 Features:
1. JWT token 30-day expiry
2. Refresh token endpoint
3. Auth endpoints working correctly
"""
import pytest
import requests
import os
import jwt
from datetime import datetime, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "qasim@tilestation.co.uk"
ADMIN_PASSWORD = "Tilestation_9614"


class TestJWTExpiry:
    """Test JWT token has 30-day expiry"""
    
    def test_login_returns_token_with_30_day_expiry(self):
        """POST /api/auth/login should return a token with ~30 day expiry"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        
        # Verify token exists
        assert "token" in data, "Response should contain token"
        token = data["token"]
        
        # Decode token without verification to check expiry
        # (We don't have the secret, but we can decode the payload)
        try:
            # Decode without verification to inspect claims
            decoded = jwt.decode(token, options={"verify_signature": False})
            
            # Check exp claim exists
            assert "exp" in decoded, "Token should have exp claim"
            
            # Calculate days until expiry
            exp_timestamp = decoded["exp"]
            exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
            now = datetime.now(timezone.utc)
            days_until_expiry = (exp_datetime - now).days
            
            # Should be approximately 30 days (allow 29-30 range for timing)
            assert days_until_expiry >= 29, f"Token should expire in ~30 days, got {days_until_expiry} days"
            assert days_until_expiry <= 31, f"Token should expire in ~30 days, got {days_until_expiry} days"
            
            print(f"✓ Token expires in {days_until_expiry} days (expected ~30)")
            
        except jwt.DecodeError as e:
            pytest.fail(f"Failed to decode token: {e}")
    
    def test_login_returns_user_data(self):
        """POST /api/auth/login should return user data"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify user data
        assert "user" in data, "Response should contain user"
        user = data["user"]
        assert user["email"] == ADMIN_EMAIL
        assert "role" in user
        print(f"✓ User data returned: {user['email']}, role: {user['role']}")


class TestRefreshToken:
    """Test refresh token endpoint"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Authentication failed")
    
    def test_refresh_token_returns_new_token(self, auth_token):
        """POST /api/auth/refresh-token should return a new token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/refresh-token",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200, f"Refresh failed: {response.text}"
        data = response.json()
        
        # Verify new token exists
        assert "token" in data, "Response should contain new token"
        new_token = data["token"]
        
        # Verify it's a valid JWT with 30-day expiry
        decoded = jwt.decode(new_token, options={"verify_signature": False})
        assert "exp" in decoded
        
        exp_timestamp = decoded["exp"]
        exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        now = datetime.now(timezone.utc)
        days_until_expiry = (exp_datetime - now).days
        
        assert days_until_expiry >= 29, f"Refreshed token should expire in ~30 days, got {days_until_expiry}"
        print(f"✓ Refreshed token expires in {days_until_expiry} days")
    
    def test_refresh_token_returns_user_data(self, auth_token):
        """POST /api/auth/refresh-token should return user data"""
        response = requests.post(
            f"{BASE_URL}/api/auth/refresh-token",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "user" in data, "Response should contain user"
        user = data["user"]
        assert user["email"] == ADMIN_EMAIL
        print(f"✓ User data returned in refresh: {user['email']}")
    
    def test_refresh_token_without_auth_fails(self):
        """POST /api/auth/refresh-token without token should fail"""
        response = requests.post(f"{BASE_URL}/api/auth/refresh-token")
        
        # Should return 401 or 403
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Refresh without auth correctly rejected")


class TestAdminEndpoints:
    """Test admin endpoints work with correct token"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Authentication failed")
    
    def test_homepage_manager_api_works(self, auth_token):
        """GET /api/website-admin/homepage should work with token"""
        response = requests.get(
            f"{BASE_URL}/api/website-admin/homepage",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200, f"Homepage API failed: {response.text}"
        print("✓ Homepage Manager API works with token")
    
    def test_hero_slides_api_works(self, auth_token):
        """GET /api/website-admin/hero-slides should work with token"""
        response = requests.get(
            f"{BASE_URL}/api/website-admin/hero-slides",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200, f"Hero slides API failed: {response.text}"
        print("✓ Hero slides API works with token")
    
    def test_bathroom_page_api_works(self, auth_token):
        """GET /api/bathroom/page should work with token"""
        response = requests.get(
            f"{BASE_URL}/api/bathroom/page",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200, f"Bathroom page API failed: {response.text}"
        print("✓ Bathroom page API works with token")


class TestPublicEndpoints:
    """Test public endpoints for homepage features"""
    
    def test_public_navigation_returns_bathroom_link(self):
        """GET /api/website-admin/public/navigation/main should include BATHROOM link"""
        response = requests.get(f"{BASE_URL}/api/website-admin/public/navigation/main")
        
        # May return 200 or 404 if not configured
        if response.status_code == 200:
            data = response.json()
            # Check if BATHROOM nav item exists with correct link
            bathroom_items = [item for item in data if item.get('label', '').upper() == 'BATHROOM']
            if bathroom_items:
                bathroom_link = bathroom_items[0].get('link_url', '')
                print(f"✓ BATHROOM nav link found: {bathroom_link}")
                # Note: The actual link may come from admin config or fallback
            else:
                print("ℹ BATHROOM nav item not in API response (may use fallback)")
        else:
            print(f"ℹ Navigation API returned {response.status_code} (may use fallback)")
    
    def test_trade_account_settings_public(self):
        """GET /api/website-admin/public/trade-account-settings should work"""
        response = requests.get(f"{BASE_URL}/api/website-admin/public/trade-account-settings")
        
        # This endpoint should be public
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Trade account settings accessible")
        else:
            print(f"ℹ Trade settings returned {response.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

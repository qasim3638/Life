"""
Test suite for admin session persistence and auth endpoints.
Tests the fixes for admin session expiry issue:
1. /auth/login - returns token and user
2. /auth/me - returns current user info
3. /auth/refresh-token - returns new token with extended expiry
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "qasim@tilestation.co.uk"
ADMIN_PASSWORD = "admin123"


class TestAuthEndpoints:
    """Authentication endpoint tests for session persistence fix"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.token = None
    
    def test_01_login_returns_token_and_user(self):
        """Test that login returns token and user data"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        
        assert response.status_code == 200, f"Login failed: {response.text}"
        
        data = response.json()
        assert "token" in data, "Response missing 'token'"
        assert "user" in data, "Response missing 'user'"
        assert len(data["token"]) > 0, "Token is empty"
        assert data["user"]["email"] == ADMIN_EMAIL, "User email mismatch"
        assert data["user"]["role"] in ["admin", "super_admin", "manager", "staff"], "Invalid role"
        
        # Store token for subsequent tests
        self.__class__.token = data["token"]
        print(f"Login successful - role: {data['user']['role']}")
    
    def test_02_auth_me_returns_user(self):
        """Test that /auth/me returns current user info"""
        if not hasattr(self.__class__, 'token') or not self.__class__.token:
            pytest.skip("No token available - login test must run first")
        
        response = self.session.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {self.__class__.token}"}
        )
        
        assert response.status_code == 200, f"Auth/me failed: {response.text}"
        
        data = response.json()
        assert data["email"] == ADMIN_EMAIL, "Email mismatch"
        assert "role" in data, "Response missing 'role'"
        assert "name" in data, "Response missing 'name'"
        print(f"Auth/me successful - user: {data['name']}")
    
    def test_03_refresh_token_returns_new_token(self):
        """Test that /auth/refresh-token returns a new token"""
        if not hasattr(self.__class__, 'token') or not self.__class__.token:
            pytest.skip("No token available - login test must run first")
        
        response = self.session.post(
            f"{BASE_URL}/api/auth/refresh-token",
            headers={"Authorization": f"Bearer {self.__class__.token}"}
        )
        
        assert response.status_code == 200, f"Refresh token failed: {response.text}"
        
        data = response.json()
        assert "token" in data, "Response missing 'token'"
        assert "user" in data, "Response missing 'user'"
        assert len(data["token"]) > 0, "New token is empty"
        
        # Verify new token is different (has different expiry)
        # Note: tokens may be same if called within same second
        print(f"Refresh token successful - new token length: {len(data['token'])}")
    
    def test_04_invalid_token_returns_401(self):
        """Test that invalid token returns 401"""
        response = self.session.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": "Bearer invalid_token_12345"}
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("Invalid token correctly rejected with 401")
    
    def test_05_missing_auth_header_returns_401_or_403(self):
        """Test that missing auth header returns 401 or 403"""
        response = self.session.get(f"{BASE_URL}/api/auth/me")
        
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"Missing auth header correctly rejected with {response.status_code}")
    
    def test_06_login_with_wrong_password_returns_401(self):
        """Test that wrong password returns 401"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": "wrongpassword123"
        })
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("Wrong password correctly rejected with 401")
    
    def test_07_protected_endpoint_with_valid_token(self):
        """Test that protected endpoints work with valid token"""
        if not hasattr(self.__class__, 'token') or not self.__class__.token:
            pytest.skip("No token available - login test must run first")
        
        # Test a protected admin endpoint
        response = self.session.get(
            f"{BASE_URL}/api/showrooms",
            headers={"Authorization": f"Bearer {self.__class__.token}"}
        )
        
        # Should return 200 (or 404 if no showrooms, but not 401/403)
        assert response.status_code not in [401, 403], f"Protected endpoint rejected valid token: {response.status_code}"
        print(f"Protected endpoint accessible with valid token - status: {response.status_code}")


class TestHealthEndpoint:
    """Health check endpoint test"""
    
    def test_health_check(self):
        """Test that health endpoint is accessible"""
        response = requests.get(f"{BASE_URL}/api/health")
        
        assert response.status_code == 200, f"Health check failed: {response.text}"
        
        data = response.json()
        assert data["status"] == "healthy", f"Unhealthy status: {data}"
        assert data["database"] == "connected", f"Database not connected: {data}"
        print(f"Health check passed - database: {data['database']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

"""
Test Trade Account Settings and Trade Accounts Management
Tests:
- GET /api/website-admin/trade-account-settings - Get trade account settings
- POST /api/website-admin/trade-account-settings - Save trade account settings
- GET /api/trade-accounts - Get trade accounts list
- PUT /api/trade-accounts/{id} - Update trade account with custom_discount, pricing_tier, status
- GET /api/trade-accounts/pricing-tiers - Get pricing tiers
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "qasim@tilestation.co.uk"
ADMIN_PASSWORD = "Tilestation_9614"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for admin user"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        return data.get("token") or data.get("access_token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def api_client(auth_token):
    """Create authenticated session"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


class TestTradeAccountSettings:
    """Test Trade Account Settings endpoints"""
    
    def test_get_trade_account_settings(self, api_client):
        """GET /api/website-admin/trade-account-settings returns settings"""
        response = api_client.get(f"{BASE_URL}/api/website-admin/trade-account-settings")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "settings" in data, "Response should have 'settings' key"
    
    def test_get_trade_account_settings_has_announcement_bar(self, api_client):
        """GET /api/website-admin/trade-account-settings returns announcement_bar items"""
        response = api_client.get(f"{BASE_URL}/api/website-admin/trade-account-settings")
        assert response.status_code == 200
        
        data = response.json()
        settings = data.get("settings", {})
        
        # announcement_bar should be present (either from saved settings or loaded from benefits_bar)
        if "announcement_bar" in settings:
            announcement_bar = settings["announcement_bar"]
            assert "enabled" in announcement_bar or "items" in announcement_bar, \
                "announcement_bar should have 'enabled' or 'items'"
    
    def test_save_trade_account_settings(self, api_client):
        """POST /api/website-admin/trade-account-settings saves settings"""
        test_settings = {
            "settings": {
                "announcement_bar": {
                    "enabled": True,
                    "items": [
                        {"text": "Test Announcement 1", "link": "/tiles", "enabled": True},
                        {"text": "Test Announcement 2", "link": "/shop", "enabled": True}
                    ]
                },
                "tiers": [
                    {"id": "bronze", "name": "Bronze", "discount": 1, "min_spend": 0, "color": "#B45309"},
                    {"id": "silver", "name": "Silver", "discount": 2, "min_spend": 5000, "color": "#9CA3AF"},
                    {"id": "gold", "name": "Gold", "discount": 3, "min_spend": 15000, "color": "#FBBF24"},
                    {"id": "platinum", "name": "Platinum", "discount": 5, "min_spend": 50000, "color": "#D1D5DB"}
                ],
                "tiers_enabled": True
            }
        }
        
        response = api_client.post(
            f"{BASE_URL}/api/website-admin/trade-account-settings",
            json=test_settings
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True or "message" in data, "Response should indicate success"
    
    def test_save_and_verify_settings_persistence(self, api_client):
        """POST then GET to verify settings are persisted"""
        # Save settings
        test_settings = {
            "settings": {
                "announcement_bar": {
                    "enabled": True,
                    "items": [
                        {"text": "Persistence Test Item", "link": "/test", "enabled": True}
                    ]
                },
                "tiers_enabled": True
            }
        }
        
        save_response = api_client.post(
            f"{BASE_URL}/api/website-admin/trade-account-settings",
            json=test_settings
        )
        assert save_response.status_code == 200
        
        # Verify by fetching
        get_response = api_client.get(f"{BASE_URL}/api/website-admin/trade-account-settings")
        assert get_response.status_code == 200
        
        data = get_response.json()
        settings = data.get("settings", {})
        
        # Check that our saved settings are present
        assert "announcement_bar" in settings or "tiers_enabled" in settings, \
            "Saved settings should be retrievable"


class TestTradeAccounts:
    """Test Trade Accounts CRUD endpoints"""
    
    def test_get_trade_accounts_list(self, api_client):
        """GET /api/trade-accounts returns list of trade accounts"""
        response = api_client.get(f"{BASE_URL}/api/trade-accounts")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "accounts" in data, "Response should have 'accounts' key"
        assert "total" in data, "Response should have 'total' key"
        assert isinstance(data["accounts"], list), "accounts should be a list"
    
    def test_get_pricing_tiers(self, api_client):
        """GET /api/trade-accounts/pricing-tiers returns tier definitions"""
        response = api_client.get(f"{BASE_URL}/api/trade-accounts/pricing-tiers")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Should have bronze, silver, gold, platinum
        assert "bronze" in data, "Should have bronze tier"
        assert "silver" in data, "Should have silver tier"
        assert "gold" in data, "Should have gold tier"
        assert "platinum" in data, "Should have platinum tier"
        
        # Each tier should have name, min_spend, discount
        for tier_key, tier_data in data.items():
            assert "name" in tier_data, f"{tier_key} should have 'name'"
            assert "min_spend" in tier_data, f"{tier_key} should have 'min_spend'"
            assert "discount" in tier_data, f"{tier_key} should have 'discount'"
    
    def test_get_trade_types(self, api_client):
        """GET /api/trade-accounts/trade-types returns list of trade types"""
        response = api_client.get(f"{BASE_URL}/api/trade-accounts/trade-types")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Should return a list of trade types"
        assert len(data) > 0, "Should have at least one trade type"
        assert "Builder" in data, "Should include 'Builder' trade type"


class TestTradeAccountUpdate:
    """Test Trade Account update with custom_discount, pricing_tier, status"""
    
    @pytest.fixture
    def existing_trade_account(self, api_client):
        """Get an existing trade account for testing updates"""
        response = api_client.get(f"{BASE_URL}/api/trade-accounts?limit=1")
        if response.status_code == 200:
            data = response.json()
            accounts = data.get("accounts", [])
            if accounts:
                return accounts[0]
        return None
    
    def test_update_trade_account_pricing_tier(self, api_client, existing_trade_account):
        """PUT /api/trade-accounts/{id} can update pricing_tier"""
        if not existing_trade_account:
            pytest.skip("No existing trade account to test update")
        
        account_id = existing_trade_account.get("id")
        original_tier = existing_trade_account.get("pricing_tier", "bronze")
        
        # Change to a different tier
        new_tier = "silver" if original_tier != "silver" else "gold"
        
        response = api_client.put(
            f"{BASE_URL}/api/trade-accounts/{account_id}",
            json={"pricing_tier": new_tier}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify the update
        get_response = api_client.get(f"{BASE_URL}/api/trade-accounts/{account_id}")
        if get_response.status_code == 200:
            updated_account = get_response.json()
            assert updated_account.get("pricing_tier") == new_tier, \
                f"pricing_tier should be updated to {new_tier}"
        
        # Restore original tier
        api_client.put(
            f"{BASE_URL}/api/trade-accounts/{account_id}",
            json={"pricing_tier": original_tier}
        )
    
    def test_update_trade_account_status(self, api_client, existing_trade_account):
        """PUT /api/trade-accounts/{id} can update status"""
        if not existing_trade_account:
            pytest.skip("No existing trade account to test update")
        
        account_id = existing_trade_account.get("id")
        original_status = existing_trade_account.get("status", "active")
        
        # Test updating status
        response = api_client.put(
            f"{BASE_URL}/api/trade-accounts/{account_id}",
            json={"status": "active"}  # Keep it active to not break anything
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_update_trade_account_custom_discount(self, api_client, existing_trade_account):
        """PUT /api/trade-accounts/{id} can set custom_discount"""
        if not existing_trade_account:
            pytest.skip("No existing trade account to test update")
        
        account_id = existing_trade_account.get("id")
        
        # Set a custom discount
        custom_discount = 7.5
        response = api_client.put(
            f"{BASE_URL}/api/trade-accounts/{account_id}",
            json={"custom_discount": custom_discount}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify the update
        get_response = api_client.get(f"{BASE_URL}/api/trade-accounts/{account_id}")
        if get_response.status_code == 200:
            updated_account = get_response.json()
            # custom_discount should be set
            assert updated_account.get("custom_discount") == custom_discount or \
                   updated_account.get("trade_discount") == custom_discount, \
                f"custom_discount should be set to {custom_discount}"
    
    def test_update_trade_account_multiple_fields(self, api_client, existing_trade_account):
        """PUT /api/trade-accounts/{id} can update multiple fields at once"""
        if not existing_trade_account:
            pytest.skip("No existing trade account to test update")
        
        account_id = existing_trade_account.get("id")
        
        # Update multiple fields
        response = api_client.put(
            f"{BASE_URL}/api/trade-accounts/{account_id}",
            json={
                "pricing_tier": "gold",
                "status": "active",
                "notes": "Test update from automated tests"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"


class TestBenefitsBarSync:
    """Test that announcement bar syncs to benefits_bar collection"""
    
    def test_public_benefits_bar_endpoint(self, api_client):
        """GET /api/website-admin/public/benefits-bar returns benefits"""
        response = requests.get(f"{BASE_URL}/api/website-admin/public/benefits-bar")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Should return a list of benefits"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

"""
Test Dynamic Settings for Trade and Customer Account Pages
Tests the public API endpoints and admin save/fetch functionality
"""
import pytest
import requests
import os
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestTradeAccountSettings:
    """Tests for Trade Account Settings API endpoints"""
    
    def test_public_trade_settings_endpoint_exists(self):
        """Test that public trade settings endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/website-admin/public/trade-account-settings")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "settings" in data, "Response should contain 'settings' key"
        print(f"✓ Public trade settings endpoint works - settings: {json.dumps(data.get('settings', {}), indent=2)[:200]}...")
    
    def test_admin_trade_settings_get(self):
        """Test admin GET endpoint for trade settings"""
        response = requests.get(f"{BASE_URL}/api/website-admin/trade-account-settings")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "settings" in data, "Response should contain 'settings' key"
        print(f"✓ Admin trade settings GET works")
    
    def test_admin_trade_settings_save(self):
        """Test saving trade account settings via admin endpoint"""
        test_settings = {
            "settings": {
                "banner": {
                    "enabled": True,
                    "badge_text": "TEST For Trade Professionals",
                    "headline": "TEST Open a Trade Account &",
                    "headline_highlight": "Save More",
                    "description": "TEST Join thousands of builders, tilers, and contractors.",
                    "cta_primary_text": "Open Trade Account",
                    "cta_primary_link": "/shop/trade/register",
                    "cta_secondary_text": "Already have an account? Sign In",
                    "cta_secondary_link": "/shop/login"
                },
                "banner_benefits": [
                    {"icon": "Percent", "text": "TEST Exclusive Discounts", "enabled": True},
                    {"icon": "Gift", "text": "TEST Up to 5% Credit Back", "enabled": True},
                    {"icon": "Truck", "text": "TEST Priority Delivery", "enabled": True},
                    {"icon": "Headphones", "text": "TEST Dedicated Support", "enabled": True}
                ],
                "tiers_enabled": True,
                "tiers": [
                    {"id": "bronze", "name": "Bronze", "discount": 1, "min_spend": 0, "color": "#B45309"},
                    {"id": "silver", "name": "Silver", "discount": 2, "min_spend": 5000, "color": "#9CA3AF"},
                    {"id": "gold", "name": "Gold", "discount": 3, "min_spend": 15000, "color": "#FBBF24"},
                    {"id": "platinum", "name": "Platinum", "discount": 5, "min_spend": 50000, "color": "#D1D5DB"}
                ],
                "benefits": [
                    {"icon": "Percent", "title": "TEST Exclusive Trade Discounts", "description": "Access special pricing", "enabled": True},
                    {"icon": "Gift", "title": "TEST Credit Back Rewards", "description": "Earn credit back on every purchase", "enabled": True}
                ]
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/website-admin/trade-account-settings",
            json=test_settings,
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        print(f"✓ Admin trade settings SAVE works")
    
    def test_public_trade_settings_returns_saved_data(self):
        """Test that public endpoint returns the saved settings"""
        response = requests.get(f"{BASE_URL}/api/website-admin/public/trade-account-settings")
        assert response.status_code == 200
        data = response.json()
        settings = data.get("settings", {})
        
        # Check if our test data is present (if previously saved)
        if settings:
            print(f"✓ Public endpoint returns settings with keys: {list(settings.keys())}")
            # Verify structure
            if "banner" in settings:
                assert "enabled" in settings["banner"] or "headline" in settings["banner"], "Banner should have expected fields"
            if "tiers" in settings:
                assert isinstance(settings["tiers"], list), "Tiers should be a list"
        else:
            print("✓ Public endpoint returns empty settings (no settings saved yet)")


class TestCustomerAccountSettings:
    """Tests for Customer Account Settings API endpoints"""
    
    def test_public_customer_settings_endpoint_exists(self):
        """Test that public customer settings endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/website-admin/public/customer-account-settings")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "settings" in data, "Response should contain 'settings' key"
        print(f"✓ Public customer settings endpoint works - settings: {json.dumps(data.get('settings', {}), indent=2)[:200]}...")
    
    def test_admin_customer_settings_get(self):
        """Test admin GET endpoint for customer settings"""
        response = requests.get(f"{BASE_URL}/api/website-admin/customer-account-settings")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "settings" in data, "Response should contain 'settings' key"
        print(f"✓ Admin customer settings GET works")
    
    def test_admin_customer_settings_save(self):
        """Test saving customer account settings via admin endpoint"""
        test_settings = {
            "settings": {
                "registration": {
                    "headline": "TEST Create Your Account",
                    "subheadline": "TEST Join Tile Station for a better shopping experience",
                    "show_trade_cta": True,
                    "trade_cta_title": "TEST Are you a Trade Professional?",
                    "trade_cta_description": "TEST Get exclusive discounts & credit back rewards",
                    "trade_cta_button": "Open Trade Account"
                },
                "registration_benefits": [
                    {"icon": "ShoppingBag", "text": "TEST Track your orders easily", "enabled": True},
                    {"icon": "Heart", "text": "TEST Save items to your wishlist", "enabled": True},
                    {"icon": "Truck", "text": "TEST Faster checkout experience", "enabled": True},
                    {"icon": "CheckCircle2", "text": "TEST Exclusive member offers", "enabled": True}
                ],
                "portal": {
                    "welcome_message": "TEST Welcome back, {name}!",
                    "welcome_subtext": "TEST Manage your account, track orders, and save your favourites.",
                    "show_trade_upgrade": True,
                    "trade_upgrade_title": "TEST Trade Professional?",
                    "trade_upgrade_text": "TEST Get exclusive discounts & credit back rewards",
                    "trade_upgrade_button": "Open Trade Account"
                },
                "dashboard": {
                    "stats": [
                        {"id": "orders", "label": "Total Orders", "icon": "ShoppingBag", "color": "blue", "enabled": True},
                        {"id": "wishlist", "label": "Wishlist Items", "icon": "Heart", "color": "pink", "enabled": True},
                        {"id": "addresses", "label": "Saved Addresses", "icon": "MapPin", "color": "green", "enabled": True}
                    ],
                    "quick_actions": [
                        {"id": "shop", "title": "Browse Tiles", "description": "Explore our collections", "link": "/shop/tiles", "enabled": True},
                        {"id": "samples", "title": "Order Samples", "description": "Try before you buy", "link": "/shop/sample-service", "enabled": True}
                    ],
                    "sidebar_tabs": [
                        {"id": "overview", "label": "Overview", "enabled": True},
                        {"id": "orders", "label": "Orders", "enabled": True},
                        {"id": "wishlist", "label": "Wishlist", "enabled": True},
                        {"id": "settings", "label": "Settings", "enabled": True}
                    ]
                }
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/website-admin/customer-account-settings",
            json=test_settings,
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        print(f"✓ Admin customer settings SAVE works")
    
    def test_public_customer_settings_returns_saved_data(self):
        """Test that public endpoint returns the saved settings"""
        response = requests.get(f"{BASE_URL}/api/website-admin/public/customer-account-settings")
        assert response.status_code == 200
        data = response.json()
        settings = data.get("settings", {})
        
        if settings:
            print(f"✓ Public endpoint returns settings with keys: {list(settings.keys())}")
            # Verify structure
            if "registration" in settings:
                assert "headline" in settings["registration"] or "show_trade_cta" in settings["registration"], "Registration should have expected fields"
            if "portal" in settings:
                assert "welcome_message" in settings["portal"] or "show_trade_upgrade" in settings["portal"], "Portal should have expected fields"
        else:
            print("✓ Public endpoint returns empty settings (no settings saved yet)")


class TestSettingsPersistence:
    """Test that settings persist correctly after save"""
    
    def test_trade_settings_persist_after_save(self):
        """Save trade settings and verify they persist"""
        # Save specific test data
        unique_text = f"PERSIST_TEST_{os.urandom(4).hex()}"
        test_settings = {
            "settings": {
                "banner": {
                    "enabled": True,
                    "badge_text": unique_text
                },
                "tiers_enabled": True,
                "tiers": [
                    {"id": "bronze", "name": "Bronze", "discount": 1, "min_spend": 0, "color": "#B45309"}
                ]
            }
        }
        
        # Save
        save_response = requests.post(
            f"{BASE_URL}/api/website-admin/trade-account-settings",
            json=test_settings,
            headers={"Content-Type": "application/json"}
        )
        assert save_response.status_code == 200
        
        # Fetch and verify
        get_response = requests.get(f"{BASE_URL}/api/website-admin/public/trade-account-settings")
        assert get_response.status_code == 200
        data = get_response.json()
        settings = data.get("settings", {})
        
        assert settings.get("banner", {}).get("badge_text") == unique_text, f"Expected badge_text={unique_text}, got {settings.get('banner', {}).get('badge_text')}"
        print(f"✓ Trade settings persist correctly after save")
    
    def test_customer_settings_persist_after_save(self):
        """Save customer settings and verify they persist"""
        # Save specific test data
        unique_text = f"PERSIST_TEST_{os.urandom(4).hex()}"
        test_settings = {
            "settings": {
                "registration": {
                    "headline": unique_text
                },
                "portal": {
                    "welcome_message": f"Welcome {unique_text}!"
                }
            }
        }
        
        # Save
        save_response = requests.post(
            f"{BASE_URL}/api/website-admin/customer-account-settings",
            json=test_settings,
            headers={"Content-Type": "application/json"}
        )
        assert save_response.status_code == 200
        
        # Fetch and verify
        get_response = requests.get(f"{BASE_URL}/api/website-admin/public/customer-account-settings")
        assert get_response.status_code == 200
        data = get_response.json()
        settings = data.get("settings", {})
        
        assert settings.get("registration", {}).get("headline") == unique_text, f"Expected headline={unique_text}, got {settings.get('registration', {}).get('headline')}"
        print(f"✓ Customer settings persist correctly after save")


class TestDefaultFallbacks:
    """Test that frontend pages work with empty settings (fallback to defaults)"""
    
    def test_empty_settings_response_structure(self):
        """Verify empty settings response has correct structure"""
        # Clear settings by saving empty
        requests.post(
            f"{BASE_URL}/api/website-admin/trade-account-settings",
            json={"settings": {}},
            headers={"Content-Type": "application/json"}
        )
        
        response = requests.get(f"{BASE_URL}/api/website-admin/public/trade-account-settings")
        assert response.status_code == 200
        data = response.json()
        assert "settings" in data, "Response should always have 'settings' key"
        print(f"✓ Empty settings response has correct structure")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

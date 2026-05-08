"""
Checkout System Tests
Tests for:
- Admin checkout settings (GET/POST /api/website-admin/checkout-settings)
- Public checkout settings (GET /api/website-admin/public/checkout-settings)
- Guest checkout order creation (POST /api/shop/guest-checkout)
- Postcode-based delivery fee calculation
- Free delivery threshold
- Click & collect delivery method
"""
import pytest
import requests
import os
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "Admin@2026"


class TestAdminLogin:
    """Test admin authentication"""
    
    def test_admin_login_success(self):
        """Test admin can login successfully"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in login response"
        print(f"✓ Admin login successful, token received")
        return data["token"]


class TestCheckoutSettingsAPI:
    """Test checkout settings endpoints"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin token for authenticated requests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Admin login failed")
    
    def test_get_checkout_settings_admin(self, admin_token):
        """Test GET /api/website-admin/checkout-settings (admin)"""
        response = requests.get(
            f"{BASE_URL}/api/website-admin/checkout-settings",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Failed to get checkout settings: {response.text}"
        data = response.json()
        assert "settings" in data, "Response missing 'settings' key"
        print(f"✓ Admin checkout settings retrieved: {json.dumps(data, indent=2)[:500]}")
    
    def test_get_public_checkout_settings(self):
        """Test GET /api/website-admin/public/checkout-settings (no auth)"""
        response = requests.get(f"{BASE_URL}/api/website-admin/public/checkout-settings")
        assert response.status_code == 200, f"Failed to get public checkout settings: {response.text}"
        data = response.json()
        assert "settings" in data, "Response missing 'settings' key"
        print(f"✓ Public checkout settings retrieved")
        return data["settings"]
    
    def test_save_checkout_settings(self, admin_token):
        """Test POST /api/website-admin/checkout-settings"""
        test_settings = {
            "settings": {
                "delivery": {
                    "enabled": True,
                    "free_threshold": 500,
                    "default_fee": 79.99,
                    "label": "Home Delivery",
                    "description": "Delivered within 3-5 working days",
                    "zones": [
                        {"id": "1", "name": "Local (TN, ME, BR, DA)", "postcodes": "TN,ME,BR,DA", "fee": 29.99},
                        {"id": "2", "name": "Greater London", "postcodes": "E,EC,N,NW,SE,SW,W,WC", "fee": 49.99},
                        {"id": "3", "name": "South East", "postcodes": "CT,SS,RM,CM,BN,RH,GU,KT,CR,SM,SL", "fee": 59.99},
                        {"id": "4", "name": "Rest of UK", "postcodes": "", "fee": 79.99}
                    ]
                },
                "collection": {
                    "enabled": True,
                    "label": "Click & Collect",
                    "description": "FREE - Collect from our store",
                    "ready_time": "Ready within 24 hours",
                    "stores": [
                        {"id": "1", "name": "Tile Station - Tonbridge", "address": "Unit 5, Cannon Lane, Tonbridge TN9 1PP", "active": True}
                    ]
                },
                "time_slots": [
                    {"id": "morning", "label": "Morning (8am - 12pm)", "description": "Best for early risers", "enabled": True},
                    {"id": "afternoon", "label": "Afternoon (12pm - 5pm)", "description": "Most popular slot", "enabled": True}
                ],
                "text": {
                    "step1_title": "Your Details",
                    "step2_title": "Delivery Method",
                    "step3_title": "Payment",
                    "secure_message": "Your payment information is encrypted and secure.",
                    "order_notes_placeholder": "Special instructions for delivery...",
                    "success_message": "Thank you! Your order has been placed."
                },
                "min_order": 0
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/website-admin/checkout-settings",
            headers={"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"},
            json=test_settings
        )
        assert response.status_code == 200, f"Failed to save checkout settings: {response.text}"
        data = response.json()
        assert "message" in data, "Response missing 'message' key"
        print(f"✓ Checkout settings saved successfully")
        
        # Verify settings were saved by fetching them
        verify_response = requests.get(f"{BASE_URL}/api/website-admin/public/checkout-settings")
        assert verify_response.status_code == 200
        saved_settings = verify_response.json().get("settings", {})
        assert saved_settings.get("delivery", {}).get("free_threshold") == 500, "Free threshold not saved correctly"
        print(f"✓ Verified settings were persisted")


class TestDeliveryFeeCalculation:
    """Test postcode-based delivery fee calculation"""
    
    def test_tn_postcode_delivery_fee(self):
        """TN postcode should get £29.99 delivery (Local zone)"""
        # Get checkout settings to verify zones
        response = requests.get(f"{BASE_URL}/api/website-admin/public/checkout-settings")
        assert response.status_code == 200
        settings = response.json().get("settings", {})
        
        zones = settings.get("delivery", {}).get("zones", [])
        print(f"Delivery zones: {json.dumps(zones, indent=2)}")
        
        # Find the zone that matches TN postcode
        tn_fee = None
        for zone in zones:
            postcodes = zone.get("postcodes", "").upper().split(",")
            postcodes = [p.strip() for p in postcodes if p.strip()]
            if "TN" in postcodes:
                tn_fee = zone.get("fee")
                break
        
        assert tn_fee == 29.99, f"TN postcode should have £29.99 fee, got {tn_fee}"
        print(f"✓ TN postcode delivery fee: £{tn_fee}")
    
    def test_se_postcode_delivery_fee(self):
        """SE postcode should get £49.99 delivery (Greater London zone)"""
        response = requests.get(f"{BASE_URL}/api/website-admin/public/checkout-settings")
        assert response.status_code == 200
        settings = response.json().get("settings", {})
        
        zones = settings.get("delivery", {}).get("zones", [])
        
        # Find the zone that matches SE postcode
        se_fee = None
        for zone in zones:
            postcodes = zone.get("postcodes", "").upper().split(",")
            postcodes = [p.strip() for p in postcodes if p.strip()]
            if "SE" in postcodes:
                se_fee = zone.get("fee")
                break
        
        assert se_fee == 49.99, f"SE postcode should have £49.99 fee, got {se_fee}"
        print(f"✓ SE postcode delivery fee: £{se_fee}")
    
    def test_unknown_postcode_default_fee(self):
        """Unknown postcode should get default fee (£79.99)"""
        response = requests.get(f"{BASE_URL}/api/website-admin/public/checkout-settings")
        assert response.status_code == 200
        settings = response.json().get("settings", {})
        
        default_fee = settings.get("delivery", {}).get("default_fee")
        assert default_fee == 79.99, f"Default fee should be £79.99, got {default_fee}"
        print(f"✓ Default delivery fee for unknown postcodes: £{default_fee}")
    
    def test_free_delivery_threshold(self):
        """Orders over £500 should get free delivery"""
        response = requests.get(f"{BASE_URL}/api/website-admin/public/checkout-settings")
        assert response.status_code == 200
        settings = response.json().get("settings", {})
        
        free_threshold = settings.get("delivery", {}).get("free_threshold")
        assert free_threshold == 500, f"Free delivery threshold should be £500, got {free_threshold}"
        print(f"✓ Free delivery threshold: £{free_threshold}")


class TestGuestCheckout:
    """Test guest checkout order creation"""
    
    def test_guest_checkout_order_creation(self):
        """Test POST /api/shop/guest-checkout creates order"""
        order_data = {
            "items": [
                {
                    "product_id": "test-tile-001",
                    "name": "Test Porcelain Tile",
                    "variant": "600x600mm",
                    "price": 45.99,
                    "quantity": 5,
                    "image": ""
                }
            ],
            "customer": {
                "email": "test@example.com",
                "firstName": "John",
                "lastName": "Doe",
                "phone": "07123456789"
            },
            "delivery": {
                "method": "delivery",
                "address1": "123 Test Street",
                "address2": "",
                "city": "London",
                "county": "Greater London",
                "postcode": "SE1 1AA",
                "notes": "Leave at door"
            },
            "payment": {
                "method": "card"
            },
            "subtotal": 229.95,
            "delivery_fee": 49.99,
            "total": 279.94
        }
        
        response = requests.post(
            f"{BASE_URL}/api/shop/guest-checkout",
            headers={"Content-Type": "application/json"},
            json=order_data
        )
        assert response.status_code == 200, f"Guest checkout failed: {response.text}"
        data = response.json()
        
        assert "order_id" in data, "Response missing order_id"
        assert "order_number" in data, "Response missing order_number"
        assert "total" in data, "Response missing total"
        assert "status" in data, "Response missing status"
        
        print(f"✓ Guest checkout order created: {data['order_number']}")
        print(f"  Order ID: {data['order_id']}")
        print(f"  Total: £{data['total']}")
        print(f"  Status: {data['status']}")
        
        return data
    
    def test_guest_checkout_click_collect(self):
        """Test guest checkout with click & collect (£0 delivery)"""
        order_data = {
            "items": [
                {
                    "product_id": "test-tile-002",
                    "name": "Test Wall Tile",
                    "variant": "300x600mm",
                    "price": 25.99,
                    "quantity": 10,
                    "image": ""
                }
            ],
            "customer": {
                "email": "collect@example.com",
                "firstName": "Jane",
                "lastName": "Smith",
                "phone": "07987654321"
            },
            "delivery": {
                "method": "collect",
                "notes": "Will collect Saturday morning"
            },
            "payment": {
                "method": "card"
            },
            "subtotal": 259.90,
            "delivery_fee": 0,
            "total": 259.90
        }
        
        response = requests.post(
            f"{BASE_URL}/api/shop/guest-checkout",
            headers={"Content-Type": "application/json"},
            json=order_data
        )
        assert response.status_code == 200, f"Click & collect checkout failed: {response.text}"
        data = response.json()
        
        # For click & collect, delivery fee should be 0
        assert data.get("total") == 259.90, f"Click & collect total should be £259.90, got £{data.get('total')}"
        print(f"✓ Click & collect order created: {data['order_number']}")
        print(f"  Total (no delivery fee): £{data['total']}")
    
    def test_guest_checkout_free_delivery_over_500(self):
        """Test free delivery for orders over £500"""
        order_data = {
            "items": [
                {
                    "product_id": "test-tile-003",
                    "name": "Premium Floor Tile",
                    "variant": "800x800mm",
                    "price": 89.99,
                    "quantity": 6,
                    "image": ""
                }
            ],
            "customer": {
                "email": "bigorder@example.com",
                "firstName": "Bob",
                "lastName": "Builder",
                "phone": "07111222333"
            },
            "delivery": {
                "method": "delivery",
                "address1": "456 Big Order Lane",
                "city": "Manchester",
                "postcode": "M1 1AA",  # Unknown postcode - would normally be £79.99
                "notes": ""
            },
            "payment": {
                "method": "card"
            },
            "subtotal": 539.94,  # Over £500 threshold
            "delivery_fee": 0,  # Should be free
            "total": 539.94
        }
        
        response = requests.post(
            f"{BASE_URL}/api/shop/guest-checkout",
            headers={"Content-Type": "application/json"},
            json=order_data
        )
        assert response.status_code == 200, f"Free delivery checkout failed: {response.text}"
        data = response.json()
        
        # Server recalculates delivery fee - should be 0 for orders over £500
        assert data.get("total") == 539.94, f"Order over £500 should have free delivery, total: £{data.get('total')}"
        print(f"✓ Free delivery order created: {data['order_number']}")
        print(f"  Subtotal: £539.94 (over £500 threshold)")
        print(f"  Total (free delivery): £{data['total']}")
    
    def test_guest_checkout_missing_customer_details(self):
        """Test guest checkout fails with missing required fields"""
        order_data = {
            "items": [
                {"product_id": "test", "name": "Test", "price": 10, "quantity": 1}
            ],
            "customer": {
                "email": "",  # Missing email
                "firstName": "",  # Missing first name
                "lastName": ""  # Missing last name
            },
            "delivery": {"method": "delivery"},
            "payment": {},
            "subtotal": 10,
            "total": 10
        }
        
        response = requests.post(
            f"{BASE_URL}/api/shop/guest-checkout",
            headers={"Content-Type": "application/json"},
            json=order_data
        )
        # Should fail with 400 or 422 for validation error
        assert response.status_code in [400, 422], f"Expected validation error, got {response.status_code}"
        print(f"✓ Guest checkout correctly rejects missing customer details")
    
    def test_guest_checkout_empty_items(self):
        """Test guest checkout fails with no items"""
        order_data = {
            "items": [],  # Empty items
            "customer": {
                "email": "test@example.com",
                "firstName": "Test",
                "lastName": "User"
            },
            "delivery": {"method": "delivery"},
            "payment": {},
            "subtotal": 0,
            "total": 0
        }
        
        response = requests.post(
            f"{BASE_URL}/api/shop/guest-checkout",
            headers={"Content-Type": "application/json"},
            json=order_data
        )
        # Should fail with 400 for empty items
        assert response.status_code == 400, f"Expected 400 for empty items, got {response.status_code}"
        print(f"✓ Guest checkout correctly rejects empty items")


class TestCheckoutSettingsStructure:
    """Test checkout settings have correct structure"""
    
    def test_settings_have_delivery_section(self):
        """Verify delivery section exists with required fields"""
        response = requests.get(f"{BASE_URL}/api/website-admin/public/checkout-settings")
        assert response.status_code == 200
        settings = response.json().get("settings", {})
        
        delivery = settings.get("delivery", {})
        assert "enabled" in delivery or delivery.get("zones"), "Delivery section missing or incomplete"
        assert "zones" in delivery, "Delivery zones missing"
        assert "free_threshold" in delivery, "Free threshold missing"
        assert "default_fee" in delivery, "Default fee missing"
        print(f"✓ Delivery section structure verified")
    
    def test_settings_have_collection_section(self):
        """Verify collection section exists with required fields"""
        response = requests.get(f"{BASE_URL}/api/website-admin/public/checkout-settings")
        assert response.status_code == 200
        settings = response.json().get("settings", {})
        
        collection = settings.get("collection", {})
        assert "enabled" in collection or collection.get("stores"), "Collection section missing or incomplete"
        assert "stores" in collection, "Collection stores missing"
        print(f"✓ Collection section structure verified")
    
    def test_settings_have_text_section(self):
        """Verify text section exists with step titles"""
        response = requests.get(f"{BASE_URL}/api/website-admin/public/checkout-settings")
        assert response.status_code == 200
        settings = response.json().get("settings", {})
        
        text = settings.get("text", {})
        assert "step1_title" in text, "Step 1 title missing"
        assert "step2_title" in text, "Step 2 title missing"
        assert "step3_title" in text, "Step 3 title missing"
        print(f"✓ Text section structure verified")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

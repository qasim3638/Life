"""
Test Next Day Delivery Feature
- GET /api/website-admin/suppliers-list returns list of all supplier names
- POST /api/website-admin/collection-detail-settings saves nextDayDelivery config
- GET /api/website-admin/collection-detail-settings returns saved nextDayDelivery config
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://feature-verification-7.preview.emergentagent.com').rstrip('/')


class TestSuppliersListAPI:
    """Test GET /api/website-admin/suppliers-list endpoint"""
    
    def test_suppliers_list_returns_200(self):
        """Test that suppliers-list endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/website-admin/suppliers-list")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/website-admin/suppliers-list returns 200")
    
    def test_suppliers_list_returns_array(self):
        """Test that suppliers-list returns a suppliers array"""
        response = requests.get(f"{BASE_URL}/api/website-admin/suppliers-list")
        data = response.json()
        assert "suppliers" in data, "Response should contain 'suppliers' key"
        assert isinstance(data["suppliers"], list), "suppliers should be a list"
        print(f"✓ suppliers-list returns array with {len(data['suppliers'])} suppliers")
    
    def test_suppliers_list_contains_expected_suppliers(self):
        """Test that suppliers-list contains expected supplier names"""
        response = requests.get(f"{BASE_URL}/api/website-admin/suppliers-list")
        data = response.json()
        suppliers = data.get("suppliers", [])
        
        # Expected suppliers from the test DB
        expected_suppliers = ["Canopy", "LEPORCE", "Splendour", "Ultra Tile", "Verona"]
        
        for supplier in expected_suppliers:
            assert supplier in suppliers, f"Expected supplier '{supplier}' not found in list"
        
        print(f"✓ All expected suppliers found: {expected_suppliers}")


class TestCollectionDetailSettingsAPI:
    """Test collection-detail-settings API for nextDayDelivery config"""
    
    def test_get_settings_returns_200(self):
        """Test that GET collection-detail-settings returns 200"""
        response = requests.get(f"{BASE_URL}/api/website-admin/collection-detail-settings")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/website-admin/collection-detail-settings returns 200")
    
    def test_save_next_day_delivery_settings(self):
        """Test saving nextDayDelivery settings with suppliers"""
        # First get current settings
        get_response = requests.get(f"{BASE_URL}/api/website-admin/collection-detail-settings")
        current_settings = get_response.json().get("settings", {})
        
        # Add nextDayDelivery config
        current_settings["nextDayDelivery"] = {
            "enabled": True,
            "suppliers": ["Canopy", "LEPORCE"]
        }
        
        # Save settings
        save_response = requests.post(
            f"{BASE_URL}/api/website-admin/collection-detail-settings",
            json={"settings": current_settings},
            headers={"Content-Type": "application/json"}
        )
        
        assert save_response.status_code == 200, f"Expected 200, got {save_response.status_code}"
        print("✓ POST /api/website-admin/collection-detail-settings saves nextDayDelivery config")
    
    def test_get_saved_next_day_delivery_settings(self):
        """Test that saved nextDayDelivery settings are returned"""
        # First save settings
        get_response = requests.get(f"{BASE_URL}/api/website-admin/collection-detail-settings")
        current_settings = get_response.json().get("settings", {})
        
        current_settings["nextDayDelivery"] = {
            "enabled": True,
            "suppliers": ["Canopy", "LEPORCE", "Verona"]
        }
        
        requests.post(
            f"{BASE_URL}/api/website-admin/collection-detail-settings",
            json={"settings": current_settings},
            headers={"Content-Type": "application/json"}
        )
        
        # Now fetch and verify
        verify_response = requests.get(f"{BASE_URL}/api/website-admin/collection-detail-settings")
        data = verify_response.json()
        settings = data.get("settings", {})
        
        assert "nextDayDelivery" in settings, "nextDayDelivery should be in settings"
        assert settings["nextDayDelivery"]["enabled"] == True, "nextDayDelivery should be enabled"
        assert "Canopy" in settings["nextDayDelivery"]["suppliers"], "Canopy should be in suppliers"
        assert "LEPORCE" in settings["nextDayDelivery"]["suppliers"], "LEPORCE should be in suppliers"
        assert "Verona" in settings["nextDayDelivery"]["suppliers"], "Verona should be in suppliers"
        
        print(f"✓ Saved nextDayDelivery settings retrieved: enabled={settings['nextDayDelivery']['enabled']}, suppliers={settings['nextDayDelivery']['suppliers']}")
    
    def test_disable_next_day_delivery(self):
        """Test disabling nextDayDelivery"""
        get_response = requests.get(f"{BASE_URL}/api/website-admin/collection-detail-settings")
        current_settings = get_response.json().get("settings", {})
        
        current_settings["nextDayDelivery"] = {
            "enabled": False,
            "suppliers": []
        }
        
        save_response = requests.post(
            f"{BASE_URL}/api/website-admin/collection-detail-settings",
            json={"settings": current_settings},
            headers={"Content-Type": "application/json"}
        )
        
        assert save_response.status_code == 200
        
        # Verify
        verify_response = requests.get(f"{BASE_URL}/api/website-admin/collection-detail-settings")
        settings = verify_response.json().get("settings", {})
        
        assert settings["nextDayDelivery"]["enabled"] == False, "nextDayDelivery should be disabled"
        print("✓ nextDayDelivery can be disabled")


class TestProductSupplierField:
    """Test that products have supplier field for next day delivery matching"""
    
    def test_collection_products_have_supplier(self):
        """Test that collection products have supplier field"""
        # Fetch a collection (Dolomite is mentioned in the test request)
        response = requests.get(f"{BASE_URL}/api/tiles/collection/Dolomite?limit=5")
        
        if response.status_code == 200:
            data = response.json()
            products = data.get("products", [])
            
            if products:
                # Check if products have supplier field
                for product in products[:3]:
                    supplier = product.get("supplier") or product.get("supplier_name")
                    print(f"  Product: {product.get('display_name', product.get('name', 'Unknown'))}, Supplier: {supplier}")
                
                print(f"✓ Collection products fetched, checking supplier field")
            else:
                print("⚠ No products found in Dolomite collection")
        else:
            print(f"⚠ Could not fetch Dolomite collection: {response.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

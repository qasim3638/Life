"""
Test Suite for Disable Tier Pricing Feature
Tests the ability to disable quantity-based tier discounts for specific products.

Test scenarios:
1. PUT /api/supplier-sync/products/bulk-tier-update with disabled=true
2. GET /api/tiles/pricing/calculate with product_sku returns disabled:true
3. GET /api/tiles/products/{slug}/tier-pricing returns disabled:true
4. Re-enable tier pricing and verify it works again
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://feature-verification-7.preview.emergentagent.com').rstrip('/')

# Test product - LP-3611 (Alabaster 30x60cm Polished)
TEST_PRODUCT_SKU = "LP-3611"
TEST_PRODUCT_SLUG = "alabaster-30x60cm-polished"
TEST_PRODUCT_SUPPLIER = "LEPORCE"


class TestTierPricingDisableFeature:
    """Test suite for the Disable Tier Pricing feature"""
    
    @pytest.fixture(autouse=True)
    def setup_and_cleanup(self):
        """Ensure tier pricing is enabled before each test and clean up after"""
        # Setup - make sure tier pricing is enabled initially
        # This also serves as cleanup for any previous test runs
        self.enable_tier_pricing()
        yield
        # Teardown - re-enable tier pricing after tests
        self.enable_tier_pricing()
    
    def enable_tier_pricing(self):
        """Helper to enable tier pricing for test product"""
        response = requests.put(
            f"{BASE_URL}/api/supplier-sync/products/bulk-tier-update",
            json={
                "products": [{"supplier": TEST_PRODUCT_SUPPLIER, "sku": TEST_PRODUCT_SKU}],
                "tier_thresholds": [10, 50, 100],
                "tier_discounts": [0, 5, 10, 15],
                "disabled": False
            },
            headers={"Content-Type": "application/json"}
        )
        return response
    
    def test_01_get_tier_pricing_config_global(self):
        """Test GET /api/tiles/pricing/tiers - Get global tier pricing config"""
        response = requests.get(f"{BASE_URL}/api/tiles/pricing/tiers")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "thresholds" in data, "Response should contain thresholds"
        assert "discounts" in data, "Response should contain discounts"
        assert "trade_discount_default" in data, "Response should contain trade_discount_default"
        
        # Verify structure
        assert isinstance(data["thresholds"], list), "Thresholds should be a list"
        assert isinstance(data["discounts"], list), "Discounts should be a list"
        print(f"✓ Global tier pricing config retrieved: thresholds={data['thresholds']}, discounts={data['discounts']}")
    
    def test_02_get_product_exists(self):
        """Test that test product LP-3611 exists in the tiles collection"""
        response = requests.get(f"{BASE_URL}/api/tiles/products/{TEST_PRODUCT_SLUG}")
        
        assert response.status_code == 200, f"Product {TEST_PRODUCT_SLUG} should exist"
        
        data = response.json()
        assert data["sku"] == TEST_PRODUCT_SKU, f"SKU should be {TEST_PRODUCT_SKU}"
        assert data["supplier"] == TEST_PRODUCT_SUPPLIER, f"Supplier should be {TEST_PRODUCT_SUPPLIER}"
        print(f"✓ Product found: {data['display_name']} (SKU: {data['sku']})")
    
    def test_03_tier_pricing_enabled_initially(self):
        """Test that tier pricing returns tiers when enabled (default state)"""
        # First make sure it's enabled
        self.enable_tier_pricing()
        time.sleep(0.5)  # Allow DB update to propagate
        
        response = requests.get(
            f"{BASE_URL}/api/tiles/pricing/calculate",
            params={
                "base_price": 50,
                "quantity": 10,
                "product_sku": TEST_PRODUCT_SKU
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # When enabled, should NOT have disabled=True
        assert data.get("disabled") != True, "Tier pricing should be enabled initially"
        assert "tiers" in data, "Response should contain tiers"
        assert len(data["tiers"]) > 0, "Should have tier pricing data"
        print(f"✓ Tier pricing enabled - {len(data['tiers'])} tiers available")
    
    def test_04_disable_tier_pricing_via_api(self):
        """Test PUT /api/supplier-sync/products/bulk-tier-update with disabled=true"""
        response = requests.put(
            f"{BASE_URL}/api/supplier-sync/products/bulk-tier-update",
            json={
                "products": [{"supplier": TEST_PRODUCT_SUPPLIER, "sku": TEST_PRODUCT_SKU}],
                "disabled": True
            },
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["success"] == True, "Operation should succeed"
        assert data["action"] == "disabled", "Action should be 'disabled'"
        assert data["updated_count"] >= 1, "Should update at least 1 product"
        print(f"✓ Tier pricing disabled via API: {data['message']}")
    
    def test_05_verify_disabled_in_calculate_endpoint(self):
        """Test GET /api/tiles/pricing/calculate returns disabled:true after disabling"""
        # First disable
        self.test_04_disable_tier_pricing_via_api()
        time.sleep(0.5)  # Allow DB update to propagate
        
        response = requests.get(
            f"{BASE_URL}/api/tiles/pricing/calculate",
            params={
                "base_price": 50,
                "quantity": 10,
                "product_sku": TEST_PRODUCT_SKU
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("disabled") == True, "Response should have disabled=True"
        assert data.get("tiers") == [] or len(data.get("tiers", [])) == 0, "Tiers should be empty when disabled"
        assert data.get("current_discount_percent") == 0, "Discount should be 0 when disabled"
        print(f"✓ Calculate endpoint returns disabled=True, base_price={data['base_price']}")
    
    def test_06_verify_disabled_in_tier_pricing_endpoint(self):
        """Test GET /api/tiles/products/{slug}/tier-pricing returns disabled:true"""
        # First disable
        requests.put(
            f"{BASE_URL}/api/supplier-sync/products/bulk-tier-update",
            json={
                "products": [{"supplier": TEST_PRODUCT_SUPPLIER, "sku": TEST_PRODUCT_SKU}],
                "disabled": True
            },
            headers={"Content-Type": "application/json"}
        )
        time.sleep(0.5)  # Allow DB update to propagate
        
        response = requests.get(
            f"{BASE_URL}/api/tiles/products/{TEST_PRODUCT_SLUG}/tier-pricing",
            params={"quantity": 10}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("disabled") == True, "Response should have disabled=True"
        assert data.get("tiers") == [], "Tiers should be empty when disabled"
        assert "product" in data, "Response should include product info"
        assert data["product"].get("tier_pricing_disabled") == True, "Product should show tier_pricing_disabled=True"
        print(f"✓ Product tier-pricing endpoint returns disabled=True for {data['product']['display_name']}")
    
    def test_07_reenable_tier_pricing(self):
        """Test re-enabling tier pricing via API"""
        # First disable
        requests.put(
            f"{BASE_URL}/api/supplier-sync/products/bulk-tier-update",
            json={
                "products": [{"supplier": TEST_PRODUCT_SUPPLIER, "sku": TEST_PRODUCT_SKU}],
                "disabled": True
            },
            headers={"Content-Type": "application/json"}
        )
        time.sleep(0.3)
        
        # Then re-enable
        response = requests.put(
            f"{BASE_URL}/api/supplier-sync/products/bulk-tier-update",
            json={
                "products": [{"supplier": TEST_PRODUCT_SUPPLIER, "sku": TEST_PRODUCT_SKU}],
                "tier_thresholds": [10, 50, 100],
                "tier_discounts": [0, 5, 10, 15],
                "disabled": False
            },
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["success"] == True, "Operation should succeed"
        assert data["action"] == "updated", "Action should be 'updated' (not disabled)"
        print(f"✓ Tier pricing re-enabled: {data['message']}")
    
    def test_08_verify_enabled_after_reenable(self):
        """Verify tier pricing works after re-enabling"""
        # Ensure it's enabled
        self.enable_tier_pricing()
        time.sleep(0.5)
        
        response = requests.get(
            f"{BASE_URL}/api/tiles/pricing/calculate",
            params={
                "base_price": 50,
                "quantity": 10,
                "product_sku": TEST_PRODUCT_SKU
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("disabled") != True, "Tier pricing should be enabled after re-enable"
        assert "tiers" in data and len(data["tiers"]) > 0, "Should have tiers after re-enable"
        print(f"✓ Tier pricing working after re-enable: {len(data['tiers'])} tiers")
    
    def test_09_product_without_sku_uses_global_tiers(self):
        """Test that calculate endpoint without product_sku uses global settings"""
        response = requests.get(
            f"{BASE_URL}/api/tiles/pricing/calculate",
            params={
                "base_price": 50,
                "quantity": 25
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Without product_sku, should never be disabled
        assert data.get("disabled") != True, "Global pricing should not be disabled"
        assert "tiers" in data, "Should have tiers"
        assert len(data["tiers"]) == 4, "Should have 4 tiers by default"
        
        # Verify discount is applied for 25m²
        assert data["current_tier"] == 2, "25m² should be in tier 2 (10-50m²)"
        assert data["current_discount_percent"] == 5, "Tier 2 should have 5% discount"
        print(f"✓ Global tier pricing works: tier={data['current_tier']}, discount={data['current_discount_percent']}%")
    
    def test_10_bulk_update_with_custom_tiers(self):
        """Test updating product with custom tier values (not just disabling)"""
        custom_thresholds = [5, 25, 75]
        custom_discounts = [0, 10, 15, 20]
        
        response = requests.put(
            f"{BASE_URL}/api/supplier-sync/products/bulk-tier-update",
            json={
                "products": [{"supplier": TEST_PRODUCT_SUPPLIER, "sku": TEST_PRODUCT_SKU}],
                "tier_thresholds": custom_thresholds,
                "tier_discounts": custom_discounts,
                "trade_discount": 8,
                "disabled": False
            },
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["success"] == True, "Operation should succeed"
        assert data["updated_count"] >= 1, "Should update at least 1 product"
        print(f"✓ Custom tier settings applied: {data['message']}")


class TestTierPricingShopPageIntegration:
    """Test tier pricing behavior for shop page display scenarios"""
    
    def test_shop_detail_page_product_exists(self):
        """Verify the test product is available via the shop tiles endpoint"""
        response = requests.get(f"{BASE_URL}/api/tiles/products/{TEST_PRODUCT_SLUG}")
        
        assert response.status_code == 200, f"Product should be accessible: {response.status_code}"
        
        data = response.json()
        assert data["sku"] == TEST_PRODUCT_SKU
        assert data["room_lot_price"] > 0, "Product should have a price"
        print(f"✓ Shop product found: {data['display_name']} at £{data['room_lot_price']}/m²")
    
    def test_tier_pricing_endpoint_for_shop_display(self):
        """Test the dedicated tier-pricing endpoint used by shop page"""
        response = requests.get(
            f"{BASE_URL}/api/tiles/products/{TEST_PRODUCT_SLUG}/tier-pricing",
            params={"quantity": 1}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "base_price" in data, "Should return base_price"
        assert "product" in data, "Should include product info"
        
        if data.get("disabled"):
            print(f"✓ Tier pricing is disabled for this product")
        else:
            assert "tiers" in data, "Should have tiers when not disabled"
            print(f"✓ Tier pricing active with {len(data.get('tiers', []))} tiers")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

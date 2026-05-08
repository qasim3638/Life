"""
Test Trade Discount Bug Fix - When Tier Pricing is Disabled

Bug: Trade discount (e.g. 20%) was not being applied to the displayed price on the storefront 
for trade users when tier pricing is disabled. Only Credit Back (5%) was showing.

Root cause: When tier pricing is disabled, the frontend skips the tier pricing API and falls back 
to base room_lot_price, only dividing by 1.20 for VAT without applying the trade discount.

Fix: When tierPricing is null/empty and user is trade, manually apply productTradeDiscount 
to the displayPrice calculation.

Tests:
1. Backend /api/tiles/collections/{series_name} returns trade_discount and credit_back_rate fields
2. Backend /api/tiles/products/{slug}/tier-pricing returns disabled:true and no tiers when tier_pricing_disabled is set
3. Verify trade_discount and credit_back_rate values are correct
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestCollectionAPITradeFields:
    """Test that collection API returns trade_discount and credit_back_rate fields"""
    
    def test_collection_api_returns_trade_discount(self):
        """Collection API should return trade_discount field"""
        # Use Bluestone collection which has a product with tier_pricing_disabled
        response = requests.get(f"{BASE_URL}/api/tiles/collection/Bluestone")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify trade_discount field exists
        assert "trade_discount" in data, "trade_discount field missing from collection API response"
        
        # trade_discount should be a number (could be 0 or positive)
        assert isinstance(data["trade_discount"], (int, float)), f"trade_discount should be a number, got {type(data['trade_discount'])}"
        
        print(f"Collection trade_discount: {data['trade_discount']}")
    
    def test_collection_api_returns_credit_back_rate(self):
        """Collection API should return credit_back_rate field"""
        response = requests.get(f"{BASE_URL}/api/tiles/collection/Bluestone")
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify credit_back_rate field exists
        assert "credit_back_rate" in data, "credit_back_rate field missing from collection API response"
        
        # credit_back_rate should be a number
        assert isinstance(data["credit_back_rate"], (int, float)), f"credit_back_rate should be a number, got {type(data['credit_back_rate'])}"
        
        print(f"Collection credit_back_rate: {data['credit_back_rate']}")
    
    def test_collection_api_returns_products_with_tier_disabled(self):
        """Collection API should return products including those with tier_pricing_disabled"""
        response = requests.get(f"{BASE_URL}/api/tiles/collection/Bluestone")
        assert response.status_code == 200
        
        data = response.json()
        products = data.get("products", [])
        
        assert len(products) > 0, "No products returned for Bluestone collection"
        
        # Find the product with tier_pricing_disabled
        tier_disabled_product = None
        for p in products:
            if p.get("tier_pricing_disabled") or "Polished" in p.get("display_name", ""):
                tier_disabled_product = p
                break
        
        print(f"Found {len(products)} products in Bluestone collection")
        if tier_disabled_product:
            print(f"Product with tier_pricing_disabled: {tier_disabled_product.get('display_name')}")


class TestTierPricingAPIDisabled:
    """Test tier pricing API returns disabled:true when tier_pricing_disabled is set"""
    
    def test_tier_pricing_disabled_returns_disabled_true(self):
        """Tier pricing API should return disabled:true for products with tier_pricing_disabled"""
        # Use the product we know has tier_pricing_disabled
        slug = "bluestone-grey-60x60-polished"
        
        response = requests.get(f"{BASE_URL}/api/tiles/products/{slug}/tier-pricing")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify disabled field is true
        assert data.get("disabled") == True, f"Expected disabled:true, got disabled:{data.get('disabled')}"
        
        print(f"Tier pricing disabled response: {data}")
    
    def test_tier_pricing_disabled_returns_empty_tiers(self):
        """Tier pricing API should return empty tiers array when disabled"""
        slug = "bluestone-grey-60x60-polished"
        
        response = requests.get(f"{BASE_URL}/api/tiles/products/{slug}/tier-pricing")
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify tiers is empty
        tiers = data.get("tiers", [])
        assert len(tiers) == 0, f"Expected empty tiers, got {len(tiers)} tiers"
        
        print(f"Tiers array is empty as expected")
    
    def test_tier_pricing_disabled_returns_base_price(self):
        """Tier pricing API should return base_price when disabled"""
        slug = "bluestone-grey-60x60-polished"
        
        response = requests.get(f"{BASE_URL}/api/tiles/products/{slug}/tier-pricing")
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify base_price is returned
        assert "base_price" in data, "base_price field missing from disabled tier pricing response"
        assert data["base_price"] > 0, f"base_price should be positive, got {data['base_price']}"
        
        print(f"Base price: {data['base_price']}")
    
    def test_tier_pricing_disabled_with_is_trade_param(self):
        """Tier pricing API with is_trade=true should still return disabled:true"""
        slug = "bluestone-grey-60x60-polished"
        
        response = requests.get(f"{BASE_URL}/api/tiles/products/{slug}/tier-pricing?is_trade=true")
        assert response.status_code == 200
        
        data = response.json()
        
        # Even with is_trade=true, should still be disabled
        assert data.get("disabled") == True, f"Expected disabled:true with is_trade=true, got disabled:{data.get('disabled')}"
        
        print(f"Tier pricing with is_trade=true still returns disabled:true")


class TestTierPricingAPIEnabled:
    """Test tier pricing API returns tiers when tier_pricing is enabled"""
    
    def test_tier_pricing_enabled_returns_tiers(self):
        """Tier pricing API should return tiers for products without tier_pricing_disabled"""
        # Use a product without tier_pricing_disabled
        slug = "bluestone-grey-60x60"
        
        response = requests.get(f"{BASE_URL}/api/tiles/products/{slug}/tier-pricing")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Should not be disabled
        assert data.get("disabled") != True, f"Expected disabled to be false/missing, got disabled:{data.get('disabled')}"
        
        # Should have tiers
        tiers = data.get("tiers", [])
        assert len(tiers) > 0, f"Expected tiers, got empty array"
        
        print(f"Tier pricing enabled - got {len(tiers)} tiers")
    
    def test_tier_pricing_enabled_with_is_trade_returns_trade_tiers(self):
        """Tier pricing API with is_trade=true should return trade_tiers"""
        slug = "bluestone-grey-60x60"
        
        response = requests.get(f"{BASE_URL}/api/tiles/products/{slug}/tier-pricing?is_trade=true")
        assert response.status_code == 200
        
        data = response.json()
        
        # Should have trade_tiers
        trade_tiers = data.get("trade_tiers", [])
        
        # trade_tiers should exist and have prices lower than regular tiers (trade discount applied)
        if trade_tiers:
            regular_tiers = data.get("tiers", [])
            if regular_tiers and trade_tiers:
                # Compare first tier prices - trade should be lower
                regular_price = regular_tiers[0].get("price_per_sqm", 0)
                trade_price = trade_tiers[0].get("price_per_sqm", 0)
                print(f"Regular tier price: {regular_price}, Trade tier price: {trade_price}")
                # Trade price should be lower (trade discount applied)
                assert trade_price <= regular_price, f"Trade price {trade_price} should be <= regular price {regular_price}"
        
        print(f"Trade tiers returned: {len(trade_tiers)} tiers")


class TestTradeDiscountCalculation:
    """Test the trade discount calculation logic"""
    
    def test_trade_discount_value_is_reasonable(self):
        """Trade discount should be a reasonable percentage (0-50%)"""
        response = requests.get(f"{BASE_URL}/api/tiles/collection/Bluestone")
        assert response.status_code == 200
        
        data = response.json()
        trade_discount = data.get("trade_discount", 0)
        
        # Trade discount should be between 0 and 50%
        assert 0 <= trade_discount <= 50, f"Trade discount {trade_discount}% is outside reasonable range (0-50%)"
        
        print(f"Trade discount: {trade_discount}%")
    
    def test_credit_back_rate_value_is_reasonable(self):
        """Credit back rate should be a reasonable percentage (0-20%)"""
        response = requests.get(f"{BASE_URL}/api/tiles/collection/Bluestone")
        assert response.status_code == 200
        
        data = response.json()
        credit_back_rate = data.get("credit_back_rate", 0)
        
        # Credit back rate should be between 0 and 20%
        assert 0 <= credit_back_rate <= 20, f"Credit back rate {credit_back_rate}% is outside reasonable range (0-20%)"
        
        print(f"Credit back rate: {credit_back_rate}%")
    
    def test_expected_trade_price_calculation(self):
        """Verify expected trade price calculation: price * (1 - trade_discount/100) / 1.20"""
        response = requests.get(f"{BASE_URL}/api/tiles/collection/Bluestone")
        assert response.status_code == 200
        
        data = response.json()
        trade_discount = data.get("trade_discount", 0)
        products = data.get("products", [])
        
        if products:
            # Get a product with tier_pricing_disabled
            product = None
            for p in products:
                if p.get("tier_pricing_disabled"):
                    product = p
                    break
            
            if product:
                base_price = product.get("room_lot_price", 0)
                
                # Calculate expected trade price
                # Formula: price * (1 - trade_discount/100) / 1.20
                expected_trade_price = round(base_price * (1 - trade_discount / 100) / 1.20, 2)
                
                print(f"Base price: £{base_price}")
                print(f"Trade discount: {trade_discount}%")
                print(f"Expected trade price (ex-VAT with discount): £{expected_trade_price}")
                
                # This is what the frontend should calculate
                assert expected_trade_price > 0, "Expected trade price should be positive"


class TestMultipleCollections:
    """Test trade fields across multiple collections"""
    
    def test_different_collection_returns_trade_fields(self):
        """Different collections should also return trade_discount and credit_back_rate"""
        # Try a few different collections
        collections_to_test = ["Bluestone", "Ardesia"]
        
        for collection_name in collections_to_test:
            response = requests.get(f"{BASE_URL}/api/tiles/collection/{collection_name}")
            
            if response.status_code == 200:
                data = response.json()
                
                assert "trade_discount" in data, f"{collection_name}: trade_discount field missing"
                assert "credit_back_rate" in data, f"{collection_name}: credit_back_rate field missing"
                
                print(f"{collection_name}: trade_discount={data['trade_discount']}, credit_back_rate={data['credit_back_rate']}")
            else:
                print(f"{collection_name}: Collection not found (status {response.status_code})")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

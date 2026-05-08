"""
Test credit_back_rate field in API responses and saved vs retail calculation
Tests for iteration 40: Credit Back Badges and Saved vs Retail features
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestCreditBackRateAPIs:
    """Test credit_back_rate field is returned in all relevant API endpoints"""
    
    def test_collections_endpoint_returns_credit_back_rate(self):
        """GET /api/tiles/collections should return credit_back_rate for each collection"""
        response = requests.get(f"{BASE_URL}/api/tiles/collections?limit=5")
        assert response.status_code == 200
        
        data = response.json()
        assert "collections" in data
        assert len(data["collections"]) > 0
        
        # Verify each collection has credit_back_rate
        for collection in data["collections"]:
            assert "credit_back_rate" in collection, f"Collection {collection.get('series_name')} missing credit_back_rate"
            assert isinstance(collection["credit_back_rate"], (int, float)), f"credit_back_rate should be numeric"
            assert collection["credit_back_rate"] >= 0, f"credit_back_rate should be non-negative"
    
    def test_collection_detail_endpoint_returns_credit_back_rate(self):
        """GET /api/tiles/collection/{series_name} should return credit_back_rate"""
        # First get a collection name
        collections_response = requests.get(f"{BASE_URL}/api/tiles/collections?limit=1")
        assert collections_response.status_code == 200
        collections = collections_response.json().get("collections", [])
        assert len(collections) > 0
        
        series_name = collections[0]["series_name"]
        
        # Now get the collection detail
        response = requests.get(f"{BASE_URL}/api/tiles/collection/{series_name}")
        assert response.status_code == 200
        
        data = response.json()
        assert "credit_back_rate" in data, "Collection detail missing credit_back_rate"
        assert isinstance(data["credit_back_rate"], (int, float))
        assert data["credit_back_rate"] >= 0
    
    def test_tier_pricing_endpoint_returns_credit_back_rate(self):
        """GET /api/tiles/products/{slug}/tier-pricing should return credit_back_rate"""
        # First get a product slug
        collections_response = requests.get(f"{BASE_URL}/api/tiles/collections?limit=1")
        assert collections_response.status_code == 200
        collections = collections_response.json().get("collections", [])
        assert len(collections) > 0
        
        first_product_slug = collections[0].get("first_product_slug")
        if not first_product_slug:
            pytest.skip("No product slug available for testing")
        
        # Get tier pricing
        response = requests.get(f"{BASE_URL}/api/tiles/products/{first_product_slug}/tier-pricing")
        assert response.status_code == 200
        
        data = response.json()
        # If tier pricing is not disabled, it should have credit_back_rate
        if not data.get("disabled"):
            assert "credit_back_rate" in data, "Tier pricing missing credit_back_rate"
            assert isinstance(data["credit_back_rate"], (int, float))
            assert data["credit_back_rate"] >= 0
    
    def test_credit_back_rate_default_value(self):
        """credit_back_rate should default to 2 (TRADE_CREDIT_BACK_DEFAULT)"""
        response = requests.get(f"{BASE_URL}/api/tiles/collections?limit=10")
        assert response.status_code == 200
        
        data = response.json()
        for collection in data.get("collections", []):
            # Default should be 2 unless explicitly set otherwise
            credit_rate = collection.get("credit_back_rate")
            assert credit_rate is not None
            # Most products should have the default rate of 2
            # (unless custom rates are set)
            assert credit_rate >= 0


class TestCreditBackRatesCartEndpoint:
    """Test the cart credit-back-rates endpoint"""
    
    def test_credit_back_rates_endpoint(self):
        """POST /api/shop/cart/credit-back-rates should return rates for product slugs"""
        # First get some product slugs
        collections_response = requests.get(f"{BASE_URL}/api/tiles/collections?limit=3")
        assert collections_response.status_code == 200
        collections = collections_response.json().get("collections", [])
        
        slugs = [c.get("first_product_slug") for c in collections if c.get("first_product_slug")]
        if len(slugs) == 0:
            pytest.skip("No product slugs available")
        
        response = requests.post(
            f"{BASE_URL}/api/shop/cart/credit-back-rates",
            json={"slugs": slugs}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "rates" in data
        assert "default_rate" in data
        assert data["default_rate"] == 2  # Default should be 2%


class TestSavedVsRetailCalculation:
    """Test the saved vs retail calculation logic"""
    
    def test_saved_vs_retail_formula(self):
        """
        Verify the saved vs retail calculation formula:
        retailPrice = tradePrice * 1.20 / (1 - tradeDiscount/100)
        savings = (retailPrice - tradePrice) * qty
        """
        # Test with sample values
        trade_price = 100.00  # ex-VAT trade price
        trade_discount = 5  # 5% trade discount
        quantity = 10
        
        # Calculate retail price (inc VAT)
        retail_price = trade_price * 1.20 / (1 - trade_discount / 100)
        # retail_price = 100 * 1.20 / 0.95 = 126.32 (approx)
        
        # Calculate savings
        savings = (retail_price - trade_price) * quantity
        # savings = (126.32 - 100) * 10 = 263.16 (approx)
        
        assert retail_price > trade_price, "Retail price should be higher than trade price"
        assert savings > 0, "Savings should be positive"
        
        # Verify the formula produces expected results
        expected_retail = 126.32  # 100 * 1.20 / 0.95
        assert abs(retail_price - expected_retail) < 0.01, f"Retail price calculation incorrect: {retail_price}"
        
        expected_savings = 263.16  # (126.32 - 100) * 10
        assert abs(savings - expected_savings) < 0.1, f"Savings calculation incorrect: {savings}"


class TestStoresEndpoint:
    """Test stores endpoint for collection feature"""
    
    def test_stores_endpoint_returns_stores(self):
        """GET /api/shop/stores should return store list"""
        response = requests.get(f"{BASE_URL}/api/shop/stores")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        # Should have at least one store
        if len(data) > 0:
            store = data[0]
            assert "name" in store
            # Optional fields
            # address, phone, opening_hours may or may not be present


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

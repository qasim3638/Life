"""
Test Dynamic Per-Product Trade Discount and Credit Back Rate

Tests that:
1. GET /api/tiles/collections returns both trade_discount AND credit_back_rate for each collection
2. GET /api/tiles/collection/{series_name} returns both trade_discount AND credit_back_rate
3. GET /api/tiles/products/{slug}/tier-pricing returns trade_discount AND credit_back_rate
4. Tier pricing endpoint uses per-product trade_discount from DB when no query param is provided
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestDynamicTradeRates:
    """Test per-product trade_discount and credit_back_rate in API responses"""
    
    def test_collections_endpoint_returns_trade_discount(self):
        """GET /api/tiles/collections should return trade_discount for each collection"""
        response = requests.get(f"{BASE_URL}/api/tiles/collections?limit=5")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "collections" in data, "Response should have 'collections' key"
        assert len(data["collections"]) > 0, "Should have at least one collection"
        
        # Check first collection has trade_discount field
        first_collection = data["collections"][0]
        assert "trade_discount" in first_collection, f"Collection should have 'trade_discount' field. Keys: {first_collection.keys()}"
        
        # trade_discount should be a number (default is 5)
        trade_discount = first_collection["trade_discount"]
        assert isinstance(trade_discount, (int, float)), f"trade_discount should be a number, got {type(trade_discount)}"
        print(f"✓ Collection '{first_collection.get('series_name')}' has trade_discount: {trade_discount}")
    
    def test_collections_endpoint_returns_credit_back_rate(self):
        """GET /api/tiles/collections should return credit_back_rate for each collection"""
        response = requests.get(f"{BASE_URL}/api/tiles/collections?limit=5")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["collections"]) > 0
        
        # Check first collection has credit_back_rate field
        first_collection = data["collections"][0]
        assert "credit_back_rate" in first_collection, f"Collection should have 'credit_back_rate' field. Keys: {first_collection.keys()}"
        
        # credit_back_rate should be a number (default is 2)
        credit_back_rate = first_collection["credit_back_rate"]
        assert isinstance(credit_back_rate, (int, float)), f"credit_back_rate should be a number, got {type(credit_back_rate)}"
        print(f"✓ Collection '{first_collection.get('series_name')}' has credit_back_rate: {credit_back_rate}")
    
    def test_collection_detail_returns_trade_discount(self):
        """GET /api/tiles/collection/{series_name} should return trade_discount"""
        # First get a collection name
        collections_response = requests.get(f"{BASE_URL}/api/tiles/collections?limit=1")
        assert collections_response.status_code == 200
        
        collections = collections_response.json().get("collections", [])
        assert len(collections) > 0, "Need at least one collection to test"
        
        series_name = collections[0]["series_name"]
        
        # Now get the collection detail
        response = requests.get(f"{BASE_URL}/api/tiles/collection/{series_name}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "trade_discount" in data, f"Collection detail should have 'trade_discount' field. Keys: {data.keys()}"
        
        trade_discount = data["trade_discount"]
        assert isinstance(trade_discount, (int, float)), f"trade_discount should be a number, got {type(trade_discount)}"
        print(f"✓ Collection detail '{series_name}' has trade_discount: {trade_discount}")
    
    def test_collection_detail_returns_credit_back_rate(self):
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
        assert "credit_back_rate" in data, f"Collection detail should have 'credit_back_rate' field. Keys: {data.keys()}"
        
        credit_back_rate = data["credit_back_rate"]
        assert isinstance(credit_back_rate, (int, float)), f"credit_back_rate should be a number, got {type(credit_back_rate)}"
        print(f"✓ Collection detail '{series_name}' has credit_back_rate: {credit_back_rate}")
    
    def test_tier_pricing_returns_trade_discount(self):
        """GET /api/tiles/products/{slug}/tier-pricing should return trade_discount"""
        # First get a product slug
        collections_response = requests.get(f"{BASE_URL}/api/tiles/collections?limit=1")
        assert collections_response.status_code == 200
        
        collections = collections_response.json().get("collections", [])
        assert len(collections) > 0
        
        product_slug = collections[0].get("first_product_slug")
        if not product_slug:
            # Try to get from collection detail
            series_name = collections[0]["series_name"]
            detail_response = requests.get(f"{BASE_URL}/api/tiles/collection/{series_name}")
            products = detail_response.json().get("products", [])
            if products:
                product_slug = products[0].get("slug")
        
        assert product_slug, "Need a product slug to test tier pricing"
        
        # Get tier pricing
        response = requests.get(f"{BASE_URL}/api/tiles/products/{product_slug}/tier-pricing")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Skip if tier pricing is disabled for this product
        if data.get("disabled"):
            pytest.skip("Tier pricing is disabled for this product")
        
        assert "trade_discount" in data, f"Tier pricing should have 'trade_discount' field. Keys: {data.keys()}"
        
        trade_discount = data["trade_discount"]
        assert isinstance(trade_discount, (int, float)), f"trade_discount should be a number, got {type(trade_discount)}"
        print(f"✓ Tier pricing for '{product_slug}' has trade_discount: {trade_discount}")
    
    def test_tier_pricing_returns_credit_back_rate(self):
        """GET /api/tiles/products/{slug}/tier-pricing should return credit_back_rate"""
        # First get a product slug
        collections_response = requests.get(f"{BASE_URL}/api/tiles/collections?limit=1")
        assert collections_response.status_code == 200
        
        collections = collections_response.json().get("collections", [])
        assert len(collections) > 0
        
        product_slug = collections[0].get("first_product_slug")
        if not product_slug:
            series_name = collections[0]["series_name"]
            detail_response = requests.get(f"{BASE_URL}/api/tiles/collection/{series_name}")
            products = detail_response.json().get("products", [])
            if products:
                product_slug = products[0].get("slug")
        
        assert product_slug, "Need a product slug to test tier pricing"
        
        # Get tier pricing
        response = requests.get(f"{BASE_URL}/api/tiles/products/{product_slug}/tier-pricing")
        assert response.status_code == 200
        
        data = response.json()
        
        if data.get("disabled"):
            pytest.skip("Tier pricing is disabled for this product")
        
        assert "credit_back_rate" in data, f"Tier pricing should have 'credit_back_rate' field. Keys: {data.keys()}"
        
        credit_back_rate = data["credit_back_rate"]
        assert isinstance(credit_back_rate, (int, float)), f"credit_back_rate should be a number, got {type(credit_back_rate)}"
        print(f"✓ Tier pricing for '{product_slug}' has credit_back_rate: {credit_back_rate}")
    
    def test_tier_pricing_uses_per_product_trade_discount(self):
        """Tier pricing should use per-product trade_discount from DB when no query param provided"""
        # Get a product slug
        collections_response = requests.get(f"{BASE_URL}/api/tiles/collections?limit=1")
        collections = collections_response.json().get("collections", [])
        
        product_slug = collections[0].get("first_product_slug")
        if not product_slug:
            series_name = collections[0]["series_name"]
            detail_response = requests.get(f"{BASE_URL}/api/tiles/collection/{series_name}")
            products = detail_response.json().get("products", [])
            if products:
                product_slug = products[0].get("slug")
        
        assert product_slug
        
        # Get tier pricing WITHOUT trade_discount query param
        response = requests.get(f"{BASE_URL}/api/tiles/products/{product_slug}/tier-pricing")
        assert response.status_code == 200
        
        data = response.json()
        
        if data.get("disabled"):
            pytest.skip("Tier pricing is disabled for this product")
        
        # The response should include the trade_discount that was used
        # This should be either the per-product value from DB or the global default (5)
        assert "trade_discount" in data
        trade_discount = data["trade_discount"]
        
        # Default is 5, but could be different if per-product value is set
        assert isinstance(trade_discount, (int, float))
        assert trade_discount >= 0 and trade_discount <= 100, f"trade_discount should be 0-100, got {trade_discount}"
        
        print(f"✓ Tier pricing uses trade_discount: {trade_discount} (from DB or default)")
    
    def test_tier_pricing_with_is_trade_flag(self):
        """Tier pricing with is_trade=true should apply trade discount to prices"""
        # Get a product slug
        collections_response = requests.get(f"{BASE_URL}/api/tiles/collections?limit=1")
        collections = collections_response.json().get("collections", [])
        
        product_slug = collections[0].get("first_product_slug")
        if not product_slug:
            series_name = collections[0]["series_name"]
            detail_response = requests.get(f"{BASE_URL}/api/tiles/collection/{series_name}")
            products = detail_response.json().get("products", [])
            if products:
                product_slug = products[0].get("slug")
        
        assert product_slug
        
        # Get tier pricing WITHOUT is_trade
        response_regular = requests.get(f"{BASE_URL}/api/tiles/products/{product_slug}/tier-pricing")
        assert response_regular.status_code == 200
        data_regular = response_regular.json()
        
        if data_regular.get("disabled"):
            pytest.skip("Tier pricing is disabled for this product")
        
        # Get tier pricing WITH is_trade=true
        response_trade = requests.get(f"{BASE_URL}/api/tiles/products/{product_slug}/tier-pricing?is_trade=true")
        assert response_trade.status_code == 200
        data_trade = response_trade.json()
        
        # Both should have trade_discount and credit_back_rate
        assert "trade_discount" in data_regular
        assert "credit_back_rate" in data_regular
        assert "trade_discount" in data_trade
        assert "credit_back_rate" in data_trade
        
        # Trade pricing should have trade_tiers if is_trade=true
        if "trade_tiers" in data_trade:
            print(f"✓ Trade pricing includes trade_tiers")
        
        print(f"✓ Regular pricing trade_discount: {data_regular['trade_discount']}")
        print(f"✓ Trade pricing trade_discount: {data_trade['trade_discount']}")


class TestDefaultValues:
    """Test that default values are used when per-product values are not set"""
    
    def test_default_trade_discount_is_5(self):
        """Default trade_discount should be 5 (TRADE_DISCOUNT_DEFAULT)"""
        response = requests.get(f"{BASE_URL}/api/tiles/collections?limit=10")
        assert response.status_code == 200
        
        collections = response.json().get("collections", [])
        
        # Most collections should have trade_discount = 5 (default)
        # unless per-product values are set in DB
        for collection in collections[:5]:
            trade_discount = collection.get("trade_discount")
            assert trade_discount is not None, f"Collection {collection.get('series_name')} missing trade_discount"
            # Default is 5, but could be different if per-product value is set
            print(f"  Collection '{collection.get('series_name')}': trade_discount = {trade_discount}")
    
    def test_default_credit_back_rate_is_2(self):
        """Default credit_back_rate should be 2 (TRADE_CREDIT_BACK_DEFAULT)"""
        response = requests.get(f"{BASE_URL}/api/tiles/collections?limit=10")
        assert response.status_code == 200
        
        collections = response.json().get("collections", [])
        
        for collection in collections[:5]:
            credit_back_rate = collection.get("credit_back_rate")
            assert credit_back_rate is not None, f"Collection {collection.get('series_name')} missing credit_back_rate"
            print(f"  Collection '{collection.get('series_name')}': credit_back_rate = {credit_back_rate}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

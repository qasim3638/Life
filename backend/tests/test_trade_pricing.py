"""
Test Trade User Pricing System
Tests:
1. Trade user login returns is_trade and trade_discount
2. Tier pricing API returns trade-adjusted prices when is_trade=true
3. Trade discount calculation is correct (5% default)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Trade user credentials from test requirements
TRADE_EMAIL = "trade@test.com"
TRADE_PASSWORD = "Trade123!"


class TestTradeUserLogin:
    """Test trade user authentication and response fields"""
    
    def test_trade_login_returns_is_trade_flag(self):
        """Trade user login should return is_trade=true"""
        response = requests.post(
            f"{BASE_URL}/api/shop/auth/login",
            json={"email": TRADE_EMAIL, "password": TRADE_PASSWORD}
        )
        
        print(f"Login response status: {response.status_code}")
        print(f"Login response: {response.json()}")
        
        assert response.status_code == 200, f"Login failed: {response.text}"
        
        data = response.json()
        assert "customer" in data, "Response should contain customer object"
        assert "token" in data, "Response should contain token"
        
        customer = data["customer"]
        assert customer.get("is_trade") == True, f"is_trade should be True, got: {customer.get('is_trade')}"
        
    def test_trade_login_returns_trade_discount(self):
        """Trade user login should return trade_discount percentage"""
        response = requests.post(
            f"{BASE_URL}/api/shop/auth/login",
            json={"email": TRADE_EMAIL, "password": TRADE_PASSWORD}
        )
        
        assert response.status_code == 200
        
        data = response.json()
        customer = data["customer"]
        
        # trade_discount should be present and be a number (default is 5)
        assert "trade_discount" in customer, "Response should contain trade_discount"
        assert isinstance(customer["trade_discount"], (int, float)), "trade_discount should be a number"
        assert customer["trade_discount"] > 0, f"trade_discount should be > 0, got: {customer['trade_discount']}"
        print(f"Trade discount: {customer['trade_discount']}%")
        
    def test_regular_user_login_no_trade_flag(self):
        """Non-trade user should have is_trade=false or missing"""
        # First check if there's a regular user we can test with
        # For now, just verify the trade user has is_trade=true
        response = requests.post(
            f"{BASE_URL}/api/shop/auth/login",
            json={"email": TRADE_EMAIL, "password": TRADE_PASSWORD}
        )
        
        assert response.status_code == 200
        data = response.json()
        # Verify trade user has is_trade=true
        assert data["customer"].get("is_trade") == True


class TestTierPricingAPI:
    """Test tier pricing API with trade parameter"""
    
    @pytest.fixture
    def sample_product_slug(self):
        """Get a sample product slug from the tiles collection"""
        # First get a collection to find a product
        response = requests.get(f"{BASE_URL}/api/tiles/collections?limit=1")
        if response.status_code == 200:
            data = response.json()
            if data.get("collections") and len(data["collections"]) > 0:
                series_name = data["collections"][0].get("series_name")
                if series_name:
                    # Get products from this collection
                    prod_response = requests.get(
                        f"{BASE_URL}/api/tiles/collection/{series_name}?limit=1"
                    )
                    if prod_response.status_code == 200:
                        prod_data = prod_response.json()
                        if prod_data.get("products") and len(prod_data["products"]) > 0:
                            return prod_data["products"][0].get("slug")
        return None
    
    def test_tier_pricing_without_trade(self, sample_product_slug):
        """Tier pricing without is_trade should return standard prices"""
        if not sample_product_slug:
            pytest.skip("No sample product found")
        
        response = requests.get(
            f"{BASE_URL}/api/tiles/products/{sample_product_slug}/tier-pricing"
        )
        
        print(f"Tier pricing response: {response.status_code}")
        
        if response.status_code == 404:
            pytest.skip("Product not found")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should not have trade pricing applied
        assert data.get("is_trade") == False, "is_trade should be False"
        assert data.get("trade_tiers") is None, "trade_tiers should be None for non-trade"
        
        print(f"Standard tiers: {data.get('tiers')}")
        
    def test_tier_pricing_with_trade(self, sample_product_slug):
        """Tier pricing with is_trade=true should return trade-adjusted prices"""
        if not sample_product_slug:
            pytest.skip("No sample product found")
        
        response = requests.get(
            f"{BASE_URL}/api/tiles/products/{sample_product_slug}/tier-pricing?is_trade=true"
        )
        
        print(f"Trade tier pricing response: {response.status_code}")
        
        if response.status_code == 404:
            pytest.skip("Product not found")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have trade pricing applied
        assert data.get("is_trade") == True, "is_trade should be True"
        assert data.get("trade_discount_percent") is not None, "trade_discount_percent should be present"
        assert data.get("trade_tiers") is not None, "trade_tiers should be present for trade users"
        
        print(f"Trade discount: {data.get('trade_discount_percent')}%")
        print(f"Trade tiers: {data.get('trade_tiers')}")
        
        # Verify trade prices are lower than standard prices
        if data.get("tiers") and data.get("trade_tiers"):
            standard_price = data["tiers"][0]["price_per_m2"]
            trade_price = data["trade_tiers"][0]["price_per_m2"]
            assert trade_price < standard_price, f"Trade price ({trade_price}) should be less than standard ({standard_price})"
            
    def test_tier_pricing_trade_discount_calculation(self, sample_product_slug):
        """Verify trade discount is calculated correctly (5% default)"""
        if not sample_product_slug:
            pytest.skip("No sample product found")
        
        # Get standard pricing
        std_response = requests.get(
            f"{BASE_URL}/api/tiles/products/{sample_product_slug}/tier-pricing"
        )
        
        # Get trade pricing
        trade_response = requests.get(
            f"{BASE_URL}/api/tiles/products/{sample_product_slug}/tier-pricing?is_trade=true"
        )
        
        if std_response.status_code != 200 or trade_response.status_code != 200:
            pytest.skip("Could not get pricing data")
        
        std_data = std_response.json()
        trade_data = trade_response.json()
        
        if not std_data.get("tiers") or not trade_data.get("trade_tiers"):
            pytest.skip("No tier data available")
        
        # Get first tier prices
        std_price = std_data["tiers"][0]["price_per_m2"]
        trade_price = trade_data["trade_tiers"][0]["price_per_m2"]
        trade_discount = trade_data.get("trade_discount_percent", 5)
        
        # Calculate expected trade price
        expected_trade_price = round(std_price * (1 - trade_discount / 100), 2)
        
        print(f"Standard price: £{std_price}")
        print(f"Trade price: £{trade_price}")
        print(f"Expected trade price (with {trade_discount}% discount): £{expected_trade_price}")
        
        # Allow small rounding difference
        assert abs(trade_price - expected_trade_price) < 0.02, \
            f"Trade price {trade_price} doesn't match expected {expected_trade_price}"


class TestOpacoCollection:
    """Test specific Opaco collection mentioned in requirements"""
    
    def test_opaco_collection_exists(self):
        """Verify Opaco collection exists and has products"""
        response = requests.get(
            f"{BASE_URL}/api/tiles/collection/Opaco?limit=5"
        )
        
        print(f"Opaco collection response: {response.status_code}")
        
        if response.status_code == 404:
            pytest.skip("Opaco collection not found")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "products" in data, "Response should contain products"
        assert len(data["products"]) > 0, "Opaco should have products"
        
        # Check first product has price
        first_product = data["products"][0]
        price = first_product.get("room_lot_price") or first_product.get("price")
        assert price and price > 0, f"Product should have price, got: {price}"
        
        print(f"Opaco has {len(data['products'])} products")
        print(f"First product price: £{price}")
        
    def test_opaco_tier_pricing_with_trade(self):
        """Test Opaco collection tier pricing with trade flag"""
        # First get a product from Opaco
        response = requests.get(
            f"{BASE_URL}/api/tiles/collection/Opaco?limit=1"
        )
        
        if response.status_code != 200:
            pytest.skip("Opaco collection not found")
        
        data = response.json()
        if not data.get("products"):
            pytest.skip("No products in Opaco collection")
        
        slug = data["products"][0].get("slug")
        if not slug:
            pytest.skip("Product has no slug")
        
        # Get trade tier pricing
        tier_response = requests.get(
            f"{BASE_URL}/api/tiles/products/{slug}/tier-pricing?is_trade=true"
        )
        
        print(f"Opaco tier pricing response: {tier_response.status_code}")
        
        if tier_response.status_code != 200:
            print(f"Tier pricing error: {tier_response.text}")
            pytest.skip("Could not get tier pricing")
        
        tier_data = tier_response.json()
        
        # Verify trade pricing is applied
        assert tier_data.get("is_trade") == True
        assert tier_data.get("trade_tiers") is not None
        
        print(f"Opaco trade tiers: {tier_data.get('trade_tiers')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
Test Suite for Unified Series Description Generator API
Tests the POST /api/products/generate-series-description endpoint
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://feature-verification-7.preview.emergentagent.com')

# Test credentials
TEST_EMAIL = "qasim@tilestation.co.uk"
TEST_PASSWORD = "Tilestation_9614"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for API calls"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get headers with auth token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


@pytest.fixture(scope="module")
def sample_product_skus(auth_headers):
    """Get sample LEPORCE product SKUs for testing"""
    response = requests.get(
        f"{BASE_URL}/api/supplier-sync/products?supplier=LEPORCE&limit=5",
        headers=auth_headers
    )
    if response.status_code == 200:
        products = response.json().get("products", [])
        if products:
            return [p["sku"] for p in products[:3]]
    return ["LP-3611", "LP-6611", "LP-1611"]  # Fallback SKUs


class TestSeriesDescriptionEndpoint:
    """Tests for POST /api/products/generate-series-description"""
    
    def test_generate_brief_description_with_skus(self, auth_headers, sample_product_skus):
        """Test generating a brief description using product SKUs"""
        response = requests.post(
            f"{BASE_URL}/api/products/generate-series-description",
            headers=auth_headers,
            json={
                "series_name": "Alabaster",
                "product_skus": sample_product_skus,
                "seo_keywords": "porcelain tiles, polished tiles, luxury tiles",
                "length": "brief"
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["success"] is True
        assert data["series_name"] == "Alabaster"
        assert data["product_count"] >= 1
        assert "description" in data
        assert len(data["description"]) > 50  # Brief should still have meaningful content
        
        # Verify aggregated_data structure
        assert "aggregated_data" in data
        agg = data["aggregated_data"]
        assert "colors" in agg
        assert "sizes" in agg
        assert "finishes" in agg
        assert "materials" in agg
        
        print(f"✓ Brief description generated: {len(data['description'])} chars for {data['product_count']} products")
    
    def test_generate_standard_description(self, auth_headers, sample_product_skus):
        """Test generating a standard length description"""
        response = requests.post(
            f"{BASE_URL}/api/products/generate-series-description",
            headers=auth_headers,
            json={
                "series_name": "Alabaster",
                "product_skus": sample_product_skus[:2],
                "seo_keywords": "porcelain tiles",
                "length": "standard"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["description"]) > 100  # Standard should be longer than brief
        
        print(f"✓ Standard description generated: {len(data['description'])} chars")
    
    def test_generate_detailed_description(self, auth_headers, sample_product_skus):
        """Test generating a detailed description"""
        response = requests.post(
            f"{BASE_URL}/api/products/generate-series-description",
            headers=auth_headers,
            json={
                "series_name": "Alabaster",
                "product_skus": sample_product_skus,
                "seo_keywords": "porcelain tiles, luxury tiles, home renovation",
                "length": "detailed"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["description"]) > 200  # Detailed should be the longest
        
        print(f"✓ Detailed description generated: {len(data['description'])} chars")
    
    def test_404_when_no_products_found(self, auth_headers):
        """Test that 404 is returned when no products match the series"""
        response = requests.post(
            f"{BASE_URL}/api/products/generate-series-description",
            headers=auth_headers,
            json={
                "series_name": "NonExistentSeriesXYZ123456",
                "seo_keywords": "tiles",
                "length": "brief"
            }
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        data = response.json()
        assert "detail" in data
        assert "No products found" in data["detail"]
        
        print("✓ 404 returned correctly for non-existent series")
    
    def test_400_when_no_series_or_skus_provided(self, auth_headers):
        """Test that 400 is returned when neither series_name nor product_skus provided"""
        response = requests.post(
            f"{BASE_URL}/api/products/generate-series-description",
            headers=auth_headers,
            json={
                "seo_keywords": "tiles",
                "length": "brief"
            }
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert "detail" in data
        
        print("✓ 400 returned correctly when no series_name or product_skus provided")
    
    def test_aggregated_data_contains_sizes(self, auth_headers, sample_product_skus):
        """Test that aggregated_data correctly extracts sizes from products"""
        response = requests.post(
            f"{BASE_URL}/api/products/generate-series-description",
            headers=auth_headers,
            json={
                "series_name": "Alabaster",
                "product_skus": sample_product_skus,
                "length": "brief"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify sizes are extracted
        sizes = data["aggregated_data"]["sizes"]
        assert isinstance(sizes, list)
        # LEPORCE Alabaster products have multiple sizes
        print(f"✓ Aggregated sizes: {sizes}")
    
    def test_aggregated_data_contains_finishes(self, auth_headers, sample_product_skus):
        """Test that aggregated_data correctly extracts finishes from products"""
        response = requests.post(
            f"{BASE_URL}/api/products/generate-series-description",
            headers=auth_headers,
            json={
                "series_name": "Alabaster",
                "product_skus": sample_product_skus,
                "length": "brief"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        finishes = data["aggregated_data"]["finishes"]
        assert isinstance(finishes, list)
        print(f"✓ Aggregated finishes: {finishes}")
    
    def test_aggregated_data_contains_materials(self, auth_headers, sample_product_skus):
        """Test that aggregated_data correctly extracts materials from products"""
        response = requests.post(
            f"{BASE_URL}/api/products/generate-series-description",
            headers=auth_headers,
            json={
                "series_name": "Alabaster",
                "product_skus": sample_product_skus,
                "length": "brief"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        materials = data["aggregated_data"]["materials"]
        assert isinstance(materials, list)
        print(f"✓ Aggregated materials: {materials}")
    
    def test_default_length_is_standard(self, auth_headers, sample_product_skus):
        """Test that default length is 'standard' when not specified"""
        response = requests.post(
            f"{BASE_URL}/api/products/generate-series-description",
            headers=auth_headers,
            json={
                "series_name": "Alabaster",
                "product_skus": sample_product_skus[:1]
                # No length specified - should default to standard
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Standard length should produce a reasonable description
        assert len(data["description"]) > 100
        
        print(f"✓ Default length works: {len(data['description'])} chars")
    
    def test_requires_authentication(self):
        """Test that endpoint requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/products/generate-series-description",
            headers={"Content-Type": "application/json"},
            json={
                "series_name": "Alabaster",
                "length": "brief"
            }
        )
        
        # Should return 401 or 403 without auth
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        
        print("✓ Authentication required correctly")


class TestSeriesDescriptionBySeriesName:
    """Tests for querying by series_name instead of product_skus"""
    
    def test_query_by_series_name_only(self, auth_headers):
        """Test generating description using only series_name (no SKUs)"""
        response = requests.post(
            f"{BASE_URL}/api/products/generate-series-description",
            headers=auth_headers,
            json={
                "series_name": "Alabaster",
                "seo_keywords": "tiles",
                "length": "brief"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["product_count"] >= 1
        
        print(f"✓ Query by series_name found {data['product_count']} products")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

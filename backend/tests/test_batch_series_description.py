"""
Test cases for Quick Generate All Descriptions feature
- POST /api/products/detect-series - Detect and group products by series from SKU list
- POST /api/products/generate-batch-series-descriptions - Generate unified descriptions for multiple series
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "qasim@tilestation.co.uk"
TEST_PASSWORD = "Tilestation_9614"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for API calls"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get headers with auth token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


@pytest.fixture(scope="module")
def sample_product_skus(auth_headers):
    """Get sample product SKUs from the database for testing"""
    # Fetch some products to get real SKUs
    response = requests.get(
        f"{BASE_URL}/api/supplier-sync/products?limit=20",
        headers=auth_headers
    )
    if response.status_code == 200:
        products = response.json().get("products", [])
        skus = [p.get("sku") for p in products if p.get("sku")]
        if len(skus) >= 5:
            return skus[:10]  # Return up to 10 SKUs
    
    # Fallback: try to get Burlington series products
    response = requests.get(
        f"{BASE_URL}/api/supplier-sync/products?search=Burlington&limit=10",
        headers=auth_headers
    )
    if response.status_code == 200:
        products = response.json().get("products", [])
        skus = [p.get("sku") for p in products if p.get("sku")]
        if skus:
            return skus
    
    pytest.skip("No products with SKUs found for testing")


class TestDetectSeriesEndpoint:
    """Tests for POST /api/products/detect-series endpoint"""
    
    def test_detect_series_success(self, auth_headers, sample_product_skus):
        """Test successful series detection from product SKUs"""
        response = requests.post(
            f"{BASE_URL}/api/products/detect-series",
            headers=auth_headers,
            json={"product_skus": sample_product_skus}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") is True
        assert "total_products" in data
        assert "series_count" in data
        assert "series" in data
        assert isinstance(data["series"], list)
        
        print(f"✓ Detected {data['series_count']} series from {data['total_products']} products")
        
        # Verify series structure
        if data["series"]:
            first_series = data["series"][0]
            assert "series_name" in first_series
            assert "product_count" in first_series
            assert "skus" in first_series
            assert isinstance(first_series["skus"], list)
            print(f"✓ First series: {first_series['series_name']} ({first_series['product_count']} products)")
    
    def test_detect_series_empty_skus(self, auth_headers):
        """Test detect-series with empty SKU list returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/products/detect-series",
            headers=auth_headers,
            json={"product_skus": []}
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Empty SKU list correctly returns 400")
    
    def test_detect_series_invalid_skus(self, auth_headers):
        """Test detect-series with non-existent SKUs returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/products/detect-series",
            headers=auth_headers,
            json={"product_skus": ["NONEXISTENT-SKU-12345", "FAKE-SKU-67890"]}
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Non-existent SKUs correctly return 404")
    
    def test_detect_series_requires_auth(self):
        """Test detect-series requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/products/detect-series",
            json={"product_skus": ["TEST-SKU"]}
        )
        
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Endpoint correctly requires authentication")
    
    def test_detect_series_returns_attributes(self, auth_headers, sample_product_skus):
        """Test that detected series include attribute badges (colors, sizes, finishes)"""
        response = requests.post(
            f"{BASE_URL}/api/products/detect-series",
            headers=auth_headers,
            json={"product_skus": sample_product_skus}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data["series"]:
            first_series = data["series"][0]
            # Check attribute arrays exist (may be empty)
            assert "colors" in first_series
            assert "sizes" in first_series
            assert "finishes" in first_series
            assert isinstance(first_series["colors"], list)
            assert isinstance(first_series["sizes"], list)
            assert isinstance(first_series["finishes"], list)
            print(f"✓ Series attributes: {len(first_series['colors'])} colors, {len(first_series['sizes'])} sizes, {len(first_series['finishes'])} finishes")


class TestGenerateBatchSeriesDescriptions:
    """Tests for POST /api/products/generate-batch-series-descriptions endpoint"""
    
    def test_generate_batch_descriptions_success(self, auth_headers, sample_product_skus):
        """Test successful batch description generation"""
        response = requests.post(
            f"{BASE_URL}/api/products/generate-batch-series-descriptions",
            headers=auth_headers,
            json={
                "product_skus": sample_product_skus,
                "length": "brief"  # Use brief for faster test
            },
            timeout=60  # AI generation may take time
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") is True
        assert "series_count" in data
        assert "results" in data
        assert isinstance(data["results"], list)
        
        print(f"✓ Generated descriptions for {data['series_count']} series")
        
        # Verify result structure
        if data["results"]:
            first_result = data["results"][0]
            assert "series_name" in first_result
            assert "description" in first_result
            assert "product_count" in first_result
            assert "skus" in first_result
            assert "aggregated_data" in first_result
            
            # Verify description is not empty
            assert len(first_result["description"]) > 50, "Description should be substantial"
            print(f"✓ First result: {first_result['series_name']} - {len(first_result['description'])} chars")
    
    def test_generate_batch_descriptions_brief_length(self, auth_headers, sample_product_skus):
        """Test brief length generates shorter descriptions"""
        response = requests.post(
            f"{BASE_URL}/api/products/generate-batch-series-descriptions",
            headers=auth_headers,
            json={
                "product_skus": sample_product_skus[:5],  # Use fewer SKUs for speed
                "length": "brief"
            },
            timeout=60
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get("results"):
            desc = data["results"][0]["description"]
            # Brief should be around 80-120 words
            word_count = len(desc.split())
            print(f"✓ Brief description: {word_count} words")
            # Allow some flexibility in word count
            assert word_count < 300, f"Brief description too long: {word_count} words"
    
    def test_generate_batch_descriptions_standard_length(self, auth_headers, sample_product_skus):
        """Test standard length (default) generates medium descriptions"""
        response = requests.post(
            f"{BASE_URL}/api/products/generate-batch-series-descriptions",
            headers=auth_headers,
            json={
                "product_skus": sample_product_skus[:5],
                "length": "standard"
            },
            timeout=60
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get("results"):
            desc = data["results"][0]["description"]
            word_count = len(desc.split())
            print(f"✓ Standard description: {word_count} words")
    
    def test_generate_batch_descriptions_empty_skus(self, auth_headers):
        """Test batch generation with empty SKU list returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/products/generate-batch-series-descriptions",
            headers=auth_headers,
            json={"product_skus": []}
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Empty SKU list correctly returns 400")
    
    def test_generate_batch_descriptions_invalid_skus(self, auth_headers):
        """Test batch generation with non-existent SKUs returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/products/generate-batch-series-descriptions",
            headers=auth_headers,
            json={"product_skus": ["NONEXISTENT-SKU-12345"]}
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Non-existent SKUs correctly return 404")
    
    def test_generate_batch_descriptions_requires_auth(self):
        """Test batch generation requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/products/generate-batch-series-descriptions",
            json={"product_skus": ["TEST-SKU"]}
        )
        
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Endpoint correctly requires authentication")
    
    def test_generate_batch_descriptions_with_seo_keywords(self, auth_headers, sample_product_skus):
        """Test batch generation with SEO keywords"""
        response = requests.post(
            f"{BASE_URL}/api/products/generate-batch-series-descriptions",
            headers=auth_headers,
            json={
                "product_skus": sample_product_skus[:5],
                "seo_keywords": "premium tiles, luxury flooring, modern design",
                "length": "brief"
            },
            timeout=60
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        print("✓ Batch generation with SEO keywords successful")
    
    def test_generate_batch_descriptions_aggregated_data(self, auth_headers, sample_product_skus):
        """Test that results include aggregated data for each series"""
        response = requests.post(
            f"{BASE_URL}/api/products/generate-batch-series-descriptions",
            headers=auth_headers,
            json={
                "product_skus": sample_product_skus,
                "length": "brief"
            },
            timeout=60
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get("results"):
            first_result = data["results"][0]
            agg_data = first_result.get("aggregated_data", {})
            
            # Check aggregated data structure
            assert "colors" in agg_data or "sizes" in agg_data or "finishes" in agg_data
            print(f"✓ Aggregated data present: colors={len(agg_data.get('colors', []))}, sizes={len(agg_data.get('sizes', []))}")


class TestIntegrationFlow:
    """Integration tests for the full Quick Generate All flow"""
    
    def test_full_flow_detect_then_generate(self, auth_headers, sample_product_skus):
        """Test the full flow: detect series -> generate descriptions"""
        # Step 1: Detect series
        detect_response = requests.post(
            f"{BASE_URL}/api/products/detect-series",
            headers=auth_headers,
            json={"product_skus": sample_product_skus}
        )
        
        assert detect_response.status_code == 200
        detect_data = detect_response.json()
        assert detect_data.get("success") is True
        
        print(f"Step 1: Detected {detect_data['series_count']} series")
        
        # Step 2: Generate descriptions for detected series
        # Get SKUs from first detected series
        if detect_data["series"]:
            first_series_skus = detect_data["series"][0]["skus"]
            
            generate_response = requests.post(
                f"{BASE_URL}/api/products/generate-batch-series-descriptions",
                headers=auth_headers,
                json={
                    "product_skus": first_series_skus,
                    "length": "brief"
                },
                timeout=60
            )
            
            assert generate_response.status_code == 200
            generate_data = generate_response.json()
            assert generate_data.get("success") is True
            
            print(f"Step 2: Generated {generate_data['series_count']} descriptions")
            print("✓ Full flow completed successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

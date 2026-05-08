"""
Test Quote Request System
Tests the Request Quote feature for large quantity orders

Features tested:
1. GET /api/shop/products/{id}/quote-status - Returns quote button visibility based on quantity
2. POST /api/shop/quotes/request - Submits a quote request
3. GET /api/shop/quotes/config - Returns global quote settings
4. PUT /api/supplier-sync/products/bulk-quote-settings - Admin disable/enable quote for products
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://feature-verification-7.preview.emergentagent.com')


class TestQuoteStatusEndpoint:
    """Test the quote-status endpoint that determines button visibility"""
    
    def test_quote_status_below_threshold(self):
        """Quantity < 150 should show Add to Cart (show_quote_button=false)"""
        # Test with quantity below threshold (default 150)
        res = requests.get(f"{BASE_URL}/api/shop/products/alabaster-30x60cm-polished/quote-status?quantity=50")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        data = res.json()
        assert "show_quote_button" in data, "Response should have show_quote_button field"
        assert data["show_quote_button"] == False, "show_quote_button should be False for quantity < threshold"
        assert data.get("quote_disabled") == False, "quote_disabled should be False"
        print(f"PASS: Below threshold (50m²) - show_quote_button={data['show_quote_button']}")
    
    def test_quote_status_at_threshold(self):
        """Quantity = 150 should show Request Quote (show_quote_button=true)"""
        res = requests.get(f"{BASE_URL}/api/shop/products/alabaster-30x60cm-polished/quote-status?quantity=150")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        data = res.json()
        assert data["show_quote_button"] == True, "show_quote_button should be True for quantity = threshold"
        assert data.get("threshold") == 150, "Default threshold should be 150"
        print(f"PASS: At threshold (150m²) - show_quote_button={data['show_quote_button']}")
    
    def test_quote_status_above_threshold(self):
        """Quantity > 150 should show Request Quote (show_quote_button=true)"""
        res = requests.get(f"{BASE_URL}/api/shop/products/alabaster-30x60cm-polished/quote-status?quantity=200")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        data = res.json()
        assert data["show_quote_button"] == True, "show_quote_button should be True for quantity > threshold"
        assert data.get("exceeds_threshold") == True, "exceeds_threshold should be True"
        print(f"PASS: Above threshold (200m²) - show_quote_button={data['show_quote_button']}")
    
    def test_quote_status_with_disabled_flag(self):
        """When quote_disabled=true, always show Add to Cart"""
        res = requests.get(f"{BASE_URL}/api/shop/products/alabaster-30x60cm-polished/quote-status?quantity=200&quote_disabled=true")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        data = res.json()
        assert data["show_quote_button"] == False, "show_quote_button should be False when quote_disabled=true"
        assert data.get("quote_disabled") == True, "quote_disabled should be True"
        print(f"PASS: Quote disabled - show_quote_button={data['show_quote_button']} even at 200m²")
    
    def test_quote_status_with_custom_threshold(self):
        """Custom threshold should override default"""
        # Test with custom threshold of 100 at quantity 100
        res = requests.get(f"{BASE_URL}/api/shop/products/alabaster-30x60cm-polished/quote-status?quantity=100&custom_threshold=100")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        data = res.json()
        assert data["show_quote_button"] == True, "show_quote_button should be True when quantity meets custom threshold"
        assert data.get("threshold") == 100, "threshold should reflect custom value"
        print(f"PASS: Custom threshold (100m²) - show_quote_button={data['show_quote_button']}")


class TestQuoteConfigEndpoint:
    """Test the global quote configuration endpoint"""
    
    def test_get_quote_config(self):
        """GET /api/shop/quotes/config should return quote settings"""
        res = requests.get(f"{BASE_URL}/api/shop/quotes/config")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        data = res.json()
        assert "quote_threshold" in data, "Response should have quote_threshold"
        assert "quote_enabled" in data, "Response should have quote_enabled"
        assert data["quote_threshold"] == 150, f"Default threshold should be 150, got {data['quote_threshold']}"
        print(f"PASS: Quote config - threshold={data['quote_threshold']}, enabled={data['quote_enabled']}")


class TestQuoteRequestSubmission:
    """Test the quote request submission endpoint"""
    
    def test_submit_quote_request_success(self):
        """POST /api/shop/quotes/request should create quote and return quote_id"""
        quote_data = {
            "product_id": "alabaster-30x60cm-polished",
            "product_name": "Alabaster 30x60cm Polished",
            "product_sku": "V-ALB-3060-POL",
            "quantity": 200,
            "customer_name": "Test Customer",
            "customer_email": "test-quote@example.com",
            "customer_phone": "07123456789",
            "customer_company": "Test Construction Ltd",
            "project_details": "Large bathroom renovation project",
            "delivery_postcode": "SW1A 1AA",
            "preferred_contact": "email"
        }
        
        res = requests.post(f"{BASE_URL}/api/shop/quotes/request", json=quote_data)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        data = res.json()
        assert data.get("success") == True, "Response should indicate success"
        assert "quote_id" in data, "Response should have quote_id"
        assert data["quote_id"].startswith("QR-"), f"Quote ID should start with QR-, got {data['quote_id']}"
        print(f"PASS: Quote submitted - quote_id={data['quote_id']}, message={data['message']}")
        return data["quote_id"]
    
    def test_submit_quote_request_missing_required_fields(self):
        """Missing required fields should return error"""
        quote_data = {
            "product_id": "test-product",
            # Missing required fields
        }
        
        res = requests.post(f"{BASE_URL}/api/shop/quotes/request", json=quote_data)
        # Should get 422 validation error
        assert res.status_code == 422, f"Expected 422 for missing fields, got {res.status_code}"
        print(f"PASS: Missing required fields returns 422 validation error")
    
    def test_submit_quote_request_invalid_email(self):
        """Invalid email format should return validation error"""
        quote_data = {
            "product_id": "test-product",
            "product_name": "Test Product",
            "quantity": 200,
            "customer_name": "Test",
            "customer_email": "invalid-email",  # Invalid email format
            "customer_phone": "07123456789"
        }
        
        res = requests.post(f"{BASE_URL}/api/shop/quotes/request", json=quote_data)
        assert res.status_code == 422, f"Expected 422 for invalid email, got {res.status_code}"
        print(f"PASS: Invalid email returns 422 validation error")


class TestBulkQuoteSettings:
    """Test bulk quote settings update endpoint (admin functionality)"""
    
    def test_bulk_disable_quote_for_products(self):
        """PUT /api/supplier-sync/products/bulk-quote-settings should disable quotes"""
        # Note: This endpoint is called from SupplierProducts.js admin page
        data = {
            "products": [
                {"supplier": "Verona", "sku": "test-sku-1"},
                {"supplier": "Verona", "sku": "test-sku-2"}
            ],
            "quote_disabled": True,
            "custom_quote_threshold": None
        }
        
        res = requests.put(f"{BASE_URL}/api/supplier-sync/products/bulk-quote-settings", json=data)
        # Even if products don't exist, endpoint should return success with updated_count=0
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        result = res.json()
        assert result.get("success") == True, "Response should indicate success"
        assert "updated_count" in result, "Response should have updated_count"
        assert result.get("quote_disabled") == True, "quote_disabled should be True"
        print(f"PASS: Bulk disable quotes - updated_count={result['updated_count']}")
    
    def test_bulk_enable_quote_with_custom_threshold(self):
        """Enable quotes with custom threshold"""
        data = {
            "products": [
                {"supplier": "Verona", "sku": "test-sku-1"}
            ],
            "quote_disabled": False,
            "custom_quote_threshold": 200  # Custom threshold
        }
        
        res = requests.put(f"{BASE_URL}/api/supplier-sync/products/bulk-quote-settings", json=data)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        result = res.json()
        assert result.get("success") == True, "Response should indicate success"
        assert result.get("quote_disabled") == False, "quote_disabled should be False"
        print(f"PASS: Enable quotes with custom threshold - updated_count={result['updated_count']}")


class TestQuoteIntegration:
    """Integration tests for quote flow"""
    
    def test_full_quote_flow(self):
        """Test complete flow: check status -> show button -> submit quote"""
        # Step 1: Check quote status at high quantity
        status_res = requests.get(f"{BASE_URL}/api/shop/products/alabaster-30x60cm-polished/quote-status?quantity=250")
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert status_data["show_quote_button"] == True, "Should show quote button at 250m²"
        
        # Step 2: Submit quote request
        quote_data = {
            "product_id": "alabaster-30x60cm-polished",
            "product_name": "Alabaster 30x60cm Polished",
            "quantity": 250,
            "customer_name": "Integration Test Customer",
            "customer_email": "integration-test@example.com",
            "customer_phone": "07987654321",
            "preferred_contact": "phone"
        }
        
        quote_res = requests.post(f"{BASE_URL}/api/shop/quotes/request", json=quote_data)
        assert quote_res.status_code == 200
        quote_data = quote_res.json()
        assert quote_data["success"] == True
        assert "QR-" in quote_data["quote_id"]
        
        print(f"PASS: Full quote flow completed - quote_id={quote_data['quote_id']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

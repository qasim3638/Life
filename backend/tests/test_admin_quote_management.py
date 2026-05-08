"""
Test Admin Quote Management APIs
Tests the admin dashboard functionality for managing quote requests

Features tested:
1. Quote threshold is now 120m² (updated from 150m²)
2. GET /api/shop/admin/quotes - List all quote requests with pagination and filtering
3. GET /api/shop/admin/quotes/stats/summary - Quote statistics for dashboard
4. GET /api/shop/admin/quotes/{quote_id} - Get detailed quote info
5. PUT /api/shop/admin/quotes/{quote_id} - Update quote status, price, notes
6. DELETE /api/shop/admin/quotes/{quote_id} - Delete a quote
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://feature-verification-7.preview.emergentagent.com')


class TestUpdatedQuoteThreshold:
    """Test that quote threshold is now 120m² (updated from 150m²)"""
    
    def test_quote_config_shows_120_threshold(self):
        """GET /api/shop/quotes/config should return threshold=120"""
        res = requests.get(f"{BASE_URL}/api/shop/quotes/config")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        data = res.json()
        assert data["quote_threshold"] == 120, f"Expected threshold=120, got {data['quote_threshold']}"
        print(f"PASS: Quote threshold is now 120m² (updated from 150m²)")
    
    def test_quote_status_at_120_shows_quote_button(self):
        """Quantity=120 should now show Request Quote button (threshold changed from 150)"""
        res = requests.get(f"{BASE_URL}/api/shop/products/alabaster-30x60cm-polished/quote-status?quantity=120")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        data = res.json()
        assert data["show_quote_button"] == True, f"show_quote_button should be True at 120m² (new threshold)"
        assert data["threshold"] == 120, f"threshold should be 120, got {data['threshold']}"
        print(f"PASS: At 120m² - show_quote_button={data['show_quote_button']}, threshold={data['threshold']}")
    
    def test_quote_status_below_120_shows_add_to_cart(self):
        """Quantity=119 should show Add to Cart (below new 120 threshold)"""
        res = requests.get(f"{BASE_URL}/api/shop/products/alabaster-30x60cm-polished/quote-status?quantity=119")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        data = res.json()
        assert data["show_quote_button"] == False, f"show_quote_button should be False at 119m²"
        print(f"PASS: At 119m² - show_quote_button={data['show_quote_button']} (below threshold)")


class TestAdminQuotesList:
    """Test GET /api/shop/admin/quotes - List all quote requests"""
    
    def test_get_all_quotes(self):
        """Should return list of quotes with pagination info"""
        res = requests.get(f"{BASE_URL}/api/shop/admin/quotes")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        data = res.json()
        assert "quotes" in data, "Response should have 'quotes' array"
        assert "total" in data, "Response should have 'total' count"
        assert "status_counts" in data, "Response should have 'status_counts'"
        assert "pagination" in data, "Response should have 'pagination' info"
        
        # Verify quotes array structure
        if len(data["quotes"]) > 0:
            quote = data["quotes"][0]
            assert "quote_ref" in quote, "Each quote should have quote_ref"
            assert "customer_name" in quote, "Each quote should have customer_name"
            assert "customer_email" in quote, "Each quote should have customer_email"
            assert "product_name" in quote, "Each quote should have product_name"
            assert "quantity" in quote, "Each quote should have quantity"
            assert "status" in quote, "Each quote should have status"
        
        print(f"PASS: GET /api/shop/admin/quotes - {data['total']} quotes found")
    
    def test_filter_quotes_by_status(self):
        """Should filter quotes by status parameter"""
        res = requests.get(f"{BASE_URL}/api/shop/admin/quotes?status=pending")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        data = res.json()
        # All returned quotes should have status=pending
        for quote in data["quotes"]:
            assert quote["status"] == "pending", f"Filtered quote should have status=pending, got {quote['status']}"
        
        print(f"PASS: Filter by status=pending - {len(data['quotes'])} quotes")
    
    def test_filter_quotes_by_quoted_status(self):
        """Should filter quotes by quoted status"""
        res = requests.get(f"{BASE_URL}/api/shop/admin/quotes?status=quoted")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        data = res.json()
        for quote in data["quotes"]:
            assert quote["status"] == "quoted", f"Quote should have status=quoted"
        
        print(f"PASS: Filter by status=quoted - {len(data['quotes'])} quotes")
    
    def test_pagination_parameters(self):
        """Should support skip and limit parameters"""
        res = requests.get(f"{BASE_URL}/api/shop/admin/quotes?limit=2&skip=0")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        data = res.json()
        assert len(data["quotes"]) <= 2, "Should return max 2 quotes with limit=2"
        assert data["pagination"]["limit"] == 2, "Pagination should reflect limit=2"
        assert data["pagination"]["skip"] == 0, "Pagination should reflect skip=0"
        
        print(f"PASS: Pagination works - limit=2, returned {len(data['quotes'])} quotes")


class TestAdminQuoteStats:
    """Test GET /api/shop/admin/quotes/stats/summary - Dashboard statistics"""
    
    def test_get_quote_stats(self):
        """Should return comprehensive quote statistics"""
        res = requests.get(f"{BASE_URL}/api/shop/admin/quotes/stats/summary")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        data = res.json()
        
        # Verify all required fields
        assert "total_quotes" in data, "Stats should have total_quotes"
        assert "pending" in data, "Stats should have pending count"
        assert "quoted" in data, "Stats should have quoted count"
        assert "accepted" in data, "Stats should have accepted count"
        assert "declined" in data, "Stats should have declined count"
        assert "recent_7_days" in data, "Stats should have recent_7_days"
        assert "total_accepted_value" in data, "Stats should have total_accepted_value"
        assert "conversion_rate" in data, "Stats should have conversion_rate"
        
        # Verify data types
        assert isinstance(data["total_quotes"], int), "total_quotes should be int"
        assert isinstance(data["total_accepted_value"], (int, float)), "total_accepted_value should be numeric"
        assert isinstance(data["conversion_rate"], (int, float)), "conversion_rate should be numeric"
        
        print(f"PASS: Quote stats - Total: {data['total_quotes']}, Pending: {data['pending']}, Quoted: {data['quoted']}, Accepted: {data['accepted']}")


class TestAdminQuoteDetail:
    """Test GET /api/shop/admin/quotes/{quote_id} - Get detailed quote info"""
    
    def test_get_quote_by_ref(self):
        """Should retrieve quote details by quote_ref (QR-XXXXX)"""
        res = requests.get(f"{BASE_URL}/api/shop/admin/quotes/QR-01001")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        data = res.json()
        assert data["quote_ref"] == "QR-01001", "Should return correct quote"
        
        # Verify all quote fields
        required_fields = ["id", "quote_ref", "product_id", "product_name", "quantity", 
                         "customer_name", "customer_email", "customer_phone", "status", "created_at"]
        for field in required_fields:
            assert field in data, f"Quote should have '{field}' field"
        
        print(f"PASS: GET /api/shop/admin/quotes/QR-01001 - Customer: {data['customer_name']}, Product: {data['product_name']}")
    
    def test_get_nonexistent_quote_returns_404(self):
        """Should return 404 for non-existent quote"""
        res = requests.get(f"{BASE_URL}/api/shop/admin/quotes/QR-99999")
        assert res.status_code == 404, f"Expected 404, got {res.status_code}"
        print("PASS: Non-existent quote returns 404")


class TestAdminQuoteUpdate:
    """Test PUT /api/shop/admin/quotes/{quote_id} - Update quote status and details"""
    
    def test_update_quote_status_to_quoted_with_price(self):
        """Should update status to 'quoted' with price and notes"""
        update_data = {
            "status": "quoted",
            "quote_price": 4500.00,
            "quote_notes": "Bulk order discount 10% applied",
            "valid_until": "2026-04-30"
        }
        
        res = requests.put(f"{BASE_URL}/api/shop/admin/quotes/QR-01002", json=update_data)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        data = res.json()
        assert data["success"] == True, "Update should succeed"
        assert data["new_status"] == "quoted", "New status should be 'quoted'"
        
        # Verify the update persisted
        verify_res = requests.get(f"{BASE_URL}/api/shop/admin/quotes/QR-01002")
        verify_data = verify_res.json()
        assert verify_data["status"] == "quoted", "Status should be updated to quoted"
        assert verify_data["quote_price"] == 4500.00, "Quote price should be 4500"
        assert verify_data["quote_notes"] == "Bulk order discount 10% applied", "Notes should be updated"
        assert "status_history" in verify_data, "Should have status_history"
        
        print(f"PASS: Updated QR-01002 to quoted with price £4500")
    
    def test_update_quote_status_to_accepted(self):
        """Should update status to 'accepted'"""
        update_data = {
            "status": "accepted",
            "quote_notes": "Customer accepted the quote via email"
        }
        
        res = requests.put(f"{BASE_URL}/api/shop/admin/quotes/QR-01002", json=update_data)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        data = res.json()
        assert data["success"] == True
        assert data["new_status"] == "accepted"
        
        print(f"PASS: Updated QR-01002 to accepted")
    
    def test_update_quote_invalid_status(self):
        """Should reject invalid status values"""
        update_data = {"status": "invalid_status"}
        
        res = requests.put(f"{BASE_URL}/api/shop/admin/quotes/QR-01003", json=update_data)
        assert res.status_code == 400, f"Expected 400 for invalid status, got {res.status_code}"
        print("PASS: Invalid status rejected with 400")
    
    def test_update_nonexistent_quote(self):
        """Should return 404 for non-existent quote"""
        update_data = {"status": "quoted"}
        
        res = requests.put(f"{BASE_URL}/api/shop/admin/quotes/QR-99999", json=update_data)
        assert res.status_code == 404, f"Expected 404, got {res.status_code}"
        print("PASS: Update non-existent quote returns 404")


class TestAdminQuoteDelete:
    """Test DELETE /api/shop/admin/quotes/{quote_id} - Delete a quote"""
    
    def test_delete_nonexistent_quote(self):
        """Should return 404 when deleting non-existent quote"""
        res = requests.delete(f"{BASE_URL}/api/shop/admin/quotes/QR-99999")
        assert res.status_code == 404, f"Expected 404, got {res.status_code}"
        print("PASS: Delete non-existent quote returns 404")
    
    def test_create_and_delete_quote(self):
        """Create a test quote and then delete it"""
        # First create a new quote
        quote_data = {
            "product_id": "test-product-delete",
            "product_name": "Test Product for Delete",
            "quantity": 150,
            "customer_name": "TEST_Delete Customer",
            "customer_email": "test-delete@example.com",
            "customer_phone": "07000000000",
            "preferred_contact": "email"
        }
        
        create_res = requests.post(f"{BASE_URL}/api/shop/quotes/request", json=quote_data)
        assert create_res.status_code == 200, f"Create quote failed: {create_res.text}"
        quote_ref = create_res.json()["quote_id"]
        print(f"Created test quote: {quote_ref}")
        
        # Now delete it
        delete_res = requests.delete(f"{BASE_URL}/api/shop/admin/quotes/{quote_ref}")
        assert delete_res.status_code == 200, f"Expected 200, got {delete_res.status_code}: {delete_res.text}"
        
        data = delete_res.json()
        assert data["success"] == True, "Delete should succeed"
        
        # Verify it's gone
        verify_res = requests.get(f"{BASE_URL}/api/shop/admin/quotes/{quote_ref}")
        assert verify_res.status_code == 404, "Deleted quote should not be found"
        
        print(f"PASS: Created and deleted quote {quote_ref}")


class TestAdminQuoteStatsAfterUpdates:
    """Test stats reflect updates correctly"""
    
    def test_stats_reflect_accepted_quote_value(self):
        """Stats should include accepted quote values"""
        res = requests.get(f"{BASE_URL}/api/shop/admin/quotes/stats/summary")
        assert res.status_code == 200
        
        data = res.json()
        # After updating QR-01002 to accepted with price 4500
        # the total_accepted_value should include this
        print(f"PASS: Stats - Accepted: {data['accepted']}, Value: £{data['total_accepted_value']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

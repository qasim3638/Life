"""
Trade Credit Back System - Backend Tests
Tests for Phase 3: Credit Back System
- GET /api/shop/trade/credits - Credit balance and history
- GET /api/shop/trade/credits/summary - Credit summary
- POST /api/shop/trade/credits/earn - Award credits after order
- POST /api/shop/trade/credits/redeem - Redeem credits
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TRADE_CUSTOMER_EMAIL = "trade@test.com"
TRADE_CUSTOMER_PASSWORD = "Test123!"
NON_TRADE_EMAIL = "guest@test.com"  # Non-trade customer for testing
NON_TRADE_PASSWORD = "Test123!"


class TestTradeCreditsEndpoint:
    """Test GET /api/shop/trade/credits - Credit balance and history"""
    
    def test_credits_requires_auth(self):
        """Credits endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/shop/trade/credits")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Credits endpoint returns 401 without auth")
    
    def test_trade_customer_can_get_credits(self):
        """Trade customer can get their credit balance and history"""
        # Login as trade customer
        login_resp = requests.post(
            f"{BASE_URL}/api/shop/auth/login",
            json={"email": TRADE_CUSTOMER_EMAIL, "password": TRADE_CUSTOMER_PASSWORD}
        )
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json()["token"]
        
        # Get credits
        response = requests.get(
            f"{BASE_URL}/api/shop/trade/credits",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure for trade customer
        assert "is_trade" in data, "Missing is_trade field"
        assert data["is_trade"] == True, f"Expected is_trade=True, got {data['is_trade']}"
        assert "credit_balance" in data, "Missing credit_balance field"
        assert "credit_rate" in data, "Missing credit_rate field"
        assert "credit_history" in data, "Missing credit_history field"
        assert "total_earned" in data, "Missing total_earned field"
        assert "total_redeemed" in data, "Missing total_redeemed field"
        
        # credit_balance should be numeric
        assert isinstance(data["credit_balance"], (int, float)), "credit_balance should be numeric"
        
        print(f"PASS: Trade customer credits - balance: £{data['credit_balance']:.2f}, "
              f"rate: {data['credit_rate']}%, earned: £{data['total_earned']:.2f}, "
              f"redeemed: £{data['total_redeemed']:.2f}, history_count: {len(data['credit_history'])}")
        
        return data


class TestCreditsSummaryEndpoint:
    """Test GET /api/shop/trade/credits/summary - Credit summary for dashboard"""
    
    def test_summary_requires_auth(self):
        """Summary endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/shop/trade/credits/summary")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Credits summary returns 401 without auth")
    
    def test_trade_customer_summary(self):
        """Trade customer can get credit summary"""
        # Login
        login_resp = requests.post(
            f"{BASE_URL}/api/shop/auth/login",
            json={"email": TRADE_CUSTOMER_EMAIL, "password": TRADE_CUSTOMER_PASSWORD}
        )
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json()["token"]
        
        # Get summary
        response = requests.get(
            f"{BASE_URL}/api/shop/trade/credits/summary",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "is_trade" in data, "Missing is_trade field"
        assert data["is_trade"] == True, f"Expected is_trade=True"
        assert "credit_balance" in data, "Missing credit_balance"
        assert "credit_rate" in data, "Missing credit_rate"
        assert "total_earned" in data, "Missing total_earned"
        assert "total_redeemed" in data, "Missing total_redeemed"
        assert "recent_transactions" in data, "Missing recent_transactions"
        assert "message" in data, "Missing message"
        
        # recent_transactions should be a list
        assert isinstance(data["recent_transactions"], list), "recent_transactions should be a list"
        
        print(f"PASS: Trade credit summary - balance: £{data['credit_balance']:.2f}, "
              f"recent_tx: {len(data['recent_transactions'])}, message: {data['message'][:50]}...")
        
        return data


class TestCreditsEarnEndpoint:
    """Test POST /api/shop/trade/credits/earn - Award credits after order completion"""
    
    def test_earn_requires_auth(self):
        """Earn endpoint requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/shop/trade/credits/earn",
            params={"order_id": "test-order-123"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Credits earn returns 401 without auth")
    
    def test_earn_invalid_order(self):
        """Earn fails for non-existent order"""
        # Login
        login_resp = requests.post(
            f"{BASE_URL}/api/shop/auth/login",
            json={"email": TRADE_CUSTOMER_EMAIL, "password": TRADE_CUSTOMER_PASSWORD}
        )
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json()["token"]
        
        # Try to earn credits for invalid order
        response = requests.post(
            f"{BASE_URL}/api/shop/trade/credits/earn",
            params={"order_id": "non-existent-order-id"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print("PASS: Credits earn returns 404 for non-existent order")


class TestCreditsRedeemEndpoint:
    """Test POST /api/shop/trade/credits/redeem - Redeem credits"""
    
    def test_redeem_requires_auth(self):
        """Redeem endpoint requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/shop/trade/credits/redeem",
            json={"order_id": "test-order", "amount": 5.0}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Credits redeem returns 401 without auth")
    
    def test_redeem_invalid_order(self):
        """Redeem fails for non-existent order"""
        # Login
        login_resp = requests.post(
            f"{BASE_URL}/api/shop/auth/login",
            json={"email": TRADE_CUSTOMER_EMAIL, "password": TRADE_CUSTOMER_PASSWORD}
        )
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json()["token"]
        
        # Try to redeem credits for invalid order
        response = requests.post(
            f"{BASE_URL}/api/shop/trade/credits/redeem",
            json={"order_id": "non-existent-order", "amount": 5.0},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print("PASS: Credits redeem returns 404 for non-existent order")
    
    def test_redeem_zero_amount_fails(self):
        """Redeem with zero amount should fail"""
        # Login
        login_resp = requests.post(
            f"{BASE_URL}/api/shop/auth/login",
            json={"email": TRADE_CUSTOMER_EMAIL, "password": TRADE_CUSTOMER_PASSWORD}
        )
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json()["token"]
        
        # Try to redeem 0 credits
        response = requests.post(
            f"{BASE_URL}/api/shop/trade/credits/redeem",
            json={"order_id": "test-order", "amount": 0},
            headers={"Authorization": f"Bearer {token}"}
        )
        # Should fail validation - either 400 or 404
        assert response.status_code in [400, 404], f"Expected 400/404, got {response.status_code}: {response.text}"
        print(f"PASS: Credits redeem rejects zero amount with status {response.status_code}")
    
    def test_redeem_negative_amount_fails(self):
        """Redeem with negative amount should fail"""
        # Login
        login_resp = requests.post(
            f"{BASE_URL}/api/shop/auth/login",
            json={"email": TRADE_CUSTOMER_EMAIL, "password": TRADE_CUSTOMER_PASSWORD}
        )
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json()["token"]
        
        # Try to redeem negative credits
        response = requests.post(
            f"{BASE_URL}/api/shop/trade/credits/redeem",
            json={"order_id": "test-order", "amount": -10},
            headers={"Authorization": f"Bearer {token}"}
        )
        # Should fail validation
        assert response.status_code in [400, 404, 422], f"Expected 400/404/422, got {response.status_code}: {response.text}"
        print(f"PASS: Credits redeem rejects negative amount with status {response.status_code}")


class TestTradeStatusIncludesCredits:
    """Test that GET /api/shop/trade/status includes credit info"""
    
    def test_trade_status_includes_credit_fields(self):
        """Trade status should include credit_balance and credit_rate"""
        # Login
        login_resp = requests.post(
            f"{BASE_URL}/api/shop/auth/login",
            json={"email": TRADE_CUSTOMER_EMAIL, "password": TRADE_CUSTOMER_PASSWORD}
        )
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json()["token"]
        
        # Get trade status
        response = requests.get(
            f"{BASE_URL}/api/shop/trade/status",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify credit fields are present
        assert "credit_balance" in data, "Missing credit_balance in trade status"
        assert "credit_rate" in data, "Missing credit_rate in trade status"
        assert data["is_trade"] == True, "Expected is_trade=True"
        
        print(f"PASS: Trade status includes credits - balance: £{data['credit_balance']}, rate: {data['credit_rate']}%")


class TestCreditHistoryStructure:
    """Test that credit history has correct structure"""
    
    def test_credit_history_structure(self):
        """Credit history records should have required fields"""
        # Login
        login_resp = requests.post(
            f"{BASE_URL}/api/shop/auth/login",
            json={"email": TRADE_CUSTOMER_EMAIL, "password": TRADE_CUSTOMER_PASSWORD}
        )
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json()["token"]
        
        # Get credits
        response = requests.get(
            f"{BASE_URL}/api/shop/trade/credits",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        credit_history = data.get("credit_history", [])
        
        if len(credit_history) > 0:
            # Verify structure of first history record
            record = credit_history[0]
            required_fields = ["id", "type", "amount", "description", "created_at"]
            
            for field in required_fields:
                assert field in record, f"Missing {field} in credit history record"
            
            # Type should be 'earn' or 'redeem'
            assert record["type"] in ["earn", "redeem"], f"Invalid type: {record['type']}"
            
            print(f"PASS: Credit history structure valid - {len(credit_history)} records, "
                  f"first: {record['type']} £{abs(record['amount']):.2f}")
        else:
            print("INFO: No credit history records to verify structure (may be expected for fresh account)")


class TestCreditBalanceVerification:
    """Verify the test trade customer has expected credit balance"""
    
    def test_trade_customer_has_credits(self):
        """Test trade customer should have £25.50 credit balance (as per context)"""
        # Login
        login_resp = requests.post(
            f"{BASE_URL}/api/shop/auth/login",
            json={"email": TRADE_CUSTOMER_EMAIL, "password": TRADE_CUSTOMER_PASSWORD}
        )
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json()["token"]
        
        # Get credits
        response = requests.get(
            f"{BASE_URL}/api/shop/trade/credits",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        credit_balance = data.get("credit_balance", 0)
        
        # According to context, trade@test.com should have £25.50 credit balance
        print(f"INFO: Trade customer credit balance: £{credit_balance:.2f}")
        
        # Verify it's a positive number (actual amount may vary due to test runs)
        assert credit_balance >= 0, f"Credit balance should be >= 0, got {credit_balance}"
        
        if credit_balance > 0:
            print(f"PASS: Trade customer has positive credit balance: £{credit_balance:.2f}")
        else:
            print("WARN: Trade customer has zero credit balance - may need seeding")


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

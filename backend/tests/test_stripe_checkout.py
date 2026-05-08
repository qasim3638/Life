"""
Stripe Checkout Integration Tests
Tests for guest checkout flow with Stripe payment integration
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://feature-verification-7.preview.emergentagent.com')


class TestGuestCheckoutFlow:
    """Tests for the guest checkout flow with Stripe integration"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data"""
        self.test_order_id = None
        self.test_session_id = None
    
    def test_health_check(self):
        """Test backend health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("✓ Backend health check passed")
    
    def test_create_guest_checkout_order(self):
        """Test POST /api/shop/guest-checkout creates an order"""
        order_data = {
            "items": [
                {
                    "product_id": f"test-tile-{uuid.uuid4().hex[:8]}",
                    "name": "Test Porcelain Tile",
                    "variant": "Matt Grey",
                    "price": 35.99,
                    "quantity": 3,
                    "image": ""
                }
            ],
            "customer": {
                "email": "stripe-test@example.com",
                "firstName": "Test",
                "lastName": "Customer",
                "phone": "07123456789"
            },
            "delivery": {
                "method": "delivery",
                "address1": "456 Test Road",
                "address2": "Flat 2",
                "city": "London",
                "county": "Greater London",
                "postcode": "SE1 2AB"
            },
            "payment": {"method": "card"},
            "subtotal": 107.97,
            "delivery_fee": 49.99,
            "total": 157.96
        }
        
        response = requests.post(
            f"{BASE_URL}/api/shop/guest-checkout",
            json=order_data
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "order_id" in data, "Response should contain order_id"
        assert "order_number" in data, "Response should contain order_number"
        assert "total" in data, "Response should contain total"
        assert "status" in data, "Response should contain status"
        
        # Verify order_id is a valid UUID
        assert len(data["order_id"]) == 36, "order_id should be a UUID"
        
        # Verify order_number format (TS-YYMMDD-XXXXXX)
        assert data["order_number"].startswith("TS-"), "order_number should start with TS-"
        
        # Verify status
        assert data["status"] == "pending", f"Expected status 'pending', got '{data['status']}'"
        
        # Store for next test
        self.__class__.test_order_id = data["order_id"]
        print(f"✓ Guest checkout order created: {data['order_number']}")
        return data
    
    def test_create_stripe_payment_session(self):
        """Test POST /api/shop/guest-checkout/pay creates Stripe session"""
        # First create an order
        order_data = {
            "items": [{"product_id": "test-tile", "name": "Test Tile", "variant": "", "price": 50.00, "quantity": 2, "image": ""}],
            "customer": {"email": "stripe-pay-test@example.com", "firstName": "Pay", "lastName": "Test", "phone": ""},
            "delivery": {"method": "delivery", "address1": "789 Pay St", "city": "London", "postcode": "E1 1AA"},
            "payment": {"method": "card"},
            "subtotal": 100.00,
            "delivery_fee": 49.99,
            "total": 149.99
        }
        
        order_response = requests.post(f"{BASE_URL}/api/shop/guest-checkout", json=order_data)
        assert order_response.status_code == 200
        order = order_response.json()
        
        # Create payment session
        pay_data = {
            "order_id": order["order_id"],
            "origin_url": BASE_URL
        }
        
        response = requests.post(
            f"{BASE_URL}/api/shop/guest-checkout/pay",
            json=pay_data
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "checkout_url" in data, "Response should contain checkout_url"
        assert "session_id" in data, "Response should contain session_id"
        
        # Verify checkout_url is a valid Stripe URL
        assert data["checkout_url"].startswith("https://checkout.stripe.com"), \
            f"checkout_url should be a Stripe URL, got: {data['checkout_url'][:50]}"
        
        # Verify session_id format (cs_test_...)
        assert data["session_id"].startswith("cs_test_"), \
            f"session_id should start with cs_test_, got: {data['session_id'][:20]}"
        
        self.__class__.test_session_id = data["session_id"]
        print(f"✓ Stripe checkout session created: {data['session_id'][:30]}...")
        return data
    
    def test_get_checkout_status(self):
        """Test GET /api/shop/guest-checkout/status/{session_id}"""
        # First create order and payment session
        order_data = {
            "items": [{"product_id": "test-tile", "name": "Test Tile", "variant": "", "price": 25.00, "quantity": 1, "image": ""}],
            "customer": {"email": "status-test@example.com", "firstName": "Status", "lastName": "Test", "phone": ""},
            "delivery": {"method": "collect"},
            "payment": {"method": "card"},
            "subtotal": 25.00,
            "delivery_fee": 0,
            "total": 25.00
        }
        
        order_response = requests.post(f"{BASE_URL}/api/shop/guest-checkout", json=order_data)
        order = order_response.json()
        
        pay_response = requests.post(
            f"{BASE_URL}/api/shop/guest-checkout/pay",
            json={"order_id": order["order_id"], "origin_url": BASE_URL}
        )
        session = pay_response.json()
        
        # Check status
        response = requests.get(f"{BASE_URL}/api/shop/guest-checkout/status/{session['session_id']}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "status" in data, "Response should contain status"
        assert "order" in data, "Response should contain order"
        
        # Verify order details
        order_data = data["order"]
        assert "order_number" in order_data, "Order should contain order_number"
        assert "customer_email" in order_data, "Order should contain customer_email"
        assert "total" in order_data, "Order should contain total"
        assert "items" in order_data, "Order should contain items"
        
        # Status should be unpaid (since we haven't completed payment)
        assert data["status"] in ["unpaid", "initiated", "pending"], \
            f"Expected unpaid/initiated/pending status, got: {data['status']}"
        
        print(f"✓ Checkout status retrieved: {data['status']}")
        return data
    
    def test_checkout_status_not_found(self):
        """Test status endpoint returns 404 for invalid session"""
        response = requests.get(f"{BASE_URL}/api/shop/guest-checkout/status/invalid_session_id")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Invalid session returns 404")
    
    def test_guest_checkout_validation_missing_email(self):
        """Test validation: missing customer email"""
        order_data = {
            "items": [{"product_id": "test", "name": "Test", "variant": "", "price": 10.00, "quantity": 1, "image": ""}],
            "customer": {"firstName": "Test", "lastName": "User", "phone": ""},
            "delivery": {"method": "delivery", "address1": "123 St", "city": "London", "postcode": "E1 1AA"},
            "payment": {"method": "card"},
            "subtotal": 10.00,
            "delivery_fee": 49.99,
            "total": 59.99
        }
        
        response = requests.post(f"{BASE_URL}/api/shop/guest-checkout", json=order_data)
        # Should fail validation
        assert response.status_code in [400, 422], f"Expected 400/422, got {response.status_code}"
        print("✓ Missing email validation works")
    
    def test_guest_checkout_validation_empty_items(self):
        """Test validation: empty items array"""
        order_data = {
            "items": [],
            "customer": {"email": "test@test.com", "firstName": "Test", "lastName": "User", "phone": ""},
            "delivery": {"method": "delivery", "address1": "123 St", "city": "London", "postcode": "E1 1AA"},
            "payment": {"method": "card"},
            "subtotal": 0,
            "delivery_fee": 49.99,
            "total": 49.99
        }
        
        response = requests.post(f"{BASE_URL}/api/shop/guest-checkout", json=order_data)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert "detail" in data
        print("✓ Empty items validation works")
    
    def test_payment_session_missing_order_id(self):
        """Test payment session creation fails without order_id"""
        response = requests.post(
            f"{BASE_URL}/api/shop/guest-checkout/pay",
            json={"origin_url": BASE_URL}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Missing order_id validation works")
    
    def test_payment_session_invalid_order(self):
        """Test payment session creation fails for non-existent order"""
        response = requests.post(
            f"{BASE_URL}/api/shop/guest-checkout/pay",
            json={"order_id": "non-existent-order-id", "origin_url": BASE_URL}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Invalid order_id returns 404")
    
    def test_click_collect_order(self):
        """Test guest checkout with click & collect delivery method"""
        order_data = {
            "items": [{"product_id": "test-tile", "name": "Test Tile", "variant": "", "price": 100.00, "quantity": 1, "image": ""}],
            "customer": {"email": "collect-test@example.com", "firstName": "Collect", "lastName": "Test", "phone": ""},
            "delivery": {"method": "collect"},
            "payment": {"method": "card"},
            "subtotal": 100.00,
            "delivery_fee": 0,
            "total": 100.00
        }
        
        response = requests.post(f"{BASE_URL}/api/shop/guest-checkout", json=order_data)
        assert response.status_code == 200
        data = response.json()
        
        # Verify delivery fee is 0 for click & collect
        assert data["total"] == 100.00, f"Click & collect should have no delivery fee, total: {data['total']}"
        print("✓ Click & collect order created with £0 delivery")


class TestStripeWebhook:
    """Tests for Stripe webhook endpoint"""
    
    def test_webhook_endpoint_exists(self):
        """Test that webhook endpoint exists (will return error without valid signature)"""
        response = requests.post(
            f"{BASE_URL}/api/webhook/stripe",
            headers={"Content-Type": "application/json"},
            data="{}"
        )
        # Should return 400 (bad request) not 404 (not found)
        assert response.status_code != 404, "Webhook endpoint should exist"
        print(f"✓ Webhook endpoint exists (returned {response.status_code})")


class TestOrderSuccessPage:
    """Tests for order success page API integration"""
    
    def test_order_success_flow(self):
        """Test complete flow: create order -> create session -> check status"""
        # Step 1: Create order
        order_data = {
            "items": [{"product_id": "flow-test", "name": "Flow Test Tile", "variant": "", "price": 75.00, "quantity": 2, "image": ""}],
            "customer": {"email": "flow-test@example.com", "firstName": "Flow", "lastName": "Test", "phone": "07999888777"},
            "delivery": {"method": "delivery", "address1": "Flow Test Road", "city": "Manchester", "postcode": "M1 1AA"},
            "payment": {"method": "card"},
            "subtotal": 150.00,
            "delivery_fee": 79.99,
            "total": 229.99
        }
        
        order_response = requests.post(f"{BASE_URL}/api/shop/guest-checkout", json=order_data)
        assert order_response.status_code == 200
        order = order_response.json()
        print(f"  Step 1: Order created - {order['order_number']}")
        
        # Step 2: Create Stripe session
        pay_response = requests.post(
            f"{BASE_URL}/api/shop/guest-checkout/pay",
            json={"order_id": order["order_id"], "origin_url": BASE_URL}
        )
        assert pay_response.status_code == 200
        session = pay_response.json()
        print(f"  Step 2: Stripe session created - {session['session_id'][:30]}...")
        
        # Step 3: Check status (simulating what OrderSuccessPage does)
        status_response = requests.get(f"{BASE_URL}/api/shop/guest-checkout/status/{session['session_id']}")
        assert status_response.status_code == 200
        status = status_response.json()
        
        # Verify order details are returned
        assert status["order"]["order_number"] == order["order_number"]
        assert status["order"]["customer_email"] == "flow-test@example.com"
        print(f"  Step 3: Status checked - {status['status']}")
        
        print("✓ Complete checkout flow works correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

"""
Test Bulk Category Editor Scope Save Mechanism
Tests the bulk-update-unified endpoint with id_field parameter for products with/without SKUs
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBulkUpdateUnified:
    """Tests for /api/supplier-sync/products/bulk-update-unified endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "admin123"
        })
        if login_response.status_code == 200:
            token = login_response.json().get("token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
        yield
    
    def test_01_endpoint_exists(self):
        """Test that bulk-update-unified endpoint exists"""
        # Send minimal request to check endpoint exists
        response = self.session.post(f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified", json={
            "product_ids": [],
            "updates": {}
        })
        # Should return 400 (bad request) not 404 (not found)
        assert response.status_code in [400, 422], f"Expected 400/422, got {response.status_code}"
        print(f"Endpoint exists - returns {response.status_code} for empty request")
    
    def test_02_bulk_update_with_sku_id_field(self):
        """Test bulk update with id_field='sku'"""
        # First get some products with SKUs
        products_response = self.session.get(f"{BASE_URL}/api/supplier-sync/products?supplier=Canopy&limit=5")
        assert products_response.status_code == 200, f"Failed to get products: {products_response.status_code}"
        
        products_data = products_response.json()
        products = products_data.get("products", products_data) if isinstance(products_data, dict) else products_data
        
        # Find products with SKUs
        products_with_sku = [p for p in products if p.get("sku")]
        if not products_with_sku:
            pytest.skip("No products with SKU found")
        
        test_sku = products_with_sku[0]["sku"]
        print(f"Testing with SKU: {test_sku}")
        
        # Test update with id_field='sku'
        response = self.session.post(f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified", json={
            "product_ids": [test_sku],
            "id_field": "sku",
            "updates": {
                "material": "Porcelain"
            },
            "mode": "replace"
        })
        
        assert response.status_code == 200, f"Bulk update failed: {response.status_code} - {response.text}"
        result = response.json()
        print(f"Update result: {result}")
        
        # Verify the update was applied
        assert "updated_count" in result or "total_updated" in result or "message" in result
    
    def test_03_bulk_update_with_supplier_code_id_field(self):
        """Test bulk update with id_field='supplier_code' for products without SKU"""
        # Get products - look for ones without SKU but with supplier_code
        products_response = self.session.get(f"{BASE_URL}/api/supplier-sync/products?supplier=ThermoSphere&limit=10")
        
        if products_response.status_code != 200:
            # Try another supplier
            products_response = self.session.get(f"{BASE_URL}/api/supplier-sync/products?limit=50")
        
        assert products_response.status_code == 200, f"Failed to get products: {products_response.status_code}"
        
        products_data = products_response.json()
        products = products_data.get("products", products_data) if isinstance(products_data, dict) else products_data
        
        # Find products without SKU but with supplier_code
        products_without_sku = [p for p in products if not p.get("sku") and p.get("supplier_code")]
        
        if not products_without_sku:
            # If no products without SKU, test with supplier_code anyway
            products_with_supplier_code = [p for p in products if p.get("supplier_code")]
            if not products_with_supplier_code:
                pytest.skip("No products with supplier_code found")
            test_supplier_code = products_with_supplier_code[0]["supplier_code"]
            print(f"Testing with supplier_code (product has SKU too): {test_supplier_code}")
        else:
            test_supplier_code = products_without_sku[0]["supplier_code"]
            print(f"Testing with supplier_code (product without SKU): {test_supplier_code}")
        
        # Test update with id_field='supplier_code'
        response = self.session.post(f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified", json={
            "product_ids": [test_supplier_code],
            "id_field": "supplier_code",
            "updates": {
                "finish": "Matt"
            },
            "mode": "replace"
        })
        
        assert response.status_code == 200, f"Bulk update with supplier_code failed: {response.status_code} - {response.text}"
        result = response.json()
        print(f"Update result: {result}")
    
    def test_04_bulk_update_multiple_products(self):
        """Test bulk update with multiple products"""
        # Get products
        products_response = self.session.get(f"{BASE_URL}/api/supplier-sync/products?supplier=Canopy&limit=3")
        assert products_response.status_code == 200
        
        products_data = products_response.json()
        products = products_data.get("products", products_data) if isinstance(products_data, dict) else products_data
        
        products_with_sku = [p for p in products if p.get("sku")]
        if len(products_with_sku) < 2:
            pytest.skip("Need at least 2 products with SKU")
        
        test_skus = [p["sku"] for p in products_with_sku[:2]]
        print(f"Testing with SKUs: {test_skus}")
        
        # Test bulk update
        response = self.session.post(f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified", json={
            "product_ids": test_skus,
            "id_field": "sku",
            "updates": {
                "type": "Wall Tile"
            },
            "mode": "replace"
        })
        
        assert response.status_code == 200, f"Bulk update failed: {response.status_code}"
        result = response.json()
        print(f"Bulk update result: {result}")
        
        # Verify count
        updated_count = result.get("updated_count") or result.get("total_updated") or 0
        assert updated_count >= 1, f"Expected at least 1 update, got {updated_count}"
    
    def test_05_bulk_update_with_fields_to_clear(self):
        """Test bulk update with fields_to_clear parameter"""
        # Get a product
        products_response = self.session.get(f"{BASE_URL}/api/supplier-sync/products?supplier=Canopy&limit=1")
        assert products_response.status_code == 200
        
        products_data = products_response.json()
        products = products_data.get("products", products_data) if isinstance(products_data, dict) else products_data
        
        if not products or not products[0].get("sku"):
            pytest.skip("No products with SKU found")
        
        test_sku = products[0]["sku"]
        
        # Test update with fields_to_clear
        response = self.session.post(f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified", json={
            "product_ids": [test_sku],
            "id_field": "sku",
            "updates": {
                "material": "Porcelain"
            },
            "fields_to_clear": {
                "made_in": True
            },
            "mode": "replace"
        })
        
        assert response.status_code == 200, f"Bulk update with fields_to_clear failed: {response.status_code}"
        print(f"Update with fields_to_clear successful")
    
    def test_06_bulk_update_with_update_mode_append(self):
        """Test bulk update with update_mode='append' (only fill empty fields)"""
        # Get a product
        products_response = self.session.get(f"{BASE_URL}/api/supplier-sync/products?supplier=Canopy&limit=1")
        assert products_response.status_code == 200
        
        products_data = products_response.json()
        products = products_data.get("products", products_data) if isinstance(products_data, dict) else products_data
        
        if not products or not products[0].get("sku"):
            pytest.skip("No products with SKU found")
        
        test_sku = products[0]["sku"]
        
        # Test update with update_mode='append'
        response = self.session.post(f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified", json={
            "product_ids": [test_sku],
            "id_field": "sku",
            "updates": {
                "slip_rating": "R10"
            },
            "mode": "replace",
            "update_mode": "append"
        })
        
        assert response.status_code == 200, f"Bulk update with append mode failed: {response.status_code}"
        print(f"Update with append mode successful")
    
    def test_07_bulk_update_category_assignment(self):
        """Test bulk update with category assignment (main_category, sub_categories)"""
        # Get a product
        products_response = self.session.get(f"{BASE_URL}/api/supplier-sync/products?supplier=Canopy&limit=1")
        assert products_response.status_code == 200
        
        products_data = products_response.json()
        products = products_data.get("products", products_data) if isinstance(products_data, dict) else products_data
        
        if not products or not products[0].get("sku"):
            pytest.skip("No products with SKU found")
        
        test_sku = products[0]["sku"]
        
        # Test category assignment
        response = self.session.post(f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified", json={
            "product_ids": [test_sku],
            "id_field": "sku",
            "updates": {
                "main_category": "Wall Tiles",
                "sub_categories": ["Bathroom", "Kitchen"]
            },
            "mode": "replace"
        })
        
        assert response.status_code == 200, f"Category assignment failed: {response.status_code}"
        print(f"Category assignment successful")


class TestSupplierProductsAPI:
    """Tests for supplier products listing API"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "admin123"
        })
        if login_response.status_code == 200:
            token = login_response.json().get("token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
        yield
    
    def test_01_get_supplier_products(self):
        """Test getting supplier products"""
        response = self.session.get(f"{BASE_URL}/api/supplier-sync/products?supplier=Canopy&limit=10")
        assert response.status_code == 200, f"Failed to get products: {response.status_code}"
        
        data = response.json()
        products = data.get("products", data) if isinstance(data, dict) else data
        
        assert len(products) > 0, "No products returned"
        print(f"Got {len(products)} products")
        
        # Check product structure
        first_product = products[0]
        print(f"Product keys: {list(first_product.keys())[:10]}...")
        
        # Verify key fields exist
        assert "product_name" in first_product or "name" in first_product, "Product missing name field"
    
    def test_02_products_have_id_fields(self):
        """Test that products have either sku or supplier_code for identification"""
        response = self.session.get(f"{BASE_URL}/api/supplier-sync/products?supplier=Canopy&limit=20")
        assert response.status_code == 200
        
        data = response.json()
        products = data.get("products", data) if isinstance(data, dict) else data
        
        products_with_sku = 0
        products_with_supplier_code = 0
        products_with_neither = 0
        
        for p in products:
            has_sku = bool(p.get("sku"))
            has_supplier_code = bool(p.get("supplier_code"))
            
            if has_sku:
                products_with_sku += 1
            if has_supplier_code:
                products_with_supplier_code += 1
            if not has_sku and not has_supplier_code:
                products_with_neither += 1
        
        print(f"Products with SKU: {products_with_sku}")
        print(f"Products with supplier_code: {products_with_supplier_code}")
        print(f"Products with neither: {products_with_neither}")
        
        # All products should have at least one identifier
        assert products_with_neither == 0, f"{products_with_neither} products have no identifier"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

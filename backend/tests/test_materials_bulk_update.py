"""
Test materials array field in bulk-update-unified endpoint.
Tests the fix for Smart Suggestions toggle in Bulk Category Editor.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestMaterialsBulkUpdate:
    """Test materials array field handling in bulk-update-unified endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get auth token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "qasim@tilestation.co.uk",
            "password": "Tilestation_9614"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        token = login_response.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Find a test product with SKU
        products_response = self.session.get(f"{BASE_URL}/api/supplier-sync/products?search=slate&limit=5")
        assert products_response.status_code == 200
        products = products_response.json().get("products", [])
        
        # Find a product with a SKU
        self.test_sku = None
        for p in products:
            if p.get("sku"):
                self.test_sku = p.get("sku")
                break
        
        if not self.test_sku:
            pytest.skip("No product with SKU found for testing")
        
        yield
        
        # Cleanup: Reset materials to empty
        self.session.post(f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified", json={
            "product_ids": [self.test_sku],
            "updates": {"materials": []},
            "mode": "replace"
        })
    
    def test_add_materials_array(self):
        """Test adding materials array via bulk-update-unified"""
        # Add materials
        response = self.session.post(f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified", json={
            "product_ids": [self.test_sku],
            "updates": {
                "materials": ["Natural Stone", "Stone Effect"]
            },
            "mode": "replace"
        })
        
        assert response.status_code == 200, f"Failed to add materials: {response.text}"
        data = response.json()
        assert data.get("success") == True
        assert data.get("supplier_products_updated", 0) >= 1 or data.get("updated_count", 0) >= 1
        
        # Verify materials were saved
        get_response = self.session.get(f"{BASE_URL}/api/supplier-sync/products?search={self.test_sku}&limit=1")
        assert get_response.status_code == 200
        products = get_response.json().get("products", [])
        assert len(products) > 0, "Product not found after update"
        
        product = products[0]
        assert "materials" in product, "materials field not in API response"
        assert product["materials"] == ["Natural Stone", "Stone Effect"], f"Materials mismatch: {product['materials']}"
    
    def test_remove_materials_array(self):
        """Test removing materials (clearing to empty array) via bulk-update-unified"""
        # First add materials
        self.session.post(f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified", json={
            "product_ids": [self.test_sku],
            "updates": {"materials": ["Natural Stone", "Stone Effect"]},
            "mode": "replace"
        })
        
        # Now remove materials by setting to empty array
        response = self.session.post(f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified", json={
            "product_ids": [self.test_sku],
            "updates": {"materials": []},
            "mode": "replace"
        })
        
        assert response.status_code == 200, f"Failed to remove materials: {response.text}"
        
        # Verify materials were cleared
        get_response = self.session.get(f"{BASE_URL}/api/supplier-sync/products?search={self.test_sku}&limit=1")
        assert get_response.status_code == 200
        products = get_response.json().get("products", [])
        assert len(products) > 0
        
        product = products[0]
        assert product.get("materials") == [], f"Materials not cleared: {product.get('materials')}"
    
    def test_toggle_single_material(self):
        """Test toggling a single material on and off (simulates UI toggle)"""
        # Toggle ON: Add single material
        response = self.session.post(f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified", json={
            "product_ids": [self.test_sku],
            "updates": {"materials": ["Natural Stone"]},
            "mode": "replace"
        })
        assert response.status_code == 200
        
        # Verify ON
        get_response = self.session.get(f"{BASE_URL}/api/supplier-sync/products?search={self.test_sku}&limit=1")
        product = get_response.json().get("products", [])[0]
        assert "Natural Stone" in product.get("materials", [])
        
        # Toggle OFF: Remove material
        response = self.session.post(f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified", json={
            "product_ids": [self.test_sku],
            "updates": {"materials": []},
            "mode": "replace"
        })
        assert response.status_code == 200
        
        # Verify OFF
        get_response = self.session.get(f"{BASE_URL}/api/supplier-sync/products?search={self.test_sku}&limit=1")
        product = get_response.json().get("products", [])[0]
        assert product.get("materials") == []
    
    def test_materials_with_other_arrays(self):
        """Test materials alongside other array fields (rooms, styles, colors, features)"""
        response = self.session.post(f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified", json={
            "product_ids": [self.test_sku],
            "updates": {
                "materials": ["Natural Stone"],
                "rooms": ["bathroom", "kitchen"],
                "styles": ["modern"],
                "colors": ["grey"],
                "features": ["anti_slip"]
            },
            "mode": "replace"
        })
        
        assert response.status_code == 200
        
        # Verify all arrays were saved
        get_response = self.session.get(f"{BASE_URL}/api/supplier-sync/products?search={self.test_sku}&limit=1")
        product = get_response.json().get("products", [])[0]
        
        assert product.get("materials") == ["Natural Stone"]
        assert "bathroom" in product.get("rooms", [])
        assert "kitchen" in product.get("rooms", [])
        assert "modern" in product.get("styles", [])
        assert "grey" in product.get("colors", [])
        assert "anti_slip" in product.get("features", [])
    
    def test_materials_append_mode(self):
        """Test materials in append mode (adds to existing)"""
        # First set initial materials
        self.session.post(f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified", json={
            "product_ids": [self.test_sku],
            "updates": {"materials": ["Natural Stone"]},
            "mode": "replace"
        })
        
        # Append more materials
        response = self.session.post(f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified", json={
            "product_ids": [self.test_sku],
            "updates": {"materials": ["Stone Effect"]},
            "mode": "append"
        })
        
        assert response.status_code == 200
        
        # Verify both materials exist
        get_response = self.session.get(f"{BASE_URL}/api/supplier-sync/products?search={self.test_sku}&limit=1")
        product = get_response.json().get("products", [])[0]
        materials = product.get("materials", [])
        
        assert "Natural Stone" in materials, f"Original material missing: {materials}"
        assert "Stone Effect" in materials, f"Appended material missing: {materials}"
    
    def test_materials_field_in_api_response(self):
        """Test that materials field is included in API response"""
        get_response = self.session.get(f"{BASE_URL}/api/supplier-sync/products?search={self.test_sku}&limit=1")
        assert get_response.status_code == 200
        
        products = get_response.json().get("products", [])
        assert len(products) > 0
        
        product = products[0]
        # materials field should exist (even if empty)
        assert "materials" in product, f"materials field missing from API response. Keys: {list(product.keys())}"


class TestBulkUpdateUnifiedArrayFields:
    """Test all array fields in bulk-update-unified endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "qasim@tilestation.co.uk",
            "password": "Tilestation_9614"
        })
        assert login_response.status_code == 200
        token = login_response.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Find test product
        products_response = self.session.get(f"{BASE_URL}/api/supplier-sync/products?limit=5")
        products = products_response.json().get("products", [])
        
        self.test_sku = None
        for p in products:
            if p.get("sku"):
                self.test_sku = p.get("sku")
                break
        
        if not self.test_sku:
            pytest.skip("No product with SKU found")
        
        yield
        
        # Cleanup
        self.session.post(f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified", json={
            "product_ids": [self.test_sku],
            "updates": {
                "materials": [],
                "rooms": [],
                "styles": [],
                "colors": [],
                "features": [],
                "sub_categories": []
            },
            "mode": "replace"
        })
    
    def test_all_array_fields_recognized(self):
        """Test that all array fields are recognized by the endpoint"""
        array_fields = ["rooms", "materials", "styles", "colors", "features", "sub_categories"]
        
        for field in array_fields:
            response = self.session.post(f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified", json={
                "product_ids": [self.test_sku],
                "updates": {field: ["test_value"]},
                "mode": "replace"
            })
            
            assert response.status_code == 200, f"Failed for field {field}: {response.text}"
            data = response.json()
            assert data.get("success") == True, f"Update not successful for field {field}"
    
    def test_clear_all_array_fields(self):
        """Test clearing all array fields with empty arrays"""
        # First set values
        self.session.post(f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified", json={
            "product_ids": [self.test_sku],
            "updates": {
                "materials": ["test"],
                "rooms": ["test"],
                "styles": ["test"],
                "colors": ["test"],
                "features": ["test"]
            },
            "mode": "replace"
        })
        
        # Clear all
        response = self.session.post(f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified", json={
            "product_ids": [self.test_sku],
            "updates": {
                "materials": [],
                "rooms": [],
                "styles": [],
                "colors": [],
                "features": []
            },
            "mode": "replace"
        })
        
        assert response.status_code == 200
        
        # Verify all cleared
        get_response = self.session.get(f"{BASE_URL}/api/supplier-sync/products?search={self.test_sku}&limit=1")
        product = get_response.json().get("products", [])[0]
        
        assert product.get("materials") == [], f"materials not cleared: {product.get('materials')}"
        assert product.get("rooms") == [], f"rooms not cleared: {product.get('rooms')}"
        assert product.get("styles") == [], f"styles not cleared: {product.get('styles')}"
        assert product.get("colors") == [], f"colors not cleared: {product.get('colors')}"
        assert product.get("features") == [], f"features not cleared: {product.get('features')}"

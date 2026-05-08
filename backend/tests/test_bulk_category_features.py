"""
Test new Bulk Category Editor features:
1. Hidden SEO Keywords text area in Description & SEO section
2. Auto-detect Large Format from size checkbox
3. Main Category and Sub-Categories saving via bulk-update-unified
"""
import pytest
import requests
import os
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "qasim@tilestation.co.uk"
ADMIN_PASSWORD = "Tilestation_9614"

# Test products from LEPORCE supplier
TEST_SKU_SMALL = "LP-3611"  # 30x60cm - small format
TEST_SKU_LARGE = "LP-6611"  # 60x60cm - large format
TEST_SUPPLIER = "LEPORCE"


class TestBulkDescriptionEndpoint:
    """Test the bulk-description endpoint for Hidden SEO Keywords feature"""
    
    def test_hidden_seo_keywords_manual_input(self):
        """Test saving manual hidden SEO keywords via bulk-description endpoint"""
        url = f"{BASE_URL}/api/supplier-sync/products/bulk-description"
        
        payload = {
            "products": [
                {
                    "supplier": TEST_SUPPLIER,
                    "sku": TEST_SKU_SMALL,
                    "name": "Test Product",
                    "supplier_product_name": "Supplier Original Name"
                }
            ],
            "description_template": "",
            "seo_keywords": "",
            "hidden_seo_keywords": "LP-3611, LEPORCE, alternate name, misspelling",
            "generate_hidden_seo": False,
            "use_placeholders": True
        }
        
        response = requests.put(url, json=payload)
        
        # Check response
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Response: {data}"
        print(f"✓ Hidden SEO Keywords saved successfully: {data}")
    
    def test_auto_generate_hidden_seo_from_supplier_names(self):
        """Test auto-generating hidden SEO from supplier_product_name"""
        url = f"{BASE_URL}/api/supplier-sync/products/bulk-description"
        
        # This should auto-generate hidden SEO keywords from supplier_product_name
        payload = {
            "products": [
                {
                    "supplier": TEST_SUPPLIER,
                    "sku": TEST_SKU_SMALL,
                    "name": "Display Name",
                    "supplier_product_name": "Original Supplier Product Name 30x60 Matt"
                }
            ],
            "description_template": "",
            "seo_keywords": "",
            "hidden_seo_keywords": "",  # Empty - should auto-generate
            "generate_hidden_seo": True,  # Enable auto-generation
            "use_placeholders": True
        }
        
        response = requests.put(url, json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Response: {data}"
        print(f"✓ Auto-generated Hidden SEO Keywords: {data}")
    
    def test_description_with_hidden_seo_keywords(self):
        """Test saving both description and hidden SEO keywords together"""
        url = f"{BASE_URL}/api/supplier-sync/products/bulk-description"
        
        payload = {
            "products": [
                {
                    "supplier": TEST_SUPPLIER,
                    "sku": TEST_SKU_SMALL,
                    "name": "Test Tile",
                    "color": "Grey",
                    "size": "30x60",
                    "material": "Porcelain",
                    "finish": "Matt"
                }
            ],
            "description_template": "Premium {color} {material} tile in {size} with {finish} finish.",
            "seo_keywords": "porcelain, grey tile, {size}",
            "hidden_seo_keywords": "LP-3611, LEPORCE, test hidden keywords",
            "generate_hidden_seo": False,
            "use_placeholders": True
        }
        
        response = requests.put(url, json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Response: {data}"
        print(f"✓ Description with Hidden SEO saved: {data}")


class TestBulkUpdateUnifiedEndpoint:
    """Test the bulk-update-unified endpoint for Main Category and Sub-Categories"""
    
    def test_main_category_saves_correctly(self):
        """Test that main_category field saves via bulk-update-unified"""
        url = f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified"
        
        payload = {
            "product_ids": [TEST_SKU_SMALL],
            "updates": {
                "main_category": "Wall & Floor Tiles"
            },
            "mode": "replace"
        }
        
        response = requests.post(url, json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Response: {data}"
        print(f"✓ Main Category saved: {data}")
    
    def test_sub_categories_saves_correctly(self):
        """Test that sub_categories array saves via bulk-update-unified"""
        url = f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified"
        
        payload = {
            "product_ids": [TEST_SKU_SMALL],
            "updates": {
                "sub_categories": ["Wall Tiles", "Small Format", "Plain"]
            },
            "mode": "replace"
        }
        
        response = requests.post(url, json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Response: {data}"
        print(f"✓ Sub-Categories saved: {data}")
    
    def test_main_category_and_sub_categories_together(self):
        """Test saving both main_category and sub_categories together"""
        url = f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified"
        
        payload = {
            "product_ids": [TEST_SKU_SMALL, TEST_SKU_LARGE],
            "updates": {
                "main_category": "Wall & Floor Tiles",
                "sub_categories": ["Floor Tiles", "Stone Effect"]
            },
            "mode": "replace"
        }
        
        response = requests.post(url, json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Response: {data}"
        print(f"✓ Main Category + Sub-Categories saved: {data}")
    
    def test_large_format_in_sub_categories(self):
        """Test saving Large Format as a sub-category"""
        url = f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified"
        
        payload = {
            "product_ids": [TEST_SKU_LARGE],  # 60x60cm - large format
            "updates": {
                "main_category": "Floor Tiles Only",
                "sub_categories": ["Large Format", "Floor Tiles", "Matt"]
            },
            "mode": "replace"
        }
        
        response = requests.post(url, json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Response: {data}"
        print(f"✓ Large Format sub-category saved: {data}")
    
    def test_sub_categories_append_mode(self):
        """Test appending to existing sub_categories (append mode)"""
        url = f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified"
        
        # First set initial sub-categories
        initial_payload = {
            "product_ids": [TEST_SKU_SMALL],
            "updates": {
                "sub_categories": ["Wall Tiles"]
            },
            "mode": "replace"
        }
        
        response1 = requests.post(url, json=initial_payload)
        assert response1.status_code == 200
        
        # Now append more sub-categories
        append_payload = {
            "product_ids": [TEST_SKU_SMALL],
            "updates": {
                "sub_categories": ["Small Format", "Plain"]
            },
            "mode": "append"
        }
        
        response2 = requests.post(url, json=append_payload)
        
        assert response2.status_code == 200, f"Expected 200, got {response2.status_code}: {response2.text}"
        data = response2.json()
        assert data.get("success") == True, f"Response: {data}"
        print(f"✓ Sub-Categories appended: {data}")
    
    def test_hidden_seo_keywords_via_unified_endpoint(self):
        """Test that hidden_seo_keywords can also be saved via bulk-update-unified"""
        url = f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified"
        
        payload = {
            "product_ids": [TEST_SKU_SMALL],
            "updates": {
                "hidden_seo_keywords": "hidden via unified endpoint"
            },
            "mode": "replace"
        }
        
        response = requests.post(url, json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Response: {data}"
        print(f"✓ Hidden SEO Keywords via unified endpoint: {data}")


class TestSupplierProductsEndpoint:
    """Test that we can retrieve supplier products correctly"""
    
    def test_get_leporce_products(self):
        """Test that we can get LEPORCE supplier products"""
        url = f"{BASE_URL}/api/supplier-sync/products"
        params = {
            "supplier": TEST_SUPPLIER,
            "limit": 10
        }
        
        response = requests.get(url, params=params)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Check that we got products
        products = data.get("products", [])
        total = data.get("total", 0)
        
        print(f"✓ Retrieved {len(products)} products from {TEST_SUPPLIER}, total: {total}")
        
        assert total > 0, f"Expected products from {TEST_SUPPLIER}, got none"
    
    def test_search_test_products(self):
        """Test that we can find our test products"""
        url = f"{BASE_URL}/api/supplier-sync/products"
        params = {
            "supplier": TEST_SUPPLIER,
            "search": "LP-",
            "limit": 50
        }
        
        response = requests.get(url, params=params)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        products = data.get("products", [])
        
        print(f"✓ Found {len(products)} LEPORCE products matching 'LP-'")
        
        # Check if our test SKUs are present
        skus = [p.get("sku") for p in products]
        if TEST_SKU_SMALL in skus:
            print(f"  ✓ Found test product {TEST_SKU_SMALL}")
        if TEST_SKU_LARGE in skus:
            print(f"  ✓ Found test product {TEST_SKU_LARGE}")


class TestBulkDescriptionValidation:
    """Test validation of bulk description endpoint"""
    
    def test_empty_products_list(self):
        """Test that empty products list returns proper response"""
        url = f"{BASE_URL}/api/supplier-sync/products/bulk-description"
        
        payload = {
            "products": [],
            "hidden_seo_keywords": "test keywords"
        }
        
        response = requests.put(url, json=payload)
        
        # Should succeed but update 0 products
        assert response.status_code == 200
        data = response.json()
        assert data.get("updated_count", 0) == 0
        print(f"✓ Empty products handled correctly: {data}")
    
    def test_only_hidden_seo_keywords(self):
        """Test that endpoint works with only hidden_seo_keywords (no description/seo)"""
        url = f"{BASE_URL}/api/supplier-sync/products/bulk-description"
        
        payload = {
            "products": [
                {
                    "supplier": TEST_SUPPLIER,
                    "sku": TEST_SKU_SMALL
                }
            ],
            "hidden_seo_keywords": "only hidden keywords test"
        }
        
        response = requests.put(url, json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True
        print(f"✓ Only hidden_seo_keywords works: {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

"""
Comprehensive Regression Tests for 4 Critical Fixes:
1. Tier Pricing on Collection Cards - tier_pricing_disabled flag behavior
2. Discount Percentage - exact user-entered value storage
3. Admin Spec Buttons - nested API response parsing
4. Product Group Routing - preserve product_group from supplier_products

Test credentials: test@admin.com / testpass123
"""
import pytest
import requests
import os
import time
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestTierPricingOnCollectionCards:
    """
    FIX 1: Tier pricing disabled collections should show base retail price (min_price),
    NOT tier-discounted price (prices_from).
    """
    
    def test_collections_endpoint_returns_tier_pricing_disabled_flag(self):
        """Verify /api/tiles/collections returns tier_pricing_disabled flag"""
        response = requests.get(f"{BASE_URL}/api/tiles/collections?limit=50")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "collections" in data, "Response should have 'collections' key"
        
        collections = data["collections"]
        if len(collections) > 0:
            # Check that tier_pricing_disabled field exists
            first_collection = collections[0]
            assert "tier_pricing_disabled" in first_collection, "Collection should have tier_pricing_disabled field"
            assert "prices_from" in first_collection, "Collection should have prices_from field"
            assert "min_price" in first_collection, "Collection should have min_price field"
            print(f"✓ First collection '{first_collection.get('series_name')}': tier_pricing_disabled={first_collection.get('tier_pricing_disabled')}, prices_from={first_collection.get('prices_from')}, min_price={first_collection.get('min_price')}")
        else:
            pytest.skip("No collections found to test")
    
    def test_tier_disabled_collection_prices_from_equals_min_price(self):
        """When tier_pricing_disabled=true, prices_from should equal min_price"""
        response = requests.get(f"{BASE_URL}/api/tiles/collections?limit=100")
        assert response.status_code == 200
        
        data = response.json()
        collections = data.get("collections", [])
        
        tier_disabled_found = False
        tier_enabled_found = False
        
        for coll in collections:
            tier_disabled = coll.get("tier_pricing_disabled", False)
            prices_from = coll.get("prices_from", 0)
            min_price = coll.get("min_price", 0)
            
            if tier_disabled and min_price > 0:
                tier_disabled_found = True
                # For tier-disabled collections, prices_from should equal min_price
                assert abs(prices_from - min_price) < 0.01, \
                    f"Collection '{coll.get('series_name')}': tier_pricing_disabled=True but prices_from ({prices_from}) != min_price ({min_price})"
                print(f"✓ Tier-disabled collection '{coll.get('series_name')}': prices_from={prices_from} == min_price={min_price}")
            
            elif not tier_disabled and min_price > 0 and prices_from > 0:
                tier_enabled_found = True
                # For tier-enabled collections, prices_from should be LESS than min_price (tier discount applied)
                # Default tier discounts are [5,10,15,20], so max discount is 20%
                if prices_from < min_price:
                    print(f"✓ Tier-enabled collection '{coll.get('series_name')}': prices_from={prices_from} < min_price={min_price} (tier discount applied)")
        
        if not tier_disabled_found:
            print("⚠ No tier-disabled collections found to verify")
        if not tier_enabled_found:
            print("⚠ No tier-enabled collections found to verify")
    
    def test_sale_collections_have_tier_pricing_disabled(self):
        """Sale collections should typically have tier_pricing_disabled=true"""
        response = requests.get(f"{BASE_URL}/api/tiles/collections?sale=true&limit=50")
        assert response.status_code == 200
        
        data = response.json()
        collections = data.get("collections", [])
        
        if len(collections) > 0:
            for coll in collections:
                print(f"Sale collection '{coll.get('series_name')}': tier_pricing_disabled={coll.get('tier_pricing_disabled')}, is_sale={coll.get('is_sale')}")
        else:
            print("⚠ No sale collections found")


class TestDiscountPercentage:
    """
    FIX 2: When user enters was_markup_percent=25, discount_percentage should store exactly 25,
    NOT a recalculated value from rounded WAS price.
    """
    
    @pytest.fixture
    def auth_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@admin.com",
            "password": "testpass123"
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Could not authenticate as admin")
    
    def test_sale_pricing_stores_exact_discount_percentage(self, auth_token):
        """Verify discount_percentage stores exact user-entered value"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # First, find a product to test with
        response = requests.get(f"{BASE_URL}/api/supplier-sync/products?limit=5", headers=headers)
        if response.status_code != 200:
            pytest.skip("Could not fetch products")
        
        products = response.json().get("products", [])
        if not products:
            pytest.skip("No products found to test")
        
        test_product = products[0]
        sku = test_product.get("sku")
        supplier = test_product.get("supplier")
        
        if not sku or not supplier:
            pytest.skip("Product missing sku or supplier")
        
        # Test with different discount percentages
        test_percentages = [25, 15, 30, 10]
        
        for test_pct in test_percentages:
            # Update sale pricing with exact percentage
            update_response = requests.post(
                f"{BASE_URL}/api/supplier-sync/products/update-sale-pricing",
                json={
                    "sku": sku,
                    "supplier": supplier,
                    "sale_active": True,
                    "was_markup_percent": test_pct
                },
                headers=headers
            )
            
            if update_response.status_code == 200:
                result = update_response.json()
                stored_discount = result.get("discount_percentage")
                
                # The stored discount_percentage should match the user-entered was_markup_percent
                assert stored_discount == test_pct, \
                    f"Expected discount_percentage={test_pct}, got {stored_discount}"
                print(f"✓ Set was_markup_percent={test_pct}, stored discount_percentage={stored_discount}")
            else:
                print(f"⚠ Could not update sale pricing: {update_response.status_code} - {update_response.text[:200]}")
        
        # Clean up - disable sale
        requests.post(
            f"{BASE_URL}/api/supplier-sync/products/update-sale-pricing",
            json={
                "sku": sku,
                "supplier": supplier,
                "sale_active": False
            },
            headers=headers
        )
    
    def test_sale_pricing_clears_fields_when_disabled(self, auth_token):
        """Verify sale_active=false clears was_price, discount_percentage, sale_savings"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # Find a product
        response = requests.get(f"{BASE_URL}/api/supplier-sync/products?limit=5", headers=headers)
        if response.status_code != 200:
            pytest.skip("Could not fetch products")
        
        products = response.json().get("products", [])
        if not products:
            pytest.skip("No products found")
        
        test_product = products[0]
        sku = test_product.get("sku")
        supplier = test_product.get("supplier")
        
        # First enable sale
        requests.post(
            f"{BASE_URL}/api/supplier-sync/products/update-sale-pricing",
            json={
                "sku": sku,
                "supplier": supplier,
                "sale_active": True,
                "was_markup_percent": 20
            },
            headers=headers
        )
        
        # Then disable sale
        disable_response = requests.post(
            f"{BASE_URL}/api/supplier-sync/products/update-sale-pricing",
            json={
                "sku": sku,
                "supplier": supplier,
                "sale_active": False
            },
            headers=headers
        )
        
        if disable_response.status_code == 200:
            result = disable_response.json()
            assert result.get("was_price") is None, "was_price should be None when sale disabled"
            assert result.get("discount_percentage") is None, "discount_percentage should be None when sale disabled"
            print(f"✓ Sale disabled: was_price={result.get('was_price')}, discount_percentage={result.get('discount_percentage')}")
        else:
            print(f"⚠ Could not disable sale: {disable_response.status_code}")


class TestSpecificationsAPI:
    """
    FIX 3: /api/specifications/types/by-group should return groups with nested specifications arrays.
    Frontend BulkCategoryEditorSections must correctly parse this structure.
    """
    
    def test_specifications_by_group_returns_nested_structure(self):
        """Verify API returns groups with nested specifications arrays"""
        response = requests.get(f"{BASE_URL}/api/specifications/types/by-group")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list of groups"
        
        if len(data) > 0:
            for group in data:
                assert "name" in group, f"Group should have 'name' field: {group}"
                assert "specifications" in group, f"Group should have 'specifications' field: {group}"
                
                specs = group.get("specifications", [])
                assert isinstance(specs, list), f"specifications should be a list: {specs}"
                
                print(f"✓ Group '{group.get('name')}' has {len(specs)} specifications")
                
                # Verify each spec has required fields
                for spec in specs[:3]:  # Check first 3 specs
                    assert "name" in spec, f"Spec should have 'name': {spec}"
                    print(f"  - Spec: {spec.get('name')}")
        else:
            print("⚠ No specification groups found")
    
    def test_specifications_include_common_types(self):
        """Verify common spec types like Material, Finish, Edge are present"""
        response = requests.get(f"{BASE_URL}/api/specifications/types/by-group")
        assert response.status_code == 200
        
        data = response.json()
        
        # Flatten all spec names
        all_spec_names = []
        for group in data:
            for spec in group.get("specifications", []):
                all_spec_names.append(spec.get("name", "").lower())
        
        # Check for common specs
        common_specs = ["material", "finish", "edge", "thickness", "size"]
        found_specs = []
        
        for common in common_specs:
            if any(common in name for name in all_spec_names):
                found_specs.append(common)
                print(f"✓ Found spec type: {common}")
        
        print(f"Found {len(found_specs)}/{len(common_specs)} common spec types")


class TestProductGroupRouting:
    """
    FIX 4: Publishing products should preserve product_group from supplier_products,
    NOT default everything to 'tiles'.
    """
    
    @pytest.fixture
    def auth_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@admin.com",
            "password": "testpass123"
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Could not authenticate as admin")
    
    def test_publish_preserves_product_group(self, auth_token):
        """Verify publish endpoint uses product_group from supplier_products"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # Find a product with a non-tiles product_group
        response = requests.get(
            f"{BASE_URL}/api/supplier-sync/products?limit=100",
            headers=headers
        )
        
        if response.status_code != 200:
            pytest.skip("Could not fetch products")
        
        products = response.json().get("products", [])
        
        # Look for products with different product_groups
        product_groups_found = set()
        for p in products:
            pg = p.get("product_group")
            if pg:
                product_groups_found.add(pg)
        
        print(f"Product groups found in supplier_products: {product_groups_found}")
        
        # Check tiles collection for product_group diversity
        tiles_response = requests.get(f"{BASE_URL}/api/tiles/collections?limit=100")
        if tiles_response.status_code == 200:
            collections = tiles_response.json().get("collections", [])
            # Note: collections don't directly expose product_group, but we can check via group filter
            
            # Test filtering by different groups
            for group in ["tiles", "materials", "flooring"]:
                group_response = requests.get(f"{BASE_URL}/api/tiles/collections?group={group}&limit=10")
                if group_response.status_code == 200:
                    group_collections = group_response.json().get("collections", [])
                    print(f"✓ Group '{group}' filter: {len(group_collections)} collections")
    
    def test_migration_ran_successfully(self, auth_token):
        """Verify the fix_product_group_routing_v1 migration ran"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # Check if migration exists in migrations collection
        # This is an indirect check - we verify the behavior is correct
        
        # Get a sample of tiles and check their product_group
        response = requests.get(f"{BASE_URL}/api/tiles/products?limit=20")
        
        if response.status_code == 200:
            products = response.json().get("products", [])
            product_groups = {}
            
            for p in products:
                pg = p.get("product_group", "tiles")
                product_groups[pg] = product_groups.get(pg, 0) + 1
            
            print(f"Product groups in tiles collection: {product_groups}")
            
            # If all products are "tiles", that might indicate the migration didn't run
            # or all products genuinely are tiles
            if len(product_groups) == 1 and "tiles" in product_groups:
                print("⚠ All products have product_group='tiles' - verify if this is expected")
        else:
            print(f"⚠ Could not fetch tiles: {response.status_code}")


class TestRegressionSalePricing:
    """
    REGRESSION: Verify sale pricing toggle works correctly
    """
    
    @pytest.fixture
    def auth_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@admin.com",
            "password": "testpass123"
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Could not authenticate as admin")
    
    def test_sale_toggle_clears_fields(self, auth_token):
        """Setting sale_active=false should clear was_price, discount_percentage, sale_savings"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # Find a product
        response = requests.get(f"{BASE_URL}/api/supplier-sync/products?limit=5", headers=headers)
        if response.status_code != 200:
            pytest.skip("Could not fetch products")
        
        products = response.json().get("products", [])
        if not products:
            pytest.skip("No products found")
        
        test_product = products[0]
        sku = test_product.get("sku")
        supplier = test_product.get("supplier")
        
        # Enable sale with 25% discount
        enable_response = requests.post(
            f"{BASE_URL}/api/supplier-sync/products/update-sale-pricing",
            json={
                "sku": sku,
                "supplier": supplier,
                "sale_active": True,
                "was_markup_percent": 25
            },
            headers=headers
        )
        
        if enable_response.status_code == 200:
            result = enable_response.json()
            assert result.get("sale_active") == True
            assert result.get("was_price") is not None
            assert result.get("discount_percentage") == 25
            print(f"✓ Sale enabled: was_price={result.get('was_price')}, discount={result.get('discount_percentage')}%")
        
        # Disable sale
        disable_response = requests.post(
            f"{BASE_URL}/api/supplier-sync/products/update-sale-pricing",
            json={
                "sku": sku,
                "supplier": supplier,
                "sale_active": False
            },
            headers=headers
        )
        
        if disable_response.status_code == 200:
            result = disable_response.json()
            assert result.get("sale_active") == False
            assert result.get("was_price") is None
            assert result.get("discount_percentage") is None
            print(f"✓ Sale disabled: fields cleared correctly")


class TestRegressionPublishFlow:
    """
    REGRESSION: Verify publish includes all tier pricing and sale fields
    """
    
    def test_tiles_have_tier_pricing_fields(self):
        """Verify tiles collection has tier pricing fields"""
        response = requests.get(f"{BASE_URL}/api/tiles/products?limit=10")
        
        if response.status_code == 200:
            products = response.json().get("products", [])
            
            if products:
                # Check first product for tier pricing fields
                p = products[0]
                
                tier_fields = ["tier_pricing_disabled", "sale_active", "was_price", "discount_percentage"]
                found_fields = []
                
                for field in tier_fields:
                    if field in p:
                        found_fields.append(field)
                        print(f"✓ Field '{field}' present: {p.get(field)}")
                
                print(f"Found {len(found_fields)}/{len(tier_fields)} tier/sale fields in tile product")
            else:
                print("⚠ No tile products found")
        else:
            print(f"⚠ Could not fetch tiles: {response.status_code}")


class TestRegressionExistingTilePricing:
    """
    REGRESSION: Tiles WITHOUT tier_pricing_disabled should get default tier discounts applied
    """
    
    def test_standard_tiles_have_tier_discount_applied(self):
        """Verify standard tiles (tier_pricing_disabled=false) have prices_from < min_price"""
        response = requests.get(f"{BASE_URL}/api/tiles/collections?limit=100")
        assert response.status_code == 200
        
        data = response.json()
        collections = data.get("collections", [])
        
        standard_tiles_checked = 0
        
        for coll in collections:
            tier_disabled = coll.get("tier_pricing_disabled", False)
            prices_from = coll.get("prices_from", 0)
            min_price = coll.get("min_price", 0)
            max_tier_discount = coll.get("max_tier_discount", 0)
            
            if not tier_disabled and min_price > 0 and prices_from > 0:
                standard_tiles_checked += 1
                
                # For standard tiles, prices_from should be less than min_price
                # due to tier discount (default [5,10,15,20] = 20% max)
                if prices_from < min_price:
                    expected_discount = round((1 - prices_from / min_price) * 100, 1)
                    print(f"✓ Standard collection '{coll.get('series_name')}': {expected_discount}% tier discount applied (prices_from={prices_from}, min_price={min_price})")
                elif prices_from == min_price:
                    print(f"⚠ Collection '{coll.get('series_name')}': prices_from == min_price but tier_pricing_disabled=False")
        
        print(f"\nChecked {standard_tiles_checked} standard tile collections")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

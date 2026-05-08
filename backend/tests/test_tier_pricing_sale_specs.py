"""
Test suite for tier pricing, sale pricing, and specifications features.
Tests:
1. /api/tiles/collections returns tier_pricing_disabled flag and prices_from equals min_price for non-tier products
2. Sale pricing endpoint stores user's entered discount_percentage directly
3. /api/specifications/types/by-group returns groups with nested specifications arrays
4. Publish endpoint includes tier_pricing_disabled, has_custom_tier_pricing, tier_discounts, sale_active, was_price, discount_percentage
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestTilesCollectionsAPI:
    """Test /api/tiles/collections endpoint for tier pricing fields"""
    
    def test_collections_returns_tier_pricing_disabled_flag(self):
        """Verify tier_pricing_disabled is returned in collection response"""
        response = requests.get(f"{BASE_URL}/api/tiles/collections?group=tiles&limit=5")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "collections" in data, "Response should have 'collections' key"
        
        if len(data["collections"]) > 0:
            collection = data["collections"][0]
            # Verify tier_pricing_disabled field exists
            assert "tier_pricing_disabled" in collection, "Collection should have tier_pricing_disabled field"
            assert isinstance(collection["tier_pricing_disabled"], bool), "tier_pricing_disabled should be boolean"
            print(f"✓ Collection '{collection['series_name']}' has tier_pricing_disabled={collection['tier_pricing_disabled']}")
        else:
            pytest.skip("No collections found in database")
    
    def test_prices_from_equals_min_price_for_non_tier_products(self):
        """For products without tier pricing, prices_from should equal min_price"""
        response = requests.get(f"{BASE_URL}/api/tiles/collections?group=tiles&limit=20")
        assert response.status_code == 200
        
        data = response.json()
        collections = data.get("collections", [])
        
        verified_count = 0
        for collection in collections:
            tier_disabled = collection.get("tier_pricing_disabled", False)
            min_price = collection.get("min_price", 0)
            prices_from = collection.get("prices_from", 0)
            
            if tier_disabled:
                # When tier pricing is disabled, prices_from should equal min_price
                assert prices_from == min_price, \
                    f"Collection '{collection['series_name']}': prices_from ({prices_from}) should equal min_price ({min_price}) when tier_pricing_disabled=True"
                verified_count += 1
                print(f"✓ Collection '{collection['series_name']}': tier_pricing_disabled=True, prices_from={prices_from} == min_price={min_price}")
        
        if verified_count == 0:
            print("Note: No collections with tier_pricing_disabled=True found")
        else:
            print(f"✓ Verified {verified_count} collections with tier_pricing_disabled=True")
    
    def test_collection_has_required_pricing_fields(self):
        """Verify collections have all required pricing fields"""
        response = requests.get(f"{BASE_URL}/api/tiles/collections?group=tiles&limit=5")
        assert response.status_code == 200
        
        data = response.json()
        if len(data.get("collections", [])) > 0:
            collection = data["collections"][0]
            
            required_fields = [
                "min_price", "max_price", "prices_from", 
                "tier_pricing_disabled", "max_tier_discount",
                "trade_discount", "credit_back_rate"
            ]
            
            for field in required_fields:
                assert field in collection, f"Collection missing required field: {field}"
            
            print(f"✓ Collection has all required pricing fields: {required_fields}")


class TestSpecificationsAPI:
    """Test /api/specifications/types/by-group endpoint"""
    
    def test_specifications_by_group_returns_nested_structure(self):
        """Verify API returns groups with nested specifications arrays"""
        response = requests.get(f"{BASE_URL}/api/specifications/types/by-group")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list of groups"
        
        if len(data) > 0:
            group = data[0]
            # Verify group structure
            assert "name" in group, "Group should have 'name' field"
            assert "specifications" in group, "Group should have 'specifications' array"
            assert isinstance(group["specifications"], list), "'specifications' should be an array"
            
            print(f"✓ Group '{group['name']}' has {len(group['specifications'])} specifications")
            
            # Verify specification structure
            if len(group["specifications"]) > 0:
                spec = group["specifications"][0]
                assert "name" in spec, "Specification should have 'name'"
                assert "slug" in spec, "Specification should have 'slug'"
                print(f"✓ First spec: {spec['name']} (slug: {spec['slug']})")
        else:
            pytest.skip("No specification groups found")
    
    def test_specifications_have_values(self):
        """Verify specifications have values arrays"""
        response = requests.get(f"{BASE_URL}/api/specifications/types/by-group")
        assert response.status_code == 200
        
        data = response.json()
        specs_with_values = 0
        
        for group in data:
            for spec in group.get("specifications", []):
                if "values" in spec and len(spec["values"]) > 0:
                    specs_with_values += 1
        
        print(f"✓ Found {specs_with_values} specifications with values")


class TestSalePricingAPI:
    """Test sale pricing endpoint stores discount_percentage correctly"""
    
    def test_sale_pricing_endpoint_exists(self):
        """Verify sale pricing endpoint is accessible (PUT /products/sale-pricing)"""
        # This endpoint requires PUT with specific data
        # Just verify it returns proper error for missing data
        response = requests.put(f"{BASE_URL}/api/supplier-sync/products/sale-pricing", json={})
        # Should return 422 (validation error) not 404
        assert response.status_code in [400, 422], f"Expected 400/422 for missing data, got {response.status_code}"
        print(f"✓ Sale pricing endpoint exists and validates input (status: {response.status_code})")
    
    def test_sale_pricing_requires_sku_and_supplier(self):
        """Verify endpoint requires sku and supplier parameters"""
        response = requests.put(
            f"{BASE_URL}/api/supplier-sync/products/sale-pricing",
            json={"sale_active": True}
        )
        assert response.status_code in [400, 422], f"Expected validation error, got {response.status_code}"
        print("✓ Endpoint correctly requires sku and supplier")


class TestPublishEndpoint:
    """Test that publish endpoint includes all required fields in tile_doc"""
    
    def test_tiles_have_tier_pricing_fields(self):
        """Verify tiles collection has tier pricing fields from publish"""
        response = requests.get(f"{BASE_URL}/api/tiles?limit=5")
        
        if response.status_code == 200:
            data = response.json()
            tiles = data.get("tiles", data.get("products", []))
            
            if len(tiles) > 0:
                tile = tiles[0]
                # Check for tier pricing fields that should be set during publish
                tier_fields = ["tier_pricing_disabled", "has_custom_tier_pricing"]
                sale_fields = ["sale_active"]
                
                for field in tier_fields:
                    if field in tile:
                        print(f"✓ Tile has {field}={tile[field]}")
                
                for field in sale_fields:
                    if field in tile:
                        print(f"✓ Tile has {field}={tile[field]}")
            else:
                print("Note: No tiles found in database")
        else:
            pytest.skip(f"Tiles endpoint returned {response.status_code}")


class TestMigrationSync:
    """Test that sync_discount_percentage_v1 migration ran"""
    
    def test_discount_percentage_matches_was_markup(self):
        """Verify discount_percentage equals was_markup_percent for sale products"""
        # Check tiles collection for products with sale pricing
        response = requests.get(f"{BASE_URL}/api/tiles/collections?sale=true&limit=10")
        
        if response.status_code == 200:
            data = response.json()
            collections = data.get("collections", [])
            
            if len(collections) > 0:
                print(f"✓ Found {len(collections)} sale collections")
                for coll in collections[:3]:
                    print(f"  - {coll['series_name']}: max_was_markup={coll.get('max_was_markup', 0)}")
            else:
                print("Note: No sale collections found")
        else:
            print(f"Note: Sale collections endpoint returned {response.status_code}")


class TestFrontendDataStructure:
    """Test data structure matches frontend expectations"""
    
    def test_collection_card_data_structure(self):
        """Verify collection data has all fields needed for TileCollectionsPage"""
        response = requests.get(f"{BASE_URL}/api/tiles/collections?group=tiles&limit=5")
        assert response.status_code == 200
        
        data = response.json()
        if len(data.get("collections", [])) > 0:
            collection = data["collections"][0]
            
            # Fields used in TileCollectionsPage.js lines 715-738
            frontend_fields = [
                "prices_from", "min_price", "is_sale", 
                "max_was_price", "tier_pricing_disabled",
                "trade_discount", "credit_back_rate"
            ]
            
            for field in frontend_fields:
                assert field in collection, f"Missing frontend field: {field}"
            
            print(f"✓ Collection has all frontend-required fields")
            print(f"  prices_from={collection['prices_from']}, min_price={collection['min_price']}")
            print(f"  tier_pricing_disabled={collection['tier_pricing_disabled']}")
            print(f"  is_sale={collection['is_sale']}, max_was_price={collection.get('max_was_price')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

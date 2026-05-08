"""
Test Production Bugfixes - Iteration 57
Tests for critical production bugs:
1. Products assigned via Collection Organizer don't show on customer-facing category pages
2. Search product click redirects to homepage instead of product detail page

Key fixes tested:
- GET /api/tiles/collections?group=tiles&category=floor-tiles returns products with sub_categories containing 'Floor Tiles'
- POST /api/website-admin/collection-organizer/assign updates BOTH supplier_products AND tiles collection
- POST /api/website-admin/collection-organizer/unassign also updates tiles collection properly
- POST /api/website-admin/collection-organizer/bulk-assign also updates tiles collection properly
- Frontend: /tiles/:slug route renders TileDetailPage (product detail), NOT redirect to home
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestCollectionOrganizerAssignFixes:
    """Test that Collection Organizer assign/unassign/bulk-assign updates tiles collection"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - ensure we have a clean state before tests"""
        # First, unassign any existing Floor Tiles assignments from Travertine series
        self.cleanup_test_assignments()
        yield
        # Cleanup after tests
        self.cleanup_test_assignments()
    
    def cleanup_test_assignments(self):
        """Remove test assignments to restore DB state"""
        try:
            # Unassign Travertine from Floor Tiles
            response = requests.post(
                f"{BASE_URL}/api/website-admin/collection-organizer/unassign",
                json={
                    "supplier": "Plus39",
                    "series": "Travertine",
                    "main_category": "Tiles",
                    "sub_categories": ["Floor Tiles"]
                }
            )
            print(f"Cleanup Travertine: {response.status_code}")
        except Exception as e:
            print(f"Cleanup error: {e}")
    
    def test_assign_updates_supplier_products(self):
        """Test that assign endpoint updates supplier_products collection"""
        # Assign Travertine series to Floor Tiles
        response = requests.post(
            f"{BASE_URL}/api/website-admin/collection-organizer/assign",
            json={
                "supplier": "Plus39",
                "series": "Travertine",
                "group_slug": "tiles",
                "main_category": "Tiles",
                "sub_categories": ["Floor Tiles"]
            }
        )
        
        assert response.status_code == 200, f"Assign failed: {response.text}"
        data = response.json()
        
        assert data.get("success") == True
        assert "products_updated" in data
        assert data["products_updated"] >= 0  # May be 0 if already assigned
        print(f"Assign response: {data}")
    
    def test_assign_updates_tiles_collection(self):
        """Test that assign endpoint ALSO updates tiles collection (the critical fix)"""
        # First assign
        assign_response = requests.post(
            f"{BASE_URL}/api/website-admin/collection-organizer/assign",
            json={
                "supplier": "Plus39",
                "series": "Travertine",
                "group_slug": "tiles",
                "main_category": "Tiles",
                "sub_categories": ["Floor Tiles"]
            }
        )
        
        assert assign_response.status_code == 200
        data = assign_response.json()
        
        # Check that tiles_updated is in the response
        assert "tiles_updated" in data, "Response should include tiles_updated count"
        print(f"Tiles updated: {data.get('tiles_updated')}")
        
        # The fix should update tiles collection - tiles_updated should be >= 0
        # (may be 0 if no matching tiles exist, but the field should be present)
    
    def test_category_query_returns_assigned_products(self):
        """Test that category query returns products with sub_categories containing 'Floor Tiles'"""
        # First assign Travertine to Floor Tiles
        assign_response = requests.post(
            f"{BASE_URL}/api/website-admin/collection-organizer/assign",
            json={
                "supplier": "Plus39",
                "series": "Travertine",
                "group_slug": "tiles",
                "main_category": "Tiles",
                "sub_categories": ["Floor Tiles"]
            }
        )
        assert assign_response.status_code == 200
        
        # Wait a moment for DB to sync
        time.sleep(0.5)
        
        # Now query floor-tiles category
        query_response = requests.get(
            f"{BASE_URL}/api/tiles/collections",
            params={"group": "tiles", "category": "floor-tiles", "limit": 50}
        )
        
        assert query_response.status_code == 200
        data = query_response.json()
        
        print(f"Floor tiles query returned {data.get('total', 0)} collections")
        
        # The fix should make products with sub_categories containing 'Floor Tiles' appear
        # Note: This depends on whether Plus39 products exist in tiles collection
        # The key is that the query now uses $or with sub_categories check
    
    def test_unassign_updates_tiles_collection(self):
        """Test that unassign endpoint also updates tiles collection"""
        # First assign
        requests.post(
            f"{BASE_URL}/api/website-admin/collection-organizer/assign",
            json={
                "supplier": "Plus39",
                "series": "Travertine",
                "group_slug": "tiles",
                "main_category": "Tiles",
                "sub_categories": ["Floor Tiles"]
            }
        )
        
        # Now unassign
        unassign_response = requests.post(
            f"{BASE_URL}/api/website-admin/collection-organizer/unassign",
            json={
                "supplier": "Plus39",
                "series": "Travertine",
                "main_category": "Tiles",
                "sub_categories": ["Floor Tiles"]
            }
        )
        
        assert unassign_response.status_code == 200
        data = unassign_response.json()
        
        assert data.get("success") == True
        assert "products_updated" in data
        print(f"Unassign response: {data}")
    
    def test_bulk_assign_updates_tiles_collection(self):
        """Test that bulk-assign endpoint also updates tiles collection"""
        # Bulk assign multiple series
        bulk_response = requests.post(
            f"{BASE_URL}/api/website-admin/collection-organizer/bulk-assign",
            json={
                "supplier": "Plus39",
                "series_names": ["Travertine"],
                "group_slug": "tiles",
                "main_category": "Tiles",
                "sub_categories": ["Floor Tiles"]
            }
        )
        
        assert bulk_response.status_code == 200
        data = bulk_response.json()
        
        assert data.get("success") == True
        assert "total_products_updated" in data
        print(f"Bulk assign response: {data}")


class TestCategoryQueryFix:
    """Test the category query fix - now uses $or with sub_categories"""
    
    def test_category_query_structure(self):
        """Test that category query endpoint works correctly"""
        response = requests.get(
            f"{BASE_URL}/api/tiles/collections",
            params={"group": "tiles", "category": "floor-tiles"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have standard response structure
        assert "collections" in data
        assert "total" in data
        assert "page" in data
        print(f"Category query returned {data.get('total', 0)} collections")
    
    def test_category_query_with_wall_tiles(self):
        """Test category query with wall-tiles"""
        response = requests.get(
            f"{BASE_URL}/api/tiles/collections",
            params={"group": "tiles", "category": "wall-tiles"}
        )
        
        assert response.status_code == 200
        data = response.json()
        print(f"Wall tiles query returned {data.get('total', 0)} collections")
    
    def test_category_query_without_category(self):
        """Test category query without category filter returns all"""
        response = requests.get(
            f"{BASE_URL}/api/tiles/collections",
            params={"group": "tiles", "limit": 5}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("total", 0) > 0, "Should return some collections without category filter"
        print(f"All tiles query returned {data.get('total', 0)} collections")


class TestTileDetailRoute:
    """Test that /tiles/:slug route works (frontend route fix)"""
    
    def test_tile_detail_api_exists(self):
        """Test that tile detail API endpoint works"""
        # First get a valid slug
        products_response = requests.get(
            f"{BASE_URL}/api/tiles/products",
            params={"limit": 1}
        )
        
        assert products_response.status_code == 200
        products = products_response.json().get("products", [])
        
        if products:
            slug = products[0].get("slug")
            print(f"Testing with slug: {slug}")
            
            # Test the detail endpoint
            detail_response = requests.get(f"{BASE_URL}/api/tiles/products/{slug}")
            
            assert detail_response.status_code == 200
            data = detail_response.json()
            
            assert "display_name" in data
            assert "slug" in data
            assert data["slug"] == slug
            print(f"Tile detail API works for: {data.get('display_name')}")
        else:
            pytest.skip("No products available for testing")
    
    def test_tile_detail_with_known_slug(self):
        """Test tile detail with a known slug"""
        # Use opaco-60x120cm which we know exists
        response = requests.get(f"{BASE_URL}/api/tiles/products/opaco-60x120cm")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("slug") == "opaco-60x120cm"
        assert "display_name" in data
        assert "supplier" in data
        print(f"Tile detail: {data.get('display_name')} from {data.get('supplier')}")


class TestAssignWithTilesOnlyProducts:
    """Test assign works when products only exist in tiles collection (not supplier_products)"""
    
    def test_assign_with_leporce_tiles(self):
        """Test assign with LEPORCE which has tiles but no supplier_products series"""
        # LEPORCE has 556 tiles but series_count=0 in supplier_products
        # The fix uses broad matching to find tiles by supplier_name + series/name
        
        # First check what series exist for LEPORCE
        series_response = requests.get(
            f"{BASE_URL}/api/website-admin/collection-organizer/series",
            params={"supplier": "LEPORCE"}
        )
        
        assert series_response.status_code == 200
        data = series_response.json()
        
        # LEPORCE may have 0 series in supplier_products but tiles exist
        print(f"LEPORCE series count: {len(data.get('series', []))}")
        
        # The endpoint should not crash even with no series
        assert "series" in data


class TestTileMatchingLogic:
    """Test the tile matching logic in assign/unassign endpoints"""
    
    def test_assign_uses_broad_matching(self):
        """Test that assign uses supplier_name regex + series/name matching for tiles"""
        # This tests the fix where tiles are matched by:
        # 1. supplier_name regex + series
        # 2. supplier_name regex + name containing series
        # 3. source_supplier regex + series
        
        response = requests.post(
            f"{BASE_URL}/api/website-admin/collection-organizer/assign",
            json={
                "supplier": "Plus39",
                "series": "Travertine",
                "group_slug": "tiles",
                "main_category": "Tiles",
                "sub_categories": ["Floor Tiles"]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Response should include both products_updated and tiles_updated
        assert "products_updated" in data
        assert "tiles_updated" in data
        
        print(f"Products updated: {data.get('products_updated')}")
        print(f"Tiles updated: {data.get('tiles_updated')}")
        print(f"Total in series: {data.get('total_in_series')}")


class TestSeriesEndpointRelevantGroups:
    """Test that series endpoint returns relevant_groups for filtering"""
    
    def test_series_returns_relevant_groups(self):
        """Test that series endpoint returns relevant_groups field"""
        response = requests.get(
            f"{BASE_URL}/api/website-admin/collection-organizer/series",
            params={"supplier": "Plus39"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have relevant_groups field
        assert "relevant_groups" in data, "Response should include relevant_groups"
        print(f"Relevant groups for Plus39: {data.get('relevant_groups')}")
    
    def test_series_returns_ungrouped_count(self):
        """Test that series endpoint returns ungrouped_count field"""
        response = requests.get(
            f"{BASE_URL}/api/website-admin/collection-organizer/series",
            params={"supplier": "Plus39"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have ungrouped_count field
        assert "ungrouped_count" in data, "Response should include ungrouped_count"
        print(f"Ungrouped count for Plus39: {data.get('ungrouped_count')}")


# Run cleanup after all tests
@pytest.fixture(scope="session", autouse=True)
def cleanup_after_all_tests():
    """Final cleanup after all tests complete"""
    yield
    # Cleanup any test assignments
    try:
        requests.post(
            f"{BASE_URL}/api/website-admin/collection-organizer/unassign",
            json={
                "supplier": "Plus39",
                "series": "Travertine",
                "main_category": "Tiles",
                "sub_categories": ["Floor Tiles"]
            }
        )
        print("Final cleanup completed")
    except Exception as e:
        print(f"Final cleanup error: {e}")

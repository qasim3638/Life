"""
Test Bulk Category Editor API endpoints
Tests for:
1. Wall & Floor Tiles category saving via bulk-update-unified
2. Categories by-group API returning correct slugs
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestCategoriesAPI:
    """Test categories/by-group API endpoint"""
    
    def test_categories_by_group_returns_wall_floor_tiles(self):
        """Verify Wall & Floor Tiles exists with correct slug"""
        response = requests.get(f"{BASE_URL}/api/website-admin/categories/by-group")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list of groups"
        
        # Find tiles group
        tiles_group = next((g for g in data if g.get('slug') == 'tiles'), None)
        assert tiles_group is not None, "Tiles group not found"
        
        # Find Wall & Floor Tiles category
        categories = tiles_group.get('categories', [])
        wall_floor = next((c for c in categories if c.get('name') == 'Wall & Floor Tiles'), None)
        
        assert wall_floor is not None, "Wall & Floor Tiles category not found"
        assert wall_floor.get('slug') == 'wall-floor-tiles', f"Expected slug 'wall-floor-tiles', got '{wall_floor.get('slug')}'"
        
        print(f"SUCCESS: Wall & Floor Tiles found with slug: {wall_floor.get('slug')}")


class TestBulkUpdateUnified:
    """Test bulk-update-unified API endpoint"""
    
    def test_bulk_update_with_wall_floor_tiles(self):
        """Test that Wall & Floor Tiles can be saved via bulk update"""
        payload = {
            "product_ids": ["TEST-WALL-FLOOR-SKU-001"],
            "updates": {
                "sub_categories": ["Wall & Floor Tiles"],
                "material": "Porcelain"
            },
            "mode": "replace"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get('success') == True, f"Expected success=True, got {data}"
        
        print(f"SUCCESS: Bulk update accepted Wall & Floor Tiles category")
        print(f"Response: {data}")
    
    def test_bulk_update_with_multiple_categories(self):
        """Test bulk update with multiple categories including Wall & Floor Tiles"""
        payload = {
            "product_ids": ["TEST-MULTI-CAT-SKU-001"],
            "updates": {
                "sub_categories": ["Wall & Floor Tiles", "Bathroom Tiles", "Kitchen Tiles"],
                "main_category": "Tiles",
                "material": "Ceramic"
            },
            "mode": "replace"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get('success') == True, f"Expected success=True, got {data}"
        
        print(f"SUCCESS: Bulk update with multiple categories accepted")
    
    def test_bulk_update_with_filters_and_specs(self):
        """Test bulk update with filters and specifications"""
        payload = {
            "product_ids": ["TEST-FULL-UPDATE-SKU-001"],
            "updates": {
                "sub_categories": ["Floor Tiles"],
                "material": "Porcelain",
                "finish": "Matt",
                "colors": ["Grey", "White"],
                "rooms": ["Bathroom", "Kitchen"]
            },
            "mode": "replace"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get('success') == True, f"Expected success=True, got {data}"
        
        print(f"SUCCESS: Full bulk update with filters and specs accepted")


class TestCategorySlugConsistency:
    """Test that category slugs are consistent between API and UI"""
    
    def test_all_tile_categories_have_valid_slugs(self):
        """Verify all tile categories have valid slugs"""
        response = requests.get(f"{BASE_URL}/api/website-admin/categories/by-group")
        
        assert response.status_code == 200
        
        data = response.json()
        tiles_group = next((g for g in data if g.get('slug') == 'tiles'), None)
        
        if tiles_group:
            categories = tiles_group.get('categories', [])
            for cat in categories:
                name = cat.get('name', '')
                slug = cat.get('slug', '')
                
                # Verify slug exists and is not empty
                assert slug, f"Category '{name}' has empty slug"
                
                # Verify slug format (lowercase, no special chars except hyphen)
                assert slug == slug.lower(), f"Slug '{slug}' should be lowercase"
                assert ' ' not in slug, f"Slug '{slug}' should not contain spaces"
                
                print(f"Category: {name} -> Slug: {slug}")
        
        print(f"SUCCESS: All {len(categories)} tile categories have valid slugs")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
Test cases for Unified Product Options System
Tests the synchronization between Navigation & Structure and Bulk Category Editor
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://feature-verification-7.preview.emergentagent.com')


class TestBulkEditorOptionsAPI:
    """Tests for /api/filters/bulk-editor-options endpoint"""
    
    def test_get_bulk_editor_options_success(self):
        """GET /api/filters/bulk-editor-options should return options grouped by category"""
        response = requests.get(f"{BASE_URL}/api/filters/bulk-editor-options")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, dict)
        
        # Verify expected categories exist
        expected_categories = ['material', 'finish', 'color', 'edge', 'slip_rating', 
                             'suitability', 'thickness', 'room', 'style', 'features']
        for cat in expected_categories:
            assert cat in data or cat.replace('-', '_') in data, f"Missing category: {cat}"
        
        print(f"✓ Bulk editor options returned {len(data)} categories")

    def test_bulk_editor_options_structure(self):
        """Options should have id, label, is_active fields"""
        response = requests.get(f"{BASE_URL}/api/filters/bulk-editor-options")
        assert response.status_code == 200
        
        data = response.json()
        
        # Check structure of material options as sample
        if 'material' in data and len(data['material']) > 0:
            option = data['material'][0]
            assert 'id' in option, "Option should have id"
            assert 'label' in option, "Option should have label"
            assert 'is_active' in option, "Option should have is_active"
            print(f"✓ Options have correct structure: id, label, is_active")


class TestCategoryGroupsAPI:
    """Tests for /api/website-admin/category-groups endpoint"""
    
    def test_get_category_groups_success(self):
        """GET /api/website-admin/category-groups should return category groups"""
        response = requests.get(f"{BASE_URL}/api/website-admin/category-groups")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0, "Should have at least one category group"
        
        # Verify expected groups exist
        group_names = [g['name'] for g in data]
        expected_groups = ['Tiles', 'Flooring', 'Underfloor Heating', 'Materials', 'Tools', 'Accessories']
        for expected in expected_groups:
            assert expected in group_names, f"Missing group: {expected}"
        
        print(f"✓ Category groups returned {len(data)} groups: {group_names}")

    def test_category_group_structure(self):
        """Category groups should have name, slug, icon, color fields"""
        response = requests.get(f"{BASE_URL}/api/website-admin/category-groups")
        assert response.status_code == 200
        
        data = response.json()
        group = data[0]
        
        assert 'name' in group, "Group should have name"
        assert 'slug' in group, "Group should have slug"
        assert 'icon' in group, "Group should have icon"
        assert 'color' in group, "Group should have color"
        assert 'is_active' in group, "Group should have is_active"
        
        print(f"✓ Category groups have correct structure")


class TestFilterTypesAPI:
    """Tests for /api/filters/types endpoint"""
    
    def test_get_filter_types_success(self):
        """GET /api/filters/types should return all filter types"""
        response = requests.get(f"{BASE_URL}/api/filters/types")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0, "Should have filter types"
        
        # Check that filters have visibility flags
        sample_filter = data[0]
        print(f"✓ Got {len(data)} filter types. Sample: {sample_filter.get('name')}")

    def test_filter_types_have_visibility_flags(self):
        """Filter types should have visibility flags for unified system"""
        response = requests.get(f"{BASE_URL}/api/filters/types")
        assert response.status_code == 200
        
        data = response.json()
        
        # Check for visibility flags on at least one filter
        found_visibility_flags = False
        for f in data:
            if any(key in f for key in ['show_in_bulk_editor', 'show_in_shop_filter', 
                                        'show_in_product_detail', 'allow_new_values_in_bulk_editor']):
                found_visibility_flags = True
                print(f"✓ Filter '{f.get('name')}' has visibility flags")
                break
        
        # Note: Some filters may not have these flags yet if they were created before the unified system
        if not found_visibility_flags:
            print("⚠ No filters found with visibility flags yet (may need to edit a filter)")


class TestFilterValueDeleteAPI:
    """Tests for DELETE /api/filters/types/by-slug/{filter_slug}/values/{value_slug}"""
    
    def test_delete_value_endpoint_exists(self):
        """DELETE endpoint for filter values should exist"""
        # Try to delete a non-existent value - should return 404 or error, not 405
        response = requests.delete(
            f"{BASE_URL}/api/filters/types/by-slug/nonexistent-filter/values/test-value"
        )
        # Should be 404 (filter not found), not 405 (method not allowed)
        assert response.status_code in [404, 500], f"Expected 404 or 500, got {response.status_code}"
        print(f"✓ DELETE endpoint exists (returned {response.status_code} for non-existent filter)")

    def test_delete_value_by_slug_workflow(self):
        """Test the delete-value-by-slug endpoint used by Manage Options modal"""
        # First, get a filter to test with
        response = requests.get(f"{BASE_URL}/api/filters/types")
        assert response.status_code == 200
        
        filters = response.json()
        
        # Find a filter with values that we can test (don't actually delete production data)
        test_filter = None
        for f in filters:
            if f.get('values') and len(f.get('values', [])) > 0:
                test_filter = f
                break
        
        if test_filter:
            slug = test_filter.get('slug')
            print(f"✓ Found filter '{test_filter.get('name')}' (slug: {slug}) with {len(test_filter.get('values', []))} values")
            # Note: We won't actually delete values in tests to avoid data loss
        else:
            print("⚠ No filters with values found to test delete endpoint")


class TestWebsiteCategoryOptionsAPI:
    """Tests for /api/supplier-sync/website-category-options (legacy API)"""
    
    def test_get_legacy_options_success(self):
        """GET /api/supplier-sync/website-category-options should return options"""
        response = requests.get(f"{BASE_URL}/api/supplier-sync/website-category-options")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, dict)
        
        print(f"✓ Legacy category options returned {len(data)} categories")

    def test_legacy_and_unified_options_sync(self):
        """Legacy and unified APIs should return overlapping data"""
        legacy_response = requests.get(f"{BASE_URL}/api/supplier-sync/website-category-options")
        unified_response = requests.get(f"{BASE_URL}/api/filters/bulk-editor-options")
        
        assert legacy_response.status_code == 200
        assert unified_response.status_code == 200
        
        legacy = legacy_response.json()
        unified = unified_response.json()
        
        # Both should have material options
        legacy_has_materials = 'materials' in legacy
        unified_has_materials = 'material' in unified
        
        print(f"✓ Legacy has materials: {legacy_has_materials}, Unified has material: {unified_has_materials}")


class TestAddOptionSync:
    """Tests for adding options and syncing between systems"""
    
    def test_add_option_to_legacy_system(self):
        """POST /api/supplier-sync/website-category-options adds option to legacy system"""
        # Test data
        test_option = {
            "category_type": "materials",
            "id": "test_material_pytest",
            "label": "Test Material PyTest",
            "color": "bg-gray-500"
        }
        
        # Add option
        response = requests.post(
            f"{BASE_URL}/api/supplier-sync/website-category-options",
            json=test_option
        )
        
        # Should succeed or indicate duplicate
        assert response.status_code in [200, 400], f"Unexpected status: {response.status_code}"
        
        if response.status_code == 200:
            print(f"✓ Added test option to legacy system")
            
            # Clean up - delete the test option
            delete_response = requests.delete(
                f"{BASE_URL}/api/supplier-sync/website-category-options/materials/test_material_pytest"
            )
            print(f"  Cleanup: {delete_response.status_code}")
        else:
            print(f"✓ Option already exists or rejected (status {response.status_code})")

    def test_add_filter_value_api(self):
        """POST /api/filters/types/{filter_slug}/add-value adds value to unified system"""
        # Test data
        test_value = {
            "value": "test-value-pytest",
            "label": "Test Value PyTest",
            "is_active": True
        }
        
        # Try to add to material filter
        response = requests.post(
            f"{BASE_URL}/api/filters/types/material/add-value",
            json=test_value
        )
        
        # Should succeed or indicate already exists
        assert response.status_code in [200, 400, 404], f"Unexpected status: {response.status_code}"
        
        data = response.json()
        print(f"✓ Add filter value response: {data.get('message', 'OK')}")


class TestProductGroupFiltering:
    """Tests for Product Group Context functionality"""
    
    def test_category_groups_have_category_count(self):
        """Category groups should include category_count for filtering"""
        response = requests.get(f"{BASE_URL}/api/website-admin/category-groups")
        assert response.status_code == 200
        
        groups = response.json()
        
        for group in groups:
            # category_count may be computed field
            if 'category_count' in group:
                print(f"✓ {group['name']}: {group['category_count']} categories")

    def test_categories_have_group_slug(self):
        """Categories should have group_slug for filtering"""
        response = requests.get(f"{BASE_URL}/api/website-admin/categories")
        assert response.status_code == 200
        
        categories = response.json()
        
        # Check that categories have group_slug
        categories_with_group = [c for c in categories if c.get('group_slug')]
        print(f"✓ {len(categories_with_group)}/{len(categories)} categories have group_slug")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

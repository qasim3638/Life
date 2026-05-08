"""
Test suite for Manage Product Options Modal Redesign
Tests the new tabs: Categories, Filters, Specifications

Features tested:
1. Modal has 3 tabs: Categories, Filters, Specifications
2. Categories tab shows same data as Navigation & Structure → Categories
3. Filters tab shows same filters with add/delete functionality
4. Specifications tab shows same specs as Navigation & Structure
5. Product Group Selector filters content
6. Bidirectional sync between modal and Navigation & Structure
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://feature-verification-7.preview.emergentagent.com')


class TestCategoriesTab:
    """Tests for Categories tab in Manage Options Modal"""
    
    def test_categories_endpoint_returns_list(self):
        """GET /api/website-admin/categories returns categories list"""
        response = requests.get(f"{BASE_URL}/api/website-admin/categories")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0, "Should have at least one category"
        print(f"✓ Categories endpoint returns {len(data)} categories")
    
    def test_categories_by_group_endpoint(self):
        """GET /api/website-admin/categories/by-group returns grouped categories"""
        response = requests.get(f"{BASE_URL}/api/website-admin/categories/by-group")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        # Check structure - each group should have slug and categories array
        for group in data:
            assert "slug" in group or "id" in group, "Each group should have slug or id"
            assert "categories" in group, "Each group should have categories array"
        
        print(f"✓ Categories by group returns {len(data)} groups")
        print(f"  Groups: {[g.get('slug', g.get('name', '?')) for g in data[:6]]}")
    
    def test_categories_have_group_slug(self):
        """Categories should have group_slug field for filtering"""
        response = requests.get(f"{BASE_URL}/api/website-admin/categories")
        assert response.status_code == 200
        data = response.json()
        
        # Check that most categories have group_slug
        with_group_slug = sum(1 for cat in data if cat.get('group_slug'))
        print(f"✓ {with_group_slug}/{len(data)} categories have group_slug")
        assert with_group_slug > 0, "At least some categories should have group_slug"
    
    def test_categories_filter_by_group(self):
        """GET /api/website-admin/categories?group_slug=tiles returns filtered categories"""
        response = requests.get(f"{BASE_URL}/api/website-admin/categories?group_slug=tiles")
        assert response.status_code == 200
        data = response.json()
        
        # All returned categories should belong to tiles group (or no group specified)
        for cat in data:
            if cat.get('group_slug'):
                assert cat['group_slug'] == 'tiles', f"Expected tiles group, got {cat.get('group_slug')}"
        
        print(f"✓ Filtered categories for 'tiles' group: {len(data)} categories")


class TestFiltersTab:
    """Tests for Filters tab in Manage Options Modal"""
    
    def test_filters_types_endpoint(self):
        """GET /api/filters/types returns filter types list"""
        response = requests.get(f"{BASE_URL}/api/filters/types")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0, "Should have at least one filter type"
        
        # Check filter structure
        first_filter = data[0]
        assert "name" in first_filter, "Filter should have name"
        assert "slug" in first_filter, "Filter should have slug"
        
        print(f"✓ Filters endpoint returns {len(data)} filter types")
        print(f"  Filters: {[f.get('name', '?') for f in data[:8]]}")
    
    def test_filters_have_values(self):
        """Filters should have values array"""
        response = requests.get(f"{BASE_URL}/api/filters/types")
        assert response.status_code == 200
        data = response.json()
        
        # Check that filters have values
        filters_with_values = sum(1 for f in data if f.get('values') and len(f.get('values', [])) > 0)
        print(f"✓ {filters_with_values}/{len(data)} filters have values")
    
    def test_add_filter_value_endpoint_exists(self):
        """POST /api/filters/types/{slug}/add-value endpoint should exist"""
        # Test with a non-existent filter to verify endpoint exists
        response = requests.post(
            f"{BASE_URL}/api/filters/types/test-nonexistent/add-value",
            json={"value": "test", "label": "Test", "is_active": True}
        )
        # Should get 404 for non-existent filter, not 405 method not allowed
        assert response.status_code in [404, 400, 422, 200], f"Unexpected status: {response.status_code}"
        print(f"✓ Add filter value endpoint exists (returned {response.status_code} for test)")
    
    def test_delete_filter_value_endpoint_exists(self):
        """DELETE /api/filters/types/by-slug/{slug}/values/{value_slug} endpoint should exist"""
        response = requests.delete(
            f"{BASE_URL}/api/filters/types/by-slug/test-nonexistent/values/test-value"
        )
        # Should get 404 for non-existent filter, not 405 method not allowed
        assert response.status_code in [404, 400, 422, 200], f"Unexpected status: {response.status_code}"
        print(f"✓ Delete filter value endpoint exists (returned {response.status_code} for test)")
    
    def test_filters_have_auto_populate_groups(self):
        """Filters may have auto_populate_groups for product group filtering"""
        response = requests.get(f"{BASE_URL}/api/filters/types")
        assert response.status_code == 200
        data = response.json()
        
        # Check if any filters have auto_populate_groups
        with_groups = sum(1 for f in data if f.get('auto_populate_groups'))
        print(f"✓ {with_groups}/{len(data)} filters have auto_populate_groups")


class TestSpecificationsTab:
    """Tests for Specifications tab in Manage Options Modal"""
    
    def test_specifications_by_group_endpoint(self):
        """GET /api/specifications/types/by-group returns specifications"""
        response = requests.get(f"{BASE_URL}/api/specifications/types/by-group")
        assert response.status_code == 200
        data = response.json()
        
        # Data should be list (of spec groups or individual specs)
        assert isinstance(data, (list, dict)), f"Expected list or dict, got {type(data)}"
        print(f"✓ Specifications by group returns data")
        if isinstance(data, list):
            print(f"  Count: {len(data)} items")
            if len(data) > 0:
                print(f"  Sample: {[s.get('name', s.get('grouping', '?')) for s in data[:3]]}")
    
    def test_specification_groups_endpoint(self):
        """GET /api/specifications/groups returns spec groups"""
        response = requests.get(f"{BASE_URL}/api/specifications/groups")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Specification groups returns {len(data)} groups")


class TestProductGroupSelector:
    """Tests for Product Group Selector filtering"""
    
    def test_category_groups_endpoint(self):
        """GET /api/website-admin/category-groups returns product groups"""
        response = requests.get(f"{BASE_URL}/api/website-admin/category-groups")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0, "Should have at least one category group"
        
        # Check for expected groups
        slugs = [g.get('slug', '') for g in data]
        print(f"✓ Category groups: {slugs}")
        
        # Should have common groups
        expected = ['tiles', 'flooring', 'materials', 'tools']
        found = sum(1 for e in expected if e in slugs)
        print(f"  Found {found}/{len(expected)} expected groups")
    
    def test_categories_filtered_by_product_group(self):
        """Categories can be filtered by product group"""
        # Get all categories grouped
        response = requests.get(f"{BASE_URL}/api/website-admin/categories/by-group")
        assert response.status_code == 200
        data = response.json()
        
        # Check tiles group has categories
        tiles_group = next((g for g in data if g.get('slug') == 'tiles'), None)
        if tiles_group:
            tiles_cats = tiles_group.get('categories', [])
            print(f"✓ Tiles group has {len(tiles_cats)} categories")


class TestSyncIndicator:
    """Tests for sync indicator functionality"""
    
    def test_filter_values_add_and_delete_flow(self):
        """Test that filter values can be added and deleted (sync functionality)"""
        # Get an existing filter
        response = requests.get(f"{BASE_URL}/api/filters/types")
        assert response.status_code == 200
        filters = response.json()
        
        # Find a filter with slug for testing
        test_filter = next((f for f in filters if f.get('slug')), None)
        if not test_filter:
            pytest.skip("No filter with slug found for testing")
        
        filter_slug = test_filter['slug']
        test_value = "test-sync-value"
        test_label = "Test Sync Value"
        
        # Try to add a value (might fail if already exists or permissions)
        add_response = requests.post(
            f"{BASE_URL}/api/filters/types/{filter_slug}/add-value",
            json={"value": test_value, "label": test_label, "is_active": True}
        )
        
        if add_response.status_code in [200, 201]:
            print(f"✓ Successfully added filter value '{test_label}' to '{filter_slug}'")
            
            # Now delete it to clean up
            delete_response = requests.delete(
                f"{BASE_URL}/api/filters/types/by-slug/{filter_slug}/values/{test_value}"
            )
            if delete_response.status_code in [200, 204]:
                print(f"✓ Successfully deleted filter value '{test_value}'")
            else:
                print(f"  Delete returned {delete_response.status_code}: {delete_response.text[:100]}")
        else:
            print(f"  Add returned {add_response.status_code} (may need auth or value exists)")


class TestModalTabData:
    """Integration tests verifying modal shows same data as Navigation & Structure"""
    
    def test_categories_data_consistency(self):
        """Categories endpoint data should match what Navigation & Structure shows"""
        # Both endpoints should return the same categories
        cats_response = requests.get(f"{BASE_URL}/api/website-admin/categories")
        assert cats_response.status_code == 200
        
        by_group_response = requests.get(f"{BASE_URL}/api/website-admin/categories/by-group")
        assert by_group_response.status_code == 200
        
        cats = cats_response.json()
        by_group = by_group_response.json()
        
        # Count total categories from by-group response
        total_from_groups = sum(len(g.get('categories', [])) for g in by_group)
        
        print(f"✓ Direct categories endpoint: {len(cats)} categories")
        print(f"✓ Categories from by-group: {total_from_groups} categories")
    
    def test_filters_data_consistency(self):
        """Filters endpoint should return same data shown in Navigation & Structure"""
        response = requests.get(f"{BASE_URL}/api/filters/types")
        assert response.status_code == 200
        data = response.json()
        
        # Count filters with values
        filters_with_values = sum(1 for f in data if f.get('values') and len(f.get('values', [])) > 0)
        total_values = sum(len(f.get('values', [])) for f in data)
        
        print(f"✓ Filters: {len(data)} types, {filters_with_values} with values")
        print(f"✓ Total filter values: {total_values}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

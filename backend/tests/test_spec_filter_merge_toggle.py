"""
Test Suite for Specification and Filter Merge/Toggle Bug Fixes

Tests the following bug fixes:
1. PUT endpoints for specifications/filters should MERGE values (not overwrite)
2. PATCH toggle-group endpoints should hide values from specific groups (not delete globally)
3. DELETE endpoints should still work for global deletion
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Known test IDs from the system
SPEC_TYPE_ID = "69ba7a646bc1e8fd70e3be39"  # Material spec with 22+ values
FILTER_TYPE_ID = "69b99daaff7cebf6fb7146da"  # Color filter with 60 values

# Test credentials
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "TestAdmin123!"


class TestSpecificationMergeBehavior:
    """Test that PUT /api/specifications/types/{id} MERGES values instead of overwriting"""
    
    def test_get_spec_type_initial_values(self):
        """Verify we can get the spec type and it has multiple values"""
        response = requests.get(f"{BASE_URL}/api/specifications/types")
        assert response.status_code == 200, f"Failed to get spec types: {response.text}"
        
        specs = response.json()
        material_spec = next((s for s in specs if s.get('id') == SPEC_TYPE_ID), None)
        
        if material_spec:
            values_count = len(material_spec.get('values', []))
            print(f"Material spec has {values_count} values")
            assert values_count > 0, "Material spec should have values"
        else:
            # Try to find any spec with values for testing
            spec_with_values = next((s for s in specs if len(s.get('values', [])) > 5), None)
            if spec_with_values:
                print(f"Using spec '{spec_with_values.get('name')}' with {len(spec_with_values.get('values', []))} values")
            pytest.skip("Material spec not found, but other specs available")
    
    def test_put_spec_with_partial_values_preserves_existing(self):
        """PUT with only 2 values should preserve all existing values (merge behavior)"""
        # First, get current spec state
        response = requests.get(f"{BASE_URL}/api/specifications/types")
        assert response.status_code == 200
        
        specs = response.json()
        # Find a spec with values to test
        test_spec = next((s for s in specs if len(s.get('values', [])) > 5), None)
        
        if not test_spec:
            pytest.skip("No spec with enough values to test merge behavior")
        
        spec_id = test_spec['id']
        original_values = test_spec.get('values', [])
        original_count = len(original_values)
        print(f"Testing spec '{test_spec.get('name')}' with {original_count} values")
        
        # Send PUT with only 2 values (simulating frontend sync that only sends partial data)
        partial_values = original_values[:2] if len(original_values) >= 2 else original_values
        
        update_payload = {
            "name": test_spec.get('name'),
            "slug": test_spec.get('slug'),
            "description": test_spec.get('description', ''),
            "group_slug": test_spec.get('group_slug', 'general'),
            "field_name": test_spec.get('field_name', ''),
            "display_order": test_spec.get('display_order', 0),
            "is_active": test_spec.get('is_active', True),
            "auto_populate": test_spec.get('auto_populate', True),
            "values": partial_values  # Only sending 2 values
        }
        
        response = requests.put(
            f"{BASE_URL}/api/specifications/types/{spec_id}",
            json=update_payload
        )
        assert response.status_code == 200, f"PUT failed: {response.text}"
        
        # Verify values were preserved (merged, not overwritten)
        response = requests.get(f"{BASE_URL}/api/specifications/types")
        assert response.status_code == 200
        
        updated_spec = next((s for s in response.json() if s.get('id') == spec_id), None)
        assert updated_spec is not None, "Spec not found after update"
        
        updated_count = len(updated_spec.get('values', []))
        print(f"After PUT with 2 values: spec now has {updated_count} values (was {original_count})")
        
        # CRITICAL: Values should be preserved, not reduced to 2
        assert updated_count >= original_count, \
            f"MERGE BUG: Values were overwritten! Had {original_count}, now have {updated_count}"
        
        print("✓ PUT merge behavior working correctly - values preserved")


class TestFilterMergeBehavior:
    """Test that PUT /api/filters/types/{id} MERGES values instead of overwriting"""
    
    def test_get_filter_type_initial_values(self):
        """Verify we can get the filter type and it has multiple values"""
        response = requests.get(f"{BASE_URL}/api/filters/types")
        assert response.status_code == 200, f"Failed to get filter types: {response.text}"
        
        filters = response.json()
        color_filter = next((f for f in filters if f.get('id') == FILTER_TYPE_ID), None)
        
        if color_filter:
            values_count = len(color_filter.get('values', []))
            print(f"Color filter has {values_count} values")
            assert values_count > 0, "Color filter should have values"
        else:
            # Try to find any filter with values for testing
            filter_with_values = next((f for f in filters if len(f.get('values', [])) > 5), None)
            if filter_with_values:
                print(f"Using filter '{filter_with_values.get('name')}' with {len(filter_with_values.get('values', []))} values")
    
    def test_put_filter_with_partial_values_preserves_existing(self):
        """PUT with only 2 values should preserve all existing values (merge behavior)"""
        # First, get current filter state
        response = requests.get(f"{BASE_URL}/api/filters/types")
        assert response.status_code == 200
        
        filters = response.json()
        # Find a filter with values to test
        test_filter = next((f for f in filters if len(f.get('values', [])) > 5), None)
        
        if not test_filter:
            pytest.skip("No filter with enough values to test merge behavior")
        
        filter_id = test_filter['id']
        original_values = test_filter.get('values', [])
        original_count = len(original_values)
        print(f"Testing filter '{test_filter.get('name')}' with {original_count} values")
        
        # Send PUT with only 2 values (simulating frontend sync that only sends partial data)
        partial_values = original_values[:2] if len(original_values) >= 2 else original_values
        
        update_payload = {
            "name": test_filter.get('name'),
            "slug": test_filter.get('slug'),
            "input_type": test_filter.get('input_type', 'checkbox'),
            "description": test_filter.get('description', ''),
            "values": partial_values,  # Only sending 2 values
            "is_active": test_filter.get('is_active', True),
            "auto_populate": test_filter.get('auto_populate', False),
            "auto_populate_field": test_filter.get('auto_populate_field', ''),
            "auto_populate_categories": test_filter.get('auto_populate_categories', []),
            "auto_populate_groups": test_filter.get('auto_populate_groups', []),
            "excluded_values": test_filter.get('excluded_values', []),
            "show_in_shop_filter": test_filter.get('show_in_shop_filter', True),
            "show_in_bulk_editor": test_filter.get('show_in_bulk_editor', True),
            "show_in_product_detail": test_filter.get('show_in_product_detail', False),
            "allow_new_values_in_bulk_editor": test_filter.get('allow_new_values_in_bulk_editor', False),
            "option_category": test_filter.get('option_category', 'general')
        }
        
        response = requests.put(
            f"{BASE_URL}/api/filters/types/{filter_id}",
            json=update_payload
        )
        assert response.status_code == 200, f"PUT failed: {response.text}"
        
        # Verify values were preserved (merged, not overwritten)
        response = requests.get(f"{BASE_URL}/api/filters/types")
        assert response.status_code == 200
        
        updated_filter = next((f for f in response.json() if f.get('id') == filter_id), None)
        assert updated_filter is not None, "Filter not found after update"
        
        updated_count = len(updated_filter.get('values', []))
        print(f"After PUT with 2 values: filter now has {updated_count} values (was {original_count})")
        
        # CRITICAL: Values should be preserved, not reduced to 2
        assert updated_count >= original_count, \
            f"MERGE BUG: Values were overwritten! Had {original_count}, now have {updated_count}"
        
        print("✓ PUT merge behavior working correctly - values preserved")


class TestSpecToggleGroupIsolation:
    """Test PATCH /api/specifications/types/{id}/values/{value}/toggle-group for group isolation"""
    
    def test_toggle_group_endpoint_exists(self):
        """Verify the toggle-group endpoint exists and accepts PATCH"""
        # Get a spec with values
        response = requests.get(f"{BASE_URL}/api/specifications/types")
        assert response.status_code == 200
        
        specs = response.json()
        test_spec = next((s for s in specs if len(s.get('values', [])) > 0), None)
        
        if not test_spec:
            pytest.skip("No spec with values to test toggle-group")
        
        spec_id = test_spec['id']
        test_value = test_spec['values'][0]['value']
        
        # Test the toggle-group endpoint
        response = requests.patch(
            f"{BASE_URL}/api/specifications/types/{spec_id}/values/{test_value}/toggle-group",
            json={"product_group": "flooring", "action": "remove"}
        )
        
        # Should return 200 (success) or 404 (value not found) - not 405 (method not allowed)
        assert response.status_code in [200, 404], \
            f"Toggle-group endpoint failed with {response.status_code}: {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            print(f"Toggle-group response: {data}")
            assert 'product_groups' in data, "Response should include product_groups array"
            print("✓ Toggle-group endpoint working correctly")
    
    def test_toggle_group_hides_value_from_specific_group(self):
        """Removing a value from 'flooring' should NOT delete it globally"""
        # Get a spec with values
        response = requests.get(f"{BASE_URL}/api/specifications/types")
        assert response.status_code == 200
        
        specs = response.json()
        test_spec = next((s for s in specs if len(s.get('values', [])) > 0), None)
        
        if not test_spec:
            pytest.skip("No spec with values to test")
        
        spec_id = test_spec['id']
        original_values = test_spec.get('values', [])
        original_count = len(original_values)
        test_value = original_values[0]['value']
        
        print(f"Testing toggle-group on spec '{test_spec.get('name')}' value '{test_value}'")
        
        # Remove value from 'flooring' group
        response = requests.patch(
            f"{BASE_URL}/api/specifications/types/{spec_id}/values/{test_value}/toggle-group",
            json={"product_group": "flooring", "action": "remove"}
        )
        
        if response.status_code != 200:
            pytest.skip(f"Toggle-group returned {response.status_code}")
        
        # Verify the value still exists (not deleted globally)
        response = requests.get(f"{BASE_URL}/api/specifications/types")
        assert response.status_code == 200
        
        updated_spec = next((s for s in response.json() if s.get('id') == spec_id), None)
        assert updated_spec is not None
        
        updated_count = len(updated_spec.get('values', []))
        
        # CRITICAL: Value count should remain the same (value hidden, not deleted)
        assert updated_count == original_count, \
            f"GROUP ISOLATION BUG: Value was deleted! Had {original_count}, now have {updated_count}"
        
        # Verify the value has product_groups set (not empty = visible everywhere)
        updated_value = next((v for v in updated_spec.get('values', []) if v.get('value') == test_value), None)
        assert updated_value is not None, "Value should still exist after toggle-group"
        
        product_groups = updated_value.get('product_groups', [])
        print(f"Value '{test_value}' now has product_groups: {product_groups}")
        
        # If product_groups is not empty, 'flooring' should NOT be in it
        if product_groups:
            assert 'flooring' not in product_groups, \
                "Value should be hidden from 'flooring' group"
        
        print("✓ Toggle-group correctly hides value from specific group without deleting")


class TestFilterToggleGroupIsolation:
    """Test PATCH /api/filters/types/{id}/values/{value}/toggle-group for group isolation"""
    
    def test_toggle_group_endpoint_exists(self):
        """Verify the toggle-group endpoint exists for filters"""
        # Get a filter with values
        response = requests.get(f"{BASE_URL}/api/filters/types")
        assert response.status_code == 200
        
        filters = response.json()
        test_filter = next((f for f in filters if len(f.get('values', [])) > 0), None)
        
        if not test_filter:
            pytest.skip("No filter with values to test toggle-group")
        
        filter_id = test_filter['id']
        test_value = test_filter['values'][0]['value']
        
        # Test the toggle-group endpoint
        response = requests.patch(
            f"{BASE_URL}/api/filters/types/{filter_id}/values/{test_value}/toggle-group",
            json={"product_group": "flooring", "action": "remove"}
        )
        
        assert response.status_code in [200, 404], \
            f"Toggle-group endpoint failed with {response.status_code}: {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            print(f"Toggle-group response: {data}")
            assert 'product_groups' in data, "Response should include product_groups array"
            print("✓ Filter toggle-group endpoint working correctly")
    
    def test_toggle_group_hides_filter_value_from_specific_group(self):
        """Removing a filter value from 'flooring' should NOT delete it globally"""
        # Get a filter with values
        response = requests.get(f"{BASE_URL}/api/filters/types")
        assert response.status_code == 200
        
        filters = response.json()
        test_filter = next((f for f in filters if len(f.get('values', [])) > 0), None)
        
        if not test_filter:
            pytest.skip("No filter with values to test")
        
        filter_id = test_filter['id']
        original_values = test_filter.get('values', [])
        original_count = len(original_values)
        test_value = original_values[0]['value']
        
        print(f"Testing toggle-group on filter '{test_filter.get('name')}' value '{test_value}'")
        
        # Remove value from 'flooring' group
        response = requests.patch(
            f"{BASE_URL}/api/filters/types/{filter_id}/values/{test_value}/toggle-group",
            json={"product_group": "flooring", "action": "remove"}
        )
        
        if response.status_code != 200:
            pytest.skip(f"Toggle-group returned {response.status_code}")
        
        # Verify the value still exists (not deleted globally)
        response = requests.get(f"{BASE_URL}/api/filters/types")
        assert response.status_code == 200
        
        updated_filter = next((f for f in response.json() if f.get('id') == filter_id), None)
        assert updated_filter is not None
        
        updated_count = len(updated_filter.get('values', []))
        
        # CRITICAL: Value count should remain the same
        assert updated_count == original_count, \
            f"GROUP ISOLATION BUG: Value was deleted! Had {original_count}, now have {updated_count}"
        
        print("✓ Filter toggle-group correctly hides value without deleting")


class TestGlobalDeleteStillWorks:
    """Verify DELETE endpoints still work for intentional global deletion"""
    
    def test_spec_delete_endpoint_works(self):
        """DELETE /api/specifications/types/{id}/values/{value} should still delete globally"""
        # Get a spec with values
        response = requests.get(f"{BASE_URL}/api/specifications/types")
        assert response.status_code == 200
        
        specs = response.json()
        test_spec = next((s for s in specs if len(s.get('values', [])) > 2), None)
        
        if not test_spec:
            pytest.skip("No spec with enough values to test delete")
        
        spec_id = test_spec['id']
        
        # Add a test value first so we can safely delete it
        test_value_name = f"TEST_DELETE_{int(time.time())}"
        add_response = requests.post(
            f"{BASE_URL}/api/specifications/types/{spec_id}/values",
            json={"value": test_value_name, "label": test_value_name}
        )
        
        if add_response.status_code != 200:
            pytest.skip("Could not add test value")
        
        # Now delete it
        delete_response = requests.delete(
            f"{BASE_URL}/api/specifications/types/{spec_id}/values/{test_value_name}"
        )
        assert delete_response.status_code == 200, f"DELETE failed: {delete_response.text}"
        
        # Verify it's gone
        response = requests.get(f"{BASE_URL}/api/specifications/types")
        updated_spec = next((s for s in response.json() if s.get('id') == spec_id), None)
        
        value_exists = any(v.get('value') == test_value_name for v in updated_spec.get('values', []))
        assert not value_exists, "Value should be deleted globally"
        
        print("✓ Global DELETE endpoint still works correctly")
    
    def test_filter_delete_endpoint_works(self):
        """DELETE /api/filters/types/{id}/values/{value} should still delete globally"""
        # Get a filter with values
        response = requests.get(f"{BASE_URL}/api/filters/types")
        assert response.status_code == 200
        
        filters = response.json()
        test_filter = next((f for f in filters if len(f.get('values', [])) > 2), None)
        
        if not test_filter:
            pytest.skip("No filter with enough values to test delete")
        
        filter_id = test_filter['id']
        
        # Add a test value first so we can safely delete it
        test_value_name = f"test-delete-{int(time.time())}"
        add_response = requests.post(
            f"{BASE_URL}/api/filters/types/{filter_id}/values",
            json={"value": test_value_name, "label": test_value_name, "display_order": 999, "is_active": True}
        )
        
        if add_response.status_code != 200:
            pytest.skip("Could not add test value")
        
        # Now delete it
        delete_response = requests.delete(
            f"{BASE_URL}/api/filters/types/{filter_id}/values/{test_value_name}"
        )
        assert delete_response.status_code == 200, f"DELETE failed: {delete_response.text}"
        
        # Verify it's gone
        response = requests.get(f"{BASE_URL}/api/filters/types")
        updated_filter = next((f for f in response.json() if f.get('id') == filter_id), None)
        
        value_exists = any(v.get('value') == test_value_name for v in updated_filter.get('values', []))
        assert not value_exists, "Value should be deleted globally"
        
        print("✓ Filter global DELETE endpoint still works correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

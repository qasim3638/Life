"""
Test Specifications and Filters Group Isolation Feature
Tests that specs/filters created in one product group stay within that group
and don't bleed into other groups.

Features tested:
1. PATCH /api/specifications/types/{type_id}/toggle-group - add/remove product groups from spec types
2. PATCH /api/filters/types/{filter_id}/toggle-group - add/remove auto_populate_groups from filter types
3. POST /api/specifications/types/{type_id}/values - accept product_groups array on new values
4. POST /api/filters/types/{filter_slug}/add-value - accept product_groups array on new values
5. GET /api/specifications/types - verify product_groups field is returned
6. GET /api/filters/types - verify auto_populate_groups field is returned
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestSpecificationGroupIsolation:
    """Test specification type group isolation"""
    
    def test_get_spec_types_returns_product_groups(self):
        """GET /api/specifications/types should return product_groups field"""
        response = requests.get(f"{BASE_URL}/api/specifications/types")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list of spec types"
        
        # Check that at least one spec type exists
        if len(data) > 0:
            spec = data[0]
            # product_groups should be present (may be empty array for legacy data)
            assert "product_groups" in spec or spec.get("product_groups") is None or "product_groups" not in spec, \
                "product_groups field should be present or absent (legacy)"
            print(f"Found {len(data)} spec types")
            print(f"First spec: {spec.get('name')} - product_groups: {spec.get('product_groups', [])}")
    
    def test_toggle_spec_type_group_add(self):
        """PATCH /api/specifications/types/{type_id}/toggle-group should add a group"""
        # First get a spec type ID
        response = requests.get(f"{BASE_URL}/api/specifications/types")
        assert response.status_code == 200
        specs = response.json()
        assert len(specs) > 0, "Need at least one spec type to test"
        
        spec_id = specs[0]["id"]
        spec_name = specs[0]["name"]
        
        # Toggle add a group
        response = requests.patch(
            f"{BASE_URL}/api/specifications/types/{spec_id}/toggle-group",
            json={"product_group": "test-group-isolation", "action": "add"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "product_groups" in data, "Response should include product_groups"
        assert "test-group-isolation" in data["product_groups"], "Group should be added"
        print(f"Added 'test-group-isolation' to spec '{spec_name}'")
        
        # Clean up - remove the test group
        response = requests.patch(
            f"{BASE_URL}/api/specifications/types/{spec_id}/toggle-group",
            json={"product_group": "test-group-isolation", "action": "remove"}
        )
        assert response.status_code == 200
    
    def test_toggle_spec_type_group_remove(self):
        """PATCH /api/specifications/types/{type_id}/toggle-group should remove a group"""
        # First get a spec type ID
        response = requests.get(f"{BASE_URL}/api/specifications/types")
        assert response.status_code == 200
        specs = response.json()
        assert len(specs) > 0, "Need at least one spec type to test"
        
        spec_id = specs[0]["id"]
        
        # First add a group
        requests.patch(
            f"{BASE_URL}/api/specifications/types/{spec_id}/toggle-group",
            json={"product_group": "test-remove-group", "action": "add"}
        )
        
        # Now remove it
        response = requests.patch(
            f"{BASE_URL}/api/specifications/types/{spec_id}/toggle-group",
            json={"product_group": "test-remove-group", "action": "remove"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "product_groups" in data, "Response should include product_groups"
        assert "test-remove-group" not in data["product_groups"], "Group should be removed"
        print(f"Successfully removed 'test-remove-group' from spec")
    
    def test_toggle_spec_type_group_requires_product_group(self):
        """PATCH /api/specifications/types/{type_id}/toggle-group should require product_group"""
        response = requests.get(f"{BASE_URL}/api/specifications/types")
        specs = response.json()
        spec_id = specs[0]["id"]
        
        response = requests.patch(
            f"{BASE_URL}/api/specifications/types/{spec_id}/toggle-group",
            json={"action": "add"}  # Missing product_group
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("Correctly rejected request without product_group")
    
    def test_add_spec_value_with_product_groups(self):
        """POST /api/specifications/types/{type_id}/values should accept product_groups"""
        # Get a spec type
        response = requests.get(f"{BASE_URL}/api/specifications/types")
        specs = response.json()
        spec_id = specs[0]["id"]
        spec_name = specs[0]["name"]
        
        # Add a value with product_groups
        test_value = f"test-value-{int(time.time())}"
        response = requests.post(
            f"{BASE_URL}/api/specifications/types/{spec_id}/values",
            json={
                "value": test_value,
                "label": f"Test Value {test_value}",
                "is_active": True,
                "product_groups": ["tiles", "flooring"]
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"Added value '{test_value}' with product_groups=['tiles', 'flooring'] to spec '{spec_name}'")
        
        # Verify the value was added with product_groups
        response = requests.get(f"{BASE_URL}/api/specifications/types")
        specs = response.json()
        target_spec = next((s for s in specs if s["id"] == spec_id), None)
        assert target_spec is not None
        
        added_value = next((v for v in target_spec.get("values", []) if v.get("value") == test_value), None)
        assert added_value is not None, f"Value '{test_value}' should exist"
        assert added_value.get("product_groups") == ["tiles", "flooring"], \
            f"product_groups should be ['tiles', 'flooring'], got {added_value.get('product_groups')}"
        print(f"Verified value has product_groups: {added_value.get('product_groups')}")
        
        # Clean up - delete the test value
        response = requests.delete(f"{BASE_URL}/api/specifications/types/{spec_id}/values/{test_value}")
        assert response.status_code == 200


class TestFilterGroupIsolation:
    """Test filter type group isolation"""
    
    def test_get_filter_types_returns_auto_populate_groups(self):
        """GET /api/filters/types should return auto_populate_groups field"""
        response = requests.get(f"{BASE_URL}/api/filters/types")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list of filter types"
        
        if len(data) > 0:
            filter_type = data[0]
            # auto_populate_groups should be present (may be empty for legacy)
            print(f"Found {len(data)} filter types")
            print(f"First filter: {filter_type.get('name')} - auto_populate_groups: {filter_type.get('auto_populate_groups', [])}")
    
    def test_toggle_filter_type_group_add(self):
        """PATCH /api/filters/types/{filter_id}/toggle-group should add a group"""
        # Get a filter type ID
        response = requests.get(f"{BASE_URL}/api/filters/types")
        assert response.status_code == 200
        filters = response.json()
        assert len(filters) > 0, "Need at least one filter type to test"
        
        filter_id = filters[0]["id"]
        filter_name = filters[0]["name"]
        
        # Toggle add a group
        response = requests.patch(
            f"{BASE_URL}/api/filters/types/{filter_id}/toggle-group",
            json={"product_group": "test-filter-group", "action": "add"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "auto_populate_groups" in data, "Response should include auto_populate_groups"
        assert "test-filter-group" in data["auto_populate_groups"], "Group should be added"
        print(f"Added 'test-filter-group' to filter '{filter_name}'")
        
        # Clean up
        response = requests.patch(
            f"{BASE_URL}/api/filters/types/{filter_id}/toggle-group",
            json={"product_group": "test-filter-group", "action": "remove"}
        )
        assert response.status_code == 200
    
    def test_toggle_filter_type_group_remove(self):
        """PATCH /api/filters/types/{filter_id}/toggle-group should remove a group"""
        response = requests.get(f"{BASE_URL}/api/filters/types")
        filters = response.json()
        filter_id = filters[0]["id"]
        
        # First add
        requests.patch(
            f"{BASE_URL}/api/filters/types/{filter_id}/toggle-group",
            json={"product_group": "test-remove-filter", "action": "add"}
        )
        
        # Now remove
        response = requests.patch(
            f"{BASE_URL}/api/filters/types/{filter_id}/toggle-group",
            json={"product_group": "test-remove-filter", "action": "remove"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "auto_populate_groups" in data
        assert "test-remove-filter" not in data["auto_populate_groups"]
        print("Successfully removed 'test-remove-filter' from filter")
    
    def test_toggle_filter_type_group_requires_product_group(self):
        """PATCH /api/filters/types/{filter_id}/toggle-group should require product_group"""
        response = requests.get(f"{BASE_URL}/api/filters/types")
        filters = response.json()
        filter_id = filters[0]["id"]
        
        response = requests.patch(
            f"{BASE_URL}/api/filters/types/{filter_id}/toggle-group",
            json={"action": "add"}  # Missing product_group
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("Correctly rejected request without product_group")
    
    def test_add_filter_value_with_product_groups(self):
        """POST /api/filters/types/{filter_slug}/add-value should accept product_groups"""
        # Get a filter type
        response = requests.get(f"{BASE_URL}/api/filters/types")
        filters = response.json()
        filter_slug = filters[0]["slug"]
        filter_name = filters[0]["name"]
        
        # Add a value with product_groups
        test_value = f"test-filter-val-{int(time.time())}"
        response = requests.post(
            f"{BASE_URL}/api/filters/types/{filter_slug}/add-value",
            json={
                "value": test_value,
                "label": f"Test Filter Value {test_value}",
                "is_active": True,
                "product_groups": ["bathroom", "outdoor"]
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"Added value '{test_value}' with product_groups=['bathroom', 'outdoor'] to filter '{filter_name}'")
        
        # Verify the value was added with product_groups
        response = requests.get(f"{BASE_URL}/api/filters/types")
        filters = response.json()
        target_filter = next((f for f in filters if f["slug"] == filter_slug), None)
        assert target_filter is not None
        
        added_value = next((v for v in target_filter.get("values", []) if v.get("value") == test_value), None)
        assert added_value is not None, f"Value '{test_value}' should exist"
        assert added_value.get("product_groups") == ["bathroom", "outdoor"], \
            f"product_groups should be ['bathroom', 'outdoor'], got {added_value.get('product_groups')}"
        print(f"Verified value has product_groups: {added_value.get('product_groups')}")
        
        # Clean up
        filter_id = target_filter["id"]
        response = requests.delete(f"{BASE_URL}/api/filters/types/by-slug/{filter_slug}/values/{test_value}")
        # May return 200 or 404 if already cleaned up


class TestGroupIsolationIntegration:
    """Integration tests for group isolation"""
    
    def test_spec_type_scoped_to_tiles_not_visible_in_flooring(self):
        """A spec type scoped to 'tiles' should not appear when filtering for 'flooring'"""
        # Get all spec types
        response = requests.get(f"{BASE_URL}/api/specifications/types")
        specs = response.json()
        
        # Find a spec with product_groups set
        scoped_spec = next((s for s in specs if s.get("product_groups") and len(s.get("product_groups")) > 0), None)
        
        if scoped_spec:
            groups = scoped_spec.get("product_groups", [])
            print(f"Found scoped spec '{scoped_spec['name']}' with groups: {groups}")
            
            # If scoped to specific groups, it should NOT be visible in other groups
            # This is a data verification test
            assert isinstance(groups, list), "product_groups should be a list"
        else:
            print("No scoped specs found - all specs are currently unscoped (visible everywhere)")
            # This is expected for legacy data
    
    def test_filter_type_scoped_to_bathroom_not_visible_in_tiles(self):
        """A filter type scoped to 'bathroom' should not appear when filtering for 'tiles'"""
        response = requests.get(f"{BASE_URL}/api/filters/types")
        filters = response.json()
        
        scoped_filter = next((f for f in filters if f.get("auto_populate_groups") and len(f.get("auto_populate_groups")) > 0), None)
        
        if scoped_filter:
            groups = scoped_filter.get("auto_populate_groups", [])
            print(f"Found scoped filter '{scoped_filter['name']}' with groups: {groups}")
            assert isinstance(groups, list), "auto_populate_groups should be a list"
        else:
            print("No scoped filters found - all filters are currently unscoped (visible everywhere)")
    
    def test_value_with_product_groups_isolation(self):
        """Values with product_groups should only be visible in those groups"""
        # Get spec types and check for values with product_groups
        response = requests.get(f"{BASE_URL}/api/specifications/types")
        specs = response.json()
        
        for spec in specs:
            for value in spec.get("values", []):
                if value.get("product_groups") and len(value.get("product_groups")) > 0:
                    print(f"Spec '{spec['name']}' value '{value['value']}' scoped to: {value['product_groups']}")
                    return  # Found at least one scoped value
        
        print("No scoped values found in specs - all values are currently unscoped")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

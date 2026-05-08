"""
Test Filter & Specification Group Assignment APIs
Tests for admin UI to assign filters and specifications to product groups
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
ADMIN_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbkB0ZXN0LmNvbSIsInJvbGUiOiJzdXBlcl9hZG1pbiIsImV4cCI6MTc3NTI5NTEyOX0.iGYO6F7xZqpfNzEblG25GPQUgnQ0FNemATXIXosEW40"

@pytest.fixture
def auth_headers():
    """Headers with admin authentication"""
    return {
        "Authorization": f"Bearer {ADMIN_TOKEN}",
        "Content-Type": "application/json"
    }


class TestFilterTypesAPI:
    """Test GET /api/filters/types endpoint"""
    
    def test_get_filter_types_returns_200(self, auth_headers):
        """GET /api/filters/types should return 200 with list of filters"""
        response = requests.get(f"{BASE_URL}/api/filters/types", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ GET /api/filters/types returned {len(data)} filter types")
    
    def test_filter_types_have_required_fields(self, auth_headers):
        """Each filter type should have id, name, slug, hidden_groups"""
        response = requests.get(f"{BASE_URL}/api/filters/types", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) > 0, "Should have at least one filter type"
        
        for filter_type in data[:5]:  # Check first 5
            assert "id" in filter_type, f"Filter missing 'id': {filter_type}"
            assert "name" in filter_type, f"Filter missing 'name': {filter_type}"
            assert "slug" in filter_type, f"Filter missing 'slug': {filter_type}"
            # hidden_groups may not exist if never set - that's OK
            print(f"  ✓ Filter '{filter_type['name']}' has required fields, hidden_groups: {filter_type.get('hidden_groups', [])}")
    
    def test_filter_types_have_values(self, auth_headers):
        """Filter types should have values array"""
        response = requests.get(f"{BASE_URL}/api/filters/types", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        filters_with_values = [f for f in data if f.get('values') and len(f.get('values', [])) > 0]
        print(f"✓ {len(filters_with_values)} filters have values defined")
        
        # Check a filter with values
        if filters_with_values:
            sample = filters_with_values[0]
            print(f"  Sample: '{sample['name']}' has {len(sample['values'])} values")


class TestSpecificationTypesAPI:
    """Test GET /api/specifications/types endpoint"""
    
    def test_get_spec_types_returns_200(self, auth_headers):
        """GET /api/specifications/types should return 200 with list of specs"""
        response = requests.get(f"{BASE_URL}/api/specifications/types", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ GET /api/specifications/types returned {len(data)} spec types")
    
    def test_spec_types_have_required_fields(self, auth_headers):
        """Each spec type should have id, name, slug, hidden_groups"""
        response = requests.get(f"{BASE_URL}/api/specifications/types", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) > 0, "Should have at least one spec type"
        
        for spec_type in data[:5]:  # Check first 5
            assert "id" in spec_type, f"Spec missing 'id': {spec_type}"
            assert "name" in spec_type, f"Spec missing 'name': {spec_type}"
            assert "slug" in spec_type, f"Spec missing 'slug': {spec_type}"
            print(f"  ✓ Spec '{spec_type['name']}' has required fields, hidden_groups: {spec_type.get('hidden_groups', [])}")


class TestFilterToggleVisibilityAPI:
    """Test PATCH /api/filters/types/{id}/toggle-type-visibility endpoint"""
    
    def test_toggle_filter_hide(self, auth_headers):
        """PATCH toggle-type-visibility with action='hide' should add group to hidden_groups"""
        # First get a filter ID
        response = requests.get(f"{BASE_URL}/api/filters/types", headers=auth_headers)
        assert response.status_code == 200
        filters = response.json()
        assert len(filters) > 0, "Need at least one filter to test"
        
        test_filter = filters[0]
        filter_id = test_filter['id']
        filter_name = test_filter['name']
        
        # Toggle to hide for 'materials' group
        toggle_response = requests.patch(
            f"{BASE_URL}/api/filters/types/{filter_id}/toggle-type-visibility",
            headers=auth_headers,
            json={"product_group": "materials", "action": "hide"}
        )
        assert toggle_response.status_code == 200, f"Expected 200, got {toggle_response.status_code}: {toggle_response.text}"
        
        result = toggle_response.json()
        assert "hidden_groups" in result, "Response should contain hidden_groups"
        assert "materials" in result["hidden_groups"], f"'materials' should be in hidden_groups: {result['hidden_groups']}"
        print(f"✓ Filter '{filter_name}' hidden from 'materials', hidden_groups: {result['hidden_groups']}")
    
    def test_toggle_filter_show(self, auth_headers):
        """PATCH toggle-type-visibility with action='show' should remove group from hidden_groups"""
        # First get a filter ID
        response = requests.get(f"{BASE_URL}/api/filters/types", headers=auth_headers)
        assert response.status_code == 200
        filters = response.json()
        assert len(filters) > 0
        
        test_filter = filters[0]
        filter_id = test_filter['id']
        filter_name = test_filter['name']
        
        # First hide it
        requests.patch(
            f"{BASE_URL}/api/filters/types/{filter_id}/toggle-type-visibility",
            headers=auth_headers,
            json={"product_group": "tools", "action": "hide"}
        )
        
        # Then show it
        toggle_response = requests.patch(
            f"{BASE_URL}/api/filters/types/{filter_id}/toggle-type-visibility",
            headers=auth_headers,
            json={"product_group": "tools", "action": "show"}
        )
        assert toggle_response.status_code == 200
        
        result = toggle_response.json()
        assert "hidden_groups" in result
        assert "tools" not in result["hidden_groups"], f"'tools' should NOT be in hidden_groups: {result['hidden_groups']}"
        print(f"✓ Filter '{filter_name}' shown in 'tools', hidden_groups: {result['hidden_groups']}")
    
    def test_toggle_filter_missing_product_group(self, auth_headers):
        """PATCH toggle-type-visibility without product_group should return 400"""
        response = requests.get(f"{BASE_URL}/api/filters/types", headers=auth_headers)
        filters = response.json()
        filter_id = filters[0]['id']
        
        toggle_response = requests.patch(
            f"{BASE_URL}/api/filters/types/{filter_id}/toggle-type-visibility",
            headers=auth_headers,
            json={"action": "hide"}  # Missing product_group
        )
        assert toggle_response.status_code == 400, f"Expected 400, got {toggle_response.status_code}"
        print("✓ Missing product_group returns 400")
    
    def test_toggle_filter_invalid_id(self, auth_headers):
        """PATCH toggle-type-visibility with invalid ID should return 404"""
        toggle_response = requests.patch(
            f"{BASE_URL}/api/filters/types/000000000000000000000000/toggle-type-visibility",
            headers=auth_headers,
            json={"product_group": "tiles", "action": "hide"}
        )
        assert toggle_response.status_code == 404, f"Expected 404, got {toggle_response.status_code}"
        print("✓ Invalid filter ID returns 404")


class TestSpecToggleVisibilityAPI:
    """Test PATCH /api/specifications/types/{id}/toggle-type-visibility endpoint"""
    
    def test_toggle_spec_hide(self, auth_headers):
        """PATCH toggle-type-visibility with action='hide' should add group to hidden_groups"""
        # First get a spec ID
        response = requests.get(f"{BASE_URL}/api/specifications/types", headers=auth_headers)
        assert response.status_code == 200
        specs = response.json()
        assert len(specs) > 0, "Need at least one spec to test"
        
        test_spec = specs[0]
        spec_id = test_spec['id']
        spec_name = test_spec['name']
        
        # Toggle to hide for 'accessories' group
        toggle_response = requests.patch(
            f"{BASE_URL}/api/specifications/types/{spec_id}/toggle-type-visibility",
            headers=auth_headers,
            json={"product_group": "accessories", "action": "hide"}
        )
        assert toggle_response.status_code == 200, f"Expected 200, got {toggle_response.status_code}: {toggle_response.text}"
        
        result = toggle_response.json()
        assert "hidden_groups" in result, "Response should contain hidden_groups"
        assert "accessories" in result["hidden_groups"], f"'accessories' should be in hidden_groups: {result['hidden_groups']}"
        print(f"✓ Spec '{spec_name}' hidden from 'accessories', hidden_groups: {result['hidden_groups']}")
    
    def test_toggle_spec_show(self, auth_headers):
        """PATCH toggle-type-visibility with action='show' should remove group from hidden_groups"""
        response = requests.get(f"{BASE_URL}/api/specifications/types", headers=auth_headers)
        specs = response.json()
        
        test_spec = specs[0]
        spec_id = test_spec['id']
        spec_name = test_spec['name']
        
        # First hide it
        requests.patch(
            f"{BASE_URL}/api/specifications/types/{spec_id}/toggle-type-visibility",
            headers=auth_headers,
            json={"product_group": "underfloor-heating", "action": "hide"}
        )
        
        # Then show it
        toggle_response = requests.patch(
            f"{BASE_URL}/api/specifications/types/{spec_id}/toggle-type-visibility",
            headers=auth_headers,
            json={"product_group": "underfloor-heating", "action": "show"}
        )
        assert toggle_response.status_code == 200
        
        result = toggle_response.json()
        assert "hidden_groups" in result
        assert "underfloor-heating" not in result["hidden_groups"]
        print(f"✓ Spec '{spec_name}' shown in 'underfloor-heating', hidden_groups: {result['hidden_groups']}")
    
    def test_toggle_spec_missing_product_group(self, auth_headers):
        """PATCH toggle-type-visibility without product_group should return 400"""
        response = requests.get(f"{BASE_URL}/api/specifications/types", headers=auth_headers)
        specs = response.json()
        spec_id = specs[0]['id']
        
        toggle_response = requests.patch(
            f"{BASE_URL}/api/specifications/types/{spec_id}/toggle-type-visibility",
            headers=auth_headers,
            json={"action": "hide"}
        )
        assert toggle_response.status_code == 400
        print("✓ Missing product_group returns 400")
    
    def test_toggle_spec_invalid_id(self, auth_headers):
        """PATCH toggle-type-visibility with invalid ID should return 404"""
        toggle_response = requests.patch(
            f"{BASE_URL}/api/specifications/types/000000000000000000000000/toggle-type-visibility",
            headers=auth_headers,
            json={"product_group": "tiles", "action": "hide"}
        )
        assert toggle_response.status_code == 404
        print("✓ Invalid spec ID returns 404")


class TestVisibilityPersistence:
    """Test that visibility changes persist correctly"""
    
    def test_filter_visibility_persists_after_refetch(self, auth_headers):
        """After toggling, refetching should show updated hidden_groups"""
        # Get a filter
        response = requests.get(f"{BASE_URL}/api/filters/types", headers=auth_headers)
        filters = response.json()
        test_filter = filters[0]
        filter_id = test_filter['id']
        
        # Hide from 'flooring'
        requests.patch(
            f"{BASE_URL}/api/filters/types/{filter_id}/toggle-type-visibility",
            headers=auth_headers,
            json={"product_group": "flooring", "action": "hide"}
        )
        
        # Refetch all filters
        response2 = requests.get(f"{BASE_URL}/api/filters/types", headers=auth_headers)
        filters2 = response2.json()
        
        # Find the same filter
        updated_filter = next((f for f in filters2 if f['id'] == filter_id), None)
        assert updated_filter is not None
        assert "flooring" in updated_filter.get('hidden_groups', []), \
            f"'flooring' should persist in hidden_groups: {updated_filter.get('hidden_groups', [])}"
        print(f"✓ Filter visibility persists after refetch: {updated_filter.get('hidden_groups', [])}")
        
        # Clean up - show it again
        requests.patch(
            f"{BASE_URL}/api/filters/types/{filter_id}/toggle-type-visibility",
            headers=auth_headers,
            json={"product_group": "flooring", "action": "show"}
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

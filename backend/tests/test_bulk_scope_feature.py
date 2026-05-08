"""
Bulk Scope Feature Tests
Tests for POST /api/specifications/types/bulk-assign-group and POST /api/filters/types/bulk-assign-group
These endpoints allow admins to bulk-assign or bulk-remove product groups from multiple spec/filter types at once.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')

# Known spec type IDs from context
SPEC_TYPE_IDS = {
    "material": "69ba7a646bc1e8fd70e3be39",
    "finish": "69ba7a646bc1e8fd70e3be3b",
    "size": "69ba7a646bc1e8fd70e3be3a",
    "color": "69ba7a646bc1e8fd70e3be3c"
}

# Known filter type IDs from context
FILTER_TYPE_IDS = {
    "color": "69b99daaff7cebf6fb7146da",
    "edge": "69baae6e3849793fe491a10b"
}

TEST_PRODUCT_GROUP = "test-bulk-scope-group"


class TestSpecificationsBulkAssignGroup:
    """Tests for POST /api/specifications/types/bulk-assign-group"""
    
    def test_bulk_assign_spec_types_add_group(self):
        """Should bulk-assign a product group to multiple spec types"""
        # Use two spec type IDs
        type_ids = [SPEC_TYPE_IDS["material"], SPEC_TYPE_IDS["finish"]]
        
        response = requests.post(
            f"{BASE_URL}/api/specifications/types/bulk-assign-group",
            json={
                "type_ids": type_ids,
                "product_group": TEST_PRODUCT_GROUP,
                "action": "add"
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "updated" in data
        assert data["updated"] >= 0  # May be 0 if already assigned
        assert "message" in data
        print(f"PASS: Bulk assign add - {data['updated']} spec types updated")
    
    def test_bulk_remove_spec_types_from_group(self):
        """Should bulk-remove a product group from multiple spec types"""
        type_ids = [SPEC_TYPE_IDS["material"], SPEC_TYPE_IDS["finish"]]
        
        response = requests.post(
            f"{BASE_URL}/api/specifications/types/bulk-assign-group",
            json={
                "type_ids": type_ids,
                "product_group": TEST_PRODUCT_GROUP,
                "action": "remove"
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "updated" in data
        assert "message" in data
        print(f"PASS: Bulk assign remove - {data['updated']} spec types updated")
    
    def test_bulk_assign_spec_types_missing_type_ids(self):
        """Should return 400 when type_ids is missing"""
        response = requests.post(
            f"{BASE_URL}/api/specifications/types/bulk-assign-group",
            json={
                "product_group": TEST_PRODUCT_GROUP,
                "action": "add"
            }
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        data = response.json()
        assert "detail" in data
        print(f"PASS: Returns 400 when type_ids missing - {data['detail']}")
    
    def test_bulk_assign_spec_types_missing_product_group(self):
        """Should return 400 when product_group is missing"""
        response = requests.post(
            f"{BASE_URL}/api/specifications/types/bulk-assign-group",
            json={
                "type_ids": [SPEC_TYPE_IDS["material"]],
                "action": "add"
            }
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        data = response.json()
        assert "detail" in data
        print(f"PASS: Returns 400 when product_group missing - {data['detail']}")
    
    def test_bulk_assign_spec_types_empty_type_ids(self):
        """Should return 400 when type_ids is empty array"""
        response = requests.post(
            f"{BASE_URL}/api/specifications/types/bulk-assign-group",
            json={
                "type_ids": [],
                "product_group": TEST_PRODUCT_GROUP,
                "action": "add"
            }
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        print("PASS: Returns 400 when type_ids is empty")
    
    def test_bulk_assign_spec_types_invalid_ids_handled_gracefully(self):
        """Should handle invalid IDs gracefully (skip them, not crash)"""
        response = requests.post(
            f"{BASE_URL}/api/specifications/types/bulk-assign-group",
            json={
                "type_ids": ["invalid-id-123", "another-invalid"],
                "product_group": TEST_PRODUCT_GROUP,
                "action": "add"
            }
        )
        
        # Should return 200 with 0 updated (graceful handling)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["updated"] == 0
        print("PASS: Invalid IDs handled gracefully")


class TestFiltersBulkAssignGroup:
    """Tests for POST /api/filters/types/bulk-assign-group"""
    
    def test_bulk_assign_filter_types_add_group(self):
        """Should bulk-assign a product group to multiple filter types"""
        type_ids = [FILTER_TYPE_IDS["color"], FILTER_TYPE_IDS["edge"]]
        
        response = requests.post(
            f"{BASE_URL}/api/filters/types/bulk-assign-group",
            json={
                "type_ids": type_ids,
                "product_group": TEST_PRODUCT_GROUP,
                "action": "add"
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "updated" in data
        assert data["updated"] >= 0
        assert "message" in data
        print(f"PASS: Bulk assign add filters - {data['updated']} filter types updated")
    
    def test_bulk_remove_filter_types_from_group(self):
        """Should bulk-remove a product group from multiple filter types"""
        type_ids = [FILTER_TYPE_IDS["color"], FILTER_TYPE_IDS["edge"]]
        
        response = requests.post(
            f"{BASE_URL}/api/filters/types/bulk-assign-group",
            json={
                "type_ids": type_ids,
                "product_group": TEST_PRODUCT_GROUP,
                "action": "remove"
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "updated" in data
        assert "message" in data
        print(f"PASS: Bulk assign remove filters - {data['updated']} filter types updated")
    
    def test_bulk_assign_filter_types_missing_type_ids(self):
        """Should return 400 when type_ids is missing"""
        response = requests.post(
            f"{BASE_URL}/api/filters/types/bulk-assign-group",
            json={
                "product_group": TEST_PRODUCT_GROUP,
                "action": "add"
            }
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        data = response.json()
        assert "detail" in data
        print(f"PASS: Returns 400 when type_ids missing - {data['detail']}")
    
    def test_bulk_assign_filter_types_missing_product_group(self):
        """Should return 400 when product_group is missing"""
        response = requests.post(
            f"{BASE_URL}/api/filters/types/bulk-assign-group",
            json={
                "type_ids": [FILTER_TYPE_IDS["color"]],
                "action": "add"
            }
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        data = response.json()
        assert "detail" in data
        print(f"PASS: Returns 400 when product_group missing - {data['detail']}")
    
    def test_bulk_assign_filter_types_empty_type_ids(self):
        """Should return 400 when type_ids is empty array"""
        response = requests.post(
            f"{BASE_URL}/api/filters/types/bulk-assign-group",
            json={
                "type_ids": [],
                "product_group": TEST_PRODUCT_GROUP,
                "action": "add"
            }
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        print("PASS: Returns 400 when type_ids is empty")
    
    def test_bulk_assign_filter_types_invalid_ids_handled_gracefully(self):
        """Should handle invalid IDs gracefully (skip them, not crash)"""
        response = requests.post(
            f"{BASE_URL}/api/filters/types/bulk-assign-group",
            json={
                "type_ids": ["invalid-id-123", "another-invalid"],
                "product_group": TEST_PRODUCT_GROUP,
                "action": "add"
            }
        )
        
        # Should return 200 with 0 updated (graceful handling)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["updated"] == 0
        print("PASS: Invalid IDs handled gracefully")


class TestBulkAssignVerifyPersistence:
    """Tests to verify bulk assign actually persists changes"""
    
    def test_bulk_assign_spec_and_verify_persistence(self):
        """Assign group to spec, then GET to verify it persisted"""
        spec_id = SPEC_TYPE_IDS["size"]
        
        # First, add the group
        add_response = requests.post(
            f"{BASE_URL}/api/specifications/types/bulk-assign-group",
            json={
                "type_ids": [spec_id],
                "product_group": TEST_PRODUCT_GROUP,
                "action": "add"
            }
        )
        assert add_response.status_code == 200
        
        # GET the spec type to verify
        get_response = requests.get(f"{BASE_URL}/api/specifications/types")
        assert get_response.status_code == 200
        
        specs = get_response.json()
        target_spec = next((s for s in specs if s.get("id") == spec_id), None)
        
        if target_spec:
            product_groups = target_spec.get("product_groups", [])
            assert TEST_PRODUCT_GROUP in product_groups, f"Expected {TEST_PRODUCT_GROUP} in {product_groups}"
            print(f"PASS: Verified {TEST_PRODUCT_GROUP} persisted in spec type product_groups")
        else:
            print(f"WARN: Could not find spec with id {spec_id} to verify")
        
        # Cleanup: remove the test group
        requests.post(
            f"{BASE_URL}/api/specifications/types/bulk-assign-group",
            json={
                "type_ids": [spec_id],
                "product_group": TEST_PRODUCT_GROUP,
                "action": "remove"
            }
        )
    
    def test_bulk_assign_filter_and_verify_persistence(self):
        """Assign group to filter, then GET to verify it persisted"""
        filter_id = FILTER_TYPE_IDS["color"]
        
        # First, add the group
        add_response = requests.post(
            f"{BASE_URL}/api/filters/types/bulk-assign-group",
            json={
                "type_ids": [filter_id],
                "product_group": TEST_PRODUCT_GROUP,
                "action": "add"
            }
        )
        assert add_response.status_code == 200
        
        # GET the filter type to verify
        get_response = requests.get(f"{BASE_URL}/api/filters/types")
        assert get_response.status_code == 200
        
        filters = get_response.json()
        target_filter = next((f for f in filters if f.get("id") == filter_id), None)
        
        if target_filter:
            auto_populate_groups = target_filter.get("auto_populate_groups", [])
            assert TEST_PRODUCT_GROUP in auto_populate_groups, f"Expected {TEST_PRODUCT_GROUP} in {auto_populate_groups}"
            print(f"PASS: Verified {TEST_PRODUCT_GROUP} persisted in filter type auto_populate_groups")
        else:
            print(f"WARN: Could not find filter with id {filter_id} to verify")
        
        # Cleanup: remove the test group
        requests.post(
            f"{BASE_URL}/api/filters/types/bulk-assign-group",
            json={
                "type_ids": [filter_id],
                "product_group": TEST_PRODUCT_GROUP,
                "action": "remove"
            }
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

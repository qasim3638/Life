"""
Test Multi-Target Bulk Assign Feature for Collection Organizer
Tests the upgraded bulk-assign endpoint that supports multiple target categories simultaneously
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestMultiTargetBulkAssign:
    """Tests for the multi-target bulk assign feature in Collection Organizer"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.token = self._get_auth_token()
        self.headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }
        self.supplier = "Plus39"  # Known supplier with 4 series
        
    def _get_auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "admin123"
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Authentication failed")
    
    def _cleanup_assignment(self, series_name, main_category, sub_category=None):
        """Helper to unassign a series after test"""
        body = {
            "supplier": self.supplier,
            "series": series_name,
            "main_category": main_category
        }
        if sub_category:
            body["sub_categories"] = [sub_category]
        
        requests.post(
            f"{BASE_URL}/api/website-admin/collection-organizer/unassign",
            headers=self.headers,
            json=body
        )
    
    def _get_series_list(self):
        """Helper to get available series"""
        response = requests.get(
            f"{BASE_URL}/api/website-admin/collection-organizer/series?supplier={self.supplier}",
            headers=self.headers
        )
        if response.status_code == 200:
            return response.json().get("series", [])
        return []
    
    # ============ MULTI-TARGET BULK ASSIGN TESTS ============
    
    def test_multi_target_bulk_assign_with_targets_array(self):
        """Test bulk assign with 'targets' array containing multiple categories"""
        series_list = self._get_series_list()
        if not series_list:
            pytest.skip("No series available")
        
        test_series = series_list[0]["name"]
        
        # Assign to multiple targets at once
        response = requests.post(
            f"{BASE_URL}/api/website-admin/collection-organizer/bulk-assign",
            headers=self.headers,
            json={
                "supplier": self.supplier,
                "series_names": [test_series],
                "targets": [
                    {"group_slug": "tiles", "main_category": "Tiles", "sub_categories": ["Wall Tiles"]},
                    {"group_slug": "tiles", "main_category": "Tiles", "sub_categories": ["Bathroom Tiles"]}
                ]
            }
        )
        assert response.status_code == 200, f"Multi-target bulk assign failed: {response.text}"
        data = response.json()
        
        assert data.get("success") == True
        assert "message" in data
        assert "total_products_updated" in data
        
        print(f"PASS: Multi-target bulk assign with targets array - {data['total_products_updated']} products updated")
        print(f"Message: {data['message']}")
        
        # Verify assignment
        verify_res = requests.get(
            f"{BASE_URL}/api/website-admin/collection-organizer/series?supplier={self.supplier}",
            headers=self.headers
        )
        updated_series = verify_res.json().get("series", [])
        
        for s in updated_series:
            if s["name"] == test_series:
                subs = s.get("sub_categories", [])
                assert "Wall Tiles" in subs, f"Expected 'Wall Tiles' in sub_categories, got {subs}"
                assert "Bathroom Tiles" in subs, f"Expected 'Bathroom Tiles' in sub_categories, got {subs}"
                print(f"VERIFIED: {test_series} has sub_categories: {subs}")
                break
        
        # Cleanup
        self._cleanup_assignment(test_series, "Tiles", "Wall Tiles")
        self._cleanup_assignment(test_series, "Tiles", "Bathroom Tiles")
    
    def test_multi_target_three_categories(self):
        """Test bulk assign to three categories simultaneously (Wall Tiles + Bathroom Tiles + Floor Tiles)"""
        series_list = self._get_series_list()
        if not series_list:
            pytest.skip("No series available")
        
        test_series = series_list[0]["name"]
        
        response = requests.post(
            f"{BASE_URL}/api/website-admin/collection-organizer/bulk-assign",
            headers=self.headers,
            json={
                "supplier": self.supplier,
                "series_names": [test_series],
                "targets": [
                    {"group_slug": "tiles", "main_category": "Tiles", "sub_categories": ["Wall Tiles"]},
                    {"group_slug": "tiles", "main_category": "Tiles", "sub_categories": ["Bathroom Tiles"]},
                    {"group_slug": "tiles", "main_category": "Tiles", "sub_categories": ["Floor Tiles"]}
                ]
            }
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert data.get("success") == True
        print(f"PASS: Assigned to 3 categories - {data['message']}")
        
        # Verify all three categories are assigned
        verify_res = requests.get(
            f"{BASE_URL}/api/website-admin/collection-organizer/series?supplier={self.supplier}",
            headers=self.headers
        )
        for s in verify_res.json().get("series", []):
            if s["name"] == test_series:
                subs = s.get("sub_categories", [])
                assert "Wall Tiles" in subs
                assert "Bathroom Tiles" in subs
                assert "Floor Tiles" in subs
                print(f"VERIFIED: All 3 categories assigned: {subs}")
                break
        
        # Cleanup
        self._cleanup_assignment(test_series, "Tiles", "Wall Tiles")
        self._cleanup_assignment(test_series, "Tiles", "Bathroom Tiles")
        self._cleanup_assignment(test_series, "Tiles", "Floor Tiles")
    
    def test_multi_target_multiple_series_multiple_categories(self):
        """Test bulk assign multiple series to multiple categories at once"""
        series_list = self._get_series_list()
        if len(series_list) < 2:
            pytest.skip("Need at least 2 series")
        
        test_series = [s["name"] for s in series_list[:2]]
        
        response = requests.post(
            f"{BASE_URL}/api/website-admin/collection-organizer/bulk-assign",
            headers=self.headers,
            json={
                "supplier": self.supplier,
                "series_names": test_series,
                "targets": [
                    {"group_slug": "tiles", "main_category": "Tiles", "sub_categories": ["Kitchen Tiles"]},
                    {"group_slug": "tiles", "main_category": "Tiles", "sub_categories": ["Outdoor Tiles"]}
                ]
            }
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert data.get("success") == True
        assert len(data["details"]) == 2
        print(f"PASS: Assigned {len(test_series)} series to 2 categories - {data['total_products_updated']} products")
        
        # Cleanup
        for series_name in test_series:
            self._cleanup_assignment(series_name, "Tiles", "Kitchen Tiles")
            self._cleanup_assignment(series_name, "Tiles", "Outdoor Tiles")
    
    def test_backwards_compatible_single_target(self):
        """Test that old format (flat fields) still works for backwards compatibility"""
        series_list = self._get_series_list()
        if not series_list:
            pytest.skip("No series available")
        
        test_series = series_list[0]["name"]
        
        # Use old format without 'targets' array
        response = requests.post(
            f"{BASE_URL}/api/website-admin/collection-organizer/bulk-assign",
            headers=self.headers,
            json={
                "supplier": self.supplier,
                "series_names": [test_series],
                "group_slug": "tiles",
                "main_category": "Tiles",
                "sub_categories": ["Mosaic Tiles"]
            }
        )
        assert response.status_code == 200, f"Backwards compatible format failed: {response.text}"
        data = response.json()
        
        assert data.get("success") == True
        print(f"PASS: Backwards compatible single target format works - {data['message']}")
        
        # Cleanup
        self._cleanup_assignment(test_series, "Tiles", "Mosaic Tiles")
    
    def test_multi_target_merges_sub_categories(self):
        """Test that multi-target correctly merges sub_categories from all targets"""
        series_list = self._get_series_list()
        if not series_list:
            pytest.skip("No series available")
        
        test_series = series_list[0]["name"]
        
        # First assign to one category
        requests.post(
            f"{BASE_URL}/api/website-admin/collection-organizer/bulk-assign",
            headers=self.headers,
            json={
                "supplier": self.supplier,
                "series_names": [test_series],
                "targets": [
                    {"group_slug": "tiles", "main_category": "Tiles", "sub_categories": ["Wall Tiles"]}
                ]
            }
        )
        
        # Then assign to additional categories - should merge, not replace
        response = requests.post(
            f"{BASE_URL}/api/website-admin/collection-organizer/bulk-assign",
            headers=self.headers,
            json={
                "supplier": self.supplier,
                "series_names": [test_series],
                "targets": [
                    {"group_slug": "tiles", "main_category": "Tiles", "sub_categories": ["Floor Tiles"]},
                    {"group_slug": "tiles", "main_category": "Tiles", "sub_categories": ["Bathroom Tiles"]}
                ]
            }
        )
        assert response.status_code == 200
        
        # Verify all categories are present (merged)
        verify_res = requests.get(
            f"{BASE_URL}/api/website-admin/collection-organizer/series?supplier={self.supplier}",
            headers=self.headers
        )
        for s in verify_res.json().get("series", []):
            if s["name"] == test_series:
                subs = s.get("sub_categories", [])
                # Should have all three from both calls
                assert "Wall Tiles" in subs, f"Wall Tiles missing after merge, got {subs}"
                assert "Floor Tiles" in subs, f"Floor Tiles missing after merge, got {subs}"
                assert "Bathroom Tiles" in subs, f"Bathroom Tiles missing after merge, got {subs}"
                print(f"PASS: Sub-categories correctly merged: {subs}")
                break
        
        # Cleanup
        self._cleanup_assignment(test_series, "Tiles", "Wall Tiles")
        self._cleanup_assignment(test_series, "Tiles", "Floor Tiles")
        self._cleanup_assignment(test_series, "Tiles", "Bathroom Tiles")
    
    def test_multi_target_empty_targets_array_fails(self):
        """Test that empty targets array returns error"""
        response = requests.post(
            f"{BASE_URL}/api/website-admin/collection-organizer/bulk-assign",
            headers=self.headers,
            json={
                "supplier": self.supplier,
                "series_names": ["Artisan"],
                "targets": []
            }
        )
        # Should fail because no targets provided
        assert response.status_code == 400
        print(f"PASS: Empty targets array correctly rejected")
    
    def test_multi_target_all_four_series_to_multiple_categories(self):
        """Test assigning all 4 Plus39 series to multiple categories at once"""
        series_list = self._get_series_list()
        all_series_names = [s["name"] for s in series_list]
        
        if len(all_series_names) < 4:
            pytest.skip(f"Expected 4 series, found {len(all_series_names)}")
        
        response = requests.post(
            f"{BASE_URL}/api/website-admin/collection-organizer/bulk-assign",
            headers=self.headers,
            json={
                "supplier": self.supplier,
                "series_names": all_series_names,
                "targets": [
                    {"group_slug": "tiles", "main_category": "Tiles", "sub_categories": ["Wall Tiles"]},
                    {"group_slug": "tiles", "main_category": "Tiles", "sub_categories": ["Floor Tiles"]}
                ]
            }
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert data.get("success") == True
        assert len(data["details"]) == len(all_series_names)
        print(f"PASS: Assigned all {len(all_series_names)} series to 2 categories - {data['total_products_updated']} products")
        
        # Cleanup all
        for series_name in all_series_names:
            self._cleanup_assignment(series_name, "Tiles", "Wall Tiles")
            self._cleanup_assignment(series_name, "Tiles", "Floor Tiles")
    
    def test_response_message_shows_all_targets(self):
        """Test that response message includes all target categories"""
        series_list = self._get_series_list()
        if not series_list:
            pytest.skip("No series available")
        
        test_series = series_list[0]["name"]
        
        response = requests.post(
            f"{BASE_URL}/api/website-admin/collection-organizer/bulk-assign",
            headers=self.headers,
            json={
                "supplier": self.supplier,
                "series_names": [test_series],
                "targets": [
                    {"group_slug": "tiles", "main_category": "Tiles", "sub_categories": ["Wall Tiles"]},
                    {"group_slug": "tiles", "main_category": "Tiles", "sub_categories": ["Bathroom Tiles"]},
                    {"group_slug": "tiles", "main_category": "Tiles", "sub_categories": ["Floor Tiles"]}
                ]
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        message = data.get("message", "")
        # Message should mention the categories
        assert "Tiles" in message
        print(f"PASS: Response message: {message}")
        
        # Cleanup
        self._cleanup_assignment(test_series, "Tiles", "Wall Tiles")
        self._cleanup_assignment(test_series, "Tiles", "Bathroom Tiles")
        self._cleanup_assignment(test_series, "Tiles", "Floor Tiles")


class TestExistingEndpointsStillWork:
    """Verify existing endpoints still work with multi-target feature"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.token = self._get_auth_token()
        self.headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }
        self.supplier = "Plus39"
    
    def _get_auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "admin123"
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Authentication failed")
    
    def test_single_assign_endpoint_still_works(self):
        """Test that single assign (drag-and-drop) endpoint still works"""
        series_res = requests.get(
            f"{BASE_URL}/api/website-admin/collection-organizer/series?supplier={self.supplier}",
            headers=self.headers
        )
        series_list = series_res.json().get("series", [])
        
        if not series_list:
            pytest.skip("No series available")
        
        test_series = series_list[0]["name"]
        
        response = requests.post(
            f"{BASE_URL}/api/website-admin/collection-organizer/assign",
            headers=self.headers,
            json={
                "supplier": self.supplier,
                "series": test_series,
                "group_slug": "tiles",
                "main_category": "Tiles",
                "sub_categories": ["Clearance"]
            }
        )
        assert response.status_code == 200
        print(f"PASS: Single assign (drag-and-drop) endpoint still works")
        
        # Cleanup
        requests.post(
            f"{BASE_URL}/api/website-admin/collection-organizer/unassign",
            headers=self.headers,
            json={
                "supplier": self.supplier,
                "series": test_series,
                "main_category": "Tiles",
                "sub_categories": ["Clearance"]
            }
        )
    
    def test_unassign_endpoint_still_works(self):
        """Test that unassign endpoint still works for removing individual badges"""
        series_res = requests.get(
            f"{BASE_URL}/api/website-admin/collection-organizer/series?supplier={self.supplier}",
            headers=self.headers
        )
        series_list = series_res.json().get("series", [])
        
        if not series_list:
            pytest.skip("No series available")
        
        test_series = series_list[0]["name"]
        
        # First assign
        requests.post(
            f"{BASE_URL}/api/website-admin/collection-organizer/bulk-assign",
            headers=self.headers,
            json={
                "supplier": self.supplier,
                "series_names": [test_series],
                "targets": [
                    {"group_slug": "tiles", "main_category": "Tiles", "sub_categories": ["Wall Tiles"]}
                ]
            }
        )
        
        # Then unassign
        response = requests.post(
            f"{BASE_URL}/api/website-admin/collection-organizer/unassign",
            headers=self.headers,
            json={
                "supplier": self.supplier,
                "series": test_series,
                "main_category": "Tiles",
                "sub_categories": ["Wall Tiles"]
            }
        )
        assert response.status_code == 200
        print(f"PASS: Unassign endpoint still works for removing individual badges")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

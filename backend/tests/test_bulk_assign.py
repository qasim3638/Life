"""
Test Bulk Assign Feature for Collection Organizer
Tests the new bulk-assign endpoint and related functionality
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBulkAssignFeature:
    """Tests for the bulk assign feature in Collection Organizer"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.token = self._get_auth_token()
        self.headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }
        self.supplier = "Plus39"  # Known supplier with series
        
    def _get_auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "admin123"
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Authentication failed")
    
    # ============ BULK ASSIGN ENDPOINT TESTS ============
    
    def test_bulk_assign_endpoint_exists(self):
        """Test that bulk-assign endpoint exists and responds"""
        # Test with empty body to check endpoint exists
        response = requests.post(
            f"{BASE_URL}/api/website-admin/collection-organizer/bulk-assign",
            headers=self.headers,
            json={}
        )
        # Should return 400 for missing required fields, not 404
        assert response.status_code == 400, f"Expected 400 for missing fields, got {response.status_code}"
        data = response.json()
        assert "detail" in data
        print(f"PASS: Bulk assign endpoint exists, returns validation error for empty body")
    
    def test_bulk_assign_requires_supplier(self):
        """Test that bulk-assign requires supplier field"""
        response = requests.post(
            f"{BASE_URL}/api/website-admin/collection-organizer/bulk-assign",
            headers=self.headers,
            json={
                "series_names": ["Artisan"],
                "group_slug": "tiles",
                "main_category": "Tiles"
            }
        )
        assert response.status_code == 400
        assert "supplier" in response.json().get("detail", "").lower() or "required" in response.json().get("detail", "").lower()
        print(f"PASS: Bulk assign validates supplier is required")
    
    def test_bulk_assign_requires_series_names(self):
        """Test that bulk-assign requires series_names array"""
        response = requests.post(
            f"{BASE_URL}/api/website-admin/collection-organizer/bulk-assign",
            headers=self.headers,
            json={
                "supplier": self.supplier,
                "group_slug": "tiles",
                "main_category": "Tiles"
            }
        )
        assert response.status_code == 400
        print(f"PASS: Bulk assign validates series_names is required")
    
    def test_bulk_assign_requires_group_slug(self):
        """Test that bulk-assign requires group_slug"""
        response = requests.post(
            f"{BASE_URL}/api/website-admin/collection-organizer/bulk-assign",
            headers=self.headers,
            json={
                "supplier": self.supplier,
                "series_names": ["Artisan"],
                "main_category": "Tiles"
            }
        )
        assert response.status_code == 400
        print(f"PASS: Bulk assign validates group_slug is required")
    
    def test_bulk_assign_requires_main_category(self):
        """Test that bulk-assign requires main_category"""
        response = requests.post(
            f"{BASE_URL}/api/website-admin/collection-organizer/bulk-assign",
            headers=self.headers,
            json={
                "supplier": self.supplier,
                "series_names": ["Artisan"],
                "group_slug": "tiles"
            }
        )
        assert response.status_code == 400
        print(f"PASS: Bulk assign validates main_category is required")
    
    def test_bulk_assign_single_series(self):
        """Test bulk assign with a single series"""
        # First get available series
        series_res = requests.get(
            f"{BASE_URL}/api/website-admin/collection-organizer/series?supplier={self.supplier}",
            headers=self.headers
        )
        assert series_res.status_code == 200
        series_data = series_res.json()
        series_list = series_data.get("series", [])
        
        if not series_list:
            pytest.skip("No series available for testing")
        
        test_series = series_list[0]["name"]
        
        # Perform bulk assign with single series
        response = requests.post(
            f"{BASE_URL}/api/website-admin/collection-organizer/bulk-assign",
            headers=self.headers,
            json={
                "supplier": self.supplier,
                "series_names": [test_series],
                "group_slug": "tiles",
                "main_category": "Tiles",
                "sub_categories": ["Wall Tiles"]
            }
        )
        assert response.status_code == 200, f"Bulk assign failed: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert data.get("success") == True
        assert "message" in data
        assert "total_products_updated" in data
        assert "details" in data
        assert len(data["details"]) == 1
        assert data["details"][0]["series"] == test_series
        
        print(f"PASS: Bulk assign single series '{test_series}' - {data['total_products_updated']} products updated")
        
        # Cleanup - unassign
        self._cleanup_assignment(test_series, "Tiles", "Wall Tiles")
    
    def test_bulk_assign_multiple_series(self):
        """Test bulk assign with multiple series at once"""
        # Get available series
        series_res = requests.get(
            f"{BASE_URL}/api/website-admin/collection-organizer/series?supplier={self.supplier}",
            headers=self.headers
        )
        assert series_res.status_code == 200
        series_list = series_res.json().get("series", [])
        
        if len(series_list) < 2:
            pytest.skip("Need at least 2 series for this test")
        
        test_series = [s["name"] for s in series_list[:2]]
        
        # Perform bulk assign with multiple series
        response = requests.post(
            f"{BASE_URL}/api/website-admin/collection-organizer/bulk-assign",
            headers=self.headers,
            json={
                "supplier": self.supplier,
                "series_names": test_series,
                "group_slug": "tiles",
                "main_category": "Tiles",
                "sub_categories": ["Floor Tiles"]
            }
        )
        assert response.status_code == 200, f"Bulk assign failed: {response.text}"
        data = response.json()
        
        # Validate response
        assert data.get("success") == True
        assert len(data["details"]) == 2
        assert data["details"][0]["series"] in test_series
        assert data["details"][1]["series"] in test_series
        
        print(f"PASS: Bulk assign multiple series {test_series} - {data['total_products_updated']} total products updated")
        
        # Cleanup
        for series_name in test_series:
            self._cleanup_assignment(series_name, "Tiles", "Floor Tiles")
    
    def test_bulk_assign_to_group_level(self):
        """Test bulk assign to group level (no sub_categories)"""
        series_res = requests.get(
            f"{BASE_URL}/api/website-admin/collection-organizer/series?supplier={self.supplier}",
            headers=self.headers
        )
        assert series_res.status_code == 200
        series_list = series_res.json().get("series", [])
        
        if not series_list:
            pytest.skip("No series available")
        
        test_series = series_list[0]["name"]
        
        # Assign to group level (empty sub_categories)
        response = requests.post(
            f"{BASE_URL}/api/website-admin/collection-organizer/bulk-assign",
            headers=self.headers,
            json={
                "supplier": self.supplier,
                "series_names": [test_series],
                "group_slug": "materials",
                "main_category": "Materials",
                "sub_categories": []
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        
        print(f"PASS: Bulk assign to group level (Materials) - {data['total_products_updated']} products updated")
        
        # Cleanup
        self._cleanup_assignment(test_series, "Materials")
    
    def test_bulk_assign_verifies_assignment(self):
        """Test that bulk assign actually updates the series data"""
        series_res = requests.get(
            f"{BASE_URL}/api/website-admin/collection-organizer/series?supplier={self.supplier}",
            headers=self.headers
        )
        series_list = series_res.json().get("series", [])
        
        if not series_list:
            pytest.skip("No series available")
        
        test_series = series_list[0]["name"]
        
        # Perform bulk assign
        response = requests.post(
            f"{BASE_URL}/api/website-admin/collection-organizer/bulk-assign",
            headers=self.headers,
            json={
                "supplier": self.supplier,
                "series_names": [test_series],
                "group_slug": "tiles",
                "main_category": "Tiles",
                "sub_categories": ["Outdoor Tiles"]
            }
        )
        assert response.status_code == 200
        
        # Verify by fetching series again
        verify_res = requests.get(
            f"{BASE_URL}/api/website-admin/collection-organizer/series?supplier={self.supplier}",
            headers=self.headers
        )
        assert verify_res.status_code == 200
        updated_series = verify_res.json().get("series", [])
        
        # Find the test series and check its assignments
        found = False
        for s in updated_series:
            if s["name"] == test_series:
                found = True
                assert "Outdoor Tiles" in s.get("sub_categories", []), f"Expected 'Outdoor Tiles' in sub_categories, got {s.get('sub_categories')}"
                print(f"PASS: Verified assignment - {test_series} now has sub_categories: {s.get('sub_categories')}")
                break
        
        assert found, f"Series {test_series} not found after assignment"
        
        # Cleanup
        self._cleanup_assignment(test_series, "Tiles", "Outdoor Tiles")
    
    def test_bulk_assign_all_four_series(self):
        """Test bulk assign with all 4 Plus39 series (Travertine, Burlington, Artisan, Moonlight)"""
        # Get all series
        series_res = requests.get(
            f"{BASE_URL}/api/website-admin/collection-organizer/series?supplier={self.supplier}",
            headers=self.headers
        )
        assert series_res.status_code == 200
        series_list = series_res.json().get("series", [])
        
        all_series_names = [s["name"] for s in series_list]
        print(f"Available series: {all_series_names}")
        
        if len(all_series_names) < 4:
            pytest.skip(f"Expected 4 series, found {len(all_series_names)}")
        
        # Bulk assign all series
        response = requests.post(
            f"{BASE_URL}/api/website-admin/collection-organizer/bulk-assign",
            headers=self.headers,
            json={
                "supplier": self.supplier,
                "series_names": all_series_names,
                "group_slug": "tiles",
                "main_category": "Tiles",
                "sub_categories": ["Mosaic Tiles"]
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("success") == True
        assert len(data["details"]) == len(all_series_names)
        
        print(f"PASS: Bulk assigned all {len(all_series_names)} series to Mosaic Tiles - {data['total_products_updated']} products updated")
        
        # Cleanup all
        for series_name in all_series_names:
            self._cleanup_assignment(series_name, "Tiles", "Mosaic Tiles")
    
    def test_bulk_assign_empty_series_array(self):
        """Test bulk assign with empty series_names array"""
        response = requests.post(
            f"{BASE_URL}/api/website-admin/collection-organizer/bulk-assign",
            headers=self.headers,
            json={
                "supplier": self.supplier,
                "series_names": [],
                "group_slug": "tiles",
                "main_category": "Tiles"
            }
        )
        # Should return 400 for empty array
        assert response.status_code == 400
        print(f"PASS: Bulk assign rejects empty series_names array")
    
    # ============ HELPER METHODS ============
    
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


class TestExistingCollectionOrganizerEndpoints:
    """Verify existing endpoints still work alongside bulk assign"""
    
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
    
    def test_suppliers_endpoint(self):
        """Test suppliers endpoint still works"""
        response = requests.get(
            f"{BASE_URL}/api/website-admin/collection-organizer/suppliers",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "suppliers" in data
        print(f"PASS: Suppliers endpoint returns {len(data['suppliers'])} suppliers")
    
    def test_series_endpoint(self):
        """Test series endpoint still works"""
        response = requests.get(
            f"{BASE_URL}/api/website-admin/collection-organizer/series?supplier={self.supplier}",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "series" in data
        print(f"PASS: Series endpoint returns {len(data['series'])} series for {self.supplier}")
    
    def test_category_tree_endpoint(self):
        """Test category tree endpoint still works"""
        response = requests.get(
            f"{BASE_URL}/api/website-admin/collection-organizer/category-tree",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "groups" in data
        print(f"PASS: Category tree endpoint returns {len(data['groups'])} groups")
    
    def test_single_assign_still_works(self):
        """Test that single assign endpoint still works"""
        # Get a series
        series_res = requests.get(
            f"{BASE_URL}/api/website-admin/collection-organizer/series?supplier={self.supplier}",
            headers=self.headers
        )
        series_list = series_res.json().get("series", [])
        
        if not series_list:
            pytest.skip("No series available")
        
        test_series = series_list[0]["name"]
        
        # Single assign
        response = requests.post(
            f"{BASE_URL}/api/website-admin/collection-organizer/assign",
            headers=self.headers,
            json={
                "supplier": self.supplier,
                "series": test_series,
                "group_slug": "tiles",
                "main_category": "Tiles",
                "sub_categories": ["Kitchen Tiles"]
            }
        )
        assert response.status_code == 200
        print(f"PASS: Single assign endpoint still works")
        
        # Cleanup
        requests.post(
            f"{BASE_URL}/api/website-admin/collection-organizer/unassign",
            headers=self.headers,
            json={
                "supplier": self.supplier,
                "series": test_series,
                "main_category": "Tiles",
                "sub_categories": ["Kitchen Tiles"]
            }
        )
    
    def test_unassign_still_works(self):
        """Test that unassign endpoint still works"""
        # First assign something
        series_res = requests.get(
            f"{BASE_URL}/api/website-admin/collection-organizer/series?supplier={self.supplier}",
            headers=self.headers
        )
        series_list = series_res.json().get("series", [])
        
        if not series_list:
            pytest.skip("No series available")
        
        test_series = series_list[0]["name"]
        
        # Assign
        requests.post(
            f"{BASE_URL}/api/website-admin/collection-organizer/assign",
            headers=self.headers,
            json={
                "supplier": self.supplier,
                "series": test_series,
                "group_slug": "tiles",
                "main_category": "Tiles",
                "sub_categories": ["Bathroom Tiles"]
            }
        )
        
        # Unassign
        response = requests.post(
            f"{BASE_URL}/api/website-admin/collection-organizer/unassign",
            headers=self.headers,
            json={
                "supplier": self.supplier,
                "series": test_series,
                "main_category": "Tiles",
                "sub_categories": ["Bathroom Tiles"]
            }
        )
        assert response.status_code == 200
        print(f"PASS: Unassign endpoint still works")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

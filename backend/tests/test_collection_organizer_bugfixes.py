"""
Test Collection Organizer Bugfixes - Iteration 56
Tests for 4 user-reported bugs/improvements:
1. Show product display names on series cards
2. Left panel should scroll independently (viewport height layout)
3. Filter category groups to only show relevant ones for selected supplier
4. Fix crash when selecting LEPORCE supplier (null series name crash)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestCollectionOrganizerBugfixes:
    """Tests for the 4 bugfixes in Collection Organizer"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with auth"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login to get token
        login_res = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "admin123"
        })
        if login_res.status_code == 200:
            token = login_res.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        yield
    
    # ========== BUG 1: Product names on series cards ==========
    
    def test_series_endpoint_returns_product_names_array(self):
        """GET /api/website-admin/collection-organizer/series?supplier=Plus39 returns product_names array"""
        res = self.session.get(f"{BASE_URL}/api/website-admin/collection-organizer/series?supplier=Plus39")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert "series" in data, "Response should have 'series' key"
        
        # Check that at least one series has product_names
        series_with_names = [s for s in data["series"] if s.get("product_names")]
        assert len(series_with_names) > 0, "At least one series should have product_names"
        
        # Verify product_names is an array
        for s in series_with_names:
            assert isinstance(s["product_names"], list), f"product_names should be a list, got {type(s['product_names'])}"
            # Verify names are actual strings (not None)
            for name in s["product_names"]:
                assert name is not None, "product_names should not contain None values"
                assert isinstance(name, str), f"Each product name should be a string, got {type(name)}"
    
    def test_product_names_contain_actual_display_names(self):
        """Product names should be actual display names like 'Travertine Beige 60x120'"""
        res = self.session.get(f"{BASE_URL}/api/website-admin/collection-organizer/series?supplier=Plus39")
        assert res.status_code == 200
        data = res.json()
        
        # Find a series with product names
        for s in data["series"]:
            if s.get("product_names") and len(s["product_names"]) > 0:
                # Check that names look like product names (not empty, not just numbers)
                for name in s["product_names"]:
                    assert len(name) > 2, f"Product name '{name}' seems too short"
                    # Should contain letters (not just numbers/symbols)
                    assert any(c.isalpha() for c in name), f"Product name '{name}' should contain letters"
                print(f"Series '{s['name']}' has product names: {s['product_names'][:3]}")
                return
        
        pytest.skip("No series with product names found to verify")
    
    # ========== BUG 2: Relevant groups filtering ==========
    
    def test_series_endpoint_returns_relevant_groups(self):
        """GET /api/website-admin/collection-organizer/series returns relevant_groups field"""
        res = self.session.get(f"{BASE_URL}/api/website-admin/collection-organizer/series?supplier=Plus39")
        assert res.status_code == 200
        data = res.json()
        
        assert "relevant_groups" in data, "Response should have 'relevant_groups' key"
        assert isinstance(data["relevant_groups"], list), "relevant_groups should be a list"
        print(f"Plus39 relevant_groups: {data['relevant_groups']}")
    
    def test_series_endpoint_returns_ungrouped_count(self):
        """GET /api/website-admin/collection-organizer/series returns ungrouped_count field"""
        res = self.session.get(f"{BASE_URL}/api/website-admin/collection-organizer/series?supplier=Plus39")
        assert res.status_code == 200
        data = res.json()
        
        assert "ungrouped_count" in data, "Response should have 'ungrouped_count' key"
        assert isinstance(data["ungrouped_count"], int), "ungrouped_count should be an integer"
        print(f"Plus39 ungrouped_count: {data['ungrouped_count']}")
    
    def test_relevant_groups_matches_supplier_product_groups(self):
        """relevant_groups should contain the product_group values from the supplier's products"""
        res = self.session.get(f"{BASE_URL}/api/website-admin/collection-organizer/series?supplier=Plus39")
        assert res.status_code == 200
        data = res.json()
        
        relevant_groups = data.get("relevant_groups", [])
        
        # Plus39 is a tile supplier, so should have 'tiles' in relevant_groups
        # (based on context from main agent)
        if len(relevant_groups) > 0:
            print(f"Relevant groups for Plus39: {relevant_groups}")
            # At minimum, verify it's not empty and contains valid slugs
            for group in relevant_groups:
                assert isinstance(group, str), f"Each group should be a string, got {type(group)}"
                assert len(group) > 0, "Group slug should not be empty"
    
    # ========== BUG 3: LEPORCE crash fix (null series handling) ==========
    
    def test_leporce_supplier_does_not_crash(self):
        """GET /api/website-admin/collection-organizer/series?supplier=LEPORCE should NOT crash"""
        res = self.session.get(f"{BASE_URL}/api/website-admin/collection-organizer/series?supplier=LEPORCE")
        
        # Should return 200, not 500
        assert res.status_code == 200, f"LEPORCE query should not crash. Got {res.status_code}: {res.text}"
        
        data = res.json()
        # Should return valid JSON structure
        assert "series" in data, "Response should have 'series' key"
        assert isinstance(data["series"], list), "series should be a list"
        
        # LEPORCE may not exist in dev, so series could be empty - that's OK
        print(f"LEPORCE series count: {len(data['series'])}")
    
    def test_unknown_supplier_returns_empty_series(self):
        """Unknown supplier should return empty series list, not crash"""
        res = self.session.get(f"{BASE_URL}/api/website-admin/collection-organizer/series?supplier=NONEXISTENT_SUPPLIER_XYZ")
        
        assert res.status_code == 200, f"Unknown supplier should return 200, got {res.status_code}"
        data = res.json()
        
        assert "series" in data
        assert data["series"] == [], "Unknown supplier should return empty series list"
        assert data.get("ungrouped_count", 0) == 0, "Unknown supplier should have 0 ungrouped"
    
    def test_null_series_excluded_from_results(self):
        """Series with null/empty names should be excluded from results (using $nin filter)"""
        res = self.session.get(f"{BASE_URL}/api/website-admin/collection-organizer/series?supplier=Plus39")
        assert res.status_code == 200
        data = res.json()
        
        # Verify no series has null or empty name
        for s in data["series"]:
            assert s.get("name") is not None, "Series name should not be None"
            assert s.get("name") != "", "Series name should not be empty string"
            assert len(s.get("name", "")) > 0, "Series name should have length > 0"
    
    # ========== Additional validation tests ==========
    
    def test_series_has_required_fields(self):
        """Each series should have all required fields for frontend display"""
        res = self.session.get(f"{BASE_URL}/api/website-admin/collection-organizer/series?supplier=Plus39")
        assert res.status_code == 200
        data = res.json()
        
        required_fields = ["name", "count", "product_names"]
        
        for s in data["series"]:
            for field in required_fields:
                assert field in s, f"Series should have '{field}' field"
    
    def test_product_names_limited_to_5(self):
        """product_names should be limited to 5 items (as per $slice in aggregation)"""
        res = self.session.get(f"{BASE_URL}/api/website-admin/collection-organizer/series?supplier=Plus39")
        assert res.status_code == 200
        data = res.json()
        
        for s in data["series"]:
            product_names = s.get("product_names", [])
            assert len(product_names) <= 5, f"product_names should have max 5 items, got {len(product_names)}"
    
    def test_suppliers_endpoint_works(self):
        """GET /api/website-admin/collection-organizer/suppliers should work"""
        res = self.session.get(f"{BASE_URL}/api/website-admin/collection-organizer/suppliers")
        assert res.status_code == 200
        data = res.json()
        
        assert "suppliers" in data
        assert isinstance(data["suppliers"], list)
        
        # Plus39 should be in the list
        supplier_names = [s["name"] for s in data["suppliers"]]
        assert "Plus39" in supplier_names, f"Plus39 should be in suppliers list. Got: {supplier_names}"
    
    def test_category_tree_endpoint_works(self):
        """GET /api/website-admin/collection-organizer/category-tree should work"""
        res = self.session.get(f"{BASE_URL}/api/website-admin/collection-organizer/category-tree")
        assert res.status_code == 200
        data = res.json()
        
        assert "groups" in data
        assert isinstance(data["groups"], list)
        
        # Should have at least one group (tiles)
        if len(data["groups"]) > 0:
            group = data["groups"][0]
            assert "name" in group
            assert "slug" in group
            print(f"First category group: {group['name']} ({group['slug']})")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

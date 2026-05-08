"""
Test Site Map & Link Manager API endpoints
Tests: GET /api/website-admin/sitemap - aggregates all pages with linked_from references
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestSitemapEndpoint:
    """Tests for GET /api/website-admin/sitemap endpoint"""
    
    def test_sitemap_returns_200(self):
        """Sitemap endpoint should return 200 OK"""
        response = requests.get(f"{BASE_URL}/api/website-admin/sitemap")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    def test_sitemap_returns_pages_array(self):
        """Sitemap should return pages array"""
        response = requests.get(f"{BASE_URL}/api/website-admin/sitemap")
        data = response.json()
        assert "pages" in data, "Response should contain 'pages' key"
        assert isinstance(data["pages"], list), "pages should be a list"
        assert len(data["pages"]) > 0, "pages should not be empty"
    
    def test_sitemap_returns_summary(self):
        """Sitemap should return summary with counts by type"""
        response = requests.get(f"{BASE_URL}/api/website-admin/sitemap")
        data = response.json()
        assert "summary" in data, "Response should contain 'summary' key"
        summary = data["summary"]
        # Check all expected types are present
        expected_types = ["shop", "collection", "product", "info", "category"]
        for t in expected_types:
            assert t in summary, f"Summary should contain '{t}' count"
            assert isinstance(summary[t], int), f"Summary[{t}] should be an integer"
    
    def test_sitemap_summary_matches_actual_counts(self):
        """Summary counts should match actual page counts by type"""
        response = requests.get(f"{BASE_URL}/api/website-admin/sitemap")
        data = response.json()
        pages = data["pages"]
        summary = data["summary"]
        
        # Count pages by type
        actual_counts = {}
        for page in pages:
            t = page["type"]
            actual_counts[t] = actual_counts.get(t, 0) + 1
        
        # Verify counts match
        for page_type, count in summary.items():
            assert actual_counts.get(page_type, 0) == count, \
                f"Summary {page_type}={count} doesn't match actual count {actual_counts.get(page_type, 0)}"
    
    def test_sitemap_page_structure(self):
        """Each page should have required fields: name, url, type, linked_from"""
        response = requests.get(f"{BASE_URL}/api/website-admin/sitemap")
        data = response.json()
        pages = data["pages"]
        
        for page in pages[:20]:  # Check first 20 pages
            assert "name" in page, f"Page missing 'name': {page}"
            assert "url" in page, f"Page missing 'url': {page}"
            assert "type" in page, f"Page missing 'type': {page}"
            assert "linked_from" in page, f"Page missing 'linked_from': {page}"
            assert isinstance(page["linked_from"], list), f"linked_from should be a list: {page}"
    
    def test_sitemap_has_shop_pages(self):
        """Sitemap should include static shop pages"""
        response = requests.get(f"{BASE_URL}/api/website-admin/sitemap")
        data = response.json()
        pages = data["pages"]
        
        shop_pages = [p for p in pages if p["type"] == "shop"]
        shop_names = [p["name"] for p in shop_pages]
        
        # Check for expected shop pages
        expected_shop = ["Homepage", "Cart", "Checkout", "Contact Us"]
        for name in expected_shop:
            assert name in shop_names, f"Missing shop page: {name}"
    
    def test_sitemap_has_collections(self):
        """Sitemap should include collection pages"""
        response = requests.get(f"{BASE_URL}/api/website-admin/sitemap")
        data = response.json()
        pages = data["pages"]
        
        collections = [p for p in pages if p["type"] == "collection"]
        assert len(collections) > 0, "Should have at least one collection"
        
        # Collections should have product_count
        for col in collections[:5]:
            assert "product_count" in col, f"Collection missing product_count: {col['name']}"
    
    def test_sitemap_has_products(self):
        """Sitemap should include product pages"""
        response = requests.get(f"{BASE_URL}/api/website-admin/sitemap")
        data = response.json()
        pages = data["pages"]
        
        products = [p for p in pages if p["type"] == "product"]
        assert len(products) > 0, "Should have at least one product"
        
        # Product URLs should start with /tiles/
        for prod in products[:5]:
            assert prod["url"].startswith("/tiles/"), f"Product URL should start with /tiles/: {prod['url']}"
    
    def test_sitemap_has_info_pages(self):
        """Sitemap should include info/CMS pages"""
        response = requests.get(f"{BASE_URL}/api/website-admin/sitemap")
        data = response.json()
        pages = data["pages"]
        
        info_pages = [p for p in pages if p["type"] == "info"]
        assert len(info_pages) > 0, "Should have at least one info page"
        
        # Info page URLs should start with /shop/info/
        for info in info_pages[:5]:
            assert info["url"].startswith("/shop/info/"), f"Info URL should start with /shop/info/: {info['url']}"
    
    def test_sitemap_has_categories(self):
        """Sitemap should include category pages"""
        response = requests.get(f"{BASE_URL}/api/website-admin/sitemap")
        data = response.json()
        pages = data["pages"]
        
        categories = [p for p in pages if p["type"] == "category"]
        assert len(categories) > 0, "Should have at least one category"
        
        # Category URLs should contain ?category=
        for cat in categories[:5]:
            assert "?category=" in cat["url"], f"Category URL should contain ?category=: {cat['url']}"
    
    def test_sitemap_linked_from_references(self):
        """Pages should have linked_from references showing where they're linked"""
        response = requests.get(f"{BASE_URL}/api/website-admin/sitemap")
        data = response.json()
        pages = data["pages"]
        
        # Find pages with linked_from references
        linked_pages = [p for p in pages if p.get("linked_from") and len(p["linked_from"]) > 0]
        assert len(linked_pages) > 0, "Should have at least some pages with linked_from references"
        
        # Check reference format
        for page in linked_pages[:5]:
            for ref in page["linked_from"]:
                assert isinstance(ref, str), f"linked_from reference should be string: {ref}"
                # References should indicate source (Nav:, Footer:, Homepage:)
                assert any(prefix in ref for prefix in ["Nav:", "Footer:", "Homepage:"]), \
                    f"Reference should have source prefix: {ref}"
    
    def test_sitemap_homepage_categories_badge(self):
        """Categories on homepage should have 'Homepage: Shop Categories' badge"""
        response = requests.get(f"{BASE_URL}/api/website-admin/sitemap")
        data = response.json()
        pages = data["pages"]
        
        categories = [p for p in pages if p["type"] == "category"]
        homepage_cats = [c for c in categories if any("Homepage" in ref for ref in c.get("linked_from", []))]
        
        # Should have some categories on homepage
        assert len(homepage_cats) > 0, "Should have at least one category on homepage"
        
        # Check for 'Homepage: Shop Categories' badge
        for cat in homepage_cats:
            has_shop_categories_badge = any("Shop Categories" in ref for ref in cat["linked_from"])
            assert has_shop_categories_badge, f"Homepage category should have 'Shop Categories' badge: {cat['name']}"
    
    def test_sitemap_total_products_count(self):
        """Sitemap should return total_products count"""
        response = requests.get(f"{BASE_URL}/api/website-admin/sitemap")
        data = response.json()
        
        assert "total_products" in data, "Response should contain 'total_products'"
        assert isinstance(data["total_products"], int), "total_products should be an integer"
        assert data["total_products"] > 0, "total_products should be greater than 0"
    
    def test_sitemap_total_collections_count(self):
        """Sitemap should return total_collections count"""
        response = requests.get(f"{BASE_URL}/api/website-admin/sitemap")
        data = response.json()
        
        assert "total_collections" in data, "Response should contain 'total_collections'"
        assert isinstance(data["total_collections"], int), "total_collections should be an integer"
        assert data["total_collections"] > 0, "total_collections should be greater than 0"


class TestNavigationItemEndpoint:
    """Tests for POST /api/website-admin/navigation/{menu_type}/item endpoint"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token for admin user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "qasim@tilestation.co.uk",
            "password": "Tilestation_9614"
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Authentication failed")
    
    def test_add_to_main_nav_works(self):
        """Adding to main nav should work (endpoint is public in current implementation)"""
        response = requests.post(f"{BASE_URL}/api/website-admin/navigation/main/item", json={
            "label": "TEST LINK",
            "link_type": "custom",
            "link_url": "/test",
            "is_active": True
        })
        # Note: This endpoint doesn't require auth in current implementation
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}"
    
    def test_add_to_main_nav_with_auth(self, auth_token):
        """Adding to main nav should work with auth"""
        response = requests.post(
            f"{BASE_URL}/api/website-admin/navigation/main/item",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "label": "TEST_SITEMAP_LINK",
                "link_type": "custom",
                "link_url": "/test-sitemap-link",
                "is_active": True,
                "highlight": False,
                "children": []
            }
        )
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}"


class TestFooterSettingsEndpoint:
    """Tests for footer settings endpoints used by Add to Footer action"""
    
    def test_get_footer_settings_public(self):
        """GET footer settings should be accessible without auth"""
        response = requests.get(f"{BASE_URL}/api/website-admin/footer-settings")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "settings" in data, "Response should contain 'settings'"
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token for admin user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "qasim@tilestation.co.uk",
            "password": "Tilestation_9614"
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Authentication failed")
    
    def test_save_footer_settings_works(self):
        """POST footer settings should work (endpoint is public in current implementation)"""
        # First get current settings
        get_res = requests.get(f"{BASE_URL}/api/website-admin/footer-settings")
        current_settings = get_res.json().get("settings", {})
        
        # Save same settings back (no change)
        response = requests.post(f"{BASE_URL}/api/website-admin/footer-settings", json={
            "settings": current_settings
        })
        # Note: This endpoint doesn't require auth in current implementation
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

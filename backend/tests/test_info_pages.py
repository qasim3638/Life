"""
Test Info Pages API endpoints
Tests for delivery, returns, faq, privacy, terms pages and slug aliases
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestInfoPagesAPI:
    """Test info pages endpoints - delivery, returns, faq, privacy, terms"""
    
    def test_get_delivery_page(self):
        """GET /api/website-admin/info-pages/delivery returns 200 with valid page data"""
        response = requests.get(f"{BASE_URL}/api/website-admin/info-pages/delivery")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "page" in data, "Response should contain 'page' key"
        page = data["page"]
        assert page is not None, "Page should not be None"
        assert page.get("title") == "Delivery Information", f"Expected 'Delivery Information', got {page.get('title')}"
        assert page.get("slug") == "delivery", f"Expected slug 'delivery', got {page.get('slug')}"
        assert "sections" in page, "Page should have sections"
        assert len(page["sections"]) > 0, "Page should have at least one section"
        print(f"✓ Delivery page has {len(page['sections'])} sections")
    
    def test_get_returns_page(self):
        """GET /api/website-admin/info-pages/returns returns 200 with valid page data"""
        response = requests.get(f"{BASE_URL}/api/website-admin/info-pages/returns")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "page" in data
        page = data["page"]
        assert page is not None, "Page should not be None"
        assert page.get("title") == "Returns & Refunds", f"Expected 'Returns & Refunds', got {page.get('title')}"
        assert page.get("slug") == "returns"
        assert "sections" in page
        print(f"✓ Returns page has {len(page['sections'])} sections")
    
    def test_get_faq_page(self):
        """GET /api/website-admin/info-pages/faq returns 200 with valid page data"""
        response = requests.get(f"{BASE_URL}/api/website-admin/info-pages/faq")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "page" in data
        page = data["page"]
        assert page is not None, "Page should not be None"
        assert page.get("title") == "Frequently Asked Questions", f"Expected 'Frequently Asked Questions', got {page.get('title')}"
        assert page.get("slug") == "faq"
        assert "sections" in page
        # Check that FAQ content has bold markdown text
        has_bold = False
        for section in page.get("sections", []):
            content = section.get("content", "")
            if "**" in content:
                has_bold = True
                break
        assert has_bold, "FAQ page should contain bold markdown text (**text**)"
        print(f"✓ FAQ page has {len(page['sections'])} sections with bold markdown")
    
    def test_get_privacy_page(self):
        """GET /api/website-admin/info-pages/privacy returns 200 with valid page data"""
        response = requests.get(f"{BASE_URL}/api/website-admin/info-pages/privacy")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "page" in data
        page = data["page"]
        assert page is not None, "Page should not be None"
        assert page.get("title") == "Privacy Policy", f"Expected 'Privacy Policy', got {page.get('title')}"
        assert page.get("slug") == "privacy"
        assert "sections" in page
        print(f"✓ Privacy page has {len(page['sections'])} sections")
    
    def test_get_terms_page(self):
        """GET /api/website-admin/info-pages/terms returns 200 with valid page data"""
        response = requests.get(f"{BASE_URL}/api/website-admin/info-pages/terms")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "page" in data
        page = data["page"]
        assert page is not None, "Page should not be None"
        assert page.get("title") == "Terms & Conditions", f"Expected 'Terms & Conditions', got {page.get('title')}"
        assert page.get("slug") == "terms"
        assert "sections" in page
        print(f"✓ Terms page has {len(page['sections'])} sections")


class TestSlugAliases:
    """Test slug aliases work correctly"""
    
    def test_delivery_information_alias(self):
        """Slug alias: /delivery-information returns same as /delivery"""
        response = requests.get(f"{BASE_URL}/api/website-admin/info-pages/delivery-information")
        assert response.status_code == 200
        data = response.json()
        page = data.get("page")
        assert page is not None, "Page should not be None for alias"
        assert page.get("slug") == "delivery", f"Expected canonical slug 'delivery', got {page.get('slug')}"
        assert page.get("title") == "Delivery Information"
        print("✓ delivery-information alias works")
    
    def test_returns_and_refunds_alias(self):
        """Slug alias: /returns-and-refunds returns same as /returns"""
        response = requests.get(f"{BASE_URL}/api/website-admin/info-pages/returns-and-refunds")
        assert response.status_code == 200
        data = response.json()
        page = data.get("page")
        assert page is not None, "Page should not be None for alias"
        assert page.get("slug") == "returns", f"Expected canonical slug 'returns', got {page.get('slug')}"
        print("✓ returns-and-refunds alias works")
    
    def test_privacy_policy_alias(self):
        """Slug alias: /privacy-policy returns same as /privacy"""
        response = requests.get(f"{BASE_URL}/api/website-admin/info-pages/privacy-policy")
        assert response.status_code == 200
        data = response.json()
        page = data.get("page")
        assert page is not None, "Page should not be None for alias"
        assert page.get("slug") == "privacy", f"Expected canonical slug 'privacy', got {page.get('slug')}"
        print("✓ privacy-policy alias works")
    
    def test_terms_and_conditions_alias(self):
        """Slug alias: /terms-and-conditions returns same as /terms"""
        response = requests.get(f"{BASE_URL}/api/website-admin/info-pages/terms-and-conditions")
        assert response.status_code == 200
        data = response.json()
        page = data.get("page")
        assert page is not None, "Page should not be None for alias"
        assert page.get("slug") == "terms", f"Expected canonical slug 'terms', got {page.get('slug')}"
        print("✓ terms-and-conditions alias works")
    
    def test_faqs_alias(self):
        """Slug alias: /faqs returns same as /faq"""
        response = requests.get(f"{BASE_URL}/api/website-admin/info-pages/faqs")
        assert response.status_code == 200
        data = response.json()
        page = data.get("page")
        assert page is not None, "Page should not be None for alias"
        assert page.get("slug") == "faq", f"Expected canonical slug 'faq', got {page.get('slug')}"
        print("✓ faqs alias works")


class TestDeliveryPageContent:
    """Test delivery page has correct content structure"""
    
    def test_delivery_has_cards_section(self):
        """Delivery page should have cards section with icons"""
        response = requests.get(f"{BASE_URL}/api/website-admin/info-pages/delivery")
        data = response.json()
        page = data.get("page")
        
        cards_section = None
        for section in page.get("sections", []):
            if section.get("type") == "cards":
                cards_section = section
                break
        
        assert cards_section is not None, "Delivery page should have a cards section"
        assert "cards" in cards_section, "Cards section should have cards array"
        assert len(cards_section["cards"]) >= 4, f"Expected at least 4 cards, got {len(cards_section['cards'])}"
        
        # Check cards have required fields
        for card in cards_section["cards"]:
            assert "title" in card, "Card should have title"
            assert "description" in card, "Card should have description"
            assert "icon" in card, "Card should have icon"
        print(f"✓ Delivery page has {len(cards_section['cards'])} cards with icons")
    
    def test_delivery_has_table_section(self):
        """Delivery page should have table section with rates"""
        response = requests.get(f"{BASE_URL}/api/website-admin/info-pages/delivery")
        data = response.json()
        page = data.get("page")
        
        table_section = None
        for section in page.get("sections", []):
            if section.get("type") == "table":
                table_section = section
                break
        
        assert table_section is not None, "Delivery page should have a table section"
        assert "rows" in table_section, "Table section should have rows"
        assert len(table_section["rows"]) >= 3, f"Expected at least 3 rows, got {len(table_section['rows'])}"
        
        # Check rows have required fields
        for row in table_section["rows"]:
            assert "description" in row, "Row should have description"
            assert "price" in row, "Row should have price"
        print(f"✓ Delivery page has table with {len(table_section['rows'])} rows")


class TestAllInfoPagesEndpoint:
    """Test the get all info pages endpoint"""
    
    def test_get_all_info_pages(self):
        """GET /api/website-admin/info-pages returns list of all pages"""
        response = requests.get(f"{BASE_URL}/api/website-admin/info-pages")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "pages" in data, "Response should contain 'pages' key"
        pages = data["pages"]
        assert isinstance(pages, list), "Pages should be a list"
        print(f"✓ Got {len(pages)} info pages from /info-pages endpoint")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

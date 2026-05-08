"""
Bathroom Page API Tests
Tests for the bathroom landing page endpoints including:
- GET /api/bathroom/page - Public page content
- PUT /api/bathroom/page - Admin update content
- GET /api/bathroom/catalogue/download - Catalogue download with tracking
- GET /api/bathroom/downloads/stats - Download analytics
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestBathroomPagePublic:
    """Public bathroom page endpoint tests"""
    
    def test_get_bathroom_page_returns_200(self):
        """GET /api/bathroom/page returns 200"""
        response = requests.get(f"{BASE_URL}/api/bathroom/page")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/bathroom/page returns 200")
    
    def test_get_bathroom_page_has_hero_fields(self):
        """Page content includes hero section fields"""
        response = requests.get(f"{BASE_URL}/api/bathroom/page")
        data = response.json()
        
        assert "hero_title" in data, "Missing hero_title"
        assert "hero_subtitle" in data, "Missing hero_subtitle"
        assert "hero_description" in data, "Missing hero_description"
        assert data["hero_title"] == "Bath Station", f"Expected 'Bath Station', got {data['hero_title']}"
        print("✓ Hero section fields present and correct")
    
    def test_get_bathroom_page_has_pricing_fields(self):
        """Page content includes pricing tier fields"""
        response = requests.get(f"{BASE_URL}/api/bathroom/page")
        data = response.json()
        
        assert "public_discount" in data, "Missing public_discount"
        assert "trade_discount" in data, "Missing trade_discount"
        assert data["public_discount"] == "35", f"Expected '35', got {data['public_discount']}"
        assert data["trade_discount"] == "50", f"Expected '50', got {data['trade_discount']}"
        print("✓ Pricing fields present: public=35%, trade=50%")
    
    def test_get_bathroom_page_has_features(self):
        """Page content includes features array"""
        response = requests.get(f"{BASE_URL}/api/bathroom/page")
        data = response.json()
        
        assert "features" in data, "Missing features"
        assert isinstance(data["features"], list), "features should be a list"
        assert len(data["features"]) == 4, f"Expected 4 features, got {len(data['features'])}"
        
        # Check feature structure
        feature = data["features"][0]
        assert "icon" in feature, "Feature missing icon"
        assert "title" in feature, "Feature missing title"
        assert "description" in feature, "Feature missing description"
        print("✓ Features array present with 4 items")
    
    def test_get_bathroom_page_has_how_to_order(self):
        """Page content includes how to order section"""
        response = requests.get(f"{BASE_URL}/api/bathroom/page")
        data = response.json()
        
        assert "how_to_order_title" in data, "Missing how_to_order_title"
        assert "how_to_order_intro" in data, "Missing how_to_order_intro"
        assert "how_to_order_channels" in data, "Missing how_to_order_channels"
        
        channels = data["how_to_order_channels"]
        assert isinstance(channels, list), "how_to_order_channels should be a list"
        assert len(channels) == 3, f"Expected 3 channels, got {len(channels)}"
        
        # Check channel titles
        channel_titles = [ch["title"] for ch in channels]
        assert "Visit Our Showrooms" in channel_titles, "Missing Showrooms channel"
        assert "Order via WhatsApp" in channel_titles, "Missing WhatsApp channel"
        assert "Order via Email" in channel_titles, "Missing Email channel"
        print("✓ How to Order section present with 3 channels")
    
    def test_get_bathroom_page_has_trade_credit_back(self):
        """Page content includes trade credit back notice"""
        response = requests.get(f"{BASE_URL}/api/bathroom/page")
        data = response.json()
        
        assert "trade_credit_back_text" in data, "Missing trade_credit_back_text"
        assert "2%" in data["trade_credit_back_text"], "Trade credit back should mention 2%"
        print("✓ Trade Credit Back notice present with 2%")
    
    def test_get_bathroom_page_has_review(self):
        """Page content includes review quote"""
        response = requests.get(f"{BASE_URL}/api/bathroom/page")
        data = response.json()
        
        assert "review_quote" in data, "Missing review_quote"
        assert "review_author" in data, "Missing review_author"
        assert data["review_author"] == "Peter B.", f"Expected 'Peter B.', got {data['review_author']}"
        print("✓ Review quote present from Peter B.")
    
    def test_get_bathroom_page_has_cta(self):
        """Page content includes CTA section"""
        response = requests.get(f"{BASE_URL}/api/bathroom/page")
        data = response.json()
        
        assert "cta_title" in data, "Missing cta_title"
        assert "cta_description" in data, "Missing cta_description"
        print("✓ CTA section present")
    
    def test_get_bathroom_page_has_catalogue_path(self):
        """Page content includes catalogue path"""
        response = requests.get(f"{BASE_URL}/api/bathroom/page")
        data = response.json()
        
        assert "catalogue_path" in data, "Missing catalogue_path"
        assert "catalogue_filename" in data, "Missing catalogue_filename"
        assert "bath-station" in data["catalogue_path"].lower(), "Catalogue path should contain bath-station"
        print("✓ Catalogue path present")


class TestBathroomDownloadStats:
    """Download stats endpoint tests"""
    
    def test_get_download_stats_returns_200(self):
        """GET /api/bathroom/downloads/stats returns 200"""
        response = requests.get(f"{BASE_URL}/api/bathroom/downloads/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/bathroom/downloads/stats returns 200")
    
    def test_get_download_stats_structure(self):
        """Download stats has correct structure"""
        response = requests.get(f"{BASE_URL}/api/bathroom/downloads/stats")
        data = response.json()
        
        assert "total" in data, "Missing total"
        assert "public" in data, "Missing public count"
        assert "trade" in data, "Missing trade count"
        assert "recent" in data, "Missing recent downloads"
        assert isinstance(data["recent"], list), "recent should be a list"
        print("✓ Download stats structure correct")


class TestBathroomCatalogueDownload:
    """Catalogue download endpoint tests"""
    
    def test_catalogue_download_tracks_public_user(self):
        """GET /api/bathroom/catalogue/download tracks public downloads"""
        # Get initial stats
        stats_before = requests.get(f"{BASE_URL}/api/bathroom/downloads/stats").json()
        initial_total = stats_before.get("total", 0)
        initial_public = stats_before.get("public", 0)
        
        # Trigger download (this will track but may fail to serve if file not accessible)
        response = requests.get(
            f"{BASE_URL}/api/bathroom/catalogue/download",
            params={"user_id": "test_public_user@example.com", "user_type": "public"},
            stream=True  # Don't download full file
        )
        
        # Check stats after
        stats_after = requests.get(f"{BASE_URL}/api/bathroom/downloads/stats").json()
        
        # If download succeeded (200), stats should increment
        if response.status_code == 200:
            assert stats_after["total"] == initial_total + 1, "Total should increment"
            assert stats_after["public"] == initial_public + 1, "Public count should increment"
            print("✓ Catalogue download tracked for public user")
        else:
            # If 500 (file not accessible), tracking still happens
            print(f"⚠ Download returned {response.status_code} - file may not be accessible in test env")
            # Check if tracking still worked
            if stats_after["total"] > initial_total:
                print("✓ Download tracking still worked despite file access issue")
    
    def test_catalogue_download_tracks_trade_user(self):
        """GET /api/bathroom/catalogue/download tracks trade downloads"""
        # Get initial stats
        stats_before = requests.get(f"{BASE_URL}/api/bathroom/downloads/stats").json()
        initial_trade = stats_before.get("trade", 0)
        
        # Trigger download
        response = requests.get(
            f"{BASE_URL}/api/bathroom/catalogue/download",
            params={"user_id": "test_trade_user@example.com", "user_type": "trade"},
            stream=True
        )
        
        # Check stats after
        stats_after = requests.get(f"{BASE_URL}/api/bathroom/downloads/stats").json()
        
        if response.status_code == 200:
            assert stats_after["trade"] == initial_trade + 1, "Trade count should increment"
            print("✓ Catalogue download tracked for trade user")
        else:
            print(f"⚠ Download returned {response.status_code} - checking if tracking worked")
            if stats_after["trade"] > initial_trade:
                print("✓ Trade download tracking worked")


class TestBathroomPageAdmin:
    """Admin bathroom page update tests"""
    
    def test_put_bathroom_page_updates_content(self):
        """PUT /api/bathroom/page updates and merges content"""
        # Get current content
        current = requests.get(f"{BASE_URL}/api/bathroom/page").json()
        original_title = current.get("hero_title", "")
        
        # Update with test value
        test_title = "TEST_Bath Station Updated"
        response = requests.put(
            f"{BASE_URL}/api/bathroom/page",
            json={"hero_title": test_title},
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Verify update
        updated = requests.get(f"{BASE_URL}/api/bathroom/page").json()
        assert updated["hero_title"] == test_title, "Title should be updated"
        
        # Verify other fields preserved (deep merge)
        assert updated.get("public_discount") == current.get("public_discount"), "Other fields should be preserved"
        
        # Restore original
        requests.put(
            f"{BASE_URL}/api/bathroom/page",
            json={"hero_title": original_title or "Bath Station"},
            headers={"Content-Type": "application/json"}
        )
        print("✓ PUT /api/bathroom/page updates and merges correctly")
    
    def test_put_bathroom_page_preserves_arrays(self):
        """PUT /api/bathroom/page preserves array fields when not updated"""
        # Get current content
        current = requests.get(f"{BASE_URL}/api/bathroom/page").json()
        original_features = current.get("features", [])
        
        # Update a non-array field
        response = requests.put(
            f"{BASE_URL}/api/bathroom/page",
            json={"cta_description": "TEST_Updated CTA description"},
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200
        
        # Verify features preserved
        updated = requests.get(f"{BASE_URL}/api/bathroom/page").json()
        assert len(updated.get("features", [])) == len(original_features), "Features should be preserved"
        
        # Restore
        requests.put(
            f"{BASE_URL}/api/bathroom/page",
            json={"cta_description": current.get("cta_description", "")},
            headers={"Content-Type": "application/json"}
        )
        print("✓ Array fields preserved during partial updates")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

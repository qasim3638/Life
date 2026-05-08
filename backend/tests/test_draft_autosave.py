"""
Test suite for Bulk Edit Draft Auto-save endpoints
Tests: GET /api/bulk-edit-tools/draft, POST /api/bulk-edit-tools/draft, DELETE /api/bulk-edit-tools/draft
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestDraftAutoSave:
    """Tests for draft auto-save functionality"""
    
    @pytest.fixture(autouse=True)
    def cleanup_draft(self):
        """Clean up test draft before and after each test"""
        # Cleanup before test
        requests.delete(f"{BASE_URL}/api/bulk-edit-tools/draft?user=admin")
        yield
        # Cleanup after test
        requests.delete(f"{BASE_URL}/api/bulk-edit-tools/draft?user=admin")
    
    def test_get_draft_returns_null_when_no_draft(self):
        """GET /api/bulk-edit-tools/draft?user=admin returns null when no draft exists"""
        response = requests.get(f"{BASE_URL}/api/bulk-edit-tools/draft?user=admin")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data is None, f"Expected null/None when no draft exists, got {data}"
        print("PASS: GET draft returns null when no draft exists")
    
    def test_post_draft_saves_draft(self):
        """POST /api/bulk-edit-tools/draft saves draft with selections, product_group, supplier"""
        draft_payload = {
            "user": "admin",
            "selections": {
                "Material": "Porcelain",
                "Finish": "Matt",
                "Color": "White"
            },
            "selected_products": ["SKU001", "SKU002"],
            "product_group": "tiles",
            "supplier": "Canopy"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/bulk-edit-tools/draft",
            json=draft_payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("status") == "saved", f"Expected status 'saved', got {data}"
        assert "updated_at" in data, "Response should include updated_at timestamp"
        print("PASS: POST draft saves draft successfully")
    
    def test_get_draft_returns_saved_draft(self):
        """GET /api/bulk-edit-tools/draft?user=admin returns saved draft with selections"""
        # First save a draft
        draft_payload = {
            "user": "admin",
            "selections": {
                "Material": "Ceramic",
                "Finish": "Gloss",
                "Size": "60x60"
            },
            "selected_products": ["SKU003", "SKU004", "SKU005"],
            "product_group": "tiles",
            "supplier": "TestSupplier"
        }
        
        save_response = requests.post(
            f"{BASE_URL}/api/bulk-edit-tools/draft",
            json=draft_payload
        )
        assert save_response.status_code == 200
        
        # Now retrieve the draft
        get_response = requests.get(f"{BASE_URL}/api/bulk-edit-tools/draft?user=admin")
        assert get_response.status_code == 200, f"Expected 200, got {get_response.status_code}"
        
        draft = get_response.json()
        assert draft is not None, "Draft should not be null after saving"
        assert draft.get("user") == "admin", f"Expected user 'admin', got {draft.get('user')}"
        assert draft.get("selections") == draft_payload["selections"], "Selections should match"
        assert draft.get("product_group") == "tiles", "Product group should match"
        assert draft.get("supplier") == "TestSupplier", "Supplier should match"
        assert "updated_at" in draft, "Draft should have updated_at timestamp"
        print("PASS: GET draft returns saved draft with all fields")
    
    def test_post_draft_upserts_existing_draft(self):
        """POST /api/bulk-edit-tools/draft with same user updates existing draft (upsert)"""
        # Save initial draft
        initial_draft = {
            "user": "admin",
            "selections": {"Material": "Porcelain"},
            "product_group": "tiles",
            "supplier": "Supplier1"
        }
        
        response1 = requests.post(
            f"{BASE_URL}/api/bulk-edit-tools/draft",
            json=initial_draft
        )
        assert response1.status_code == 200
        
        # Update with new selections
        updated_draft = {
            "user": "admin",
            "selections": {"Material": "Ceramic", "Finish": "Matt", "Color": "Grey"},
            "product_group": "tiles",
            "supplier": "Supplier2"
        }
        
        response2 = requests.post(
            f"{BASE_URL}/api/bulk-edit-tools/draft",
            json=updated_draft
        )
        assert response2.status_code == 200
        
        # Verify the draft was updated (not duplicated)
        get_response = requests.get(f"{BASE_URL}/api/bulk-edit-tools/draft?user=admin")
        assert get_response.status_code == 200
        
        draft = get_response.json()
        assert draft is not None
        assert draft.get("selections") == updated_draft["selections"], "Selections should be updated"
        assert draft.get("supplier") == "Supplier2", "Supplier should be updated"
        print("PASS: POST draft upserts existing draft correctly")
    
    def test_delete_draft_clears_draft(self):
        """DELETE /api/bulk-edit-tools/draft?user=admin clears the draft"""
        # First save a draft
        draft_payload = {
            "user": "admin",
            "selections": {"Material": "Stone"},
            "product_group": "tiles",
            "supplier": "TestSupplier"
        }
        
        save_response = requests.post(
            f"{BASE_URL}/api/bulk-edit-tools/draft",
            json=draft_payload
        )
        assert save_response.status_code == 200
        
        # Verify draft exists
        get_response1 = requests.get(f"{BASE_URL}/api/bulk-edit-tools/draft?user=admin")
        assert get_response1.status_code == 200
        assert get_response1.json() is not None, "Draft should exist before delete"
        
        # Delete the draft
        delete_response = requests.delete(f"{BASE_URL}/api/bulk-edit-tools/draft?user=admin")
        assert delete_response.status_code == 200, f"Expected 200, got {delete_response.status_code}"
        data = delete_response.json()
        assert data.get("status") == "cleared", f"Expected status 'cleared', got {data}"
        
        # Verify draft is gone
        get_response2 = requests.get(f"{BASE_URL}/api/bulk-edit-tools/draft?user=admin")
        assert get_response2.status_code == 200
        assert get_response2.json() is None, "Draft should be null after delete"
        print("PASS: DELETE draft clears the draft successfully")
    
    def test_draft_with_per_attribute_scopes(self):
        """POST draft saves per_attribute_scopes field correctly"""
        draft_payload = {
            "user": "admin",
            "selections": {"Material": "Porcelain", "Finish": "Matt"},
            "per_attribute_scopes": {
                "Material": "all",
                "Finish": "selected"
            },
            "product_group": "tiles",
            "supplier": "Canopy"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/bulk-edit-tools/draft",
            json=draft_payload
        )
        assert response.status_code == 200
        
        # Verify per_attribute_scopes is saved
        get_response = requests.get(f"{BASE_URL}/api/bulk-edit-tools/draft?user=admin")
        assert get_response.status_code == 200
        draft = get_response.json()
        assert draft.get("per_attribute_scopes") == draft_payload["per_attribute_scopes"]
        print("PASS: Draft saves per_attribute_scopes correctly")
    
    def test_draft_different_users(self):
        """Drafts are isolated by user"""
        # Save draft for admin
        admin_draft = {
            "user": "admin",
            "selections": {"Material": "Porcelain"},
            "product_group": "tiles",
            "supplier": "AdminSupplier"
        }
        requests.post(f"{BASE_URL}/api/bulk-edit-tools/draft", json=admin_draft)
        
        # Save draft for different user
        other_draft = {
            "user": "other_user",
            "selections": {"Material": "Ceramic"},
            "product_group": "tiles",
            "supplier": "OtherSupplier"
        }
        requests.post(f"{BASE_URL}/api/bulk-edit-tools/draft", json=other_draft)
        
        # Verify admin draft is unchanged
        admin_response = requests.get(f"{BASE_URL}/api/bulk-edit-tools/draft?user=admin")
        assert admin_response.status_code == 200
        admin_data = admin_response.json()
        assert admin_data.get("selections", {}).get("Material") == "Porcelain"
        assert admin_data.get("supplier") == "AdminSupplier"
        
        # Verify other user draft
        other_response = requests.get(f"{BASE_URL}/api/bulk-edit-tools/draft?user=other_user")
        assert other_response.status_code == 200
        other_data = other_response.json()
        assert other_data.get("selections", {}).get("Material") == "Ceramic"
        assert other_data.get("supplier") == "OtherSupplier"
        
        # Cleanup other user draft
        requests.delete(f"{BASE_URL}/api/bulk-edit-tools/draft?user=other_user")
        print("PASS: Drafts are isolated by user")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

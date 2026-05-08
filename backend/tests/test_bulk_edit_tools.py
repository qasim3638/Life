"""
Test Bulk Edit Tools - Presets, History, Snapshot, and Undo endpoints
Tests for the 5 new features in Bulk Category Editor:
1. Save & Verify workflow
2. Dry Run / Preview Mode
3. Save History / Audit Log
4. Attribute Presets / Templates
5. Undo Last Bulk Edit
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestBulkEditPresets:
    """Tests for /api/bulk-edit-tools/presets endpoints"""
    
    created_preset_ids = []
    
    def test_get_presets_initially_empty_or_list(self):
        """GET /api/bulk-edit-tools/presets should return array"""
        response = requests.get(f"{BASE_URL}/api/bulk-edit-tools/presets")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"PASS: GET /presets returns list with {len(data)} presets")
    
    def test_create_preset(self):
        """POST /api/bulk-edit-tools/presets creates a preset"""
        preset_name = f"TEST_Preset_{uuid.uuid4().hex[:8]}"
        payload = {
            "name": preset_name,
            "description": "Test preset for automated testing",
            "selections": {
                "material": "Porcelain",
                "finish": "Matt",
                "rooms": ["Bathroom", "Kitchen"],
                "cat_wall_tiles": True
            },
            "product_group": "tiles"
        }
        response = requests.post(
            f"{BASE_URL}/api/bulk-edit-tools/presets",
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "id" in data, "Response should contain 'id'"
        assert data.get("name") == preset_name, f"Expected name '{preset_name}', got '{data.get('name')}'"
        assert data.get("status") == "saved", f"Expected status 'saved', got '{data.get('status')}'"
        
        # Store for cleanup
        self.created_preset_ids.append(data["id"])
        print(f"PASS: Created preset '{preset_name}' with id {data['id']}")
        return data["id"], preset_name
    
    def test_get_presets_returns_saved_preset(self):
        """GET /api/bulk-edit-tools/presets returns the saved preset"""
        # First create a preset
        preset_name = f"TEST_Verify_{uuid.uuid4().hex[:8]}"
        create_response = requests.post(
            f"{BASE_URL}/api/bulk-edit-tools/presets",
            json={
                "name": preset_name,
                "selections": {"material": "Ceramic"},
                "product_group": ""
            }
        )
        assert create_response.status_code == 200
        preset_id = create_response.json()["id"]
        self.created_preset_ids.append(preset_id)
        
        # Now fetch presets
        response = requests.get(f"{BASE_URL}/api/bulk-edit-tools/presets")
        assert response.status_code == 200
        data = response.json()
        
        # Find our preset
        found = next((p for p in data if p.get("id") == preset_id), None)
        assert found is not None, f"Preset {preset_id} not found in list"
        assert found.get("name") == preset_name
        assert found.get("selections", {}).get("material") == "Ceramic"
        print(f"PASS: Preset '{preset_name}' found in GET /presets response")
    
    def test_create_preset_duplicate_name_fails(self):
        """POST /api/bulk-edit-tools/presets with duplicate name returns 409"""
        preset_name = f"TEST_Duplicate_{uuid.uuid4().hex[:8]}"
        
        # Create first preset
        response1 = requests.post(
            f"{BASE_URL}/api/bulk-edit-tools/presets",
            json={"name": preset_name, "selections": {"material": "Stone"}}
        )
        assert response1.status_code == 200
        self.created_preset_ids.append(response1.json()["id"])
        
        # Try to create duplicate
        response2 = requests.post(
            f"{BASE_URL}/api/bulk-edit-tools/presets",
            json={"name": preset_name, "selections": {"material": "Marble"}}
        )
        assert response2.status_code == 409, f"Expected 409 for duplicate, got {response2.status_code}"
        print(f"PASS: Duplicate preset name correctly rejected with 409")
    
    def test_create_preset_empty_name_fails(self):
        """POST /api/bulk-edit-tools/presets with empty name returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/bulk-edit-tools/presets",
            json={"name": "", "selections": {"material": "Wood"}}
        )
        assert response.status_code == 400, f"Expected 400 for empty name, got {response.status_code}"
        print(f"PASS: Empty preset name correctly rejected with 400")
    
    def test_delete_preset(self):
        """DELETE /api/bulk-edit-tools/presets/{id} deletes a preset"""
        # Create a preset to delete
        preset_name = f"TEST_Delete_{uuid.uuid4().hex[:8]}"
        create_response = requests.post(
            f"{BASE_URL}/api/bulk-edit-tools/presets",
            json={"name": preset_name, "selections": {"finish": "Gloss"}}
        )
        assert create_response.status_code == 200
        preset_id = create_response.json()["id"]
        
        # Delete it
        delete_response = requests.delete(f"{BASE_URL}/api/bulk-edit-tools/presets/{preset_id}")
        assert delete_response.status_code == 200, f"Expected 200, got {delete_response.status_code}"
        assert delete_response.json().get("status") == "deleted"
        
        # Verify it's gone
        get_response = requests.get(f"{BASE_URL}/api/bulk-edit-tools/presets")
        presets = get_response.json()
        found = next((p for p in presets if p.get("id") == preset_id), None)
        assert found is None, f"Preset {preset_id} should be deleted but still exists"
        print(f"PASS: Preset '{preset_name}' deleted successfully")
    
    def test_delete_nonexistent_preset_returns_404(self):
        """DELETE /api/bulk-edit-tools/presets/{id} with invalid id returns 404"""
        fake_id = f"nonexistent-{uuid.uuid4().hex}"
        response = requests.delete(f"{BASE_URL}/api/bulk-edit-tools/presets/{fake_id}")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print(f"PASS: Delete nonexistent preset correctly returns 404")


class TestBulkEditSnapshot:
    """Tests for /api/bulk-edit-tools/snapshot endpoint"""
    
    def test_snapshot_empty_product_ids(self):
        """POST /api/bulk-edit-tools/snapshot with empty ids returns empty snapshot"""
        response = requests.post(
            f"{BASE_URL}/api/bulk-edit-tools/snapshot",
            json={"product_ids": [], "id_field": "sku", "fields": ["material", "finish"]}
        )
        assert response.status_code == 200
        data = response.json()
        assert "snapshot" in data
        assert data["snapshot"] == []
        print(f"PASS: Empty product_ids returns empty snapshot")
    
    def test_snapshot_with_product_ids(self):
        """POST /api/bulk-edit-tools/snapshot returns product values for given IDs"""
        # First get some real product SKUs from supplier_products
        products_response = requests.get(f"{BASE_URL}/api/supplier-sync/products?supplier=Canopy&limit=3")
        if products_response.status_code != 200:
            pytest.skip("Could not fetch products for snapshot test")
        
        response_data = products_response.json()
        # Handle both formats: direct list or {products: [...]}
        products = response_data.get("products", response_data) if isinstance(response_data, dict) else response_data
        if not products or len(products) == 0:
            pytest.skip("No products available for snapshot test")
        
        skus = [p.get("sku") for p in products if isinstance(p, dict) and p.get("sku")][:3]
        if not skus:
            pytest.skip("No SKUs found in products")
        
        response = requests.post(
            f"{BASE_URL}/api/bulk-edit-tools/snapshot",
            json={
                "product_ids": skus,
                "id_field": "sku",
                "fields": ["material", "finish", "rooms", "main_category"]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "snapshot" in data
        assert isinstance(data["snapshot"], list)
        print(f"PASS: Snapshot returned {len(data['snapshot'])} products for {len(skus)} SKUs")


class TestBulkEditHistory:
    """Tests for /api/bulk-edit-tools/history endpoints"""
    
    created_history_ids = []
    
    def test_get_history_returns_list(self):
        """GET /api/bulk-edit-tools/history returns array"""
        response = requests.get(f"{BASE_URL}/api/bulk-edit-tools/history?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: GET /history returns list with {len(data)} entries")
    
    def test_save_edit_history(self):
        """POST /api/bulk-edit-tools/history saves an edit history entry"""
        payload = {
            "user": "test_user",
            "action": "bulk_update",
            "product_count": 5,
            "product_ids": ["SKU001", "SKU002", "SKU003", "SKU004", "SKU005"],
            "id_field": "sku",
            "changes_summary": {
                "material": "Porcelain",
                "finish": "Matt"
            },
            "before_snapshot": [
                {"sku": "SKU001", "material": "Ceramic", "finish": "Gloss"},
                {"sku": "SKU002", "material": "Stone", "finish": "Natural"},
            ],
            "updates_applied": {
                "material": "Porcelain",
                "finish": "Matt"
            },
            "mode": "replace",
            "supplier": "TEST_Supplier"
        }
        response = requests.post(
            f"{BASE_URL}/api/bulk-edit-tools/history",
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "id" in data
        assert data.get("status") == "saved"
        
        self.created_history_ids.append(data["id"])
        print(f"PASS: History entry saved with id {data['id']}")
        return data["id"]
    
    def test_get_history_returns_saved_entry(self):
        """GET /api/bulk-edit-tools/history returns the saved entry"""
        # Create a history entry
        history_id = self.test_save_edit_history()
        
        # Fetch history
        response = requests.get(f"{BASE_URL}/api/bulk-edit-tools/history?limit=50")
        assert response.status_code == 200
        data = response.json()
        
        # Find our entry
        found = next((e for e in data if e.get("id") == history_id), None)
        assert found is not None, f"History entry {history_id} not found"
        assert found.get("product_count") == 5
        assert found.get("user") == "test_user"
        assert found.get("undone") == False
        print(f"PASS: History entry {history_id} found in GET /history response")
    
    def test_get_history_with_supplier_filter(self):
        """GET /api/bulk-edit-tools/history with supplier filter"""
        response = requests.get(f"{BASE_URL}/api/bulk-edit-tools/history?supplier=TEST_Supplier&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # All entries should have the supplier filter
        for entry in data:
            assert entry.get("supplier") == "TEST_Supplier", f"Entry has wrong supplier: {entry.get('supplier')}"
        print(f"PASS: History filtered by supplier returns {len(data)} entries")


class TestBulkEditUndo:
    """Tests for /api/bulk-edit-tools/history/{id}/undo endpoint"""
    
    def test_undo_nonexistent_entry_returns_404(self):
        """POST /api/bulk-edit-tools/history/{id}/undo with invalid id returns 404"""
        fake_id = f"nonexistent-{uuid.uuid4().hex}"
        response = requests.post(f"{BASE_URL}/api/bulk-edit-tools/history/{fake_id}/undo")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print(f"PASS: Undo nonexistent entry correctly returns 404")
    
    def test_undo_entry_without_snapshot_returns_400(self):
        """POST /api/bulk-edit-tools/history/{id}/undo without snapshot returns 400"""
        # Create entry without before_snapshot
        create_response = requests.post(
            f"{BASE_URL}/api/bulk-edit-tools/history",
            json={
                "user": "test_user",
                "action": "bulk_update",
                "product_count": 1,
                "product_ids": ["SKU_NO_SNAP"],
                "before_snapshot": [],  # Empty snapshot
                "updates_applied": {"material": "Test"},
                "supplier": "TEST_NoSnap"
            }
        )
        assert create_response.status_code == 200
        history_id = create_response.json()["id"]
        
        # Try to undo
        undo_response = requests.post(f"{BASE_URL}/api/bulk-edit-tools/history/{history_id}/undo")
        assert undo_response.status_code == 400, f"Expected 400, got {undo_response.status_code}"
        assert "snapshot" in undo_response.json().get("detail", "").lower()
        print(f"PASS: Undo without snapshot correctly returns 400")
    
    def test_undo_already_undone_entry_returns_400(self):
        """POST /api/bulk-edit-tools/history/{id}/undo on already undone entry returns 400"""
        # Create entry with snapshot
        create_response = requests.post(
            f"{BASE_URL}/api/bulk-edit-tools/history",
            json={
                "user": "test_user",
                "action": "bulk_update",
                "product_count": 1,
                "product_ids": ["SKU_UNDO_TEST"],
                "id_field": "sku",
                "before_snapshot": [{"sku": "SKU_UNDO_TEST", "material": "Original"}],
                "updates_applied": {"material": "Changed"},
                "supplier": "TEST_UndoTwice"
            }
        )
        assert create_response.status_code == 200
        history_id = create_response.json()["id"]
        
        # First undo (should succeed)
        undo1_response = requests.post(f"{BASE_URL}/api/bulk-edit-tools/history/{history_id}/undo")
        assert undo1_response.status_code == 200, f"First undo failed: {undo1_response.text}"
        
        # Second undo (should fail)
        undo2_response = requests.post(f"{BASE_URL}/api/bulk-edit-tools/history/{history_id}/undo")
        assert undo2_response.status_code == 400, f"Expected 400 for double undo, got {undo2_response.status_code}"
        assert "already" in undo2_response.json().get("detail", "").lower()
        print(f"PASS: Double undo correctly returns 400")


# Cleanup fixture
@pytest.fixture(scope="module", autouse=True)
def cleanup_test_data():
    """Cleanup TEST_ prefixed data after all tests"""
    yield
    # Cleanup presets
    try:
        response = requests.get(f"{BASE_URL}/api/bulk-edit-tools/presets")
        if response.status_code == 200:
            for preset in response.json():
                if preset.get("name", "").startswith("TEST_"):
                    requests.delete(f"{BASE_URL}/api/bulk-edit-tools/presets/{preset['id']}")
    except Exception as e:
        print(f"Cleanup warning: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
Regression test for the "Prices not updating" bug.

Root cause: Frontend Supplier Products "Save Prices" button was sending
`supplier: selectedSupplier` which equals "all" when on the All Suppliers tab.
Backend then added `{supplier: "all"}` to the Mongo query, matching zero products.

Fix:
1. Backend `bulk-update-unified` now treats `supplier` in {"all", "", None} as None (no filter).
2. Frontend save handler now sends `selectedSupplier !== 'all' ? selectedSupplier : null`.

This test locks in the backend guard so the bug can never recur even if a new
caller forgets the frontend check.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
ENDPOINT = f"{BASE_URL}/api/supplier-sync/products/bulk-update-unified"


def _find_test_sku():
    """Pick any SKU from the current supplier_products list to exercise."""
    r = requests.get(f"{BASE_URL}/api/supplier-sync/products?limit=1")
    assert r.status_code == 200, f"Could not list products: {r.status_code}"
    products = r.json().get("products", [])
    assert products, "No products available to run the regression test against"
    return products[0]


def _get_product(sku):
    r = requests.get(f"{BASE_URL}/api/supplier-sync/products?limit=1000")
    for p in r.json().get("products", []):
        if p.get("sku") == sku:
            return p
    return None


class TestSupplierAllGuard:
    """Guard test: supplier='all' must NOT restrict the update to zero products."""

    def test_supplier_all_string_updates_products(self):
        p = _find_test_sku()
        sku = p["sku"]
        original_cost = p.get("cost_price")

        # Set a known marker price via the "buggy" call signature (supplier='all')
        marker = 77.77
        r = requests.post(
            ENDPOINT,
            json={
                "product_ids": [sku],
                "id_field": "sku",
                "supplier": "all",  # THE PROBLEM VALUE
                "updates": {"cost_price": marker},
            },
        )
        assert r.status_code == 200, f"Unexpected status: {r.status_code} — {r.text[:200]}"
        body = r.json()
        assert body.get("updated_count", 0) >= 1, (
            f"FIX REGRESSED: supplier='all' caused updated_count=0. "
            f"Response: {body}"
        )

        # Verify the marker actually persisted
        after = _get_product(sku)
        assert after is not None, f"Could not re-fetch {sku}"
        assert float(after.get("cost_price", 0)) == marker, (
            f"cost_price did not persist: expected {marker}, got {after.get('cost_price')}"
        )

        # Restore
        restore = original_cost if original_cost is not None else 0
        requests.post(
            ENDPOINT,
            json={
                "product_ids": [sku],
                "id_field": "sku",
                "updates": {"cost_price": restore},
            },
        )

    def test_supplier_empty_string_updates_products(self):
        """Empty string should also be treated as 'no filter'."""
        p = _find_test_sku()
        sku = p["sku"]
        original_cost = p.get("cost_price")

        marker = 66.66
        r = requests.post(
            ENDPOINT,
            json={
                "product_ids": [sku],
                "id_field": "sku",
                "supplier": "",  # edge case
                "updates": {"cost_price": marker},
            },
        )
        assert r.status_code == 200
        assert r.json().get("updated_count", 0) >= 1

        after = _get_product(sku)
        assert float(after.get("cost_price", 0)) == marker

        # Restore
        restore = original_cost if original_cost is not None else 0
        requests.post(
            ENDPOINT,
            json={
                "product_ids": [sku],
                "id_field": "sku",
                "updates": {"cost_price": restore},
            },
        )

    def test_real_supplier_filter_still_rejects_mismatch(self):
        """The guard must NOT break genuine supplier filtering."""
        p = _find_test_sku()
        sku = p["sku"]
        real_supplier = p.get("supplier") or ""
        # Pick a definitely-wrong supplier name
        wrong = "DefinitelyNotARealSupplier_9999"
        assert wrong != real_supplier

        before = _get_product(sku)
        before_cost = before.get("cost_price")

        r = requests.post(
            ENDPOINT,
            json={
                "product_ids": [sku],
                "id_field": "sku",
                "supplier": wrong,
                "updates": {"cost_price": 1234.56},
            },
        )
        assert r.status_code == 200
        # Wrong supplier should match zero
        assert r.json().get("updated_count", 0) == 0, (
            "Supplier filter got broken — a wrong supplier name should not update anything"
        )

        # Price should be unchanged
        after = _get_product(sku)
        assert after.get("cost_price") == before_cost, (
            "Product cost was modified despite a non-matching supplier filter"
        )

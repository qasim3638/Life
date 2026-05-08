"""
Storefront Regression Tests - CRITICAL SAFETY NET

These tests verify that all essential storefront features are intact.
Run before every deployment: pytest backend/tests/test_storefront_health.py -v

PROTECTED FEATURES:
1. Trade Login visibility
2. Volume Pricing table
3. Tier pricing API
4. Collection data integrity
5. Product catalog availability
"""
import requests
import os

API_URL = os.environ.get("REACT_APP_BACKEND_URL", os.environ.get("BACKEND_URL", "http://localhost:8001"))

# Ensure API_URL uses /api prefix
if not API_URL.endswith("/api"):
    BASE = API_URL.rstrip("/")
else:
    BASE = API_URL.rstrip("/").rsplit("/api", 1)[0]


def test_storefront_health_check():
    """Health check endpoint returns healthy status."""
    r = requests.get(f"{BASE}/api/storefront-health/check")
    assert r.status_code == 200
    data = r.json()
    assert data["overall_status"] in ("healthy", "degraded")
    assert "checks" in data
    assert "tiles_collection" in data["checks"]


def test_tiles_collection_has_data():
    """The storefront must have published products."""
    r = requests.get(f"{BASE}/api/tiles/collections")
    assert r.status_code == 200
    data = r.json()
    collections = data if isinstance(data, list) else data.get("collections", [])
    assert len(collections) > 0, "No collections found - storefront is empty"


def test_individual_product_accessible():
    """At least one product must be accessible via its slug."""
    r = requests.get(f"{BASE}/api/tiles/products?limit=1")
    assert r.status_code == 200
    data = r.json()
    products = data if isinstance(data, list) else data.get("products", data.get("tiles", []))
    assert len(products) > 0, "No products returned"
    slug = products[0].get("slug")
    assert slug, "Product missing slug"

    # Verify individual product endpoint
    r2 = requests.get(f"{BASE}/api/tiles/products/{slug}")
    assert r2.status_code == 200


def test_tier_pricing_endpoint():
    """Tier pricing API must respond for any product."""
    # Get a product
    r = requests.get(f"{BASE}/api/tiles/products?limit=1")
    data = r.json()
    products = data if isinstance(data, list) else data.get("products", data.get("tiles", []))
    if not products:
        return  # Skip if no products
    slug = products[0].get("slug")

    r2 = requests.get(f"{BASE}/api/tiles/products/{slug}/tier-pricing")
    assert r2.status_code == 200
    tp_data = r2.json()
    # Must have 'disabled' or 'tiers' field
    assert "disabled" in tp_data or "tiers" in tp_data, f"Tier pricing response missing expected fields: {tp_data.keys()}"


def test_tier_pricing_disabled_product():
    """Products with tier_pricing_disabled must still have a valid API response."""
    r = requests.get(f"{BASE}/api/tiles/products?limit=100")
    data = r.json()
    products = data if isinstance(data, list) else data.get("products", data.get("tiles", []))

    disabled_products = [p for p in products if p.get("tier_pricing_disabled")]
    for p in disabled_products[:3]:
        slug = p.get("slug")
        r2 = requests.get(f"{BASE}/api/tiles/products/{slug}/tier-pricing")
        assert r2.status_code == 200
        tp_data = r2.json()
        assert tp_data.get("disabled") is True, f"Product {slug} should have disabled=True"


def test_collection_detail_data():
    """Collection detail API returns products with required fields."""
    r = requests.get(f"{BASE}/api/tiles/collections")
    data = r.json()
    collections = data if isinstance(data, list) else data.get("collections", [])
    if not collections:
        return

    series = collections[0].get("series_name")
    r2 = requests.get(f"{BASE}/api/tiles/collection/{series}")
    assert r2.status_code == 200
    detail = r2.json()
    products = detail if isinstance(detail, list) else detail.get("products", [])
    if products:
        p = products[0]
        # Essential fields for storefront rendering
        assert "slug" in p or "name" in p, "Product missing identifier"


def test_trade_account_login_endpoint():
    """Trade login endpoint must exist and respond."""
    r = requests.post(f"{BASE}/api/shop/auth/login", json={
        "email": "nonexistent@test.com",
        "password": "wrong"
    })
    # Should return 401 or 400, NOT 404 (endpoint must exist)
    assert r.status_code != 404, "Trade/Shop login endpoint missing - Trade Login feature broken"
    assert r.status_code in (400, 401, 422, 200)


def test_shop_customer_login_endpoint():
    """Shop customer login endpoint must exist."""
    r = requests.post(f"{BASE}/api/shop/auth/login", json={
        "email": "nonexistent@test.com",
        "password": "wrong"
    })
    # Should NOT be 404
    assert r.status_code != 404, "Shop login endpoint missing"


def test_critical_ui_elements_documented():
    """Health check must document all critical UI elements."""
    r = requests.get(f"{BASE}/api/storefront-health/check")
    data = r.json()
    ui_check = data["checks"].get("critical_ui_elements", {})
    elements = ui_check.get("elements", [])

    required_elements = {"Trade Login Box", "Trade Login Banner", "Volume Pricing Table", "Header Trade Tab"}
    found = {e["name"] for e in elements}
    missing = required_elements - found
    assert not missing, f"Critical UI elements not documented: {missing}"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])

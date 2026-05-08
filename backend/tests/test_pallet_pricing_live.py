"""Live API tests for half + full pallet pricing end-to-end (iter 177)."""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://feature-verification-7.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    # Try common admin login endpoints
    for path in ["/api/auth/admin/login", "/api/admin/login", "/api/auth/login"]:
        try:
            r = s.post(f"{BASE_URL}{path}", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
            if r.status_code == 200:
                data = r.json()
                token = data.get("access_token") or data.get("token") or (data.get("data") or {}).get("token")
                if token:
                    s.headers.update({"Authorization": f"Bearer {token}"})
                return s
        except Exception:
            continue
    pytest.skip("Admin login failed on all known paths")


# --- Public storefront ---

def test_tiles_products_returns_pallet_fields():
    r = requests.get(f"{BASE_URL}/api/tiles/products", timeout=30)
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    products = data if isinstance(data, list) else (data.get("products") or data.get("data") or [])
    assert isinstance(products, list) and len(products) > 0
    sample = products[0]
    # Fields should be present (may be None for products without pallet)
    for f in ["m2_per_pallet", "m2_per_half_pallet", "half_pallet_price", "pallet_price"]:
        assert f in sample, f"missing field {f} in tile-product serializer keys: {list(sample.keys())}"


def test_alabaster_60x60_has_expected_pallet_pricing():
    r = requests.get(f"{BASE_URL}/api/tiles/products", timeout=30)
    assert r.status_code == 200
    data = r.json()
    products = data if isinstance(data, list) else (data.get("products") or data.get("data") or [])
    matches = [
        p for p in products
        if "alabaster" in ((p.get("display_name") or p.get("name") or "")).lower()
        and "60x60" in ((p.get("size") or p.get("display_name") or p.get("name") or "")).replace(" ", "").lower()
    ]
    assert matches, "Alabaster 60x60cm test product not found"
    p = matches[0]
    assert float(p.get("m2_per_pallet") or 0) == 32.0, p
    assert float(p.get("m2_per_half_pallet") or 0) == 16.0, p
    assert abs(float(p.get("half_pallet_price") or 0) - 27.5) < 0.01, p
    assert abs(float(p.get("pallet_price") or 0) - 26.09) < 0.01, p


def test_half_pallet_default_is_half_when_only_full_set():
    """Implicit defaulting in serializer: m2_per_half = m2_per_pallet/2 when null."""
    r = requests.get(f"{BASE_URL}/api/tiles/products", timeout=30)
    assert r.status_code == 200
    data = r.json()
    products = data if isinstance(data, list) else (data.get("products") or data.get("data") or [])
    # Check global invariant on every tile that has m2_per_pallet
    violations = []
    for p in products:
        full = p.get("m2_per_pallet")
        half = p.get("m2_per_half_pallet")
        if full and float(full) > 0 and (half is None or half == 0):
            violations.append((p.get("name"), full, half))
    assert not violations, f"half-pallet default not applied: {violations[:5]}"


# --- Admin pallet settings ---

def test_admin_pallet_settings_returns_expected_shape(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/admin/pallet-settings", timeout=15)
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert "pallet_pricing_mode" in body
    assert "pallet_trade_extra_discount_pct" in body
    assert "allowed_modes" in body
    assert isinstance(body["allowed_modes"], list)


def test_admin_pallet_settings_unauth_blocks():
    r = requests.get(f"{BASE_URL}/api/admin/pallet-settings", timeout=15)
    assert r.status_code in (401, 403), r.status_code


# --- Admin product update sync ---

def test_update_product_persists_pallet_fields(admin_session):
    # Find the Alabaster product via the public tile feed first
    pub = requests.get(f"{BASE_URL}/api/tiles/products", timeout=20).json()
    products = pub if isinstance(pub, list) else (pub.get("products") or pub.get("data") or [])
    target = None
    for p in products:
        if "alabaster" in ((p.get("display_name") or p.get("name") or "")).lower():
            target = p
            break
    if not target:
        pytest.skip("Alabaster test tile not found in storefront feed")

    sku = target.get("sku") or target.get("display_code")
    # Now find the corresponding admin product by SKU
    ap = admin_session.get(f"{BASE_URL}/api/products?limit=500", timeout=30)
    if ap.status_code != 200:
        pytest.skip(f"products list returned {ap.status_code}")
    body = ap.json()
    items = body if isinstance(body, list) else (body.get("products") or body.get("items") or body.get("data") or [])
    matched = [p for p in items if (p.get("sku") == sku) or ((p.get("display_name") or p.get("name") or "").lower().startswith("alabaster"))]
    if not matched:
        # fall back to any product with an SKU so we can still validate persistence
        matched = [p for p in items if p.get("sku")]
    if not matched:
        pytest.skip("No admin product available")
    pid = matched[0].get("id") or matched[0].get("_id") or matched[0].get("product_id")
    assert pid

    get_r = admin_session.get(f"{BASE_URL}/api/products/{pid}", timeout=15)
    assert get_r.status_code == 200, get_r.text[:300]
    orig = get_r.json()
    orig = orig.get("product") if isinstance(orig, dict) and "product" in orig else orig

    payload = {
        "m2_per_pallet": 40,
        "m2_per_half_pallet": 20,
        "pallet_price": 24.99,
        "half_pallet_price": 25.99,
        "pallet_enabled": True,
    }
    upd = admin_session.put(f"{BASE_URL}/api/products/{pid}", json=payload, timeout=20)
    assert upd.status_code in (200, 204), upd.text[:400]

    fetched = admin_session.get(f"{BASE_URL}/api/products/{pid}", timeout=15).json()
    fetched = fetched.get("product") if isinstance(fetched, dict) and "product" in fetched else fetched
    assert float(fetched.get("m2_per_pallet") or 0) == 40, fetched
    assert float(fetched.get("m2_per_half_pallet") or 0) == 20, fetched
    assert abs(float(fetched.get("pallet_price") or 0) - 24.99) < 0.01, fetched
    assert abs(float(fetched.get("half_pallet_price") or 0) - 25.99) < 0.01, fetched

    # Restore original values
    restore = {
        "m2_per_pallet": orig.get("m2_per_pallet") or 32,
        "m2_per_half_pallet": orig.get("m2_per_half_pallet") or 16,
        "pallet_price": orig.get("pallet_price") or 26.09,
        "half_pallet_price": orig.get("half_pallet_price") or 27.5,
        "pallet_enabled": orig.get("pallet_enabled", True),
    }
    admin_session.put(f"{BASE_URL}/api/products/{pid}", json=restore, timeout=20)

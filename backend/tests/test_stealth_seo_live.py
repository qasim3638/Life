"""Live-API tests for the Stealth-Keyword SEO endpoints.

Hits the deployed REACT_APP_BACKEND_URL via HTTP. Read-only on bulk
endpoints (uses ?dry_run=true). Per-product mutate/restore is performed
on a single tile and rolled back at end.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://feature-verification-7.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"

API = f"{BASE_URL}/api"


# ── auth ──

@pytest.fixture(scope="module")
def admin_token():
    # try common admin login endpoints
    for path in ("/auth/login", "/admin/login", "/auth/signin"):
        try:
            r = requests.post(f"{API}{path}", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
            if r.status_code == 200:
                data = r.json()
                tok = data.get("access_token") or data.get("token") or (data.get("data") or {}).get("access_token")
                if tok:
                    return tok
        except Exception:
            pass
    pytest.skip(f"Could not authenticate {ADMIN_EMAIL}")


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ── stats ──

def test_stats_anon_is_forbidden():
    r = requests.get(f"{API}/admin/seo/stealth-keywords/stats", timeout=15)
    assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}: {r.text[:200]}"


def test_stats_admin_returns_shape(auth_headers):
    r = requests.get(f"{API}/admin/seo/stealth-keywords/stats", headers=auth_headers, timeout=15)
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    for k in ("products_total", "products_with_keywords", "products_eligible", "coverage_pct", "collection_keyword_sets"):
        assert k in data, f"missing key {k} in {data}"
    assert isinstance(data["products_total"], int)
    assert data["products_total"] > 0


# ── collections ──

def test_collections_admin_only(auth_headers):
    r = requests.get(f"{API}/admin/seo/stealth-keywords/collections", timeout=15)
    assert r.status_code in (401, 403)
    r = requests.get(f"{API}/admin/seo/stealth-keywords/collections", headers=auth_headers, timeout=20)
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert "collections" in body
    cols = body["collections"]
    assert isinstance(cols, list)
    if cols:
        # sorted by product_count desc
        counts = [c["product_count"] for c in cols]
        assert counts == sorted(counts, reverse=True)
        for c in cols[:3]:
            assert {"collection", "product_count", "with_stealth_keywords", "coverage_pct"} <= set(c.keys())


# ── products list ──

@pytest.fixture(scope="module")
def first_collection(auth_headers):
    r = requests.get(f"{API}/admin/seo/stealth-keywords/collections", headers=auth_headers, timeout=20)
    cols = r.json().get("collections", [])
    if not cols:
        pytest.skip("No collections in catalogue")
    return cols[0]["collection"]


def test_products_admin_only(auth_headers, first_collection):
    r = requests.get(f"{API}/admin/seo/stealth-keywords/products?collection={first_collection}&limit=5", timeout=15)
    assert r.status_code in (401, 403)
    r = requests.get(
        f"{API}/admin/seo/stealth-keywords/products",
        params={"collection": first_collection, "only_missing": "true", "limit": 5},
        headers=auth_headers, timeout=20,
    )
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert "products" in body
    rows = body["products"]
    assert isinstance(rows, list)
    if rows:
        row = rows[0]
        for k in ("id", "name", "stealth_keywords", "suggested_keywords", "image_url"):
            assert k in row, f"missing {k} in {row}"
        assert isinstance(row["stealth_keywords"], list)
        assert isinstance(row["suggested_keywords"], list)


# ── per-product set / restore ──

@pytest.fixture(scope="module")
def sample_product(auth_headers, first_collection):
    """Pick the first product (any state) and remember its keywords for restoration."""
    r = requests.get(
        f"{API}/admin/seo/stealth-keywords/products",
        params={"collection": first_collection, "limit": 5},
        headers=auth_headers, timeout=20,
    )
    rows = r.json().get("products", [])
    if not rows:
        pytest.skip(f"No products in collection {first_collection}")
    return rows[0]


def test_set_product_keywords_round_trip(auth_headers, sample_product):
    pid = sample_product["id"]
    original = sample_product.get("stealth_keywords") or []
    test_kw = list(original) + ["TEST_STEALTH_LIVE_KW"]
    try:
        r = requests.post(
            f"{API}/admin/seo/stealth-keywords/products/{pid}",
            json={"keywords": test_kw},
            headers=auth_headers, timeout=20,
        )
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert data.get("ok") is True
        assert "TEST_STEALTH_LIVE_KW" in data["stealth_keywords"]
    finally:
        # restore original
        rr = requests.post(
            f"{API}/admin/seo/stealth-keywords/products/{pid}",
            json={"keywords": original},
            headers=auth_headers, timeout=20,
        )
        assert rr.status_code == 200, f"RESTORE FAILED: {rr.text[:300]}"


def test_set_product_keywords_404(auth_headers):
    r = requests.post(
        f"{API}/admin/seo/stealth-keywords/products/__nonexistent_xyz__",
        json={"keywords": ["x"]},
        headers=auth_headers, timeout=15,
    )
    assert r.status_code == 404, r.text[:200]


# ── bulk-apply (validation only — no mass mutation) ──

def test_bulk_apply_invalid_mode_400(auth_headers, first_collection):
    r = requests.post(
        f"{API}/admin/seo/stealth-keywords/bulk-apply",
        json={"collection": first_collection, "keywords": ["x"], "mode": "nonsense"},
        headers=auth_headers, timeout=15,
    )
    # Pydantic regex returns 422; ValueError 400. Either is acceptable rejection.
    assert r.status_code in (400, 422), r.text[:300]


def test_bulk_apply_admin_only(first_collection):
    r = requests.post(
        f"{API}/admin/seo/stealth-keywords/bulk-apply",
        json={"collection": first_collection, "keywords": ["x"], "mode": "merge"},
        timeout=15,
    )
    assert r.status_code in (401, 403)


# ── auto-fill (dry_run only — DO NOT MUTATE LIVE) ──

def test_auto_fill_dry_run_admin_only():
    r = requests.post(f"{API}/admin/seo/stealth-keywords/auto-fill-all?dry_run=true", timeout=20)
    assert r.status_code in (401, 403)


def test_auto_fill_dry_run_returns_preview(auth_headers):
    r = requests.post(
        f"{API}/admin/seo/stealth-keywords/auto-fill-all?dry_run=true",
        headers=auth_headers, timeout=60,
    )
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    assert data.get("dry_run") is True
    for k in ("matched", "updated", "keywords_added", "skipped_already_have", "skipped_no_supplier_data"):
        assert k in data, f"missing {k} in {data}"
    assert isinstance(data["matched"], int)
    assert data["matched"] > 0


# ── collection-wide keywords ──

def test_collection_keywords_admin_round_trip(auth_headers):
    coll = "__TEST_STEALTH_COLLECTION__"
    try:
        # set
        r = requests.post(
            f"{API}/admin/seo/stealth-keywords/collection/{coll}",
            json={"keywords": ["TestAlt1", "TestAlt2"]},
            headers=auth_headers, timeout=15,
        )
        assert r.status_code == 200, r.text[:300]
        # admin get
        r = requests.get(f"{API}/admin/seo/stealth-keywords/collection/{coll}", headers=auth_headers, timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert body["collection"] == coll
        assert "TestAlt1" in body["keywords"]
        # public anon get
        rp = requests.get(f"{API}/shop/seo/stealth-keywords/collection/{coll}", timeout=15)
        assert rp.status_code == 200, rp.text[:200]
        pbody = rp.json()
        assert pbody["collection"] == coll
        assert "TestAlt1" in pbody["keywords"]
    finally:
        requests.post(
            f"{API}/admin/seo/stealth-keywords/collection/{coll}",
            json={"keywords": []},
            headers=auth_headers, timeout=15,
        )


def test_public_collection_endpoint_anon_unknown_returns_empty():
    r = requests.get(f"{API}/shop/seo/stealth-keywords/collection/__nope_no_such_thing__", timeout=15)
    assert r.status_code == 200, r.text[:200]
    body = r.json()
    assert body["collection"] == "__nope_no_such_thing__"
    assert body["keywords"] == []


def test_admin_collection_get_admin_only():
    r = requests.get(f"{API}/admin/seo/stealth-keywords/collection/anything", timeout=15)
    assert r.status_code in (401, 403)


# ── tile serializer exposes seo fields ──

def test_tile_serializer_exposes_hidden_seo_keywords_field(auth_headers, first_collection):
    # find a slug
    rr = requests.get(
        f"{API}/admin/seo/stealth-keywords/products",
        params={"collection": first_collection, "limit": 5},
        headers=auth_headers, timeout=20,
    )
    rows = rr.json().get("products", [])
    slug = next((r.get("slug") for r in rows if r.get("slug")), None)
    if not slug:
        pytest.skip("No tile with slug available")
    r = requests.get(f"{API}/tiles/products/{slug}", timeout=20)
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    # The two SEO fields the SSR meta builder reads
    assert "hidden_seo_keywords" in body, f"hidden_seo_keywords missing from {list(body.keys())[:30]}"
    assert "original_name" in body, f"original_name missing from {list(body.keys())[:30]}"

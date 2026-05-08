"""Live API tests for /api/admin/seo/stealth-keywords/margin-intel."""
import os
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or os.environ.get("BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback: read frontend/.env
    try:
        with open("/app/frontend/.env") as f:
            for ln in f:
                if ln.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = ln.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASS = "admin123"
MARGIN_URL = f"{BASE_URL}/api/admin/seo/stealth-keywords/margin-intel"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
        timeout=20,
    )
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get("access_token") or data.get("token")
    assert tok, f"No token in {data}"
    return tok


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ─── Auth & validation ───

def test_anon_403():
    r = requests.get(MARGIN_URL, timeout=30)
    assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}"


def test_top_n_too_low_422(auth_headers):
    r = requests.get(MARGIN_URL, params={"top_n": 4}, headers=auth_headers, timeout=30)
    assert r.status_code == 422, f"Expected 422 for top_n=4, got {r.status_code}"


def test_top_n_too_high_422(auth_headers):
    r = requests.get(MARGIN_URL, params={"top_n": 200}, headers=auth_headers, timeout=30)
    assert r.status_code == 422, f"Expected 422 for top_n=200, got {r.status_code}"


# ─── Happy path & shape ───

def test_default_call_shape(auth_headers):
    r = requests.get(MARGIN_URL, headers=auth_headers, timeout=60)
    assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
    data = r.json()
    for key in ("summary", "top_revenue_gen", "price_test_candidates", "suppliers", "generated_at"):
        assert key in data, f"missing key {key}"
    s = data["summary"]
    for k in ("total_products", "with_cost_data", "with_organic_traffic", "median_margin_pct", "gsc_connected"):
        assert k in s, f"summary missing {k}"
    assert isinstance(data["top_revenue_gen"], list)
    assert isinstance(data["suppliers"], list)


def test_top_revenue_gen_row_shape(auth_headers):
    r = requests.get(MARGIN_URL, params={"top_n": 10}, headers=auth_headers, timeout=60)
    assert r.status_code == 200
    rows = r.json().get("top_revenue_gen") or []
    if not rows:
        pytest.skip("No top_revenue_gen rows in live data")
    row = rows[0]
    for k in ("product_id", "name", "supplier_name", "price", "cost_price",
              "margin_pct", "impressions_this_week", "impressions_last_week",
              "impressions_delta_pct", "score"):
        assert k in row, f"row missing {k}: {row}"


def test_price_test_filter(auth_headers):
    r = requests.get(MARGIN_URL, headers=auth_headers, timeout=60)
    cands = r.json().get("price_test_candidates") or []
    for c in cands:
        assert c["impressions_this_week"] >= 50, c
        # margin_pct may be None - filter requires <30 OR None counted as 0
        m = c.get("margin_pct")
        assert (m is None) or (m < 30), c


def test_supplier_league_sorted(auth_headers):
    r = requests.get(MARGIN_URL, headers=auth_headers, timeout=60)
    sups = r.json().get("suppliers") or []
    if len(sups) < 2:
        pytest.skip("Not enough suppliers to verify sort")
    scores = [s["score_sum"] for s in sups]
    assert scores == sorted(scores, reverse=True), "suppliers not sorted by score_sum desc"
    # Field shape check
    for s in sups[:3]:
        for k in ("supplier", "product_count", "avg_margin_pct", "impressions_this_week", "score_sum"):
            assert k in s, f"supplier row missing {k}"


# ─── Cache behaviour ───

def test_cache_hit_same_generated_at(auth_headers):
    r1 = requests.get(MARGIN_URL, params={"top_n": 20}, headers=auth_headers, timeout=60)
    assert r1.status_code == 200
    g1 = r1.json()["generated_at"]
    time.sleep(1)
    r2 = requests.get(MARGIN_URL, params={"top_n": 20}, headers=auth_headers, timeout=60)
    assert r2.status_code == 200
    g2 = r2.json()["generated_at"]
    assert g1 == g2, f"cache miss: {g1} != {g2}"


def test_force_refresh_changes_generated_at(auth_headers):
    r1 = requests.get(MARGIN_URL, params={"top_n": 20}, headers=auth_headers, timeout=60)
    g1 = r1.json()["generated_at"]
    time.sleep(1)
    r2 = requests.get(MARGIN_URL, params={"top_n": 20, "refresh": "true"},
                     headers=auth_headers, timeout=60)
    assert r2.status_code == 200
    g2 = r2.json()["generated_at"]
    assert g1 != g2, "refresh=true did not bypass cache"


def test_different_top_n_separate_cache(auth_headers):
    # Use refresh on first to set a unique cached_at, then GET other top_n
    r10 = requests.get(MARGIN_URL, params={"top_n": 10, "refresh": "true"},
                      headers=auth_headers, timeout=60)
    assert r10.status_code == 200
    time.sleep(1)
    r50 = requests.get(MARGIN_URL, params={"top_n": 50, "refresh": "true"},
                      headers=auth_headers, timeout=60)
    assert r50.status_code == 200
    # Different top_n should yield different list lengths normally
    a = r10.json()["top_revenue_gen"]
    b = r50.json()["top_revenue_gen"]
    assert len(a) <= 10
    assert len(b) <= 50
    # generated_at should be different (separate cache keys, both freshly written)
    assert r10.json()["generated_at"] != r50.json()["generated_at"]

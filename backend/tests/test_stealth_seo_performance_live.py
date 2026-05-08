"""Live HTTP tests against the preview backend for the stealth-keyword
performance endpoints:
  GET  /api/admin/seo/stealth-keywords/performance
  POST /api/admin/seo/stealth-keywords/performance/promote-missed-win

Uses a SENTINEL collection name ("__TEST_PROMOTE_SENTINEL__") to avoid
polluting real data — cleaned up at teardown.
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://feature-verification-7.preview.emergentagent.com",
).rstrip("/")
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"
SENTINEL_COLLECTION = "__TEST_PROMOTE_SENTINEL__"
SENTINEL_QUERY = "__test_promote_query_1234__"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    tok = r.json().get("token") or r.json().get("access_token")
    assert tok, f"no token in login resp: {r.json()}"
    return tok


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ───── Auth / RBAC ─────

def test_performance_requires_auth():
    r = requests.get(
        f"{BASE_URL}/api/admin/seo/stealth-keywords/performance", timeout=15,
    )
    assert r.status_code in (401, 403), f"expected 401/403 anon got {r.status_code}"


def test_promote_requires_auth():
    r = requests.post(
        f"{BASE_URL}/api/admin/seo/stealth-keywords/performance/promote-missed-win",
        json={"target": "collection", "query": "x", "collection": "y"},
        timeout=15,
    )
    assert r.status_code in (401, 403)


# ───── GET /performance schema & behaviour ─────

def test_performance_returns_report(auth_headers):
    r = requests.get(
        f"{BASE_URL}/api/admin/seo/stealth-keywords/performance",
        headers=auth_headers, params={"days": 28}, timeout=60,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    # Required top-level keys per spec
    for k in (
        "gsc_connected", "totals", "stealth", "brand", "other",
        "top_winners", "missed_wins", "underperformers", "generated_at",
    ):
        assert k in data, f"missing key {k} in report"
    # Buckets have the expected shape
    for bucket in ("totals", "stealth", "brand", "other"):
        for field in ("clicks", "impressions", "ctr", "queries_count"):
            assert field in data[bucket], f"{bucket}.{field} missing"
    # If GSC is connected we also expect start_date/end_date
    if data["gsc_connected"] and not data.get("reason"):
        assert data.get("start_date")
        assert data.get("end_date")


def test_days_range_rejects_below_min(auth_headers):
    r = requests.get(
        f"{BASE_URL}/api/admin/seo/stealth-keywords/performance",
        headers=auth_headers, params={"days": 3}, timeout=15,
    )
    assert r.status_code == 422


def test_days_range_rejects_above_max(auth_headers):
    r = requests.get(
        f"{BASE_URL}/api/admin/seo/stealth-keywords/performance",
        headers=auth_headers, params={"days": 120}, timeout=15,
    )
    assert r.status_code == 422


def test_days_accepts_boundary_7_and_90(auth_headers):
    for d in (7, 90):
        r = requests.get(
            f"{BASE_URL}/api/admin/seo/stealth-keywords/performance",
            headers=auth_headers, params={"days": d}, timeout=60,
        )
        assert r.status_code == 200, f"days={d} failed"


def test_cache_vs_force_refresh(auth_headers):
    # First call — use cache
    r1 = requests.get(
        f"{BASE_URL}/api/admin/seo/stealth-keywords/performance",
        headers=auth_headers, params={"days": 28}, timeout=60,
    )
    assert r1.status_code == 200
    r2 = requests.get(
        f"{BASE_URL}/api/admin/seo/stealth-keywords/performance",
        headers=auth_headers, params={"days": 28}, timeout=60,
    )
    assert r2.status_code == 200
    # Same cache → same generated_at
    assert r1.json()["generated_at"] == r2.json()["generated_at"], (
        "cache did not return same generated_at"
    )
    time.sleep(1.1)
    r3 = requests.get(
        f"{BASE_URL}/api/admin/seo/stealth-keywords/performance",
        headers=auth_headers, params={"days": 28, "refresh": "true"}, timeout=60,
    )
    assert r3.status_code == 200
    assert r3.json()["generated_at"] != r1.json()["generated_at"], (
        "refresh=true did not bypass cache"
    )


# ───── POST /performance/promote-missed-win — body validation ─────

def test_promote_invalid_target_422(auth_headers):
    r = requests.post(
        f"{BASE_URL}/api/admin/seo/stealth-keywords/performance/promote-missed-win",
        headers=auth_headers,
        json={"target": "bogus", "query": "x", "collection": "y"},
        timeout=15,
    )
    assert r.status_code == 422, f"expected 422 got {r.status_code}: {r.text}"


def test_promote_product_missing_id_400(auth_headers):
    r = requests.post(
        f"{BASE_URL}/api/admin/seo/stealth-keywords/performance/promote-missed-win",
        headers=auth_headers,
        json={"target": "product", "query": "foo bar"},
        timeout=15,
    )
    assert r.status_code == 400
    assert "product_id" in r.text


def test_promote_collection_missing_collection_400(auth_headers):
    r = requests.post(
        f"{BASE_URL}/api/admin/seo/stealth-keywords/performance/promote-missed-win",
        headers=auth_headers,
        json={"target": "collection", "query": "foo bar"},
        timeout=15,
    )
    assert r.status_code == 400
    assert "collection" in r.text


# ───── POST promote-missed-win — happy path (uses sentinel) ─────

def test_promote_collection_appends_and_idempotent(auth_headers):
    # Clean any leftover sentinel data first
    requests.post(
        f"{BASE_URL}/api/admin/seo/stealth-keywords/collection/{SENTINEL_COLLECTION}",
        headers=auth_headers, json={"keywords": []}, timeout=15,
    )

    # First promote — appends
    r1 = requests.post(
        f"{BASE_URL}/api/admin/seo/stealth-keywords/performance/promote-missed-win",
        headers=auth_headers,
        json={"target": "collection", "query": SENTINEL_QUERY,
              "collection": SENTINEL_COLLECTION},
        timeout=15,
    )
    assert r1.status_code == 200, r1.text

    # GET to verify persistence
    g1 = requests.get(
        f"{BASE_URL}/api/admin/seo/stealth-keywords/collection/{SENTINEL_COLLECTION}",
        headers=auth_headers, timeout=15,
    )
    assert g1.status_code == 200
    kws = g1.json().get("keywords") or []
    assert SENTINEL_QUERY in kws, f"sentinel keyword not persisted: {kws}"

    # Second call — idempotent, no duplicate
    r2 = requests.post(
        f"{BASE_URL}/api/admin/seo/stealth-keywords/performance/promote-missed-win",
        headers=auth_headers,
        json={"target": "collection", "query": SENTINEL_QUERY,
              "collection": SENTINEL_COLLECTION},
        timeout=15,
    )
    assert r2.status_code == 200
    g2 = requests.get(
        f"{BASE_URL}/api/admin/seo/stealth-keywords/collection/{SENTINEL_COLLECTION}",
        headers=auth_headers, timeout=15,
    )
    kws2 = g2.json().get("keywords") or []
    assert kws2.count(SENTINEL_QUERY) == 1, (
        f"promote is not idempotent — keyword appears {kws2.count(SENTINEL_QUERY)} times: {kws2}"
    )

    # Teardown — clear sentinel collection
    requests.post(
        f"{BASE_URL}/api/admin/seo/stealth-keywords/collection/{SENTINEL_COLLECTION}",
        headers=auth_headers, json={"keywords": []}, timeout=15,
    )


def test_promote_product_unknown_id_returns_404(auth_headers):
    r = requests.post(
        f"{BASE_URL}/api/admin/seo/stealth-keywords/performance/promote-missed-win",
        headers=auth_headers,
        json={"target": "product", "query": "x",
              "product_id": "__this_id_does_not_exist__"},
        timeout=15,
    )
    # Should surface the LookupError as 404 per the route
    assert r.status_code == 404, f"expected 404 got {r.status_code}: {r.text}"

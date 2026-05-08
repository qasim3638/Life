"""Live API smoke tests for Stealth-Keyword Attribution Timeline endpoints.

Hits the real REACT_APP_BACKEND_URL so we can validate wiring + auth
guards. Write-heavy tests use the cache collection only (safe to mutate).
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fall back to frontend .env
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                    break
    except FileNotFoundError:
        pass

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text[:200]}"
    token = r.json().get("access_token") or r.json().get("token")
    assert token, f"No token in login response: {r.json()}"
    return token


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ───── Auth guards ─────

def test_timeline_requires_auth():
    r = requests.get(
        f"{BASE_URL}/api/admin/seo/stealth-keywords/attribution/timeline",
        timeout=15,
    )
    assert r.status_code in (401, 403), f"Expected 401/403 anon, got {r.status_code}"


def test_rebuild_requires_auth():
    r = requests.post(
        f"{BASE_URL}/api/admin/seo/stealth-keywords/attribution/rebuild",
        timeout=15,
    )
    assert r.status_code in (401, 403)


# ───── Param validation ─────

def test_timeline_days_too_low_422(admin_headers):
    r = requests.get(
        f"{BASE_URL}/api/admin/seo/stealth-keywords/attribution/timeline",
        params={"days": 1},
        headers=admin_headers,
        timeout=15,
    )
    assert r.status_code == 422


def test_timeline_days_too_high_422(admin_headers):
    r = requests.get(
        f"{BASE_URL}/api/admin/seo/stealth-keywords/attribution/timeline",
        params={"days": 200},
        headers=admin_headers,
        timeout=15,
    )
    assert r.status_code == 422


def test_timeline_scope_bad_value_422(admin_headers):
    r = requests.get(
        f"{BASE_URL}/api/admin/seo/stealth-keywords/attribution/timeline",
        params={"scope": "bogus"},
        headers=admin_headers,
        timeout=15,
    )
    assert r.status_code == 422


def test_timeline_min_days_live_too_high_422(admin_headers):
    r = requests.get(
        f"{BASE_URL}/api/admin/seo/stealth-keywords/attribution/timeline",
        params={"min_days_live": 100},
        headers=admin_headers,
        timeout=15,
    )
    assert r.status_code == 422


# ───── Happy paths ─────

def test_timeline_default_ok(admin_headers):
    r = requests.get(
        f"{BASE_URL}/api/admin/seo/stealth-keywords/attribution/timeline",
        headers=admin_headers,
        timeout=30,
    )
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert "rows" in body
    assert "summary" in body
    assert "generated_at" in body
    assert isinstance(body["rows"], list)
    # Each row (if any) must have sparkline of 28 ints and roi_band
    for row in body["rows"]:
        assert isinstance(row.get("spark"), list)
        assert len(row["spark"]) == 28
        assert all(isinstance(v, int) for v in row["spark"])
        assert row.get("roi_band") in ("winner", "ok", "slow", "quiet")


def test_timeline_scope_collection(admin_headers):
    r = requests.get(
        f"{BASE_URL}/api/admin/seo/stealth-keywords/attribution/timeline",
        params={"scope": "collection"},
        headers=admin_headers,
        timeout=30,
    )
    assert r.status_code == 200
    for row in r.json().get("rows", []):
        assert row.get("scope") == "collection"


def test_timeline_scope_city_page(admin_headers):
    r = requests.get(
        f"{BASE_URL}/api/admin/seo/stealth-keywords/attribution/timeline",
        params={"scope": "city_page"},
        headers=admin_headers,
        timeout=30,
    )
    assert r.status_code == 200
    for row in r.json().get("rows", []):
        assert row.get("scope") == "city_page"


def test_timeline_days_90_ok(admin_headers):
    r = requests.get(
        f"{BASE_URL}/api/admin/seo/stealth-keywords/attribution/timeline",
        params={"days": 90},
        headers=admin_headers,
        timeout=30,
    )
    assert r.status_code == 200


def test_rebuild_endpoint(admin_headers):
    # Accept long cold-GSC response
    r = requests.post(
        f"{BASE_URL}/api/admin/seo/stealth-keywords/attribution/rebuild",
        headers=admin_headers,
        timeout=60,
    )
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    # Either success or well-formed failure
    assert "ok" in body
    if body["ok"]:
        for k in ("rows_pulled", "tracked_kws", "matched_pairs",
                  "keywords_with_data", "rebuilt_at"):
            assert k in body, f"missing key {k} in {body}"
    else:
        assert body.get("reason") in ("gsc_not_connected", "gsc_error")

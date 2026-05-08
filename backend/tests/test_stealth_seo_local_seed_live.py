"""Live API smoke tests for stealth-keyword Local Seeder (iter170).
Verifies endpoint shape on production-like preview env. Must NOT
mutate live data permanently — restores defaults at teardown.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://feature-verification-7.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASS = "admin123"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get("token") or data.get("access_token")
    assert tok, f"no token in {data}"
    return tok


@pytest.fixture(scope="module")
def headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


def test_get_settings_returns_auto_local_seed_field(headers):
    r = requests.get(f"{BASE_URL}/api/admin/seo/stealth-keywords/digest/settings",
                     headers=headers, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert "auto_local_seed_enabled" in d
    assert isinstance(d["auto_local_seed_enabled"], bool)


def test_put_auto_local_seed_round_trip(headers):
    # 1) enable
    r = requests.put(f"{BASE_URL}/api/admin/seo/stealth-keywords/digest/settings",
                     json={"auto_local_seed_enabled": True}, headers=headers, timeout=30)
    assert r.status_code == 200
    assert r.json()["auto_local_seed_enabled"] is True

    # 2) confirm via GET
    r2 = requests.get(f"{BASE_URL}/api/admin/seo/stealth-keywords/digest/settings",
                      headers=headers, timeout=30)
    assert r2.json()["auto_local_seed_enabled"] is True

    # 3) restore
    r3 = requests.put(f"{BASE_URL}/api/admin/seo/stealth-keywords/digest/settings",
                      json={"auto_local_seed_enabled": False}, headers=headers, timeout=30)
    assert r3.status_code == 200
    assert r3.json()["auto_local_seed_enabled"] is False


def test_history_endpoint_token_redacted(headers):
    r = requests.get(f"{BASE_URL}/api/admin/seo/stealth-keywords/auto-promote/history",
                     headers=headers, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert "rows" in d
    for row in d["rows"]:
        assert "token" not in row, "raw token must not be exposed"
        # token_hint may or may not be set


def test_undo_unknown_record_id_returns_404(headers):
    r = requests.post(f"{BASE_URL}/api/admin/seo/stealth-keywords/auto-promote/undo/UNKNOWN_xyz",
                      headers=headers, timeout=30)
    assert r.status_code == 404


def test_public_undo_unknown_token_returns_404():
    r = requests.get(f"{BASE_URL}/api/shop/seo/stealth-keywords/auto-promote/undo/badbadbad",
                     timeout=30, allow_redirects=False)
    assert r.status_code == 404


def test_public_city_page_returns_hidden_seo_keywords_field(headers):
    """Endpoint should at minimum surface the field in its response shape
    when present (we can't guarantee any city-page actually has kws set).
    Just confirm the route works."""
    # find any city page
    r = requests.get(f"{BASE_URL}/api/admin/city-pages?limit=1",
                     headers=headers, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"admin city-pages list unavailable: {r.status_code}")
    rows = r.json().get("rows") or r.json().get("pages") or []
    if not rows:
        pytest.skip("no city pages exist on this env")
    slug = rows[0].get("slug")
    if not slug:
        pytest.skip("no slug field")
    r2 = requests.get(f"{BASE_URL}/api/shop/city-page/{slug}", timeout=30)
    assert r2.status_code == 200
    body = r2.json()
    # field may be empty string but must be present in output schema
    assert "hidden_seo_keywords" in body, f"hidden_seo_keywords missing in {list(body.keys())[:20]}"

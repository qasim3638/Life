"""Live HTTP tests for the Stealth-Keyword Performance Digest endpoints.
Hits the preview backend using REACT_APP_BACKEND_URL. Admin credentials
from /app/memory/test_credentials.md. Safe to re-run — only toggles
settings; does not send real emails unless recipients are configured
(we only use empty recipients OR intentionally stamp a test recipient
that silently fails at Resend).
"""
import os
import pytest
import requests


def _read_frontend_env_url() -> str:
    with open("/app/frontend/.env") as f:
        for line in f:
            line = line.strip()
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().strip('"').rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not found")


BASE_URL = _read_frontend_env_url()
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text[:200]}"
    token = r.json().get("token") or r.json().get("access_token")
    assert token, f"No token in login response: {r.json()}"
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def anon_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ──── RBAC ────

def test_get_settings_anon_forbidden(anon_session):
    r = anon_session.get(f"{BASE_URL}/api/admin/seo/stealth-keywords/digest/settings", timeout=20)
    assert r.status_code in (401, 403), f"Expected 401/403 got {r.status_code}"


def test_put_settings_anon_forbidden(anon_session):
    r = anon_session.put(f"{BASE_URL}/api/admin/seo/stealth-keywords/digest/settings", json={"enabled": True}, timeout=20)
    assert r.status_code in (401, 403)


def test_send_now_anon_forbidden(anon_session):
    r = anon_session.post(f"{BASE_URL}/api/admin/seo/stealth-keywords/digest/send-now", json={}, timeout=20)
    assert r.status_code in (401, 403)


# ──── GET /digest/settings ────

def test_get_settings_returns_shape(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/admin/seo/stealth-keywords/digest/settings", timeout=20)
    assert r.status_code == 200
    body = r.json()
    for key in ("enabled", "recipients", "last_sent_at", "last_sent_snapshot", "id"):
        assert key in body, f"missing key {key} in {body}"
    assert isinstance(body["enabled"], bool)
    assert isinstance(body["recipients"], list)
    assert body["id"] == "main"


# ──── PUT /digest/settings ────

def test_put_toggle_enabled_round_trip(admin_session):
    # disable
    r = admin_session.put(
        f"{BASE_URL}/api/admin/seo/stealth-keywords/digest/settings",
        json={"enabled": False}, timeout=20,
    )
    assert r.status_code == 200
    assert r.json()["enabled"] is False
    # re-enable (leave enabled=True at end per request)
    r = admin_session.put(
        f"{BASE_URL}/api/admin/seo/stealth-keywords/digest/settings",
        json={"enabled": True}, timeout=20,
    )
    assert r.status_code == 200
    assert r.json()["enabled"] is True


def test_put_recipients_whitelist_and_cap(admin_session):
    # Snapshot current recipients to restore
    initial = admin_session.get(f"{BASE_URL}/api/admin/seo/stealth-keywords/digest/settings", timeout=20).json()
    original_recipients = initial.get("recipients") or []
    try:
        # Send mix of valid emails + garbage + way-over-cap count
        dirty = [f"TEST_x{i}@example.com" for i in range(15)] + ["garbage", "no_at_sign", ""]
        r = admin_session.put(
            f"{BASE_URL}/api/admin/seo/stealth-keywords/digest/settings",
            json={"recipients": dirty}, timeout=20,
        )
        assert r.status_code == 200
        body = r.json()
        # Capped at 10, no garbage, all contain @
        assert len(body["recipients"]) == 10
        for email in body["recipients"]:
            assert "@" in email
            assert email.startswith("TEST_")
    finally:
        # Restore
        admin_session.put(
            f"{BASE_URL}/api/admin/seo/stealth-keywords/digest/settings",
            json={"recipients": original_recipients}, timeout=20,
        )


def test_put_recipients_as_raw_string_returns_422(admin_session):
    # Backend expects list[str]; raw str must fail Pydantic validation
    r = admin_session.put(
        f"{BASE_URL}/api/admin/seo/stealth-keywords/digest/settings",
        json={"recipients": "a@b.com, c@d.com"}, timeout=20,
    )
    assert r.status_code == 422


def test_put_empty_patch_idempotent(admin_session):
    r = admin_session.put(
        f"{BASE_URL}/api/admin/seo/stealth-keywords/digest/settings",
        json={}, timeout=20,
    )
    # Should return current settings without error (allowed dict is empty → returns get_settings())
    assert r.status_code == 200
    body = r.json()
    assert "enabled" in body


# ──── POST /digest/send-now ────

def test_send_now_no_recipients_returns_no_recipients(admin_session):
    """With empty recipients + no ADMIN_EMAIL env, send-now must not
    actually dispatch — it returns {ok:false, reason:no_recipients}.
    Safe to execute against live DB.
    """
    # Snapshot and clear recipients
    initial = admin_session.get(f"{BASE_URL}/api/admin/seo/stealth-keywords/digest/settings", timeout=20).json()
    original_recipients = initial.get("recipients") or []
    try:
        admin_session.put(
            f"{BASE_URL}/api/admin/seo/stealth-keywords/digest/settings",
            json={"recipients": []}, timeout=20,
        )
        r = admin_session.post(
            f"{BASE_URL}/api/admin/seo/stealth-keywords/digest/send-now",
            json={}, timeout=60,
        )
        assert r.status_code == 200, f"expected 200 got {r.status_code}: {r.text[:200]}"
        body = r.json()
        # Either {ok:false, reason:no_recipients} when ADMIN_EMAIL not set,
        # OR {ok:true/false, recipients:[ADMIN_EMAIL]} when env is set
        if body.get("reason") == "no_recipients":
            assert body["ok"] is False
        else:
            # env ADMIN_EMAIL is set on prod — still safe because recipients come from env
            assert "recipients" in body and isinstance(body["recipients"], list)
            assert "subject" in body
            assert "snapshot" in body
    finally:
        admin_session.put(
            f"{BASE_URL}/api/admin/seo/stealth-keywords/digest/settings",
            json={"recipients": original_recipients}, timeout=20,
        )

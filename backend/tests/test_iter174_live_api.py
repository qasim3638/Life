"""
Iter 174 live API smoke tests:
- Lifetime savings (admin only)
- Web push (public /api/push/* and admin /api/admin/push/*)
- Bot traffic cleanup (admin only, dry-run + actual)
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://feature-verification-7.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def admin_token():
    for path in ("/api/auth/login", "/api/admin/login"):
        r = requests.post(
            f"{BASE_URL}{path}",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=20,
        )
        if r.status_code == 200:
            data = r.json()
            tok = data.get("token") or data.get("access_token") or (data.get("data") or {}).get("token")
            if tok:
                return tok
    pytest.skip("Admin auth failed on both /api/auth/login and /api/admin/login")


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# -------- Lifetime Savings --------
class TestLifetimeSavings:
    PATH = "/api/admin/seo/stealth-keywords/lifetime-savings"

    def test_anon_forbidden(self):
        r = requests.get(f"{BASE_URL}{self.PATH}", timeout=20)
        assert r.status_code in (401, 403), f"expected 401/403 got {r.status_code}"

    def test_admin_200_and_schema(self, admin_headers):
        r = requests.get(f"{BASE_URL}{self.PATH}", headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("currency") == "GBP"
        totals = data.get("totals") or {}
        for k in ("agency_equivalent_gbp", "actual_ai_spend_gbp", "net_savings_gbp",
                  "per_day_savings_gbp", "monthly_run_rate_gbp", "days_running"):
            assert k in totals, f"missing totals.{k}"
            assert isinstance(totals[k], (int, float)), f"totals.{k} not numeric"
        bd = data.get("breakdown")
        assert isinstance(bd, list) and len(bd) == 6, f"expected 6 breakdown rows got {len(bd) if isinstance(bd, list) else 'n/a'}"


# -------- Web Push public --------
FAKE_SUB = {
    "endpoint": "https://fcm.googleapis.com/fcm/send/iter174-test-endpoint",
    "keys": {
        "p256dh": "BN6n+YN3iQAj3kEHbN3Q6BSpVKBXRdHXKJOhwLNpLiRN",
        "auth": "ceFm1UpYKVqvEJqS+tF8IA==",
    },
}


class TestWebPushPublic:
    def test_config_public(self):
        r = requests.get(f"{BASE_URL}/api/push/config", timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "public_key" in data
        assert "subject" in data
        assert isinstance(data["public_key"], str) and len(data["public_key"]) > 10

    def test_subscribe_ok(self):
        r = requests.post(f"{BASE_URL}/api/push/subscribe", json={"subscription": FAKE_SUB}, timeout=20)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

    def test_subscribe_idempotent(self):
        payload = {"subscription": FAKE_SUB}
        r1 = requests.post(f"{BASE_URL}/api/push/subscribe", json=payload, timeout=20)
        r2 = requests.post(f"{BASE_URL}/api/push/subscribe", json=payload, timeout=20)
        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.json().get("ok") is True and r2.json().get("ok") is True

    def test_unsubscribe_ok(self):
        r = requests.post(
            f"{BASE_URL}/api/push/unsubscribe",
            json={"endpoint": FAKE_SUB["endpoint"]},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True


# -------- Web Push admin --------
class TestWebPushAdmin:
    def test_stats_anon_forbidden(self):
        r = requests.get(f"{BASE_URL}/api/admin/push/stats", timeout=20)
        assert r.status_code in (401, 403)

    def test_stats_admin(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/push/stats", headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("configured", "public_key", "active_subscribers", "total_subscribers_lifetime", "last_broadcast"):
            assert k in d, f"missing stats.{k}"

    def test_broadcast_validation_title(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/admin/push/broadcast",
            headers=admin_headers,
            json={"title": "", "body": "hello"},
            timeout=20,
        )
        assert r.status_code in (400, 422), r.text

    def test_broadcast_validation_body_too_long(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/admin/push/broadcast",
            headers=admin_headers,
            json={"title": "ok", "body": "x" * 241},
            timeout=20,
        )
        assert r.status_code in (400, 422), r.text

    def test_broadcast_ok(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/admin/push/broadcast",
            headers=admin_headers,
            json={"title": "Iter174 smoke", "body": "Hello from test"},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("sent", "failed", "expired", "total_targets"):
            assert k in d, f"missing broadcast.{k}"
            assert isinstance(d[k], int)

    def test_history_admin(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/push/history", headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert isinstance(d, list) or (isinstance(d, dict) and ("history" in d or "rows" in d))


# -------- Bot traffic cleanup --------
class TestBotCleanup:
    def test_anon_forbidden(self):
        r = requests.post(f"{BASE_URL}/api/website/cleanup-bot-traffic?dry_run=true", timeout=20)
        assert r.status_code in (401, 403)

    def test_dry_run_ok(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/website/cleanup-bot-traffic?dry_run=true",
            headers=admin_headers,
            timeout=30,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        # count should be present, nothing deleted
        assert any(k in d for k in ("matched", "count", "total", "would_delete"))

    def test_actual_delete_ok(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/website/cleanup-bot-traffic?dry_run=false",
            headers=admin_headers,
            timeout=60,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert any(k in d for k in ("deleted", "count", "removed"))

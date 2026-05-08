"""Backend tests for new features:
- Public status page (/api/website/status, /uptime)
- Promo banner schedule fields
- Marketing studio lifestyle endpoint validation
- Bulletproof shield on additional public endpoints
"""
import os
import pytest
import requests
from datetime import datetime, timedelta, timezone

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://feature-verification-7.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASS = "admin123"


@pytest.fixture(scope="module")
def admin_token():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code} {r.text[:200]}")
    tok = r.json().get("access_token") or r.json().get("token")
    if not tok:
        pytest.skip(f"No token: {r.json()}")
    return tok


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# -------------------- Public status --------------------

class TestPublicStatus:
    def test_status_shape(self):
        r = requests.get(f"{BASE_URL}/api/website/status", timeout=20)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert "overall" in data
        assert "services" in data
        assert "checked_at" in data
        assert isinstance(data["services"], list)
        # 8 known services
        assert len(data["services"]) == 8, f"expected 8 services, got {len(data['services'])}"
        for s in data["services"]:
            assert "name" in s
            assert "status" in s

    def test_uptime_shape(self):
        r = requests.get(f"{BASE_URL}/api/website/status/uptime?days=7", timeout=20)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert data.get("days") == 7
        assert isinstance(data.get("services"), list)
        assert len(data["services"]) == 8
        for s in data["services"]:
            assert "name" in s
            assert "uptime_percent" in s
            assert "incidents" in s


# -------------------- Promo banner schedule --------------------

class TestPromoBannerSchedule:
    @pytest.fixture(autouse=True)
    def _save_state(self, admin_headers):
        # Save current promo banner state and restore at end
        r = requests.get(f"{BASE_URL}/api/admin/marketing-studio/promo-banner", headers=admin_headers, timeout=15)
        self._original = r.json() if r.status_code == 200 else None
        yield
        if self._original:
            restore = {
                "enabled": self._original.get("enabled", False),
                "schedule_enabled": self._original.get("schedule_enabled", False),
                "scheduled_start": self._original.get("scheduled_start"),
                "scheduled_end": self._original.get("scheduled_end"),
            }
            requests.put(f"{BASE_URL}/api/admin/marketing-studio/promo-banner",
                         json=restore, headers=admin_headers, timeout=15)

    def test_schedule_persists_via_admin_get(self, admin_headers):
        future_start = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
        future_end = (datetime.now(timezone.utc) + timedelta(days=20)).isoformat()
        payload = {
            "enabled": False,
            "schedule_enabled": True,
            "scheduled_start": future_start,
            "scheduled_end": future_end,
        }
        r = requests.put(f"{BASE_URL}/api/admin/marketing-studio/promo-banner",
                         json=payload, headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text[:300]
        # GET admin
        g = requests.get(f"{BASE_URL}/api/admin/marketing-studio/promo-banner", headers=admin_headers, timeout=15)
        assert g.status_code == 200
        gd = g.json()
        assert gd.get("schedule_enabled") is True
        assert gd.get("scheduled_start") == future_start
        assert gd.get("scheduled_end") == future_end

    def test_future_schedule_returns_disabled_publicly(self, admin_headers):
        # Future schedule, manual=false → public should report enabled:false
        future_start = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
        future_end = (datetime.now(timezone.utc) + timedelta(days=20)).isoformat()
        requests.put(f"{BASE_URL}/api/admin/marketing-studio/promo-banner",
                     json={"enabled": False, "schedule_enabled": True,
                           "scheduled_start": future_start, "scheduled_end": future_end},
                     headers=admin_headers, timeout=15)
        # bust cache by waiting beyond short_ttl=15
        import time as _t; _t.sleep(16)
        p = requests.get(f"{BASE_URL}/api/website/promo-banner", timeout=15)
        assert p.status_code == 200
        assert p.json().get("enabled") is False

    def test_active_window_overrides_manual_off(self, admin_headers):
        # Window covers now, manual=false → schedule turns banner ON
        # First check there is an image_url; if not we can't expect enabled:true
        admin_get = requests.get(f"{BASE_URL}/api/admin/marketing-studio/promo-banner",
                                 headers=admin_headers, timeout=15).json()
        if not admin_get.get("image_url"):
            pytest.skip("No image_url on promo banner; can't verify scheduled-on without image")
        start = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        end = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        r = requests.put(f"{BASE_URL}/api/admin/marketing-studio/promo-banner",
                         json={"enabled": False, "schedule_enabled": True,
                               "scheduled_start": start, "scheduled_end": end},
                         headers=admin_headers, timeout=15)
        assert r.status_code == 200
        import time as _t; _t.sleep(16)
        p = requests.get(f"{BASE_URL}/api/website/promo-banner", timeout=15)
        assert p.status_code == 200
        assert p.json().get("enabled") is True, f"Expected enabled:true within window, got {p.json()}"


# -------------------- Lifestyle endpoint validation --------------------

class TestLifestyleValidation:
    def test_requires_admin_auth(self):
        r = requests.post(f"{BASE_URL}/api/admin/marketing-studio/lifestyle",
                          json={"tile_id": "no_such_tile", "room_type": "bathroom"}, timeout=20)
        # 403 without auth (or 401)
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"

    def test_404_for_missing_tile(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/admin/marketing-studio/lifestyle",
                          json={"tile_id": "no_such_tile_xyz", "room_type": "bathroom"},
                          headers=admin_headers, timeout=20)
        assert r.status_code == 404, f"expected 404, got {r.status_code} {r.text[:200]}"

    def test_422_for_bad_room_type(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/admin/marketing-studio/lifestyle",
                          json={"tile_id": "69b7f50064c2cc7794de86de", "room_type": "garage"},
                          headers=admin_headers, timeout=20)
        assert r.status_code == 422, f"expected 422, got {r.status_code} {r.text[:200]}"


# -------------------- Bulletproof public endpoints --------------------

class TestBulletproofPublicEndpoints:
    @pytest.mark.parametrize("path", [
        "/api/website-admin/public/hero-slides",
        "/api/website-admin/public/categories",
        "/api/website-admin/public/navigation/main",
        "/api/website-admin/public/announcement-ribbon",
    ])
    def test_endpoint_returns_200(self, path):
        r = requests.get(f"{BASE_URL}{path}", timeout=20)
        assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:200]}"

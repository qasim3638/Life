"""SEO Autopilot — backend integration tests."""
import os
import requests
import pytest

BASE_URL = os.environ.get("BACKEND_BASE_URL", "https://feature-verification-7.preview.emergentagent.com")


@pytest.fixture
def admin_headers():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "admin@test.com", "password": "admin123"},
        timeout=30,
    )
    assert r.status_code == 200
    token = r.json().get("access_token") or r.json().get("token")
    return {"Authorization": f"Bearer {token}"}


class TestWebVitalsBeacon:
    def test_beacon_accepts_payload(self):
        r = requests.post(
            f"{BASE_URL}/api/health/web-vitals",
            json={"path": "/tiles/test", "lcp_ms": 1500, "inp_ms": 100, "cls": 0.05},
            timeout=15,
        )
        assert r.status_code == 200
        assert r.json().get("ok") is True

    def test_beacon_skips_admin_paths(self):
        r = requests.post(
            f"{BASE_URL}/api/health/web-vitals",
            json={"path": "/admin/dashboard", "lcp_ms": 2000},
            timeout=15,
        )
        assert r.status_code == 200
        assert r.json().get("skipped") is True

    def test_beacon_drops_garbage_values(self):
        # Out-of-bounds LCP should be dropped silently — no 500
        r = requests.post(
            f"{BASE_URL}/api/health/web-vitals",
            json={"path": "/tiles/abc", "lcp_ms": 999999, "cls": 99},
            timeout=15,
        )
        assert r.status_code == 200


class TestAutopilotRoutes:
    def test_summary_requires_admin(self):
        r = requests.get(f"{BASE_URL}/api/admin/seo-autopilot/summary", timeout=15)
        assert r.status_code in (401, 403)

    def test_summary_returns_counters(self, admin_headers):
        r = requests.get(
            f"{BASE_URL}/api/admin/seo-autopilot/summary",
            headers=admin_headers, timeout=15,
        )
        assert r.status_code == 200
        for k in (
            "actions_total", "canonical_overrides", "redirects",
            "brand_serp_snapshots", "stale_pages_marked",
        ):
            assert k in r.json()

    def test_actions_endpoint_returns_list(self, admin_headers):
        r = requests.get(
            f"{BASE_URL}/api/admin/seo-autopilot/actions?limit=10",
            headers=admin_headers, timeout=15,
        )
        assert r.status_code == 200
        assert isinstance(r.json().get("actions"), list)

    def test_run_unknown_job_404s(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/admin/seo-autopilot/run/wibble",
            headers=admin_headers, timeout=15,
        )
        assert r.status_code == 404


class TestAutopilotJobs:
    """Each job must complete cleanly (200) — even when GSC isn't connected
    or there's no data. The point is: no crashes in production."""

    @pytest.mark.parametrize("job", [
        "cannibalization", "404", "stale", "brand_serp", "algo",
        "web_vitals_aggregate", "web_vitals_alert",
    ])
    def test_job_runs_without_crashing(self, admin_headers, job):
        r = requests.post(
            f"{BASE_URL}/api/admin/seo-autopilot/run/{job}",
            headers=admin_headers, timeout=120,
        )
        assert r.status_code == 200, f"{job} failed: {r.status_code} {r.text}"
        data = r.json()
        # Either OK with results or skipped with a reason.
        assert data.get("ok") is True

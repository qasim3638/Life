"""Marketing Studio backend tests.

Covers:
- generate (1 real nano-banana call, smallest size)
- public marketing-media serve
- list / filter / stats
- publish to promo_banner + homepage_hero
- toggle promo_banner off and confirm public API reflects
- delete (soft-delete)
- validation errors (invalid model, small width, no auth)
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://feature-verification-7.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"

# Known asset from main agent context (1200x300 nano-banana, already published)
EXISTING_ASSET_ID = "63e17e3a615347f1b2d78ef0129ab278"


@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def generated_asset(admin_headers):
    """One real Nano Banana 512x512 call — shared across tests."""
    payload = {
        "prompt": "A minimal UK tile shop promo banner, gold text 'Test Only', marble background, magazine photography.",
        "model": "nano-banana",
        "width": 512,
        "height": 512,
        "preset": "ribbon",
        "asset_kind": "ribbon",
    }
    r = requests.post(f"{API}/admin/marketing-studio/generate", headers=admin_headers, json=payload, timeout=120)
    assert r.status_code == 200, f"generate failed: {r.status_code} {r.text[:300]}"
    data = r.json()
    assert "asset" in data
    return data["asset"]


# ---------------- Generate ----------------

class TestGenerate:
    def test_generate_returns_asset(self, generated_asset):
        a = generated_asset
        assert "id" in a and len(a["id"]) > 0
        assert a["model"] == "nano-banana"
        assert a["width"] == 512 and a["height"] == 512
        assert a["cost_usd"] > 0
        assert a["image_url"].startswith("/api/website/marketing-media/")
        assert a["prompt"]

    def test_generate_invalid_model(self, admin_headers):
        r = requests.post(f"{API}/admin/marketing-studio/generate", headers=admin_headers, json={
            "prompt": "test prompt for banner image generation",
            "model": "dall-e-9000",
            "width": 512, "height": 512,
        }, timeout=30)
        assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text[:200]}"

    def test_generate_width_too_small(self, admin_headers):
        r = requests.post(f"{API}/admin/marketing-studio/generate", headers=admin_headers, json={
            "prompt": "test prompt for banner image generation",
            "model": "nano-banana",
            "width": 100, "height": 512,
        }, timeout=30)
        assert r.status_code == 422

    def test_generate_without_auth(self):
        r = requests.post(f"{API}/admin/marketing-studio/generate", json={
            "prompt": "test prompt for banner image generation",
            "model": "nano-banana",
            "width": 512, "height": 512,
        }, timeout=30)
        # 401/403 both acceptable for no auth
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"


# ---------------- Public media serve ----------------

class TestPublicMedia:
    def test_serve_png(self, generated_asset):
        asset_id = generated_asset["id"]
        r = requests.get(f"{API}/website/marketing-media/{asset_id}.png", timeout=30)
        assert r.status_code == 200, f"serve failed: {r.status_code}"
        assert r.headers.get("content-type", "").startswith("image/"), f"content-type: {r.headers.get('content-type')}"
        assert len(r.content) > 1000, "image too small"


# ---------------- List / filter / stats ----------------

class TestListAndStats:
    def test_list_contains_generated(self, admin_headers, generated_asset):
        r = requests.get(f"{API}/admin/marketing-studio/assets", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "assets" in data and isinstance(data["assets"], list)
        ids = [a["id"] for a in data["assets"]]
        assert generated_asset["id"] in ids

    def test_filter_ribbon(self, admin_headers, generated_asset):
        r = requests.get(f"{API}/admin/marketing-studio/assets?kind=ribbon", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        data = r.json()
        # all returned assets must be kind=ribbon
        for a in data["assets"]:
            assert a.get("asset_kind") == "ribbon", f"non-ribbon leaked: {a.get('asset_kind')}"
        assert generated_asset["id"] in [a["id"] for a in data["assets"]]

    def test_stats(self, admin_headers):
        r = requests.get(f"{API}/admin/marketing-studio/stats", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "total_assets" in d and d["total_assets"] >= 1
        assert "total_spend_usd" in d and d["total_spend_usd"] >= 0


# ---------------- Publish + public promo banner ----------------

class TestPublish:
    def test_publish_to_promo_banner(self, admin_headers, generated_asset):
        asset_id = generated_asset["id"]
        r = requests.post(
            f"{API}/admin/marketing-studio/assets/{asset_id}/publish",
            headers=admin_headers,
            json={"placement": "promo_banner", "link_url": "/shop/sale"},
            timeout=30,
        )
        assert r.status_code == 200, f"publish failed: {r.status_code} {r.text[:200]}"
        assert r.json().get("placement") == "promo_banner"

        # Public read confirms enabled + image_url
        pr = requests.get(f"{API}/website/promo-banner", timeout=30)
        assert pr.status_code == 200
        p = pr.json()
        assert p.get("enabled") is True
        assert p.get("image_url")
        assert p.get("image_url") == generated_asset["image_url"]

    def test_publish_to_homepage_hero(self, admin_headers, generated_asset):
        asset_id = generated_asset["id"]
        r = requests.post(
            f"{API}/admin/marketing-studio/assets/{asset_id}/publish",
            headers=admin_headers,
            json={"placement": "homepage_hero", "cta_text": "Shop Sale"},
            timeout=30,
        )
        assert r.status_code == 200, f"hero publish failed: {r.status_code} {r.text[:200]}"
        assert r.json().get("placement") == "homepage_hero"

    def test_toggle_promo_banner_off(self, admin_headers):
        r = requests.put(
            f"{API}/admin/marketing-studio/promo-banner",
            headers=admin_headers,
            json={"enabled": False},
            timeout=30,
        )
        assert r.status_code == 200
        # Public API should now return enabled:false (assuming schedule off)
        pr = requests.get(f"{API}/website/promo-banner", timeout=30)
        assert pr.status_code == 200
        assert pr.json().get("enabled") is False


# ---------------- Delete (soft-delete) ----------------

class TestDelete:
    def test_soft_delete_generated(self, admin_headers, generated_asset):
        asset_id = generated_asset["id"]
        r = requests.delete(f"{API}/admin/marketing-studio/assets/{asset_id}", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        # verify not in list
        lr = requests.get(f"{API}/admin/marketing-studio/assets?limit=500", headers=admin_headers, timeout=30)
        ids = [a["id"] for a in lr.json().get("assets", [])]
        assert asset_id not in ids, "soft-deleted asset still returned in list"

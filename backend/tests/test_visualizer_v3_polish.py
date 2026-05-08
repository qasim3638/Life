"""Tests for V3 Polish: Visualizer Pricing config, Share tokens, Launch email."""
import os
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://feature-verification-7.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASS = "admin123"
SAMPLE_ROOM = "vis_room_kitchen_floor"
TILE_ID = "69b7f50064c2cc7794de86de"

DEFAULTS = {
    "adhesive_price_per_bag": 18.50,
    "grout_price_per_bag": 9.99,
    "wastage_percent": 10,
    "floor_m2_per_adhesive_bag": 4.0,
    "wall_m2_per_adhesive_bag": 5.0,
    "m2_per_grout_bag": 11.0,
}


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code} {r.text[:200]}")
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def H(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# --- Pricing GET/PUT ---
class TestPricing:
    def test_get_pricing(self, H):
        r = requests.get(f"{BASE}/api/admin/visualizer/pricing", headers=H, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "pricing" in d and "defaults" in d
        for k in DEFAULTS:
            assert k in d["pricing"]
            assert k in d["defaults"]

    def test_put_pricing_persists(self, H):
        new = {"adhesive_price_per_bag": 22.75, "grout_price_per_bag": 12.50,
               "wastage_percent": 12, "floor_m2_per_adhesive_bag": 4.5,
               "wall_m2_per_adhesive_bag": 5.5, "m2_per_grout_bag": 10.5}
        r = requests.put(f"{BASE}/api/admin/visualizer/pricing", json=new, headers=H, timeout=30)
        assert r.status_code == 200, r.text
        # Verify GET round-trips
        g = requests.get(f"{BASE}/api/admin/visualizer/pricing", headers=H, timeout=30).json()["pricing"]
        for k, v in new.items():
            assert float(g[k]) == float(v), f"{k}: got {g[k]}, expected {v}"

    def test_pricing_bounds(self, H):
        # wastage capped at 50, prices floored at 0.5
        r = requests.put(f"{BASE}/api/admin/visualizer/pricing",
                         json={"wastage_percent": 999, "adhesive_price_per_bag": 0.01,
                               "grout_price_per_bag": -5},
                         headers=H, timeout=30)
        assert r.status_code == 200, r.text
        p = r.json()["pricing"]
        assert p["wastage_percent"] == 50
        assert p["adhesive_price_per_bag"] == 0.5
        assert p["grout_price_per_bag"] == 0.5

    def test_quote_uses_admin_pricing(self, H):
        # Set custom pricing
        custom = {"adhesive_price_per_bag": 25.00, "grout_price_per_bag": 14.00,
                  "wastage_percent": 15, "floor_m2_per_adhesive_bag": 4.0,
                  "wall_m2_per_adhesive_bag": 5.0, "m2_per_grout_bag": 11.0}
        requests.put(f"{BASE}/api/admin/visualizer/pricing", json=custom, headers=H, timeout=30)
        # Create session
        s = requests.post(f"{BASE}/api/visualizer/sessions", headers=H,
                          json={"sample_room_id": SAMPLE_ROOM, "tile_id": TILE_ID}, timeout=30)
        assert s.status_code == 200, s.text
        sid = s.json()["session_id"]
        q = requests.post(f"{BASE}/api/visualizer/sessions/{sid}/quote", headers=H, json={}, timeout=30)
        assert q.status_code == 200, q.text
        qd = q.json()
        assert qd["adhesive_price_per_bag"] == 25.00
        assert qd["grout_price_per_bag"] == 14.00
        assert qd["wastage_percent"] == 15


# --- Share tokens ---
class TestShare:
    def test_existing_share_token_public(self):
        # Try the known good token first
        r = requests.get(f"{BASE}/api/visualizer/share/40575bba2fb941", timeout=30)
        if r.status_code == 200:
            d = r.json()
            assert "tile" in d and "result_url" in d
            assert d.get("room_label") is not None
        else:
            pytest.skip(f"Known share token returned {r.status_code}")

    def test_bad_share_token_404(self):
        r = requests.get(f"{BASE}/api/visualizer/share/badbadbadbad", timeout=30)
        assert r.status_code == 404

    def test_create_share_no_render_404(self, H):
        # Create a fresh session with no render → share should 404
        s = requests.post(f"{BASE}/api/visualizer/sessions", headers=H,
                          json={"sample_room_id": SAMPLE_ROOM, "tile_id": TILE_ID}, timeout=30)
        assert s.status_code == 200
        sid = s.json()["session_id"]
        r = requests.post(f"{BASE}/api/visualizer/sessions/{sid}/share", headers=H, json={}, timeout=30)
        assert r.status_code == 404, r.text

    def test_share_idempotent_and_public_get(self, H):
        # Create session + a fast render so we can share
        s = requests.post(f"{BASE}/api/visualizer/sessions", headers=H,
                          json={"sample_room_id": SAMPLE_ROOM, "tile_id": TILE_ID}, timeout=30)
        sid = s.json()["session_id"]
        rr = requests.post(f"{BASE}/api/visualizer/sessions/{sid}/render", headers=H,
                           json={"style": "fast"}, timeout=120)
        if rr.status_code != 200:
            pytest.skip(f"Fast render failed: {rr.status_code} {rr.text[:200]}")
        # First share
        sh1 = requests.post(f"{BASE}/api/visualizer/sessions/{sid}/share", headers=H, json={}, timeout=30)
        assert sh1.status_code == 200, sh1.text
        t1 = sh1.json()["share_token"]
        assert sh1.json()["share_url"].endswith(t1)
        # Second share — idempotent
        sh2 = requests.post(f"{BASE}/api/visualizer/sessions/{sid}/share", headers=H, json={}, timeout=30)
        assert sh2.status_code == 200
        assert sh2.json()["share_token"] == t1
        # Public GET (no auth)
        pub = requests.get(f"{BASE}/api/visualizer/share/{t1}", timeout=30)
        assert pub.status_code == 200, pub.text
        d = pub.json()
        assert d["tile"]["name"] is not None
        assert d["result_url"] is not None
        assert d["room_label"] is not None
        # View count increment — fetch once more and confirm no error
        pub2 = requests.get(f"{BASE}/api/visualizer/share/{t1}", timeout=30)
        assert pub2.status_code == 200


# --- Launch email ---
class TestLaunchEmail:
    def test_dry_run(self, H):
        r = requests.post(f"{BASE}/api/admin/visualizer/waitlist/send-launch-email",
                          json={"dry_run": True}, headers=H, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        # Either there are unnotified or response is empty
        if "would_send" in d:
            assert d.get("dry_run") is True
            assert "recipients_preview" in d
            assert isinstance(d["recipients_preview"], list)
        else:
            assert d.get("sent") == 0


# --- Reset to defaults ---
class TestZZReset:
    def test_reset_pricing_to_defaults(self, H):
        r = requests.put(f"{BASE}/api/admin/visualizer/pricing", json=DEFAULTS, headers=H, timeout=30)
        assert r.status_code == 200
        g = requests.get(f"{BASE}/api/admin/visualizer/pricing", headers=H, timeout=30).json()["pricing"]
        for k, v in DEFAULTS.items():
            assert float(g[k]) == float(v)

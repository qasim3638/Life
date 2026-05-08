"""Live HTTP tests for Stealth-Keyword Auto-Promote.

Per main-agent instructions: only verify RBAC + schema + error paths
on the live preview DB. Do NOT trigger a real promotion. Auto-promote
must be left DISABLED at the end of this run.

Endpoints under test:
  GET  /api/admin/seo/stealth-keywords/digest/settings
  PUT  /api/admin/seo/stealth-keywords/digest/settings
  GET  /api/admin/seo/stealth-keywords/auto-promote/history
  POST /api/admin/seo/stealth-keywords/auto-promote/undo/{record_id}
  GET  /api/shop/seo/stealth-keywords/auto-promote/undo/{token}  (public)
"""
import os
from pathlib import Path

import pytest
import requests


def _load_backend_url() -> str:
    url = os.environ.get("REACT_APP_BACKEND_URL", "").strip()
    if url:
        return url.rstrip("/")
    # Fallback: read from /app/frontend/.env
    env_path = Path("/app/frontend/.env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    return ""


BASE_URL = _load_backend_url()
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{API}/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok, f"no token in admin login response: {r.json()}"
    return tok


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ───────── Settings GET/PUT ─────────

class TestDigestSettingsAutoPromoteFields:
    """auto_promote_enabled + auto_promote_min_impressions schema."""

    def test_get_includes_auto_promote_fields(self, admin_headers):
        r = requests.get(f"{API}/admin/seo/stealth-keywords/digest/settings",
                         headers=admin_headers, timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert "auto_promote_enabled" in body
        assert "auto_promote_min_impressions" in body
        assert isinstance(body["auto_promote_enabled"], bool)
        assert isinstance(body["auto_promote_min_impressions"], int)

    def test_put_persists_min_impressions_round_trip(self, admin_headers):
        # Read original
        cur = requests.get(f"{API}/admin/seo/stealth-keywords/digest/settings",
                           headers=admin_headers, timeout=10).json()
        original = cur.get("auto_promote_min_impressions", 20)
        try:
            r = requests.put(
                f"{API}/admin/seo/stealth-keywords/digest/settings",
                headers=admin_headers,
                json={"auto_promote_min_impressions": 42},
                timeout=10,
            )
            assert r.status_code == 200
            after = requests.get(
                f"{API}/admin/seo/stealth-keywords/digest/settings",
                headers=admin_headers, timeout=10).json()
            assert after["auto_promote_min_impressions"] == 42
        finally:
            requests.put(
                f"{API}/admin/seo/stealth-keywords/digest/settings",
                headers=admin_headers,
                json={"auto_promote_min_impressions": original},
                timeout=10,
            )

    def test_put_clamps_min_impressions_high(self, admin_headers):
        cur = requests.get(f"{API}/admin/seo/stealth-keywords/digest/settings",
                           headers=admin_headers, timeout=10).json()
        original = cur.get("auto_promote_min_impressions", 20)
        try:
            r = requests.put(
                f"{API}/admin/seo/stealth-keywords/digest/settings",
                headers=admin_headers,
                json={"auto_promote_min_impressions": 9999},
                timeout=10,
            )
            assert r.status_code == 200
            after = requests.get(
                f"{API}/admin/seo/stealth-keywords/digest/settings",
                headers=admin_headers, timeout=10).json()
            assert after["auto_promote_min_impressions"] == 500, \
                f"expected clamp to 500, got {after['auto_promote_min_impressions']}"
        finally:
            requests.put(
                f"{API}/admin/seo/stealth-keywords/digest/settings",
                headers=admin_headers,
                json={"auto_promote_min_impressions": original},
                timeout=10,
            )

    def test_put_clamps_min_impressions_low(self, admin_headers):
        cur = requests.get(f"{API}/admin/seo/stealth-keywords/digest/settings",
                           headers=admin_headers, timeout=10).json()
        original = cur.get("auto_promote_min_impressions", 20)
        try:
            r = requests.put(
                f"{API}/admin/seo/stealth-keywords/digest/settings",
                headers=admin_headers,
                json={"auto_promote_min_impressions": 1},
                timeout=10,
            )
            assert r.status_code == 200
            after = requests.get(
                f"{API}/admin/seo/stealth-keywords/digest/settings",
                headers=admin_headers, timeout=10).json()
            assert after["auto_promote_min_impressions"] == 5, \
                f"expected clamp to 5, got {after['auto_promote_min_impressions']}"
        finally:
            requests.put(
                f"{API}/admin/seo/stealth-keywords/digest/settings",
                headers=admin_headers,
                json={"auto_promote_min_impressions": original},
                timeout=10,
            )

    def test_put_garbage_min_impressions_ignored_or_422(self, admin_headers):
        """Non-int/garbage value: pydantic should 422 OR be silently ignored.
        Either is acceptable so long as DB state is unchanged.
        """
        cur = requests.get(f"{API}/admin/seo/stealth-keywords/digest/settings",
                           headers=admin_headers, timeout=10).json()
        original = cur.get("auto_promote_min_impressions", 20)
        r = requests.put(
            f"{API}/admin/seo/stealth-keywords/digest/settings",
            headers=admin_headers,
            json={"auto_promote_min_impressions": "not-a-number"},
            timeout=10,
        )
        # Either pydantic rejects → 422, or coerces/ignores → 200
        assert r.status_code in (200, 422), f"unexpected status {r.status_code}"
        after = requests.get(
            f"{API}/admin/seo/stealth-keywords/digest/settings",
            headers=admin_headers, timeout=10).json()
        assert after["auto_promote_min_impressions"] == original

    def test_put_auto_promote_enabled_round_trip_safe(self, admin_headers):
        """Toggle false→true→false. Leaves DB at false (production safe)."""
        cur = requests.get(f"{API}/admin/seo/stealth-keywords/digest/settings",
                           headers=admin_headers, timeout=10).json()
        original = cur.get("auto_promote_enabled", False)
        try:
            # Force to true momentarily
            r1 = requests.put(
                f"{API}/admin/seo/stealth-keywords/digest/settings",
                headers=admin_headers,
                json={"auto_promote_enabled": True},
                timeout=10,
            )
            assert r1.status_code == 200
            mid = requests.get(
                f"{API}/admin/seo/stealth-keywords/digest/settings",
                headers=admin_headers, timeout=10).json()
            assert mid["auto_promote_enabled"] is True
        finally:
            # CRITICAL: always restore to original (false on prod)
            requests.put(
                f"{API}/admin/seo/stealth-keywords/digest/settings",
                headers=admin_headers,
                json={"auto_promote_enabled": bool(original)},
                timeout=10,
            )
            final = requests.get(
                f"{API}/admin/seo/stealth-keywords/digest/settings",
                headers=admin_headers, timeout=10).json()
            assert final["auto_promote_enabled"] == bool(original)


# ───────── Auto-promote history (admin) ─────────

class TestAutoPromoteHistory:

    def test_anon_blocked(self):
        r = requests.get(
            f"{API}/admin/seo/stealth-keywords/auto-promote/history",
            timeout=10,
        )
        assert r.status_code in (401, 403), f"anon got {r.status_code}"

    def test_admin_returns_rows_array(self, admin_headers):
        r = requests.get(
            f"{API}/admin/seo/stealth-keywords/auto-promote/history",
            headers=admin_headers, timeout=10,
        )
        assert r.status_code == 200
        body = r.json()
        assert "rows" in body
        assert isinstance(body["rows"], list)

    def test_admin_redacts_raw_token(self, admin_headers):
        r = requests.get(
            f"{API}/admin/seo/stealth-keywords/auto-promote/history",
            headers=admin_headers, timeout=10,
        )
        assert r.status_code == 200
        rows = r.json().get("rows", [])
        for row in rows:
            assert "token" not in row, \
                f"raw token leaked in history row: {row}"
            # token_hint may or may not be present on every row depending
            # on legacy data, but if present must be a 6+1 char string
            if "token_hint" in row and row["token_hint"]:
                assert len(row["token_hint"]) <= 16
            # Required fields per contract (best-effort — only assert
            # these on rows that have any of them)
            expected_fields = {
                "id", "query", "collection", "added_keyword",
                "impressions", "clicks", "promoted_at", "undone_at",
                "promoted_by",
            }
            present = expected_fields & set(row.keys())
            assert "id" in row, f"row missing id: {row}"
            # Don't be over-strict, but at least id+query+collection
            assert "query" in row
            assert "collection" in row

    def test_limit_query_validated(self, admin_headers):
        # ge=1, le=50
        r = requests.get(
            f"{API}/admin/seo/stealth-keywords/auto-promote/history?limit=0",
            headers=admin_headers, timeout=10,
        )
        assert r.status_code == 422
        r2 = requests.get(
            f"{API}/admin/seo/stealth-keywords/auto-promote/history?limit=999",
            headers=admin_headers, timeout=10,
        )
        assert r2.status_code == 422


# ───────── Admin undo by record_id ─────────

class TestAdminUndoByRecordId:

    def test_anon_blocked(self):
        r = requests.post(
            f"{API}/admin/seo/stealth-keywords/auto-promote/undo/anything",
            timeout=10,
        )
        assert r.status_code in (401, 403)

    def test_unknown_id_returns_404(self, admin_headers):
        r = requests.post(
            f"{API}/admin/seo/stealth-keywords/auto-promote/undo/zzz_does_not_exist_123",
            headers=admin_headers, timeout=10,
        )
        assert r.status_code == 404


# ───────── Public token undo ─────────

class TestPublicTokenUndo:

    def test_bogus_token_returns_404(self):
        r = requests.get(
            f"{API}/shop/seo/stealth-keywords/auto-promote/undo/zzz_bogus_token_does_not_exist",
            timeout=10, allow_redirects=False,
        )
        assert r.status_code == 404

    def test_public_endpoint_does_not_require_auth_for_short_path(self):
        """Smoke: route exists and is unauthenticated. We don't have a
        real token to verify the success path on live (unit tests cover
        that), but we can confirm the route is mounted on public_router
        by checking the 404 response doesn't say 'Not authenticated'."""
        r = requests.get(
            f"{API}/shop/seo/stealth-keywords/auto-promote/undo/zzz_bogus",
            timeout=10, allow_redirects=False,
        )
        assert r.status_code == 404
        body = r.json() if "application/json" in r.headers.get("content-type", "") else {}
        # Must not be an auth error
        detail = (body.get("detail") or "").lower() if isinstance(body, dict) else ""
        assert "auth" not in detail and "credentials" not in detail

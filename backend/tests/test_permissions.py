"""
Test suite for the new Permissions admin module.

Covers:
- GET /api/permissions/registry
- GET /api/permissions/me
- GET /api/permissions/roles (super_admin only)
- POST /api/permissions/roles (create custom role, default OFF, duplicate -> 409)
- PUT /api/permissions/roles/{role_id} (filter invalid keys, super_admin not editable)
- DELETE /api/permissions/roles/{role_id} (system roles -> 400, in-use -> 400)
"""
import os
import time
import pytest
import requests
from pathlib import Path


def _load_backend_url() -> str:
    url = os.environ.get("REACT_APP_BACKEND_URL", "").strip()
    if not url:
        env_path = Path("/app/frontend/.env")
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("REACT_APP_BACKEND_URL="):
                    url = line.split("=", 1)[1].strip()
                    break
    return url.rstrip("/")


BASE_URL = _load_backend_url()
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def admin_token():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if r.status_code != 200:
        pytest.skip(f"Admin login failed ({r.status_code}): {r.text}")
    data = r.json()
    return data["token"]


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


class TestPermissionsRegistry:
    def test_registry_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/permissions/registry")
        assert r.status_code in (401, 403), f"Expected unauthorized, got {r.status_code}"

    def test_registry_returns_pages_and_actions(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/permissions/registry", headers=auth_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "pages" in data and "actions" in data
        assert isinstance(data["pages"], list) and len(data["pages"]) > 50
        assert isinstance(data["actions"], list) and len(data["actions"]) >= 14
        page_keys = {p["key"] for p in data["pages"]}
        assert "permissions_admin" in page_keys
        assert "supplier_products" in page_keys
        action_keys = {a["key"] for a in data["actions"]}
        assert "supplier_products.cost_column" in action_keys
        assert "supplier_products.action.delete" in action_keys
        for p in data["pages"]:
            assert {"key", "label", "group"} <= set(p.keys())


class TestPermissionsMe:
    def test_me_super_admin_has_all(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/permissions/me", headers=auth_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["role"] == "super_admin"
        assert data["is_super_admin"] is True
        # super_admin gets every page key from registry
        reg = requests.get(f"{BASE_URL}/api/permissions/registry", headers=auth_headers).json()
        assert set(data["pages"]) == {p["key"] for p in reg["pages"]}
        assert set(data["actions"]) == {a["key"] for a in reg["actions"]}


class TestRolesList:
    def test_roles_seeds_four_system_roles(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/permissions/roles", headers=auth_headers)
        assert r.status_code == 200, r.text
        roles = r.json()
        ids = {x["role_id"] for x in roles}
        for needed in ("super_admin", "admin", "manager", "staff"):
            assert needed in ids, f"system role missing: {needed}"
        for r_ in roles:
            if r_["role_id"] in {"super_admin", "admin", "manager", "staff"}:
                assert r_["is_system"] is True
            assert "pages" in r_ and "actions" in r_

    def test_super_admin_role_marker(self, auth_headers):
        roles = requests.get(f"{BASE_URL}/api/permissions/roles", headers=auth_headers).json()
        sa = next(r for r in roles if r["role_id"] == "super_admin")
        assert sa["is_super_admin"] is True
        assert sa["is_system"] is True


class TestCustomRoleCRUD:
    test_role_id = f"test_role_{int(time.time())}"

    def test_create_custom_role_defaults_off(self, auth_headers):
        payload = {
            "role_id": self.test_role_id,
            "role_name": "TEST Role",
            "pages": [],
            "actions": [],
        }
        r = requests.post(f"{BASE_URL}/api/permissions/roles", json=payload, headers=auth_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["role_id"] == self.test_role_id
        assert data["pages"] == []
        assert data["actions"] == []
        assert data["is_system"] is False
        assert data["is_super_admin"] is False

        # Verify persisted via list
        roles = requests.get(f"{BASE_URL}/api/permissions/roles", headers=auth_headers).json()
        assert any(x["role_id"] == self.test_role_id for x in roles)

    def test_duplicate_role_id_returns_409(self, auth_headers):
        payload = {"role_id": self.test_role_id, "role_name": "Dup", "pages": [], "actions": []}
        r = requests.post(f"{BASE_URL}/api/permissions/roles", json=payload, headers=auth_headers)
        assert r.status_code == 409, r.text

    def test_update_filters_invalid_keys(self, auth_headers):
        payload = {
            "pages": ["dashboard", "supplier_products", "definitely_not_a_page"],
            "actions": ["supplier_products.cost_column", "fake.action"],
        }
        r = requests.put(
            f"{BASE_URL}/api/permissions/roles/{self.test_role_id}",
            json=payload,
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "definitely_not_a_page" not in data["pages"]
        assert "fake.action" not in data["actions"]
        assert "dashboard" in data["pages"]
        assert "supplier_products" in data["pages"]
        assert "supplier_products.cost_column" in data["actions"]

        # verify persisted via list
        roles = requests.get(f"{BASE_URL}/api/permissions/roles", headers=auth_headers).json()
        rec = next(x for x in roles if x["role_id"] == self.test_role_id)
        assert "dashboard" in rec["pages"]
        assert "supplier_products.cost_column" in rec["actions"]

    def test_cannot_edit_super_admin(self, auth_headers):
        r = requests.put(
            f"{BASE_URL}/api/permissions/roles/super_admin",
            json={"pages": []},
            headers=auth_headers,
        )
        assert r.status_code == 400, r.text

    def test_cannot_delete_system_role(self, auth_headers):
        r = requests.delete(f"{BASE_URL}/api/permissions/roles/admin", headers=auth_headers)
        assert r.status_code == 400, r.text

    def test_delete_custom_role(self, auth_headers):
        r = requests.delete(
            f"{BASE_URL}/api/permissions/roles/{self.test_role_id}", headers=auth_headers
        )
        assert r.status_code == 200, r.text
        # verify gone
        roles = requests.get(f"{BASE_URL}/api/permissions/roles", headers=auth_headers).json()
        assert not any(x["role_id"] == self.test_role_id for x in roles)

    def test_delete_unknown_role_returns_404(self, auth_headers):
        r = requests.delete(
            f"{BASE_URL}/api/permissions/roles/does_not_exist_xyz", headers=auth_headers
        )
        assert r.status_code == 404

    def test_delete_role_in_use_returns_400(self, auth_headers):
        """Create a custom role, assign a TEST user to it, then delete must 400."""
        rid = f"test_inuse_{int(time.time())}"
        r = requests.post(
            f"{BASE_URL}/api/permissions/roles",
            json={"role_id": rid, "role_name": "TEST In Use", "pages": [], "actions": []},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text

        # Try to create a user with that role; if endpoint is missing, just inject via assignment endpoint
        # We try the standard /api/users endpoint
        ucreate = requests.post(
            f"{BASE_URL}/api/users",
            json={
                "email": f"TEST_inuse_{int(time.time())}@example.com",
                "name": "TEST inuse",
                "password": "TestPass123!",
                "role": rid,
            },
            headers=auth_headers,
        )
        if ucreate.status_code not in (200, 201):
            # Cleanup role and skip — we can't assign a user via the public API in this env
            requests.delete(f"{BASE_URL}/api/permissions/roles/{rid}", headers=auth_headers)
            pytest.skip(f"Could not create test user (status {ucreate.status_code}); skipping in-use guard test")
        user_id = ucreate.json().get("id") or ucreate.json().get("_id") or ucreate.json().get("user", {}).get("id")

        try:
            r = requests.delete(f"{BASE_URL}/api/permissions/roles/{rid}", headers=auth_headers)
            assert r.status_code == 400, f"Expected 400 (role in use), got {r.status_code}: {r.text}"
            assert "user" in r.json().get("detail", "").lower()
        finally:
            # Cleanup: delete user, then role
            if user_id:
                requests.delete(f"{BASE_URL}/api/users/{user_id}", headers=auth_headers)
            requests.delete(f"{BASE_URL}/api/permissions/roles/{rid}", headers=auth_headers)


class TestCleanup:
    """Final sweep: remove any TEST_ prefixed custom roles so list stays at 4 system roles."""

    def test_cleanup_test_roles(self, auth_headers):
        roles = requests.get(f"{BASE_URL}/api/permissions/roles", headers=auth_headers).json()
        for r_ in roles:
            if not r_.get("is_system") and (
                r_["role_id"].startswith("test_role_") or r_["role_name"].startswith("TEST")
            ):
                requests.delete(
                    f"{BASE_URL}/api/permissions/roles/{r_['role_id']}", headers=auth_headers
                )
        roles2 = requests.get(f"{BASE_URL}/api/permissions/roles", headers=auth_headers).json()
        assert len(roles2) == 4, f"Expected 4 system roles only, got {[r['role_id'] for r in roles2]}"

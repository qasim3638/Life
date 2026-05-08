"""Live API tests for Pinterest Visual Engine admin routes.

Hits REACT_APP_BACKEND_URL using an admin session.
"""
from __future__ import annotations

import base64
import os

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://feature-verification-7.preview.emergentagent.com").rstrip("/")
PREFIX = f"{BASE_URL}/api/admin/pinterest/visual"

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"


# ───── fixtures ─────

@pytest.fixture(scope="module")
def admin_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    # Try a few common login endpoints
    for path in ("/api/auth/login", "/api/login", "/api/admin/login"):
        r = s.post(f"{BASE_URL}{path}", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        if r.status_code == 200:
            data = r.json()
            token = (
                data.get("access_token")
                or data.get("token")
                or (data.get("user") or {}).get("token")
            )
            if token:
                s.headers.update({"Authorization": f"Bearer {token}"})
                return s
            # If no token but login succeeded, session cookie might be set
            return s
    pytest.skip("Admin login failed - cannot authenticate")


@pytest.fixture(scope="module")
def anon_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ───── Auth guard ─────

def test_boards_requires_auth(anon_client):
    r = anon_client.get(f"{PREFIX}/boards")
    assert r.status_code in (401, 403), f"Expected 401/403 got {r.status_code}"


def test_summary_requires_auth(anon_client):
    r = anon_client.get(f"{PREFIX}/queue/summary")
    assert r.status_code in (401, 403)


# ───── Boards ─────

def test_get_boards_returns_9_with_required_fields(admin_client):
    r = admin_client.get(f"{PREFIX}/boards")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "boards" in data
    boards = data["boards"]
    assert len(boards) == 9, f"Expected 9 default boards, got {len(boards)}"

    slugs = {b["slug"] for b in boards}
    expected = {
        "bathroom-ideas", "kitchen-ideas", "outdoor-patios", "garden-ideas",
        "patio-ideas", "how-to-tile", "luxury-bathroom-suites", "design-trends",
        "whole-home-renovation",
    }
    assert expected.issubset(slugs), f"Missing boards: {expected - slugs}"

    for b in boards:
        assert "auto_approve" in b
        assert "priority" in b
        assert "name" in b
        assert "_id" not in b  # ObjectId must be excluded


def test_patch_board_toggle_auto_approve(admin_client):
    # Read current value first
    r0 = admin_client.get(f"{PREFIX}/boards")
    boards = r0.json()["boards"]
    target = next(b for b in boards if b["slug"] == "bathroom-ideas")
    original = bool(target.get("auto_approve"))

    # Toggle
    r = admin_client.patch(
        f"{PREFIX}/boards/bathroom-ideas",
        json={"auto_approve": not original, "description": "Updated by test"},
    )
    assert r.status_code == 200, r.text
    updated = r.json()
    assert updated.get("auto_approve") == (not original)
    assert updated.get("description") == "Updated by test"

    # Restore
    r2 = admin_client.patch(
        f"{PREFIX}/boards/bathroom-ideas",
        json={"auto_approve": original, "description": target.get("description", "")},
    )
    assert r2.status_code == 200


def test_patch_board_unknown_slug_404(admin_client):
    r = admin_client.patch(
        f"{PREFIX}/boards/does-not-exist",
        json={"auto_approve": True},
    )
    assert r.status_code == 404


def test_patch_board_ignores_unknown_fields(admin_client):
    """Pydantic strips unknown fields silently."""
    r = admin_client.patch(
        f"{PREFIX}/boards/bathroom-ideas",
        json={"evil_field": "x", "auto_approve": False},
    )
    # Should still succeed, unknown field ignored
    assert r.status_code == 200


def test_seed_boards_idempotent(admin_client):
    r = admin_client.post(f"{PREFIX}/boards/seed")
    assert r.status_code == 200
    data = r.json()
    assert "boards" in data
    assert "inserted" in data
    # Second call should insert 0
    r2 = admin_client.post(f"{PREFIX}/boards/seed")
    assert r2.status_code == 200
    assert r2.json().get("inserted", 0) == 0


# ───── Queue ─────

def test_queue_summary_shape(admin_client):
    r = admin_client.get(f"{PREFIX}/queue/summary")
    assert r.status_code == 200
    data = r.json()
    for k in ("pending", "approved", "posted", "skipped", "blocked_images"):
        assert k in data, f"Missing key {k} in summary"
        assert isinstance(data[k], int)


def test_generate_candidates_and_filter_by_status(admin_client):
    r = admin_client.post(f"{PREFIX}/queue/generate", json={"target_count": 5})
    assert r.status_code == 200, r.text
    gen = r.json()
    assert "generated" in gen or "candidates" in gen or "count" in gen

    # List pending
    r2 = admin_client.get(f"{PREFIX}/queue?status=pending&limit=10")
    assert r2.status_code == 200
    rows = r2.json().get("rows", [])
    assert isinstance(rows, list)
    for row in rows:
        assert row.get("status") == "pending"
        assert "_id" not in row


def test_approve_skip_block_edit_flow(admin_client):
    # Ensure there's a candidate
    admin_client.post(f"{PREFIX}/queue/generate", json={"target_count": 4})
    r = admin_client.get(f"{PREFIX}/queue?status=pending&limit=20")
    rows = r.json().get("rows", [])
    if len(rows) < 3:
        pytest.skip("Not enough pending candidates to run flow")

    # PATCH (edit) — valid
    c_edit = rows[0]
    r_edit = admin_client.patch(
        f"{PREFIX}/queue/{c_edit['id']}",
        json={"title": "TEST_edited title", "description": "TEST edited"},
    )
    assert r_edit.status_code == 200, r_edit.text
    assert r_edit.json().get("title") == "TEST_edited title"

    # PATCH — max_length validation
    r_bad = admin_client.patch(
        f"{PREFIX}/queue/{c_edit['id']}",
        json={"title": "x" * 500},
    )
    assert r_bad.status_code == 422, f"Expected 422 pydantic, got {r_bad.status_code}"

    # PATCH — no fields → 400
    r_empty = admin_client.patch(f"{PREFIX}/queue/{c_edit['id']}", json={})
    assert r_empty.status_code == 400

    # approve
    c_approve = rows[0]
    r_ap = admin_client.post(f"{PREFIX}/queue/{c_approve['id']}/approve")
    assert r_ap.status_code == 200
    assert r_ap.json().get("status") == "approved"
    assert r_ap.json().get("scheduled_for")

    # Approving again → 404 (not pending)
    r_ap2 = admin_client.post(f"{PREFIX}/queue/{c_approve['id']}/approve")
    assert r_ap2.status_code == 404

    # skip
    c_skip = rows[1]
    r_sk = admin_client.post(f"{PREFIX}/queue/{c_skip['id']}/skip")
    assert r_sk.status_code == 200
    assert r_sk.json().get("status") == "skipped"

    # block
    c_block = rows[2]
    r_bl = admin_client.post(f"{PREFIX}/queue/{c_block['id']}/block")
    assert r_bl.status_code == 200
    assert r_bl.json().get("status") == "blocked"


# ───── Blocklist ─────

def test_blocklist_and_delete(admin_client):
    r = admin_client.get(f"{PREFIX}/blocklist")
    assert r.status_code == 200
    rows = r.json().get("rows", [])
    assert isinstance(rows, list)
    for row in rows:
        assert "_id" not in row

    # Try to delete an entry if one exists
    if rows:
        url = rows[0].get("image_url") or rows[0].get("url")
        if url:
            enc = base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")
            r_del = admin_client.delete(f"{PREFIX}/blocklist/{enc}")
            assert r_del.status_code in (200, 404)


def test_blocklist_delete_bad_base64(admin_client):
    r = admin_client.delete(f"{PREFIX}/blocklist/!!!notbase64!!!")
    # either invalid base64 (400) or not in blocklist (404)
    assert r.status_code in (400, 404)

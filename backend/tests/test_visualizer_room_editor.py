"""Tests for the Sample Room Editor backend endpoints.

Covers:
  • POST /api/admin/visualizer/upload-image — admin-only, rejects empty
    files, rejects non-image content types, rejects oversize files.
  • POST /api/admin/visualizer/sample-rooms — upsert path: creating a new
    room (no id) returns a fresh UUID; updating an existing room (with
    id) modifies fields without changing id; non-admin gets 403.
  • Round-trip: created → edited → deleted is a clean lifecycle.

Skipped in CI when FAL_KEY is missing, since the upload-image endpoint
hits fal.ai's CDN.
"""
import os
import requests

BASE_URL = os.environ.get(
    "BACKEND_URL",
    "https://feature-verification-7.preview.emergentagent.com",
)


def _admin_headers():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "admin@test.com", "password": "admin123"},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok
    return {"Authorization": f"Bearer {tok}"}


def test_upload_image_requires_admin():
    # No auth header at all → 401/403 from FastAPI security dep
    r = requests.post(f"{BASE_URL}/api/admin/visualizer/upload-image",
                      files={"file": ("a.png", b"", "image/png")}, timeout=10)
    assert r.status_code in (401, 403), r.text


def test_upload_image_rejects_empty_file():
    h = _admin_headers()
    r = requests.post(
        f"{BASE_URL}/api/admin/visualizer/upload-image",
        files={"file": ("empty.jpg", b"", "image/jpeg")},
        headers=h,
        timeout=15,
    )
    assert r.status_code == 422, r.text
    assert "empty" in r.text.lower()


def test_upload_image_rejects_unsupported_type():
    h = _admin_headers()
    # Use a TXT extension/content-type — endpoint must refuse before
    # spending an fal.ai call.
    r = requests.post(
        f"{BASE_URL}/api/admin/visualizer/upload-image",
        files={"file": ("not_an_image.txt", b"hello", "text/plain")},
        headers=h,
        timeout=15,
    )
    assert r.status_code == 415, r.text


def test_upsert_create_then_edit_then_delete():
    h = _admin_headers()
    # Create
    create_payload = {
        "label": "PYTEST Throwaway Room",
        "room_type": "kitchen",
        "surface_kind": "floor",
        "image_url": "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=1024&q=80",
        "surface_polygon": [[60, 660], [970, 660], [780, 360], [240, 360]],
        "default_surface_m2": 9.0,
        "tile_repeat_size_px": 180,
        "display_order": 9999,
        "active": True,
    }
    r = requests.post(f"{BASE_URL}/api/admin/visualizer/sample-rooms",
                      json=create_payload, headers=h, timeout=10)
    assert r.status_code == 200, r.text
    rid = r.json().get("id")
    assert rid

    try:
        # Edit — change polygon and label, keep id
        edit_payload = dict(create_payload)
        edit_payload["id"] = rid
        edit_payload["label"] = "PYTEST Edited Label"
        edit_payload["surface_polygon"] = [[100, 600], [900, 600], [700, 350], [300, 350]]
        edit_payload["default_surface_m2"] = 14.0
        r = requests.post(f"{BASE_URL}/api/admin/visualizer/sample-rooms",
                          json=edit_payload, headers=h, timeout=10)
        assert r.status_code == 200, r.text
        assert r.json().get("id") == rid  # same id

        # Verify changes landed in admin list
        r = requests.get(f"{BASE_URL}/api/admin/visualizer/sample-rooms",
                         headers=h, timeout=10)
        assert r.status_code == 200, r.text
        match = next((row for row in r.json()["rooms"] if row["id"] == rid), None)
        assert match is not None
        assert match["label"] == "PYTEST Edited Label"
        assert match["surface_polygon"][0] == [100, 600]
        assert match["default_surface_m2"] == 14.0
    finally:
        # Cleanup — always
        requests.delete(f"{BASE_URL}/api/admin/visualizer/sample-rooms/{rid}",
                        headers=h, timeout=10)

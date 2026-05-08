"""Tests for the polygon-validator endpoint.

Covers:
  • Admin-only guard (no auth → 401/403).
  • Returns a per-room report with summary {ok, warn, bad, total}.
  • Each result has the required fields: id, status, reasons, polygon,
    image_dims (when fetch succeeded).
  • Rooms with intentionally bad polygons are flagged.
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
    return {"Authorization": f"Bearer {tok}"}


def test_validate_polygons_requires_admin():
    r = requests.post(
        f"{BASE_URL}/api/admin/visualizer/sample-rooms/validate-polygons",
        timeout=10,
    )
    assert r.status_code in (401, 403), r.text


def test_validate_polygons_returns_summary_and_results():
    h = _admin_headers()
    r = requests.post(
        f"{BASE_URL}/api/admin/visualizer/sample-rooms/validate-polygons",
        headers=h,
        timeout=120,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "summary" in body
    assert "results" in body
    summary = body["summary"]
    for k in ("total", "ok", "warn", "bad"):
        assert k in summary, f"summary missing {k}"
        assert isinstance(summary[k], int)
    assert summary["total"] >= 1
    assert summary["ok"] + summary["warn"] + summary["bad"] == summary["total"]

    for row in body["results"]:
        assert "id" in row
        assert "status" in row
        assert row["status"] in ("ok", "warn", "bad")
        assert "reasons" in row and isinstance(row["reasons"], list)
        assert "polygon" in row
        # image_dims may be None when fetch failed (status=bad)
        if row["status"] == "ok":
            assert row.get("image_dims") is not None


def test_validate_polygons_flags_a_bad_polygon():
    """Insert a deliberately-broken sample room (polygon centroid in the
    top of a floor image), validate, then confirm it shows up as 'bad'.
    Cleans up the test room afterwards."""
    h = _admin_headers()
    rid = "_pytest_bad_polygon_room"
    bad = {
        "id": rid,
        "label": "PYTEST Bad Polygon",
        "room_type": "kitchen",
        "surface_kind": "floor",
        "image_url": "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=1024&q=80",
        # Polygon for a floor BUT centroid is at y=50 (top of image) —
        # the validator should flag this as bad.
        "surface_polygon": [[300, 30], [700, 30], [700, 70], [300, 70]],
        "default_surface_m2": 4.0,
        "tile_repeat_size_px": 160,
        "display_order": 9999,
        "active": True,
    }
    requests.post(f"{BASE_URL}/api/admin/visualizer/sample-rooms",
                  json=bad, headers=h, timeout=10)
    try:
        r = requests.post(
            f"{BASE_URL}/api/admin/visualizer/sample-rooms/validate-polygons",
            headers=h,
            timeout=120,
        )
        assert r.status_code == 200
        rows = r.json()["results"]
        my = next((x for x in rows if x["id"] == rid), None)
        assert my is not None, "test room not in validation results"
        assert my["status"] == "bad", f"expected status=bad, got {my['status']} ({my['reasons']})"
        assert any("top" in reason.lower() or "tiny" in reason.lower() or "covers only" in reason.lower()
                   for reason in my["reasons"]), my["reasons"]
    finally:
        requests.delete(f"{BASE_URL}/api/admin/visualizer/sample-rooms/{rid}",
                        headers=h, timeout=10)

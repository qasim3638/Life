"""Tests for the multi-image picker on the visualizer.

Covers:
  • _resolve_tile returns the full `images: list[str]` array, not just
    the first image.
  • Sessions accept `image_index` and clamp out-of-range values.
  • Sessions persist `tile_images`, `tile_image_index`, and `tile_image`
    so subsequent renders use the correct texture.

Skipped automatically when there's no product with ≥2 images in the DB.
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


def _find_multi_image_tile(headers, min_images=2):
    """Skip the test if no product has enough images."""
    import pytest
    r = requests.get(f"{BASE_URL}/api/tiles/products?limit=50", headers=headers, timeout=15)
    if r.status_code != 200:
        pytest.skip(f"products endpoint returned {r.status_code}")
    payload = r.json()
    prods = payload.get("products") if isinstance(payload, dict) else payload
    for p in prods or []:
        imgs = p.get("images") or []
        if len(imgs) >= min_images:
            return p.get("id")
    pytest.skip(f"no product in DB with ≥{min_images} images — multi-image picker untestable here")


def test_session_returns_full_image_gallery():
    h = _admin_headers()
    tid = _find_multi_image_tile(h, min_images=2)
    r = requests.post(
        f"{BASE_URL}/api/visualizer/sessions",
        json={"sample_room_id": "vis_room_kitchen_floor", "tile_id": tid, "image_index": 0},
        headers=h,
        timeout=15,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    tile = body.get("tile") or {}
    assert "images" in tile, "session.tile must include `images: string[]` so the client can build the strip"
    assert isinstance(tile["images"], list)
    assert len(tile["images"]) >= 2
    assert all(isinstance(u, str) and u.startswith("http") for u in tile["images"])
    assert body.get("image_index") == 0
    # The chosen image must be the first one in the list
    assert tile.get("image") == tile["images"][0]


def test_session_image_index_picks_correct_url():
    h = _admin_headers()
    tid = _find_multi_image_tile(h, min_images=3)
    # Pick image #2
    r = requests.post(
        f"{BASE_URL}/api/visualizer/sessions",
        json={"sample_room_id": "vis_room_kitchen_floor", "tile_id": tid, "image_index": 2},
        headers=h,
        timeout=15,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("image_index") == 2
    sid = body["session_id"]

    # The session doc should also reflect the chosen image
    r = requests.get(f"{BASE_URL}/api/visualizer/sessions/{sid}", headers=h, timeout=10)
    assert r.status_code == 200, r.text
    sess = r.json()
    assert sess.get("tile_image_index") == 2
    assert isinstance(sess.get("tile_images"), list)
    assert len(sess["tile_images"]) >= 3
    assert sess.get("tile_image") == sess["tile_images"][2]


def test_session_image_index_clamps_out_of_range():
    h = _admin_headers()
    tid = _find_multi_image_tile(h, min_images=2)
    r = requests.post(
        f"{BASE_URL}/api/visualizer/sessions",
        json={"sample_room_id": "vis_room_kitchen_floor", "tile_id": tid, "image_index": 9999},
        headers=h,
        timeout=15,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    tile = body.get("tile") or {}
    last_idx = len(tile["images"]) - 1
    assert body.get("image_index") == last_idx, "out-of-range index must clamp to the last available image"

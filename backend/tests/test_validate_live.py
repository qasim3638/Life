"""Live integration test for validate-polygons endpoint."""
import os
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://feature-verification-7.preview.emergentagent.com").rstrip("/")
ENDPOINT = f"{BASE_URL}/api/admin/visualizer/sample-rooms/validate-polygons"


def _login_admin():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "admin@test.com", "password": "admin123"},
        timeout=30,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    return data.get("access_token") or data.get("token")


def test_validate_requires_auth():
    r = requests.post(ENDPOINT, timeout=30)
    assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"


def test_validate_with_admin():
    token = _login_admin()
    r = requests.post(ENDPOINT, headers={"Authorization": f"Bearer {token}"}, timeout=120)
    assert r.status_code == 200, f"validator failed: {r.status_code} {r.text[:500]}"
    data = r.json()
    assert "summary" in data and "results" in data
    s = data["summary"]
    for k in ("total", "ok", "warn", "bad"):
        assert k in s and isinstance(s[k], int), f"missing/bad summary key {k}: {s}"
    assert s["ok"] + s["warn"] + s["bad"] == s["total"], f"summary not summing: {s}"

    # shape of each result
    for r_ in data["results"]:
        for k in ("id", "status", "reasons", "polygon"):
            assert k in r_, f"missing key {k} in {r_}"
        assert r_["status"] in ("ok", "warn", "bad")
        assert isinstance(r_["reasons"], list)

    # Expectation: 9 OK + 1 BAD (utility room dead URL)
    print(f"\nSUMMARY: {s}")
    bad_rooms = [r_["id"] for r_ in data["results"] if r_["status"] == "bad"]
    warn_rooms = [(r_["id"], r_["reasons"]) for r_ in data["results"] if r_["status"] == "warn"]
    print(f"BAD rooms: {bad_rooms}")
    print(f"WARN rooms: {warn_rooms}")

    assert s["bad"] == 1, f"expected 1 BAD, got {s['bad']}: {bad_rooms}"
    assert s["ok"] == 9, f"expected 9 OK, got {s['ok']}"
    assert "vis_room_utility_floor" in bad_rooms, f"utility room must be BAD, bad={bad_rooms}"

    # The polygon-fix rooms must be OK now
    by_id = {r_["id"]: r_ for r_ in data["results"]}
    for must_ok in ("vis_room_bathroom_wall", "vis_room_bathroom_floor", "vis_room_hallway_floor"):
        if must_ok in by_id:
            assert by_id[must_ok]["status"] == "ok", (
                f"{must_ok} should be OK, got {by_id[must_ok]['status']} reasons={by_id[must_ok]['reasons']}"
            )


def test_admin_lists_10_customer_lists_9():
    token = _login_admin()
    h = {"Authorization": f"Bearer {token}"}
    admin_r = requests.get(f"{BASE_URL}/api/admin/visualizer/sample-rooms", headers=h, timeout=30)
    assert admin_r.status_code == 200
    admin_rooms = admin_r.json()
    if isinstance(admin_rooms, dict) and "rooms" in admin_rooms:
        admin_rooms = admin_rooms["rooms"]
    print(f"\nAdmin sees {len(admin_rooms)} rooms")
    assert len(admin_rooms) == 10, f"admin should see 10, got {len(admin_rooms)}"

    cust_r = requests.get(f"{BASE_URL}/api/visualizer/sample-rooms", timeout=30)
    if cust_r.status_code != 200:
        # try preview flag
        cust_r = requests.get(f"{BASE_URL}/api/visualizer/sample-rooms?preview=1", headers=h, timeout=30)
    assert cust_r.status_code == 200
    cust_rooms = cust_r.json()
    if isinstance(cust_rooms, dict) and "rooms" in cust_rooms:
        cust_rooms = cust_rooms["rooms"]
    print(f"Customer endpoint sees {len(cust_rooms)} rooms")
    assert len(cust_rooms) == 9, f"customer should see 9, got {len(cust_rooms)}"

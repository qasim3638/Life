"""
Regression tests for two linked admin-dashboard bugs:

1. `GET /api/historical-sales/manual-entries` used to throw 500 with
   `KeyError: 'id'` whenever even one showroom document in the DB lacked
   an `id` field (two legacy "coming soon" showrooms in production did).

2. `GET /api/showrooms` used to return those legacy records with NO `id`
   field, causing React duplicate-key warnings on the admin dashboard
   (four <select>s map `showrooms` with `key={s.id}`).

Both are fixed. These tests pin the contract so they can't recur.
"""
import os
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


def _login_admin():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "admin@test.com", "password": "admin123"},
    )
    assert r.status_code == 200, f"Admin login failed: {r.status_code}"
    body = r.json()
    token = body.get("token") or body.get("access_token")
    assert token, f"No token in login response: {body}"
    return {"Authorization": f"Bearer {token}"}


class TestHistoricalEntriesDoesNotCrash:
    def test_get_manual_entries_returns_200(self):
        """
        Was 500 with `KeyError: 'id'` when any showroom doc lacked an `id`.
        Must now return 200 regardless of showroom doc shape.
        """
        r = requests.get(
            f"{BASE_URL}/api/historical-sales/manual-entries",
            headers=_login_admin(),
        )
        assert r.status_code == 200, (
            f"Endpoint regressed — status {r.status_code}, body: {r.text[:300]}"
        )
        payload = r.json()
        # Must be a list (may be empty if no entries seeded)
        assert isinstance(payload, list), f"Expected list, got {type(payload)}"


class TestShowroomsApiHasStableIds:
    def test_every_showroom_has_a_unique_string_id(self):
        """
        Was returning legacy showroom docs with no `id` field → duplicate React
        keys. Every doc must now expose a non-empty unique `id`.
        """
        r = requests.get(
            f"{BASE_URL}/api/showrooms", headers=_login_admin()
        )
        assert r.status_code == 200, f"Status {r.status_code}: {r.text[:200]}"
        showrooms = r.json()
        assert isinstance(showrooms, list)
        assert showrooms, "Expected at least one showroom in the DB"

        ids = [s.get("id") for s in showrooms]
        # No None/empty ids allowed
        assert all(i for i in ids), (
            f"Some showrooms returned without an `id` — legacy backfill regressed. ids={ids}"
        )
        # All ids must be strings
        assert all(isinstance(i, str) for i in ids), f"Non-string ids present: {ids}"
        # All ids must be unique (the actual requirement for React list keys)
        assert len(set(ids)) == len(ids), f"Duplicate showroom ids: {ids}"

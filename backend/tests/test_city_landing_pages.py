"""
Backend integration tests for AI City Landing Pages.

Covers:
  - Auth gating on admin endpoints
  - GET /api/admin/seo/city-pages list + counts envelope
  - POST /generate for tile-shop-gravesend → real Gravesend showroom data
  - POST /generate for tile-shop-brighton → falls back to Tonbridge showroom
  - POST /generate for buy-tiles-online-uk → nationwide page mentions
    Gravesend + Tonbridge + Chingford and excludes closed Sydenham as a
    primary recommendation
  - POST /generate-batch with auto-pick (limit=2, only_pending=true)
  - POST /generate-batch with explicit slug list

Notes:
  • /seed and /refresh-pending are slow + already verified manually by
    the main agent. We do NOT call them again here.
  • LLM calls take 5-15s each → request timeout is 90s for /generate
    and 180s for /generate-batch.
  • All 33 TOWNS in routes/city_landing_pages.py:TOWNS are present in
    business_config/showrooms.py:TOWN_NEAREST_SHOWROOM, so the
    "unmapped town fallback" path is unreachable from the seeded queue
    and is skipped per the review_request guidance.
"""
from __future__ import annotations

import os
import re

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback to frontend/.env value at test discovery time.
    try:
        with open("/app/frontend/.env") as fh:
            for line in fh:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                    break
    except Exception:  # noqa: BLE001
        pass

assert BASE_URL, "REACT_APP_BACKEND_URL must be set for tests"


# ─── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def admin_token() -> str:
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "admin@test.com", "password": "admin123"},
        timeout=20,
    )
    if resp.status_code != 200:
        pytest.skip(f"Admin login failed ({resp.status_code}): {resp.text}")
    data = resp.json()
    token = data.get("token")
    assert token, "Login response missing token"
    return token


@pytest.fixture(scope="session")
def auth_headers(admin_token: str) -> dict:
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ─── Auth gating ───────────────────────────────────────────────────────────


class TestAuthGating:
    """Every admin endpoint must reject unauthenticated calls."""

    def test_seed_requires_auth(self):
        r = requests.post(f"{BASE_URL}/api/admin/seo/city-pages/seed", timeout=20)
        assert r.status_code in (401, 403), f"Expected 401/403 got {r.status_code}: {r.text}"

    def test_refresh_pending_requires_auth(self):
        r = requests.post(
            f"{BASE_URL}/api/admin/seo/city-pages/refresh-pending", timeout=20
        )
        assert r.status_code in (401, 403)

    def test_list_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/admin/seo/city-pages", timeout=20)
        assert r.status_code in (401, 403)

    def test_generate_requires_auth(self):
        r = requests.post(
            f"{BASE_URL}/api/admin/seo/city-pages/generate",
            json={"slug": "tile-shop-gravesend"},
            timeout=20,
        )
        assert r.status_code in (401, 403)

    def test_generate_batch_requires_auth(self):
        r = requests.post(
            f"{BASE_URL}/api/admin/seo/city-pages/generate-batch",
            json={"limit": 1},
            timeout=20,
        )
        assert r.status_code in (401, 403)


# ─── List endpoint envelope ────────────────────────────────────────────────


class TestListEndpoint:
    def test_list_pending_returns_envelope_with_counts(self, auth_headers):
        r = requests.get(
            f"{BASE_URL}/api/admin/seo/city-pages?status=pending",
            headers=auth_headers,
            timeout=30,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "rows" in data and isinstance(data["rows"], list)
        assert "counts" in data and isinstance(data["counts"], dict)
        # All four status buckets should be present (may be 0)
        for s in ("pending", "generated", "approved", "skipped"):
            assert s in data["counts"], f"missing count bucket: {s}"
            assert isinstance(data["counts"][s], int)
        # total queue should be at least 165 town rows + 3 nationwide rows
        total = sum(data["counts"].values())
        assert total >= 168, f"expected >=168 queue rows, got {total}"

    def test_list_status_all(self, auth_headers):
        r = requests.get(
            f"{BASE_URL}/api/admin/seo/city-pages?status=all&limit=500",
            headers=auth_headers,
            timeout=30,
        )
        assert r.status_code == 200
        data = r.json()
        assert len(data["rows"]) >= 1


# ─── Generate single page ──────────────────────────────────────────────────


def _fetch_row(auth_headers: dict, slug: str) -> dict:
    """Fetch a single queue row by slug (using the all-status list)."""
    r = requests.get(
        f"{BASE_URL}/api/admin/seo/city-pages?status=all&limit=500",
        headers=auth_headers,
        timeout=30,
    )
    r.raise_for_status()
    rows = r.json().get("rows", [])
    for row in rows:
        if row.get("slug") == slug:
            return row
    raise AssertionError(f"slug {slug} not found in queue")


class TestGenerateSingle:
    def test_generate_gravesend_includes_real_showroom_details(self, auth_headers):
        slug = "tile-shop-gravesend"
        r = requests.post(
            f"{BASE_URL}/api/admin/seo/city-pages/generate",
            headers=auth_headers,
            json={"slug": slug},
            timeout=120,
        )
        assert r.status_code == 200, f"{r.status_code}: {r.text}"
        body = r.json()
        assert body.get("ok") is True
        assert body.get("slug") == slug

        # Pull persisted body to assert real showroom details
        row = _fetch_row(auth_headers, slug)
        assert row.get("status") == "generated"
        body_md = (row.get("body_md") or "").lower()
        assert body_md, "body_md should be populated after generate"

        # Required real-data assertions for Gravesend showroom
        # (address, postcode, phone) — address must include Coldharbour Road OR Trade City
        assert (
            "coldharbour road" in body_md or "trade city" in body_md
        ), "Gravesend address (Coldharbour Road / Trade City) missing from body_md"
        assert "da11 8ab" in body_md, "Gravesend postcode DA11 8AB missing"
        assert "01474 878 989" in body_md, "Gravesend phone 01474 878 989 missing"

    def test_generate_brighton_routes_to_tonbridge(self, auth_headers):
        slug = "tile-shop-brighton"
        r = requests.post(
            f"{BASE_URL}/api/admin/seo/city-pages/generate",
            headers=auth_headers,
            json={"slug": slug},
            timeout=120,
        )
        assert r.status_code == 200, f"{r.status_code}: {r.text}"
        assert r.json().get("ok") is True

        row = _fetch_row(auth_headers, slug)
        body_md = (row.get("body_md") or "").lower()
        assert body_md, "body_md should be populated after generate"
        # Brighton's nearest open showroom is Tonbridge.
        assert "tn9 1sp" in body_md, "Tonbridge postcode TN9 1SP missing for Brighton page"
        assert "01732 914 374" in body_md, "Tonbridge phone 01732 914 374 missing for Brighton page"

    def test_generate_nationwide_lists_open_showrooms_only(self, auth_headers):
        slug = "buy-tiles-online-uk"
        r = requests.post(
            f"{BASE_URL}/api/admin/seo/city-pages/generate",
            headers=auth_headers,
            json={"slug": slug},
            timeout=120,
        )
        assert r.status_code == 200, f"{r.status_code}: {r.text}"
        assert r.json().get("ok") is True

        row = _fetch_row(auth_headers, slug)
        body_md = row.get("body_md") or ""
        body_lc = body_md.lower()
        assert body_md, "nationwide body_md should be populated"

        # Mentions all three open showroom locations
        for town in ("gravesend", "tonbridge", "chingford"):
            assert town in body_lc, f"nationwide page missing showroom: {town}"

        # Sydenham is currently closed (is_open=False); it should NOT be
        # listed in the showroom section that the prompt builds from
        # all_open_showrooms(). Allow the word elsewhere only if not
        # presented as a primary location — assert SE26 5BA postcode is
        # absent (that is the Sydenham postcode and would only appear if
        # Sydenham was in the open list).
        assert "se26 5ba" not in body_lc, (
            "Closed Sydenham showroom (SE26 5BA) leaked into nationwide page"
        )


# ─── Generate batch ────────────────────────────────────────────────────────


class TestGenerateBatch:
    def test_batch_auto_pick_pending(self, auth_headers):
        r = requests.post(
            f"{BASE_URL}/api/admin/seo/city-pages/generate-batch",
            headers=auth_headers,
            json={"limit": 2, "only_pending": True},
            timeout=240,
        )
        assert r.status_code == 200, f"{r.status_code}: {r.text}"
        data = r.json()
        assert data.get("ok") is True
        assert "attempted" in data and "succeeded" in data and "failed" in data
        assert "results" in data and isinstance(data["results"], list)
        # attempted should be 0 (no pending left) or up to 2
        assert data["attempted"] <= 2
        # When attempted > 0, succeeded+failed must equal attempted
        assert data["succeeded"] + data["failed"] == data["attempted"]
        # results entries shape
        for res in data["results"]:
            assert "slug" in res and "ok" in res

    def test_batch_explicit_slug_list(self, auth_headers):
        slugs = ["tile-shop-dartford", "kitchen-tiles-rochester"]
        r = requests.post(
            f"{BASE_URL}/api/admin/seo/city-pages/generate-batch",
            headers=auth_headers,
            json={"slugs": slugs, "limit": 5},
            timeout=240,
        )
        assert r.status_code == 200, f"{r.status_code}: {r.text}"
        data = r.json()
        assert data.get("ok") is True
        # All requested slugs should be attempted (assuming they exist in queue)
        attempted_slugs = {res["slug"] for res in data["results"]}
        for s in slugs:
            assert s in attempted_slugs, f"requested slug {s} missing from results"
        assert data["succeeded"] + data["failed"] == data["attempted"]

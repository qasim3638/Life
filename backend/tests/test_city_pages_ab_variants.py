"""
A/B variant generation, sticky-cookie public serving, CTA click tracking,
ab-stats, and promote-variant — for /api/admin/seo/city-pages and the
public /api/shop/city-page route.

We run a single live LLM call (generate-variant-b on
porcelain-tiles-maidstone) end-to-end. All other tests reuse pre-existing
DB state (tile-shop-gravesend already has variant_b populated per the
hand-off note) so we avoid burning LLM budget on every CI run.

Test order matters: pytest preserves source order within a class. The
public-route promote-cleanup tests (#14, #17) re-fetch the row after
promote-variant to verify the stored A/B fields are gone.
"""
from __future__ import annotations

import os
import requests
import pytest

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or os.environ.get("BACKEND_URL")
            or os.environ.get("PUBLIC_PREVIEW_URL", "")).rstrip("/")
assert BASE_URL, "BASE_URL not set — need REACT_APP_BACKEND_URL/BACKEND_URL/PUBLIC_PREVIEW_URL"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"

# Slugs in the live preview DB:
SLUG_AB_LIVE = "tile-shop-gravesend"           # has variant_b at start
SLUG_NO_VB = "tile-suppliers-maidstone"        # approved, NO variant_b
SLUG_FOR_GEN_B = "porcelain-tiles-maidstone"   # approved, no variant_b -> we'll generate B onto it


# ─── Shared fixtures ───────────────────────────────────────────────


@pytest.fixture(scope="module")
def admin_token() -> str:
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=10,
    )
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def pending_slug(admin_headers) -> str:
    """Find one slug whose body_md is None (status=pending) — needed for the
    400 'generate variant A first' test. We don't mutate it."""
    r = requests.get(
        f"{BASE_URL}/api/admin/seo/city-pages?status=pending&limit=5",
        headers=admin_headers, timeout=10,
    )
    assert r.status_code == 200
    rows = r.json().get("rows") or []
    for row in rows:
        if not row.get("body_md"):
            return row["slug"]
    pytest.skip("no pending slug found in preview DB")


# ─── 1. Auth & validation on POST /generate-variant-b ──────────────


class TestGenerateVariantBGuards:
    def test_403_without_token(self):
        r = requests.post(
            f"{BASE_URL}/api/admin/seo/city-pages/generate-variant-b",
            json={"slug": SLUG_AB_LIVE}, timeout=10,
        )
        # Some auth setups return 401 for missing header, 403 for wrong role.
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"

    def test_404_unknown_slug(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/admin/seo/city-pages/generate-variant-b",
            headers=admin_headers,
            json={"slug": "this-slug-does-not-exist-xyz"}, timeout=15,
        )
        assert r.status_code == 404, r.text
        assert "Page not in queue" in r.text

    def test_400_when_variant_a_missing(self, admin_headers, pending_slug):
        r = requests.post(
            f"{BASE_URL}/api/admin/seo/city-pages/generate-variant-b",
            headers=admin_headers,
            json={"slug": pending_slug}, timeout=15,
        )
        assert r.status_code == 400, r.text
        assert "Generate variant A first" in r.text


# ─── 2. Public route A/B serving (uses pre-existing variant_b) ─────


class TestPublicABServing:
    """Uses tile-shop-gravesend which already has variant_b populated."""

    def test_no_cookie_assigns_variant_and_sets_cookie(self):
        s = requests.Session()
        r = s.get(f"{BASE_URL}/api/shop/city-page/{SLUG_AB_LIVE}", timeout=10)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("active_variant") in ("a", "b"), body.keys()
        # Cookie must be set on first visit
        cookie_header = r.headers.get("set-cookie") or ""
        assert "ts_cp_ab=" in cookie_header.lower(), f"missing Set-Cookie: {cookie_header!r}"
        cookie_lower = cookie_header.lower()
        assert "samesite=lax" in cookie_lower
        assert "secure" in cookie_lower
        assert "max-age=2592000" in cookie_lower
        # Session has cookie now
        assert s.cookies.get("ts_cp_ab") in ("a", "b")

    def test_sticky_a(self):
        s = requests.Session()
        s.cookies.set("ts_cp_ab", "a", domain=BASE_URL.split("://", 1)[1].split("/", 1)[0])
        r = s.get(f"{BASE_URL}/api/shop/city-page/{SLUG_AB_LIVE}", timeout=10)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("active_variant") == "a", body.get("active_variant")
        # No new Set-Cookie — sticky
        assert "set-cookie" not in {k.lower() for k in r.headers.keys()} or \
               "ts_cp_ab" not in (r.headers.get("set-cookie", "").lower())

    def test_sticky_b_serves_variant_b_body(self, admin_headers):
        # Pull DB-stored variant_b body to compare.
        admin_list = requests.get(
            f"{BASE_URL}/api/admin/seo/city-pages?status=approved&limit=20",
            headers=admin_headers, timeout=10,
        ).json()
        target = next((r for r in admin_list["rows"] if r["slug"] == SLUG_AB_LIVE), None)
        assert target and target.get("variant_b"), "live A/B page lost its variant_b"
        expected_b_body = target["variant_b"]["body_md"]

        s = requests.Session()
        s.cookies.set("ts_cp_ab", "b", domain=BASE_URL.split("://", 1)[1].split("/", 1)[0])
        r = s.get(f"{BASE_URL}/api/shop/city-page/{SLUG_AB_LIVE}", timeout=10)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("active_variant") == "b"
        assert body.get("body_md") == expected_b_body, "variant B body not served"

    def test_public_no_variant_b_returns_raw_no_cookie(self):
        s = requests.Session()
        r = s.get(f"{BASE_URL}/api/shop/city-page/{SLUG_NO_VB}", timeout=10)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "active_variant" not in body, "active_variant must be absent when no variant_b"
        assert s.cookies.get("ts_cp_ab") is None, "no cookie should be set"


# ─── 3. CTA click tracking ─────────────────────────────────────────


class TestTrackCtaClick:
    def test_track_variant_a(self, admin_headers):
        before = self._fetch_clicks(admin_headers, SLUG_AB_LIVE)
        r = requests.post(
            f"{BASE_URL}/api/shop/city-page/track-cta-click",
            json={"slug": SLUG_AB_LIVE, "variant": "a"}, timeout=10,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data == {"ok": True, "matched": 1}, data
        after = self._fetch_clicks(admin_headers, SLUG_AB_LIVE)
        assert after["a"] == before["a"] + 1, (before, after)

    def test_track_variant_b(self, admin_headers):
        before = self._fetch_clicks(admin_headers, SLUG_AB_LIVE)
        r = requests.post(
            f"{BASE_URL}/api/shop/city-page/track-cta-click",
            json={"slug": SLUG_AB_LIVE, "variant": "b"}, timeout=10,
        )
        assert r.status_code == 200, r.text
        after = self._fetch_clicks(admin_headers, SLUG_AB_LIVE)
        assert after["b"] == before["b"] + 1, (before, after)

    def test_track_invalid_variant(self):
        r = requests.post(
            f"{BASE_URL}/api/shop/city-page/track-cta-click",
            json={"slug": SLUG_AB_LIVE, "variant": "c"}, timeout=10,
        )
        assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text}"

    def test_track_empty_variant(self):
        r = requests.post(
            f"{BASE_URL}/api/shop/city-page/track-cta-click",
            json={"slug": SLUG_AB_LIVE, "variant": ""}, timeout=10,
        )
        assert r.status_code == 422

    @staticmethod
    def _fetch_clicks(headers, slug):
        r = requests.get(f"{BASE_URL}/api/admin/seo/city-pages/ab-stats", headers=headers, timeout=10)
        assert r.status_code == 200, r.text
        for row in r.json()["rows"]:
            if row["slug"] == slug:
                return {"a": row["variant_a"]["clicks"], "b": row["variant_b"]["clicks"]}
        pytest.fail(f"slug {slug} not in ab-stats")


# ─── 4. /ab-stats endpoint ─────────────────────────────────────────


class TestAbStats:
    def test_403_without_token(self):
        r = requests.get(f"{BASE_URL}/api/admin/seo/city-pages/ab-stats", timeout=10)
        assert r.status_code in (401, 403)

    def test_returns_only_rows_with_variant_b(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/seo/city-pages/ab-stats", headers=admin_headers, timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "rows" in data and isinstance(data["rows"], list)
        # Every row must include the expected shape
        for row in data["rows"]:
            for key in ("slug", "town", "intent_phrase", "url", "ab_started_at",
                        "variant_a", "variant_b"):
                assert key in row, f"missing {key} in {row}"
            for v in ("variant_a", "variant_b"):
                for inner in ("score", "impressions", "clicks", "ctr"):
                    assert inner in row[v]
                imp = row[v]["impressions"]
                clk = row[v]["clicks"]
                ctr = row[v]["ctr"]
                if imp == 0:
                    assert ctr is None, (v, imp, ctr)
                else:
                    assert ctr == round(100 * clk / imp, 2), (v, imp, clk, ctr)
        # tile-shop-gravesend should be present (still has variant_b at this stage)
        slugs = [r["slug"] for r in data["rows"]]
        assert SLUG_AB_LIVE in slugs


# ─── 5. promote-variant validation + winner=a flow ─────────────────


class TestPromoteVariantA:
    """winner='a' just unsets variant_b without changing primary body_md.
    We use tile-shop-gravesend which has variant_b populated."""

    def test_invalid_winner(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/admin/seo/city-pages/promote-variant",
            headers=admin_headers,
            json={"slug": SLUG_AB_LIVE, "winner": "c"}, timeout=10,
        )
        assert r.status_code == 422, r.text

    def test_403_without_token(self):
        r = requests.post(
            f"{BASE_URL}/api/admin/seo/city-pages/promote-variant",
            json={"slug": SLUG_AB_LIVE, "winner": "a"}, timeout=10,
        )
        assert r.status_code in (401, 403)

    def test_winner_a_keeps_primary_unsets_variant_b(self, admin_headers):
        # Snapshot primary body_md BEFORE promote
        list_resp = requests.get(
            f"{BASE_URL}/api/admin/seo/city-pages?status=approved&limit=20",
            headers=admin_headers, timeout=10,
        ).json()
        before = next(r for r in list_resp["rows"] if r["slug"] == SLUG_AB_LIVE)
        before_body = before["body_md"]
        assert before.get("variant_b"), "precondition failed: SLUG_AB_LIVE has no variant_b"

        r = requests.post(
            f"{BASE_URL}/api/admin/seo/city-pages/promote-variant",
            headers=admin_headers,
            json={"slug": SLUG_AB_LIVE, "winner": "a"}, timeout=10,
        )
        assert r.status_code == 200, r.text
        assert r.json() == {"ok": True, "slug": SLUG_AB_LIVE, "winner": "a"}

        # Re-fetch and verify
        list_resp = requests.get(
            f"{BASE_URL}/api/admin/seo/city-pages?status=approved&limit=20",
            headers=admin_headers, timeout=10,
        ).json()
        after = next(r for r in list_resp["rows"] if r["slug"] == SLUG_AB_LIVE)
        assert after["body_md"] == before_body, "primary body_md must NOT change for winner=a"
        assert after.get("variant_b") in (None, {}), f"variant_b should be unset, got {after.get('variant_b')!r}"
        for k in ("variant_a_impressions", "variant_b_impressions",
                  "variant_a_cta_clicks", "variant_b_cta_clicks", "ab_started_at"):
            assert after.get(k) in (None, 0) or k not in after, f"{k} should be unset, got {after.get(k)!r}"
        assert after.get("ab_winner") == "a"
        assert after.get("ab_won_at")

    def test_public_after_promote_a_no_active_variant_no_cookie(self):
        s = requests.Session()
        r = s.get(f"{BASE_URL}/api/shop/city-page/{SLUG_AB_LIVE}", timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert "active_variant" not in body, body.keys()
        assert s.cookies.get("ts_cp_ab") is None


# ─── 6. Live LLM: generate-variant-b happy path on a fresh slug ────


class TestGenerateVariantBHappyPath:
    """Single live LLM call (~1p)."""

    def test_generate_b_populates_row_and_resets_counters(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/admin/seo/city-pages/generate-variant-b",
            headers=admin_headers,
            json={"slug": SLUG_FOR_GEN_B}, timeout=120,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ok"] is True
        assert data["slug"] == SLUG_FOR_GEN_B
        assert isinstance(data["variant_b_score"], int)
        assert isinstance(data["preview"], str) and len(data["preview"]) > 0

        # Verify DB state via admin list
        list_resp = requests.get(
            f"{BASE_URL}/api/admin/seo/city-pages?status=approved&limit=20",
            headers=admin_headers, timeout=10,
        ).json()
        row = next(r for r in list_resp["rows"] if r["slug"] == SLUG_FOR_GEN_B)
        vb = row.get("variant_b")
        assert vb, "variant_b not populated"
        for k in ("body_md", "meta_title", "meta_description",
                  "confidence_score", "confidence_failed", "ai_generated_at"):
            assert k in vb, f"variant_b missing {k}"
        # Counters reset to 0
        for k in ("variant_a_impressions", "variant_b_impressions",
                  "variant_a_cta_clicks", "variant_b_cta_clicks"):
            assert row.get(k) == 0, f"{k} expected 0, got {row.get(k)}"
        assert row.get("ab_started_at"), "ab_started_at not set"


# ─── 7. promote-variant winner=b flow ──────────────────────────────


class TestPromoteVariantB:
    """winner='b' copies variant_b body/meta onto primary; unsets variant_b."""

    def test_winner_b_copies_b_to_primary(self, admin_headers):
        list_resp = requests.get(
            f"{BASE_URL}/api/admin/seo/city-pages?status=approved&limit=20",
            headers=admin_headers, timeout=10,
        ).json()
        before = next(r for r in list_resp["rows"] if r["slug"] == SLUG_FOR_GEN_B)
        vb = before.get("variant_b")
        assert vb, "precondition: variant_b must be populated"
        expected_body = vb["body_md"]
        expected_meta_title = vb["meta_title"]
        expected_meta_desc = vb["meta_description"]

        r = requests.post(
            f"{BASE_URL}/api/admin/seo/city-pages/promote-variant",
            headers=admin_headers,
            json={"slug": SLUG_FOR_GEN_B, "winner": "b"}, timeout=10,
        )
        assert r.status_code == 200, r.text
        assert r.json() == {"ok": True, "slug": SLUG_FOR_GEN_B, "winner": "b"}

        list_resp = requests.get(
            f"{BASE_URL}/api/admin/seo/city-pages?status=approved&limit=20",
            headers=admin_headers, timeout=10,
        ).json()
        after = next(r for r in list_resp["rows"] if r["slug"] == SLUG_FOR_GEN_B)
        assert after["body_md"] == expected_body, "primary body_md should equal variant B's body"
        assert after["meta_title"] == expected_meta_title
        assert after["meta_description"] == expected_meta_desc
        assert after.get("variant_b") in (None, {}), "variant_b should be unset"
        assert after.get("ab_winner") == "b"
        assert after.get("ab_won_at")

    def test_public_after_promote_b_serves_b_as_primary(self):
        s = requests.Session()
        r = s.get(f"{BASE_URL}/api/shop/city-page/{SLUG_FOR_GEN_B}", timeout=10)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "active_variant" not in body
        assert s.cookies.get("ts_cp_ab") is None
        assert body.get("body_md")

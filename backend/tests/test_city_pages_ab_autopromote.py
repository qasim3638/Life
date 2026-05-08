"""
Backend tests for the A/B winner auto-promotion feature.

Covers:
  - GET /api/admin/seo/city-pages/ab-autopromote (admin-gated, defaults)
  - PUT /api/admin/seo/city-pages/ab-autopromote (persistence + 422 ranges)
  - POST /api/admin/seo/city-pages/ab-autopromote/run-now (admin-gated, force)
  - Eligibility gates (variant_b, min_impressions, min_days)
  - _decide_winner pure function (CTR -> score -> incumbent)
  - Promotion side-effects (body_md/meta copied, counters unset, ab_won_at set)
  - Public GET after auto-promote (no cookie set, no A/B running)
  - Idempotency (last_run_date guard)
  - Disabled gate (force=False, enabled=False -> skipped)
  - Scheduler job registration in /api/import/scheduler/status

Synthetic rows are inserted directly into Mongo with a unique TEST_ prefix
and cleaned up in teardown so the live preview queue stays clean.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests

# Ensure backend module imports work
import sys
sys.path.insert(0, "/app/backend")

from config import get_db  # noqa: E402
from services.city_pages_ab_autopromote import (  # noqa: E402
    DEFAULT_SETTINGS,
    SETTINGS_ID,
    _decide_winner,
    _is_eligible,
    run_ab_autopromote_tick,
)

BASE_URL = (
    os.environ.get("REACT_APP_BACKEND_URL")
    or os.environ.get("BACKEND_URL")
    or os.environ.get("PUBLIC_PREVIEW_URL", "")
).rstrip("/")
assert BASE_URL, "BASE_URL not set"

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"

AB_URL = f"{BASE_URL}/api/admin/seo/city-pages/ab-autopromote"


# ─── fixtures ───────────────────────────────────────────────────────


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
def event_loop():
    """Module-scoped loop so we can drive Motor coroutines from sync tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def run_async(coro):
    """Run an async coro on a fresh event loop (sync test helper)."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ─── settings doc reset/cleanup ─────────────────────────────────────


@pytest.fixture(scope="module", autouse=True)
def reset_settings_around_module(event_loop):
    """Snapshot current settings, ensure tests start from defaults, then
    restore original at end so we don't enable autopromote on the live preview."""
    async def _snapshot():
        db = get_db()
        original = await db.website_settings.find_one({"_id": SETTINGS_ID})
        # Reset to no doc -> defaults active
        await db.website_settings.delete_one({"_id": SETTINGS_ID})
        return original

    async def _restore(original):
        db = get_db()
        await db.website_settings.delete_one({"_id": SETTINGS_ID})
        if original is not None:
            await db.website_settings.insert_one(original)

    original = event_loop.run_until_complete(_snapshot())
    yield
    event_loop.run_until_complete(_restore(original))


# ─── 1. GET endpoint ────────────────────────────────────────────────


class TestAbAutopromoteGet:
    def test_get_requires_admin(self):
        r = requests.get(AB_URL, timeout=10)
        assert r.status_code in (401, 403), f"unauth got {r.status_code}"

    def test_get_returns_defaults(self, admin_headers):
        r = requests.get(AB_URL, headers=admin_headers, timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        # Defaults
        assert data["enabled"] is False
        assert data["min_impressions"] == 200
        assert data["min_days"] == 14
        assert data["hour_utc"] == 5
        # last_run_date may be None (we just deleted the settings)
        assert data["last_run_date"] is None
        assert data["last_run_promoted"] == 0
        assert data["last_run_message"] is None
        # candidate_count is from live DB
        assert isinstance(data["candidate_count"], int)
        assert data["candidate_count"] >= 0


# ─── 2. PUT endpoint ────────────────────────────────────────────────


class TestAbAutopromotePut:
    def test_put_persists_values(self, admin_headers):
        r = requests.put(
            AB_URL,
            headers=admin_headers,
            json={"enabled": True, "min_impressions": 500, "min_days": 21, "hour_utc": 6},
            timeout=10,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["enabled"] is True
        assert data["min_impressions"] == 500
        assert data["min_days"] == 21
        assert data["hour_utc"] == 6

        # GET confirms persistence
        g = requests.get(AB_URL, headers=admin_headers, timeout=10)
        assert g.status_code == 200
        gdata = g.json()
        assert gdata["min_impressions"] == 500
        assert gdata["enabled"] is True

        # Reset to defaults for downstream tests
        requests.put(
            AB_URL,
            headers=admin_headers,
            json={"enabled": False, "min_impressions": 200, "min_days": 14, "hour_utc": 5},
            timeout=10,
        )

    @pytest.mark.parametrize(
        "field,value",
        [
            ("min_impressions", 5),       # < 50
            ("min_impressions", 20000),   # > 10000
            ("min_days", 0),              # < 1
            ("min_days", 200),            # > 90
            ("hour_utc", -1),             # < 0
            ("hour_utc", 24),             # > 23
        ],
    )
    def test_put_rejects_out_of_range(self, admin_headers, field, value):
        r = requests.put(AB_URL, headers=admin_headers, json={field: value}, timeout=10)
        assert r.status_code == 422, f"expected 422 for {field}={value}, got {r.status_code} {r.text}"


# ─── 3. run-now endpoint (admin gate) ───────────────────────────────


class TestAbAutopromoteRunNow:
    def test_run_now_requires_admin(self):
        r = requests.post(f"{AB_URL}/run-now", timeout=15)
        assert r.status_code in (401, 403)

    def test_run_now_force_runs_even_when_disabled(self, admin_headers):
        # Ensure disabled
        requests.put(AB_URL, headers=admin_headers, json={"enabled": False}, timeout=10)
        r = requests.post(f"{AB_URL}/run-now", headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ran"] is True
        assert isinstance(data["candidates"], int)
        assert isinstance(data["promoted"], int)
        assert isinstance(data["promotions"], list)


# ─── 4. _decide_winner pure function ────────────────────────────────


class TestDecideWinner:
    def test_b_higher_ctr(self):
        row = {
            "variant_a_impressions": 1000, "variant_a_cta_clicks": 10,
            "variant_b_impressions": 1000, "variant_b_cta_clicks": 30,
            "confidence_score": 80,
            "variant_b": {"confidence_score": 50},
        }
        winner, dec = _decide_winner(row)
        assert winner == "b"
        assert dec["a_ctr"] == 1.0
        assert dec["b_ctr"] == 3.0

    def test_a_higher_ctr(self):
        row = {
            "variant_a_impressions": 1000, "variant_a_cta_clicks": 50,
            "variant_b_impressions": 1000, "variant_b_cta_clicks": 10,
            "confidence_score": 50,
            "variant_b": {"confidence_score": 90},
        }
        winner, _ = _decide_winner(row)
        assert winner == "a"

    def test_tied_ctr_b_higher_score(self):
        row = {
            "variant_a_impressions": 500, "variant_a_cta_clicks": 0,
            "variant_b_impressions": 500, "variant_b_cta_clicks": 0,
            "confidence_score": 70,
            "variant_b": {"confidence_score": 90},
        }
        winner, _ = _decide_winner(row)
        assert winner == "b"

    def test_full_tie_incumbent_wins(self):
        row = {
            "variant_a_impressions": 500, "variant_a_cta_clicks": 0,
            "variant_b_impressions": 500, "variant_b_cta_clicks": 0,
            "confidence_score": 80,
            "variant_b": {"confidence_score": 80},
        }
        winner, _ = _decide_winner(row)
        assert winner == "a"


# ─── 5. _is_eligible gate ───────────────────────────────────────────


class TestIsEligible:
    def _now(self):
        return datetime.now(timezone.utc)

    def test_no_variant_b(self):
        assert not _is_eligible({}, min_impressions=200, min_days=14, now_utc=self._now())

    def test_below_impressions(self):
        row = {
            "variant_b": {"body_md": "x"},
            "variant_a_impressions": 100,
            "variant_b_impressions": 250,
            "ab_started_at": self._now() - timedelta(days=20),
        }
        assert not _is_eligible(row, min_impressions=200, min_days=14, now_utc=self._now())

    def test_too_recent(self):
        row = {
            "variant_b": {"body_md": "x"},
            "variant_a_impressions": 300,
            "variant_b_impressions": 300,
            "ab_started_at": self._now() - timedelta(days=2),
        }
        assert not _is_eligible(row, min_impressions=200, min_days=14, now_utc=self._now())

    def test_eligible(self):
        row = {
            "variant_b": {"body_md": "x"},
            "variant_a_impressions": 300,
            "variant_b_impressions": 300,
            "ab_started_at": self._now() - timedelta(days=20),
        }
        assert _is_eligible(row, min_impressions=200, min_days=14, now_utc=self._now())


# ─── 6. End-to-end synthetic row promotion ──────────────────────────


def _make_test_slug(label: str) -> str:
    return f"TEST-autopromote-{label}-{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="class")
def synthetic_rows(event_loop):
    """Insert four synthetic city_landing_pages rows covering each gate
    case, yield slugs, then clean up."""
    slugs = {
        "ready": _make_test_slug("ready"),
        "low_imp": _make_test_slug("low-imp"),
        "too_recent": _make_test_slug("too-recent"),
        "no_b": _make_test_slug("no-b"),
    }
    now = datetime.now(timezone.utc)

    async def _seed():
        db = get_db()
        common = {
            "town": "TestTown",
            "town_slug": "testtown",
            "intent_phrase": "test tiles",
            "h1": "TEST",
            "url": "/tiles/test",
            "status": "approved",
            "body_md": "ORIGINAL_A_BODY",
            "meta_title": "ORIGINAL_A_TITLE",
            "meta_description": "ORIGINAL_A_META",
            "confidence_score": 70,
        }
        # (a) eligible -> should be promoted (B wins on score, CTRs tied at 0)
        await db.city_landing_pages.insert_one({
            **common,
            "slug": slugs["ready"],
            "variant_b": {
                "body_md": "VARIANT_B_BODY",
                "meta_title": "VARIANT_B_TITLE",
                "meta_description": "VARIANT_B_META",
                "confidence_score": 95,
                "confidence_failed": [],
            },
            "variant_a_impressions": 300,
            "variant_b_impressions": 300,
            "variant_a_cta_clicks": 0,
            "variant_b_cta_clicks": 0,
            "ab_started_at": now - timedelta(days=20),
        })
        # (b) impressions just below threshold
        await db.city_landing_pages.insert_one({
            **common,
            "slug": slugs["low_imp"],
            "variant_b": {
                "body_md": "VB_LOWIMP", "meta_title": "x", "meta_description": "x",
                "confidence_score": 80, "confidence_failed": [],
            },
            "variant_a_impressions": 100,
            "variant_b_impressions": 199,
            "variant_a_cta_clicks": 0, "variant_b_cta_clicks": 0,
            "ab_started_at": now - timedelta(days=20),
        })
        # (c) too recent
        await db.city_landing_pages.insert_one({
            **common,
            "slug": slugs["too_recent"],
            "variant_b": {
                "body_md": "VB_RECENT", "meta_title": "x", "meta_description": "x",
                "confidence_score": 80, "confidence_failed": [],
            },
            "variant_a_impressions": 500, "variant_b_impressions": 500,
            "variant_a_cta_clicks": 0, "variant_b_cta_clicks": 0,
            "ab_started_at": now - timedelta(days=2),
        })
        # (d) no variant_b at all
        await db.city_landing_pages.insert_one({
            **common,
            "slug": slugs["no_b"],
        })

    async def _cleanup():
        db = get_db()
        await db.city_landing_pages.delete_many({"slug": {"$in": list(slugs.values())}})

    event_loop.run_until_complete(_seed())
    yield slugs
    event_loop.run_until_complete(_cleanup())


class TestRunAbAutopromoteTick:
    def test_promotes_eligible_and_skips_others(self, synthetic_rows, admin_headers, event_loop):
        # Reset settings to defaults so eligibility gates apply (200 / 14)
        async def _reset():
            db = get_db()
            await db.website_settings.delete_one({"_id": SETTINGS_ID})

        event_loop.run_until_complete(_reset())

        # Use force=True via direct service call
        result = event_loop.run_until_complete(run_ab_autopromote_tick(force=True))

        assert result["ran"] is True
        promoted_slugs = {p["slug"] for p in result["promotions"]}
        assert synthetic_rows["ready"] in promoted_slugs, (
            f"ready slug not promoted: {result}"
        )
        assert synthetic_rows["low_imp"] not in promoted_slugs
        assert synthetic_rows["too_recent"] not in promoted_slugs
        assert synthetic_rows["no_b"] not in promoted_slugs

        # Verify DB state for ready row -> winner=b, body replaced, counters unset
        async def _fetch():
            db = get_db()
            return await db.city_landing_pages.find_one(
                {"slug": synthetic_rows["ready"]}, {"_id": 0}
            )

        row = event_loop.run_until_complete(_fetch())
        assert row is not None
        assert row["body_md"] == "VARIANT_B_BODY"
        assert row["meta_title"] == "VARIANT_B_TITLE"
        assert row["meta_description"] == "VARIANT_B_META"
        assert row["confidence_score"] == 95
        assert row.get("ab_winner") == "b"
        assert "ab_won_at" in row
        assert "ab_won_decision" in row
        # All A/B fields unset
        for f in ("variant_b", "variant_a_impressions", "variant_b_impressions",
                  "variant_a_cta_clicks", "variant_b_cta_clicks", "ab_started_at"):
            assert f not in row, f"{f} should be unset, got row keys {list(row.keys())}"

        # The other synthetic rows should still have their variant_b intact
        async def _fetch_low():
            db = get_db()
            return await db.city_landing_pages.find_one(
                {"slug": synthetic_rows["low_imp"]}, {"_id": 0}
            )

        low_row = event_loop.run_until_complete(_fetch_low())
        assert low_row.get("variant_b") is not None
        assert low_row.get("ab_winner") is None

    def test_public_get_after_promotion_no_cookie(self, synthetic_rows):
        # The 'ready' row has been promoted in the previous test. It's
        # status=approved, no variant_b -> public GET should return it
        # WITHOUT setting ts_cp_ab cookie.
        slug = synthetic_rows["ready"]
        s = requests.Session()
        r = s.get(f"{BASE_URL}/api/shop/city-page/{slug}", timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["body_md"] == "VARIANT_B_BODY"
        # No active_variant key (A/B test concluded)
        assert "active_variant" not in data
        # No A/B cookie set
        set_cookie = r.headers.get("Set-Cookie", "")
        assert "ts_cp_ab" not in set_cookie.lower()


# ─── 7. Idempotency & disabled gate ─────────────────────────────────


class TestIdempotencyAndGates:
    def test_idempotency_already_ran_today(self, admin_headers, event_loop):
        # Enable so non-force tick doesn't bail on disabled
        requests.put(AB_URL, headers=admin_headers, json={"enabled": True}, timeout=10)

        # Force-run sets last_run_date=today
        r1 = requests.post(f"{AB_URL}/run-now", headers=admin_headers, timeout=30)
        assert r1.status_code == 200

        # Now a non-force tick should skip with already_ran_today
        result = event_loop.run_until_complete(run_ab_autopromote_tick(force=False))
        # If hour_utc doesn't match, it might say wrong_hour first.
        # Both wrong_hour and already_ran_today are valid skip reasons here,
        # but the spec asks for already_ran_today specifically when hour matches.
        # We accept either skip (since we can't control current hour vs hour_utc),
        # but try to coerce hour_utc to current hour first to validate the
        # already_ran_today branch precisely.
        now_hour = datetime.now(timezone.utc).hour
        requests.put(AB_URL, headers=admin_headers, json={"hour_utc": now_hour}, timeout=10)
        result2 = event_loop.run_until_complete(run_ab_autopromote_tick(force=False))
        assert result2.get("skipped") is True
        assert result2.get("reason") == "already_ran_today", f"got {result2}"

        # Cleanup: disable + reset hour_utc
        requests.put(AB_URL, headers=admin_headers, json={"enabled": False, "hour_utc": 5}, timeout=10)

    def test_disabled_gate_returns_skipped(self, admin_headers, event_loop):
        # Ensure disabled
        requests.put(AB_URL, headers=admin_headers, json={"enabled": False}, timeout=10)
        result = event_loop.run_until_complete(run_ab_autopromote_tick(force=False))
        assert result == {"skipped": True, "reason": "disabled"}


# ─── 8. Scheduler job registered ────────────────────────────────────


class TestSchedulerJobRegistered:
    def test_ab_autopromote_in_status(self, admin_headers):
        r = requests.get(
            f"{BASE_URL}/api/import/scheduler/status", headers=admin_headers, timeout=10
        )
        assert r.status_code == 200, r.text
        data = r.json()
        # status payload could be {"jobs": [...]} or list directly
        jobs = data.get("jobs") if isinstance(data, dict) else data
        assert isinstance(jobs, list)
        ids = [j.get("id") for j in jobs]
        assert "city_pages_ab_autopromote" in ids, f"job not registered: {ids}"
        job = next(j for j in jobs if j.get("id") == "city_pages_ab_autopromote")
        # Must have a future next_run timestamp
        assert job.get("next_run") or job.get("next_run_time"), f"no next_run: {job}"

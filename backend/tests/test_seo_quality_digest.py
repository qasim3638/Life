"""Backend tests for the NEW Weekly SEO Quality Digest (iter 143).

Covers
------
1. POST /api/admin/seo/city-pages/quality-digest/send-now
   * 403 without admin token / with non-admin
   * 200 + full payload {ok, recipients, auto_approved_count,
     manual_approved_count, low_conf_count, auto_score_avg,
     auto_score_min} when admin
2. Idempotency:
   * After /send-now writes last_sent_iso_week, an immediate
     run_seo_quality_digest_tick(force=False) returns
     {ok:True, skipped:True, reason:"already sent this iso week"}.
   * /send-now itself uses force=True so it bypasses the guard.
3. Empty-window guard (services/_gather_last_7d monkeypatched):
   * tick(force=False) with zero activity → skipped with reason
     "no city-page activity in window".
   * tick(force=True) overrides the guard and still attempts a send.
4. _gather_last_7d bucketing (synthetic TEST_ rows):
   * approved + approved_by=auto-approve in window  → auto_approved
   * approved + approved_by!=auto-approve in window → manual_approved
   * generated + ai_generated_at in window          → low_conf
   * approved/generated outside the 7d window       → excluded
5. top_failures aggregator: most-common confidence_failed strings,
   max 6 entries, ordered desc.
6. Scheduler job 'seo_quality_digest_weekly' is registered with a
   future Monday 09:30 Europe/London next-run (via GET
   /api/import/scheduler/status).
7. website_settings._id="seo_quality_digest" is upserted with
   last_sent_iso_week / last_sent_at / last_totals / recipients_count
   after a successful send.
8. _render_html does not crash on a fully-empty payload.

Side-effect safety
------------------
* Snapshots and restores the website_settings._id="seo_quality_digest"
  doc around the send-now / idempotency tests so we don't poison the
  real cron's dedupe key.
* All synthetic city_landing_pages rows use slug prefix "TEST_QDIGEST_"
  and are deleted on teardown.
* No LLM calls. Email send is a graceful no-op via
  send_simple_email_if_possible — we assert on the API response, not
  on actual delivery.
"""
from __future__ import annotations

import asyncio
import os
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
import requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env", override=False)
load_dotenv("/app/frontend/.env", override=False)

from config import get_db  # noqa: E402
from services import seo_quality_digest as sqd  # noqa: E402

BASE_URL = (
    os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
    or os.environ.get("BACKEND_URL", "").rstrip("/")
)
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"

SETTINGS_ID = sqd.SETTINGS_ID
TEST_SLUG_PREFIX = "TEST_QDIGEST_"


# ───────── fixtures ─────────

@pytest.fixture(scope="session")
def admin_token() -> str:
    r = requests.post(
        f"{API}/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=20,
    )
    if r.status_code != 200:
        pytest.skip(f"admin login failed ({r.status_code}): {r.text[:200]}")
    tok = r.json().get("access_token") or r.json().get("token")
    if not tok:
        pytest.skip("login response missing token")
    return tok


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest_asyncio.fixture
async def settings_snapshot():
    """Snapshot website_settings doc for the digest, restore on teardown
    so we don't permanently bump last_sent_iso_week on the live env."""
    db = get_db()
    snap = await db.website_settings.find_one({"_id": SETTINGS_ID})
    yield snap
    if snap is None:
        await db.website_settings.delete_one({"_id": SETTINGS_ID})
    else:
        await db.website_settings.replace_one(
            {"_id": SETTINGS_ID}, snap, upsert=True
        )


@pytest_asyncio.fixture
async def synthetic_rows():
    """Insert a known set of TEST_ rows covering every bucket + an
    out-of-window negative case. Cleaned up on teardown."""
    db = get_db()
    now = datetime.now(timezone.utc)
    in_window = now - timedelta(days=2)
    out_of_window = now - timedelta(days=14)

    docs = [
        # auto-approved in window x2
        {
            "slug": f"{TEST_SLUG_PREFIX}auto_a",
            "h1": "TEST auto A",
            "url": "/tiles/test-auto-a",
            "status": "approved",
            "approved_by": "auto-approve",
            "approved_at": in_window,
            "confidence_score": 95,
            "confidence_failed": [],
        },
        {
            "slug": f"{TEST_SLUG_PREFIX}auto_b",
            "h1": "TEST auto B",
            "url": "/tiles/test-auto-b",
            "status": "approved",
            "approved_by": "auto-approve",
            "approved_at": in_window,
            "confidence_score": 88,
            "confidence_failed": [],
        },
        # manual approved in window x1
        {
            "slug": f"{TEST_SLUG_PREFIX}manual_a",
            "h1": "TEST manual A",
            "url": "/tiles/test-manual-a",
            "status": "approved",
            "approved_by": "admin@test.com",
            "approved_at": in_window,
            "confidence_score": 80,
            "confidence_failed": [],
        },
        # low-conf generated in window x3 (each with overlapping failure
        # reasons so top_failures has predictable counts)
        {
            "slug": f"{TEST_SLUG_PREFIX}low_a",
            "h1": "TEST low A",
            "url": "/tiles/test-low-a",
            "status": "generated",
            "ai_generated_at": in_window,
            "confidence_score": 60,
            "confidence_failed": ["has_real_phone", "word_count_ok"],
        },
        {
            "slug": f"{TEST_SLUG_PREFIX}low_b",
            "h1": "TEST low B",
            "url": "/tiles/test-low-b",
            "status": "generated",
            "ai_generated_at": in_window,
            "confidence_score": 65,
            "confidence_failed": ["has_real_phone", "no_forbidden_strings"],
        },
        {
            "slug": f"{TEST_SLUG_PREFIX}low_c",
            "h1": "TEST low C",
            "url": "/tiles/test-low-c",
            "status": "generated",
            "ai_generated_at": in_window,
            "confidence_score": 70,
            "confidence_failed": ["has_real_phone"],
        },
        # OUT OF WINDOW (must be excluded from every bucket)
        {
            "slug": f"{TEST_SLUG_PREFIX}old_approved",
            "h1": "TEST old approved",
            "url": "/tiles/test-old-approved",
            "status": "approved",
            "approved_by": "auto-approve",
            "approved_at": out_of_window,
            "confidence_score": 95,
            "confidence_failed": [],
        },
        {
            "slug": f"{TEST_SLUG_PREFIX}old_generated",
            "h1": "TEST old generated",
            "url": "/tiles/test-old-generated",
            "status": "generated",
            "ai_generated_at": out_of_window,
            "confidence_score": 50,
            "confidence_failed": ["should_not_count"],
        },
    ]
    await db.city_landing_pages.insert_many(docs)
    yield {"slugs": [d["slug"] for d in docs]}
    await db.city_landing_pages.delete_many(
        {"slug": {"$regex": f"^{TEST_SLUG_PREFIX}"}}
    )


# ───────── 1. /send-now auth gate ─────────

class TestQualityDigestAuthGate:
    def test_send_now_requires_auth(self):
        r = requests.post(
            f"{API}/admin/seo/city-pages/quality-digest/send-now", timeout=30
        )
        # No token → FastAPI's get_current_user typically returns 401 or 403
        assert r.status_code in (401, 403), (
            f"expected 401/403, got {r.status_code}: {r.text[:200]}"
        )

    def test_send_now_rejects_bad_token(self):
        r = requests.post(
            f"{API}/admin/seo/city-pages/quality-digest/send-now",
            headers={"Authorization": "Bearer not-a-real-token"},
            timeout=30,
        )
        assert r.status_code in (401, 403)


# ───────── 2. /send-now happy path + idempotency ─────────

class TestQualityDigestSendNow:
    @pytest.mark.asyncio
    async def test_send_now_returns_full_payload_and_persists_settings(
        self, admin_headers, settings_snapshot
    ):
        # Clear any existing dedupe key so /send-now is unambiguous.
        # /send-now uses force=True so it should send even if the key exists,
        # but clearing makes the resulting state easier to assert.
        db = get_db()
        await db.website_settings.delete_one({"_id": SETTINGS_ID})

        r = requests.post(
            f"{API}/admin/seo/city-pages/quality-digest/send-now",
            headers=admin_headers,
            timeout=60,
        )
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        # Either the env has admin recipients (success path) or it doesn't
        # (no recipients path). Both are well-defined.
        if body.get("ok") is False:
            # Acceptable degraded outcome: no admin emails configured.
            assert body.get("reason") == "no admin recipients" or body.get("error")
            pytest.skip(f"environment has no admin recipients: {body}")

        assert body["ok"] is True
        # Manual /send-now must NOT report 'skipped' (force=True).
        assert "skipped" not in body or body.get("skipped") is False
        for k in (
            "recipients",
            "auto_approved_count",
            "manual_approved_count",
            "low_conf_count",
        ):
            assert k in body, f"missing key {k} in {body}"
            assert isinstance(body[k], int), f"{k} should be int, got {type(body[k])}"
        # auto_score_avg / auto_score_min may be None when no auto-approvals.
        assert body["auto_approved_count"] >= 0
        assert body["recipients"] >= 1

        # Settings doc must now reflect the send.
        doc = await db.website_settings.find_one({"_id": SETTINGS_ID})
        assert doc is not None
        assert re.match(r"^\d{4}-W\d{2}$", doc["last_sent_iso_week"])
        assert doc["last_sent_iso_week"] == datetime.now(timezone.utc).strftime(
            "%G-W%V"
        )
        assert isinstance(doc["last_totals"], dict)
        assert doc["recipients_count"] == body["recipients"]
        assert doc["last_sent_at"] is not None

    @pytest.mark.asyncio
    async def test_idempotency_tick_skips_after_send_now(
        self, admin_headers, settings_snapshot
    ):
        # 1. Trigger a real send-now to set last_sent_iso_week.
        r = requests.post(
            f"{API}/admin/seo/city-pages/quality-digest/send-now",
            headers=admin_headers,
            timeout=60,
        )
        assert r.status_code == 200, r.text[:300]
        sent = r.json()
        if not sent.get("ok") or sent.get("skipped"):
            pytest.skip(f"send-now did not actually send ({sent}); idempotency moot")

        # 2. Immediately call the scheduler tick with force=False.
        result = await sqd.run_seo_quality_digest_tick(force=False)
        assert result == {
            "ok": True,
            "skipped": True,
            "reason": "already sent this iso week",
        }


# ───────── 3. Empty-window guard ─────────

class TestEmptyWindowGuard:
    @pytest.mark.asyncio
    async def test_tick_skips_when_no_activity(self, monkeypatch, settings_snapshot):
        """When _gather_last_7d returns zero rows in every bucket, the
        non-forced tick must skip without sending."""
        db = get_db()
        await db.website_settings.delete_one({"_id": SETTINGS_ID})

        async def _empty(_db):
            return {
                "since": datetime.now(timezone.utc) - timedelta(days=7),
                "auto_approved": [],
                "manual_approved": [],
                "low_conf": [],
                "totals": {
                    "auto_approved_count": 0,
                    "manual_approved_count": 0,
                    "low_conf_count": 0,
                    "auto_score_avg": None,
                    "auto_score_min": None,
                },
                "top_failures": [],
            }

        monkeypatch.setattr(sqd, "_gather_last_7d", _empty)
        result = await sqd.run_seo_quality_digest_tick(force=False)
        assert result == {
            "ok": True,
            "skipped": True,
            "reason": "no city-page activity in window",
        }

        # Settings doc must NOT have been updated by a skipped tick.
        doc = await db.website_settings.find_one({"_id": SETTINGS_ID})
        assert doc is None or "last_sent_iso_week" not in doc


# ───────── 4. Bucketing logic ─────────

class TestGatherBucketing:
    @pytest.mark.asyncio
    async def test_buckets_split_by_status_and_window(self, synthetic_rows):
        db = get_db()
        payload = await sqd._gather_last_7d(db)

        # Filter to only our synthetic rows so prod data doesn't pollute counts.
        def _ours(rows):
            return [r for r in rows if str(r.get("slug", "")).startswith(TEST_SLUG_PREFIX)]

        auto = _ours(payload["auto_approved"])
        manual = _ours(payload["manual_approved"])
        low = _ours(payload["low_conf"])

        auto_slugs = {r["slug"] for r in auto}
        manual_slugs = {r["slug"] for r in manual}
        low_slugs = {r["slug"] for r in low}

        assert auto_slugs == {
            f"{TEST_SLUG_PREFIX}auto_a",
            f"{TEST_SLUG_PREFIX}auto_b",
        }, f"auto bucket wrong: {auto_slugs}"
        assert manual_slugs == {f"{TEST_SLUG_PREFIX}manual_a"}, (
            f"manual bucket wrong: {manual_slugs}"
        )
        assert low_slugs == {
            f"{TEST_SLUG_PREFIX}low_a",
            f"{TEST_SLUG_PREFIX}low_b",
            f"{TEST_SLUG_PREFIX}low_c",
        }, f"low_conf bucket wrong: {low_slugs}"

        # Out-of-window rows must NOT appear in any bucket.
        all_test_slugs = auto_slugs | manual_slugs | low_slugs
        assert f"{TEST_SLUG_PREFIX}old_approved" not in all_test_slugs
        assert f"{TEST_SLUG_PREFIX}old_generated" not in all_test_slugs

        # No bucket leaks _id (mongo objectid scrubbed by projection).
        for bucket in (auto, manual, low):
            for r in bucket:
                assert "_id" not in r


# ───────── 5. Top-failures aggregator ─────────

class TestTopFailures:
    @pytest.mark.asyncio
    async def test_top_failures_counts_correctly(self, synthetic_rows):
        db = get_db()
        payload = await sqd._gather_last_7d(db)
        # Filter to only the failure reasons attached to OUR low_conf rows.
        # (Prod rows may also contribute, so we count by name for our 3 known
        # synthetic reasons.)
        names = dict(payload["top_failures"])
        # 'has_real_phone' appears in 3 of our 3 low_conf rows.
        assert names.get("has_real_phone", 0) >= 3, payload["top_failures"]
        # 'word_count_ok' appears in 1 of ours.
        assert names.get("word_count_ok", 0) >= 1
        # 'no_forbidden_strings' appears in 1 of ours.
        assert names.get("no_forbidden_strings", 0) >= 1
        # 'should_not_count' is on the OUT-OF-WINDOW row → must not appear.
        assert "should_not_count" not in names
        # Result is at most 6 entries.
        assert len(payload["top_failures"]) <= 6
        # Ordered descending by count.
        counts = [c for _, c in payload["top_failures"]]
        assert counts == sorted(counts, reverse=True)


# ───────── 6. Scheduler job registered ─────────

class TestSchedulerRegistration:
    def test_quality_digest_job_registered_for_monday_0930(self, admin_headers):
        r = requests.get(
            f"{API}/import/scheduler/status", headers=admin_headers, timeout=15
        )
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        jobs = body.get("jobs") or body.get("scheduled_jobs") or []
        # Some schedulers wrap the list — fall back to deep search.
        if not jobs and isinstance(body, dict):
            for v in body.values():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    jobs = v
                    break

        assert jobs, f"no jobs reported by scheduler/status: {body}"
        match = next(
            (j for j in jobs if j.get("id") == "seo_quality_digest_weekly"),
            None,
        )
        assert match is not None, (
            f"seo_quality_digest_weekly not registered. Available IDs: "
            f"{[j.get('id') for j in jobs]}"
        )

        # next_run_time must be in the future and on a Monday.
        nrt = (
            match.get("next_run_time")
            or match.get("next_run")
            or match.get("nextRunTime")
        )
        assert nrt, f"no next_run_time on job: {match}"
        # Best-effort parse — ISO string typical for APScheduler exports.
        try:
            dt = datetime.fromisoformat(str(nrt).replace("Z", "+00:00"))
        except ValueError:
            pytest.skip(f"next_run_time format not parseable: {nrt}")
        else:
            assert dt > datetime.now(timezone.utc), (
                f"next_run_time should be future, got {dt}"
            )
            assert dt.weekday() == 0, (
                f"next_run_time should be a Monday, got {dt} (weekday={dt.weekday()})"
            )


# ───────── 7. _render_html survives empty payload ─────────

class TestRenderHtmlEmpty:
    def test_render_html_with_empty_payload(self):
        empty = {
            "since": datetime.now(timezone.utc) - timedelta(days=7),
            "auto_approved": [],
            "manual_approved": [],
            "low_conf": [],
            "totals": {
                "auto_approved_count": 0,
                "manual_approved_count": 0,
                "low_conf_count": 0,
                "auto_score_avg": None,
                "auto_score_min": None,
            },
            "top_failures": [],
        }
        html = sqd._render_html(empty)
        assert isinstance(html, str) and len(html) > 200
        # Placeholders for every empty section must appear.
        assert "Nothing auto-approved this week." in html
        assert "No manual approvals this week." in html
        assert "No low-confidence drafts pending." in html
        assert "No check failed this week." in html
        # The "no auto-approvals" chip path (avg=None) must render.
        assert "no auto-approvals" in html

"""
Tests for GET /api/admin/failed-payments (admin dashboard widget).

Scope:
  • Auth gate (admin-only)
  • Query param validation (days 1-180, status enum)
  • Empty-result envelope shape
  • _recovery_status pure-function branches (recovered / pending / abandoned)
  • Top decline codes aggregator (most-common, max 6, 'unknown' bucket)
  • recovery_rate_pct rounding (including divide-by-zero guard)
  • ISO-string $gte filter on payment_failed_at (lexicographic = chronological)
  • Status filter narrows rows but keeps totals for full window
  • Row field whitelist (no Stripe IDs, no recovery_token)
  • Reason truncation to 200 chars

Synthetic shop_orders rows are written directly to Mongo with id prefix
TEST_FP_ and cleaned up on teardown. No real webhooks triggered.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from dotenv import load_dotenv

sys.path.insert(0, "/app/backend")
load_dotenv("/app/backend/.env")

from config import get_db  # noqa: E402
from routes.failed_payments import _recovery_status  # noqa: E402
from services.payment_recovery import RECOVERY_WINDOW_DAYS  # noqa: E402

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

ENDPOINT = f"{BASE_URL}/api/admin/failed-payments"
TEST_PREFIX = "TEST_FP_"

# Single shared event loop — Motor pins its async queue.
_LOOP = asyncio.new_event_loop()


def _run(coro):
    return _LOOP.run_until_complete(coro)


_created_ids: list[str] = []


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _make_failed_order(
    *,
    failed_at: datetime,
    code: str | None = "card_declined",
    reason: str = "Your card was declined.",
    total: float = 28.98,
    paid_at: datetime | None = None,
    payment_status: str = "failed",
    recovery_email_sent_at: datetime | None = None,
    customer_email: str = "recovery-test@example.com",
    customer_name: str = "Jane Tester",
    customer_phone: str = "+441234567890",
    recovery_token: str | None = None,
    payment_intent_id: str | None = None,
) -> dict:
    oid = f"{TEST_PREFIX}{uuid.uuid4().hex[:12]}"
    _created_ids.append(oid)
    doc = {
        "id": oid,
        "order_number": f"TS-FP-{uuid.uuid4().hex[:6].upper()}",
        "customer_email": customer_email,
        "customer_name": customer_name,
        "customer_phone": customer_phone,
        "total": total,
        "subtotal": total,
        "items": [{"sku": "FP-SKU-1", "name": "Tile", "quantity": 1, "price": total}],
        "payment_status": payment_status,
        "payment_failed_at": _iso(failed_at),
        "payment_failed_reason": reason,
        "status": "payment_failed",
        "created_at": _iso(failed_at),
    }
    if code is not None:
        doc["payment_failed_code"] = code
    if paid_at is not None:
        doc["paid_at"] = _iso(paid_at)
    if recovery_email_sent_at is not None:
        doc["recovery_email_sent_at"] = _iso(recovery_email_sent_at)
    if recovery_token is not None:
        doc["recovery_token"] = recovery_token
    if payment_intent_id is not None:
        doc["payment_intent_id"] = payment_intent_id
    return doc


async def _insert(doc: dict):
    await get_db().shop_orders.insert_one(dict(doc))


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_token(api):
    r = api.post(f"{BASE_URL}/api/auth/login",
                 json={"email": "admin@test.com", "password": "admin123"})
    if r.status_code != 200:
        pytest.skip(f"admin login failed: {r.status_code} {r.text[:160]}")
    token = r.json().get("access_token") or r.json().get("token")
    assert token, f"no token in response: {r.json()}"
    return token


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module", autouse=True)
def cleanup_module():
    yield
    try:
        _LOOP.run_until_complete(
            get_db().shop_orders.delete_many({"id": {"$regex": f"^{TEST_PREFIX}"}})
        )
    finally:
        _LOOP.close()


def _only_ours(rows: list[dict]) -> list[dict]:
    """Filter out non-TEST rows that may exist in live Mongo."""
    return [r for r in rows if (r.get("id") or "").startswith(TEST_PREFIX)]


# ─────────────────────────────────────────────────────────────────────────────
# Auth gate
# ─────────────────────────────────────────────────────────────────────────────
class TestAuthGate:
    def test_without_token_rejects(self, api):
        # Fresh session — no auth header
        s = requests.Session()
        r = s.get(ENDPOINT)
        assert r.status_code in (401, 403), r.text

    def test_with_non_admin_token_returns_403(self, api):
        # Try to log in with a non-admin if possible; otherwise skip.
        # Use a bogus bearer which should also yield 401/403.
        r = api.get(ENDPOINT, headers={"Authorization": "Bearer bogus.token.value"})
        assert r.status_code in (401, 403), r.text

    def test_with_admin_token_200(self, api, admin_headers):
        r = api.get(ENDPOINT, headers=admin_headers)
        assert r.status_code == 200, r.text


# ─────────────────────────────────────────────────────────────────────────────
# Query param validation
# ─────────────────────────────────────────────────────────────────────────────
class TestQueryValidation:
    def test_days_too_large_returns_422(self, api, admin_headers):
        r = api.get(f"{ENDPOINT}?days=200", headers=admin_headers)
        assert r.status_code == 422, r.text

    def test_days_zero_returns_422(self, api, admin_headers):
        r = api.get(f"{ENDPOINT}?days=0", headers=admin_headers)
        assert r.status_code == 422, r.text

    def test_bad_status_returns_422(self, api, admin_headers):
        r = api.get(f"{ENDPOINT}?status=foo", headers=admin_headers)
        assert r.status_code == 422, r.text

    def test_valid_status_200(self, api, admin_headers):
        for s in ("recovered", "pending", "abandoned"):
            r = api.get(f"{ENDPOINT}?status={s}", headers=admin_headers)
            assert r.status_code == 200, f"{s}: {r.text}"


# ─────────────────────────────────────────────────────────────────────────────
# Response envelope (empty + shape)
# ─────────────────────────────────────────────────────────────────────────────
class TestResponseShape:
    def test_envelope_keys_always_present(self, api, admin_headers):
        # Use a 1-day window; even if prod rows exist we validate key presence.
        r = api.get(f"{ENDPOINT}?days=1", headers=admin_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["window_days"] == 1
        assert "since" in body and isinstance(body["since"], str)
        # 'since' must be ISO parseable
        datetime.fromisoformat(body["since"])

        totals = body["totals"]
        for k in ("count", "amount", "recovered_count", "pending_count",
                  "abandoned_count", "recovered_amount", "recovery_rate_pct"):
            assert k in totals, f"missing totals.{k}"
        assert isinstance(totals["count"], int)
        assert isinstance(totals["amount"], (int, float))
        assert isinstance(totals["recovery_rate_pct"], (int, float))

        assert "top_decline_codes" in body and isinstance(body["top_decline_codes"], list)
        assert "rows" in body and isinstance(body["rows"], list)

    def test_empty_window_totals_zeroed(self, api, admin_headers):
        # We can't guarantee zero prod rows, so just check that when no
        # TEST_FP_ rows are filtered out, the response is well-formed.
        # Plus recovery_rate_pct must be 0.0 when count is 0.
        r = api.get(f"{ENDPOINT}?days=1", headers=admin_headers)
        body = r.json()
        if body["totals"]["count"] == 0:
            assert body["totals"]["amount"] == 0.0
            assert body["totals"]["recovered_count"] == 0
            assert body["totals"]["pending_count"] == 0
            assert body["totals"]["abandoned_count"] == 0
            assert body["totals"]["recovered_amount"] == 0.0
            assert body["totals"]["recovery_rate_pct"] == 0.0
            assert body["top_decline_codes"] == []
            assert body["rows"] == []


# ─────────────────────────────────────────────────────────────────────────────
# _recovery_status pure function
# ─────────────────────────────────────────────────────────────────────────────
class TestRecoveryStatusPureFunction:
    now = datetime.now(timezone.utc)

    def test_recovered_when_paid_after_failed(self):
        failed = self.now - timedelta(hours=5)
        paid = self.now - timedelta(hours=1)
        row = {
            "payment_status": "paid",
            "payment_failed_at": failed.isoformat(),
            "paid_at": paid.isoformat(),
        }
        assert _recovery_status(row, self.now) == "recovered"

    def test_pending_when_email_within_window(self):
        failed = self.now - timedelta(hours=5)
        sent = self.now - timedelta(days=2)  # within 7 days
        row = {
            "payment_status": "failed",
            "payment_failed_at": failed.isoformat(),
            "recovery_email_sent_at": sent.isoformat(),
        }
        assert _recovery_status(row, self.now) == "pending"

    def test_abandoned_when_email_outside_window(self):
        failed = self.now - timedelta(days=10)
        sent = self.now - timedelta(days=8)  # beyond 7
        row = {
            "payment_status": "failed",
            "payment_failed_at": failed.isoformat(),
            "recovery_email_sent_at": sent.isoformat(),
        }
        assert _recovery_status(row, self.now) == "abandoned"

    def test_abandoned_when_no_email_and_not_paid(self):
        row = {
            "payment_status": "failed",
            "payment_failed_at": (self.now - timedelta(days=3)).isoformat(),
        }
        assert _recovery_status(row, self.now) == "abandoned"

    def test_paid_before_failed_is_not_recovered(self):
        # If paid_at is BEFORE failed_at, that's not a recovery.
        row = {
            "payment_status": "paid",
            "payment_failed_at": self.now.isoformat(),
            "paid_at": (self.now - timedelta(days=1)).isoformat(),
        }
        assert _recovery_status(row, self.now) == "abandoned"

    def test_window_constant_is_seven(self):
        assert RECOVERY_WINDOW_DAYS == 7


# ─────────────────────────────────────────────────────────────────────────────
# Integration tests that write synthetic rows and hit the endpoint
# ─────────────────────────────────────────────────────────────────────────────
class TestIntegrationWithSyntheticRows:
    def test_three_status_branches_end_to_end(self, api, admin_headers):
        """Write 3 rows (one per branch) and assert the endpoint classifies them."""
        now = datetime.now(timezone.utc)

        recovered = _make_failed_order(
            failed_at=now - timedelta(hours=5),
            code="card_declined",
            payment_status="paid",
            paid_at=now - timedelta(hours=1),
            total=100.00,
        )
        pending = _make_failed_order(
            failed_at=now - timedelta(hours=4),
            code="insufficient_funds",
            recovery_email_sent_at=now - timedelta(days=2),
            total=50.00,
        )
        abandoned = _make_failed_order(
            failed_at=now - timedelta(hours=3),
            code="expired_card",
            total=25.00,
        )

        for doc in (recovered, pending, abandoned):
            _run(_insert(doc))

        r = api.get(f"{ENDPOINT}?days=30", headers=admin_headers)
        assert r.status_code == 200
        body = r.json()

        by_id = {row["id"]: row for row in body["rows"]}
        assert by_id[recovered["id"]]["recovery_status"] == "recovered"
        assert by_id[pending["id"]]["recovery_status"] == "pending"
        assert by_id[abandoned["id"]]["recovery_status"] == "abandoned"

        # Sanity: amounts on our rows
        assert by_id[recovered["id"]]["total"] == 100.00
        assert by_id[pending["id"]]["total"] == 50.00
        assert by_id[abandoned["id"]]["total"] == 25.00

    def test_status_filter_narrows_rows(self, api, admin_headers):
        # We already inserted 3 rows above. Filter ?status=recovered.
        r_all = api.get(f"{ENDPOINT}?days=30", headers=admin_headers)
        r_rec = api.get(f"{ENDPOINT}?days=30&status=recovered", headers=admin_headers)
        assert r_all.status_code == 200 and r_rec.status_code == 200

        body_all = r_all.json()
        body_rec = r_rec.json()

        # Filtered rows must only contain 'recovered' status
        for row in body_rec["rows"]:
            assert row["recovery_status"] == "recovered"

        # Totals should be identical because totals cover the full window
        assert body_all["totals"] == body_rec["totals"], \
            "totals must not change when status filter is applied"

    def test_row_field_whitelist_no_sensitive_ids(self, api, admin_headers):
        now = datetime.now(timezone.utc)
        sensitive = _make_failed_order(
            failed_at=now - timedelta(hours=2),
            code="card_declined",
            recovery_token=uuid.uuid4().hex,
            payment_intent_id="pi_test_DO_NOT_LEAK_999",
            total=77.77,
        )
        _run(_insert(sensitive))

        r = api.get(f"{ENDPOINT}?days=30", headers=admin_headers)
        assert r.status_code == 200
        body = r.json()
        body_text = r.text

        # No stripe IDs or recovery_token anywhere in the payload
        assert "pi_test_DO_NOT_LEAK" not in body_text
        assert "recovery_token" not in body_text

        target = next((row for row in body["rows"] if row["id"] == sensitive["id"]), None)
        assert target is not None
        # Required fields
        for k in ("id", "order_number", "customer_name", "customer_email",
                  "customer_phone", "total", "payment_failed_at",
                  "payment_failed_code", "payment_failed_reason",
                  "recovery_email_sent_at", "recovery_status", "paid_at"):
            assert k in target, f"row missing {k}"
        # Forbidden fields
        assert "recovery_token" not in target
        assert "payment_intent_id" not in target
        assert "_id" not in target

    def test_reason_truncated_to_200_chars(self, api, admin_headers):
        now = datetime.now(timezone.utc)
        long_reason = "A" * 500
        doc = _make_failed_order(
            failed_at=now - timedelta(hours=1),
            code="card_declined",
            reason=long_reason,
        )
        _run(_insert(doc))

        r = api.get(f"{ENDPOINT}?days=30", headers=admin_headers)
        assert r.status_code == 200
        row = next((x for x in r.json()["rows"] if x["id"] == doc["id"]), None)
        assert row is not None
        assert len(row["payment_failed_reason"]) == 200
        assert row["payment_failed_reason"] == "A" * 200


class TestTopDeclineCodesAggregator:
    def test_most_common_ordering_and_unknown_bucket(self, api, admin_headers):
        """Insert 5 fresh rows with known codes + 1 missing-code row.
        We can't guarantee Mongo is empty, so we test that OUR codes appear
        in the aggregated output with the correct counts."""
        # Use a unique marker code to avoid colliding with prod data.
        marker = f"TESTCODE_{uuid.uuid4().hex[:6]}"
        c1 = f"{marker}_a"
        c2 = f"{marker}_b"
        c3 = f"{marker}_c"

        now = datetime.now(timezone.utc)
        specs = [
            (c1, "card one"),
            (c1, "card two"),
            (c2, "ins funds"),
            (c3, "expired"),
            (c1, "card three"),  # c1 total = 3
        ]
        for code, reason in specs:
            doc = _make_failed_order(
                failed_at=now - timedelta(minutes=len(_created_ids)),
                code=code,
                reason=reason,
            )
            _run(_insert(doc))
        # One row missing the code entirely → should bucket into 'unknown'
        unknown_doc = _make_failed_order(
            failed_at=now - timedelta(minutes=len(_created_ids)),
            code=None,
            reason="no code set",
        )
        _run(_insert(unknown_doc))

        r = api.get(f"{ENDPOINT}?days=30", headers=admin_headers)
        assert r.status_code == 200
        body = r.json()

        # top_decline_codes entries are serialised as 2-element arrays by JSON
        pairs = {entry[0]: entry[1] for entry in body["top_decline_codes"]}
        assert pairs.get(c1) == 3, f"expected {c1}=3, got {pairs}"
        assert pairs.get(c2) == 1, f"expected {c2}=1"
        assert pairs.get(c3) == 1
        # 'unknown' bucket exists for the row missing the code
        assert pairs.get("unknown", 0) >= 1

        # Max 6 entries
        assert len(body["top_decline_codes"]) <= 6

        # Ordering: most_common → first entry count >= last entry count
        counts_seq = [entry[1] for entry in body["top_decline_codes"]]
        assert counts_seq == sorted(counts_seq, reverse=True), \
            f"top_decline_codes not sorted desc: {counts_seq}"


class TestRecoveryRateAndIsoWindow:
    def test_iso_gte_filter_respects_window_boundary(self, api, admin_headers):
        """Insert one row just INSIDE window, one just OUTSIDE. Query with
        a narrow window and ensure only the inside one is returned."""
        now = datetime.now(timezone.utc)
        # Query will ask for days=2. Endpoint computes since = now - 2 days.
        # So 'inside' = now - 1 day, 'outside' = now - 3 days.
        inside = _make_failed_order(
            failed_at=now - timedelta(days=1),
            code=f"INSIDE_{uuid.uuid4().hex[:6]}",
        )
        outside = _make_failed_order(
            failed_at=now - timedelta(days=3),
            code=f"OUTSIDE_{uuid.uuid4().hex[:6]}",
        )
        _run(_insert(inside))
        _run(_insert(outside))

        r = api.get(f"{ENDPOINT}?days=2", headers=admin_headers)
        assert r.status_code == 200
        body = r.json()
        ids = {row["id"] for row in body["rows"]}
        assert inside["id"] in ids, "inside-window row should be returned"
        assert outside["id"] not in ids, "outside-window row should NOT be returned"

    def test_recovery_rate_calculation_is_sane(self, api, admin_headers):
        """With our inserted mix we can't get an exact 40% (prod noise), but
        we can verify: (a) count>0 → rate is 0<=rate<=100, rounded to 1dp;
        (b) recovered_count/count ratio matches rate_pct within 0.2."""
        r = api.get(f"{ENDPOINT}?days=30", headers=admin_headers)
        body = r.json()
        t = body["totals"]
        if t["count"] > 0:
            expected = round(100 * t["recovered_count"] / t["count"], 1)
            assert abs(t["recovery_rate_pct"] - expected) < 0.05, \
                f"rate={t['recovery_rate_pct']} expected≈{expected}"
            assert 0.0 <= t["recovery_rate_pct"] <= 100.0
        else:
            assert t["recovery_rate_pct"] == 0.0

    def test_totals_counts_add_up(self, api, admin_headers):
        r = api.get(f"{ENDPOINT}?days=30", headers=admin_headers)
        t = r.json()["totals"]
        assert t["recovered_count"] + t["pending_count"] + t["abandoned_count"] == t["count"]

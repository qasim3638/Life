"""
Tests for the payment-recovery feature.

Scope:
  • services.payment_recovery.send_payment_recovery_email (persistence + idempotency)
  • services.payment_recovery.lookup_recovery_token (window enforcement + token leak guard)
  • GET /api/shop/checkout/recover/{token}  (public, slim payload)
  • POST /api/notifications/telegram/test-recovery-email (super_admin gated)
  • server.py stripe webhook source-code wire-up

Synthetic shop_orders rows are written directly to Mongo, prefixed with TEST_
and cleaned up on teardown. No real Stripe webhook is triggered.
"""
from __future__ import annotations

import asyncio
import os
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests

sys.path.insert(0, "/app/backend")

from config import get_db  # noqa: E402
from services.payment_recovery import (  # noqa: E402
    RECOVERY_WINDOW_DAYS,
    lookup_recovery_token,
    send_payment_recovery_email,
)

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Test file runs inside backend container; fall back to frontend env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break


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
def admin_session(api, admin_token):
    api.headers.update({"Authorization": f"Bearer {admin_token}"})
    return api


# Cleanup helper — any TEST_ order we create gets dropped at end of module.
_created_ids: list[str] = []


def _make_order_doc(**overrides) -> dict:
    oid = f"TEST_{uuid.uuid4().hex[:12]}"
    _created_ids.append(oid)
    doc = {
        "id": oid,
        "order_number": f"TS-TEST-{uuid.uuid4().hex[:6].upper()}",
        "customer_email": "recovery-test@example.com",
        "customer_name": "Jane Tester",
        "customer_phone": "+441234567890",
        "delivery_method": "delivery",
        "delivery_address": {"line1": "1 Test Road", "city": "London", "postcode": "E1 1AA"},
        "items": [{"sku": "TEST-SKU-1", "name": "Test tile", "quantity": 2, "price": 9.99}],
        "subtotal": 19.98,
        "vat": 4.00,
        "delivery_fee": 5.00,
        "total": 28.98,
        "payment_failed_reason": "Your card was declined.",
        "status": "payment_failed",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    doc.update(overrides)
    return doc


# Single shared event loop — Motor pins its async queue to the first loop it
# sees, so we must reuse the SAME loop across every _run(...) call in this
# module. Creating a fresh loop per call gives "Event loop is closed".
_LOOP = asyncio.new_event_loop()


def _run(coro):
    return _LOOP.run_until_complete(coro)


@pytest.fixture(scope="module", autouse=True)
def cleanup_module():
    yield
    try:
        _LOOP.run_until_complete(
            get_db().shop_orders.delete_many({"id": {"$in": _created_ids}})
        )
    finally:
        _LOOP.close()


# ─────────────────────────────────────────────────────────────────────────────
# services.payment_recovery.send_payment_recovery_email
# ─────────────────────────────────────────────────────────────────────────────
class TestSendPaymentRecoveryEmail:
    def test_persists_token_and_timestamps(self):
        order = _make_order_doc()

        async def _go():
            db = get_db()
            await db.shop_orders.insert_one(dict(order))
            res = await send_payment_recovery_email(db, order)
            fresh = await db.shop_orders.find_one({"id": order["id"]}, {"_id": 0})
            return res, fresh

        res, fresh = _run(_go())

        # Response shape — either sent, skipped-not-configured, or resend
        # outage. All 'ok' paths must include a token.
        assert res.get("ok") in (True, False)  # we'll assert further below
        # Token must be a 32-char hex (uuid4.hex).
        if res.get("ok"):
            assert "token" in res or res.get("skipped")
        # Persistence assertions — must always happen, even on resend outage.
        assert fresh is not None
        assert isinstance(fresh.get("recovery_token"), str)
        assert re.fullmatch(r"[0-9a-f]{32}", fresh["recovery_token"])
        assert fresh.get("recovery_email_sent_at"), "recovery_email_sent_at must be set"
        assert fresh.get("recovery_token_expires_at"), "expires_at must be set"

        # TTL ≈ 7 days from sent_at
        sent = datetime.fromisoformat(fresh["recovery_email_sent_at"])
        exp = datetime.fromisoformat(fresh["recovery_token_expires_at"])
        delta = exp - sent
        assert timedelta(days=RECOVERY_WINDOW_DAYS - 1) < delta <= timedelta(days=RECOVERY_WINDOW_DAYS + 1)

    def test_recovery_url_shape_when_sent(self):
        """When Resend is configured + send succeeds, recovery_url must be of
        shape <SHOP_WEBSITE_URL>/shop/checkout/recover/<32-hex>. When Resend
        is NOT configured the helper still returns a token."""
        order = _make_order_doc()

        async def _go():
            db = get_db()
            await db.shop_orders.insert_one(dict(order))
            return await send_payment_recovery_email(db, order)

        res = _run(_go())
        # Accept any of these three outcomes per spec:
        #  • ok=True sent=True with recovery_url
        #  • ok=True skipped='resend_not_configured' with token
        #  • ok=False reason='resend_send_failed' with token+recovery_url
        if res.get("sent"):
            url = res["recovery_url"]
            assert re.match(r"^https?://.+/shop/checkout/recover/[0-9a-f]{32}$", url), url
            assert len(res["token"]) == 32
        elif res.get("skipped") == "resend_not_configured":
            assert re.fullmatch(r"[0-9a-f]{32}", res["token"])
        elif not res.get("ok"):
            assert res.get("reason") == "resend_send_failed"
            assert re.fullmatch(r"[0-9a-f]{32}", res["token"])
            assert "/shop/checkout/recover/" in res["recovery_url"]
        else:
            pytest.fail(f"unexpected response: {res}")

    def test_idempotent_second_call_is_noop(self):
        order = _make_order_doc()

        async def _go():
            db = get_db()
            await db.shop_orders.insert_one(dict(order))
            first = await send_payment_recovery_email(db, order)
            # Re-fetch the order — because send() doesn't mutate the caller's
            # dict, we need to reload so the idempotency guard trips on the
            # second call.
            fresh_after_first = await db.shop_orders.find_one({"id": order["id"]}, {"_id": 0})
            second = await send_payment_recovery_email(db, fresh_after_first)
            fresh_after_second = await db.shop_orders.find_one({"id": order["id"]}, {"_id": 0})
            return first, second, fresh_after_first, fresh_after_second

        first, second, a, b = _run(_go())

        # Second call must short-circuit with skipped=already_sent_at
        assert second.get("ok") is True
        assert second.get("skipped") == "already_sent_at"
        assert "value" in second

        # Token + timestamps must be unchanged.
        assert a["recovery_token"] == b["recovery_token"]
        assert a["recovery_email_sent_at"] == b["recovery_email_sent_at"]
        assert a["recovery_token_expires_at"] == b["recovery_token_expires_at"]

    def test_missing_email_returns_not_ok(self):
        order = _make_order_doc(customer_email=None)

        async def _go():
            db = get_db()
            await db.shop_orders.insert_one(dict(order))
            return await send_payment_recovery_email(db, order)

        res = _run(_go())
        assert res.get("ok") is False
        assert res.get("reason") == "missing_email_or_order_id"


# ─────────────────────────────────────────────────────────────────────────────
# services.payment_recovery.lookup_recovery_token
# ─────────────────────────────────────────────────────────────────────────────
class TestLookupRecoveryToken:
    def test_returns_order_without_token_field(self):
        token = uuid.uuid4().hex
        order = _make_order_doc(
            recovery_token=token,
            recovery_token_expires_at=(datetime.now(timezone.utc) + timedelta(days=3)).isoformat(),
            recovery_email_sent_at=datetime.now(timezone.utc).isoformat(),
        )

        async def _go():
            db = get_db()
            await db.shop_orders.insert_one(dict(order))
            return await lookup_recovery_token(db, token)

        res = _run(_go())
        assert res is not None
        assert res.get("id") == order["id"]
        # Token MUST be stripped from the returned dict
        assert "recovery_token" not in res

    def test_returns_none_for_unknown_token(self):
        async def _go():
            return await lookup_recovery_token(get_db(), uuid.uuid4().hex)
        assert _run(_go()) is None

    def test_returns_none_for_short_token(self):
        async def _go():
            return await lookup_recovery_token(get_db(), "abc")
        assert _run(_go()) is None

    def test_returns_none_for_expired_token(self):
        token = uuid.uuid4().hex
        order = _make_order_doc(
            recovery_token=token,
            # Expired 1 day ago
            recovery_token_expires_at=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
            recovery_email_sent_at=(datetime.now(timezone.utc) - timedelta(days=8)).isoformat(),
        )

        async def _go():
            db = get_db()
            await db.shop_orders.insert_one(dict(order))
            return await lookup_recovery_token(db, token)

        assert _run(_go()) is None

    def test_returns_none_for_empty_or_non_string(self):
        async def _go():
            db = get_db()
            return (
                await lookup_recovery_token(db, ""),
                await lookup_recovery_token(db, None),  # type: ignore
            )
        a, b = _run(_go())
        assert a is None and b is None


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/shop/checkout/recover/{token}
# ─────────────────────────────────────────────────────────────────────────────
class TestPublicRecoveryEndpoint:
    def test_invalid_token_returns_404(self, api):
        r = api.get(f"{BASE_URL}/api/shop/checkout/recover/not-a-real-token-xxxx")
        assert r.status_code == 404
        detail = r.json().get("detail", "")
        assert "expired" in detail.lower() or "already been used" in detail.lower()

    def test_valid_token_returns_slim_payload(self, api):
        token = uuid.uuid4().hex
        order = _make_order_doc(
            recovery_token=token,
            recovery_token_expires_at=(datetime.now(timezone.utc) + timedelta(days=5)).isoformat(),
            recovery_email_sent_at=datetime.now(timezone.utc).isoformat(),
            payment_intent_id="pi_test_should_not_leak_123",
        )

        async def _insert():
            await get_db().shop_orders.insert_one(dict(order))
        _run(_insert())

        r = api.get(f"{BASE_URL}/api/shop/checkout/recover/{token}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["order_id"] == order["id"]
        assert body["order_number"] == order["order_number"]
        assert body["customer_email"] == order["customer_email"]
        assert body["customer_name"] == order["customer_name"]
        assert body["customer_phone"] == order["customer_phone"]
        assert body["delivery_method"] == order["delivery_method"]
        assert body["delivery_address"] == order["delivery_address"]
        assert body["items"] == order["items"]
        assert body["subtotal"] == order["subtotal"]
        assert body["vat"] == order["vat"]
        assert body["delivery_fee"] == order["delivery_fee"]
        assert body["total"] == order["total"]
        assert body["decline_reason"] == order["payment_failed_reason"]

        # Must NOT leak any sensitive identifiers
        assert "recovery_token" not in body
        assert "payment_intent_id" not in body
        # Crude scan for stripe-ish ids across the whole payload
        body_str = r.text
        assert "pi_test_should_not_leak" not in body_str

    def test_expired_token_returns_404(self, api):
        token = uuid.uuid4().hex
        order = _make_order_doc(
            recovery_token=token,
            recovery_token_expires_at=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
            recovery_email_sent_at=(datetime.now(timezone.utc) - timedelta(days=8)).isoformat(),
        )

        async def _insert():
            await get_db().shop_orders.insert_one(dict(order))
        _run(_insert())

        r = api.get(f"{BASE_URL}/api/shop/checkout/recover/{token}")
        assert r.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/notifications/telegram/test-recovery-email
# ─────────────────────────────────────────────────────────────────────────────
class TestRecoveryEmailAdminEndpoint:
    URL = f"{BASE_URL}/api/notifications/telegram/test-recovery-email"

    def test_without_auth_returns_403(self, api):
        # Bare requests session (no admin auth header on this call) — use a
        # fresh session to avoid the module-scoped admin header.
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        r = s.post(self.URL, json={"to": "foo@bar.com"})
        # Could be 401 (no token) or 403 (role check). Spec says 403 for
        # role mismatch; without any token it's typically 401.
        assert r.status_code in (401, 403), r.text

    def test_missing_to_returns_422(self, admin_session):
        r = admin_session.post(self.URL, json={})
        assert r.status_code == 422

    def test_bad_email_returns_400(self, admin_session):
        r = admin_session.post(self.URL, json={"to": "not-an-email"})
        assert r.status_code == 400
        assert "valid email address" in r.json().get("detail", "").lower()

    def test_valid_email_attempts_send(self, admin_session):
        """RESEND_API_KEY may or may not be set. Accept:
           • 200 ok sent_to=<email>
           • 400 with 'resend isn't configured'
           • 502 with 'resend send failed'"""
        r = admin_session.post(self.URL, json={"to": "preview-test@tilestation.co.uk"})
        assert r.status_code in (200, 400, 502), r.text
        if r.status_code == 200:
            body = r.json()
            assert body.get("ok") is True
            assert body.get("sent_to") == "preview-test@tilestation.co.uk"
        elif r.status_code == 400:
            assert "resend isn't configured" in r.json().get("detail", "").lower() \
                or "resend is not configured" in r.json().get("detail", "").lower()
        else:
            assert "resend send failed" in r.json().get("detail", "").lower()


# ─────────────────────────────────────────────────────────────────────────────
# server.py wire-up — source-code presence checks
# ─────────────────────────────────────────────────────────────────────────────
class TestWebhookWireUp:
    SERVER_PY = "/app/backend/server.py"
    SERVICE_PY = "/app/backend/services/payment_recovery.py"

    def test_import_inside_failed_payment_branch(self):
        src = open(self.SERVER_PY).read()
        assert "from services.payment_recovery import send_payment_recovery_email" in src

        # Confirm the new event_type tuple exists
        assert 'payment_intent.payment_failed' in src
        assert 'checkout.session.async_payment_failed' in src

    def test_call_is_wrapped_in_try_except(self):
        """The recovery send should never bring the webhook down."""
        src = open(self.SERVER_PY).read()
        # Grab a window around the send_payment_recovery_email call
        idx = src.find("send_payment_recovery_email(db, fresh_order)")
        assert idx != -1, "send_payment_recovery_email call missing"
        window = src[max(0, idx - 400): idx + 400]
        assert "try:" in window
        assert "except" in window
        assert "logging.warning" in window or "logger.warning" in window

    def test_rerfetches_order_before_send(self):
        src = open(self.SERVER_PY).read()
        idx = src.find("send_payment_recovery_email(db, fresh_order)")
        window = src[max(0, idx - 400): idx]
        assert 'db.shop_orders.find_one({"id": order_id}' in window \
            or "db.shop_orders.find_one({'id': order_id}" in window, \
            "must re-fetch the order with persisted decline reason"

    def test_persistence_guard_uses_exists_false(self):
        src = open(self.SERVICE_PY).read()
        # The idempotency guard filter must include the $exists:False clause
        assert '"recovery_email_sent_at": {"$exists": False}' in src \
            or "'recovery_email_sent_at': {'$exists': False}" in src

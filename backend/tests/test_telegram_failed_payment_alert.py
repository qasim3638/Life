"""
Backend tests for the new '🚨 Payment failed' Telegram alert pipeline.

Covers:
  - POST /api/notifications/telegram/test-failed-payment — auth gating,
    validation error paths (disabled / event-toggle off / missing token /
    missing chat_ids), happy path returns {ok,result,preview_text} shape
    with '🚨' + 'Payment failed' + 'TEST' in preview_text.
  - Dedupe isolation: test-failed-payment uses 'failed-payment-test:' prefix
    (verified via source inspection) so test pings don't suppress real
    'failed-payment:<order_id|pi_id>' alerts.
  - Source-code presence of the failed-payment branch in server.py
    stripe_webhook (both 'payment_intent.payment_failed' AND
    'checkout.session.async_payment_failed' event types, idempotent
    payment_failed_at stamp, fire_and_forget wire-up, try/except wrap).
  - Default failed_payment toggle is True both in TelegramEventToggles and
    services.telegram_notify._default_config.
  - Regression: existing /telegram/test-new-order still 400s on all 4
    validation gates (covered by iteration_146 but spot-checked here).

Notes:
  - Autouse module-scope fixture snapshots the live telegram config and
    restores it on teardown so the preview env is not disturbed.
  - No real Stripe webhooks are simulated — valid signature construction
    is brittle in pytest. Source-code grep is sufficient per review request.
"""
import os
import re
import time
from pathlib import Path

import pytest
import requests


# ─────────────────────────── Setup ───────────────────────────
def _load_backend_url():
    env_path = Path("/app/frontend/.env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    return os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


BASE_URL = _load_backend_url()
assert BASE_URL, "REACT_APP_BACKEND_URL not set"

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"

CFG_URL = f"{BASE_URL}/api/notifications/telegram/config"
TEST_FP_URL = f"{BASE_URL}/api/notifications/telegram/test-failed-payment"
TEST_NEW_ORDER_URL = f"{BASE_URL}/api/notifications/telegram/test-new-order"

SERVER_PY = Path("/app/backend/server.py")
NOTIF_PY = Path("/app/backend/routes/notifications.py")
TG_SVC_PY = Path("/app/backend/services/telegram_notify.py")


# ─────────────────────────── Fixtures ───────────────────────────
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    body = r.json()
    token = body.get("access_token") or body.get("token")
    assert token, f"No token in login response: {body}"
    return token


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module", autouse=True)
def restore_config_after_module(auth_headers):
    """Snapshot existing telegram config and restore at teardown."""
    snap = requests.get(CFG_URL, headers=auth_headers, timeout=15)
    assert snap.status_code == 200, f"Could not read initial config: {snap.text}"
    original = snap.json()

    def to_payload(cfg: dict) -> dict:
        return {
            "enabled": bool(cfg.get("enabled", False)),
            "bot_token": cfg.get("bot_token", "") or "",
            "chat_ids": cfg.get("chat_ids", []) or [],
            "events": cfg.get("events") or {},
            "abandoned_basket_threshold_gbp": int(
                cfg.get("abandoned_basket_threshold_gbp", 100)
            ),
        }

    yield original

    # Restore original config
    payload = to_payload(original)
    r = requests.put(CFG_URL, headers=auth_headers, json=payload, timeout=15)
    assert r.status_code == 200, f"Failed to restore config: {r.status_code} {r.text}"


DEFAULT_EVENTS = {
    "visitor_landed": False,
    "new_order": True,
    "new_inquiry": True,
    "abandoned_basket": True,
    "failed_payment": True,
    "customer_error": True,
    "basket_add": False,
    "new_customer": True,
}


def _save_config(auth_headers, **overrides):
    """Helper: read current, merge overrides, PUT."""
    base = requests.get(CFG_URL, headers=auth_headers, timeout=15).json()
    payload = {
        "enabled": overrides.get("enabled", base.get("enabled", False)),
        "bot_token": overrides.get("bot_token", base.get("bot_token", "") or ""),
        "chat_ids": overrides.get("chat_ids", base.get("chat_ids", []) or []),
        "events": overrides.get("events", base.get("events") or DEFAULT_EVENTS),
        "abandoned_basket_threshold_gbp": int(
            overrides.get(
                "abandoned_basket_threshold_gbp",
                base.get("abandoned_basket_threshold_gbp", 100),
            )
        ),
    }
    r = requests.put(CFG_URL, headers=auth_headers, json=payload, timeout=15)
    assert r.status_code == 200, f"Save config failed: {r.status_code} {r.text}"
    return payload


# ─────────────── Auth gating ───────────────
class TestAuthGating:
    def test_no_token_returns_401_or_403(self):
        r = requests.post(TEST_FP_URL, timeout=10)
        assert r.status_code in (401, 403), (
            f"Expected 401/403 without token, got {r.status_code}: {r.text}"
        )

    def test_invalid_token_returns_401_or_403(self):
        r = requests.post(
            TEST_FP_URL,
            headers={"Authorization": "Bearer not-a-real-token"},
            timeout=10,
        )
        assert r.status_code in (401, 403), (
            f"Expected 401/403 with bad token, got {r.status_code}"
        )


# ─────────────── Validation error paths ───────────────
class TestValidationGates:
    def test_disabled_returns_400(self, auth_headers):
        _save_config(
            auth_headers,
            enabled=False,
            bot_token="1234567890:AA-test-fake-fp",
            chat_ids=["12345"],
            events=DEFAULT_EVENTS,
        )
        r = requests.post(TEST_FP_URL, headers=auth_headers, timeout=10)
        assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
        detail = r.json().get("detail", "").lower()
        assert "disabled in config" in detail, r.text

    def test_event_toggle_off_returns_400(self, auth_headers):
        events = {**DEFAULT_EVENTS, "failed_payment": False}
        _save_config(
            auth_headers,
            enabled=True,
            bot_token="1234567890:AA-test-fake-fp",
            chat_ids=["12345"],
            events=events,
        )
        r = requests.post(TEST_FP_URL, headers=auth_headers, timeout=10)
        assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
        detail = r.json().get("detail", "").lower()
        assert "failed_payment" in detail and "toggle" in detail, r.text
        assert "turn it on" in detail, r.text

    def test_missing_bot_token_returns_400(self, auth_headers):
        _save_config(
            auth_headers,
            enabled=True,
            bot_token="",
            chat_ids=["12345"],
            events=DEFAULT_EVENTS,
        )
        r = requests.post(TEST_FP_URL, headers=auth_headers, timeout=10)
        assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
        detail = r.json().get("detail", "").lower()
        assert "bot token" in detail or "chat id" in detail, r.text

    def test_missing_chat_ids_returns_400(self, auth_headers):
        _save_config(
            auth_headers,
            enabled=True,
            bot_token="1234567890:AA-test-fake-fp",
            chat_ids=[],
            events=DEFAULT_EVENTS,
        )
        r = requests.post(TEST_FP_URL, headers=auth_headers, timeout=10)
        assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
        detail = r.json().get("detail", "").lower()
        assert "bot token" in detail or "chat id" in detail, r.text


# ─────────────── Happy path ───────────────
class TestHappyPath:
    def test_all_gates_pass_returns_ok_and_preview(self, auth_headers):
        # Use a unique-enough token suffix to avoid dedupe collision with
        # earlier runs inside the same backend process.
        _save_config(
            auth_headers,
            enabled=True,
            bot_token=f"1234567890:AA-fake-fp-{int(time.time())}",
            chat_ids=["99999"],
            events=DEFAULT_EVENTS,
        )
        r = requests.post(TEST_FP_URL, headers=auth_headers, timeout=15)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        body = r.json()
        assert body.get("ok") is True, body
        assert "result" in body and isinstance(body["result"], dict), body
        preview = body.get("preview_text", "")
        assert "🚨" in preview, f"Missing 🚨 in preview: {preview}"
        assert "Payment failed" in preview, f"Missing 'Payment failed' in preview: {preview}"
        assert "TEST" in preview, f"Missing 'TEST' in preview: {preview}"


# ─────────────── Source-code assertions ───────────────
class TestSourceCodeWireUp:
    """Per review request: source-code grep is acceptable for the webhook
    tests since simulating a valid Stripe webhook signature is brittle."""

    @pytest.fixture(scope="class")
    def server_src(self):
        return SERVER_PY.read_text()

    @pytest.fixture(scope="class")
    def notif_src(self):
        return NOTIF_PY.read_text()

    @pytest.fixture(scope="class")
    def tg_svc_src(self):
        return TG_SVC_PY.read_text()

    def test_webhook_handles_both_event_types(self, server_src):
        assert '"payment_intent.payment_failed"' in server_src, (
            "payment_intent.payment_failed not found in server.py"
        )
        assert '"checkout.session.async_payment_failed"' in server_src, (
            "checkout.session.async_payment_failed not found in server.py"
        )
        # Must be in the same elif tuple
        assert re.search(
            r'elif\s+event_type\s+in\s*\(\s*"payment_intent\.payment_failed"\s*,\s*'
            r'"checkout\.session\.async_payment_failed"\s*\)',
            server_src,
        ), "Both event types are not grouped in the same elif tuple"

    def test_webhook_fires_failed_payment_with_dedupe(self, server_src):
        assert 'dedupe_key=f"failed-payment:{dedupe}"' in server_src, (
            "fire_and_forget dedupe_key for failed-payment missing or wrong shape"
        )
        assert '"failed_payment"' in server_src, "failed_payment event name missing"
        # Try/except wrap
        assert "Telegram failed_payment alert failed" in server_src, (
            "try/except fallback logging.warning missing"
        )

    def test_webhook_persists_failure_idempotently(self, server_src):
        # Update filter must require payment_failed_at to not exist yet,
        # so Stripe retries don't overwrite the original timestamp.
        assert re.search(
            r'shop_orders\.update_one\(\s*\{\s*"id"\s*:\s*order_id\s*,\s*'
            r'"payment_failed_at"\s*:\s*\{\s*"\$exists"\s*:\s*False\s*\}',
            server_src,
        ), "Idempotent {'payment_failed_at': {'$exists': False}} filter missing"
        assert '"payment_failed_reason"' in server_src
        assert '"payment_failed_code"' in server_src
        assert '"payment_status": "failed"' in server_src

    def test_webhook_extracts_order_id_with_fallback(self, server_src):
        # metadata.order_id primary
        assert 'obj.get("metadata") or {}).get("order_id")' in server_src
        # payment_transactions fallback for checkout.session
        assert re.search(
            r'payment_transactions\.find_one\(\s*\{\s*"session_id"\s*:\s*sess_id\s*\}',
            server_src,
        ), "Fallback to payment_transactions.find_one by session_id missing"

    def test_webhook_extracts_decline_info(self, server_src):
        # decline code + message
        assert 'err.get("decline_code")' in server_src
        assert re.search(r'err\.get\("message"\)[^\n]*\[:\s*160\s*\]', server_src), (
            "decline message not truncated to 160 chars as spec says"
        )
        # Amount in minor units → divided by 100 for £
        assert re.search(r'int\(amount_minor\)\s*/\s*100\.0', server_src), (
            "Amount divide-by-100 conversion missing"
        )

    def test_test_endpoint_uses_isolated_dedupe_prefix(self, notif_src):
        # Test endpoint must use 'failed-payment-test:' prefix (NOT 'failed-payment:')
        # so test pings cannot suppress real alerts.
        assert 'dedupe_key=f"failed-payment-test:{fake_order}"' in notif_src, (
            "test-failed-payment endpoint uses wrong/no dedupe prefix"
        )
        # And real webhook uses the 'failed-payment:' prefix (different)
        assert "failed-payment-test:" != "failed-payment:", "sanity"

    def test_test_endpoint_exists_and_gated(self, notif_src):
        assert '@router.post("/telegram/test-failed-payment")' in notif_src
        assert '"Super admin only"' in notif_src
        # All 4 validation gates present
        assert "Telegram notifications are disabled in config." in notif_src
        assert "failed_payment" in notif_src and "toggle is OFF" in notif_src
        assert "Bot token and at least one chat ID must be saved first." in notif_src

    def test_telegram_toggles_default_failed_payment_true(self, notif_src):
        # routes/notifications.py TelegramEventToggles
        assert re.search(r"failed_payment:\s*bool\s*=\s*True", notif_src), (
            "TelegramEventToggles.failed_payment default is not True"
        )

    def test_telegram_service_default_failed_payment_true(self, tg_svc_src):
        # services/telegram_notify._default_config events dict
        assert re.search(r'"failed_payment"\s*:\s*True', tg_svc_src), (
            "_default_config events.failed_payment default is not True"
        )

    def test_fire_and_forget_signature_matches_usage(self, tg_svc_src):
        # fire_and_forget(event_type, text, *, dedupe_key=None)
        assert re.search(
            r"def\s+fire_and_forget\(\s*event_type\s*:\s*str\s*,\s*text\s*:\s*str\s*,\s*\*\s*,\s*dedupe_key",
            tg_svc_src,
        ), "fire_and_forget signature in telegram_notify.py has drifted"


# ─────────────── Regression: /test-new-order unaffected ───────────────
class TestRegressionNewOrder:
    def test_new_order_still_400s_when_disabled(self, auth_headers):
        _save_config(
            auth_headers,
            enabled=False,
            bot_token="1234567890:AA-test-fake-fp",
            chat_ids=["12345"],
            events=DEFAULT_EVENTS,
        )
        r = requests.post(TEST_NEW_ORDER_URL, headers=auth_headers, timeout=10)
        assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
        assert "disabled in config" in r.json().get("detail", "").lower()

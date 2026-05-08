"""
Backend tests for the new '🛒 New order' Telegram alert pipeline.

Covers:
  - POST /api/notifications/telegram/test-new-order — auth gating, validation
    error paths (disabled / event-toggle off / missing token / missing chat_ids),
    happy path returns shape {ok,result,preview_text}, and dedupe behaviour.
  - Regression: /api/notifications/telegram/test still works.
  - Default new_order toggle is True both in TelegramEventToggles and in
    services.telegram_notify._default_config.
  - Wire-up exists in server.py (both Stripe webhook branches) and in
    routes/shop.py (polling-based payment-status path).

Notes:
  - The actual Telegram HTTP call is expected to fail (401/404 from Telegram's
    side) when we use a fake bot_token in the test config — that is FINE.
    The point is to verify our code reaches send_telegram, which means
    notify_event passed all gates.
  - Test backs up + restores the live telegram config so production-like
    settings in preview are not disturbed.
"""
import os
import re
import time
import pytest
import requests
from pathlib import Path

# Load REACT_APP_BACKEND_URL from frontend/.env (preview public URL)
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
TEST_NEW_ORDER_URL = f"{BASE_URL}/api/notifications/telegram/test-new-order"
TEST_GENERIC_URL = f"{BASE_URL}/api/notifications/telegram/test"


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
    """Snapshot existing telegram config and restore at the end so we don't
    leave the preview env in a weird state."""
    snap = requests.get(CFG_URL, headers=auth_headers, timeout=15)
    assert snap.status_code == 200, f"Could not read initial config: {snap.text}"
    original = snap.json()

    # Strip server-only fields before re-PUT
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

    # Restore
    payload = to_payload(original)
    r = requests.put(CFG_URL, headers=auth_headers, json=payload, timeout=15)
    assert r.status_code == 200, f"Failed to restore config: {r.status_code} {r.text}"


def _save_config(auth_headers, **overrides):
    """Helper: read current, merge overrides, PUT."""
    base = requests.get(CFG_URL, headers=auth_headers, timeout=15).json()
    payload = {
        "enabled": overrides.get("enabled", base.get("enabled", False)),
        "bot_token": overrides.get("bot_token", base.get("bot_token", "") or ""),
        "chat_ids": overrides.get("chat_ids", base.get("chat_ids", []) or []),
        "events": overrides.get("events", base.get("events") or {}),
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


# ─────────────── Auth gating on /test-new-order ───────────────
class TestAuthGating:
    def test_no_token_returns_401_or_403(self):
        r = requests.post(TEST_NEW_ORDER_URL, timeout=10)
        assert r.status_code in (401, 403), (
            f"Expected 401/403 without token, got {r.status_code}: {r.text}"
        )

    def test_invalid_token_returns_401(self):
        r = requests.post(
            TEST_NEW_ORDER_URL,
            headers={"Authorization": "Bearer not-a-real-token"},
            timeout=10,
        )
        assert r.status_code in (401, 403), (
            f"Expected 401/403 with bad token, got {r.status_code}"
        )


# ─────────────── Validation error paths ───────────────
class TestValidationGates:
    def test_disabled_returns_400(self, auth_headers):
        # Force-disable telegram first
        _save_config(
            auth_headers,
            enabled=False,
            bot_token="1234567890:AA-test-fake",
            chat_ids=["12345"],
            events={
                "visitor_landed": False,
                "new_order": True,
                "new_inquiry": True,
                "abandoned_basket": True,
                "failed_payment": True,
                "customer_error": True,
                "basket_add": False,
                "new_customer": True,
            },
        )
        r = requests.post(TEST_NEW_ORDER_URL, headers=auth_headers, timeout=10)
        assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
        assert "disabled in config" in r.json().get("detail", "").lower(), r.text

    def test_event_toggle_off_returns_400(self, auth_headers):
        _save_config(
            auth_headers,
            enabled=True,
            bot_token="1234567890:AA-test-fake",
            chat_ids=["12345"],
            events={
                "visitor_landed": False,
                "new_order": False,  # toggle OFF
                "new_inquiry": True,
                "abandoned_basket": True,
                "failed_payment": True,
                "customer_error": True,
                "basket_add": False,
                "new_customer": True,
            },
        )
        r = requests.post(TEST_NEW_ORDER_URL, headers=auth_headers, timeout=10)
        assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
        detail = r.json().get("detail", "").lower()
        assert "new_order" in detail and "toggle" in detail, r.text

    def test_missing_bot_token_returns_400(self, auth_headers):
        _save_config(
            auth_headers,
            enabled=True,
            bot_token="",  # missing
            chat_ids=["12345"],
            events={
                "visitor_landed": False, "new_order": True, "new_inquiry": True,
                "abandoned_basket": True, "failed_payment": True,
                "customer_error": True, "basket_add": False, "new_customer": True,
            },
        )
        r = requests.post(TEST_NEW_ORDER_URL, headers=auth_headers, timeout=10)
        assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
        detail = r.json().get("detail", "").lower()
        assert "bot token" in detail or "chat id" in detail, r.text

    def test_missing_chat_ids_returns_400(self, auth_headers):
        _save_config(
            auth_headers,
            enabled=True,
            bot_token="1234567890:AA-test-fake",
            chat_ids=[],  # missing
            events={
                "visitor_landed": False, "new_order": True, "new_inquiry": True,
                "abandoned_basket": True, "failed_payment": True,
                "customer_error": True, "basket_add": False, "new_customer": True,
            },
        )
        r = requests.post(TEST_NEW_ORDER_URL, headers=auth_headers, timeout=10)
        assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
        detail = r.json().get("detail", "").lower()
        assert "chat id" in detail or "bot token" in detail, r.text


# ─────────────── Happy path + dedupe ───────────────
class TestHappyPathAndDedupe:
    def test_happy_path_and_dedupe(self, auth_headers):
        # Configure fully — fake but valid-looking creds. Telegram itself
        # will return 401/404, but our code path should reach send_telegram.
        _save_config(
            auth_headers,
            enabled=True,
            bot_token="1234567890:AA-fake-but-valid-shape",
            chat_ids=["12345"],
            events={
                "visitor_landed": False, "new_order": True, "new_inquiry": True,
                "abandoned_basket": True, "failed_payment": True,
                "customer_error": True, "basket_add": False, "new_customer": True,
            },
        )

        r1 = requests.post(TEST_NEW_ORDER_URL, headers=auth_headers, timeout=15)
        assert r1.status_code == 200, f"Expected 200, got {r1.status_code}: {r1.text}"
        body = r1.json()
        assert body.get("ok") is True
        preview = body.get("preview_text") or ""
        assert "🛒" in preview and "New order" in preview, (
            f"Missing emoji/header: {preview}"
        )
        assert "TEST" in preview, f"Missing TEST badge: {preview}"
        result = body.get("result") or {}
        # Either it actually attempted to send (result has 'sent' or 'errors')
        # or was skipped (e.g. no_targets / dedupe). Either is fine — what we
        # really care about is that NONE of the 4xx gates triggered.
        assert isinstance(result, dict), f"result not a dict: {result}"
        assert "skipped" in result or "sent" in result or "errors" in result, (
            f"Unexpected result shape: {result}"
        )

        # Immediately call again — should hit dedupe window. The dedupe key
        # used by the endpoint is "new-order-test:<fake_order>" which is
        # date-stamped (same within the same UTC day) so a second call in
        # the same second/minute MUST hit the dedupe window.
        r2 = requests.post(TEST_NEW_ORDER_URL, headers=auth_headers, timeout=15)
        assert r2.status_code == 200, f"Expected 200 on 2nd call, got {r2.status_code}: {r2.text}"
        body2 = r2.json()
        result2 = body2.get("result") or {}
        assert result2.get("skipped") == "dedupe_window", (
            f"Expected dedupe_window skip on 2nd call, got: {result2}"
        )


# ─────────────── Regression: /telegram/test still works ───────────────
class TestRegressionGenericTest:
    def test_generic_test_endpoint(self, auth_headers):
        _save_config(
            auth_headers,
            enabled=True,
            bot_token="1234567890:AA-fake-but-valid-shape",
            chat_ids=["12345"],
            events={
                "visitor_landed": False, "new_order": True, "new_inquiry": True,
                "abandoned_basket": True, "failed_payment": True,
                "customer_error": True, "basket_add": False, "new_customer": True,
            },
        )
        r = requests.post(
            TEST_GENERIC_URL, headers=auth_headers, json={}, timeout=15
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        body = r.json()
        # send_telegram returns {sent, errors}
        assert "sent" in body or "errors" in body, f"Unexpected shape: {body}"


# ─────────── Defaults & code-level wire-up presence ───────────
class TestDefaultsAndWireUp:
    def test_telegram_event_toggles_default_new_order_true(self):
        # File-level check (avoids importing the backend package which
        # requires MONGO_URL on import). The TelegramEventToggles class
        # has new_order: bool = True as default.
        path = "/app/backend/routes/notifications.py"
        text = open(path, "r", encoding="utf-8").read()
        # Match: "new_order: bool = True" (whitespace-tolerant)
        m = re.search(r"class\s+TelegramEventToggles\b[^}]*?new_order\s*:\s*bool\s*=\s*True",
                      text, flags=re.DOTALL)
        assert m, "TelegramEventToggles.new_order default is not True"

    def test_default_config_includes_new_order_true(self):
        path = "/app/backend/services/telegram_notify.py"
        text = open(path, "r", encoding="utf-8").read()
        # Match: "new_order": True inside the events dict in _default_config
        m = re.search(r'def\s+_default_config[^}]*?"new_order"\s*:\s*True',
                      text, flags=re.DOTALL)
        assert m, "_default_config events dict does not have new_order=True"

    def test_wire_up_in_server_py_checkout_session(self):
        path = "/app/backend/server.py"
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        # Find the checkout.session.completed branch's fire_and_forget
        idx = text.find("Payment confirmed for session")
        assert idx > 0, "checkout.session.completed branch marker missing"
        # Look for the alert wire-up in the lines BEFORE the log line (it
        # is logged AFTER the fire_and_forget call in this code path).
        window = text[max(0, idx - 4000): idx + 200]
        assert "fire_and_forget" in window, "fire_and_forget missing near checkout.session"
        assert 'dedupe_key=f"new-order:{order_id}"' in window, (
            "dedupe_key missing/wrong near checkout.session"
        )
        assert "🛒" in window and "New order" in window, "alert text shape missing"

    def test_wire_up_in_server_py_wallet_express(self):
        path = "/app/backend/server.py"
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        idx = text.find("Wallet Express PaymentIntent paid")
        assert idx > 0, "Wallet Express branch marker missing"
        window = text[idx: idx + 4000]
        assert "fire_and_forget" in window, "fire_and_forget missing near wallet express"
        assert 'dedupe_key=f"new-order:{order_id}"' in window
        assert "🛒" in window and "New order" in window

    def test_wire_up_in_shop_py_poll_path(self):
        path = "/app/backend/routes/shop.py"
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        idx = text.find("Order confirmation email sent")
        assert idx > 0, "Order confirmation email log marker missing"
        window = text[idx: idx + 3000]
        assert "fire_and_forget" in window, "fire_and_forget missing in poll path"
        assert 'dedupe_key=f"new-order:{order_id}"' in window
        assert "🛒" in window and "New order" in window

"""
Regression tests for Klarna-via-Stripe checkout integration.

Covers:
  1. `get_enabled_checkout_payment_methods(total)` correctly returns
     ['card']      when Klarna toggle is OFF
     ['card', 'klarna']   when Klarna toggle is ON AND total >= £30
     ['card']      when Klarna toggle is ON but total < £30
     ['card']      when settings doc is missing
     ['card']      when settings read fails (defensive)
  2. The admin checkout-settings endpoint round-trips the new `payments` block.
  3. Sample-postage checkout endpoint NEVER includes Klarna (kept card-only by
     design, since samples are ~£3 — well below Klarna UK minimum).
"""
import os

import pytest
import pytest_asyncio
import requests

from routes.shop import (
    get_enabled_checkout_payment_methods,
    KLARNA_UK_MIN_AMOUNT_GBP,
)
from config import get_db


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


# -------- Helper: admin login --------
def _login_admin():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "admin@test.com", "password": "admin123"},
    )
    assert r.status_code == 200, f"Admin login failed: {r.status_code} — {r.text[:200]}"
    token = r.json().get("token") or r.json().get("access_token")
    assert token, "No token in login response"
    return {"Authorization": f"Bearer {token}"}


# -------- Helper: set payments settings in DB --------
async def _set_payments_enabled(enabled: bool):
    db = get_db()
    await db.website_settings.update_one(
        {"key": "checkout_settings"},
        {"$set": {"key": "checkout_settings", "value.payments.klarna_enabled": enabled}},
        upsert=True,
    )


async def _clear_payments_settings():
    db = get_db()
    await db.website_settings.update_one(
        {"key": "checkout_settings"},
        {"$unset": {"value.payments": ""}},
    )


# ============ Helper function unit tests ============


class TestPaymentMethodsHelper:
    """Combined into one test to share a single event loop — Motor client is
    session-scoped and breaks when torn down between `asyncio.run()` calls."""

    @pytest.mark.asyncio
    async def test_all_helper_scenarios(self):
        # (1) Klarna disabled → card-only
        await _set_payments_enabled(enabled=False)
        methods = await get_enabled_checkout_payment_methods(order_total=150.00)
        assert methods == ["card"], f"(1) expected ['card'], got {methods}"

        # (2) Klarna enabled + above min → includes klarna
        await _set_payments_enabled(enabled=True)
        methods = await get_enabled_checkout_payment_methods(order_total=150.00)
        assert "card" in methods and "klarna" in methods, (
            f"(2) expected klarna included at £150, got {methods}"
        )

        # (3) Klarna enabled + below min → card-only
        methods = await get_enabled_checkout_payment_methods(
            order_total=KLARNA_UK_MIN_AMOUNT_GBP - 0.01
        )
        assert methods == ["card"], (
            f"(3) basket below £{KLARNA_UK_MIN_AMOUNT_GBP} must not offer Klarna; got {methods}"
        )

        # (4) Klarna enabled + exactly at min → includes klarna
        methods = await get_enabled_checkout_payment_methods(
            order_total=KLARNA_UK_MIN_AMOUNT_GBP
        )
        assert "klarna" in methods, f"(4) at min, expected klarna; got {methods}"

        # (5) Payments section absent → disabled
        await _clear_payments_settings()
        methods = await get_enabled_checkout_payment_methods(order_total=150.00)
        assert methods == ["card"], f"(5) missing settings, expected ['card']; got {methods}"


# ============ Admin API round-trip ============


class TestAdminPaymentsRoundtrip:
    def test_save_and_load_payments_block(self):
        headers = _login_admin()

        # Save via admin API
        payload = {
            "settings": {
                "payments": {
                    "klarna_enabled": True,
                    "klarna_osm_enabled": True,
                    "klarna_client_id": "test-client-id-xyz-1234",
                }
            }
        }
        r = requests.post(
            f"{BASE_URL}/api/website-admin/checkout-settings",
            headers=headers,
            json=payload,
        )
        assert r.status_code == 200, f"Save failed: {r.status_code} {r.text[:200]}"

        # Read back via admin API
        r2 = requests.get(
            f"{BASE_URL}/api/website-admin/checkout-settings", headers=headers
        )
        assert r2.status_code == 200
        data = r2.json().get("settings", {})
        assert data.get("payments", {}).get("klarna_enabled") is True
        assert data.get("payments", {}).get("klarna_osm_enabled") is True
        assert data.get("payments", {}).get("klarna_client_id") == "test-client-id-xyz-1234"

        # Read back via PUBLIC endpoint (the storefront uses this)
        r3 = requests.get(f"{BASE_URL}/api/website-admin/public/checkout-settings")
        assert r3.status_code == 200
        pub = r3.json().get("settings", {})
        assert pub.get("payments", {}).get("klarna_enabled") is True
        assert pub.get("payments", {}).get("klarna_client_id") == "test-client-id-xyz-1234"

        # Cleanup
        requests.post(
            f"{BASE_URL}/api/website-admin/checkout-settings",
            headers=headers,
            json={
                "settings": {
                    "payments": {
                        "klarna_enabled": False,
                        "klarna_osm_enabled": False,
                        "klarna_client_id": "",
                    }
                }
            },
        )


# ============ Sample postage stays card-only ============


class TestSamplePostageNeverOffersKlarna:
    def test_sample_postage_never_includes_klarna_in_code(self):
        """
        By design, sample-postage checkout (route `@router.post('/samples/checkout/{order_id}')`)
        does NOT pass payment_methods=… to CheckoutSessionRequest, which keeps it card-only.
        Samples are ~£3 — below Klarna UK £30 minimum — so Klarna would never accept them
        anyway, and we don't want that noise at checkout.
        
        This test is a static guard: it reads the shop.py source and asserts the
        sample endpoint does not call get_enabled_checkout_payment_methods.
        """
        import re
        src = open(os.path.join(os.path.dirname(__file__), "..", "routes", "shop.py")).read()
        # Find the @router.post("/samples/checkout/...") block
        m = re.search(
            r'@router\.post\("/samples/checkout/\{order_id\}"\).*?^\s*session\s*=\s*checkout\.create_checkout_session',
            src,
            re.DOTALL | re.MULTILINE,
        )
        assert m, "Could not locate sample-postage checkout endpoint in shop.py"
        block = m.group(0)
        assert "get_enabled_checkout_payment_methods" not in block, (
            "Sample postage should NOT call the Klarna-eligible payment-methods helper. "
            "Samples are ~£3, below Klarna UK minimum."
        )


# ============ Klarna Express Checkout endpoint ============


class TestKlarnaExpress:
    """Verifies the /api/shop/klarna-express/create-session endpoint."""

    _EP = "/api/shop/klarna-express/create-session"

    def _enable_klarna(self):
        headers = _login_admin()
        requests.post(
            f"{BASE_URL}/api/website-admin/checkout-settings",
            headers=headers,
            json={"settings": {"payments": {"klarna_enabled": True}}},
        )

    def _disable_klarna(self):
        headers = _login_admin()
        requests.post(
            f"{BASE_URL}/api/website-admin/checkout-settings",
            headers=headers,
            json={"settings": {"payments": {"klarna_enabled": False}}},
        )

    def test_rejects_when_klarna_admin_toggle_off(self):
        self._disable_klarna()
        r = requests.post(
            f"{BASE_URL}{self._EP}",
            json={
                "items": [{"product_id": "X", "quantity": 3, "price": 50.0, "name": "N", "sku": "", "image": ""}],
                "origin_url": "https://example.com",
            },
        )
        assert r.status_code == 400
        assert "not enabled" in r.json().get("detail", "").lower()

    def test_rejects_empty_basket(self):
        self._enable_klarna()
        try:
            r = requests.post(
                f"{BASE_URL}{self._EP}",
                json={"items": [], "origin_url": "https://example.com"},
            )
            assert r.status_code == 400
            assert "empty" in r.json().get("detail", "").lower()
        finally:
            self._disable_klarna()

    def test_rejects_when_total_below_min(self):
        """Crafts a basket + free-delivery threshold state that ends up < £30."""
        self._enable_klarna()
        # Lower free_threshold to £1 so delivery is waived → total = subtotal alone.
        # Subtotal of £5 → total £5 → well below Klarna's £30 minimum.
        headers = _login_admin()
        requests.post(
            f"{BASE_URL}/api/website-admin/checkout-settings",
            headers=headers,
            json={"settings": {"delivery": {"free_threshold": 1}}},
        )
        try:
            r = requests.post(
                f"{BASE_URL}{self._EP}",
                json={
                    "items": [{"product_id": "X", "quantity": 1, "price": 5.0, "name": "N", "sku": "", "image": ""}],
                    "origin_url": "https://example.com",
                },
            )
            assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text[:200]}"
            assert "minimum" in r.json().get("detail", "").lower()
        finally:
            # Restore delivery threshold
            requests.post(
                f"{BASE_URL}/api/website-admin/checkout-settings",
                headers=headers,
                json={"settings": {"delivery": {"free_threshold": 1000}}},
            )
            self._disable_klarna()

    def test_returns_session_url_and_creates_order(self):
        self._enable_klarna()
        try:
            r = requests.post(
                f"{BASE_URL}{self._EP}",
                json={
                    "items": [
                        {"product_id": "TILE-A", "quantity": 5, "price": 20.0, "name": "Test Tile", "sku": "TA-1", "image": ""}
                    ],
                    "origin_url": "https://example.com",
                },
            )
            assert r.status_code == 200, f"Got {r.status_code}: {r.text[:200]}"
            body = r.json()
            assert body.get("session_id", "").startswith("cs_"), f"Unexpected session_id: {body.get('session_id')}"
            assert body.get("url", "").startswith("https://"), f"No valid Stripe URL returned: {body.get('url')}"
            assert body.get("order_id"), "order_id missing from response"
            # Total = 100 (items) + 49.99 (default standard fee, since free_threshold default is high)
            assert body.get("total") == 149.99, f"Expected total 149.99, got {body.get('total')}"
        finally:
            self._disable_klarna()

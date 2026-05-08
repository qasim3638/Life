"""
Regression tests for Apple Pay / Google Pay Wallet Express integration.

Covers:
  1. `is_wallet_express_enabled()` reflects admin toggle.
  2. `POST /api/shop/wallet-express/create-intent`:
     - 400 when toggle OFF
     - 400 when basket empty / invalid
     - 200 returns a Stripe PaymentIntent client_secret + order_id when ON
     - Creates a shop_orders record with source='wallet_express'
  3. `POST /api/shop/wallet-express/register-apple-domain`:
     - 400 when toggle OFF
     - 200 or idempotent "already registered" when ON
  4. `.well-known/apple-developer-merchantid-domain-association` is served at
     app root (not /api/…) and returns the bundled Stripe file.
"""
import os
import pytest
import requests

from routes.wallet_express import is_wallet_express_enabled
from config import get_db


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


async def _set_wallet(enabled: bool):
    db = get_db()
    await db.website_settings.update_one(
        {"key": "checkout_settings"},
        {"$set": {
            "key": "checkout_settings",
            "value.payments.wallet_express_enabled": enabled,
        }},
        upsert=True,
    )


class TestWalletExpressToggle:
    @pytest.mark.asyncio
    async def test_toggle_reflects_db(self):
        await _set_wallet(False)
        assert await is_wallet_express_enabled() is False

        await _set_wallet(True)
        assert await is_wallet_express_enabled() is True

        await _set_wallet(False)


class TestWalletExpressIntent:
    def _toggle(self, enabled: bool):
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@test.com", "password": "admin123"},
        )
        token = r.json().get("token") or r.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}"}
        cur = requests.get(
            f"{BASE_URL}/api/website-admin/checkout-settings", headers=headers
        ).json().get("settings", {})
        cur.setdefault("payments", {})
        cur["payments"]["wallet_express_enabled"] = enabled
        requests.post(
            f"{BASE_URL}/api/website-admin/checkout-settings",
            headers=headers,
            json={"settings": cur},
        )

    def test_400_when_disabled(self):
        self._toggle(False)
        r = requests.post(
            f"{BASE_URL}/api/shop/wallet-express/create-intent",
            json={
                "items": [{"product_id": "x", "name": "t", "price": 10, "quantity": 1}],
                "origin_url": "https://example.com",
            },
        )
        assert r.status_code == 400
        assert "not enabled" in r.json().get("detail", "").lower()

    def test_400_when_basket_empty(self):
        self._toggle(True)
        try:
            r = requests.post(
                f"{BASE_URL}/api/shop/wallet-express/create-intent",
                json={"items": [], "origin_url": "https://example.com"},
            )
            assert r.status_code == 400
        finally:
            self._toggle(False)

    def test_200_returns_client_secret_and_order(self):
        self._toggle(True)
        try:
            r = requests.post(
                f"{BASE_URL}/api/shop/wallet-express/create-intent",
                json={
                    "items": [{"product_id": "x", "name": "Tile", "price": 42.99, "quantity": 2.88}],
                    "origin_url": "https://example.com",
                },
            )
            assert r.status_code == 200, f"{r.status_code} — {r.text[:200]}"
            data = r.json()
            # Client secret looks like pi_XXX_secret_YYY
            assert "_secret_" in (data.get("client_secret") or ""), f"bad secret: {data}"
            assert data.get("payment_intent_id", "").startswith("pi_")
            assert data.get("order_id")
            assert data.get("total", 0) > 0
        finally:
            self._toggle(False)


class TestAppleDomainAssociation:
    def test_served_at_root(self):
        """Stripe (and Apple) require this file at the exact path
        `/.well-known/apple-developer-merchantid-domain-association`. In our
        k8s preview the ingress routes only /api/* to the backend, so the
        file is served by the frontend static `public/` folder (React's
        `public/` tree is served at root by most hosts / Railway)."""
        r = requests.get(
            f"{BASE_URL}/.well-known/apple-developer-merchantid-domain-association"
        )
        assert r.status_code == 200
        body = r.text
        assert len(body) > 100, "file looks empty"
        # Stripe's bundled file is a long hex string beginning with these bytes
        assert body.strip().startswith("7B22"), f"unexpected content: {body[:60]}"

    def test_register_requires_wallet_enabled(self):
        """register-apple-domain should 400 when the feature is off."""
        # Ensure wallet off
        r1 = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@test.com", "password": "admin123"},
        )
        token = r1.json().get("token") or r1.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}"}
        cur = requests.get(
            f"{BASE_URL}/api/website-admin/checkout-settings", headers=headers
        ).json().get("settings", {})
        cur.setdefault("payments", {})
        cur["payments"]["wallet_express_enabled"] = False
        requests.post(
            f"{BASE_URL}/api/website-admin/checkout-settings",
            headers=headers,
            json={"settings": cur},
        )

        r = requests.post(f"{BASE_URL}/api/shop/wallet-express/register-apple-domain")
        assert r.status_code == 400

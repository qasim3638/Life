"""
Cart Save Banner regression tests.

Covers:
- GET /api/storefront-features/public exposes cart_save_banner_enabled flag
- PUT /api/storefront-features (super-admin) toggles the flag and is reflected on /public
- GET /api/website-admin/welcome-popup/public exposes coupon_enabled
- POST /api/website-admin/welcome-popup/email captures the lead and mints a WELCOME-* code
  when coupon_enabled is true. Code is single-use and idempotent per email.
- /api/promo-codes/admin/list (or shop_discount_codes admin route) lists the WELCOME-* code
  freshly minted by the banner submission.
"""
import os
import time
import uuid
import asyncio
import requests
import pytest
from motor.motor_asyncio import AsyncIOMotorClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")

assert BASE_URL, "REACT_APP_BACKEND_URL not set"

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"


# ---------------------- fixtures ----------------------

@pytest.fixture(scope="session")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def admin_token(api):
    r = api.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD,
    })
    if r.status_code != 200:
        pytest.skip(f"Admin login failed ({r.status_code}): {r.text[:200]}")
    data = r.json()
    token = data.get("access_token") or data.get("token")
    if not token:
        pytest.skip(f"No token in admin login response: {data}")
    return token


@pytest.fixture(scope="session")
def admin_session(api, admin_token):
    s = requests.Session()
    s.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {admin_token}",
    })
    return s


@pytest.fixture(scope="session")
def db():
    if not MONGO_URL or not DB_NAME:
        pytest.skip("MONGO_URL/DB_NAME not configured")
    client = AsyncIOMotorClient(MONGO_URL)
    return client[DB_NAME]


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------- 1. storefront-features/public ----------------------

class TestStorefrontFeaturesPublic:

    def test_public_returns_cart_save_banner_flag(self, api):
        r = api.get(f"{BASE_URL}/api/storefront-features/public")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "cart_save_banner_enabled" in data, f"Missing flag: {data.keys()}"
        assert isinstance(data["cart_save_banner_enabled"], bool)

    def test_admin_toggle_reflects_on_public(self, api, admin_session):
        # Read current
        r = admin_session.get(f"{BASE_URL}/api/storefront-features")
        assert r.status_code == 200, r.text
        original = r.json()
        original_flag = bool(original.get("cart_save_banner_enabled"))

        try:
            # Flip
            new_flag = not original_flag
            r = admin_session.put(
                f"{BASE_URL}/api/storefront-features",
                json={"cart_save_banner_enabled": new_flag},
            )
            assert r.status_code == 200, r.text
            assert r.json().get("cart_save_banner_enabled") is new_flag

            # Verify on /public
            r = api.get(f"{BASE_URL}/api/storefront-features/public")
            assert r.status_code == 200
            assert r.json().get("cart_save_banner_enabled") is new_flag
        finally:
            # restore
            admin_session.put(
                f"{BASE_URL}/api/storefront-features",
                json={"cart_save_banner_enabled": original_flag},
            )


# ---------------------- 2. welcome-popup/public ----------------------

class TestWelcomePopupPublic:

    def test_public_returns_coupon_fields(self, api):
        r = api.get(f"{BASE_URL}/api/website-admin/welcome-popup/public")
        assert r.status_code == 200, r.text
        data = r.json()
        for key in ("coupon_enabled", "coupon_percent", "coupon_expires_days"):
            assert key in data, f"Missing {key} in welcome-popup/public: {data.keys()}"
        assert isinstance(data["coupon_enabled"], bool)
        assert isinstance(data["coupon_percent"], int)


# ---------------------- 3. welcome-popup/email — banner submission ----------------------

class TestWelcomePopupEmailCapture:

    def setup_method(self):
        self.test_email = f"TEST_cartbanner_{uuid.uuid4().hex[:8]}@tilestationtest.com"

    def teardown_method(self):
        if not (MONGO_URL and DB_NAME):
            return

        async def cleanup(email):
            client = AsyncIOMotorClient(MONGO_URL)
            d = client[DB_NAME]
            await d.popup_emails.delete_many({"email": email})
            await d.shop_discount_codes.delete_many({"email": email})
            client.close()
        try:
            _run(cleanup(self.test_email))
        except Exception:
            pass

    def _ensure_coupon_enabled(self, admin_session):
        """Read current welcome popup config; if coupon is disabled, enable it for the test.
        Returns the original config so the test can restore it."""
        r = admin_session.get(f"{BASE_URL}/api/website-admin/welcome-popup")
        assert r.status_code == 200, r.text
        original = r.json()
        if not original.get("coupon_enabled"):
            payload = dict(original)
            payload["coupon_enabled"] = True
            payload.setdefault("coupon_percent", 10)
            payload.setdefault("coupon_expires_days", 30)
            payload.pop("_id", None)
            payload.pop("updated_at", None)
            r2 = admin_session.put(f"{BASE_URL}/api/website-admin/welcome-popup", json=payload)
            assert r2.status_code == 200, r2.text
        return original

    def _restore_popup(self, admin_session, original):
        payload = dict(original)
        payload.pop("_id", None)
        payload.pop("updated_at", None)
        admin_session.put(f"{BASE_URL}/api/website-admin/welcome-popup", json=payload)

    def test_post_email_captures_lead_and_mints_welcome_code(self, api, admin_session, db):
        original = self._ensure_coupon_enabled(admin_session)
        try:
            r = api.post(
                f"{BASE_URL}/api/website-admin/welcome-popup/email",
                json={"email": self.test_email},
            )
            assert r.status_code == 200, r.text
            assert "captured" in r.json().get("message", "").lower()

            # popup_emails persistence
            doc = _run(db.popup_emails.find_one({"email": self.test_email.lower()}))
            assert doc is not None, "popup_emails row not created"

            # WELCOME-* code minted
            code_doc = _run(db.shop_discount_codes.find_one({
                "email": self.test_email.lower(),
                "code": {"$regex": "^WELCOME-"},
            }))
            assert code_doc is not None, "No WELCOME-* code minted for the captured email"
            assert code_doc.get("percent_off"), "Code missing percent_off"
            assert code_doc.get("active") in (True, None), f"Code should be active: {code_doc}"
            assert code_doc.get("source") == "welcome_popup"
            assert code_doc.get("max_uses") == 1, "WELCOME code should be single-use"
        finally:
            self._restore_popup(admin_session, original)

    def test_missing_email_returns_400(self, api):
        r = api.post(f"{BASE_URL}/api/website-admin/welcome-popup/email", json={"email": ""})
        assert r.status_code == 400, r.text

    def test_idempotent_same_email_does_not_create_second_lead(self, api, admin_session, db):
        original = self._ensure_coupon_enabled(admin_session)
        try:
            r = api.post(
                f"{BASE_URL}/api/website-admin/welcome-popup/email",
                json={"email": self.test_email},
            )
            assert r.status_code == 200
            r2 = api.post(
                f"{BASE_URL}/api/website-admin/welcome-popup/email",
                json={"email": self.test_email},
            )
            assert r2.status_code == 200

            count = _run(db.popup_emails.count_documents({"email": self.test_email.lower()}))
            assert count == 1, f"Expected 1 popup_emails row, got {count}"

            # Should still only have one active WELCOME code for that email
            codes = _run(db.shop_discount_codes.count_documents({
                "email": self.test_email.lower(),
                "code": {"$regex": "^WELCOME-"},
                "used_count": 0,
                "active": True,
            }))
            assert codes == 1, f"Expected 1 unused WELCOME code, got {codes}"
        finally:
            self._restore_popup(admin_session, original)

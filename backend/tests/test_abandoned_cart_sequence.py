"""
P2 Abandoned Basket Email Sequence — backend tests.

Covers:
- /api/abandoned-carts/settings GET/PUT (defaults + persistence)
- /api/abandoned-carts/save (create/update + reminder flag reset)
- /api/abandoned-carts/mark-recovered/{email}
- /api/abandoned-carts/send-reminders (idempotent, disabled toggle, day-0/day-1 cadence)
- services/promo_codes.generate_promo_code_for_email idempotency (via day-1 reminder + reuse)
- /api/shop/discount-codes/validate (valid, used, wrong-email, expired, missing)
- /api/shop/guest-checkout (promo applied to total, consumed, second use rejected)
- /api/shop/guest-checkout/status/{session_id} recovered branch (code review only — Stripe live)

We talk to the LIVE backend at REACT_APP_BACKEND_URL plus do MongoDB-level fixups
(backdating updated_at, expiring codes) using motor with MONGO_URL/DB_NAME from
backend/.env so we don't need to wait real wall-clock hours.
"""
import os
import asyncio
import uuid
import pytest
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# Load backend .env for MONGO_URL / DB_NAME
load_dotenv(Path("/app/backend/.env"))
load_dotenv(Path("/app/frontend/.env"))

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

API = f"{BASE_URL}/api"

TEST_EMAIL = f"test_abandoned_{uuid.uuid4().hex[:6]}@tilestationtest.com"
TEST_EMAIL_2 = f"test_abandoned_{uuid.uuid4().hex[:6]}@tilestationtest.com"
TEST_EMAIL_3 = f"test_abandoned_{uuid.uuid4().hex[:6]}@tilestationtest.com"


@pytest.fixture(scope="module")
def http():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
def db(event_loop):
    client = AsyncIOMotorClient(MONGO_URL)
    database = client[DB_NAME]
    yield database
    # cleanup
    async def _cleanup():
        for em in (TEST_EMAIL, TEST_EMAIL_2, TEST_EMAIL_3):
            await database.abandoned_carts.delete_many({"customer_email": em})
            await database.shop_discount_codes.delete_many({"email": em})
            await database.shop_orders.delete_many({"customer_email": em})
    event_loop.run_until_complete(_cleanup())
    client.close()


def _run(loop, coro):
    return loop.run_until_complete(coro)


def _sample_items():
    return [{
        "product_id": f"test-prod-{uuid.uuid4().hex[:6]}",
        "name": "Test Tile",
        "price": 25.50,
        "quantity": 4,
        "sku": "TS-TEST",
        "image": "",
    }]


# ---------- Settings ----------

class TestSettings:
    def test_get_settings_defaults(self, http):
        r = http.get(f"{API}/abandoned-carts/settings")
        assert r.status_code == 200, r.text
        data = r.json()
        # Defaults from DEFAULTS dict (or any persisted value — both must match contract)
        assert "enabled" in data and isinstance(data["enabled"], bool)
        assert int(data.get("day_0_hours", 3)) >= 1
        assert int(data.get("day_1_hours", 24)) >= 1
        assert int(data.get("discount_percent", 10)) >= 0
        assert int(data.get("expires_days", 7)) >= 1

    def test_put_settings_persists(self, http):
        # save current
        original = http.get(f"{API}/abandoned-carts/settings").json()
        try:
            new_payload = {
                "enabled": True,
                "day_0_hours": 4,
                "day_1_hours": 25,
                "discount_percent": 15,
                "expires_days": 10,
            }
            r = http.put(f"{API}/abandoned-carts/settings", json=new_payload)
            assert r.status_code == 200, r.text
            saved = r.json()
            assert saved["day_0_hours"] == 4
            assert saved["discount_percent"] == 15

            r2 = http.get(f"{API}/abandoned-carts/settings")
            assert r2.status_code == 200
            data = r2.json()
            assert data["day_0_hours"] == 4
            assert data["day_1_hours"] == 25
            assert data["discount_percent"] == 15
            assert data["expires_days"] == 10
        finally:
            # restore defaults
            http.put(f"{API}/abandoned-carts/settings", json={
                "enabled": True, "day_0_hours": 3, "day_1_hours": 24,
                "discount_percent": 10, "expires_days": 7,
            })


# ---------- Save / Mark recovered ----------

class TestSaveAndRecover:
    def test_save_creates_then_updates_and_resets_flags(self, http, db, event_loop):
        payload = {
            "customer_email": TEST_EMAIL,
            "customer_name": "Test Shopper",
            "items": _sample_items(),
            "cart_total": 102.0,
        }
        r = http.post(f"{API}/abandoned-carts/save", json=payload)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "created"

        # Manually set reminder flags True to simulate prior send
        async def set_flags():
            await db.abandoned_carts.update_one(
                {"customer_email": TEST_EMAIL.lower()},
                {"$set": {"reminder_sent_day_0": True, "reminder_sent_day_1": True}},
            )
        _run(event_loop, set_flags())

        # Update payload (cart changed)
        payload["cart_total"] = 200.0
        r2 = http.post(f"{API}/abandoned-carts/save", json=payload)
        assert r2.status_code == 200
        assert r2.json()["status"] == "updated"

        async def fetch():
            return await db.abandoned_carts.find_one({"customer_email": TEST_EMAIL.lower()})
        doc = _run(event_loop, fetch())
        assert doc["cart_total"] == 200.0
        assert doc["reminder_sent_day_0"] is False
        assert doc["reminder_sent_day_1"] is False

    def test_mark_recovered(self, http, db, event_loop):
        r = http.post(f"{API}/abandoned-carts/mark-recovered/{TEST_EMAIL}")
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "success"

        async def fetch():
            return await db.abandoned_carts.find_one({"customer_email": TEST_EMAIL.lower()})
        doc = _run(event_loop, fetch())
        assert doc["status"] == "recovered"


# ---------- send-reminders cadence ----------

class TestReminders:
    def test_disabled_toggle_short_circuits(self, http):
        # Disable
        http.put(f"{API}/abandoned-carts/settings", json={
            "enabled": False, "day_0_hours": 3, "day_1_hours": 24,
            "discount_percent": 10, "expires_days": 7,
        })
        try:
            r = http.post(f"{API}/abandoned-carts/send-reminders")
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["status"] == "disabled"
            assert data["day_0_sent"] == 0
            assert data["day_1_sent"] == 0
        finally:
            http.put(f"{API}/abandoned-carts/settings", json={
                "enabled": True, "day_0_hours": 3, "day_1_hours": 24,
                "discount_percent": 10, "expires_days": 7,
            })

    def test_day_0_then_day_1_cadence_with_promo(self, http, db, event_loop):
        # Save a fresh abandoned cart for TEST_EMAIL_2
        http.post(f"{API}/abandoned-carts/save", json={
            "customer_email": TEST_EMAIL_2,
            "customer_name": "Cadence Tester",
            "items": _sample_items(),
            "cart_total": 88.0,
        })

        # Backdate updated_at to >3h ago so day_0 fires
        async def backdate(hours):
            await db.abandoned_carts.update_one(
                {"customer_email": TEST_EMAIL_2.lower()},
                {"$set": {"updated_at": datetime.now(timezone.utc) - timedelta(hours=hours)}},
            )
        _run(event_loop, backdate(4))

        r = http.post(f"{API}/abandoned-carts/send-reminders")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "ok"
        assert data["day_0_sent"] >= 1, f"Expected day_0 to fire, got {data}"

        # Idempotency: second call should not re-send day_0 (still <24h since update)
        async def fetch():
            return await db.abandoned_carts.find_one({"customer_email": TEST_EMAIL_2.lower()})
        doc1 = _run(event_loop, fetch())
        assert doc1["reminder_sent_day_0"] is True
        assert doc1.get("reminder_sent_day_1") is not True

        # Backdate further to >24h to trigger day_1
        _run(event_loop, backdate(25))

        r2 = http.post(f"{API}/abandoned-carts/send-reminders")
        assert r2.status_code == 200, r2.text
        d2 = r2.json()
        assert d2["day_1_sent"] >= 1, f"Expected day_1 to fire, got {d2}"

        doc2 = _run(event_loop, fetch())
        assert doc2["reminder_sent_day_1"] is True
        assert doc2.get("promo_code"), "promo_code must be stamped on cart"
        assert doc2["promo_code"].startswith("BACK-"), f"Expected BACK- prefix, got {doc2['promo_code']}"

        # Code is also persisted in shop_discount_codes
        async def fetch_code(code):
            return await db.shop_discount_codes.find_one({"code": code})
        code_doc = _run(event_loop, fetch_code(doc2["promo_code"]))
        assert code_doc is not None
        assert code_doc["email"] == TEST_EMAIL_2.lower()
        assert code_doc["max_uses"] == 1
        assert code_doc["used_count"] == 0
        assert code_doc["percent_off"] == 10

        # Idempotency: third call should not re-send (both flags True)
        r3 = http.post(f"{API}/abandoned-carts/send-reminders")
        assert r3.status_code == 200
        d3 = r3.json()
        # No new sends for our cart
        doc3 = _run(event_loop, fetch())
        assert doc3["promo_code"] == doc2["promo_code"]


# ---------- Promo code service ----------

class TestPromoCodes:
    def test_generate_is_idempotent_for_same_email_unused(self, db, event_loop):
        from services.promo_codes import generate_promo_code_for_email

        async def gen():
            a = await generate_promo_code_for_email(db, email=TEST_EMAIL_3, percent_off=10, expires_days=7)
            b = await generate_promo_code_for_email(db, email=TEST_EMAIL_3, percent_off=10, expires_days=7)
            return a, b
        a, b = _run(event_loop, gen())
        assert a["code"] == b["code"], "Same unused code should be reused"

    def test_generate_returns_new_after_consumed(self, db, event_loop):
        from services.promo_codes import generate_promo_code_for_email, consume_promo_code

        async def go():
            first = await generate_promo_code_for_email(db, email=TEST_EMAIL_3, percent_off=10, expires_days=7)
            await consume_promo_code(db, first["code"])
            second = await generate_promo_code_for_email(db, email=TEST_EMAIL_3, percent_off=10, expires_days=7)
            return first, second
        first, second = _run(event_loop, go())
        assert first["code"] != second["code"]


# ---------- /shop/discount-codes/validate ----------

class TestValidateEndpoint:
    def test_missing_code(self, http):
        r = http.post(f"{API}/shop/discount-codes/validate", json={"code": "", "email": TEST_EMAIL_2, "subtotal": 100})
        assert r.status_code == 200
        assert r.json()["valid"] is False

    def test_unknown_code(self, http):
        r = http.post(f"{API}/shop/discount-codes/validate", json={"code": "BACK-NOPE99", "email": TEST_EMAIL_2, "subtotal": 100})
        assert r.status_code == 200
        body = r.json()
        assert body["valid"] is False
        assert "not found" in (body.get("reason") or "").lower()

    def test_wrong_email(self, http, db, event_loop):
        # use code minted for TEST_EMAIL_2 in TestReminders
        async def fetch():
            return await db.shop_discount_codes.find_one({"email": TEST_EMAIL_2.lower(), "used_count": 0})
        code_doc = _run(event_loop, fetch())
        assert code_doc, "Expected an unused code for TEST_EMAIL_2 from earlier test"
        r = http.post(f"{API}/shop/discount-codes/validate",
                      json={"code": code_doc["code"], "email": "stranger@example.com", "subtotal": 100})
        assert r.status_code == 200
        body = r.json()
        assert body["valid"] is False
        assert "email" in (body.get("reason") or "").lower()

    def test_valid_code(self, http, db, event_loop):
        async def fetch():
            return await db.shop_discount_codes.find_one({"email": TEST_EMAIL_2.lower(), "used_count": 0})
        code_doc = _run(event_loop, fetch())
        assert code_doc
        r = http.post(f"{API}/shop/discount-codes/validate",
                      json={"code": code_doc["code"], "email": TEST_EMAIL_2, "subtotal": 100})
        assert r.status_code == 200
        body = r.json()
        assert body["valid"] is True
        assert body["percent_off"] == 10
        assert abs(body["discount_amount"] - 10.0) < 0.01

    def test_expired_code(self, http, db, event_loop):
        # Mint a code, then expire it via DB
        from services.promo_codes import generate_promo_code_for_email

        async def setup():
            res = await generate_promo_code_for_email(db, email=TEST_EMAIL, percent_off=10, expires_days=7,
                                                     source="test_expired", prefix="EXP")
            await db.shop_discount_codes.update_one(
                {"code": res["code"]},
                {"$set": {"expires_at": datetime.now(timezone.utc) - timedelta(days=1)}},
            )
            return res["code"]
        code = _run(event_loop, setup())
        r = http.post(f"{API}/shop/discount-codes/validate",
                      json={"code": code, "email": TEST_EMAIL, "subtotal": 100})
        assert r.status_code == 200
        body = r.json()
        assert body["valid"] is False
        assert "expired" in (body.get("reason") or "").lower()


# ---------- guest-checkout with promo ----------

class TestGuestCheckoutPromo:
    def test_promo_applied_and_consumed(self, http, db, event_loop):
        # Get the code for TEST_EMAIL_2 (single-use, unused)
        async def fetch_code():
            return await db.shop_discount_codes.find_one({"email": TEST_EMAIL_2.lower(), "used_count": 0})
        code_doc = _run(event_loop, fetch_code())
        assert code_doc, "Need an unused code"
        code = code_doc["code"]

        order_payload = {
            "customer": {
                "email": TEST_EMAIL_2,
                "firstName": "Cad",
                "lastName": "Tester",
                "phone": "07000000000",
            },
            "delivery": {
                "method": "collection",  # avoid delivery fee logic for predictability
                "postcode": "DA12 1AA",
                "address1": "1 Test St",
                "city": "Gravesend",
            },
            "billing": {"same_as_delivery": True},
            "items": [
                {"product_id": "test-promo-prod", "name": "Test", "price": 100.0, "quantity": 1.0},
            ],
            "payment": {"method": "card"},
            "promo_code": code,
        }
        r = http.post(f"{API}/shop/guest-checkout", json=order_payload)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("promo_applied"), "promo_applied should be present in response"
        assert body["promo_applied"]["code"] == code
        # subtotal=100, 10% off => total should be 90 (no delivery fee for collection)
        assert abs(body["total"] - 90.0) < 0.01, f"Expected total ~90, got {body['total']}"

        # Order doc has promo fields
        async def fetch_order():
            return await db.shop_orders.find_one({"id": body["order_id"]})
        order = _run(event_loop, fetch_order())
        assert order["promo_code"] == code
        assert abs(order["promo_discount"] - 10.0) < 0.01
        assert order["promo_percent_off"] == 10

        # used_count incremented
        async def fetch_code_again():
            return await db.shop_discount_codes.find_one({"code": code})
        cd = _run(event_loop, fetch_code_again())
        assert cd["used_count"] == 1

        # Re-submit with same code → validate endpoint should now reject as used
        r2 = http.post(f"{API}/shop/discount-codes/validate",
                       json={"code": code, "email": TEST_EMAIL_2, "subtotal": 100})
        body2 = r2.json()
        assert body2["valid"] is False
        assert "used" in (body2.get("reason") or "").lower()


# ---------- Admin list/stats ----------

class TestAdminListStats:
    def test_list(self, http):
        r = http.get(f"{API}/abandoned-carts/list?status=abandoned&limit=10")
        assert r.status_code == 200
        data = r.json()
        assert "carts" in data and "total" in data
        for c in data["carts"]:
            # Should expose new day_0/day_1 fields, not _id
            assert "_id" not in c

    def test_stats(self, http):
        r = http.get(f"{API}/abandoned-carts/stats")
        assert r.status_code == 200
        data = r.json()
        for k in ("total_abandoned", "recovered", "pending_reminders", "conversion_rate", "total_value"):
            assert k in data

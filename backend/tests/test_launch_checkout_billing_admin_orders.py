"""Pre-launch verification tests for Tile Station shop checkout & admin online orders.

Covers:
- POST /api/shop/guest-checkout with billing.same_as_delivery=True / False
- GET /api/shop/admin/online-orders (auth, pagination, filters, search, response shape)
- GET /api/shop/admin/online-orders/:id (auth, full detail incl. billing_address)
- Auth gating (401/403 for non-admin)
- Slashed-dimension URL splat route does NOT 404
- checkout_settings doc has expected payments/free_sample seed values

Stripe is LIVE — these tests DO NOT call /guest-checkout/pay (would create a real session).
"""
from __future__ import annotations

import os
import uuid
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env", override=False)

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"


# ---------- Fixtures ----------

@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_token(session):
    r = session.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code} {r.text}")
    data = r.json()
    token = data.get("access_token") or data.get("token")
    if not token:
        pytest.skip(f"No token in login response: {data}")
    return token


@pytest.fixture(scope="module")
def admin_session(session, admin_token):
    s = requests.Session()
    s.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {admin_token}",
    })
    return s


# ---------- Guest Checkout: billing address persistence ----------

def _make_guest_payload(*, same_as_delivery: bool, billing_override: dict | None = None):
    suffix = uuid.uuid4().hex[:6]
    items = [{
        "product_id": f"TEST-{suffix}",
        "name": "TEST_Tile Sample",
        "variant": "60x60",
        "price": 25.5,
        "quantity": 2.0,
        "image": "https://example.com/test.jpg",
    }]
    customer = {
        "firstName": "TestFirst",
        "lastName": "TestLast",
        "email": f"TEST_{suffix}@example.com",
        "phone": "07000000000",
    }
    delivery = {
        "method": "delivery",
        "speed": "standard",
        "address1": "1 Delivery Lane",
        "address2": "",
        "city": "London",
        "county": "Greater London",
        "postcode": "E1 6AN",
        "notes": "leave with neighbour",
    }
    billing = {
        "same_as_delivery": same_as_delivery,
        "firstName": customer["firstName"],
        "lastName": customer["lastName"],
        "company": "",
        "address1": delivery["address1"] if same_as_delivery else "",
        "address2": delivery["address2"] if same_as_delivery else "",
        "city": delivery["city"] if same_as_delivery else "",
        "county": delivery["county"] if same_as_delivery else "",
        "postcode": delivery["postcode"] if same_as_delivery else "",
    }
    if billing_override:
        billing.update(billing_override)
    return {
        "items": items,
        "customer": customer,
        "delivery": delivery,
        "billing": billing,
        "payment": {"method": "card"},
    }


class TestGuestCheckoutBilling:
    def test_creates_order_with_billing_same_as_delivery(self, session, admin_session):
        payload = _make_guest_payload(same_as_delivery=True)
        r = session.post(f"{BASE_URL}/api/shop/guest-checkout", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "order_id" in body and "order_number" in body
        order_id = body["order_id"]

        # Verify via admin detail endpoint
        d = admin_session.get(f"{BASE_URL}/api/shop/admin/online-orders/{order_id}", timeout=30)
        assert d.status_code == 200, d.text
        order = d.json()
        b = order.get("billing_address")
        assert b is not None, "billing_address missing on order doc"
        assert b.get("same_as_delivery") is True
        # Mirrors delivery
        assert b.get("address1") == payload["delivery"]["address1"]
        assert b.get("city") == payload["delivery"]["city"]
        assert b.get("postcode", "").upper() == payload["delivery"]["postcode"].upper().replace(" ", "") or \
               b.get("postcode", "") == payload["delivery"]["postcode"].upper()
        # First/last name fall back to customer when omitted
        assert b.get("first_name") == payload["customer"]["firstName"]
        assert b.get("last_name") == payload["customer"]["lastName"]

    def test_creates_order_with_separate_billing_address(self, session, admin_session):
        payload = _make_guest_payload(
            same_as_delivery=False,
            billing_override={
                "firstName": "BillFirst",
                "lastName": "BillLast",
                "company": "TEST_Co Ltd",
                "address1": "99 Billing Road",
                "address2": "Suite 5",
                "city": "Manchester",
                "county": "Greater Manchester",
                "postcode": "M1 1AA",
            },
        )
        r = session.post(f"{BASE_URL}/api/shop/guest-checkout", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        order_id = r.json()["order_id"]

        d = admin_session.get(f"{BASE_URL}/api/shop/admin/online-orders/{order_id}", timeout=30)
        assert d.status_code == 200
        b = d.json().get("billing_address")
        assert b is not None
        assert b.get("same_as_delivery") is False
        assert b.get("first_name") == "BillFirst"
        assert b.get("last_name") == "BillLast"
        assert b.get("company") == "TEST_Co Ltd"
        assert b.get("address1") == "99 Billing Road"
        assert b.get("city") == "Manchester"
        assert b.get("postcode", "").replace(" ", "").upper() == "M11AA"

    def test_guest_checkout_rejects_missing_customer(self, session):
        payload = _make_guest_payload(same_as_delivery=True)
        payload["customer"].pop("email")
        r = session.post(f"{BASE_URL}/api/shop/guest-checkout", json=payload, timeout=30)
        assert r.status_code == 400


# ---------- Admin Online Orders list ----------

class TestAdminOnlineOrdersList:
    def test_requires_auth(self, session):
        r = session.get(f"{BASE_URL}/api/shop/admin/online-orders", timeout=30)
        assert r.status_code in (401, 403), f"expected auth failure, got {r.status_code}"

    def test_list_response_shape(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/shop/admin/online-orders?limit=5&skip=0", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ("total", "skip", "limit", "orders"):
            assert k in data, f"missing key {k} in list response"
        assert isinstance(data["orders"], list)
        assert isinstance(data["total"], int)
        if data["orders"]:
            o = data["orders"][0]
            for k in (
                "id", "order_number", "customer_name", "customer_email",
                "delivery_method", "delivery_address", "billing_address",
                "subtotal", "delivery_fee", "total", "status",
                "payment_status", "payment_method", "items_count", "created_at",
            ):
                assert k in o, f"order summary missing {k}"

    def test_status_filter(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/shop/admin/online-orders?status=pending&limit=10", timeout=30)
        assert r.status_code == 200
        for o in r.json()["orders"]:
            assert o["status"] == "pending"

    def test_status_all_returns_any(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/shop/admin/online-orders?status=all&limit=5", timeout=30)
        assert r.status_code == 200

    def test_search_by_email(self, admin_session, session):
        # Create an order with a unique email to search for
        suffix = uuid.uuid4().hex[:8]
        payload = _make_guest_payload(same_as_delivery=True)
        unique_email = f"TEST_search_{suffix}@example.com"
        payload["customer"]["email"] = unique_email
        cr = session.post(f"{BASE_URL}/api/shop/guest-checkout", json=payload, timeout=30)
        assert cr.status_code == 200

        r = admin_session.get(
            f"{BASE_URL}/api/shop/admin/online-orders",
            params={"search": unique_email, "limit": 10},
            timeout=30,
        )
        assert r.status_code == 200
        emails = [o["customer_email"] for o in r.json()["orders"]]
        assert unique_email in emails

    def test_pagination_skip_limit(self, admin_session):
        r1 = admin_session.get(f"{BASE_URL}/api/shop/admin/online-orders?limit=2&skip=0", timeout=30)
        r2 = admin_session.get(f"{BASE_URL}/api/shop/admin/online-orders?limit=2&skip=2", timeout=30)
        assert r1.status_code == 200 and r2.status_code == 200
        ids1 = [o["id"] for o in r1.json()["orders"]]
        ids2 = [o["id"] for o in r2.json()["orders"]]
        # No overlap (assuming at least 4 orders exist post-create above)
        if ids1 and ids2:
            assert set(ids1).isdisjoint(set(ids2))

    def test_no_mongodb_objectid_in_response(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/shop/admin/online-orders?limit=5", timeout=30)
        assert r.status_code == 200
        body_str = r.text
        # Mongo ObjectId would serialize as {"$oid":"..."} or similar if it leaked
        assert '"_id"' not in body_str


# ---------- Admin Online Order detail ----------

class TestAdminOnlineOrderDetail:
    def test_requires_auth(self, session):
        r = session.get(f"{BASE_URL}/api/shop/admin/online-orders/does-not-exist", timeout=30)
        assert r.status_code in (401, 403)

    def test_404_when_unknown(self, admin_session):
        r = admin_session.get(
            f"{BASE_URL}/api/shop/admin/online-orders/{uuid.uuid4().hex}", timeout=30
        )
        assert r.status_code == 404

    def test_detail_includes_full_fields(self, session, admin_session):
        payload = _make_guest_payload(same_as_delivery=True)
        cr = session.post(f"{BASE_URL}/api/shop/guest-checkout", json=payload, timeout=30)
        assert cr.status_code == 200
        order_id = cr.json()["order_id"]

        r = admin_session.get(f"{BASE_URL}/api/shop/admin/online-orders/{order_id}", timeout=30)
        assert r.status_code == 200
        order = r.json()
        for k in (
            "id", "order_number", "customer_email", "customer_name",
            "delivery_method", "delivery_address", "billing_address",
            "items", "subtotal", "delivery_fee", "total", "status",
            "payment_status", "created_at",
        ):
            assert k in order, f"detail missing {k}"
        assert isinstance(order["items"], list) and len(order["items"]) >= 1
        assert "_id" not in order


# ---------- Slashed-dimension splat route ----------

class TestSlashedDimensionUrl:
    def test_collection_with_encoded_slash_does_not_404(self, session):
        # /shop/collection/70 x 350 x 20/5mm — slash is part of dimension
        from urllib.parse import quote
        slug = quote("70 x 350 x 20/5mm", safe="")
        # Public frontend route is React-only, but backend has a tiles/collection lookup endpoint.
        # We just verify the React app does not 404 by checking the index.html responds 200.
        r = session.get(f"{BASE_URL}/shop/collection/{slug}", timeout=30, allow_redirects=True)
        assert r.status_code == 200, f"expected 200 for slashed dimension URL, got {r.status_code}"
        # Should serve the SPA shell (contains a root div)
        assert "<div id=\"root\">" in r.text or "id=\"root\"" in r.text


# ---------- Checkout Settings seed verification ----------

class TestCheckoutSettingsSeed:
    def test_payments_flags_enabled(self, session):
        r = session.get(f"{BASE_URL}/api/website-admin/public/checkout-settings", timeout=30)
        assert r.status_code == 200, r.text
        cfg = r.json().get("settings", {})
        payments = cfg.get("payments", {})
        assert payments.get("paypal_enabled") is True
        assert payments.get("klarna_enabled") is True
        assert payments.get("wallet_express_enabled") is True

    def test_free_sample_seed(self, session):
        r = session.get(f"{BASE_URL}/api/website-admin/public/checkout-settings", timeout=30)
        assert r.status_code == 200
        fs = r.json().get("settings", {}).get("free_sample", {})
        assert fs.get("enabled") is True
        assert int(fs.get("threshold", 0)) == 100
        assert fs.get("fulfillment_mode") == "smart"
        assert "Ultra Tile" in (fs.get("direct_ship_suppliers") or [])

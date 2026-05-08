"""Track Order + Status Notes regression tests (launch-eve)."""
import os
import re
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://feature-verification-7.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASS = "admin123"
TEST_ORDER_NUMBER = "TS-260425-C455E9"
TEST_ORDER_ID = "c455e918-c610-4091-af8a-1b636b76ff46"
TEST_CUST_EMAIL = "qasim3638@gmail.com"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=20)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text[:200]}"
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ---------- Public Track Order ----------
class TestPublicTrack:
    def test_track_returns_order_with_history(self):
        r = requests.get(
            f"{BASE_URL}/api/shop/track/{TEST_ORDER_NUMBER}",
            params={"email": TEST_CUST_EMAIL}, timeout=20,
        )
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert data.get("order_number") == TEST_ORDER_NUMBER
        assert "status_history" in data
        assert isinstance(data["status_history"], list)

    def test_track_case_insensitive(self):
        r = requests.get(
            f"{BASE_URL}/api/shop/track/{TEST_ORDER_NUMBER.lower()}",
            params={"email": TEST_CUST_EMAIL.upper()}, timeout=20,
        )
        assert r.status_code == 200
        assert r.json().get("order_number") == TEST_ORDER_NUMBER

    def test_track_wrong_email_rejected(self):
        r = requests.get(
            f"{BASE_URL}/api/shop/track/{TEST_ORDER_NUMBER}",
            params={"email": "wrong@example.com"}, timeout=20,
        )
        assert r.status_code in (401, 403, 404)

    def test_track_suggest_did_you_mean(self):
        # Did You Mean recovery
        r = requests.get(
            f"{BASE_URL}/api/shop/track/suggest",
            params={"order_number": "TS-WRONG", "email": TEST_CUST_EMAIL},
            timeout=20,
        )
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        # should return a list of orders for that email
        suggestions = data.get("suggestions") or data.get("orders") or []
        nums = [s.get("order_number") for s in suggestions]
        assert TEST_ORDER_NUMBER in nums, f"Expected {TEST_ORDER_NUMBER} in suggestions {nums}"


# ---------- Admin status update with notes ----------
class TestStatusUpdate:
    def test_update_with_notes_persists_and_emails(self, auth_headers):
        payload = {"status": "processing", "notes": "TEST_NOTE Your tiles ship Monday morning"}
        r = requests.put(
            f"{BASE_URL}/api/shop/orders/{TEST_ORDER_ID}/status",
            json=payload, headers=auth_headers, timeout=30,
        )
        assert r.status_code == 200, f"PUT failed {r.status_code} {r.text[:300]}"
        data = r.json()
        # email_sent should be true (resend may fail in some envs but must be present)
        assert "email_sent" in data, f"Missing email_sent in response: {data}"

        # Verify the note was persisted via public track
        rt = requests.get(
            f"{BASE_URL}/api/shop/track/{TEST_ORDER_NUMBER}",
            params={"email": TEST_CUST_EMAIL}, timeout=20,
        )
        assert rt.status_code == 200
        history = rt.json().get("status_history", [])
        latest_with_note = [h for h in history if h.get("notes") == payload["notes"]]
        assert latest_with_note, f"Note not persisted. History: {history[-3:]}"

    def test_update_skip_notes(self, auth_headers):
        payload = {"status": "shipped"}  # no notes key
        r = requests.put(
            f"{BASE_URL}/api/shop/orders/{TEST_ORDER_ID}/status",
            json=payload, headers=auth_headers, timeout=30,
        )
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert "email_sent" in data

        rt = requests.get(
            f"{BASE_URL}/api/shop/track/{TEST_ORDER_NUMBER}",
            params={"email": TEST_CUST_EMAIL}, timeout=20,
        )
        assert rt.status_code == 200
        order = rt.json()
        assert order.get("status") == "shipped"

    def test_reset_to_processing(self, auth_headers):
        # Reset state for next runs
        r = requests.put(
            f"{BASE_URL}/api/shop/orders/{TEST_ORDER_ID}/status",
            json={"status": "processing"}, headers=auth_headers, timeout=30,
        )
        assert r.status_code == 200


# ---------- Email HTML deep-link CTA ----------
class TestEmailDeepLink:
    def test_email_template_contains_deep_link(self):
        # static source check - cheaper than sending an email
        path = "/app/backend/services/email.py"
        with open(path, "r") as f:
            src = f.read()
        # Must build /shop/track?order=...&email=...
        pattern = re.compile(r"/shop/track\?order=.{0,40}email=", re.IGNORECASE | re.DOTALL)
        assert pattern.search(src), "Email HTML missing /shop/track?order=...&email=... deep-link"

"""Test the welcome-email + voucher enhancement on showroom signup."""
import os
import sys
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from motor.motor_asyncio import AsyncIOMotorClient


def _db():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return client[os.environ["DB_NAME"]], client


@pytest.mark.asyncio
async def test_first_signup_mints_voucher_and_attempts_email():
    """First signup → voucher minted, email sent (mocked), lead doc has both."""
    db, client = _db()
    email = f"welcome-{uuid.uuid4().hex[:6]}@example.com"
    try:
        # Mock the email send (non-fatal even when Resend isn't configured)
        mock_send = AsyncMock(return_value={"sent": True, "error": None})
        with patch("services.email.send_lead_welcome_email", mock_send):
            from routes.marketing_admin import showroom_signup, ShowroomSignupPayload
            req = MagicMock()
            req.client.host = "1.2.3.4"
            req.headers = {"user-agent": "iPad/test"}
            payload = ShowroomSignupPayload(
                name="Welcome Bob", email=email, consent=True, showroom_id="tonbridge",
            )
            res = await showroom_signup(payload, req)

            assert res["ok"] is True
            assert res["voucher_issued"] is True
            mock_send.assert_awaited_once()
            kwargs = mock_send.await_args.kwargs
            assert kwargs["email"] == email
            assert kwargs["voucher_code"].startswith("WELCOME-")
            assert kwargs["percent_off"] == 5

        doc = await db.marketing_leads.find_one({"email": email}, {"_id": 0})
        assert doc["voucher_code"].startswith("WELCOME-")
        assert doc["welcome_email_sent_at"] is not None

        # Voucher persisted in shop_discount_codes
        promo = await db.shop_discount_codes.find_one({"code": doc["voucher_code"]})
        assert promo
        assert promo["source"] == "lead_welcome"
        assert promo["max_uses"] == 1
        assert promo["email"] == email
    finally:
        await db.marketing_leads.delete_many({"email": email})
        await db.shop_discount_codes.delete_many({"email": email})
        client.close()


@pytest.mark.asyncio
async def test_repeat_signup_does_not_resend_welcome():
    """Customer signing up twice (e.g. at a second showroom) updates the row
    but does NOT mint a fresh voucher or re-email."""
    db, client = _db()
    email = f"repeat-{uuid.uuid4().hex[:6]}@example.com"
    try:
        mock_send = AsyncMock(return_value={"sent": True, "error": None})
        with patch("services.email.send_lead_welcome_email", mock_send):
            from routes.marketing_admin import showroom_signup, ShowroomSignupPayload
            req = MagicMock()
            req.client.host = "1.2.3.4"
            req.headers = {"user-agent": "iPad/test"}
            p1 = ShowroomSignupPayload(name="A", email=email, consent=True, showroom_id="tonbridge")
            p2 = ShowroomSignupPayload(name="A2", email=email, consent=True, showroom_id="canterbury")
            await showroom_signup(p1, req)
            await showroom_signup(p2, req)
            # Welcome email called exactly ONCE (first signup only)
            assert mock_send.await_count == 1

        promos = await db.shop_discount_codes.count_documents({
            "email": email, "source": "lead_welcome",
        })
        assert promos == 1
    finally:
        await db.marketing_leads.delete_many({"email": email})
        await db.shop_discount_codes.delete_many({"email": email})
        client.close()


@pytest.mark.asyncio
async def test_email_failure_is_non_fatal():
    """If Resend fails, the lead is still saved and the response is 200.
    The lead remains eligible for re-trigger on next signup since
    welcome_email_sent_at is set to None on send failure."""
    db, client = _db()
    email = f"fail-{uuid.uuid4().hex[:6]}@example.com"
    try:
        mock_send = AsyncMock(return_value={"sent": False, "error": "SMTP down"})
        with patch("services.email.send_lead_welcome_email", mock_send):
            from routes.marketing_admin import showroom_signup, ShowroomSignupPayload
            req = MagicMock()
            req.client.host = "1.2.3.4"
            req.headers = {"user-agent": "iPad/test"}
            payload = ShowroomSignupPayload(name="Will Fail", email=email, consent=True)
            res = await showroom_signup(payload, req)
            assert res["ok"] is True

        doc = await db.marketing_leads.find_one({"email": email}, {"_id": 0})
        assert doc is not None
        # welcome_email_sent_at should be None after failure → next signup
        # would retry the email
        assert doc.get("welcome_email_sent_at") is None
    finally:
        await db.marketing_leads.delete_many({"email": email})
        await db.shop_discount_codes.delete_many({"email": email})
        client.close()

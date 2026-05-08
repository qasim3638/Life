"""Test the Marketing & SEO admin module.

Covers:
  • GET /api/marketing/admin/settings — returns merged defaults
  • PUT /api/marketing/admin/settings — partial updates merge cleanly
  • POST /api/marketing/showroom-signup — public, GDPR-safe (consent required)
    and idempotent on email
  • GET /api/marketing/admin/leads — admin-only viewer
  • Auth gating — non-admin users get 403
  • SEO audit endpoint runs without crashing (network checks return ok=False
    in dev because the live origin isn't reachable)
"""
import os
import sys
import asyncio
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from motor.motor_asyncio import AsyncIOMotorClient


def _db():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return client[os.environ["DB_NAME"]], client


@pytest.mark.asyncio
async def test_admin_settings_get_returns_defaults():
    db, client = _db()
    # Wipe any existing marketing settings doc
    await db.website_settings.delete_one({"key": "marketing"})
    try:
        from routes.marketing_admin import admin_get_marketing_settings
        admin = {"role": "super_admin", "email": "a@x"}
        res = await admin_get_marketing_settings(current_user=admin)
        assert "qr" in res and "referrals" in res and "lead_capture" in res
        # Default referral trigger_approved is enabled at £25
        assert res["referrals"]["trigger_approved"]["enabled"] is True
        assert res["referrals"]["trigger_approved"]["referrer_amount"] == 25
        # Default QR points to the existing trade signup page
        assert res["qr"]["default"]["destination"] == "/shop/trade/register"
    finally:
        client.close()


@pytest.mark.asyncio
async def test_admin_settings_put_merges_partial_updates():
    db, client = _db()
    await db.website_settings.delete_one({"key": "marketing"})
    try:
        from routes.marketing_admin import admin_put_marketing_settings, MarketingSettingsPayload
        admin = {"role": "admin", "email": "a@x"}

        # Update only the signup trigger
        payload = MarketingSettingsPayload(referrals={"trigger_signup": {"enabled": True, "referrer_amount": 10}})
        res = await admin_put_marketing_settings(payload, current_user=admin)
        assert res["referrals"]["trigger_signup"]["enabled"] is True
        assert res["referrals"]["trigger_signup"]["referrer_amount"] == 10
        # trigger_approved must NOT have been wiped
        assert res["referrals"]["trigger_approved"]["enabled"] is True

        # Update only QR
        payload2 = MarketingSettingsPayload(qr={"default": {"label": "Tonbridge Trade", "destination": "/promo/trade"}})
        res2 = await admin_put_marketing_settings(payload2, current_user=admin)
        assert res2["qr"]["default"]["label"] == "Tonbridge Trade"
        # Referrals must NOT have been wiped
        assert res2["referrals"]["trigger_signup"]["referrer_amount"] == 10
    finally:
        await db.website_settings.delete_one({"key": "marketing"})
        client.close()


@pytest.mark.asyncio
async def test_admin_settings_requires_admin_role():
    from routes.marketing_admin import admin_get_marketing_settings
    from fastapi import HTTPException
    user = {"role": "staff", "email": "x@x"}  # not admin
    with pytest.raises(HTTPException) as exc:
        await admin_get_marketing_settings(current_user=user)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_showroom_signup_requires_consent():
    """GDPR/PECR — consent=False MUST be rejected with 400."""
    db, client = _db()
    try:
        from routes.marketing_admin import showroom_signup, ShowroomSignupPayload
        from fastapi import HTTPException
        req = MagicMock()
        req.client.host = "1.2.3.4"
        req.headers = {"user-agent": "test"}
        payload = ShowroomSignupPayload(name="Bob", email="bob@example.com", consent=False)
        with pytest.raises(HTTPException) as exc:
            await showroom_signup(payload, req)
        assert exc.value.status_code == 400
        # Nothing stored
        count = await db.marketing_leads.count_documents({"email": "bob@example.com"})
        assert count == 0
    finally:
        client.close()


@pytest.mark.asyncio
async def test_showroom_signup_stores_lead_and_is_idempotent():
    db, client = _db()
    email = f"lead-{uuid.uuid4().hex[:6]}@example.com"
    try:
        from routes.marketing_admin import showroom_signup, ShowroomSignupPayload
        req = MagicMock()
        req.client.host = "1.2.3.4"
        req.headers = {"user-agent": "iPad/1.0"}

        # First signup
        p1 = ShowroomSignupPayload(name="Alice", email=email, consent=True, showroom_id="tonbridge")
        r1 = await showroom_signup(p1, req)
        assert r1["ok"] is True

        # Second signup with same email but different name
        p2 = ShowroomSignupPayload(name="Alice Updated", email=email, consent=True, showroom_id="canterbury")
        r2 = await showroom_signup(p2, req)
        assert r2["ok"] is True

        # Should be ONE document with the latest values
        count = await db.marketing_leads.count_documents({"email": email})
        assert count == 1
        doc = await db.marketing_leads.find_one({"email": email}, {"_id": 0})
        assert doc["name"] == "Alice Updated"
        assert doc["showroom_id"] == "canterbury"
        assert doc["consent"] is True
    finally:
        await db.marketing_leads.delete_many({"email": email})
        client.close()


@pytest.mark.asyncio
async def test_admin_leads_endpoint_returns_recent_first():
    db, client = _db()
    emails = [f"lead-{uuid.uuid4().hex[:6]}@example.com" for _ in range(3)]
    try:
        from datetime import datetime, timezone, timedelta
        for i, e in enumerate(emails):
            await db.marketing_leads.insert_one({
                "name": f"User {i}", "email": e, "consent": True,
                "consent_at": (datetime.now(timezone.utc) - timedelta(days=i)).isoformat(),
                "created_at": (datetime.now(timezone.utc) - timedelta(days=i)).isoformat(),
            })

        from routes.marketing_admin import admin_list_leads
        admin = {"role": "manager", "email": "m@x"}
        res = await admin_list_leads(limit=5, current_user=admin)
        assert res["total"] >= 3
        # Most recent first → emails[0] is index 0 of result
        first_emails = [l["email"] for l in res["leads"][:3]]
        assert emails[0] in first_emails
    finally:
        await db.marketing_leads.delete_many({"email": {"$in": emails}})
        client.close()


@pytest.mark.asyncio
async def test_seo_audit_runs_without_crashing():
    """Even if the live origin is unreachable in dev, the endpoint must
    return a structured response — never 500."""
    from routes.marketing_admin import admin_seo_audit
    admin = {"role": "super_admin", "email": "a@x"}
    res = await admin_seo_audit(current_user=admin)
    assert "checks" in res
    assert "origin" in res
    # 4 checks expected
    expected = {"sitemap", "robots", "homepage_meta", "product_descriptions"}
    assert expected.issubset(set(res["checks"].keys()))
    # product_descriptions runs against local DB and should always return ok bool
    assert isinstance(res["checks"]["product_descriptions"].get("ok"), bool)


@pytest.mark.asyncio
async def test_public_lead_capture_settings_endpoint():
    """The public endpoint must return only the safe fields needed by the
    showroom tablet — no admin-only data."""
    from routes.marketing_admin import public_lead_capture_settings
    res = await public_lead_capture_settings()
    assert "title" in res
    assert "consent_text" in res
    # Must NOT leak qr/referrals settings
    assert "qr" not in res
    assert "referrals" not in res

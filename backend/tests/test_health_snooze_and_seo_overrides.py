"""Tests for the outage-banner snooze + SEO-lock-in dismiss flows."""
import os
import sys
import uuid
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, AsyncMock

import pytest
import pytest_asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402


@pytest_asyncio.fixture
async def db():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    test_db = client[f"test_health_snooze_{uuid.uuid4().hex[:8]}"]
    yield test_db
    await client.drop_database(test_db.name)
    client.close()


# ----------  Health snooze  ----------


@pytest.mark.asyncio
async def test_active_returns_alerts_when_no_suppression(db, monkeypatch):
    from config import get_db as _  # noqa: F401 — ensure import works
    monkeypatch.setattr("routes.health_critical.get_db", lambda: db)

    await db.health_alerts.insert_many([
        {"id": "a1", "label": "Promo", "path": "/p", "resolved": False, "acknowledged": False,
         "first_failure_at": datetime.now(timezone.utc)},
        {"id": "a2", "label": "Search", "path": "/s", "resolved": False, "acknowledged": False,
         "first_failure_at": datetime.now(timezone.utc)},
    ])

    from routes.health_critical import active_alerts
    out = await active_alerts({"role": "admin", "email": "x@y"})
    assert out["count"] == 2
    assert out.get("suppressed_until") is None


@pytest.mark.asyncio
async def test_snooze_hides_banner_and_acks_current_incidents(db, monkeypatch):
    monkeypatch.setattr("routes.health_critical.get_db", lambda: db)

    await db.health_alerts.insert_one({
        "id": "a1", "label": "Promo", "path": "/p",
        "resolved": False, "acknowledged": False,
        "first_failure_at": datetime.now(timezone.utc),
    })

    from routes.health_critical import snooze_all, active_alerts, SnoozePayload
    res = await snooze_all(SnoozePayload(hours=24, reason="config fix"), {"role": "admin", "email": "admin@x"})
    assert res["ok"] is True
    assert res["hours"] == 24
    assert "suppressed_until" in res

    # Alerts endpoint should report empty + suppressed_until ISO timestamp
    out = await active_alerts({"role": "admin", "email": "admin@x"})
    assert out["alerts"] == []
    assert out["suppressed_until"] is not None
    assert out["suppressed_by"] == "admin@x"
    assert out["suppression_reason"] == "config fix"

    # Current incident should have been acknowledged
    doc = await db.health_alerts.find_one({"id": "a1"})
    assert doc["acknowledged"] is True
    assert doc.get("snoozed") is True


@pytest.mark.asyncio
async def test_snooze_caps_at_7_days(db, monkeypatch):
    monkeypatch.setattr("routes.health_critical.get_db", lambda: db)

    from routes.health_critical import snooze_all, SnoozePayload
    res = await snooze_all(SnoozePayload(hours=9999), {"role": "admin", "email": "admin@x"})
    assert res["hours"] == 168  # capped


@pytest.mark.asyncio
async def test_resume_clears_suppression(db, monkeypatch):
    monkeypatch.setattr("routes.health_critical.get_db", lambda: db)

    await db.health_alerts_suppression.insert_one({
        "id": "global",
        "suppressed_until": datetime.now(timezone.utc) + timedelta(hours=24),
        "suppressed_by": "x@y",
    })

    from routes.health_critical import resume_alerts, active_alerts
    await resume_alerts({"role": "admin", "email": "x@y"})

    out = await active_alerts({"role": "admin", "email": "x@y"})
    assert out.get("suppressed_until") is None


@pytest.mark.asyncio
async def test_expired_suppression_is_ignored(db, monkeypatch):
    monkeypatch.setattr("routes.health_critical.get_db", lambda: db)

    # Insert a suppression that's already past
    await db.health_alerts_suppression.insert_one({
        "id": "global",
        "suppressed_until": datetime.now(timezone.utc) - timedelta(hours=1),
        "suppressed_by": "x@y",
    })
    await db.health_alerts.insert_one({
        "id": "a1", "label": "Promo", "path": "/p",
        "resolved": False, "acknowledged": False,
        "first_failure_at": datetime.now(timezone.utc),
    })

    from routes.health_critical import active_alerts
    out = await active_alerts({"role": "admin", "email": "x@y"})
    # expired → suppressed_until returned None, alerts flow through
    assert out.get("suppressed_until") is None
    assert out["count"] == 1


# ----------  SEO lock-in dismiss  ----------


@pytest.mark.asyncio
async def test_dismiss_flips_item_to_acknowledged(db, monkeypatch):
    monkeypatch.setattr("routes.seo_health_status.get_db", lambda: db)

    # Dismiss gbp_api
    from routes.seo_health_status import dismiss_item, DismissPayload
    out = await dismiss_item("gbp_api", DismissPayload(days=30, reason="awaiting Google"), {"role": "admin", "email": "admin@x"})
    assert out["ok"] is True
    assert out["days"] == 30

    # Fetch status — patch the six underlying checks so we don't hit external APIs
    async def amber(): return {"status": "amber", "message": "waiting"}
    with patch("routes.seo_health_status._check_stripe_webhook", new=AsyncMock(side_effect=amber)), \
         patch("routes.seo_health_status._check_resend_domain",  new=AsyncMock(side_effect=amber)), \
         patch("routes.seo_health_status._check_gbp",            new=AsyncMock(side_effect=amber)), \
         patch("routes.seo_health_status._check_ads_api",        new=AsyncMock(side_effect=amber)), \
         patch("routes.seo_health_status._check_autopilot_jobs", new=AsyncMock(side_effect=amber)), \
         patch("routes.seo_health_status._check_last_autopilot_action", new=AsyncMock(side_effect=amber)):
        from routes.seo_health_status import seo_health_status
        resp = await seo_health_status({"role": "admin", "email": "admin@x"})
    gbp = resp["checks"]["gbp_api"]
    assert gbp["status"] == "acknowledged"
    assert gbp["overridden"] is True
    assert gbp["live_status"] == "amber"
    assert gbp["override_reason"] == "awaiting Google"
    # dismissed → counted toward locked
    assert resp["summary"]["locked_count"] == 1


@pytest.mark.asyncio
async def test_dismiss_auto_clears_when_live_check_green(db, monkeypatch):
    monkeypatch.setattr("routes.seo_health_status.get_db", lambda: db)

    # Dismiss gbp_api first
    from routes.seo_health_status import dismiss_item, DismissPayload
    await dismiss_item("gbp_api", DismissPayload(days=30), {"role": "admin", "email": "admin@x"})

    # Now live check goes green
    async def amber(): return {"status": "amber", "message": "waiting"}
    async def green(): return {"status": "green", "message": "connected"}
    with patch("routes.seo_health_status._check_stripe_webhook", new=AsyncMock(side_effect=amber)), \
         patch("routes.seo_health_status._check_resend_domain",  new=AsyncMock(side_effect=amber)), \
         patch("routes.seo_health_status._check_gbp",            new=AsyncMock(side_effect=green)), \
         patch("routes.seo_health_status._check_ads_api",        new=AsyncMock(side_effect=amber)), \
         patch("routes.seo_health_status._check_autopilot_jobs", new=AsyncMock(side_effect=amber)), \
         patch("routes.seo_health_status._check_last_autopilot_action", new=AsyncMock(side_effect=amber)):
        from routes.seo_health_status import seo_health_status
        resp = await seo_health_status({"role": "admin", "email": "admin@x"})
    gbp = resp["checks"]["gbp_api"]
    # Override should have auto-cleared because live is green
    assert gbp["status"] == "green"
    assert gbp.get("overridden") is not True
    # And the override doc should have been deleted
    assert await db.seo_health_overrides.find_one({"key": "gbp_api"}) is None


@pytest.mark.asyncio
async def test_dismiss_auto_clears_when_expired(db, monkeypatch):
    monkeypatch.setattr("routes.seo_health_status.get_db", lambda: db)

    # Insert an already-expired override directly
    await db.seo_health_overrides.insert_one({
        "key": "ads_api",
        "reason": "old",
        "dismissed_by": "x@y",
        "dismissed_at": datetime.now(timezone.utc) - timedelta(days=60),
        "expires_at": datetime.now(timezone.utc) - timedelta(days=30),
    })

    async def amber(): return {"status": "amber", "message": "heuristic"}
    with patch("routes.seo_health_status._check_stripe_webhook", new=AsyncMock(side_effect=amber)), \
         patch("routes.seo_health_status._check_resend_domain",  new=AsyncMock(side_effect=amber)), \
         patch("routes.seo_health_status._check_gbp",            new=AsyncMock(side_effect=amber)), \
         patch("routes.seo_health_status._check_ads_api",        new=AsyncMock(side_effect=amber)), \
         patch("routes.seo_health_status._check_autopilot_jobs", new=AsyncMock(side_effect=amber)), \
         patch("routes.seo_health_status._check_last_autopilot_action", new=AsyncMock(side_effect=amber)):
        from routes.seo_health_status import seo_health_status
        resp = await seo_health_status({"role": "admin", "email": "admin@x"})
    ads = resp["checks"]["ads_api"]
    assert ads["status"] == "amber"  # live status shows through — not acknowledged
    assert ads.get("overridden") is not True
    # and stale override row has been cleaned up
    assert await db.seo_health_overrides.find_one({"key": "ads_api"}) is None


@pytest.mark.asyncio
async def test_undismiss_removes_override(db, monkeypatch):
    monkeypatch.setattr("routes.seo_health_status.get_db", lambda: db)

    from routes.seo_health_status import dismiss_item, undismiss_item, DismissPayload
    await dismiss_item("resend_domain", DismissPayload(days=30), {"role": "admin", "email": "x@y"})
    assert await db.seo_health_overrides.find_one({"key": "resend_domain"}) is not None

    await undismiss_item("resend_domain", {"role": "admin", "email": "x@y"})
    assert await db.seo_health_overrides.find_one({"key": "resend_domain"}) is None


@pytest.mark.asyncio
async def test_invalid_key_rejected():
    from routes.seo_health_status import dismiss_item, DismissPayload
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        await dismiss_item("banana_api", DismissPayload(days=30), {"role": "admin", "email": "x@y"})
    assert exc.value.status_code == 400


# ----------  Health monitor — SPA HTML detection  ----------


@pytest.mark.asyncio
async def test_check_one_flags_spa_html_misconfiguration():
    """If the monitor URL returns the React SPA shell instead of JSON,
    the failure reason should point at the config problem explicitly."""
    import httpx
    from services.health_monitor import _check_one

    class _FakeClient:
        async def get(self, url, timeout=None):
            class _R:
                status_code = 200
                text = (
                    "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
                    "</head><body><div id=\"root\"></div></body></html>"
                )
                def json(self):
                    raise ValueError("not json")
            return _R()

    result = await _check_one(_FakeClient(), {"label": "Test", "path": "/x", "expect_key": "products"})
    assert result["healthy"] is False
    assert "MONITOR_BASE_URL" in (result["failure_reason"] or "")


def test_self_base_url_defaults_to_localhost(monkeypatch):
    """Previously we fell back to REACT_APP_BACKEND_URL which, on
    production, points at the public frontend domain — causing the
    monitor to self-ping through Cloudflare → SPA → chronic false
    positives. Default must be localhost:8001 so `is uvicorn alive
    and returning valid data?` is always answered correctly."""
    from services.health_monitor import _self_base_url
    monkeypatch.delenv("MONITOR_BASE_URL", raising=False)
    # Even with REACT_APP_BACKEND_URL set (which happens on every prod
    # backend because the same image is shared with the frontend build),
    # the monitor must not accidentally pick it up.
    monkeypatch.setenv("REACT_APP_BACKEND_URL", "https://tilestation.co.uk")
    assert _self_base_url() == "http://localhost:8001"


def test_self_base_url_respects_explicit_monitor_url(monkeypatch):
    """Opt-in CDN-layer monitoring via explicit env var."""
    from services.health_monitor import _self_base_url
    monkeypatch.setenv("MONITOR_BASE_URL", "https://api.tilestation.co.uk/")
    assert _self_base_url() == "https://api.tilestation.co.uk"  # trailing / stripped

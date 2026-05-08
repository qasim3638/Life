"""Tests for the Stripe webhook health check URL matching."""
import os
import sys
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _mock_httpx_response(status_code, json_body):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json = MagicMock(return_value=json_body)
    return resp


def _mock_client(resp):
    """Build a context-manager mock for httpx.AsyncClient."""
    cli = AsyncMock()
    cli.get = AsyncMock(return_value=resp)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=cli)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


@pytest.mark.asyncio
async def test_stripe_check_accepts_singular_url(monkeypatch):
    """Production registers webhooks at `/api/webhook/stripe` (singular)
    per shop.py. The lock-in check used to only accept `/webhooks/`
    (plural) — regression coverage for the fix."""
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_xxx")
    from routes.seo_health_status import _check_stripe_webhook

    resp = _mock_httpx_response(200, {
        "data": [{
            "id": "we_1TSihLRrO4AkXmfSflGMPY5d",
            "url": "https://tile-station-production.up.railway.app/api/webhook/stripe",
            "status": "enabled",
            "enabled_events": [
                "payment_intent.succeeded",
                "payment_intent.payment_failed",
                "charge.refunded",
                "checkout.session.completed",
            ],
        }],
    })

    with patch("routes.seo_health_status.httpx.AsyncClient", return_value=_mock_client(resp)):
        out = await _check_stripe_webhook()

    assert out["status"] == "green"
    assert "Live webhook configured" in out["message"]
    assert out["endpoints"][0]["url"].endswith("/api/webhook/stripe")


@pytest.mark.asyncio
async def test_stripe_check_also_accepts_plural_url(monkeypatch):
    """Historic `/webhooks/` URL must still validate (back-compat if
    somebody renames the backend route)."""
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_xxx")
    from routes.seo_health_status import _check_stripe_webhook

    resp = _mock_httpx_response(200, {
        "data": [{
            "id": "we_123",
            "url": "https://example.railway.app/api/webhooks/stripe",
            "status": "enabled",
            "enabled_events": [
                "payment_intent.succeeded",
                "payment_intent.payment_failed",
                "charge.refunded",
                "checkout.session.completed",
            ],
        }],
    })

    with patch("routes.seo_health_status.httpx.AsyncClient", return_value=_mock_client(resp)):
        out = await _check_stripe_webhook()

    assert out["status"] == "green"


@pytest.mark.asyncio
async def test_stripe_check_red_when_no_matching_url(monkeypatch):
    """An unrelated webhook URL should still be red — guard against
    accidentally passing any old URL as 'matching'."""
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_xxx")
    from routes.seo_health_status import _check_stripe_webhook

    resp = _mock_httpx_response(200, {
        "data": [{
            "id": "we_xyz",
            "url": "https://some-other-service.example.com/hooks/stripe",
            "status": "enabled",
            "enabled_events": ["payment_intent.succeeded"],
        }],
    })

    with patch("routes.seo_health_status.httpx.AsyncClient", return_value=_mock_client(resp)):
        out = await _check_stripe_webhook()

    assert out["status"] == "red"
    assert "/api/webhook/stripe" in out["message"]


@pytest.mark.asyncio
async def test_stripe_check_amber_when_events_missing(monkeypatch):
    """Right URL but missing required events → amber, not red."""
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_xxx")
    from routes.seo_health_status import _check_stripe_webhook

    resp = _mock_httpx_response(200, {
        "data": [{
            "id": "we_partial",
            "url": "https://prod.up.railway.app/api/webhook/stripe",
            "status": "enabled",
            "enabled_events": ["payment_intent.succeeded"],  # missing 3 others
        }],
    })

    with patch("routes.seo_health_status.httpx.AsyncClient", return_value=_mock_client(resp)):
        out = await _check_stripe_webhook()

    assert out["status"] == "amber"
    assert "missing" in out["message"].lower()

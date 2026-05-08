"""Tests for services.credential_check — startup credential safety net."""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_all_present_returns_ok(monkeypatch):
    """When every required env var is set, returns ok=True and fires no alert."""
    from services import credential_check
    for var, _ in credential_check.REQUIRED_CREDENTIALS:
        monkeypatch.setenv(var, "set-value")

    with patch("services.telegram_notify.notify_event", new=AsyncMock()) as mock_notify:
        result = await credential_check.run_credential_check_on_startup()

    assert result == {"ok": True, "missing": []}
    mock_notify.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_var_fires_telegram(monkeypatch):
    """When a required env var is empty, fires the Telegram alert."""
    from services import credential_check
    for var, _ in credential_check.REQUIRED_CREDENTIALS:
        monkeypatch.setenv(var, "set-value")
    monkeypatch.delenv("WALLCANO_PORTAL_PASSWORD", raising=False)

    mock_notify = AsyncMock()
    with patch("services.telegram_notify.notify_event", new=mock_notify):
        result = await credential_check.run_credential_check_on_startup()

    assert result["ok"] is False
    assert "WALLCANO_PORTAL_PASSWORD" in result["missing"]
    mock_notify.assert_awaited_once()
    args, kwargs = mock_notify.call_args
    assert args[0] == "missing_credentials"
    assert "WALLCANO_PORTAL_PASSWORD" in args[1]
    assert kwargs["dedupe_key"].startswith("missing_creds:")


@pytest.mark.asyncio
async def test_empty_string_treated_as_missing(monkeypatch):
    """Whitespace-only or empty values are treated as missing."""
    from services import credential_check
    for var, _ in credential_check.REQUIRED_CREDENTIALS:
        monkeypatch.setenv(var, "set-value")
    monkeypatch.setenv("CERAMICA_PORTAL_PASSWORD", "   ")

    mock_notify = AsyncMock()
    with patch("services.telegram_notify.notify_event", new=mock_notify):
        result = await credential_check.run_credential_check_on_startup()

    assert result["ok"] is False
    assert "CERAMICA_PORTAL_PASSWORD" in result["missing"]
    mock_notify.assert_awaited_once()


@pytest.mark.asyncio
async def test_multiple_missing_one_alert(monkeypatch):
    """Multiple missing vars produce ONE alert (not N)."""
    from services import credential_check
    for var, _ in credential_check.REQUIRED_CREDENTIALS:
        monkeypatch.delenv(var, raising=False)

    mock_notify = AsyncMock()
    with patch("services.telegram_notify.notify_event", new=mock_notify):
        result = await credential_check.run_credential_check_on_startup()

    assert result["ok"] is False
    assert len(result["missing"]) == len(credential_check.REQUIRED_CREDENTIALS)
    mock_notify.assert_awaited_once()
    body = mock_notify.call_args[0][1]
    for var, _ in credential_check.REQUIRED_CREDENTIALS:
        assert var in body


@pytest.mark.asyncio
async def test_telegram_failure_does_not_raise(monkeypatch):
    """If Telegram dispatch raises, the startup hook still returns cleanly."""
    from services import credential_check
    monkeypatch.delenv("WALLCANO_PORTAL_PASSWORD", raising=False)
    for var, _ in credential_check.REQUIRED_CREDENTIALS:
        if var != "WALLCANO_PORTAL_PASSWORD":
            monkeypatch.setenv(var, "set-value")

    async def boom(*_args, **_kwargs):
        raise RuntimeError("telegram down")

    with patch("services.telegram_notify.notify_event", new=boom):
        result = await credential_check.run_credential_check_on_startup()

    assert result["ok"] is False
    assert "WALLCANO_PORTAL_PASSWORD" in result["missing"]


@pytest.mark.asyncio
async def test_dedupe_key_stable_for_same_set(monkeypatch):
    """Same missing set → same dedupe key → Telegram dedupe layer suppresses."""
    from services import credential_check
    for var, _ in credential_check.REQUIRED_CREDENTIALS:
        monkeypatch.setenv(var, "set-value")
    monkeypatch.delenv("VERONA_PORTAL_PASSWORD", raising=False)

    seen_keys = []

    async def capture(_event, _text, *, dedupe_key=None):
        seen_keys.append(dedupe_key)

    with patch("services.telegram_notify.notify_event", new=capture):
        await credential_check.run_credential_check_on_startup()
        await credential_check.run_credential_check_on_startup()

    assert len(seen_keys) == 2
    assert seen_keys[0] == seen_keys[1]


def test_all_5_password_vars_in_required_list():
    """Regression: all 5 password env vars from the Feb 2026 cleanup are watched."""
    from services import credential_check
    watched = {var for var, _ in credential_check.REQUIRED_CREDENTIALS}
    assert "TILESTATION_ADMIN_PASSWORD" in watched
    assert "SPLENDOUR_PORTAL_PASSWORD" in watched
    assert "CERAMICA_PORTAL_PASSWORD" in watched
    assert "WALLCANO_PORTAL_PASSWORD" in watched
    assert "VERONA_PORTAL_PASSWORD" in watched


def test_critical_third_party_keys_in_required_list():
    """Regression: payment, email, storage, LLM keys all watched."""
    from services import credential_check
    watched = {var for var, _ in credential_check.REQUIRED_CREDENTIALS}
    # Payment
    assert "STRIPE_API_KEY" in watched
    # Email
    assert "RESEND_API_KEY" in watched
    # Object storage
    assert "R2_ACCOUNT_ID" in watched
    assert "R2_ACCESS_KEY_ID" in watched
    assert "R2_SECRET_ACCESS_KEY" in watched
    assert "R2_BUCKET_NAME" in watched
    assert "R2_PUBLIC_URL" in watched
    # AI
    assert "EMERGENT_LLM_KEY" in watched

"""Tests for routes.client_errors — guards against the customer-issues
panel getting flooded with browser-internal benign noise."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Request
from starlette.datastructures import Headers


def _fake_request(user_agent: str = "Mozilla/5.0") -> Request:
    """Build a minimal Request object for unit tests."""
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/client-errors/log",
        "headers": [(b"user-agent", user_agent.encode()), (b"x-forwarded-for", b"1.2.3.4")],
        "client": ("1.2.3.4", 12345),
        "query_string": b"",
        "scheme": "https",
        "server": ("test", 443),
    }
    return Request(scope)


def _payload(message: str, error_type: str = "js"):
    """Build a minimal valid ClientErrorPayload."""
    from routes.client_errors import ClientErrorPayload
    return ClientErrorPayload(
        session_id="sess-test-1",
        error_type=error_type,
        message=message,
        page_url="/shop",
        severity="error",
        breadcrumbs=[],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("benign_message", [
    "Failed to update a ServiceWorker for scope ('https://www.tilestation.co.uk/') with script ('https://www.tilestation.co.uk/service-worker.js'): An unknown error occurred when fetching the script.",
    "Failed to register a ServiceWorker for scope ('https://www.tilestation.co.uk/')",
    "Script https://tilestation.co.uk/service-worker.js load failed",
    "Service worker registration failed: NetworkError",
    "The user aborted a request",
    "ResizeObserver loop limit exceeded",
])
async def test_benign_browser_internal_errors_dropped(benign_message):
    """Regression: benign browser-internal noise is dropped at /api/client-errors/log
    so it never pollutes the customer-issues admin panel.

    Customer experience for these is unaffected — browser silently retries.
    Logging them was flooding the admin panel with non-actionable items."""
    from routes.client_errors import log_client_error
    payload = _payload(benign_message)
    request = _fake_request()

    with patch("routes.client_errors.get_db") as mock_db:
        # If we DON'T short-circuit, this would fail because `get_db()`
        # returns a MagicMock, not a real DB. Asserting we never reach
        # the DB write is the test.
        mock_db.return_value = AsyncMock()
        result = await log_client_error(payload, request)

    assert result == {"ok": True, "skipped": "benign_browser_internal"}


@pytest.mark.asyncio
async def test_real_customer_error_still_logged():
    """Anti-regression: filter MUST NOT drop genuine customer-impacting
    errors. Verify by sending a real-looking 500-error payload — it
    should NOT be classified as benign."""
    from routes.client_errors import log_client_error
    payload = _payload(
        "500 on /api/orders/create: Database connection lost",
        error_type="api",
    )
    request = _fake_request()

    # We expect this NOT to short-circuit as benign — it should reach
    # the DB rate-limit step. Mock DB to verify we got that far.
    db_mock = AsyncMock()
    db_mock.client_errors.count_documents = AsyncMock(return_value=0)
    db_mock.client_errors.insert_one = AsyncMock(return_value=None)

    with patch("routes.client_errors.get_db", return_value=db_mock), \
         patch("routes.client_errors.notify_event", new=AsyncMock()):
        result = await log_client_error(payload, request)

    # Either accepted or rate-limited but NOT skipped as benign.
    assert result.get("skipped") != "benign_browser_internal"


@pytest.mark.asyncio
async def test_script_error_short_circuit_still_works():
    """Anti-regression: pre-existing 'Script error.' filter is unchanged."""
    from routes.client_errors import log_client_error
    payload = _payload("Script error.")
    request = _fake_request()

    with patch("routes.client_errors.get_db") as mock_db:
        mock_db.return_value = AsyncMock()
        result = await log_client_error(payload, request)

    assert result == {"ok": True, "skipped": "cross_origin_browser_extension"}


@pytest.mark.asyncio
async def test_bot_traffic_filter_runs_first():
    """Anti-regression: bot UA detection short-circuits BEFORE the benign
    filter so we don't even need to evaluate patterns for bot traffic."""
    from routes.client_errors import log_client_error
    payload = _payload("Failed to update a ServiceWorker")
    request = _fake_request(user_agent="Googlebot/2.1")

    with patch("routes.client_errors.get_db") as mock_db:
        mock_db.return_value = AsyncMock()
        result = await log_client_error(payload, request)

    assert result == {"ok": True, "skipped": "bot_traffic"}

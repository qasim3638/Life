"""Tests for the Pinterest auto-pin integration."""
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402


@pytest_asyncio.fixture
async def db(monkeypatch):
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    test_db = client[f"test_pin_{uuid.uuid4().hex[:8]}"]
    monkeypatch.setattr("services.pinterest.get_db", lambda: test_db)
    yield test_db
    await client.drop_database(test_db.name)
    client.close()


# ──────── Settings ────────

@pytest.mark.asyncio
async def test_save_tokens_and_get_settings(db):
    from services.pinterest import save_tokens, get_settings
    saved = await save_tokens(
        access_token="atok", refresh_token="rtok",
        expires_in_seconds=2_592_000, connected_by_email="qasim@x",
    )
    assert saved["access_token"] == "atok"
    assert saved["connected_by_email"] == "qasim@x"
    assert "token_expires_at" in saved
    s = await get_settings()
    assert s["access_token"] == "atok"


@pytest.mark.asyncio
async def test_disconnect_clears_settings(db):
    from services.pinterest import save_tokens, disconnect, get_settings
    await save_tokens(access_token="atok", refresh_token="rtok",
                      expires_in_seconds=86400)
    await disconnect()
    s = await get_settings()
    assert not s


@pytest.mark.asyncio
async def test_set_board_persists(db):
    from services.pinterest import save_tokens, set_board, get_settings
    await save_tokens(access_token="a", refresh_token="r", expires_in_seconds=86400)
    await set_board("9876543210", "TileStation Inspiration")
    s = await get_settings()
    assert s["board_id"] == "9876543210"
    assert s["board_name"] == "TileStation Inspiration"


# ──────── OAuth URL ────────

def test_authorize_url_requires_app_id(monkeypatch):
    from services.pinterest import authorize_url
    monkeypatch.delenv("PINTEREST_APP_ID", raising=False)
    with pytest.raises(RuntimeError, match="PINTEREST_APP_ID"):
        authorize_url()


def test_authorize_url_includes_correct_params(monkeypatch):
    from services.pinterest import authorize_url
    monkeypatch.setenv("PINTEREST_APP_ID", "1234567890")
    monkeypatch.setenv("PINTEREST_REDIRECT_URI", "https://example.com/cb")
    url = authorize_url(state="qasim@x")
    assert url.startswith("https://www.pinterest.com/oauth/?")
    assert "client_id=1234567890" in url
    assert "redirect_uri=https%3A%2F%2Fexample.com%2Fcb" in url
    assert "response_type=code" in url
    assert "pins%3Awrite" in url
    assert "state=qasim%40x" in url


# ──────── Status reporting ────────

@pytest.mark.asyncio
async def test_status_when_disconnected(db, monkeypatch):
    monkeypatch.delenv("PINTEREST_APP_ID", raising=False)
    monkeypatch.delenv("PINTEREST_APP_SECRET", raising=False)
    from services.pinterest import status
    s = await status()
    assert s["app_credentials_set"] is False
    assert s["connected"] is False


@pytest.mark.asyncio
async def test_status_after_connect(db, monkeypatch):
    monkeypatch.setenv("PINTEREST_APP_ID", "1234")
    monkeypatch.setenv("PINTEREST_APP_SECRET", "abc")
    from services.pinterest import save_tokens, set_board, status
    await save_tokens(access_token="atok", refresh_token="rtok",
                      expires_in_seconds=86400, connected_by_email="qasim@x")
    await set_board("777", "TileStation")
    s = await status()
    assert s["connected"] is True
    assert s["app_credentials_set"] is True
    assert s["board_id"] == "777"
    assert s["board_name"] == "TileStation"
    assert s["connected_by_email"] == "qasim@x"


# ──────── Token refresh ────────

@pytest.mark.asyncio
async def test_refresh_skipped_when_token_fresh(db, monkeypatch):
    """Token with 25 days to live should NOT trigger a refresh."""
    monkeypatch.setenv("PINTEREST_APP_ID", "1234")
    monkeypatch.setenv("PINTEREST_APP_SECRET", "abc")
    from services.pinterest import save_tokens, _refresh_if_needed
    await save_tokens(access_token="fresh-token", refresh_token="rtok",
                      expires_in_seconds=25 * 86400)

    # Should never call httpx because no refresh needed
    with patch("services.pinterest.httpx.AsyncClient") as mock_cli:
        out = await _refresh_if_needed()
        assert out == "fresh-token"
        mock_cli.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_fires_when_token_near_expiry(db, monkeypatch):
    """Token with <5 days to live triggers a refresh + persists the new one."""
    monkeypatch.setenv("PINTEREST_APP_ID", "1234")
    monkeypatch.setenv("PINTEREST_APP_SECRET", "abc")
    from services.pinterest import save_tokens, _refresh_if_needed, get_settings
    await save_tokens(access_token="old-token", refresh_token="rtok",
                      expires_in_seconds=2 * 86400)

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json = MagicMock(return_value={
        "access_token": "new-token", "refresh_token": "new-rtok",
        "expires_in": 30 * 86400,
    })
    cli = AsyncMock()
    cli.post = AsyncMock(return_value=fake_resp)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=cli)
    cm.__aexit__ = AsyncMock(return_value=None)
    with patch("services.pinterest.httpx.AsyncClient", return_value=cm):
        out = await _refresh_if_needed()
    assert out == "new-token"
    s = await get_settings()
    assert s["access_token"] == "new-token"
    assert s["refresh_token"] == "new-rtok"


# ──────── create_pin ────────

@pytest.mark.asyncio
async def test_create_pin_skips_when_no_board(db, monkeypatch):
    """If no board is set, pin creation is a no-op (success=False)."""
    monkeypatch.setenv("PINTEREST_APP_ID", "x")
    monkeypatch.setenv("PINTEREST_APP_SECRET", "y")
    from services.pinterest import save_tokens, create_pin
    await save_tokens(access_token="atok", refresh_token="rtok",
                      expires_in_seconds=86400)
    out = await create_pin(title="t", description="d",
                           image_url="https://x/im.png", link="https://x/")
    assert out["success"] is False
    assert out["error"] == "no_board_set"


@pytest.mark.asyncio
async def test_create_pin_skips_when_disconnected(db):
    from services.pinterest import create_pin
    out = await create_pin(title="t", description="d",
                           image_url="https://x/im.png", link="https://x/")
    assert out["success"] is False
    # board check happens before token check, so we'll get no_board_set
    assert out["error"] in ("no_board_set", "not_connected")


@pytest.mark.asyncio
async def test_create_pin_happy_path(db, monkeypatch):
    monkeypatch.setenv("PINTEREST_APP_ID", "x")
    monkeypatch.setenv("PINTEREST_APP_SECRET", "y")
    from services.pinterest import save_tokens, set_board, create_pin
    await save_tokens(access_token="atok", refresh_token="rtok",
                      expires_in_seconds=86400)
    await set_board("777", "TileStation")

    fake_resp = MagicMock()
    fake_resp.status_code = 201
    fake_resp.json = MagicMock(return_value={"id": "pin_111"})
    cli = AsyncMock()
    cli.post = AsyncMock(return_value=fake_resp)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=cli)
    cm.__aexit__ = AsyncMock(return_value=None)
    with patch("services.pinterest.httpx.AsyncClient", return_value=cm):
        out = await create_pin(
            title="Marble guide",
            description="Buyer's guide to marble tiles in the UK.",
            image_url="https://tilestation.co.uk/img.png",
            link="https://tilestation.co.uk/blog/marble-guide",
            alt_text="Marble bathroom photo",
        )
    assert out["success"] is True
    assert out["pin_id"] == "pin_111"
    assert out["pin_url"] == "https://pinterest.com/pin/pin_111"
    # Verify the request body that was sent
    call = cli.post.call_args
    body = call.kwargs["json"]
    assert body["board_id"] == "777"
    assert body["title"] == "Marble guide"
    assert body["link"] == "https://tilestation.co.uk/blog/marble-guide"
    assert body["media_source"] == {"source_type": "image_url", "url": "https://tilestation.co.uk/img.png"}
    assert body["alt_text"] == "Marble bathroom photo"


@pytest.mark.asyncio
async def test_create_pin_truncates_long_description(db, monkeypatch):
    """Pinterest rejects description > 500 chars — we truncate."""
    monkeypatch.setenv("PINTEREST_APP_ID", "x")
    monkeypatch.setenv("PINTEREST_APP_SECRET", "y")
    from services.pinterest import save_tokens, set_board, create_pin
    await save_tokens(access_token="atok", refresh_token="rtok",
                      expires_in_seconds=86400)
    await set_board("777", "TileStation")

    fake_resp = MagicMock()
    fake_resp.status_code = 201
    fake_resp.json = MagicMock(return_value={"id": "p"})
    cli = AsyncMock()
    cli.post = AsyncMock(return_value=fake_resp)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=cli)
    cm.__aexit__ = AsyncMock(return_value=None)
    with patch("services.pinterest.httpx.AsyncClient", return_value=cm):
        await create_pin(title="x" * 200, description="d" * 800,
                         image_url="https://x/i.png", link="https://x/")
    body = cli.post.call_args.kwargs["json"]
    assert len(body["title"]) == 100
    assert len(body["description"]) == 500


@pytest.mark.asyncio
async def test_create_pin_handles_400(db, monkeypatch):
    monkeypatch.setenv("PINTEREST_APP_ID", "x")
    monkeypatch.setenv("PINTEREST_APP_SECRET", "y")
    from services.pinterest import save_tokens, set_board, create_pin
    await save_tokens(access_token="atok", refresh_token="rtok",
                      expires_in_seconds=86400)
    await set_board("777", "TileStation")

    fake_resp = MagicMock()
    fake_resp.status_code = 400
    fake_resp.text = '{"message": "Image URL not fetchable"}'
    cli = AsyncMock()
    cli.post = AsyncMock(return_value=fake_resp)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=cli)
    cm.__aexit__ = AsyncMock(return_value=None)
    with patch("services.pinterest.httpx.AsyncClient", return_value=cm):
        out = await create_pin(title="t", description="d",
                               image_url="https://x/i.png", link="https://x/")
    assert out["success"] is False
    assert out["error_code"] == 400
    assert "Image URL" in out["error"]


@pytest.mark.asyncio
async def test_create_pin_retries_once_on_401(db, monkeypatch):
    """A 401 should trigger ONE forced refresh + retry. If the retry
    succeeds, treat the call as a success."""
    monkeypatch.setenv("PINTEREST_APP_ID", "x")
    monkeypatch.setenv("PINTEREST_APP_SECRET", "y")
    from services.pinterest import save_tokens, set_board, create_pin
    await save_tokens(access_token="old", refresh_token="rtok",
                      expires_in_seconds=86400)
    await set_board("777", "TileStation")

    # First /pins call → 401, then refresh-token call → 200, then second
    # /pins call → 201. We need the AsyncClient mock to handle those
    # three POSTs in order.
    fail_resp = MagicMock()
    fail_resp.status_code = 401
    fail_resp.text = "expired"
    refresh_resp = MagicMock()
    refresh_resp.status_code = 200
    refresh_resp.json = MagicMock(return_value={
        "access_token": "fresh", "refresh_token": "rtok2", "expires_in": 30 * 86400,
    })
    success_resp = MagicMock()
    success_resp.status_code = 201
    success_resp.json = MagicMock(return_value={"id": "pin_222"})

    call_log = []
    async def fake_post(url, **kwargs):
        call_log.append(url)
        if url.endswith("/pins") and len(call_log) == 1:
            return fail_resp
        if url.endswith("/oauth/token"):
            return refresh_resp
        return success_resp
    cli = AsyncMock()
    cli.post = fake_post
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=cli)
    cm.__aexit__ = AsyncMock(return_value=None)
    with patch("services.pinterest.httpx.AsyncClient", return_value=cm):
        out = await create_pin(title="t", description="d",
                               image_url="https://x/i.png", link="https://x/")
    assert out["success"] is True
    assert out["pin_id"] == "pin_222"


# ──────── Editorial autopilot integration ────────

@pytest.mark.asyncio
async def test_auto_pin_skipped_when_pinterest_disconnected(monkeypatch):
    """The autopilot's _auto_pin_when_ready helper must be a silent
    no-op if Pinterest isn't connected. This is the safety net that
    means a disabled Pinterest never breaks article publishing."""
    from services import editorial_autopilot as eap

    async def fake_status():
        return {"connected": False, "board_id": None}
    monkeypatch.setattr("services.pinterest.status", fake_status)

    create_pin_mock = AsyncMock()
    monkeypatch.setattr("services.pinterest.create_pin", create_pin_mock)

    await eap._auto_pin_when_ready("anything", max_wait_seconds=0)
    create_pin_mock.assert_not_called()


@pytest.mark.asyncio
async def test_auto_pin_publishes_when_hero_ready(db, monkeypatch):
    """Happy path: Pinterest connected, hero banner present → create_pin
    fires with the right URLs and the article row gets the pin metadata."""
    from services import editorial_autopilot as eap
    monkeypatch.setattr(eap, "get_db", lambda: db)
    monkeypatch.setenv("FRONTEND_BASE_URL", "https://tilestation.co.uk")

    await db.blog_articles.insert_one({
        "slug": "test-pin-article",
        "title": "Marble Tiles Buyer's Guide",
        "meta_description": "Choose the right marble tiles for your home.",
        "hero_image_url": "/api/website/marketing-media/hero1.png",
        "status": "published",
    })

    async def fake_status():
        return {"connected": True, "board_id": "777"}
    monkeypatch.setattr("services.pinterest.status", fake_status)

    create_mock = AsyncMock(return_value={
        "success": True, "pin_id": "pin_xyz",
        "pin_url": "https://pinterest.com/pin/pin_xyz",
    })
    monkeypatch.setattr("services.pinterest.create_pin", create_mock)

    await eap._auto_pin_when_ready("test-pin-article", max_wait_seconds=10)

    # Verify Pin was attempted with the right URLs
    assert create_mock.await_count == 1
    kwargs = create_mock.call_args.kwargs
    assert kwargs["title"] == "Marble Tiles Buyer's Guide"
    assert kwargs["image_url"] == "https://tilestation.co.uk/api/website/marketing-media/hero1.png"
    assert kwargs["link"] == "https://tilestation.co.uk/blog/test-pin-article"

    # Verify the article was updated with pin metadata
    doc = await db.blog_articles.find_one({"slug": "test-pin-article"})
    assert doc["pinterest_pin_id"] == "pin_xyz"
    assert doc["pinterest_status"] == "published"
    assert doc["pinterest_error"] is None


@pytest.mark.asyncio
async def test_auto_pin_records_failure_without_breaking(db, monkeypatch):
    """A pin failure must persist the error on the article doc — not
    raise. The autopilot run shouldn't fail because Pinterest had
    a hiccup."""
    from services import editorial_autopilot as eap
    monkeypatch.setattr(eap, "get_db", lambda: db)
    monkeypatch.setenv("FRONTEND_BASE_URL", "https://tilestation.co.uk")

    await db.blog_articles.insert_one({
        "slug": "broken-pin",
        "title": "Test",
        "meta_description": "Test",
        "hero_image_url": "/img/hero.png",
        "status": "published",
    })
    async def fake_status():
        return {"connected": True, "board_id": "777"}
    monkeypatch.setattr("services.pinterest.status", fake_status)
    monkeypatch.setattr("services.pinterest.create_pin",
                        AsyncMock(return_value={"success": False, "error": "rate_limited", "pin_id": None}))

    # Should NOT raise
    await eap._auto_pin_when_ready("broken-pin", max_wait_seconds=10)

    doc = await db.blog_articles.find_one({"slug": "broken-pin"})
    assert doc["pinterest_status"] == "failed"
    assert doc["pinterest_error"] == "rate_limited"
    assert doc.get("pinterest_pin_id") is None


@pytest.mark.asyncio
async def test_auto_pin_skips_when_hero_never_arrives(db, monkeypatch):
    """If banner generation fails or hangs, the auto-pin gives up
    cleanly — Pinterest needs an image, no point firing without one."""
    from services import editorial_autopilot as eap
    monkeypatch.setattr(eap, "get_db", lambda: db)

    await db.blog_articles.insert_one({
        "slug": "no-hero",
        "title": "Test",
        "meta_description": "Test",
        "hero_image_url": None,  # banner gen failed
        "status": "published",
    })
    async def fake_status():
        return {"connected": True, "board_id": "777"}
    monkeypatch.setattr("services.pinterest.status", fake_status)
    create_mock = AsyncMock()
    monkeypatch.setattr("services.pinterest.create_pin", create_mock)

    # Use a tiny wait so the test runs fast
    await eap._auto_pin_when_ready("no-hero", max_wait_seconds=2)
    create_mock.assert_not_called()

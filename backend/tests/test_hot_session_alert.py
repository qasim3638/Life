"""
Hot Session Telegram alert — unit tests for the URL classifier and the
detection logic in `routes/analytics.py`.

These tests deliberately stay at the unit level (no real HTTP, no real
Mongo) so they run fast in CI and don't touch live data.
"""
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from routes.analytics import _is_pdp_url  # noqa: E402


# ---------- _is_pdp_url ---------- #

@pytest.mark.parametrize(
    "url,expected",
    [
        # Real product pages ─ should match
        ("/shop/collection/60x60-porcelain", True),
        ("/shop/product/abc-123", True),
        ("/tile/marble-white", True),
        ("/product/xyz", True),
        ("/product-detail/abc?ref=fb", True),
        # Storefront utility / auth routes ─ NOT PDPs
        ("/shop/login", False),
        ("/shop/register", False),
        ("/shop/trade/login", False),
        ("/shop/checkout", False),
        ("/shop/basket", False),
        ("/shop/wishlist", False),
        ("/shop/info/delivery", False),
        # Other non-product paths
        ("/", False),
        ("/admin/live-visitors", False),
        ("/contact", False),
        ("", False),
        (None, False),
        # Malformed
        ("/shop", False),  # no slug → not a PDP
        ("/tile/", False),
    ],
)
def test_is_pdp_url(url, expected):
    assert _is_pdp_url(url) is expected


# ---------- Hot Session detection logic ---------- #

@pytest.mark.asyncio
async def test_hot_session_fires_when_thresholds_met():
    """Posting a 4th PDP page-view 3+ minutes after the first session entry
    should fire the `hot_session` Telegram event exactly once."""
    from fastapi.testclient import TestClient
    from routes import analytics as analytics_mod

    now = datetime.now(timezone.utc)
    session_id = "hot-session-test-1"
    visitor_id = "visitor-hot-1"

    # Mock Mongo: page_views.find returns 4 prior PDPs spanning >2 min
    fake_pages = [
        {"page_url": "/shop/product/a", "timestamp": now - timedelta(minutes=4)},
        {"page_url": "/shop/product/b", "timestamp": now - timedelta(minutes=3)},
        {"page_url": "/shop/product/c", "timestamp": now - timedelta(minutes=2)},
        {"page_url": "/shop/product/d", "timestamp": now},
    ]
    fake_cursor = MagicMock()
    fake_cursor.to_list = AsyncMock(return_value=fake_pages)

    fake_db = MagicMock()
    fake_db.page_views.insert_one = AsyncMock()
    fake_db.page_views.find = MagicMock(return_value=fake_cursor)
    fake_db.analytics_daily.update_one = AsyncMock()
    fake_db.known_devices.find_one = AsyncMock(return_value=None)  # not tagged

    fired = []

    def _fake_ff(event_type, text, *, dedupe_key=None):
        fired.append((event_type, dedupe_key, text))

    with patch.object(analytics_mod, "get_db", return_value=fake_db), \
         patch("services.telegram_notify.fire_and_forget", side_effect=_fake_ff), \
         patch.object(analytics_mod, "broadcast_live_update", new=AsyncMock()), \
         patch.object(analytics_mod, "get_geo_location", new=AsyncMock(return_value={"country": "United Kingdom", "city": "London"})):

        # Build the request payload + a fake Request object
        from server import app  # FastAPI app
        client = TestClient(app)
        payload = {
            "session_id": session_id,
            "page_url": "/shop/product/d",
            "page_title": "Product D",
            "referrer": "Direct",
        }
        # Force a deterministic visitor_id by stubbing the helper
        with patch.object(analytics_mod, "generate_visitor_id", return_value=visitor_id):
            r = client.post("/api/website/track", json=payload)
        assert r.status_code == 200, r.text

    hot = [f for f in fired if f[0] == "hot_session"]
    assert len(hot) == 1, f"expected exactly one hot_session, got {fired}"
    assert hot[0][1] == session_id  # dedupe key
    assert "Hot session" in hot[0][2]
    assert "Products viewed:</b> 4" in hot[0][2]


@pytest.mark.asyncio
async def test_hot_session_skipped_when_under_three_pdps():
    from routes import analytics as analytics_mod

    now = datetime.now(timezone.utc)
    fake_pages = [
        {"page_url": "/shop/product/a", "timestamp": now - timedelta(minutes=3)},
        {"page_url": "/shop/product/b", "timestamp": now},
    ]
    fake_cursor = MagicMock()
    fake_cursor.to_list = AsyncMock(return_value=fake_pages)
    fake_db = MagicMock()
    fake_db.page_views.insert_one = AsyncMock()
    fake_db.page_views.find = MagicMock(return_value=fake_cursor)
    fake_db.analytics_daily.update_one = AsyncMock()
    fake_db.known_devices.find_one = AsyncMock(return_value=None)

    fired = []
    with patch.object(analytics_mod, "get_db", return_value=fake_db), \
         patch("services.telegram_notify.fire_and_forget", side_effect=lambda *a, **kw: fired.append(a)), \
         patch.object(analytics_mod, "broadcast_live_update", new=AsyncMock()), \
         patch.object(analytics_mod, "get_geo_location", new=AsyncMock(return_value={})):

        from fastapi.testclient import TestClient
        from server import app
        client = TestClient(app)
        with patch.object(analytics_mod, "generate_visitor_id", return_value="v"):
            r = client.post("/api/website/track", json={
                "session_id": "s2",
                "page_url": "/shop/product/b",
                "page_title": "B",
            })
        assert r.status_code == 200

    assert not [f for f in fired if f and f[0] == "hot_session"]


@pytest.mark.asyncio
async def test_hot_session_skipped_when_under_two_minutes():
    from routes import analytics as analytics_mod

    now = datetime.now(timezone.utc)
    fake_pages = [
        {"page_url": "/shop/product/a", "timestamp": now - timedelta(seconds=30)},
        {"page_url": "/shop/product/b", "timestamp": now - timedelta(seconds=20)},
        {"page_url": "/shop/product/c", "timestamp": now},
    ]
    fake_cursor = MagicMock()
    fake_cursor.to_list = AsyncMock(return_value=fake_pages)
    fake_db = MagicMock()
    fake_db.page_views.insert_one = AsyncMock()
    fake_db.page_views.find = MagicMock(return_value=fake_cursor)
    fake_db.analytics_daily.update_one = AsyncMock()
    fake_db.known_devices.find_one = AsyncMock(return_value=None)

    fired = []
    with patch.object(analytics_mod, "get_db", return_value=fake_db), \
         patch("services.telegram_notify.fire_and_forget", side_effect=lambda *a, **kw: fired.append(a)), \
         patch.object(analytics_mod, "broadcast_live_update", new=AsyncMock()), \
         patch.object(analytics_mod, "get_geo_location", new=AsyncMock(return_value={})):

        from fastapi.testclient import TestClient
        from server import app
        client = TestClient(app)
        with patch.object(analytics_mod, "generate_visitor_id", return_value="v"):
            r = client.post("/api/website/track", json={
                "session_id": "s3",
                "page_url": "/shop/product/c",
                "page_title": "C",
            })
        assert r.status_code == 200

    assert not [f for f in fired if f and f[0] == "hot_session"]


@pytest.mark.asyncio
async def test_hot_session_skipped_for_tagged_devices():
    from routes import analytics as analytics_mod

    now = datetime.now(timezone.utc)
    fake_pages = [
        {"page_url": "/shop/product/a", "timestamp": now - timedelta(minutes=4)},
        {"page_url": "/shop/product/b", "timestamp": now - timedelta(minutes=3)},
        {"page_url": "/shop/product/c", "timestamp": now - timedelta(minutes=1)},
        {"page_url": "/shop/product/d", "timestamp": now},
    ]
    fake_cursor = MagicMock()
    fake_cursor.to_list = AsyncMock(return_value=fake_pages)
    fake_db = MagicMock()
    fake_db.page_views.insert_one = AsyncMock()
    fake_db.page_views.find = MagicMock(return_value=fake_cursor)
    fake_db.analytics_daily.update_one = AsyncMock()
    # Tagged staff device
    fake_db.known_devices.find_one = AsyncMock(return_value={"visitor_id": "v", "exclude_from_stats": True})

    fired = []
    with patch.object(analytics_mod, "get_db", return_value=fake_db), \
         patch("services.telegram_notify.fire_and_forget", side_effect=lambda *a, **kw: fired.append(a)), \
         patch.object(analytics_mod, "broadcast_live_update", new=AsyncMock()), \
         patch.object(analytics_mod, "get_geo_location", new=AsyncMock(return_value={})):

        from fastapi.testclient import TestClient
        from server import app
        client = TestClient(app)
        with patch.object(analytics_mod, "generate_visitor_id", return_value="v"):
            r = client.post("/api/website/track", json={
                "session_id": "s4",
                "page_url": "/shop/product/d",
                "page_title": "D",
            })
        assert r.status_code == 200

    assert not [f for f in fired if f and f[0] == "hot_session"]

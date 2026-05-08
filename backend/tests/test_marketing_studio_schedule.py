"""Tests for marketing-studio scheduled auto-unpublish.

Covers:
  • Publishing with `auto_unpublish_at` stores the schedule on the
    promo_banner doc AND on the asset.
  • The auto_unpublish loop unpublishes banners whose scheduled_end
    has passed.
  • The asset's `published_to` is cleared when the loop fires.
  • The public storefront cache is invalidated so the banner is hidden
    immediately.
"""
import os
import asyncio
import uuid
import requests

BASE_URL = os.environ.get(
    "BACKEND_URL",
    "https://feature-verification-7.preview.emergentagent.com",
)


def _admin_headers():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "admin@test.com", "password": "admin123"},
        timeout=10,
    )
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json().get('access_token') or r.json().get('token')}"}


def _create_asset():
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
    from motor.motor_asyncio import AsyncIOMotorClient
    aid = str(uuid.uuid4())

    async def _ins():
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = cli[os.environ["DB_NAME"]]
        await db.marketing_assets.insert_one({
            "id": aid,
            "model": "nano-banana",
            "prompt": "PYTEST schedule test",
            "image_url": "https://example.com/test.png",
            "width": 1200, "height": 300,
            "cost_usd": 0.04, "deleted": False, "published_to": None,
            "created_at": "2026-05-03T00:00:00+00:00",
        })
        cli.close()
    asyncio.get_event_loop().run_until_complete(_ins())
    return aid


def _delete_asset(aid):
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
    from motor.motor_asyncio import AsyncIOMotorClient

    async def _drop():
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = cli[os.environ["DB_NAME"]]
        await db.marketing_assets.delete_one({"id": aid})
        cli.close()
    asyncio.get_event_loop().run_until_complete(_drop())


def test_publish_with_auto_unpublish_at_persists_schedule():
    h = _admin_headers()
    aid = _create_asset()
    try:
        # Publish with a far-future auto-unpublish time
        future = "2099-12-31T23:59:00+00:00"
        r = requests.post(
            f"{BASE_URL}/api/admin/marketing-studio/assets/{aid}/publish",
            json={"placement": "promo_banner", "auto_unpublish_at": future},
            headers=h, timeout=10,
        )
        assert r.status_code == 200, r.text
        assert r.json().get("auto_unpublish_at") == future

        # Verify the banner doc has the schedule fields
        from dotenv import load_dotenv
        load_dotenv("/app/backend/.env")
        from motor.motor_asyncio import AsyncIOMotorClient

        async def _check():
            cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
            db = cli[os.environ["DB_NAME"]]
            banner = await db.website_settings.find_one({"key": "promo_banner"}, {"_id": 0})
            asset = await db.marketing_assets.find_one({"id": aid}, {"_id": 0})
            cli.close()
            return banner, asset

        banner, asset = asyncio.get_event_loop().run_until_complete(_check())
        assert banner["schedule_enabled"] is True
        assert banner["scheduled_end"] == future
        assert banner["asset_id"] == aid  # bookkeeping link for auto-unpublish
        assert asset["auto_unpublish_at"] == future

        # Cleanup — unpublish so we don't leave a far-future schedule live
        requests.post(f"{BASE_URL}/api/admin/marketing-studio/assets/{aid}/unpublish",
                      headers=h, timeout=10)
    finally:
        _delete_asset(aid)


def test_auto_unpublish_loop_fires_when_schedule_elapsed():
    """End-to-end: publish with a PAST scheduled_end, then directly
    invoke `_run_one_pass` and assert the banner gets disabled and the
    asset's published_to is cleared."""
    h = _admin_headers()
    aid = _create_asset()
    try:
        past = "2020-01-01T00:00:00+00:00"
        r = requests.post(
            f"{BASE_URL}/api/admin/marketing-studio/assets/{aid}/publish",
            json={"placement": "promo_banner", "auto_unpublish_at": past},
            headers=h, timeout=10,
        )
        assert r.status_code == 200

        # Manually trigger one pass of the loop (rather than waiting 60s)
        from dotenv import load_dotenv
        load_dotenv("/app/backend/.env")
        from motor.motor_asyncio import AsyncIOMotorClient
        from services.auto_unpublish import _run_one_pass

        async def _trigger():
            cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
            db = cli[os.environ["DB_NAME"]]
            n = await _run_one_pass(db)
            banner = await db.website_settings.find_one({"key": "promo_banner"}, {"_id": 0})
            asset = await db.marketing_assets.find_one({"id": aid}, {"_id": 0})
            cli.close()
            return n, banner, asset

        n, banner, asset = asyncio.get_event_loop().run_until_complete(_trigger())
        assert n >= 1, "expected at least 1 placement to be auto-unpublished"
        assert banner["enabled"] is False, "banner.enabled must flip to False after schedule expiry"
        assert asset["published_to"] is None, "asset.published_to must be cleared after auto-unpublish"
        assert "auto_unpublished_at" in asset

        # Public endpoint should reflect the change immediately (cache busted)
        public = requests.get(f"{BASE_URL}/api/website/promo-banner", timeout=10).json()
        assert public.get("enabled") is False
    finally:
        _delete_asset(aid)


def test_publish_without_auto_unpublish_at_clears_old_schedule():
    """If admin re-publishes without a schedule, any leftover schedule
    from a previous publish should be cleared so the banner doesn't
    auto-end unexpectedly."""
    h = _admin_headers()
    aid = _create_asset()
    try:
        # Publish WITH a schedule
        future = "2099-12-31T23:59:00+00:00"
        requests.post(
            f"{BASE_URL}/api/admin/marketing-studio/assets/{aid}/publish",
            json={"placement": "promo_banner", "auto_unpublish_at": future},
            headers=h, timeout=10,
        )
        # Re-publish WITHOUT a schedule
        r = requests.post(
            f"{BASE_URL}/api/admin/marketing-studio/assets/{aid}/publish",
            json={"placement": "promo_banner"},
            headers=h, timeout=10,
        )
        assert r.status_code == 200
        assert r.json().get("auto_unpublish_at") in (None, "")

        from dotenv import load_dotenv
        load_dotenv("/app/backend/.env")
        from motor.motor_asyncio import AsyncIOMotorClient

        async def _check():
            cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
            db = cli[os.environ["DB_NAME"]]
            banner = await db.website_settings.find_one({"key": "promo_banner"}, {"_id": 0})
            cli.close()
            return banner
        banner = asyncio.get_event_loop().run_until_complete(_check())
        assert banner.get("schedule_enabled") in (False, None)
        assert banner.get("scheduled_end") in (None, "")

        # Cleanup
        requests.post(f"{BASE_URL}/api/admin/marketing-studio/assets/{aid}/unpublish",
                      headers=h, timeout=10)
    finally:
        _delete_asset(aid)

"""Tests for the May 3 2026 production hero-slides bug.

Root cause: Marketing Studio publish_to_homepage_hero wrote to
`page_content.homepage.content.hero_image`, but the storefront's
HeroBannerCarousel reads from the `hero_slides` collection. So a
published banner appeared on the live site but Delete/Unpublish in
Marketing Studio never removed the carousel slide.

After the fix:
  • Publishing to homepage_hero ALSO inserts/upserts a slide in
    `hero_slides` tagged with `source: "marketing_studio"` and
    `asset_id` for tracking.
  • Unpublish/Delete removes the matching slide (by asset_id, with
    image-URL fallback for legacy slides without asset_id).
  • New POST /admin/marketing-studio/cleanup-orphan-hero-slides
    cleans up legacy orphan slides whose linked asset is gone.
"""
import asyncio
import os
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
            "id": aid, "model": "nano-banana", "prompt": "PYTEST hero slide test",
            "image_url": f"https://example.com/{aid}.png",
            "width": 1600, "height": 600, "cost_usd": 0.04,
            "deleted": False, "published_to": None,
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
        await db.hero_slides.delete_many({"asset_id": aid})
        cli.close()
    asyncio.get_event_loop().run_until_complete(_drop())


def test_publish_to_homepage_hero_inserts_slide_into_hero_slides():
    """Regression: the May 3 production bug. Publish must write to the
    `hero_slides` collection that the storefront ACTUALLY reads from."""
    h = _admin_headers()
    aid = _create_asset()
    try:
        r = requests.post(
            f"{BASE_URL}/api/admin/marketing-studio/assets/{aid}/publish",
            json={"placement": "homepage_hero", "cta_text": "PYTEST Hero", "link_url": "/sale"},
            headers=h, timeout=10,
        )
        assert r.status_code == 200, r.text

        # The public storefront endpoint must now show a marketing_studio slide
        slides = requests.get(
            f"{BASE_URL}/api/website-admin/public/hero-slides", timeout=10,
        ).json()
        ms_slides = [s for s in slides if s.get("source") == "marketing_studio"
                     and s.get("asset_id") == aid]
        assert len(ms_slides) == 1, (
            "publish_to_homepage_hero must add a slide to hero_slides "
            f"(May 3 prod regression). Got: {[s for s in slides if s.get('asset_id')==aid]}"
        )
        slide = ms_slides[0]
        assert slide["link"] == "/sale"
        assert slide["image"].endswith(f"{aid}.png")
    finally:
        _delete_asset(aid)


def test_unpublish_removes_slide_from_hero_slides():
    h = _admin_headers()
    aid = _create_asset()
    try:
        # Publish then immediately unpublish
        requests.post(
            f"{BASE_URL}/api/admin/marketing-studio/assets/{aid}/publish",
            json={"placement": "homepage_hero"}, headers=h, timeout=10,
        )
        slides_before = requests.get(
            f"{BASE_URL}/api/website-admin/public/hero-slides", timeout=10,
        ).json()
        assert any(s.get("asset_id") == aid for s in slides_before), "precondition: slide must exist"

        r = requests.post(
            f"{BASE_URL}/api/admin/marketing-studio/assets/{aid}/unpublish",
            headers=h, timeout=10,
        )
        assert r.status_code == 200

        slides_after = requests.get(
            f"{BASE_URL}/api/website-admin/public/hero-slides", timeout=10,
        ).json()
        assert not any(s.get("asset_id") == aid for s in slides_after), (
            "Unpublish must remove the slide from hero_slides "
            "(otherwise carousel still shows it on the storefront)"
        )
    finally:
        _delete_asset(aid)


def test_delete_published_hero_asset_removes_slide():
    """The actual May 3 production scenario the user hit."""
    h = _admin_headers()
    aid = _create_asset()
    try:
        requests.post(
            f"{BASE_URL}/api/admin/marketing-studio/assets/{aid}/publish",
            json={"placement": "homepage_hero"}, headers=h, timeout=10,
        )
        # Sanity check
        slides = requests.get(f"{BASE_URL}/api/website-admin/public/hero-slides", timeout=10).json()
        assert any(s.get("asset_id") == aid for s in slides)

        # User clicks Delete
        r = requests.delete(
            f"{BASE_URL}/api/admin/marketing-studio/assets/{aid}", headers=h, timeout=10,
        )
        assert r.status_code == 200
        assert r.json().get("unpublished_from") == "homepage_hero"

        # Carousel must reflect the deletion
        slides = requests.get(f"{BASE_URL}/api/website-admin/public/hero-slides", timeout=10).json()
        assert not any(s.get("asset_id") == aid for s in slides), (
            "REGRESSION: deleting a published homepage_hero asset must remove "
            "its slide from the public carousel — exactly the May 3 bug."
        )
    finally:
        _delete_asset(aid)


def test_cleanup_orphan_hero_slides():
    """Inject an orphan marketing_studio slide whose asset is gone, then
    call the cleanup endpoint and verify it's removed."""
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
    from motor.motor_asyncio import AsyncIOMotorClient
    from datetime import datetime, timezone

    h = _admin_headers()
    orphan_id = f"pytest-orphan-{uuid.uuid4().hex[:8]}"

    async def _setup():
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = cli[os.environ["DB_NAME"]]
        await db.hero_slides.insert_one({
            "asset_id": orphan_id, "source": "marketing_studio",
            "image": f"https://example.com/{orphan_id}.png",
            "title": "PYTEST orphan", "cta": "Shop", "link": "/",
            "is_active": True, "display_order": 0,
            "created_at": datetime.now(timezone.utc),
        })
        cli.close()
    asyncio.get_event_loop().run_until_complete(_setup())

    try:
        r = requests.post(
            f"{BASE_URL}/api/admin/marketing-studio/cleanup-orphan-hero-slides",
            headers=h, timeout=15,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("removed_count", 0) >= 1
        # Confirm it's actually gone
        slides = requests.get(
            f"{BASE_URL}/api/website-admin/public/hero-slides", timeout=10,
        ).json()
        assert not any(s.get("asset_id") == orphan_id for s in slides)
    finally:
        async def _drop():
            cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
            db = cli[os.environ["DB_NAME"]]
            await db.hero_slides.delete_many({"asset_id": orphan_id})
            cli.close()
        asyncio.get_event_loop().run_until_complete(_drop())

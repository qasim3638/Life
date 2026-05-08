"""Tests for the Marketing Studio unpublish flow.

Covers the May 3 2026 production incident where deleting a published
asset did NOT remove the banner from the storefront. After the fix:

  • DELETE /api/admin/marketing-studio/assets/{id} now disables the
    placement (promo_banner.enabled=False or hero_image cleared).
  • POST .../assets/{id}/unpublish removes the placement WITHOUT
    deleting the asset (idempotent — was_published flag indicates
    whether anything changed).
  • Storefront cache is invalidated immediately so the change is
    visible within a few seconds, not minutes.
"""
import os
import time
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
    assert r.status_code == 200, r.text
    tok = r.json().get("access_token") or r.json().get("token")
    return {"Authorization": f"Bearer {tok}"}


def _create_test_asset(headers):
    """Insert a synthetic asset directly via Mongo so we don't burn
    real fal.ai bandwidth in CI. The test asset has a placeholder URL
    that never gets rendered to a customer (we only need the asset to
    exist for the publish→unpublish round-trip)."""
    import asyncio, os
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
    from motor.motor_asyncio import AsyncIOMotorClient
    aid = str(uuid.uuid4())

    async def _insert():
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = cli[os.environ["DB_NAME"]]
        await db.marketing_assets.insert_one({
            "id": aid,
            "model": "nano-banana",
            "prompt": "PYTEST throwaway asset",
            "image_url": "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=400&q=60",
            "width": 1200, "height": 300,
            "cost_usd": 0.04,
            "deleted": False,
            "published_to": None,
            "created_at": "2026-05-03T00:00:00+00:00",
        })
        cli.close()

    asyncio.get_event_loop().run_until_complete(_insert())
    return aid


def _delete_test_asset(aid):
    import asyncio, os
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
    from motor.motor_asyncio import AsyncIOMotorClient

    async def _drop():
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = cli[os.environ["DB_NAME"]]
        await db.marketing_assets.delete_one({"id": aid})
        cli.close()

    asyncio.get_event_loop().run_until_complete(_drop())


def test_publish_then_unpublish_disables_promo_banner():
    h = _admin_headers()
    aid = _create_test_asset(h)
    try:
        # Publish to promo_banner
        r = requests.post(
            f"{BASE_URL}/api/admin/marketing-studio/assets/{aid}/publish",
            json={"placement": "promo_banner", "link_url": "/sale"},
            headers=h, timeout=10,
        )
        assert r.status_code == 200, r.text

        # Public endpoint should now show enabled=True (cache invalidated)
        time.sleep(0.5)
        public = requests.get(f"{BASE_URL}/api/website/promo-banner", timeout=10).json()
        assert public.get("enabled") is True, f"after publish, public said: {public}"

        # Unpublish
        r = requests.post(
            f"{BASE_URL}/api/admin/marketing-studio/assets/{aid}/unpublish",
            headers=h, timeout=10,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("was_published") is True
        assert body.get("placement") == "promo_banner"

        # Public endpoint should now show enabled=False (cache busted again)
        time.sleep(0.5)
        public = requests.get(f"{BASE_URL}/api/website/promo-banner", timeout=10).json()
        assert public.get("enabled") is False, f"after unpublish, public said: {public}"
    finally:
        _delete_test_asset(aid)


def test_unpublish_idempotent_when_nothing_published():
    h = _admin_headers()
    aid = _create_test_asset(h)  # never publish it
    try:
        r = requests.post(
            f"{BASE_URL}/api/admin/marketing-studio/assets/{aid}/unpublish",
            headers=h, timeout=10,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is True
        assert body.get("was_published") is False
    finally:
        _delete_test_asset(aid)


def test_delete_published_asset_also_unpublishes():
    """The May 3 2026 user-reported bug — admin clicks Delete on the
    published banner card; the asset disappears from the gallery but
    the banner stays live on the storefront. Now Delete should also
    unpublish."""
    h = _admin_headers()
    aid = _create_test_asset(h)
    try:
        # Publish to promo_banner
        requests.post(
            f"{BASE_URL}/api/admin/marketing-studio/assets/{aid}/publish",
            json={"placement": "promo_banner"},
            headers=h, timeout=10,
        )
        time.sleep(0.3)
        public = requests.get(f"{BASE_URL}/api/website/promo-banner", timeout=10).json()
        assert public.get("enabled") is True, "precondition: banner should be live before delete"

        # Delete
        r = requests.delete(
            f"{BASE_URL}/api/admin/marketing-studio/assets/{aid}",
            headers=h, timeout=10,
        )
        assert r.status_code == 200, r.text
        assert r.json().get("unpublished_from") == "promo_banner"

        # Public should now show banner OFF — this is the regression check
        time.sleep(0.5)
        public = requests.get(f"{BASE_URL}/api/website/promo-banner", timeout=10).json()
        assert public.get("enabled") is False, (
            "REGRESSION: deleting a published asset must also disable the "
            f"public banner (got {public})"
        )
    finally:
        _delete_test_asset(aid)

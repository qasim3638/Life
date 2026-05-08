"""Live tests against public endpoint for schedule unpublish (iter 163)."""
import os
import requests
import pytest
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Load backend .env so MONGO_URL/DB_NAME match runtime
load_dotenv('/app/backend/.env')

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://feature-verification-7.preview.emergentagent.com').rstrip('/')
MONGO_URL = os.environ['MONGO_URL']
DB_NAME = os.environ['DB_NAME']


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": "admin@test.com", "password": "admin123"}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


def _list_assets(headers):
    r = requests.get(f"{BASE_URL}/api/admin/marketing-studio/assets", headers=headers, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    return data if isinstance(data, list) else data.get("assets", [])


def _get_test_asset(headers):
    """Return a non-deleted TEST_ seeded asset; seed one if missing."""
    assets = _list_assets(headers)
    test = [a for a in assets if (a.get("id") or "").startswith("test-iter163-")]
    if test:
        return test[0]
    # seed via Mongo
    from pymongo import MongoClient
    import uuid as _uuid
    from datetime import datetime as _dt, timezone as _tz
    c = MongoClient(MONGO_URL)
    db_s = c[DB_NAME]
    aid = "test-iter163-" + _uuid.uuid4().hex[:8]
    db_s.marketing_assets.insert_one({
        "id": aid, "asset_kind": "banner", "model": "nano-banana",
        "prompt": "TEST iter163", "width": 1920, "height": 480,
        "storage_path": f"x/{aid}.png", "public_url": f"/api/website/marketing-media/{aid}.png",
        "image_url": f"/api/website/marketing-media/{aid}.png",
        "size_bytes": 100, "content_type": "image/png", "cost_cents": 0,
        "created_by": "admin@test.com", "created_at": _dt.now(_tz.utc),
        "deleted": False, "published_to": None, "auto_unpublish_at": None,
    })
    c.close()
    return {"id": aid}


def test_publish_with_auto_unpublish_persists_schedule(headers):
    asset = _get_test_asset(headers)
    asset_id = asset.get("id") or asset.get("_id")

    iso_future = "2099-12-31T23:59:00+00:00"
    payload = {"placement": "promo_banner", "auto_unpublish_at": iso_future}
    r = requests.post(f"{BASE_URL}/api/admin/marketing-studio/assets/{asset_id}/publish",
                      json=payload, headers=headers, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    aup = body.get("auto_unpublish_at") or (body.get("asset") or {}).get("auto_unpublish_at")
    assert aup is not None, f"auto_unpublish_at missing in response: {body}"

    async def _check():
        client = AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]
        ws = await db.website_settings.find_one({"key": "promo_banner"})
        assert ws is not None, "promo_banner doc missing"
        assert ws.get("schedule_enabled") is True, f"schedule_enabled not true: {ws}"
        assert ws.get("scheduled_end") is not None
        assert ws.get("asset_id") == asset_id, f"asset_id mismatch: {ws.get('asset_id')} vs {asset_id}"
        ma = await db.marketing_assets.find_one({"id": asset_id})
        assert ma is not None, "marketing asset doc missing"
        assert ma.get("auto_unpublish_at") is not None, f"asset.auto_unpublish_at missing: {ma}"
        client.close()
    asyncio.get_event_loop().run_until_complete(_check())


def test_get_promo_banner_public_endpoint():
    r = requests.get(f"{BASE_URL}/api/website/promo-banner", timeout=30)
    assert r.status_code == 200, r.text


def test_unpublish_clears_auto_unpublish(headers):
    # Publish a seeded asset with schedule first
    asset = _get_test_asset(headers)
    asset_id = asset.get("id") or asset.get("_id")
    requests.post(f"{BASE_URL}/api/admin/marketing-studio/assets/{asset_id}/publish",
                  json={"placement": "promo_banner", "auto_unpublish_at": "2099-12-31T23:59:00+00:00"},
                  headers=headers, timeout=30)
    r = requests.post(f"{BASE_URL}/api/admin/marketing-studio/assets/{asset_id}/unpublish",
                      headers=headers, timeout=30)
    assert r.status_code == 200, r.text

    async def _check():
        client = AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]
        ma = await db.marketing_assets.find_one({"id": asset_id})
        assert ma.get("published_to") in (None, "")
        assert ma.get("auto_unpublish_at") in (None, "")
        client.close()
    asyncio.get_event_loop().run_until_complete(_check())


def test_publish_without_schedule_clears_previous(headers):
    asset = _get_test_asset(headers)
    asset_id = asset.get("id") or asset.get("_id")
    # First publish with schedule
    requests.post(f"{BASE_URL}/api/admin/marketing-studio/assets/{asset_id}/publish",
                  json={"placement": "promo_banner", "auto_unpublish_at": "2099-12-31T23:59:00+00:00"},
                  headers=headers, timeout=30)
    # Re-publish without schedule
    r = requests.post(f"{BASE_URL}/api/admin/marketing-studio/assets/{asset_id}/publish",
                      json={"placement": "promo_banner"}, headers=headers, timeout=30)
    assert r.status_code == 200, r.text

    async def _check():
        client = AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]
        ws = await db.website_settings.find_one({"key": "promo_banner"})
        assert not ws.get("schedule_enabled") or ws.get("scheduled_end") in (None, ""), f"schedule not cleared: {ws}"
        ma = await db.marketing_assets.find_one({"id": asset_id})
        assert ma.get("auto_unpublish_at") in (None, ""), f"asset.auto_unpublish_at not cleared: {ma}"
        client.close()
    asyncio.get_event_loop().run_until_complete(_check())

    # Cleanup: unpublish
    requests.post(f"{BASE_URL}/api/admin/marketing-studio/assets/{asset_id}/unpublish",
                  headers=headers, timeout=30)


def test_auto_unpublish_loop_fires_on_elapsed(headers):
    """Set scheduled_end in the past, invoke _run_one_pass, verify flip."""
    asset = _get_test_asset(headers)
    asset_id = asset.get("id") or asset.get("_id")
    # Publish with future, then overwrite DB to be in the past
    requests.post(f"{BASE_URL}/api/admin/marketing-studio/assets/{asset_id}/publish",
                  json={"placement": "promo_banner", "auto_unpublish_at": "2099-12-31T23:59:00+00:00"},
                  headers=headers, timeout=30)

    from pymongo import MongoClient
    c = MongoClient(MONGO_URL)
    db = c[DB_NAME]
    db.website_settings.update_one({"key": "promo_banner"},
                                   {"$set": {"scheduled_end": "2020-01-01T00:00:00+00:00",
                                             "schedule_enabled": True, "enabled": True,
                                             "asset_id": asset_id}})
    c.close()

    # Invoke the loop one pass - import directly to bypass services/__init__
    import importlib.util
    spec = importlib.util.spec_from_file_location("auto_unpublish_mod", "/app/backend/services/auto_unpublish.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _run_one_pass = mod._run_one_pass
    from motor.motor_asyncio import AsyncIOMotorClient as _Motor

    async def _invoke():
        mc = _Motor(MONGO_URL)
        mdb = mc[DB_NAME]
        flipped = await _run_one_pass(mdb)
        mc.close()
        return flipped
    flipped = asyncio.get_event_loop().run_until_complete(_invoke())
    assert flipped >= 1, f"Expected >=1 flip, got {flipped}"

    # Verify website_settings + asset updates
    c = MongoClient(MONGO_URL)
    db = c[DB_NAME]
    ws = db.website_settings.find_one({"key": "promo_banner"})
    assert ws.get("enabled") is False, f"promo_banner.enabled not flipped: {ws}"
    ma = db.marketing_assets.find_one({"id": asset_id})
    assert ma.get("published_to") in (None, ""), f"asset.published_to not cleared: {ma}"
    c.close()

    # Public endpoint reflects disabled
    pub = requests.get(f"{BASE_URL}/api/website/promo-banner", timeout=30)
    assert pub.status_code == 200
    body = pub.json()
    assert body.get("enabled") in (False, None, ""), f"public promo-banner still enabled: {body}"


def test_cleanup_seed_assets():
    """Remove TEST_ seeded assets."""
    from pymongo import MongoClient
    c = MongoClient(MONGO_URL)
    db = c[DB_NAME]
    res = db.marketing_assets.delete_many({"id": {"$regex": "^test-iter163-"}})
    print(f"Deleted {res.deleted_count} seed assets")
    c.close()

"""Tests for the regenerate-with-safe-zone flow."""
import os
import sys
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402


@pytest_asyncio.fixture
async def db(monkeypatch):
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    test_db = client[f"test_regen_{uuid.uuid4().hex[:8]}"]
    # Monkey-patch the get_db used by the route module
    from routes import marketing_studio as ms_mod
    monkeypatch.setattr(ms_mod, "get_db", lambda: test_db)
    yield test_db
    await client.drop_database(test_db.name)
    client.close()


def _fake_generation_result(prompt="user prompt"):
    """Mock what services.marketing_studio.generate_banner_image returns."""
    return {
        "png_bytes": b"\x89PNG\r\n\x1a\nfake-new-bytes",
        "model": "nano-banana",
        "width": 1920,
        "height": 640,
        "cost_usd": 0.04,
        "prompt": f"{prompt} SAFE ZONE RULES ...",
    }


@pytest.mark.asyncio
async def test_regenerate_creates_new_asset_and_supersedes_old(db):
    """Happy path: non-published asset → new asset created, old asset
    gets `superseded_by` back-reference, new asset gets `replaces_asset_id`."""
    # Seed an old asset
    old_id = "old1"
    await db.marketing_assets.insert_one({
        "id": old_id,
        "prompt": "BANK HOLIDAY SALE — up to 70% off",
        "model": "nano-banana",
        "width": 1920, "height": 640,
        "asset_kind": "banner",
        "preset": "hero",
        "image_url": "/api/website/marketing-media/old1.png",
        "storage_path": "tile-station/marketing/old1.png",
        "cost_usd": 0.04,
        "deleted": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    from routes.marketing_studio import regenerate_asset

    with patch("services.marketing_studio.generate_banner_image",
               new=AsyncMock(return_value=_fake_generation_result())), \
         patch("services.object_storage.put_object", new=MagicMock(return_value={"ok": True})):
        res = await regenerate_asset(old_id, {"role": "admin", "email": "king@x"})

    assert res["ok"] is True
    assert res["swapped"] is False  # old wasn't published
    assert res["placement"] is None
    assert res["new"]["replaces_asset_id"] == old_id
    assert res["new"]["regenerated_with"] == "safe_zone_v1"
    assert res["old"]["superseded_by"] == res["new"]["id"]

    # Both docs should exist; gallery default filter should now hide
    # the old one.
    rows_default = await db.marketing_assets.find(
        {"$or": [{"superseded_by": {"$exists": False}}, {"superseded_by": None}]}
    ).to_list(length=None)
    assert len(rows_default) == 1
    assert rows_default[0]["id"] == res["new"]["id"]


@pytest.mark.asyncio
async def test_regenerate_inherits_hero_placement(db):
    """If the old asset was live as homepage_hero, the new asset
    auto-takes over — storefront hot-swaps with zero extra clicks."""
    old_id = "old-hero"
    await db.marketing_assets.insert_one({
        "id": old_id,
        "prompt": "Summer collection lifestyle",
        "model": "nano-banana",
        "width": 1920, "height": 640,
        "asset_kind": "banner",
        "image_url": "/api/website/marketing-media/old-hero.png",
        "cost_usd": 0.04,
        "deleted": False,
        "published_to": "homepage_hero",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    # Seed a matching hero_slides row and page_content
    await db.hero_slides.insert_one({
        "asset_id": old_id,
        "source": "marketing_studio",
        "image": "/api/website/marketing-media/old-hero.png",
        "is_active": True,
    })
    await db.page_content.insert_one({
        "page_key": "homepage",
        "content": {"hero_image": "/api/website/marketing-media/old-hero.png", "hero_asset_id": old_id},
    })

    from routes.marketing_studio import regenerate_asset

    with patch("services.marketing_studio.generate_banner_image",
               new=AsyncMock(return_value=_fake_generation_result())), \
         patch("services.object_storage.put_object", new=MagicMock(return_value={"ok": True})):
        res = await regenerate_asset(old_id, {"role": "admin", "email": "king@x"})

    assert res["swapped"] is True
    assert res["placement"] == "homepage_hero"
    new_id = res["new"]["id"]

    # hero_slides row has been updated to point at the NEW asset
    slide = await db.hero_slides.find_one({"asset_id": new_id})
    assert slide is not None
    assert slide["image"] == res["new"]["image_url"]

    # page_content's hero_image points to the new URL
    page = await db.page_content.find_one({"page_key": "homepage"})
    assert page["content"]["hero_image"] == res["new"]["image_url"]
    assert page["content"]["hero_asset_id"] == new_id

    # New asset carries the placement; old asset's placement is cleared
    new_doc = await db.marketing_assets.find_one({"id": new_id})
    assert new_doc["published_to"] == "homepage_hero"
    old_doc = await db.marketing_assets.find_one({"id": old_id})
    assert old_doc.get("published_to") in (None, "")


@pytest.mark.asyncio
async def test_regenerate_inherits_promo_banner_placement(db):
    """If the old asset was live as the promo_banner, the new asset
    is swapped into `website_settings.promo_banner`."""
    old_id = "old-promo"
    await db.marketing_assets.insert_one({
        "id": old_id,
        "prompt": "10% off all orders this weekend",
        "model": "nano-banana",
        "width": 1200, "height": 120,
        "asset_kind": "banner",
        "image_url": "/api/website/marketing-media/old-promo.png",
        "cost_usd": 0.04,
        "deleted": False,
        "published_to": "promo_banner",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.website_settings.insert_one({
        "key": "promo_banner",
        "enabled": True,
        "image_url": "/api/website/marketing-media/old-promo.png",
        "asset_id": old_id,
    })

    from routes.marketing_studio import regenerate_asset

    with patch("services.marketing_studio.generate_banner_image",
               new=AsyncMock(return_value=_fake_generation_result())), \
         patch("services.object_storage.put_object", new=MagicMock(return_value={"ok": True})):
        res = await regenerate_asset(old_id, {"role": "admin", "email": "king@x"})

    assert res["swapped"] is True
    assert res["placement"] == "promo_banner"
    promo = await db.website_settings.find_one({"key": "promo_banner"})
    assert promo["image_url"] == res["new"]["image_url"]
    assert promo["asset_id"] == res["new"]["id"]


@pytest.mark.asyncio
async def test_regenerate_rejects_already_superseded(db):
    """Double-regenerate protection — UI should stop the user from
    creating a chain of supersedes accidentally."""
    old_id = "already-done"
    await db.marketing_assets.insert_one({
        "id": old_id,
        "prompt": "test",
        "model": "nano-banana",
        "width": 1920, "height": 640,
        "asset_kind": "banner",
        "image_url": "",
        "deleted": False,
        "superseded_by": "new-xyz",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    from routes.marketing_studio import regenerate_asset
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        await regenerate_asset(old_id, {"role": "admin", "email": "x"})
    assert exc.value.status_code == 400
    assert "already been regenerated" in exc.value.detail


@pytest.mark.asyncio
async def test_regenerate_404_for_missing_asset(db):
    from routes.marketing_studio import regenerate_asset
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        await regenerate_asset("no-such-id", {"role": "admin", "email": "x"})
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_regenerate_rejects_when_prompt_missing(db):
    """Guard against regenerating very-old assets that lacked prompts."""
    old_id = "no-prompt"
    await db.marketing_assets.insert_one({
        "id": old_id,
        "model": "nano-banana",
        "width": 1920, "height": 640,
        "asset_kind": "banner",
        "image_url": "",
        "deleted": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    from routes.marketing_studio import regenerate_asset
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        await regenerate_asset(old_id, {"role": "admin", "email": "x"})
    assert exc.value.status_code == 400
    assert "prompt" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_list_assets_hides_superseded_by_default(db):
    """The default gallery filter must hide assets flagged
    `superseded_by`, but `?include_superseded=true` opts in."""
    await db.marketing_assets.insert_many([
        {"id": "a1", "deleted": False, "asset_kind": "banner", "created_at": "2026-01-01"},
        {"id": "a2", "deleted": False, "asset_kind": "banner", "superseded_by": "a3", "created_at": "2026-01-01"},
        {"id": "a3", "deleted": False, "asset_kind": "banner", "replaces_asset_id": "a2", "created_at": "2026-01-02"},
    ])

    from routes.marketing_studio import list_assets
    default = await list_assets(current_user={"role": "admin", "email": "x"})
    ids = sorted(r["id"] for r in default["assets"])
    assert ids == ["a1", "a3"], f"superseded row leaked — got {ids}"

    full = await list_assets(include_superseded=True, current_user={"role": "admin", "email": "x"})
    ids_full = sorted(r["id"] for r in full["assets"])
    assert ids_full == ["a1", "a2", "a3"]

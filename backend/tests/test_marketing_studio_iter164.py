"""Iter-164 tests for the new BANK HOLIDAY banner cleanup primitives.

Three new pieces of functionality in this iteration:

1. POST /api/admin/marketing-studio/delete-hero-slide-by-text
   Surgical delete: any slide whose title/badge/subtitle contains
   the match text (case-insensitive). Returns removed_count + list.
   Rejects match shorter than 3 chars with 400.

2. POST /api/admin/marketing-studio/cleanup-orphan-hero-slides?aggressive=true
   Accepts the new ?aggressive=true query param. In aggressive mode,
   also removes untagged slides whose image URL matches any
   marketing_assets doc (even still-published) — used during the
   May 3 production cleanup when the deleted asset was hard-removed.

3. _orphan_slides_cleanup_kickstart background task (server.py)
   Fires 20s after every backend boot; scans hero_slides and auto-
   removes orphans so legacy BANK HOLIDAY-style slides self-heal
   without admin action.
"""
import asyncio
import os
import uuid

import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get(
    "BACKEND_URL",
    "https://feature-verification-7.preview.emergentagent.com",
).rstrip("/")


# ---------- helpers ----------
def _admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "admin@test.com", "password": "admin123"},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    return data.get("access_token") or data.get("token")


def _hdrs():
    return {"Authorization": f"Bearer {_admin_token()}"}


async def _db():
    from motor.motor_asyncio import AsyncIOMotorClient
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return cli, cli[os.environ["DB_NAME"]]


async def _insert_slide(doc):
    cli, db = await _db()
    try:
        await db.hero_slides.insert_one(doc)
    finally:
        cli.close()


async def _remove_slides(q):
    cli, db = await _db()
    try:
        await db.hero_slides.delete_many(q)
    finally:
        cli.close()


async def _count_slides(q):
    cli, db = await _db()
    try:
        return await db.hero_slides.count_documents(q)
    finally:
        cli.close()


async def _insert_marketing_asset(doc):
    cli, db = await _db()
    try:
        await db.marketing_assets.insert_one(doc)
    finally:
        cli.close()


async def _remove_marketing_asset(aid):
    cli, db = await _db()
    try:
        await db.marketing_assets.delete_one({"id": aid})
    finally:
        cli.close()


# ---------- 1. delete-hero-slide-by-text ----------
class TestDeleteHeroSlideByText:
    """Admin surgical-delete endpoint."""

    def test_requires_auth(self):
        r = requests.post(
            f"{BASE_URL}/api/admin/marketing-studio/delete-hero-slide-by-text",
            json={"match": "BANK HOLIDAY"}, timeout=10,
        )
        assert r.status_code in (401, 403), r.status_code

    def test_rejects_short_match(self):
        r = requests.post(
            f"{BASE_URL}/api/admin/marketing-studio/delete-hero-slide-by-text",
            json={"match": "AB"}, headers=_hdrs(), timeout=10,
        )
        assert r.status_code == 400
        assert "3" in (r.json().get("detail") or "")

    def test_rejects_empty_match(self):
        r = requests.post(
            f"{BASE_URL}/api/admin/marketing-studio/delete-hero-slide-by-text",
            json={"match": "   "}, headers=_hdrs(), timeout=10,
        )
        assert r.status_code == 400

    def test_case_insensitive_title_match(self):
        marker = f"PYTEST-ITER164-{uuid.uuid4().hex[:6]}"
        title = f"DeleteMe {marker}"  # mixed case stored
        slide = {
            "id": str(uuid.uuid4()),
            "title": title, "subtitle": "",
            "badge": "", "image": f"https://ex.com/{marker}.png",
            "is_active": True, "sort_order": 99,
        }
        asyncio.get_event_loop().run_until_complete(_insert_slide(slide))
        try:
            # search in lower case — should still match
            r = requests.post(
                f"{BASE_URL}/api/admin/marketing-studio/delete-hero-slide-by-text",
                json={"match": marker.lower()},
                headers=_hdrs(), timeout=10,
            )
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["ok"] is True
            assert data["removed_count"] >= 1
            titles = [x.get("title", "") for x in data["removed"]]
            assert any(marker in t for t in titles)
            # verify gone from DB
            remaining = asyncio.get_event_loop().run_until_complete(
                _count_slides({"title": title})
            )
            assert remaining == 0
        finally:
            asyncio.get_event_loop().run_until_complete(
                _remove_slides({"title": title})
            )

    def test_badge_match(self):
        marker = f"PYTESTBADGE{uuid.uuid4().hex[:6]}"
        slide = {
            "id": str(uuid.uuid4()),
            "title": "innocent-title", "subtitle": "",
            "badge": f"SALE {marker}", "image": f"https://ex.com/b{marker}.png",
            "is_active": True, "sort_order": 88,
        }
        asyncio.get_event_loop().run_until_complete(_insert_slide(slide))
        try:
            r = requests.post(
                f"{BASE_URL}/api/admin/marketing-studio/delete-hero-slide-by-text",
                json={"match": marker},
                headers=_hdrs(), timeout=10,
            )
            assert r.status_code == 200
            data = r.json()
            assert data["removed_count"] >= 1
            remaining = asyncio.get_event_loop().run_until_complete(
                _count_slides({"badge": f"SALE {marker}"})
            )
            assert remaining == 0
        finally:
            asyncio.get_event_loop().run_until_complete(
                _remove_slides({"badge": f"SALE {marker}"})
            )

    def test_no_match_returns_empty(self):
        r = requests.post(
            f"{BASE_URL}/api/admin/marketing-studio/delete-hero-slide-by-text",
            json={"match": f"NOPE-{uuid.uuid4().hex}"},
            headers=_hdrs(), timeout=10,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["removed_count"] == 0
        assert data["removed"] == []


# ---------- 2. cleanup-orphan-hero-slides?aggressive=true ----------
class TestCleanupOrphansAggressive:
    def test_default_mode_still_works(self):
        r = requests.post(
            f"{BASE_URL}/api/admin/marketing-studio/cleanup-orphan-hero-slides",
            headers=_hdrs(), timeout=15,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert "removed_count" in data
        assert isinstance(data["removed"], list)

    def test_aggressive_mode_accepted(self):
        r = requests.post(
            f"{BASE_URL}/api/admin/marketing-studio/cleanup-orphan-hero-slides?aggressive=true",
            headers=_hdrs(), timeout=15,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert isinstance(data["removed"], list)

    def test_aggressive_removes_image_match_even_if_published(self):
        """Aggressive mode should match untagged slides by image URL
        even when the matching asset is still published (Strategy 3)."""
        aid = str(uuid.uuid4())
        img = f"https://ex.com/aggr-{aid}.png"
        asyncio.get_event_loop().run_until_complete(_insert_marketing_asset({
            "id": aid, "model": "nano-banana", "prompt": "PYTEST aggressive",
            "image_url": img, "width": 1600, "height": 600, "cost_usd": 0.04,
            "deleted": False, "published_to": "promo_banner",  # still published
            "created_at": "2026-05-03T00:00:00+00:00",
        }))
        slide = {
            "id": str(uuid.uuid4()),
            "title": "AggressiveOrphan", "subtitle": "", "badge": "",
            "image": img, "is_active": True, "sort_order": 77,
            # intentionally NO source/asset_id — untagged legacy slide
        }
        asyncio.get_event_loop().run_until_complete(_insert_slide(slide))
        try:
            # non-aggressive should NOT remove it (asset is published, not deleted)
            r1 = requests.post(
                f"{BASE_URL}/api/admin/marketing-studio/cleanup-orphan-hero-slides",
                headers=_hdrs(), timeout=15,
            )
            assert r1.status_code == 200
            still_there = asyncio.get_event_loop().run_until_complete(
                _count_slides({"image": img})
            )
            assert still_there == 1, "non-aggressive should leave published asset's slide alone"

            # aggressive should remove it
            r2 = requests.post(
                f"{BASE_URL}/api/admin/marketing-studio/cleanup-orphan-hero-slides?aggressive=true",
                headers=_hdrs(), timeout=15,
            )
            assert r2.status_code == 200
            data = r2.json()
            gone = asyncio.get_event_loop().run_until_complete(
                _count_slides({"image": img})
            )
            assert gone == 0, f"aggressive should have removed slide, data={data}"
        finally:
            asyncio.get_event_loop().run_until_complete(_remove_slides({"image": img}))
            asyncio.get_event_loop().run_until_complete(_remove_marketing_asset(aid))

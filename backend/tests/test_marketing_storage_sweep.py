"""Tests for the Marketing Studio orphan storage sweep.

Each safety rail gets its own test — if any future refactor breaks
one, CI flags it immediately. This is critical because the sweep
soft-deletes production assets; a regression could silently torch
live banners.
"""
import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest


# -- helpers -----------------------------------------------------------------

def _cli_and_db():
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
    from motor.motor_asyncio import AsyncIOMotorClient
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return cli, cli[os.environ["DB_NAME"]]


def _insert_asset(**overrides):
    """Insert a throwaway marketing_asset with sensible defaults. Returns id."""
    async def _ins():
        cli, db = _cli_and_db()
        aid = overrides.pop("id", None) or str(uuid.uuid4())
        doc = {
            "id": aid,
            "model": "nano-banana",
            "prompt": "PYTEST orphan-sweep asset",
            "image_url": f"/api/website/marketing-media/{aid}.png",  # will 404 — no real file
            "width": 1600, "height": 600,
            "cost_usd": 0.04,
            "deleted": False,
            "published_to": None,
            "created_at": datetime.now(timezone.utc) - timedelta(days=7),  # old enough
        }
        doc.update(overrides)
        await db.marketing_assets.insert_one(doc)
        cli.close()
        return aid
    return asyncio.get_event_loop().run_until_complete(_ins())


def _cleanup(ids):
    async def _drop():
        cli, db = _cli_and_db()
        await db.marketing_assets.delete_many({"id": {"$in": ids}})
        await db.marketing_assets_orphan_log.delete_many({"asset_id": {"$in": ids}})
        await db.hero_slides.delete_many({"asset_id": {"$in": ids}})
        cli.close()
    asyncio.get_event_loop().run_until_complete(_drop())


def _probe():
    from services.marketing_storage_sweep import probe_assets

    async def _go():
        cli, db = _cli_and_db()
        try:
            return await probe_assets(db)
        finally:
            cli.close()
    return asyncio.get_event_loop().run_until_complete(_go())


def _mark(probe):
    from services.marketing_storage_sweep import mark_orphans

    async def _go():
        cli, db = _cli_and_db()
        try:
            return await mark_orphans(db, probe)
        finally:
            cli.close()
    return asyncio.get_event_loop().run_until_complete(_go())


def _get_asset(aid):
    async def _go():
        cli, db = _cli_and_db()
        try:
            return await db.marketing_assets.find_one({"id": aid}, {"_id": 0})
        finally:
            cli.close()
    return asyncio.get_event_loop().run_until_complete(_go())


# -- Rail 1: never hard-delete ---------------------------------------------

def test_rail1_never_hard_deletes():
    """Even a fully-eligible orphan must remain in Mongo after the sweep —
    just with `deleted: true`. No `delete_one` call anywhere in the sweep."""
    aid = _insert_asset(
        probe_first_404_at=datetime.now(timezone.utc) - timedelta(hours=72),
    )
    try:
        probe = _probe()
        _mark(probe)
        doc = _get_asset(aid)
        assert doc is not None, "asset must still exist in Mongo (soft-delete only)"
        if doc.get("deleted"):
            assert doc.get("deleted_reason", "").startswith("r2_blob_404_")
    finally:
        _cleanup([aid])


# -- Rail 2: skip published assets -----------------------------------------

def test_rail2_skip_published_assets():
    aid = _insert_asset(
        published_to="promo_banner",
        probe_first_404_at=datetime.now(timezone.utc) - timedelta(hours=72),
    )
    try:
        probe = _probe()
        row = next((r for r in probe if r["id"] == aid), None)
        assert row is not None
        assert row["would_mark"] is False, "published asset must NEVER be marked"
        assert "published" in (row.get("skip_reason") or "").lower()
    finally:
        _cleanup([aid])


# -- Rail 3: skip assets linked to hero_slides ------------------------------

def test_rail3_skip_hero_slide_linked_assets():
    aid = _insert_asset(
        probe_first_404_at=datetime.now(timezone.utc) - timedelta(hours=72),
    )
    # Create a hero_slide pointing at this asset
    async def _link():
        cli, db = _cli_and_db()
        await db.hero_slides.insert_one({
            "asset_id": aid, "image": f"/api/website/marketing-media/{aid}.png",
            "title": "PYTEST linked slide", "is_active": True,
            "created_at": datetime.now(timezone.utc),
        })
        cli.close()
    asyncio.get_event_loop().run_until_complete(_link())
    try:
        probe = _probe()
        row = next((r for r in probe if r["id"] == aid), None)
        assert row is not None
        assert row["would_mark"] is False, "hero-slide-linked asset must NEVER be marked"
        assert "hero_slides" in (row.get("skip_reason") or "")
    finally:
        _cleanup([aid])


# -- Rail 4: 48h cooling period --------------------------------------------

def test_rail4_requires_48h_cooling_before_marking():
    # Seen 404 only 12h ago — still within cooling period
    aid = _insert_asset(
        probe_first_404_at=datetime.now(timezone.utc) - timedelta(hours=12),
    )
    try:
        probe = _probe()
        row = next((r for r in probe if r["id"] == aid), None)
        assert row is not None
        assert row["would_mark"] is False, "sub-48h 404 must NOT be marked"
        assert "48h" in (row.get("skip_reason") or "") or "cooling" in (row.get("skip_reason") or "").lower()
    finally:
        _cleanup([aid])


def test_rail4_allows_marking_after_48h():
    aid = _insert_asset(
        probe_first_404_at=datetime.now(timezone.utc) - timedelta(hours=72),
    )
    try:
        probe = _probe()
        row = next((r for r in probe if r["id"] == aid), None)
        assert row is not None
        assert row["would_mark"] is True, "72h 404 with all other rails passing should be marked"
    finally:
        _cleanup([aid])


# -- Rail 5: skip recent creates --------------------------------------------

def test_rail5_skip_recent_creates():
    # Recently created (1h ago) — may still be uploading
    aid = _insert_asset(
        created_at=datetime.now(timezone.utc) - timedelta(hours=1),
        probe_first_404_at=datetime.now(timezone.utc) - timedelta(hours=72),
    )
    try:
        probe = _probe()
        row = next((r for r in probe if r["id"] == aid), None)
        assert row is not None
        assert row["would_mark"] is False, "asset <24h old must NOT be marked"
        assert "recent" in (row.get("skip_reason") or "").lower()
    finally:
        _cleanup([aid])


# -- Rail 6: audit log ------------------------------------------------------

def test_rail6_audit_log_snapshot_pre_delete():
    aid = _insert_asset(
        probe_first_404_at=datetime.now(timezone.utc) - timedelta(hours=72),
    )
    try:
        probe = _probe()
        _mark(probe)

        async def _check():
            cli, db = _cli_and_db()
            log = await db.marketing_assets_orphan_log.find_one({"asset_id": aid})
            cli.close()
            return log
        log = asyncio.get_event_loop().run_until_complete(_check())
        assert log is not None, "sweep must write an audit log entry"
        assert log["action"] == "auto_soft_delete"
        assert log["reason"] == "r2_blob_404_for_48h"
        assert "snapshot" in log
        assert log["snapshot"]["id"] == aid
        assert log["snapshot"]["prompt"] == "PYTEST orphan-sweep asset"
    finally:
        _cleanup([aid])


# -- Rail 7: idempotent ------------------------------------------------------

def test_rail7_idempotent_already_deleted():
    aid = _insert_asset(
        deleted=True,
        probe_first_404_at=datetime.now(timezone.utc) - timedelta(hours=72),
    )
    try:
        probe = _probe()
        # Already-deleted assets shouldn't even appear in the probe list
        row = next((r for r in probe if r["id"] == aid), None)
        assert row is None, "deleted=True assets must not be re-probed"
    finally:
        _cleanup([aid])


# -- Restore ----------------------------------------------------------------

def test_restore_only_undoes_auto_sweep_marks():
    from services.marketing_storage_sweep import restore_asset

    # Create an asset marked by MANUAL admin delete (not auto-sweep)
    aid_manual = _insert_asset(
        deleted=True,
        deleted_reason="manual_admin_delete",
    )
    # Create an asset marked by AUTO-SWEEP
    aid_auto = _insert_asset(
        deleted=True,
        deleted_reason="r2_blob_404_for_48h_auto_sweep",
    )

    async def _go():
        cli, db = _cli_and_db()
        try:
            manual_res = await restore_asset(db, aid_manual)
            auto_res = await restore_asset(db, aid_auto)
            manual_doc = await db.marketing_assets.find_one({"id": aid_manual}, {"_id": 0})
            auto_doc = await db.marketing_assets.find_one({"id": aid_auto}, {"_id": 0})
            return manual_res, auto_res, manual_doc, auto_doc
        finally:
            cli.close()

    manual_res, auto_res, manual_doc, auto_doc = asyncio.get_event_loop().run_until_complete(_go())
    _cleanup([aid_manual, aid_auto])

    assert manual_res["restored"] == 0, "manual delete must NOT be restored by the auto-sweep endpoint"
    assert manual_doc["deleted"] is True
    assert auto_res["restored"] == 1, "auto-sweep mark must be restored"
    assert auto_doc.get("deleted") is False
    assert "deleted_reason" not in auto_doc


# -- Probe endpoint ---------------------------------------------------------

def test_verify_storage_dry_run_does_not_modify():
    """HTTP smoke: dry_run=true must not mark anything."""
    import requests
    BASE = os.environ.get("BACKEND_URL",
                         "https://feature-verification-7.preview.emergentagent.com")
    login = requests.post(f"{BASE}/api/auth/login",
                          json={"email": "admin@test.com", "password": "admin123"},
                          timeout=10)
    assert login.status_code == 200
    tok = login.json().get("access_token") or login.json().get("token")
    h = {"Authorization": f"Bearer {tok}"}

    aid = _insert_asset(
        probe_first_404_at=datetime.now(timezone.utc) - timedelta(hours=72),
    )
    try:
        r = requests.post(f"{BASE}/api/admin/marketing-studio/verify-storage",
                          params={"dry_run": "true"}, headers=h, timeout=120)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["summary"]["dry_run"] is True
        # Asset must still be deleted=False after dry run
        doc = _get_asset(aid)
        assert doc["deleted"] is False, "dry_run must not modify assets"
    finally:
        _cleanup([aid])

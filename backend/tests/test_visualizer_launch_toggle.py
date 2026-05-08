"""Tests for the DB-backed visualizer public-launch toggle."""
import os
import sys
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402


@pytest_asyncio.fixture
async def db():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    test_db = client[f"test_vis_launch_{uuid.uuid4().hex[:8]}"]
    yield test_db
    await client.drop_database(test_db.name)
    client.close()


# ---------- env override helper ----------

def test_sync_env_override_reads_various_truthy(monkeypatch):
    from routes.visualizer import _public_enabled_sync
    monkeypatch.setenv("VISUALIZER_PUBLIC_ENABLED", "true")
    assert _public_enabled_sync() is True
    monkeypatch.setenv("VISUALIZER_PUBLIC_ENABLED", "1")
    assert _public_enabled_sync() is True
    monkeypatch.setenv("VISUALIZER_PUBLIC_ENABLED", "YES")
    assert _public_enabled_sync() is True


def test_sync_env_override_reads_various_falsy(monkeypatch):
    from routes.visualizer import _public_enabled_sync
    monkeypatch.setenv("VISUALIZER_PUBLIC_ENABLED", "false")
    assert _public_enabled_sync() is False
    monkeypatch.setenv("VISUALIZER_PUBLIC_ENABLED", "0")
    assert _public_enabled_sync() is False
    monkeypatch.setenv("VISUALIZER_PUBLIC_ENABLED", "off")
    assert _public_enabled_sync() is False


def test_sync_env_override_returns_none_when_unset(monkeypatch):
    from routes.visualizer import _public_enabled_sync
    monkeypatch.delenv("VISUALIZER_PUBLIC_ENABLED", raising=False)
    assert _public_enabled_sync() is None
    monkeypatch.setenv("VISUALIZER_PUBLIC_ENABLED", "")
    assert _public_enabled_sync() is None
    # Gibberish also returns None (so we fall back to DB, not hard-OFF)
    monkeypatch.setenv("VISUALIZER_PUBLIC_ENABLED", "bananas")
    assert _public_enabled_sync() is None


# ---------- DB toggle ----------

@pytest.mark.asyncio
async def test_public_enabled_reads_db_when_env_unset(db, monkeypatch):
    monkeypatch.delenv("VISUALIZER_PUBLIC_ENABLED", raising=False)
    from routes.visualizer import _public_enabled
    # No doc → OFF
    assert await _public_enabled(db) is False
    # Insert doc ON
    await db.website_settings.insert_one({"key": "visualizer_launch", "enabled": True})
    assert await _public_enabled(db) is True
    # Flip OFF
    await db.website_settings.update_one(
        {"key": "visualizer_launch"}, {"$set": {"enabled": False}}
    )
    assert await _public_enabled(db) is False


@pytest.mark.asyncio
async def test_env_override_beats_db(db, monkeypatch):
    from routes.visualizer import _public_enabled
    # DB says ON
    await db.website_settings.insert_one({"key": "visualizer_launch", "enabled": True})
    monkeypatch.setenv("VISUALIZER_PUBLIC_ENABLED", "false")
    assert await _public_enabled(db) is False  # env override wins
    monkeypatch.setenv("VISUALIZER_PUBLIC_ENABLED", "true")
    assert await _public_enabled(db) is True   # still wins when on


# ---------- Launch-status admin endpoints ----------

@pytest.mark.asyncio
async def test_set_launch_status_persists_and_records_admin(db, monkeypatch):
    monkeypatch.setattr("routes.visualizer.get_db", lambda: db)
    monkeypatch.delenv("VISUALIZER_PUBLIC_ENABLED", raising=False)

    from routes.visualizer import set_launch_status, LaunchStatusReq
    res = await set_launch_status(LaunchStatusReq(enabled=True), {"role": "admin", "email": "king@x"})
    assert res["ok"] is True
    assert res["enabled"] is True
    assert res["db_enabled"] is True
    assert res["env_override"] is None

    doc = await db.website_settings.find_one({"key": "visualizer_launch"})
    assert doc["enabled"] is True
    assert doc["updated_by"] == "king@x"
    assert isinstance(doc["updated_at"], datetime)


@pytest.mark.asyncio
async def test_get_launch_status_surfaces_env_override(db, monkeypatch):
    monkeypatch.setattr("routes.visualizer.get_db", lambda: db)

    from routes.visualizer import get_launch_status, set_launch_status, LaunchStatusReq
    # Save DB toggle OFF
    await set_launch_status(LaunchStatusReq(enabled=False), {"role": "admin", "email": "x@y"})
    # But env var forces ON
    monkeypatch.setenv("VISUALIZER_PUBLIC_ENABLED", "true")
    res = await get_launch_status({"role": "admin", "email": "x@y"})
    assert res["enabled"] is True           # effective value respects env
    assert res["db_enabled"] is False        # but DB toggle is honestly reported
    assert res["env_override"] is True


@pytest.mark.asyncio
async def test_feature_flag_endpoint_reflects_db(db, monkeypatch):
    monkeypatch.setattr("routes.visualizer.get_db", lambda: db)
    monkeypatch.delenv("VISUALIZER_PUBLIC_ENABLED", raising=False)

    from routes.visualizer import feature_flag
    # Fake request without bearer → admin_preview should be False
    class _Req:
        headers = {}
    # DB OFF → public=False
    out = await feature_flag(_Req())
    assert out == {"enabled": False, "public": False, "admin_preview": False}

    # Flip DB ON
    from routes.visualizer import set_launch_status, LaunchStatusReq
    await set_launch_status(LaunchStatusReq(enabled=True), {"role": "admin", "email": "x@y"})
    out2 = await feature_flag(_Req())
    assert out2 == {"enabled": True, "public": True, "admin_preview": False}


# ---------- One-click go-live + email waitlist ----------

@pytest.mark.asyncio
async def test_also_email_waitlist_triggers_launch_email(db, monkeypatch):
    """When `also_email_waitlist=True` on a go-live toggle, the launch
    email is sent in the same request. Idempotent — no double emails."""
    from unittest.mock import AsyncMock
    monkeypatch.setattr("routes.visualizer.get_db", lambda: db)
    monkeypatch.delenv("VISUALIZER_PUBLIC_ENABLED", raising=False)

    # Seed 3 unnotified + 1 already notified subscriber
    await db.visualizer_waitlist.insert_many([
        {"id": "1", "email": "a@x.com", "notified": False},
        {"id": "2", "email": "b@x.com", "notified": False},
        {"id": "3", "email": "c@x.com", "notified": False},
        {"id": "4", "email": "already@x.com", "notified": True},
    ])

    # Stub the Resend send so we don't hit the network
    send_mock = AsyncMock(return_value=True)
    monkeypatch.setattr("services.email.send_email_notification", send_mock)

    from routes.visualizer import set_launch_status, LaunchStatusReq
    res = await set_launch_status(
        LaunchStatusReq(enabled=True, also_email_waitlist=True),
        {"role": "admin", "email": "king@x"},
    )
    assert res["enabled"] is True
    assert res["first_go_live"] is True
    assert res["email_result"]["sent"] == 3  # only unnotified
    assert res["email_result"]["failed"] == 0
    assert send_mock.await_count == 1  # one chunk since 3 < 40

    # All 3 should now be marked notified so a re-click won't double-send
    remaining = await db.visualizer_waitlist.count_documents({"notified": {"$ne": True}})
    assert remaining == 0

    # Second flip with the same flag should be a no-op email
    send_mock.reset_mock()
    # Reset the launch state so we can go-live again (simulate hide + unhide)
    await set_launch_status(LaunchStatusReq(enabled=False), {"role": "admin", "email": "king@x"})
    res2 = await set_launch_status(
        LaunchStatusReq(enabled=True, also_email_waitlist=True),
        {"role": "admin", "email": "king@x"},
    )
    assert res2["first_go_live"] is False  # not first-ever any more
    assert res2["email_result"]["sent"] == 0
    assert res2["email_result"].get("message", "").startswith("No unnotified")


@pytest.mark.asyncio
async def test_also_email_skipped_when_hiding(db, monkeypatch):
    """Hiding the visualizer must never send the launch email even if
    the flag is passed in (defence against accidental misuse)."""
    from unittest.mock import AsyncMock
    monkeypatch.setattr("routes.visualizer.get_db", lambda: db)
    monkeypatch.delenv("VISUALIZER_PUBLIC_ENABLED", raising=False)

    send_mock = AsyncMock(return_value=True)
    monkeypatch.setattr("services.email.send_email_notification", send_mock)
    await db.visualizer_waitlist.insert_one({"id": "1", "email": "a@x.com", "notified": False})

    from routes.visualizer import set_launch_status, LaunchStatusReq
    res = await set_launch_status(
        LaunchStatusReq(enabled=False, also_email_waitlist=True),
        {"role": "admin", "email": "king@x"},
    )
    assert res["enabled"] is False
    assert res["email_result"] is None  # didn't fire
    assert send_mock.await_count == 0


@pytest.mark.asyncio
async def test_also_email_skipped_when_env_forces_off(db, monkeypatch):
    """If env var forces OFF, effective stays False — don't email."""
    from unittest.mock import AsyncMock
    monkeypatch.setattr("routes.visualizer.get_db", lambda: db)
    monkeypatch.setenv("VISUALIZER_PUBLIC_ENABLED", "false")

    send_mock = AsyncMock(return_value=True)
    monkeypatch.setattr("services.email.send_email_notification", send_mock)
    await db.visualizer_waitlist.insert_one({"id": "1", "email": "a@x.com", "notified": False})

    from routes.visualizer import set_launch_status, LaunchStatusReq
    res = await set_launch_status(
        LaunchStatusReq(enabled=True, also_email_waitlist=True),
        {"role": "admin", "email": "king@x"},
    )
    assert res["enabled"] is False  # env override wins
    assert res["db_enabled"] is True
    assert res["email_result"] is None  # didn't fire because effective is False
    assert send_mock.await_count == 0


@pytest.mark.asyncio
async def test_launch_status_exposes_unnotified_count(db, monkeypatch):
    monkeypatch.setattr("routes.visualizer.get_db", lambda: db)
    monkeypatch.delenv("VISUALIZER_PUBLIC_ENABLED", raising=False)

    await db.visualizer_waitlist.insert_many([
        {"id": "1", "email": "a@x.com", "notified": False},
        {"id": "2", "email": "b@x.com", "notified": False},
        {"id": "3", "email": "c@x.com", "notified": True},
    ])

    from routes.visualizer import get_launch_status
    res = await get_launch_status({"role": "admin", "email": "x@y"})
    assert res["waitlist_unnotified"] == 2
    assert res["ever_gone_live"] is False

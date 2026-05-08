"""Tests for Sora 2 video generation — job queue + cost estimate."""
import os
import sys
import uuid
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
import pytest_asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402


@pytest_asyncio.fixture
async def db(monkeypatch):
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    test_db = client[f"test_mkt_video_{uuid.uuid4().hex[:8]}"]
    monkeypatch.setattr("services.video_generation.get_db", lambda: test_db)
    yield test_db
    await client.drop_database(test_db.name)
    client.close()


# ---- Cost / catalogue --------------------------------------------

def test_estimate_cost_defaults(monkeypatch):
    monkeypatch.delenv("SORA2_COST_PER_SECOND", raising=False)
    monkeypatch.delenv("SORA2_PRO_COST_PER_SECOND", raising=False)
    from services.video_generation import estimate_cost
    assert estimate_cost("sora-2", 4) == 0.40
    assert estimate_cost("sora-2", 12) == 1.20
    assert estimate_cost("sora-2-pro", 4) == 1.20
    assert estimate_cost("sora-2-pro", 12) == 3.60


def test_estimate_cost_env_override(monkeypatch):
    monkeypatch.setenv("SORA2_COST_PER_SECOND", "0.08")
    monkeypatch.setenv("SORA2_PRO_COST_PER_SECOND", "0.25")
    from services.video_generation import estimate_cost
    assert estimate_cost("sora-2", 4) == 0.32
    assert estimate_cost("sora-2-pro", 12) == 3.00


# ---- Queue validation --------------------------------------------

@pytest.mark.asyncio
async def test_enqueue_validates_model(db):
    from services.video_generation import enqueue_job
    with pytest.raises(ValueError):
        await enqueue_job(prompt="hi", model="banana", size="1280x720", duration=4, admin_email="x@y")


@pytest.mark.asyncio
async def test_enqueue_validates_size(db):
    from services.video_generation import enqueue_job
    with pytest.raises(ValueError):
        await enqueue_job(prompt="hello world", model="sora-2", size="9999x9999", duration=4, admin_email="x@y")


@pytest.mark.asyncio
async def test_enqueue_rejects_incompatible_size_model_pair(db):
    """sora-2 can only do 1280x720. Submitting 1024x1792 (pro-only)
    with the basic model must fail cleanly before we call the API."""
    from services.video_generation import enqueue_job
    with pytest.raises(ValueError) as exc:
        await enqueue_job(
            prompt="a nice tile video",
            model="sora-2", size="1024x1792", duration=4, admin_email="x@y",
        )
    assert "sora-2-pro" in str(exc.value)


@pytest.mark.asyncio
async def test_enqueue_accepts_hd_for_both_models(db, monkeypatch):
    """1280x720 (HD landscape) works on sora-2 AND sora-2-pro."""
    monkeypatch.setattr("services.video_generation._ensure_worker_running", lambda: None)
    from services.video_generation import enqueue_job
    j1 = await enqueue_job(
        prompt="a nice tile video",
        model="sora-2", size="1280x720", duration=4, admin_email="x@y",
    )
    assert j1["status"] == "queued"
    j2 = await enqueue_job(
        prompt="a nice tile video pro",
        model="sora-2-pro", size="1280x720", duration=4, admin_email="x@y",
    )
    assert j2["status"] == "queued"


@pytest.mark.asyncio
async def test_enqueue_validates_duration(db):
    from services.video_generation import enqueue_job
    with pytest.raises(ValueError):
        await enqueue_job(prompt="hi", model="sora-2", size="1280x720", duration=5, admin_email="x@y")


@pytest.mark.asyncio
async def test_enqueue_validates_prompt_length(db):
    from services.video_generation import enqueue_job
    with pytest.raises(ValueError):
        await enqueue_job(prompt="hi", model="sora-2", size="1280x720", duration=4, admin_email="x@y")


@pytest.mark.asyncio
async def test_enqueue_persists_job(db, monkeypatch):
    # Stop the background worker from actually running so we can inspect the queued row
    monkeypatch.setattr("services.video_generation._ensure_worker_running", lambda: None)
    from services.video_generation import enqueue_job, get_job
    res = await enqueue_job(
        prompt="A stylish marble tile rotating on a turntable",
        model="sora-2", size="1280x720", duration=4, admin_email="admin@x",
    )
    assert res["status"] == "queued"
    assert res["progress"] == 0
    assert res["estimated_cost_usd"] == 0.40
    assert res["admin_email"] == "admin@x"
    # Reading the job back by id works
    got = await get_job(res["id"])
    assert got is not None
    assert got["prompt"].startswith("A stylish marble")


# ---- Job lifecycle (mocked Sora) ---------------------------------

@pytest.mark.asyncio
async def test_execute_job_happy_path(db, monkeypatch):
    """End-to-end: queue a job, let the worker drain it with Sora + R2 mocks,
    verify a marketing_video_assets row is created + job is succeeded."""
    monkeypatch.setenv("EMERGENT_LLM_KEY", "sk-test")

    # Mock the OpenAIVideoGeneration class — returns fake bytes fast
    class _FakeGen:
        def __init__(self, api_key):
            self.api_key = api_key
        def text_to_video(self, **kwargs):
            return b"\x00\x00\x00 ftypmp42 some fake mp4 bytes"

    monkeypatch.setattr("services.video_generation.OpenAIVideoGeneration", _FakeGen)

    # Mock R2 put_object — records call, returns success
    put_mock = MagicMock(return_value={"ok": True})
    monkeypatch.setattr("services.video_generation.put_object", put_mock)

    from services.video_generation import enqueue_job, _drain_queue_loop, get_job, list_assets
    job = await enqueue_job(
        prompt="A luxury marble tile glossy on a black backdrop",
        model="sora-2", size="1280x720", duration=4, admin_email="k@x",
    )
    # Run the worker synchronously to completion
    await _drain_queue_loop()

    # Job flipped to succeeded
    finished = await get_job(job["id"])
    assert finished["status"] == "succeeded", f"got {finished['status']}: {finished.get('error')}"
    assert finished["progress"] == 100
    assert finished["video_url"].startswith("/api/website/marketing-video/")
    assert finished["actual_cost_usd"] == 0.40
    assert put_mock.called
    # Asset row exists
    videos = await list_assets()
    assert len(videos) == 1
    assert videos[0]["id"] == finished["video_id"]
    assert videos[0]["cost_usd"] == 0.40
    assert videos[0]["duration_seconds"] == 4


@pytest.mark.asyncio
async def test_execute_job_handles_sora_failure(db, monkeypatch):
    """If Sora blows up, the job is marked failed with the error message,
    and no asset row is created."""
    monkeypatch.setenv("EMERGENT_LLM_KEY", "sk-test")

    class _FakeGen:
        def __init__(self, api_key): pass
        def text_to_video(self, **kwargs):
            raise RuntimeError("sora quota exceeded")

    monkeypatch.setattr("services.video_generation.OpenAIVideoGeneration", _FakeGen)
    monkeypatch.setattr("services.video_generation.put_object", MagicMock())

    from services.video_generation import enqueue_job, _drain_queue_loop, get_job, list_assets
    job = await enqueue_job(prompt="a tile video", model="sora-2", size="1280x720", duration=4, admin_email="k@x")
    await _drain_queue_loop()
    failed = await get_job(job["id"])
    assert failed["status"] == "failed"
    assert "sora quota exceeded" in (failed.get("error") or "")
    assert await list_assets() == []


@pytest.mark.asyncio
async def test_execute_job_handles_empty_bytes(db, monkeypatch):
    """Sora returning empty → fail, don't create a zero-byte asset."""
    monkeypatch.setenv("EMERGENT_LLM_KEY", "sk-test")

    class _FakeGen:
        def __init__(self, api_key): pass
        def text_to_video(self, **kwargs):
            return b""

    monkeypatch.setattr("services.video_generation.OpenAIVideoGeneration", _FakeGen)
    monkeypatch.setattr("services.video_generation.put_object", MagicMock())

    from services.video_generation import enqueue_job, _drain_queue_loop, get_job
    job = await enqueue_job(prompt="a tile video", model="sora-2", size="1280x720", duration=4, admin_email="k@x")
    await _drain_queue_loop()
    failed = await get_job(job["id"])
    assert failed["status"] == "failed"
    assert "empty bytes" in (failed.get("error") or "").lower()


@pytest.mark.asyncio
async def test_execute_job_handles_r2_upload_failure(db, monkeypatch):
    """If R2 upload fails, mark job failed — don't create an asset row
    with a broken video_url."""
    monkeypatch.setenv("EMERGENT_LLM_KEY", "sk-test")

    class _FakeGen:
        def __init__(self, api_key): pass
        def text_to_video(self, **kwargs):
            return b"mp4 bytes"

    monkeypatch.setattr("services.video_generation.OpenAIVideoGeneration", _FakeGen)

    def _broken_put(*args, **kwargs):
        raise RuntimeError("R2 connection refused")
    monkeypatch.setattr("services.video_generation.put_object", _broken_put)

    from services.video_generation import enqueue_job, _drain_queue_loop, get_job, list_assets
    job = await enqueue_job(prompt="a tile video", model="sora-2", size="1280x720", duration=4, admin_email="k@x")
    await _drain_queue_loop()
    failed = await get_job(job["id"])
    assert failed["status"] == "failed"
    assert "R2" in (failed.get("error") or "")
    assert await list_assets() == []


# ---- Cancel / stats / reap  --------------------------------------

@pytest.mark.asyncio
async def test_cancel_queued_job(db, monkeypatch):
    monkeypatch.setattr("services.video_generation._ensure_worker_running", lambda: None)
    from services.video_generation import enqueue_job, cancel_job, get_job
    j = await enqueue_job(prompt="a tile video", model="sora-2", size="1280x720", duration=4, admin_email="k@x")
    cancelled = await cancel_job(j["id"])
    assert cancelled["status"] == "cancelled"
    after = await get_job(j["id"])
    assert after["status"] == "cancelled"


@pytest.mark.asyncio
async def test_reap_stale_running_jobs(db, monkeypatch):
    """Jobs stuck in 'running' for more than RUNNING_TIMEOUT_MINUTES
    should be reaped so the queue never wedges."""
    # Seed a stale running row directly
    await db.marketing_video_jobs.insert_one({
        "id": "stale1",
        "status": "running",
        "started_at": datetime.now(timezone.utc) - timedelta(minutes=30),
        "prompt": "stale", "model": "sora-2", "size": "1280x720", "duration": 4,
        "progress": 50,
    })
    from services.video_generation import _reap_stale_running_jobs
    await _reap_stale_running_jobs()
    row = await db.marketing_video_jobs.find_one({"id": "stale1"})
    assert row["status"] == "failed"
    assert "timeout" in (row.get("error") or "").lower()


@pytest.mark.asyncio
async def test_stats_rollup(db, monkeypatch):
    await db.marketing_video_assets.insert_many([
        {"id": "v1", "cost_usd": 0.40, "duration_seconds": 4, "video_url": "", "prompt": "", "model": "sora-2", "size": "1280x720", "created_at": datetime.now(timezone.utc)},
        {"id": "v2", "cost_usd": 2.40, "duration_seconds": 8, "video_url": "", "prompt": "", "model": "sora-2-pro", "size": "1024x1024", "created_at": datetime.now(timezone.utc)},
    ])
    await db.marketing_video_jobs.insert_many([
        {"id": "j1", "status": "running", "prompt": "", "model": "sora-2", "size": "1280x720", "duration": 4, "created_at": datetime.now(timezone.utc)},
        {"id": "j2", "status": "queued", "prompt": "", "model": "sora-2", "size": "1280x720", "duration": 4, "created_at": datetime.now(timezone.utc)},
        {"id": "j3", "status": "queued", "prompt": "", "model": "sora-2", "size": "1280x720", "duration": 4, "created_at": datetime.now(timezone.utc)},
    ])
    from services.video_generation import stats
    s = await stats()
    assert s["total_videos"] == 2
    assert s["running_jobs"] == 1
    assert s["queued_jobs"] == 2
    assert s["lifetime_spend_usd"] == 2.80
    assert s["lifetime_seconds"] == 12


@pytest.mark.asyncio
async def test_delete_asset_removes_from_db(db, monkeypatch):
    await db.marketing_video_assets.insert_one({
        "id": "v-del", "cost_usd": 0.40, "duration_seconds": 4,
        "video_url": "", "prompt": "", "model": "sora-2",
        "size": "1280x720", "created_at": datetime.now(timezone.utc),
    })
    from services.video_generation import delete_asset
    res = await delete_asset("v-del")
    assert res["ok"] is True
    assert await db.marketing_video_assets.count_documents({}) == 0


@pytest.mark.asyncio
async def test_delete_asset_404_when_missing(db):
    from services.video_generation import delete_asset
    with pytest.raises(LookupError):
        await delete_asset("does-not-exist")

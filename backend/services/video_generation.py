"""
Sora 2 video generation — wraps the emergentintegrations library,
adds a Mongo-backed job queue so the admin doesn't have to hold the
HTTP connection open for the 2-5 minute generation.

Shape:

    client submits a job (POST /api/admin/marketing-studio/videos/generate)
        ↓
    row inserted in `marketing_video_jobs` with status="queued"
        ↓
    background worker (fanout by the API-router startup event)
    picks the next queued job, flips status=running, calls Sora,
    uploads the MP4 to R2, flips status=succeeded or failed
        ↓
    client polls /jobs/{id} every 5s and renders progress

Concurrency is capped at 2 in-flight jobs so we don't hammer either
Sora or our R2 bucket. Jobs stuck running for >15 min are reaped and
marked failed so the queue never wedges.

Cost is estimated client-side from the model + duration and shown
before generation; real cost is written to the job row once the MP4
lands.
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from emergentintegrations.llm.openai.video_generation import OpenAIVideoGeneration

from config import get_db
from services.object_storage import put_object

logger = logging.getLogger(__name__)


# ---- Model catalog -----------------------------------------------

# Cost numbers are deliberately env-overridable because OpenAI's public
# Sora 2 rate card moves. Defaults are conservative estimates as of
# Feb 2026 so admin-facing cost previews never understate spend.
def _cost_per_second(model: str) -> float:
    if model == "sora-2-pro":
        return float(os.environ.get("SORA2_PRO_COST_PER_SECOND", "0.30"))
    return float(os.environ.get("SORA2_COST_PER_SECOND", "0.10"))


# NOTE on sizes: as of May 2026 the real OpenAI Sora 2 API accepts a
# more restricted set than the emergentintegrations library advertises
# in its validator. The intersection of "what the library lets through"
# AND "what the upstream API actually accepts" is:
#
#   sora-2:       {1280x720}          (landscape 16:9 only — NO portrait)
#   sora-2-pro:   {1280x720, 1792x1024, 1024x1792}
#
# The library's validator also rejects `720x1280` outright (even though
# that's the real sora-2 portrait size from OpenAI), so we can't work
# around the sora-2 portrait gap via the library today. When the admin
# picks a portrait/widescreen preset we therefore auto-upgrade the
# model to sora-2-pro.
SUPPORTED_SIZES = {"1280x720", "1792x1024", "1024x1792"}
SUPPORTED_DURATIONS = {4, 8, 12}
SUPPORTED_MODELS = {"sora-2", "sora-2-pro"}

# Map friendly labels → size strings so the frontend stays declarative.
# `requires_model` pins the preset to sora-2-pro when the standard
# model can't deliver that aspect.
SIZE_PRESETS = [
    {
        "id": "vertical",
        "label": "Vertical 9:16 (Reels/TikTok)",
        "size": "1024x1792",
        "requires_model": "sora-2-pro",
    },
    {
        "id": "widescreen",
        "label": "Widescreen 16:9 (YT Shorts/X)",
        "size": "1792x1024",
        "requires_model": "sora-2-pro",
    },
    {
        "id": "hd",
        "label": "HD 720p (landscape)",
        "size": "1280x720",
        "requires_model": None,  # works on both sora-2 and sora-2-pro
    },
]


# Per-size model compatibility — used by the validator to block any
# request that would fail upstream.
SIZE_MODEL_COMPAT = {
    "1280x720": {"sora-2", "sora-2-pro"},
    "1792x1024": {"sora-2-pro"},
    "1024x1792": {"sora-2-pro"},
}


def estimate_cost(model: str, duration: int) -> float:
    """Return an estimated cost in USD for a given model + duration.
    Rounded up to 4 decimal places so admin UI never shows $0.00."""
    return round(_cost_per_second(model) * int(duration), 4)


# ---- Queue plumbing ----------------------------------------------

MAX_CONCURRENCY = int(os.environ.get("SORA2_MAX_CONCURRENCY", "2"))
RUNNING_TIMEOUT_MINUTES = 15
_queue_lock = asyncio.Lock()
_background_task: Optional[asyncio.Task] = None


async def enqueue_job(
    *,
    prompt: str,
    model: str,
    size: str,
    duration: int,
    admin_email: Optional[str],
    source_asset_id: Optional[str] = None,
) -> dict:
    """Validate + insert a new queued job. Returns the job dict."""
    if model not in SUPPORTED_MODELS:
        raise ValueError(f"Unsupported model '{model}'. Choose from: {sorted(SUPPORTED_MODELS)}")
    if size not in SUPPORTED_SIZES:
        raise ValueError(f"Unsupported size '{size}'. Choose from: {sorted(SUPPORTED_SIZES)}")
    if int(duration) not in SUPPORTED_DURATIONS:
        raise ValueError(f"Unsupported duration {duration}. Choose 4, 8, or 12 seconds.")
    # Hard-check the size/model pair so we never submit a request that
    # we already know the upstream Sora API will reject. The frontend
    # auto-upgrades the model on the client side too (defence in
    # depth), but back-end must enforce it as well.
    compat = SIZE_MODEL_COMPAT.get(size, set())
    if model not in compat:
        raise ValueError(
            f"Model '{model}' does not support size {size}. "
            f"Supported models for this size: {sorted(compat)}"
        )
    if not prompt or len(prompt.strip()) < 4:
        raise ValueError("Prompt must be at least 4 characters.")
    db = get_db()
    job_id = uuid.uuid4().hex[:20]
    now = datetime.now(timezone.utc)
    doc = {
        "id": job_id,
        "prompt": prompt.strip()[:2000],
        "model": model,
        "size": size,
        "duration": int(duration),
        "estimated_cost_usd": estimate_cost(model, duration),
        "actual_cost_usd": None,
        "admin_email": admin_email,
        "source_asset_id": source_asset_id,
        "status": "queued",
        "progress": 0,
        "status_message": "Queued for generation",
        "video_url": None,
        "video_id": None,
        "video_bytes": None,
        "error": None,
        "created_at": now,
        "started_at": None,
        "completed_at": None,
    }
    await db.marketing_video_jobs.insert_one(doc)
    # Fire the background worker now if one isn't already running. The
    # worker drains the queue and exits — saves having a permanent
    # event-loop task when no videos are being made.
    _ensure_worker_running()
    return _strip(doc)


def _strip(doc: dict) -> dict:
    """Drop Mongo-y fields + inline the datetimes for JSON clients."""
    out = dict(doc)
    out.pop("_id", None)
    out.pop("video_bytes", None)
    for k in ("created_at", "started_at", "completed_at"):
        v = out.get(k)
        if isinstance(v, datetime):
            out[k] = v.isoformat()
    return out


async def list_jobs(*, limit: int = 20, include_statuses: Optional[list] = None) -> list:
    """Recent jobs (newest first). Defaults to running+queued+failed so
    the frontend strip shows what's happening right now."""
    db = get_db()
    q = {}
    if include_statuses:
        q["status"] = {"$in": include_statuses}
    rows = await db.marketing_video_jobs.find(q, {"_id": 0, "video_bytes": 0}) \
        .sort("created_at", -1).limit(limit).to_list(length=limit)
    return [_strip(r) for r in rows]


async def get_job(job_id: str) -> Optional[dict]:
    db = get_db()
    row = await db.marketing_video_jobs.find_one(
        {"id": job_id}, {"_id": 0, "video_bytes": 0}
    )
    return _strip(row) if row else None


async def cancel_job(job_id: str) -> dict:
    """Mark a queued (not-yet-running) job as cancelled. Running jobs
    can't be cancelled mid-flight — Sora doesn't support that — but we
    mark them so the worker stops waiting for them."""
    db = get_db()
    now = datetime.now(timezone.utc)
    row = await db.marketing_video_jobs.find_one({"id": job_id})
    if not row:
        raise LookupError(f"Job {job_id} not found")
    if row.get("status") in ("succeeded", "failed", "cancelled"):
        return _strip(row)
    await db.marketing_video_jobs.update_one(
        {"id": job_id},
        {"$set": {
            "status": "cancelled",
            "status_message": "Cancelled by admin",
            "completed_at": now,
        }},
    )
    updated = await db.marketing_video_jobs.find_one({"id": job_id})
    return _strip(updated)


# ---- Worker ------------------------------------------------------

def _ensure_worker_running() -> None:
    global _background_task
    if _background_task and not _background_task.done():
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    _background_task = loop.create_task(_drain_queue_loop())


async def _drain_queue_loop() -> None:
    """Process queued jobs up to MAX_CONCURRENCY in parallel, then exit."""
    try:
        sem = asyncio.Semaphore(MAX_CONCURRENCY)
        active: list[asyncio.Task] = []
        # First, sweep timed-out running jobs
        await _reap_stale_running_jobs()
        while True:
            next_job = await _claim_next_queued_job()
            if next_job is None:
                break  # queue drained
            async def _runner(job=next_job):
                async with sem:
                    await _execute_job(job)
            active.append(asyncio.create_task(_runner()))
            # Bound concurrency
            if len(active) >= MAX_CONCURRENCY:
                # Wait for at least one to finish before claiming more
                done, pending = await asyncio.wait(active, return_when=asyncio.FIRST_COMPLETED)
                active = list(pending)
        if active:
            await asyncio.gather(*active, return_exceptions=True)
    except Exception:
        logger.exception("video generation worker crashed")


async def _claim_next_queued_job() -> Optional[dict]:
    """Atomically flip the oldest queued job to running and return it."""
    db = get_db()
    now = datetime.now(timezone.utc)
    async with _queue_lock:
        row = await db.marketing_video_jobs.find_one_and_update(
            {"status": "queued"},
            {"$set": {
                "status": "running",
                "status_message": "Calling Sora 2 — expect 2-5 minutes",
                "started_at": now,
                "progress": 5,
            }},
            sort=[("created_at", 1)],
            return_document=True,
        )
    return row


async def _reap_stale_running_jobs() -> None:
    """Fail any job that's been 'running' for longer than
    RUNNING_TIMEOUT_MINUTES — prevents the queue wedging if a worker
    crashed mid-flight."""
    db = get_db()
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=RUNNING_TIMEOUT_MINUTES)
    await db.marketing_video_jobs.update_many(
        {"status": "running", "started_at": {"$lt": cutoff}},
        {"$set": {
            "status": "failed",
            "status_message": "Timed out — worker likely crashed",
            "error": "running-state timeout",
            "completed_at": datetime.now(timezone.utc),
        }},
    )


async def _execute_job(job: dict) -> None:
    """Run one Sora 2 generation and upload to R2."""
    db = get_db()
    job_id = job["id"]
    prompt = job["prompt"]
    model = job["model"]
    size = job["size"]
    duration = int(job["duration"])
    try:
        # Bump progress so the frontend knows we started
        await db.marketing_video_jobs.update_one(
            {"id": job_id},
            {"$set": {"progress": 10, "status_message": "Submitting to Sora 2…"}},
        )

        # Sora 2 is synchronous from our POV — blocks for 2-5 min. Run
        # in a thread so we don't starve the event loop.
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            raise RuntimeError("EMERGENT_LLM_KEY not set — cannot call Sora 2")
        def _do_gen():
            gen = OpenAIVideoGeneration(api_key=api_key)
            return gen.text_to_video(
                prompt=prompt,
                model=model,
                size=size,
                duration=duration,
                max_wait_time=900,  # 15 minutes; the reaper kicks at 15 too
            )
        # Keep kicking progress forward while the blocking call runs so
        # the admin sees a live bar instead of a frozen 10%.
        async def _tick():
            pct = 15
            while pct < 85:
                await asyncio.sleep(15)
                try:
                    await db.marketing_video_jobs.update_one(
                        {"id": job_id, "status": "running"},
                        {"$set": {"progress": pct}},
                    )
                except Exception:
                    pass
                pct += 8

        ticker = asyncio.create_task(_tick())
        try:
            video_bytes = await asyncio.to_thread(_do_gen)
        finally:
            ticker.cancel()

        if not video_bytes:
            raise RuntimeError("Sora 2 returned empty bytes")

        # Upload to R2
        await db.marketing_video_jobs.update_one(
            {"id": job_id},
            {"$set": {"progress": 90, "status_message": "Uploading to storage…"}},
        )
        video_id = uuid.uuid4().hex[:24]
        r2_path = f"tile-station/marketing-videos/{video_id}.mp4"
        try:
            await asyncio.to_thread(put_object, r2_path, video_bytes, "video/mp4")
        except Exception as upload_err:
            raise RuntimeError(f"R2 upload failed: {upload_err}") from upload_err

        public_url = f"/api/website/marketing-video/{video_id}.mp4"
        now = datetime.now(timezone.utc)

        # Insert into the "assets" collection so the videos-list query
        # is a simple find() and not a derived join of jobs.
        await db.marketing_video_assets.insert_one({
            "id": video_id,
            "job_id": job_id,
            "prompt": prompt,
            "model": model,
            "size": size,
            "duration_seconds": duration,
            "cost_usd": estimate_cost(model, duration),
            "video_url": public_url,
            "source_asset_id": job.get("source_asset_id"),
            "created_at": now,
            "created_by": job.get("admin_email"),
        })
        await db.marketing_video_jobs.update_one(
            {"id": job_id},
            {"$set": {
                "status": "succeeded",
                "status_message": "Ready",
                "progress": 100,
                "completed_at": now,
                "video_url": public_url,
                "video_id": video_id,
                "actual_cost_usd": estimate_cost(model, duration),
            }},
        )
    except Exception as exc:
        logger.exception(f"video job {job_id} failed")
        await db.marketing_video_jobs.update_one(
            {"id": job_id},
            {"$set": {
                "status": "failed",
                "status_message": "Generation failed",
                "error": str(exc)[:500],
                "completed_at": datetime.now(timezone.utc),
            }},
        )


# ---- Asset / video CRUD ------------------------------------------

async def list_assets(*, limit: int = 40) -> list:
    db = get_db()
    rows = await db.marketing_video_assets.find({}, {"_id": 0}) \
        .sort("created_at", -1).limit(limit).to_list(length=limit)
    for r in rows:
        v = r.get("created_at")
        if isinstance(v, datetime):
            r["created_at"] = v.isoformat()
    return rows


async def delete_asset(video_id: str) -> dict:
    db = get_db()
    row = await db.marketing_video_assets.find_one({"id": video_id})
    if not row:
        raise LookupError(f"Video {video_id} not found")
    # Drop the DB row first (admin UX: removed from list immediately),
    # then try to delete the R2 blob. R2 deletion is best-effort —
    # orphaned blobs get swept by the storage-sweep cron.
    await db.marketing_video_assets.delete_one({"id": video_id})
    try:
        from services.object_storage import delete_object  # pylint: disable=import-outside-toplevel
        await asyncio.to_thread(delete_object, f"tile-station/marketing-videos/{video_id}.mp4")
    except Exception:
        pass  # non-fatal — the sweeper will clean up
    return {"ok": True, "id": video_id}


async def stats() -> dict:
    """Videos overview for the stats strip."""
    db = get_db()
    total = await db.marketing_video_assets.count_documents({})
    running = await db.marketing_video_jobs.count_documents({"status": "running"})
    queued = await db.marketing_video_jobs.count_documents({"status": "queued"})
    # Lifetime spend
    cursor = db.marketing_video_assets.aggregate([
        {"$group": {"_id": None, "spend": {"$sum": "$cost_usd"}, "seconds": {"$sum": "$duration_seconds"}}}
    ])
    spend = 0.0
    seconds = 0
    async for d in cursor:
        spend = float(d.get("spend") or 0)
        seconds = int(d.get("seconds") or 0)
    return {
        "total_videos": total,
        "running_jobs": running,
        "queued_jobs": queued,
        "lifetime_spend_usd": round(spend, 2),
        "lifetime_seconds": seconds,
    }

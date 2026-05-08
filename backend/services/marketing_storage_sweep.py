"""
Marketing Studio — orphan asset storage sweep.

Detects `marketing_assets` whose R2 blob is missing (the image URL
404s) and soft-deletes them so they stop cluttering the admin gallery.

Safety rails (every one of these must pass before an asset is marked):

  1. **Never hard-delete.** Soft-deletes only (`deleted: true,
     orphaned_at: <ts>`). The row stays in Mongo so we can recover
     if R2 comes back or if this code was wrong.

  2. **Skip currently-published assets.** If `published_to` is set,
     the banner is live on the storefront — never auto-delete even
     if the blob is missing. Admin needs visibility to re-upload.

  3. **Skip assets linked to hero_slides.** The storefront carousel
     is critical — if an asset_id matches any hero_slide row, leave
     it alone. (Separate `cleanup-orphan-hero-slides` endpoint handles
     the reverse: slides without assets.)

  4. **48h cooling period.** An asset must return 404 on TWO
     consecutive nightly probes (≥48h apart) before being marked.
     Transient R2/network hiccups don't cause auto-delete.

  5. **Skip recent creates (<24h).** Uploads in progress or assets
     mid-generation shouldn't be flagged.

  6. **Audit log.** Every mark writes a snapshot to
     `marketing_assets_orphan_log` with the full asset doc for
     forensic recovery.

  7. **Idempotent.** Already-soft-deleted assets are skipped. Re-runs
     of the tick on the same R2 state do nothing new.

The whole sweep defaults to `dry_run=True` so admins can inspect
what WOULD be deleted before pulling the trigger. The nightly tick
runs in real (non-dry-run) mode but the same safety rails apply.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

PROBE_TIMEOUT_S = 8.0
CONSECUTIVE_404_HOURS = 48  # must be 404 for >=48h before marking
MIN_ASSET_AGE_HOURS = 24    # skip creates <24h old
MAX_PROBES_PER_RUN = 500    # safety cap on scan size


def _public_base_url() -> str:
    """Where the marketing-media serve endpoint lives.

    Local dev uses the frontend preview URL; production points at the
    Railway backend directly so we don't depend on the frontend proxy
    being up to probe storage.
    """
    return (
        os.environ.get("BACKEND_PUBLIC_URL")
        or os.environ.get("REACT_APP_BACKEND_URL")
        or "http://localhost:8001"
    ).rstrip("/")


async def _probe_url(client: httpx.AsyncClient, url: str) -> int:
    """Single probe — returns HTTP status int or 0 on connection error."""
    try:
        resp = await client.get(url, timeout=PROBE_TIMEOUT_S)
        return resp.status_code
    except httpx.TimeoutException:
        return 0
    except Exception:
        return 0


async def probe_assets(db, limit: int = MAX_PROBES_PER_RUN) -> list[dict]:
    """Probe each non-deleted asset's image_url. For each:

      • 200 → clear any prior `probe_first_404_at` stamp.
      • 404 → stamp `probe_first_404_at` if not already set.
      • other → leave alone (doesn't count as either)

    Returns list of dicts `{id, status, first_404_at, would_mark}` so
    the admin UI / nightly tick can decide what to do.

    `would_mark=True` means the asset is eligible for the orphan sweep
    RIGHT NOW (satisfies all 7 safety rails). Callers pass this list
    to `mark_orphans(...)` to actually perform the soft-delete.
    """
    base = _public_base_url()
    now = datetime.now(timezone.utc)
    cutoff_404 = now - timedelta(hours=CONSECUTIVE_404_HOURS)
    cutoff_age = now - timedelta(hours=MIN_ASSET_AGE_HOURS)

    cursor = db.marketing_assets.find(
        {"deleted": {"$ne": True}},
        {
            "_id": 0, "id": 1, "image_url": 1, "prompt": 1,
            "published_to": 1, "created_at": 1, "probe_first_404_at": 1,
        },
    ).limit(limit)

    results: list[dict] = []
    async with httpx.AsyncClient(timeout=PROBE_TIMEOUT_S) as client:
        async for a in cursor:
            img_url = a.get("image_url") or ""
            if not img_url:
                continue
            # `image_url` is stored as a path like /api/website/marketing-media/<file>.
            # Build the full URL against the backend origin.
            full_url = f"{base}{img_url}" if img_url.startswith("/") else img_url
            status = await _probe_url(client, full_url)

            row = {
                "id": a.get("id"),
                "status": status,
                "prompt": (a.get("prompt") or "")[:120],
                "image_url": img_url,
                "published_to": a.get("published_to"),
                "created_at": a.get("created_at"),
                "first_404_at": a.get("probe_first_404_at"),
                "would_mark": False,
                "skip_reason": None,
            }

            if status == 200:
                # Blob exists → clear any stale 404 stamp.
                if a.get("probe_first_404_at"):
                    await db.marketing_assets.update_one(
                        {"id": a["id"]}, {"$unset": {"probe_first_404_at": ""}},
                    )
                    row["first_404_at"] = None
            elif status == 404:
                if not a.get("probe_first_404_at"):
                    # First time we've seen it 404 — start the 48h clock.
                    await db.marketing_assets.update_one(
                        {"id": a["id"]},
                        {"$set": {"probe_first_404_at": now}},
                    )
                    row["first_404_at"] = now
                # Evaluate the safety rails to set would_mark
                first_404 = a.get("probe_first_404_at") or now
                # Normalise to aware datetime
                if isinstance(first_404, str):
                    try:
                        first_404 = datetime.fromisoformat(first_404.replace("Z", "+00:00"))
                    except Exception:
                        first_404 = now
                if first_404.tzinfo is None:
                    first_404 = first_404.replace(tzinfo=timezone.utc)

                created_at = a.get("created_at")
                if isinstance(created_at, str):
                    try:
                        created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    except Exception:
                        created_at = now
                if created_at and created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)

                if a.get("published_to"):
                    row["skip_reason"] = "published — never auto-delete a live banner"
                elif created_at and created_at > cutoff_age:
                    row["skip_reason"] = "too recent (<24h) — may be uploading"
                elif first_404 > cutoff_404:
                    age_hours = int((now - first_404).total_seconds() / 3600)
                    row["skip_reason"] = f"first seen 404 only {age_hours}h ago — 48h cooling period"
                else:
                    # Check hero_slides link — any slide pointing to this asset?
                    linked_slide = await db.hero_slides.find_one(
                        {"asset_id": a["id"]}, {"_id": 1}
                    )
                    if linked_slide:
                        row["skip_reason"] = "linked to a hero_slides row — never auto-delete"
                    else:
                        row["would_mark"] = True
            # Status 0 (timeout/conn error) or other 5xx — don't modify the
            # stamp. Probe again next tick.

            results.append(row)
    return results


async def mark_orphans(db, probe_results: list[dict]) -> dict:
    """Apply soft-delete to assets the probe flagged as `would_mark`.
    Writes a snapshot to `marketing_assets_orphan_log` first (audit trail
    for recovery), then sets `deleted: true` on the asset.

    Returns `{marked: N, skipped: M, errors: K}`.
    """
    marked = 0
    errors = 0
    now = datetime.now(timezone.utc)
    for r in probe_results:
        if not r.get("would_mark"):
            continue
        asset_id = r.get("id")
        try:
            # Snapshot for recovery — includes the full doc pre-delete
            snap = await db.marketing_assets.find_one({"id": asset_id}, {"_id": 0})
            if not snap:
                continue
            # Double-check the safety rails (race-free — something may
            # have published this asset between probe and mark).
            if snap.get("published_to") or snap.get("deleted"):
                errors += 1
                logger.warning("[orphan-sweep] safety rail caught race: %s is now %s",
                               asset_id, "published" if snap.get("published_to") else "deleted")
                continue
            await db.marketing_assets_orphan_log.insert_one({
                "asset_id": asset_id,
                "action": "auto_soft_delete",
                "reason": "r2_blob_404_for_48h",
                "orphaned_at": now,
                "snapshot": snap,
            })
            await db.marketing_assets.update_one(
                {"id": asset_id, "published_to": None, "deleted": {"$ne": True}},
                {"$set": {
                    "deleted": True,
                    "deleted_at": now.isoformat(),
                    "deleted_reason": "r2_blob_404_for_48h_auto_sweep",
                    "orphaned_at": now,
                }},
            )
            marked += 1
            logger.info("[orphan-sweep] marked asset %s as orphan (img=%s)",
                        asset_id, (snap.get("image_url") or "")[:80])
        except Exception:
            errors += 1
            logger.exception("[orphan-sweep] failed to mark %s", asset_id)
    return {"marked": marked, "errors": errors}


async def restore_asset(db, asset_id: str) -> dict:
    """Undo an auto-sweep mark. Only restores assets that were marked
    by this sweep (deleted_reason starts with 'r2_blob_404_*') — so
    regular admin Delete actions aren't touched."""
    res = await db.marketing_assets.update_one(
        {
            "id": asset_id,
            "deleted_reason": {"$regex": "^r2_blob_404_"},
        },
        {"$set": {"deleted": False},
         "$unset": {"deleted_at": "", "deleted_reason": "",
                    "orphaned_at": "", "probe_first_404_at": ""}},
    )
    return {"ok": True, "restored": res.modified_count}


async def run_nightly_orphan_sweep() -> dict:
    """Scheduled entrypoint. Probes + marks in one pass."""
    from config import get_db
    db = get_db()
    try:
        probe = await probe_assets(db)
        would_mark = sum(1 for r in probe if r.get("would_mark"))
        logger.info("[orphan-sweep] probed %d assets, %d eligible for marking",
                    len(probe), would_mark)
        if would_mark == 0:
            return {"probed": len(probe), "marked": 0, "would_mark": 0}
        result = await mark_orphans(db, probe)
        return {"probed": len(probe), "would_mark": would_mark, **result}
    except Exception:
        logger.exception("[orphan-sweep] nightly run crashed")
        return {"error": "sweep crashed — see logs"}


async def nightly_loop():
    """Forever-loop: run once per 24h at 03:00 UTC. Sleeps off-peak
    so the probe doesn't compete with customers / the autogen tick."""
    await asyncio.sleep(90)  # let startup settle
    while True:
        try:
            now = datetime.now(timezone.utc)
            target = now.replace(hour=3, minute=0, second=0, microsecond=0)
            if target <= now:
                target = target + timedelta(days=1)
            wait = (target - now).total_seconds()
            logger.info("[orphan-sweep] next run at %s (in %ds)",
                        target.isoformat(), int(wait))
            await asyncio.sleep(wait)
            try:
                await run_nightly_orphan_sweep()
            except Exception:
                logger.exception("[orphan-sweep] sweep iteration crashed; retry tomorrow")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("[orphan-sweep] loop iteration crashed; backing off 1h")
            await asyncio.sleep(3600)

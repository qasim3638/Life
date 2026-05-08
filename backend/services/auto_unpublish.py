"""Auto-unpublish background task for marketing assets.

Runs every 60s; scans for promo banners whose `scheduled_end` has
passed and the linked marketing_asset is still flagged as published.
For each match it:

  • Calls `_unpublish_placement('promo_banner')` — sets
    `website_settings.promo_banner.enabled=False` and busts the
    storefront cache so the homepage flips immediately.
  • Updates `marketing_assets.published_to=None` on the linked asset
    so the admin gallery card no longer says "PUBLISHED → PROMO
    BANNER" (matches reality).

Idempotent — safe to run repeatedly. Failed scans log a warning but
don't crash the loop. This mirrors the pattern of `health_monitor.py`
and `visualizer_seed.py` startup tasks.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 60


async def _run_one_pass(db) -> int:
    """Single pass — returns the number of banners auto-unpublished."""
    from routes.marketing_studio import _unpublish_placement

    now = datetime.now(timezone.utc)
    flipped = 0

    # Promo banner — schedule_end past, but still enabled
    banner = await db.website_settings.find_one(
        {"key": "promo_banner"}, {"_id": 0}
    )
    if banner and banner.get("schedule_enabled") and banner.get("enabled") and banner.get("scheduled_end"):
        try:
            end = datetime.fromisoformat(str(banner["scheduled_end"]).replace("Z", "+00:00"))
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
            if now >= end:
                # Resolve the linked asset for hero_slides cleanup
                linked_id = banner.get("asset_id")
                linked_asset = None
                if linked_id:
                    linked_asset = await db.marketing_assets.find_one({"id": linked_id}, {"_id": 0})
                await _unpublish_placement(db, "promo_banner", asset=linked_asset)
                # Also clear the published_to flag on the linked asset so the
                # admin gallery card no longer shows "PUBLISHED → PROMO BANNER".
                if linked_id:
                    await db.marketing_assets.update_one(
                        {"id": linked_id},
                        {"$set": {
                            "published_to": None,
                            "auto_unpublished_at": now.isoformat(),
                            "auto_unpublished_reason": f"scheduled_end {banner['scheduled_end']} passed",
                        }},
                    )
                logger.info(
                    "[auto-unpublish] promo_banner scheduled_end %s elapsed — unpublished asset %s",
                    banner["scheduled_end"], linked_id or "(no link)",
                )
                flipped += 1
        except Exception as e:
            logger.warning("[auto-unpublish] failed to parse scheduled_end %r: %s",
                           banner.get("scheduled_end"), e)

    # Homepage hero — same pattern but reading page_content.homepage
    hp = await db.page_content.find_one({"page_key": "homepage"}, {"_id": 0})
    content = (hp or {}).get("content") or {}
    hero_end = content.get("hero_auto_unpublish_at")
    if content.get("hero_image") and hero_end:
        try:
            end = datetime.fromisoformat(str(hero_end).replace("Z", "+00:00"))
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
            if now >= end:
                linked_id = content.get("hero_asset_id")
                linked_asset = None
                if linked_id:
                    linked_asset = await db.marketing_assets.find_one({"id": linked_id}, {"_id": 0})
                await _unpublish_placement(db, "homepage_hero", asset=linked_asset)
                if linked_id:
                    await db.marketing_assets.update_one(
                        {"id": linked_id},
                        {"$set": {
                            "published_to": None,
                            "auto_unpublished_at": now.isoformat(),
                        }},
                    )
                logger.info("[auto-unpublish] homepage hero auto-end %s elapsed", hero_end)
                flipped += 1
        except Exception as e:
            logger.warning("[auto-unpublish] failed to parse hero auto-end %r: %s", hero_end, e)

    return flipped


async def auto_unpublish_loop(db) -> None:
    """Forever-loop: scan once per minute, log + sleep."""
    logger.info("[auto-unpublish] background task started (interval=%ds)", CHECK_INTERVAL_SECONDS)
    # Small initial delay so we don't race with other startup tasks
    await asyncio.sleep(15)
    while True:
        try:
            n = await _run_one_pass(db)
            if n:
                logger.info("[auto-unpublish] flipped %d expired placement(s)", n)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("[auto-unpublish] pass crashed; will retry next interval")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)

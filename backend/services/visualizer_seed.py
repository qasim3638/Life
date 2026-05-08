"""
Auto-seed for visualizer sample rooms.

Importable helper that idempotently inserts the curated sample rooms
defined in `scripts/seed_visualizer_rooms.py` whenever the
`visualizer_sample_rooms` collection is empty. Called from server.py
startup so a fresh Railway deploy auto-populates the rooms — no
manual `python scripts/seed_visualizer_rooms.py` step needed.

Idempotent by design: if any rooms already exist (active or not),
we skip seeding entirely so admins can curate the list without
having their changes overwritten on the next deploy. Use the
`force=True` kwarg from the admin "Re-seed defaults" button to
upsert the canonical set on top of whatever's there.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from scripts.seed_visualizer_rooms import ROOMS

logger = logging.getLogger(__name__)


async def seed_visualizer_rooms_if_empty(db, force: bool = False) -> dict:
    """Seed the curated visualizer rooms.

    Returns a dict with `seeded` (count upserted) and `skipped` (bool —
    True when the collection was non-empty and force=False).
    """
    existing = await db.visualizer_sample_rooms.count_documents({})
    if existing > 0 and not force:
        return {"seeded": 0, "skipped": True, "existing": existing}

    upserted = 0
    now_iso = datetime.now(timezone.utc).isoformat()
    for room in ROOMS:
        doc = dict(room)
        doc["created_at"] = doc.get("created_at") or now_iso
        doc["updated_at"] = now_iso
        await db.visualizer_sample_rooms.update_one(
            {"id": doc["id"]},
            {"$set": doc},
            upsert=True,
        )
        upserted += 1
    logger.info("[visualizer-seed] upserted %d sample rooms (force=%s)", upserted, force)
    return {"seeded": upserted, "skipped": False, "existing": existing}

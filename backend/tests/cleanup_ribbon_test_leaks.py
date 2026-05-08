"""Purge test-leak messages from the live announcement ribbon.

Background (30-Apr-2026)
------------------------
An earlier version of `test_announcement_ribbon_history.py` PUT literal
test strings (TEST_PRESERVE_fields, TEST_CAP_entry_*, TEST_E2E_REPUB_*)
directly against the live admin endpoint with no teardown. When the test
run left `enabled=True`, customers saw the test string scrolling across
the top of tilestation.co.uk.

This module safely purges any ribbon corruption:

  1. Reads `website_settings` doc where `message` starts with any known
     test prefix (`TEST_`, `_E1_TEST_`).
  2. Blanks the `message` field and sets `enabled=False` so the ribbon
     stops rendering until an admin re-publishes a real announcement.
  3. Strips any `history[]` entries whose `message` starts with a test
     prefix (keeps real historical messages intact).
  4. Stamps `updated_by: system-cleanup-test-leak` for audit.

Usage
-----
As a CLI (preview or one-off prod shell):
    cd /app/backend && set -a && source .env && set +a && \
      python tests/cleanup_ribbon_test_leaks.py [--dry-run]

As a scheduled job:
    from services.scheduler adds a nightly `ribbon_leak_cleanup` that
    calls `cleanup_ribbon_test_leaks(dry_run=False)` once a day — belt
    and braces in case a future test file is careless.
"""
import asyncio
import os
import sys
from datetime import datetime, timezone
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient


TEST_PREFIXES = ("TEST_", "_E1_TEST_")


def _is_test_message(message: Optional[str]) -> bool:
    if not message:
        return False
    return any(str(message).startswith(p) for p in TEST_PREFIXES)


async def cleanup_ribbon_test_leaks(
    db=None,
    *,
    dry_run: bool = False,
    logger=None,
) -> dict:
    """Purge any TEST_ / _E1_TEST_ leaks from the announcement ribbon.

    Args:
      db: Optional Motor database handle. If None, opens one using the
          `MONGO_URL` + `DB_NAME` env vars (CLI mode).
      dry_run: If True, logs what would change without writing.
      logger: Optional logger; falls back to print when absent.

    Returns:
      {
        "docs_inspected": int,
        "docs_cleaned": int,
        "history_entries_pruned": int,
        "dry_run": bool,
      }
    """
    def _log(msg: str) -> None:
        if logger is not None:
            logger.info(msg)
        else:
            print(msg)

    owns_client = False
    client = None
    if db is None:
        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME")
        if not mongo_url or not db_name:
            raise RuntimeError(
                "MONGO_URL and DB_NAME env vars required when db is not supplied"
            )
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        owns_client = True

    try:
        candidates = []
        # Shape B (top-level message field — the one hit on 30-Apr-2026)
        async for doc in db.website_settings.find({"message": {"$exists": True}}):
            candidates.append(doc)
        # Shape A (nested under `value`)
        async for doc in db.website_settings.find({"key": "announcement_ribbon"}):
            if not any(c.get("_id") == doc.get("_id") for c in candidates):
                candidates.append(doc)

        docs_cleaned = 0
        history_pruned = 0

        for doc in candidates:
            if isinstance(doc.get("value"), dict) and "message" in doc["value"]:
                container_key: Optional[str] = "value"
                container = doc["value"]
            elif "message" in doc:
                container_key = None
                container = doc
            else:
                continue

            msg = container.get("message")
            hist = container.get("history") or []

            updates: dict = {}
            dirty = False

            if _is_test_message(msg):
                _log(f"  • message '{msg}' → blank (disabling ribbon)")
                prefix = f"{container_key}." if container_key else ""
                updates[f"{prefix}message"] = ""
                updates[f"{prefix}enabled"] = False
                updates[f"{prefix}updated_at"] = datetime.now(timezone.utc).isoformat()
                updates[f"{prefix}updated_by"] = "system-cleanup-test-leak"
                dirty = True

            clean_hist = [h for h in hist if not _is_test_message(h.get("message"))]
            removed = len(hist) - len(clean_hist)
            if removed > 0:
                _log(
                    f"  • history: removing {removed} test entr"
                    f"{'y' if removed == 1 else 'ies'}"
                )
                prefix = f"{container_key}." if container_key else ""
                updates[f"{prefix}history"] = clean_hist
                dirty = True
                history_pruned += removed

            if dirty:
                docs_cleaned += 1
                if dry_run:
                    _log(f"  [DRY-RUN] Would update doc _id={doc.get('_id')}")
                    continue
                await db.website_settings.update_one(
                    {"_id": doc["_id"]}, {"$set": updates}
                )
                _log(f"  ✓ Updated doc _id={doc.get('_id')}")

        return {
            "docs_inspected": len(candidates),
            "docs_cleaned": docs_cleaned,
            "history_entries_pruned": history_pruned,
            "dry_run": dry_run,
        }
    finally:
        if owns_client and client is not None:
            client.close()


async def _cli(dry_run: bool) -> int:
    try:
        result = await cleanup_ribbon_test_leaks(dry_run=dry_run)
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return 2

    print()
    print(
        f"Summary: inspected {result['docs_inspected']} doc(s), "
        f"cleaned {result['docs_cleaned']}, "
        f"pruned {result['history_entries_pruned']} history entr"
        f"{'y' if result['history_entries_pruned'] == 1 else 'ies'}."
    )
    if dry_run:
        print("DRY-RUN mode — no writes performed. Re-run without --dry-run to apply.")
    return 0


if __name__ == "__main__":
    is_dry = "--dry-run" in sys.argv
    sys.exit(asyncio.run(_cli(is_dry)))

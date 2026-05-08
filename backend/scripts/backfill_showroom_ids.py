"""
One-shot migration: backfill `id` for legacy showroom documents.

Background
----------
Two "coming soon" showroom docs in production have no `id` field (only Mongo
`_id`). That caused:

  - `GET /api/historical-sales/manual-entries` to 500 (`KeyError: 'id'`).
  - React duplicate-key warnings on the admin dashboard where 4 `<select>`s
    map showrooms with `key={s.id}`.

The request/response paths now defensively backfill `id ← str(_id)` at read
time. This script writes that same value *into the DB* so the data is clean
at the source — once that's done, the defensive guards become belt-and-braces.

Usage
-----
    cd /app/backend
    python -m scripts.backfill_showroom_ids             # dry-run by default
    python -m scripts.backfill_showroom_ids --apply     # actually write

The script is idempotent: running it again is a no-op once every doc has
a non-empty `id`.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any

# Ensure backend/ is on sys.path so `database` and siblings import cleanly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


async def main(apply: bool) -> int:
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        print("ERROR: MONGO_URL or DB_NAME missing from env.", file=sys.stderr)
        return 2

    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    # Target: docs where `id` is absent or empty ('', None)
    query: dict[str, Any] = {
        "$or": [
            {"id": {"$exists": False}},
            {"id": {"$in": ["", None]}},
        ]
    }

    total = await db.showrooms.count_documents({})
    broken = await db.showrooms.count_documents(query)
    print(f"Total showrooms: {total}")
    print(f"Showrooms missing a proper `id`: {broken}")

    if broken == 0:
        print("Nothing to do — dataset already clean.")
        return 0

    fixed = 0
    failed = 0
    async for doc in db.showrooms.find(query):
        _id = doc.get("_id")
        new_id = str(_id) if _id else None
        name = doc.get("name", "<unnamed>")
        if not new_id:
            failed += 1
            print(f"  - SKIP '{name}' (no _id either — should be impossible)")
            continue
        print(f"  - {'WOULD SET' if not apply else 'SET'} id={new_id!r} for '{name}'")
        if apply:
            result = await db.showrooms.update_one(
                {"_id": _id},
                {"$set": {"id": new_id}},
            )
            if result.modified_count != 1:
                failed += 1
                print(f"    (expected 1 modification, got {result.modified_count})")
                continue
        fixed += 1

    print()
    mode = "APPLIED" if apply else "DRY-RUN"
    print(f"[{mode}] fixed={fixed}, failed={failed}")
    if not apply:
        print("Pass --apply to actually write the changes.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="Write changes (default is dry-run).")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(apply=args.apply)))

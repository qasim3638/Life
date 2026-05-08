"""Seed a synthetic SMOKETEST auto-promote + timeline rows to verify
the populated Attribution table UI, then clean up. Safe against live DB."""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/app/backend")
from motor.motor_asyncio import AsyncIOMotorClient


async def main(action: str):
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    now = datetime.now(timezone.utc)
    marker = "SMOKETEST_attr_timeline"

    if action == "seed":
        await db.seo_stealth_auto_promotes.insert_one({
            "id": marker,
            "query": "SMOKETEST spanish tiles",
            "scope": "collection",
            "collection": "SMOKETEST",
            "added_keyword": "SMOKETEST spanish tiles",
            "promoted_at": now - timedelta(days=10),
            "undone_at": None,
            "impressions": 100,
            "smoketest": True,
        })
        # 3 cache rows
        for offset, clicks, imps in [(2, 6, 80), (5, 4, 50), (8, 8, 100)]:
            await db.seo_stealth_kw_timeline.insert_one({
                "keyword_lower": "smoketest spanish tiles",
                "keyword": "SMOKETEST spanish tiles",
                "date": (now - timedelta(days=offset)).date().isoformat(),
                "clicks": clicks, "impressions": imps,
                "ctr": clicks / imps, "position": 3.2,
                "cached_at": now,
                "smoketest": True,
            })
        print("Seeded")
    elif action == "clean":
        r1 = await db.seo_stealth_auto_promotes.delete_many(
            {"$or": [{"smoketest": True}, {"id": marker}]}
        )
        r2 = await db.seo_stealth_kw_timeline.delete_many({"smoketest": True})
        print(f"Cleaned: promotes={r1.deleted_count}, timeline={r2.deleted_count}")
    client.close()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "seed"))

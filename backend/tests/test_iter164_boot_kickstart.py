"""Iter-164 test — the auto orphan-slide cleanup on backend boot.

Setup:
  1. Insert a marketing_asset with deleted=True and a unique image_url.
  2. Insert a hero_slide whose `image` matches that asset's image_url,
     without source/asset_id tags (legacy untagged slide — the real
     BANK HOLIDAY scenario).
  3. Restart backend via supervisorctl.
  4. Sleep 30s (kickstart waits 20s + one pass).
  5. Confirm slide gone + log line present.
"""
import asyncio
import os
import subprocess
import time
import uuid

from dotenv import load_dotenv

load_dotenv("/app/backend/.env")


async def _conn():
    from motor.motor_asyncio import AsyncIOMotorClient
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return cli, cli[os.environ["DB_NAME"]]


async def run():
    cli, db = await _conn()
    marker = uuid.uuid4().hex[:10]
    aid = f"ITER164ORPHAN-{marker}"
    img = f"https://example.com/iter164-orphan-{marker}.png"
    try:
        # 1. Fake marketing asset (deleted)
        await db.marketing_assets.insert_one({
            "id": aid, "model": "nano-banana", "prompt": "iter164 orphan test",
            "image_url": img, "width": 1600, "height": 600, "cost_usd": 0.04,
            "deleted": True, "published_to": None,
            "created_at": "2026-05-03T00:00:00+00:00",
        })
        # 2. Orphan slide pointing to it (untagged)
        await db.hero_slides.insert_one({
            "id": str(uuid.uuid4()),
            "title": f"ITER164-ORPHAN-{marker}",
            "subtitle": "", "badge": "", "image": img,
            "is_active": True, "sort_order": 50,
        })
        # sanity: inserted
        n0 = await db.hero_slides.count_documents({"image": img})
        print(f"[pre-restart] slides with img: {n0}")
        assert n0 == 1

        # 3. Restart backend
        print("[action] restarting backend via supervisorctl ...")
        subprocess.run(["sudo", "supervisorctl", "restart", "backend"], check=True)

        # 4. Wait for kickstart (20s sleep + scan time)
        print("[wait] sleeping 32s for kickstart ...")
        time.sleep(32)

        # 5. Verify gone
        n1 = await db.hero_slides.count_documents({"image": img})
        print(f"[post-restart] slides with img: {n1}")

        # Look for log line
        log = subprocess.run(
            ["tail", "-n", "400", "/var/log/supervisor/backend.out.log"],
            capture_output=True, text=True,
        ).stdout
        log_err = subprocess.run(
            ["tail", "-n", "400", "/var/log/supervisor/backend.err.log"],
            capture_output=True, text=True,
        ).stdout
        combined = log + "\n" + log_err
        seen_log = "[orphan-slides]" in combined
        print(f"[log-line] '[orphan-slides]' seen: {seen_log}")
        # Print matching lines for debugging
        for ln in combined.splitlines():
            if "orphan-slides" in ln:
                print("  ", ln)

        assert n1 == 0, "kickstart did NOT remove the orphan slide"
        print("PASS: auto-cleanup on boot works")
    finally:
        # Cleanup leftovers
        await db.hero_slides.delete_many({"image": img})
        await db.marketing_assets.delete_one({"id": aid})
        cli.close()


if __name__ == "__main__":
    asyncio.run(run())

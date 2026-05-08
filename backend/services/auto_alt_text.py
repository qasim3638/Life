"""
Auto image alt-text generation — fully autonomous.

Triggered:
  • On every new image attached to a tile (called from product save handler).
  • Backfill cron — once daily at 04:00 Europe/London, processes any
    images where alt_text is missing.

Strategy:
  • Use the Emergent LLM key (Gemini-3 Pro vision) to describe each image
    in 8-14 words, including the tile's name + key spec for SEO weight.
  • Cache the alt text inside the existing `tiles.images` array entry so
    the storefront / sitemap can read it without another LLM call.
  • Failure mode: if the LLM call fails for any reason, fall back to a
    deterministic templated alt that at least includes the product name
    + colour + size — never leave alt empty (accessibility + SEO floor).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from config import get_db

logger = logging.getLogger(__name__)


def _fallback_alt(tile: dict[str, Any]) -> str:
    bits = [
        tile.get("name") or "Tile",
        tile.get("colour") or tile.get("color") or "",
        tile.get("size") or "",
        tile.get("finish") or "",
    ]
    txt = " ".join(b for b in bits if b).strip()
    return f"{txt} — Tile Station UK".strip(" —")


async def _describe_image_with_gemini(*, image_url: str, tile: dict[str, Any]) -> str | None:
    """One Gemini vision call. Returns None on any failure (caller falls
    back to the deterministic alt)."""
    try:
        from emergentintegrations.llm.chat import LlmChat, ImageContent, UserMessage
        import os
        key = os.environ.get("EMERGENT_LLM_KEY")
        if not key:
            return None
        chat = LlmChat(
            api_key=key,
            session_id=f"alt-{tile.get('id') or tile.get('sku')}",
            system_message=(
                "You write SEO-optimised alt text for tile e-commerce images. "
                "Return 8 to 14 words, no quotes, no full stop at end. "
                "Mention the tile name, colour, finish, and one visible feature. "
                "Never say 'image of' or 'picture of'."
            ),
        ).with_model("gemini", "gemini-2.5-pro")
        prompt = (
            f"Tile name: {tile.get('name', 'unknown')}. "
            f"Colour: {tile.get('colour') or tile.get('color') or 'n/a'}. "
            f"Size: {tile.get('size') or 'n/a'}. "
            f"Finish: {tile.get('finish') or 'n/a'}. "
            f"Write the alt text now:"
        )
        msg = UserMessage(text=prompt, file_contents=[ImageContent(image_url=image_url)])
        result = await chat.send_message(msg)
        text = (str(result) or "").strip().strip('"').strip("'")
        # Defensive trim — sometimes the model returns a sentence + tail.
        text = text.split("\n")[0]
        words = text.split()
        if 4 <= len(words) <= 30:
            return text
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gemini alt-text generation failed: %s", exc)
    return None


async def generate_alt_for_tile(tile_id: str, *, force: bool = False) -> dict[str, Any]:
    """Generate alt text for every image on one tile. Idempotent — skips
    images that already have alt unless force=True."""
    db = get_db()
    tile = await db.tiles.find_one({"id": tile_id}) or await db.tiles.find_one({"_id": tile_id})
    if not tile:
        return {"ok": False, "reason": "tile_not_found"}

    images = tile.get("images") or []
    if not images and tile.get("image_url"):
        images = [{"url": tile["image_url"]}]

    updated_images = []
    written = 0
    for img in images:
        # Normalise — some legacy rows store a plain URL string.
        if isinstance(img, str):
            img = {"url": img}
        if not isinstance(img, dict) or not img.get("url"):
            continue
        if not force and img.get("alt"):
            updated_images.append(img)
            continue
        alt = await _describe_image_with_gemini(image_url=img["url"], tile=tile)
        if not alt:
            alt = _fallback_alt(tile)
        img = {**img, "alt": alt, "alt_generated_at": datetime.now(timezone.utc)}
        updated_images.append(img)
        written += 1

    if written:
        await db.tiles.update_one(
            {"id": tile_id} if tile.get("id") == tile_id else {"_id": tile_id},
            {"$set": {"images": updated_images, "alt_text_updated_at": datetime.now(timezone.utc)}},
        )
    return {"ok": True, "tile_id": tile_id, "written": written, "total_images": len(updated_images)}


async def run_alt_text_backfill_tick(limit: int = 50) -> dict[str, Any]:
    """Daily backfill — fix up to `limit` tiles whose images lack alt
    text. Limit prevents a runaway LLM bill if 1000 products land in
    one go."""
    db = get_db()
    cursor = db.tiles.find(
        {"is_active": True},
        {"_id": 0, "id": 1, "images": 1, "image_url": 1, "name": 1, "colour": 1, "color": 1,
         "size": 1, "finish": 1, "sku": 1},
    )
    needs: list[str] = []
    async for t in cursor:
        imgs = t.get("images") or []
        if not imgs and t.get("image_url"):
            imgs = [{"url": t["image_url"]}]
        for img in imgs:
            if isinstance(img, str):
                img = {"url": img}
            if isinstance(img, dict) and img.get("url") and not img.get("alt"):
                needs.append(t.get("id"))
                break
        if len(needs) >= limit:
            break

    processed = 0
    for tid in needs:
        try:
            res = await generate_alt_for_tile(tid)
            if res.get("ok"):
                processed += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("alt backfill error for %s: %s", tid, exc)
        # gentle throttle so we don't hammer the LLM key
        await asyncio.sleep(0.3)
    return {"ok": True, "considered": len(needs), "processed": processed}

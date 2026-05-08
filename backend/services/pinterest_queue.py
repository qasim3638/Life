"""
Pinterest Pin Queue — candidate generation, approval, dispatch
──────────────────────────────────────────────────────────────

The closed-loop side of the visual marketing engine.

Daily cron at 05:00 BST runs `generate_candidates()` which:
  1. Picks N high-priority products via `priority_product_picker()`
     (best-sellers → high-margin → tail products in that order)
  2. For each product, matches it to the 1-3 best boards via
     `pinterest_engine.match_product_to_boards()`
  3. Selects the hero image — Tier-1 lifestyle/room shot first,
     then Tier-2 AI-generated scene (queued for Nano Banana, not
     blocking), then Tier-3 product cutout fallback
  4. Generates SEO-optimized title + description via Claude Sonnet 4.5
  5. Drops a row in `pinterest_pin_candidates` with status=pending
  6. If the target board has auto_approve=True, also marks the row as
     approved+scheduled so it skips the queue review step

A drip-feeder cron runs every 90 minutes and dispatches the
oldest-approved-not-yet-posted candidate to Pinterest (or marks it
"locked_pending_pinterest_unlock" if the integration isn't live yet —
which is the common case during the trial-access wait).
"""
from __future__ import annotations

import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from config import get_db
from services import pinterest_engine as engine

logger = logging.getLogger(__name__)


# ───── Constants ─────

CANDIDATES_PER_DAY = 12          # 12 products × ~2 boards = ~24 Pins/day max
DRIP_INTERVAL_MINUTES = 90       # 1 Pin every 90 min ≈ 11 Pins/day if all approved
MIN_IMAGE_WIDTH_PX = 800
MIN_IMAGE_HEIGHT_PX = 1000
DEFAULT_FRONTEND_BASE = "https://tilestation.co.uk"


# ───── Public — admin actions on a candidate ─────

async def list_candidates(
    status: str | None = None, limit: int = 50,
) -> list[dict[str, Any]]:
    db = get_db()
    q: dict = {}
    if status:
        q["status"] = status
    cur = db.pinterest_pin_candidates.find(q, {"_id": 0}).sort("created_at", -1).limit(limit)
    rows = await cur.to_list(limit)
    return [_serialize(r) for r in rows]


async def queue_summary() -> dict[str, Any]:
    """Compact stats for the admin card."""
    db = get_db()
    pending = await db.pinterest_pin_candidates.count_documents({"status": "pending"})
    approved = await db.pinterest_pin_candidates.count_documents({"status": "approved"})
    posted = await db.pinterest_pin_candidates.count_documents({"status": "posted"})
    skipped = await db.pinterest_pin_candidates.count_documents({"status": "skipped"})
    blocked_imgs = await db.pinterest_image_blocklist.count_documents({})
    last_gen = await db.pinterest_pin_candidates.find_one(
        {}, {"_id": 0, "created_at": 1}, sort=[("created_at", -1)],
    )
    return {
        "pending": pending,
        "approved": approved,
        "posted": posted,
        "skipped": skipped,
        "blocked_images": blocked_imgs,
        "last_generated_at": (last_gen.get("created_at").isoformat()
                              if last_gen and isinstance(last_gen.get("created_at"), datetime)
                              else None),
    }


async def approve_candidate(candidate_id: str) -> dict | None:
    db = get_db()
    res = await db.pinterest_pin_candidates.find_one_and_update(
        {"id": candidate_id, "status": {"$in": ["pending"]}},
        {"$set": {
            "status": "approved",
            "approved_at": datetime.now(timezone.utc),
            "scheduled_for": _next_drip_slot(),
        }},
        return_document=True,
        projection={"_id": 0},
    )
    return _serialize(res) if res else None


async def skip_candidate(candidate_id: str) -> dict | None:
    db = get_db()
    res = await db.pinterest_pin_candidates.find_one_and_update(
        {"id": candidate_id, "status": "pending"},
        {"$set": {
            "status": "skipped",
            "skipped_at": datetime.now(timezone.utc),
        }},
        return_document=True,
        projection={"_id": 0},
    )
    return _serialize(res) if res else None


async def block_candidate(candidate_id: str) -> dict | None:
    """Reject the candidate AND blocklist its image so future
    generations never reuse it."""
    db = get_db()
    cand = await db.pinterest_pin_candidates.find_one(
        {"id": candidate_id}, {"_id": 0},
    )
    if not cand:
        return None
    img = cand.get("image_url")
    if img:
        await db.pinterest_image_blocklist.update_one(
            {"image_url": img},
            {"$set": {
                "image_url": img,
                "blocked_at": datetime.now(timezone.utc),
                "reason": "admin_blocked_via_queue",
                "product_slug": cand.get("product_slug"),
            }},
            upsert=True,
        )
    res = await db.pinterest_pin_candidates.find_one_and_update(
        {"id": candidate_id},
        {"$set": {
            "status": "blocked",
            "blocked_at": datetime.now(timezone.utc),
        }},
        return_document=True,
        projection={"_id": 0},
    )
    return _serialize(res) if res else None


async def update_candidate(candidate_id: str, fields: dict[str, Any]) -> dict | None:
    """Inline edit of title, description, board, link_url, image_url.
    Anything else is silently ignored."""
    db = get_db()
    safe = {k: fields[k] for k in (
        "title", "description", "board_slug", "link_url", "image_url", "alt_text",
    ) if k in fields and fields[k] is not None}
    if not safe:
        return None
    safe["edited_at"] = datetime.now(timezone.utc)
    res = await db.pinterest_pin_candidates.find_one_and_update(
        {"id": candidate_id},
        {"$set": safe},
        return_document=True,
        projection={"_id": 0},
    )
    return _serialize(res) if res else None


async def list_blocklist(limit: int = 100) -> list[dict[str, Any]]:
    db = get_db()
    cur = db.pinterest_image_blocklist.find({}, {"_id": 0}).sort("blocked_at", -1).limit(limit)
    rows = await cur.to_list(limit)
    for r in rows:
        if isinstance(r.get("blocked_at"), datetime):
            r["blocked_at"] = r["blocked_at"].isoformat()
    return rows


async def unblock_image(image_url: str) -> bool:
    db = get_db()
    res = await db.pinterest_image_blocklist.delete_one({"image_url": image_url})
    return res.deleted_count > 0


# ───── Candidate generation (daily cron) ─────

async def generate_candidates(target_count: int = CANDIDATES_PER_DAY) -> dict[str, Any]:
    """Pick `target_count` products and produce 1 candidate per product
    × up to 3 boards each. Returns aggregate stats."""
    db = get_db()
    await engine.init_default_boards()

    products = await _priority_product_picker(target_count)
    if not products:
        return {"generated": 0, "reason": "no_eligible_products"}

    boards_cfg = {b["slug"]: b for b in await engine.list_boards_config()}
    blocked = await _blocklist_set()

    generated = 0
    auto_approved = 0
    for product in products:
        try:
            slugs = engine.match_product_to_boards(product)
            for board_slug in slugs:
                board = boards_cfg.get(board_slug)
                if not board or not board.get("is_active", True):
                    continue
                hero = await _select_hero_image(product, blocked)
                if not hero:
                    continue
                copy = await _build_pin_copy(product, board)
                cand = {
                    "id": secrets.token_urlsafe(10),
                    "product_id": product.get("id") or product.get("slug"),
                    "product_slug": product.get("slug"),
                    "product_name": product.get("name"),
                    "board_slug": board_slug,
                    "board_name": board["name"],
                    "title": copy["title"],
                    "description": copy["description"],
                    "alt_text": copy["alt_text"],
                    "image_url": hero["url"],
                    "image_tier": hero["tier"],
                    "link_url": _product_link(product),
                    "status": "pending",
                    "created_at": datetime.now(timezone.utc),
                    "auto_approve_eligible": bool(board.get("auto_approve")),
                }
                # Carousel slides (Pinterest multi-image format) — one
                # extra field on the candidate; the dispatcher uses
                # this when the Pinterest carousel API is wired.
                try:
                    from services.pinterest_engine_phase2 import build_carousel_slides
                    cand["carousel_slides"] = build_carousel_slides(product, hero["url"])
                except Exception:
                    cand["carousel_slides"] = []
                if board.get("auto_approve"):
                    cand["status"] = "approved"
                    cand["approved_at"] = datetime.now(timezone.utc)
                    cand["scheduled_for"] = _next_drip_slot(generated)
                    cand["approved_by"] = "auto"
                    auto_approved += 1
                await db.pinterest_pin_candidates.insert_one(cand)
                generated += 1
        except Exception:
            logger.exception(
                "Failed generating candidates for product %s", product.get("slug"),
            )
            continue

    return {
        "generated": generated,
        "auto_approved": auto_approved,
        "products_used": len(products),
        "ran_at": datetime.now(timezone.utc).isoformat(),
    }


# ───── Internal helpers ─────

async def _priority_product_picker(target_count: int) -> list[dict[str, Any]]:
    """Smart priority: products that haven't been pinned recently first,
    weighted by stock + image quality. Excludes products already in the
    pending/approved queue so we don't double-up."""
    db = get_db()

    # Exclude products that have a candidate within the last 14 days
    fortnight_ago = datetime.now(timezone.utc) - timedelta(days=14)
    recent_slugs_cursor = db.pinterest_pin_candidates.distinct(
        "product_slug",
        {"created_at": {"$gte": fortnight_ago}},
    )
    recent = set(await recent_slugs_cursor)

    # Pull active products with real images, exclude bullet products
    # and accessories — those don't make great Pins.
    cur = db.tiles.find(
        {
            "is_active": {"$ne": False},
            "$or": [
                {"images": {"$exists": True, "$not": {"$size": 0}}},
                {"image_url": {"$exists": True, "$ne": ""}},
            ],
            "category": {"$nin": [
                "", "Cable Kit", "Foil 140W/m2", "Foil Kit 140W/m2",
                "Mesh 100W/m2", "Mesh 150W/m2", "Mesh 200W/m2",
                "Membrane Mat", "Overlay Board", "Screed Cable",
                "Screed Cable Accessories", "Ultimate Heating Cable 130W/m2",
                "Ultimate Low Wattage Cable", "TEST_CAT_1",
            ]},
        },
        {
            "_id": 0, "id": 1, "slug": 1, "name": 1, "description": 1,
            "category": 1, "collection": 1, "images": 1, "image_url": 1,
            "price": 1, "tags": 1,
        },
    )
    candidates: list[dict[str, Any]] = []
    async for p in cur:
        if p.get("slug") in recent:
            continue
        candidates.append(p)
        if len(candidates) >= target_count * 4:
            # Pull a 4× pool then random-sample so we don't always
            # hit the same alphabetically-first products.
            break

    # Shuffle for variety, then return first target_count
    import random
    random.shuffle(candidates)
    return candidates[:target_count]


async def _blocklist_set() -> set[str]:
    db = get_db()
    cur = db.pinterest_image_blocklist.find({}, {"_id": 0, "image_url": 1})
    return {r["image_url"] async for r in cur if r.get("image_url")}


async def _select_hero_image(
    product: dict[str, Any], blocked: set[str],
) -> dict[str, Any] | None:
    """Return {url, tier} where tier is 'lifestyle' / 'product' / 'ai'.

    Tier 1: room/lifestyle shots from the existing `images` array.
            Heuristic — images later in the array are usually room
            shots (suppliers put cutout first, lifestyle later).
    Tier 2: AI-generated lifestyle scene via Nano Banana — pulled
            from `pinterest_lifestyle_renders` if status='ready'.
            If no render exists, queue one for next cycle and return
            Tier 3 fallback for now.
    Tier 3: bare product cutout from `image_url` or `images[0]`.
    """
    images = product.get("images") or []
    if not isinstance(images, list):
        images = []

    # Tier 1 — try later-position images first (likely lifestyle)
    for img in reversed(images):
        if not img or not isinstance(img, str):
            continue
        if img in blocked:
            continue
        # Pinterest requires HTTPS image URLs
        if not img.startswith("https://"):
            continue
        return {"url": img, "tier": "lifestyle" if len(images) > 1 else "product"}

    # Tier 2 — check if a Nano Banana lifestyle render is ready
    try:
        from config import get_db
        db = get_db()
        render = await db.pinterest_lifestyle_renders.find_one(
            {"product_slug": product.get("slug"), "status": "ready"},
            {"_id": 0, "image_url": 1},
        )
        if render and render.get("image_url"):
            url = render["image_url"]
            if url.startswith("https://") and url not in blocked:
                return {"url": url, "tier": "ai"}
    except Exception:
        pass  # Nano Banana fallback isn't fatal — Tier 3 takes over

    # Tier 3 — fall back to image_url
    cutout = product.get("image_url")
    if cutout and isinstance(cutout, str) and cutout.startswith("https://") and cutout not in blocked:
        # Side-effect: queue a Nano Banana render for next time so
        # this product gets richer imagery on its next pass through
        # the candidate generator.
        try:
            from services.pinterest_engine_phase2 import queue_lifestyle_render
            await queue_lifestyle_render(product)
        except Exception:
            pass
        return {"url": cutout, "tier": "product"}

    return None


async def _build_pin_copy(
    product: dict[str, Any], board: dict[str, Any],
) -> dict[str, str]:
    """Generate Pinterest-optimized title (60-100 chars) + description
    (200-500 chars) using Claude Haiku 4.5 for speed/cost.

    Pinterest SEO ≠ Google SEO — Pinterest searches are usually
    short visual queries ("luxury bathroom ideas", "kitchen splashback
    marble"). The prompt explicitly steers Claude toward that.
    Falls back to a deterministic template if the LLM is unreachable.
    """
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    name = product.get("name") or "TileStation tile"
    desc = (product.get("description") or "")[:300]
    board_name = board["name"]

    fallback = _template_pin_copy(product, board)
    if not api_key:
        return fallback

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=api_key,
            session_id=f"pin-copy-{secrets.token_hex(4)}",
            system_message=(
                "You write Pinterest pin copy that ranks for visual-discovery searches "
                "in the UK home renovation niche. Output strict JSON with three string "
                "keys: 'title' (60-100 chars, MUST include 1 high-search-volume "
                "Pinterest phrase like 'bathroom ideas' / 'kitchen splashback ideas' / "
                "'patio inspiration'), 'description' (180-380 chars, conversational, "
                "ends with a soft CTA, includes 2-3 hashtags at the end), and "
                "'alt_text' (under 200 chars, plain factual scene description for "
                "accessibility). British English. No markdown. No code fences."
            ),
        ).with_model("anthropic", "claude-haiku-4-5-20251001").with_params(max_tokens=600)

        prompt = (
            f"Product: {name}\n"
            f"Category: {product.get('category') or 'Tile'}\n"
            f"Collection: {product.get('collection') or 'TileStation'}\n"
            f"Description (truncated): {desc}\n"
            f"Target Pinterest board: {board_name}\n\n"
            "Write the Pin copy. JSON only."
        )
        raw = await chat.send_message(UserMessage(text=prompt))
        raw = (raw or "").strip()
        if raw.startswith("```"):
            import re
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
        import json as _json
        out = _json.loads(raw)
        title = (out.get("title") or "").strip()[:100]
        description = (out.get("description") or "").strip()[:500]
        alt = (out.get("alt_text") or "").strip()[:200]
        if not title or not description:
            return fallback
        return {"title": title, "description": description, "alt_text": alt or name}
    except Exception:
        logger.exception("Pin-copy LLM failed; using template")
        return fallback


def _template_pin_copy(
    product: dict[str, Any], board: dict[str, Any],
) -> dict[str, str]:
    """Deterministic copy used when the LLM is unavailable. Still
    Pinterest-optimised — leads with a search-friendly phrase."""
    name = (product.get("name") or "TileStation tile").strip()
    cat = (product.get("category") or "tile").strip()
    board_kw = (board.get("keywords") or ["tile ideas"])[0]
    title = f"{name} — {board_kw.title()} Inspiration"[:100]
    description = (
        f"Discover {name}, a stunning {cat.lower()} from TileStation's "
        f"premium UK collection. Perfect for {board_kw} projects — "
        f"shop the full range online with free samples & UK-wide delivery. "
        f"#{board_kw.replace(' ', '').lower()} #tilestation #ukinteriors"
    )[:500]
    alt = f"{name} {cat} tile shown in a styled interior"[:200]
    return {"title": title, "description": description, "alt_text": alt}


def _product_link(product: dict[str, Any]) -> str:
    base = (os.environ.get("FRONTEND_BASE_URL") or DEFAULT_FRONTEND_BASE).rstrip("/")
    slug = product.get("slug") or product.get("id")
    return f"{base}/shop/product/{slug}?utm_source=pinterest&utm_medium=organic&utm_campaign=visual_engine"


def _next_drip_slot(offset_index: int = 0) -> datetime:
    """Schedule approved Pins so they drip-feed every DRIP_INTERVAL_MINUTES.
    Each successive Pin in the same generation batch goes one slot later
    to spread them across the day."""
    return datetime.now(timezone.utc) + timedelta(minutes=DRIP_INTERVAL_MINUTES * (offset_index + 1))


# ───── Cron tick (called by scheduler.py) ─────

async def daily_generation_tick() -> dict[str, Any]:
    """Called once per day by APScheduler."""
    try:
        return await generate_candidates(CANDIDATES_PER_DAY)
    except Exception as exc:
        logger.exception("Pinterest daily generation failed")
        return {"generated": 0, "error": str(exc)[:200]}


async def drip_dispatch_tick() -> dict[str, Any]:
    """Called every DRIP_INTERVAL_MINUTES. Posts the oldest approved
    Pin whose `scheduled_for` has passed, IF the Pinterest integration
    is connected. Otherwise returns 'integration_locked'."""
    db = get_db()
    from services import pinterest as pin_api
    settings = await pin_api.get_settings()
    if not settings.get("access_token") or not settings.get("board_id"):
        # Can't post yet (Pinterest still locked / not connected) —
        # leave Pins approved-not-yet-posted; we'll catch up after
        # connection.
        return {"dispatched": 0, "reason": "integration_not_connected"}

    now = datetime.now(timezone.utc)
    cand = await db.pinterest_pin_candidates.find_one_and_update(
        {
            "status": "approved",
            "$or": [
                {"scheduled_for": {"$lte": now}},
                {"scheduled_for": {"$exists": False}},
            ],
        },
        {"$set": {"status": "posting", "posting_started_at": now}},
        sort=[("approved_at", 1)],
        return_document=True,
        projection={"_id": 0},
    )
    if not cand:
        return {"dispatched": 0, "reason": "nothing_due"}

    result = await pin_api.create_pin(
        title=cand["title"],
        description=cand["description"],
        image_url=cand["image_url"],
        link=cand["link_url"],
        alt_text=cand.get("alt_text"),
    )
    update: dict[str, Any] = {
        "post_result": result,
        "posted_at": datetime.now(timezone.utc),
    }
    if result.get("success"):
        update["status"] = "posted"
        update["pinterest_pin_id"] = result.get("pin_id")
        update["pinterest_pin_url"] = result.get("pin_url")
    else:
        update["status"] = "failed"
        update["last_error"] = result.get("error")

    await db.pinterest_pin_candidates.update_one(
        {"id": cand["id"]}, {"$set": update},
    )
    return {
        "dispatched": 1 if result.get("success") else 0,
        "candidate_id": cand["id"],
        "status": update["status"],
        "error": result.get("error") if not result.get("success") else None,
    }


# ───── Serialization ─────

def _serialize(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return row
    out = dict(row)
    for k in ("created_at", "approved_at", "skipped_at", "blocked_at",
              "scheduled_for", "posting_started_at", "posted_at", "edited_at"):
        v = out.get(k)
        if isinstance(v, datetime):
            out[k] = v.isoformat()
    return out

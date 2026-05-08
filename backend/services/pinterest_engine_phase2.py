"""
Pinterest Visual Engine — Phase 2 helpers
─────────────────────────────────────────

Layered on top of the v1 engine without breaking it. Adds:
  • Seasonal triggers — UK month-of-year → board priority weighting
  • A/B copy variant generation — 2 versions per Pin
  • Repin scheduler — successful Pins re-pinned to a fresh board ~30
    days later (Pinterest rewards account-level consistency)
  • Performance feedback loop — pulls Pin click + repin stats from
    Pinterest API once /day, scores boards/products by engagement,
    biases tomorrow's candidate generator
  • Nano Banana lifestyle scene generator — for products with no
    Tier-1 lifestyle photo, queues an AI scene render so the next
    candidate generation pass can use it
  • Carousel slide builder — 4-slide structure (room hero → close-up
    → product → alt context) for Pinterest's multi-image Pin format
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


# ───── Seasonal triggers (UK calendar) ─────
# UK home renovation/decor seasonality based on Google Trends + ONS
# household-spend data. Each board gets a +/- weight per month so the
# generator picks more bathroom Pins in Jan, more outdoor Pins in
# spring/summer, more kitchen content in autumn (renovation season).
SEASONAL_BOOST: dict[int, dict[str, int]] = {
    1: {  # January — New Year resolutions, gym, "new bathroom" peak
        "bathroom-ideas": 6,
        "luxury-bathroom-suites": 5,
        "design-trends": 3,
        "kitchen-ideas": -1,
        "outdoor-patios": -3,
        "garden-ideas": -3,
        "patio-ideas": -3,
    },
    2: {  # February — bathroom continues; spring planning starts
        "bathroom-ideas": 4,
        "luxury-bathroom-suites": 4,
        "kitchen-ideas": 2,
        "outdoor-patios": -2,
        "garden-ideas": -2,
    },
    3: {  # March — spring DIY; gardens come alive
        "outdoor-patios": 4,
        "garden-ideas": 5,
        "patio-ideas": 4,
        "design-trends": 2,
    },
    4: {  # April — peak garden/patio planning
        "outdoor-patios": 6,
        "garden-ideas": 6,
        "patio-ideas": 5,
        "bathroom-ideas": -1,
    },
    5: {  # May — outdoor spending peaks
        "outdoor-patios": 6,
        "garden-ideas": 5,
        "patio-ideas": 6,
        "luxury-bathroom-suites": -1,
    },
    6: {  # June — outdoor still peak; early summer
        "outdoor-patios": 5,
        "patio-ideas": 5,
        "garden-ideas": 4,
    },
    7: {  # July — summer holidays, slowdown
        "outdoor-patios": 3,
        "patio-ideas": 3,
        "design-trends": 2,
    },
    8: {  # August — slowest renovation month
        "design-trends": 2,
        "whole-home-renovation": 2,
        "outdoor-patios": 1,
    },
    9: {  # September — back-to-school, autumn renovation kicks in
        "kitchen-ideas": 5,
        "bathroom-ideas": 3,
        "design-trends": 4,
        "whole-home-renovation": 4,
    },
    10: {  # October — peak autumn renovation
        "kitchen-ideas": 6,
        "bathroom-ideas": 4,
        "luxury-bathroom-suites": 3,
        "design-trends": 4,
    },
    11: {  # November — pre-Christmas slowdown but kitchens still hot
        "kitchen-ideas": 4,
        "bathroom-ideas": 3,
        "design-trends": 3,
        "outdoor-patios": -3,
    },
    12: {  # December — minimal except trends/aspirational
        "design-trends": 4,
        "luxury-bathroom-suites": 4,
        "whole-home-renovation": 3,
        "outdoor-patios": -3,
        "garden-ideas": -3,
    },
}


def seasonal_weight(slug: str, when: datetime | None = None) -> int:
    """Return the +/- weight to add to a board's match score for the
    current month. Used by the candidate generator's product-→board
    matching to bias seasonally relevant content."""
    when = when or datetime.now(timezone.utc)
    return (SEASONAL_BOOST.get(when.month) or {}).get(slug, 0)


# ───── A/B copy variants ─────

async def generate_ab_variants(
    product: dict[str, Any], board: dict[str, Any],
) -> list[dict[str, str]]:
    """Generate 2 distinct copy variants for the same product+board so
    the engine can A/B test which performs better. Variant A is the
    standard SEO-optimised copy from `_build_pin_copy`. Variant B is a
    different angle (question-based or emotion-led).

    Returns: [{title, description, alt_text, variant: 'A'},
              {title, description, alt_text, variant: 'B'}]
    """
    from services.pinterest_queue import _build_pin_copy, _template_pin_copy
    api_key = os.environ.get("EMERGENT_LLM_KEY")

    a = await _build_pin_copy(product, board)
    a["variant"] = "A"

    if not api_key:
        # Fallback — slight template variation
        b = _template_pin_copy(product, board)
        b["title"] = f"5 Ways to Style {product.get('name', 'This Tile')}"[:100]
        b["variant"] = "B"
        return [a, b]

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=api_key,
            session_id=f"pin-ab-{secrets.token_hex(4)}",
            system_message=(
                "You write Pinterest pin copy variants for A/B testing. "
                "Given a product + board, write a SECOND variant that takes "
                "a DIFFERENT emotional/structural angle to the first one — "
                "if the first was descriptive ('Discover X'), make this "
                "question-led ('Looking for X?'). If the first was generic, "
                "make this story-led. Output strict JSON: title (60-100 "
                "chars, includes a Pinterest search phrase), description "
                "(180-380 chars, ends with hashtags), alt_text (under 200 "
                "chars). British English. No markdown."
            ),
        ).with_model("anthropic", "claude-haiku-4-5-20251001").with_params(max_tokens=600)

        prompt = (
            f"Variant A title: {a['title']}\n"
            f"Variant A description: {a['description']}\n\n"
            f"Product: {product.get('name')}\n"
            f"Category: {product.get('category')}\n"
            f"Board: {board['name']}\n\n"
            "Now write Variant B from a different angle. JSON only."
        )
        raw = (await chat.send_message(UserMessage(text=prompt))).strip()
        if raw.startswith("```"):
            import re
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
        import json as _json
        out = _json.loads(raw)
        b = {
            "title": (out.get("title") or "").strip()[:100],
            "description": (out.get("description") or "").strip()[:500],
            "alt_text": (out.get("alt_text") or product.get("name", "TileStation tile")).strip()[:200],
            "variant": "B",
        }
        if b["title"] and b["description"]:
            return [a, b]
    except Exception:
        logger.exception("A/B copy variant gen failed; returning template fallback")

    b = _template_pin_copy(product, board)
    b["title"] = f"Looking for {board.get('keywords', ['inspiration'])[0]}? — {product.get('name')}"[:100]
    b["variant"] = "B"
    return [a, b]


# ───── Carousel slide builder ─────

def build_carousel_slides(
    product: dict[str, Any], hero_url: str,
) -> list[dict[str, str]]:
    """Build a 4-slide carousel from a product's images.

    Slide 1: hero (lifestyle/room shot)
    Slide 2: close-up detail (second image if available, else hero)
    Slide 3: product cutout (image_url, "Shop now" overlay applied
             client-side via Pinterest's Pin templates — we just send
             the URL)
    Slide 4: alt context (third image if available, else hero)

    Returns list of {url, alt_text} dicts. Pinterest's carousel API
    accepts up to 5 images; we send 4.
    """
    images = product.get("images") or []
    if not isinstance(images, list):
        images = []
    https_imgs = [i for i in images if isinstance(i, str) and i.startswith("https://")]

    name = product.get("name", "TileStation tile")

    # Always start with the hero
    slides = [{"url": hero_url, "alt_text": f"{name} — room view"}]

    # Slide 2 — close-up: prefer a different image than hero
    cu = next((i for i in https_imgs if i != hero_url), hero_url)
    slides.append({"url": cu, "alt_text": f"{name} — close-up texture"})

    # Slide 3 — product cutout
    cutout = product.get("image_url") or https_imgs[0] if https_imgs else hero_url
    if cutout and cutout != hero_url and cutout != cu:
        slides.append({"url": cutout, "alt_text": f"{name} — single tile"})
    else:
        slides.append({"url": hero_url, "alt_text": f"{name} — overview"})

    # Slide 4 — alt context (different image if we have it)
    used = {s["url"] for s in slides}
    alt = next((i for i in https_imgs if i not in used), hero_url)
    slides.append({"url": alt, "alt_text": f"{name} — styled in different setting"})

    return slides


# ───── Repin scheduler ─────

async def schedule_repins(
    *, after_days: int = 30, top_n: int = 5,
) -> dict[str, Any]:
    """Once /week, find Pins posted ≥30 days ago that performed in the
    top N (by clicks). For each, schedule a fresh Pin to a DIFFERENT
    eligible board so the same image gets a second life on Pinterest.

    Pinterest rewards account-level consistency — re-pinning your top
    performers keeps your domain reputation high. Returns aggregate
    stats."""
    db = get_db()
    cutoff = datetime.now(timezone.utc) - timedelta(days=after_days)

    # Find top N posted Pins by click count (from performance feedback)
    cur = db.pinterest_pin_candidates.find(
        {
            "status": "posted",
            "posted_at": {"$lte": cutoff},
            "performance.clicks": {"$gte": 1},
            "repinned": {"$ne": True},
        },
        {"_id": 0},
    ).sort([("performance.clicks", -1)]).limit(top_n)
    candidates = await cur.to_list(top_n)
    if not candidates:
        return {"repinned": 0, "reason": "no_eligible_top_performers"}

    boards_cfg = {b["slug"]: b for b in await engine.list_boards_config()}
    repinned = 0

    for orig in candidates:
        # Pick a different active board than the original
        original_slug = orig.get("board_slug")
        alts = [s for s, b in boards_cfg.items()
                if s != original_slug and b.get("is_active", True)
                and b.get("link_target") == "product"]
        if not alts:
            continue
        new_slug = alts[0]
        new_board = boards_cfg[new_slug]

        new_cand = {
            "id": secrets.token_urlsafe(10),
            "product_id": orig.get("product_id"),
            "product_slug": orig.get("product_slug"),
            "product_name": orig.get("product_name"),
            "board_slug": new_slug,
            "board_name": new_board["name"],
            "title": orig.get("title"),
            "description": orig.get("description"),
            "alt_text": orig.get("alt_text"),
            "image_url": orig.get("image_url"),
            "image_tier": orig.get("image_tier"),
            "link_url": orig.get("link_url"),
            "status": "approved" if new_board.get("auto_approve") else "pending",
            "created_at": datetime.now(timezone.utc),
            "is_repin": True,
            "repin_of": orig.get("id"),
            "repin_of_pin_id": orig.get("pinterest_pin_id"),
        }
        if new_board.get("auto_approve"):
            new_cand["approved_at"] = datetime.now(timezone.utc)
            new_cand["scheduled_for"] = datetime.now(timezone.utc) + timedelta(hours=2)
            new_cand["approved_by"] = "auto-repin"
        await db.pinterest_pin_candidates.insert_one(new_cand)

        # Mark original as repinned so we don't repeat
        await db.pinterest_pin_candidates.update_one(
            {"id": orig["id"]}, {"$set": {"repinned": True, "repinned_at": datetime.now(timezone.utc)}},
        )
        repinned += 1

    return {"repinned": repinned, "considered": len(candidates)}


# ───── Performance feedback loop ─────

async def sync_pin_performance() -> dict[str, Any]:
    """Daily — pulls click + save (repin) stats from Pinterest API for
    every Pin posted in the last 30 days. Stores stats on the
    candidate row so the candidate generator + repin scheduler can
    score products and boards by real engagement.

    Skips silently if the Pinterest integration isn't connected.
    """
    db = get_db()
    from services import pinterest as pin_api
    settings = await pin_api.get_settings()
    if not settings.get("access_token"):
        return {"synced": 0, "reason": "integration_not_connected"}

    token = await pin_api._refresh_if_needed()
    if not token:
        return {"synced": 0, "reason": "token_invalid"}

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    cur = db.pinterest_pin_candidates.find(
        {
            "status": "posted",
            "posted_at": {"$gte": cutoff},
            "pinterest_pin_id": {"$exists": True, "$ne": None},
        },
        {"_id": 0, "id": 1, "pinterest_pin_id": 1},
    )

    import httpx
    synced = 0
    failed = 0
    async with httpx.AsyncClient(timeout=20.0) as cli:
        async for row in cur:
            pin_id = row["pinterest_pin_id"]
            try:
                # Pinterest analytics: GET /v5/pins/{pin_id}/analytics
                r = await cli.get(
                    f"{pin_api.API_BASE}/pins/{pin_id}/analytics",
                    headers={"Authorization": f"Bearer {token}"},
                    params={
                        "metric_types": "PIN_CLICK,SAVE,IMPRESSION",
                        "start_date": cutoff.strftime("%Y-%m-%d"),
                        "end_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    },
                )
                if r.status_code == 200:
                    data = r.json()
                    summary = (
                        (data.get("all") or {}).get("summary_metrics") or {}
                    )
                    perf = {
                        "clicks": int(summary.get("PIN_CLICK") or 0),
                        "saves": int(summary.get("SAVE") or 0),
                        "impressions": int(summary.get("IMPRESSION") or 0),
                        "synced_at": datetime.now(timezone.utc),
                    }
                    await db.pinterest_pin_candidates.update_one(
                        {"id": row["id"]},
                        {"$set": {"performance": perf}},
                    )
                    synced += 1
                else:
                    failed += 1
            except Exception:
                failed += 1
                continue

    return {"synced": synced, "failed": failed}


async def board_performance_score() -> dict[str, float]:
    """Return a score per board based on aggregate clicks/impressions
    of recent posted Pins. Used to bias next-day candidate generation."""
    db = get_db()
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    cur = db.pinterest_pin_candidates.aggregate([
        {"$match": {
            "status": "posted",
            "posted_at": {"$gte": cutoff},
            "performance": {"$exists": True},
        }},
        {"$group": {
            "_id": "$board_slug",
            "total_clicks": {"$sum": "$performance.clicks"},
            "total_impressions": {"$sum": "$performance.impressions"},
            "pin_count": {"$sum": 1},
        }},
    ])
    scores: dict[str, float] = {}
    async for r in cur:
        if r["pin_count"] == 0:
            continue
        scores[r["_id"]] = round(
            (r.get("total_clicks", 0) / max(r["pin_count"], 1)), 2,
        )
    return scores


# ───── Nano Banana lifestyle scene generator ─────

async def queue_lifestyle_render(product: dict[str, Any]) -> str | None:
    """For products with no Tier-1 lifestyle photo, queue a Nano Banana
    render of the tile in a stylised UK interior scene. The render
    runs ASYNC (Nano Banana takes ~6-10 sec) — this function just
    *queues* the request and returns the queue ID. The next candidate
    generation cycle will pick up completed renders.

    Returns the lifestyle_render queue ID, or None if generation isn't
    available (e.g. EMERGENT_LLM_KEY not set or product unsuitable).
    """
    if not os.environ.get("EMERGENT_LLM_KEY"):
        return None

    db = get_db()
    slug = product.get("slug")
    if not slug:
        return None

    # Idempotent — don't queue the same product twice if a recent
    # request is still in-flight or completed
    existing = await db.pinterest_lifestyle_renders.find_one(
        {"product_slug": slug, "status": {"$in": ["queued", "rendering", "ready"]}},
    )
    if existing:
        return existing.get("id")

    qid = secrets.token_urlsafe(10)
    name = product.get("name", "TileStation tile")
    cat = product.get("category", "tile")
    scene_prompt = _scene_prompt_for(name, cat)

    await db.pinterest_lifestyle_renders.insert_one({
        "id": qid,
        "product_slug": slug,
        "product_name": name,
        "scene_prompt": scene_prompt,
        "status": "queued",
        "created_at": datetime.now(timezone.utc),
    })
    return qid


def _scene_prompt_for(name: str, category: str) -> str:
    """Build a Nano Banana prompt describing where this tile should
    appear. Different categories get different scene templates."""
    cat = (category or "").lower()
    base = f"Photorealistic UK interior scene featuring {name} tiles. "
    if "outdoor" in cat or "patio" in cat:
        return base + (
            "Modern British garden patio with comfortable seating, "
            "potted plants, soft afternoon light, blurred green foliage "
            "background. The tiles cover the patio floor prominently. "
            "Editorial lifestyle photography, magazine-quality."
        )
    if "bathroom" in cat:
        return base + (
            "Luxury UK master bathroom with freestanding tub, brushed "
            "brass fixtures, large marble-effect tiles on walls and "
            "floor, soft natural light through frosted window, fresh "
            "eucalyptus, neutral palette. Editorial magazine quality."
        )
    if "wall" in cat:
        return base + (
            "Stylish UK home interior — kitchen splashback or bathroom "
            "feature wall with these tiles prominently featured. Warm "
            "modern decor, brushed brass accents, soft daylight. "
            "Editorial photography."
        )
    return base + (
        "Stylish UK home interior — could be a hallway, living space "
        "or open-plan kitchen — with these tiles featured on the floor "
        "or accent wall. Warm modern UK decor, soft daylight, "
        "editorial-magazine photography quality."
    )


async def render_lifestyle_tick(batch_size: int = 3) -> dict[str, Any]:
    """Cron tick — picks up queued lifestyle renders, calls Nano Banana,
    saves the resulting image to R2 (or stores the URL inline), marks
    the queue row 'ready'. Limited to `batch_size` per run so we don't
    bill £30 in one go.

    GRACEFUL DEGRADATION: if Nano Banana fails / no key / no R2, marks
    the row 'failed' with the error and moves on. The candidate
    generator simply ignores failed renders.
    """
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        return {"rendered": 0, "reason": "no_emergent_key"}

    db = get_db()
    cur = db.pinterest_lifestyle_renders.find(
        {"status": "queued"}
    ).sort("created_at", 1).limit(batch_size)
    queued = await cur.to_list(batch_size)
    if not queued:
        return {"rendered": 0, "reason": "queue_empty"}

    rendered = 0
    failed = 0
    for row in queued:
        await db.pinterest_lifestyle_renders.update_one(
            {"id": row["id"]}, {"$set": {
                "status": "rendering",
                "rendering_started_at": datetime.now(timezone.utc),
            }},
        )
        try:
            from emergentintegrations.llm.image_generation import OpenAIImageGeneration
            # Nano Banana isn't directly listed; use Gemini's image gen
            # via the same playbook. The integration playbook treats
            # this as the standard gen path. Falls back to a no-op if
            # the model isn't available.
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            chat = LlmChat(
                api_key=api_key,
                session_id=f"nano-banana-{row['id']}",
                system_message="You are a photo-realistic interior visualiser.",
            ).with_model("google", "gemini-2.5-flash-image-preview").with_params(modalities=["image", "text"])

            resp = await chat.send_message(UserMessage(text=row["scene_prompt"]))
            # The chat SDK returns image data inline — extract URL or
            # base64. Real production code needs upload-to-R2 step;
            # for now we store the data URL inline (works as Pinterest
            # image_url IF host accepts; otherwise this is a stub for
            # the user to wire up R2 upload after seeing first results).
            image_url = _extract_image_url(resp)
            if not image_url:
                raise RuntimeError("nano_banana_no_image_in_response")

            await db.pinterest_lifestyle_renders.update_one(
                {"id": row["id"]},
                {"$set": {
                    "status": "ready",
                    "image_url": image_url,
                    "rendered_at": datetime.now(timezone.utc),
                }},
            )
            rendered += 1
        except Exception as exc:
            logger.exception("Nano Banana render failed for %s", row.get("product_slug"))
            await db.pinterest_lifestyle_renders.update_one(
                {"id": row["id"]},
                {"$set": {
                    "status": "failed",
                    "error": str(exc)[:300],
                    "failed_at": datetime.now(timezone.utc),
                }},
            )
            failed += 1

    return {"rendered": rendered, "failed": failed, "batch_size": batch_size}


def _extract_image_url(response: Any) -> str | None:
    """Best-effort extraction of an image URL from the LLM response.
    Different models return different structures — handle the common
    ones (Gemini returns inline_data with base64; OpenAI returns a URL)."""
    if isinstance(response, str) and response.startswith("http"):
        return response
    if isinstance(response, str) and response.startswith("data:image"):
        return response
    if isinstance(response, dict):
        for key in ("image_url", "url", "image"):
            v = response.get(key)
            if isinstance(v, str) and (v.startswith("http") or v.startswith("data:")):
                return v
    return None

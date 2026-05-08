"""
Pinterest Visual Marketing Engine — Configuration & Defaults
─────────────────────────────────────────────────────────────

Defines the 9 default Pinterest boards plus the rules that map a
TileStation product → relevant boards. Boards are seeded into the
`pinterest_boards` collection on first call to `init_default_boards()`
so the admin can edit them later without losing the structure.

The mapping rules are deliberately broad — most products fit multiple
boards. Pinterest's algorithm rewards cross-posting the same content
across topically-related boards, so we lean into that.

Auto-approve flags follow your strategic directive:
  • Brand-flagship boards = manual approval only (Luxury, Bathroom Ideas)
  • High-volume boards = auto after first 30 days
  • Adjacency boards = always auto-approve (low-stakes lifestyle content)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from config import get_db

logger = logging.getLogger(__name__)


# ───── Default board definitions ─────
# `slug` is our internal stable ID. `pinterest_board_id` gets filled in
# once the admin creates the matching board on Pinterest and the system
# auto-detects it (see /admin/pinterest/sync-boards).
DEFAULT_BOARDS: list[dict[str, Any]] = [
    {
        "slug": "bathroom-ideas",
        "name": "Bathroom Ideas with Our Tiles",
        "description": "Stunning UK bathroom designs featuring TileStation marble, porcelain & stone — wet rooms, ensuites, family bathrooms & cloakrooms.",
        "emoji": "🛁",
        "auto_approve": False,  # brand-flagship — review every Pin
        "category_match": ["Bathroom", "Floor Tiles", "Wall Tiles", "Large Format"],
        "keywords": ["bathroom", "ensuite", "wet room", "shower", "wall tile", "floor tile", "marble", "porcelain"],
        "link_target": "product",
        "priority": 1,
    },
    {
        "slug": "kitchen-ideas",
        "name": "Kitchen Ideas & Splashback Inspiration",
        "description": "UK kitchen renovation ideas — splashbacks, breakfast bars, kitchen floors, countertops in marble and porcelain.",
        "emoji": "🍳",
        "auto_approve": False,  # high-traffic board, manual review for first month
        "category_match": ["Floor Tiles", "Wall Tiles", "Large Format", "Small Format"],
        "keywords": ["kitchen", "splashback", "worktop", "breakfast bar", "marble", "subway tile", "metro"],
        "link_target": "product",
        "priority": 1,
    },
    {
        "slug": "outdoor-patios",
        "name": "Outdoor Patios & Pool Decks",
        "description": "Porcelain outdoor tiles for UK gardens — patios, pool surrounds, walkways, terraces. R11 anti-slip 20mm pavers.",
        "emoji": "🌳",
        "auto_approve": True,
        "category_match": ["Outdoor Tiles"],
        "keywords": ["outdoor", "patio", "pool", "deck", "garden", "20mm", "paver", "porcelain paving"],
        "link_target": "product",
        "priority": 1,
    },
    {
        "slug": "garden-ideas",
        "name": "Garden Ideas & Landscaping",
        "description": "UK garden inspiration — paths, raised beds, seating areas, BBQ stations. Porcelain garden tiles that beat traditional flagstone.",
        "emoji": "🌿",
        "auto_approve": True,
        "category_match": ["Outdoor Tiles"],
        "keywords": ["garden", "landscape", "path", "BBQ", "stepping stone", "lawn"],
        "link_target": "product",
        "priority": 2,
    },
    {
        "slug": "patio-ideas",
        "name": "Patio Ideas (UK Homes)",
        "description": "Smaller-garden patio ideas for UK semi-detached & terraced homes — alfresco dining, fire pits, family-friendly designs.",
        "emoji": "☀️",
        "auto_approve": True,
        "category_match": ["Outdoor Tiles"],
        "keywords": ["patio", "alfresco", "dining", "fire pit", "small garden", "courtyard"],
        "link_target": "product",
        "priority": 2,
    },
    {
        "slug": "how-to-tile",
        "name": "How To: Tile Like a Pro",
        "description": "Step-by-step UK tile installation tutorials — laying, grouting, cutting, sealing. By TileStation experts.",
        "emoji": "🔨",
        "auto_approve": False,  # tutorial content — needs human review for accuracy
        "category_match": [],  # tutorial-driven, not product-driven
        "keywords": ["how to", "tutorial", "installation", "grout", "lay", "cut", "DIY"],
        "link_target": "blog",
        "priority": 2,
    },
    {
        "slug": "luxury-bathroom-suites",
        "name": "Luxury Bathroom Suites 2026",
        "description": "Aspirational UK luxury bathrooms — Calacatta marble master suites, freestanding tubs, rainfall showers. Editorial-quality only.",
        "emoji": "✨",
        "auto_approve": False,  # premium showcase — strict curation
        "category_match": ["Bathroom", "Large Format", "Floor Tiles", "Wall Tiles"],
        "keywords": ["luxury", "marble", "calacatta", "carrara", "spa", "hotel", "high-end", "premium"],
        "link_target": "product",
        "priority": 1,
    },
    {
        "slug": "design-trends",
        "name": "Design Trends: Marble, Terrazzo & Beyond",
        "description": "2026 UK tile trends — terrazzo, fluted, microcement effect, large-format slabs, biophilic stone.",
        "emoji": "🎨",
        "auto_approve": True,
        "category_match": ["Large Format", "Floor Tiles", "Wall Tiles"],
        "keywords": ["trend", "terrazzo", "fluted", "microcement", "concrete effect", "wood effect", "stone effect"],
        "link_target": "collection",
        "priority": 2,
    },
    {
        "slug": "whole-home-renovation",
        "name": "Whole-Home Renovation Inspiration",
        "description": "UK whole-home renovation ideas — bedrooms, hallways, mudrooms, lighting, paint pairings. Cross-room inspiration.",
        "emoji": "🏠",
        "auto_approve": True,
        "category_match": [],
        "keywords": ["renovation", "interior", "home", "decor", "bedroom", "hallway", "mudroom"],
        "link_target": "blog",
        "priority": 3,
    },
]


def board_by_slug(slug: str) -> dict[str, Any] | None:
    return next((b for b in DEFAULT_BOARDS if b["slug"] == slug), None)


# ───── DB initialisation ─────

async def init_default_boards() -> int:
    """Idempotent — inserts only boards that don't yet exist by slug.
    Returns the number of boards inserted."""
    db = get_db()
    inserted = 0
    for board in DEFAULT_BOARDS:
        existing = await db.pinterest_boards.find_one({"slug": board["slug"]}, {"_id": 0})
        if existing:
            continue
        doc = {
            **board,
            "pinterest_board_id": None,  # filled by sync-boards
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
        }
        await db.pinterest_boards.insert_one(doc)
        inserted += 1
    if inserted:
        logger.info("Pinterest visual engine — seeded %d boards", inserted)
    return inserted


async def list_boards_config() -> list[dict[str, Any]]:
    """Get all boards from DB, sorted by priority then alpha."""
    db = get_db()
    cur = db.pinterest_boards.find({}, {"_id": 0}).sort([("priority", 1), ("name", 1)])
    return await cur.to_list(50)


async def update_board_config(slug: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    """Admin-side update — accepts auto_approve, pinterest_board_id,
    is_active. Other fields locked to prevent foot-shooting."""
    db = get_db()
    safe = {k: updates[k] for k in (
        "auto_approve", "pinterest_board_id", "is_active", "name", "description"
    ) if k in updates}
    if not safe:
        return await db.pinterest_boards.find_one({"slug": slug}, {"_id": 0})
    safe["updated_at"] = datetime.now(timezone.utc)
    await db.pinterest_boards.update_one({"slug": slug}, {"$set": safe})
    return await db.pinterest_boards.find_one({"slug": slug}, {"_id": 0})


# ───── Product → board matching ─────

def match_product_to_boards(product: dict[str, Any]) -> list[str]:
    """Score-based fit: each board contributes if category matches OR
    any keyword appears in the product name/description/collection.
    Returns up to the 3 best-fit board slugs (Pinterest spam protection
    — 4+ boards for the same content gets flagged).

    Seasonal weighting: for the current UK month, boards get a +/-
    boost defined in `pinterest_engine_phase2.SEASONAL_BOOST` so we
    push more outdoor content in spring/summer, more bathroom content
    in January (resolution season), more kitchen content in autumn.
    """
    name = (product.get("name") or "").lower()
    desc = (product.get("description") or "").lower()
    coll = (product.get("collection") or "").lower()
    cat = (product.get("category") or "").strip()
    haystack = f"{name} {desc} {coll}"

    # Seasonal booster — local import avoids a circular dep
    try:
        from services.pinterest_engine_phase2 import seasonal_weight
    except Exception:
        def seasonal_weight(_slug: str) -> int:  # type: ignore[no-redef]
            return 0

    scored: list[tuple[str, int, int]] = []  # (slug, score, priority)
    for board in DEFAULT_BOARDS:
        # Skip boards whose link target is "blog" — those are reserved
        # for editorial autopilot articles, not product Pins.
        if board["link_target"] == "blog":
            continue
        score = 0
        if cat in (board.get("category_match") or []):
            score += 10
        for kw in board.get("keywords") or []:
            if kw in haystack:
                score += 2
        # Seasonal bias only applies to boards that already matched
        # — never invents a match from thin air.
        if score > 0:
            score += seasonal_weight(board["slug"])
        if score > 0:
            scored.append((board["slug"], score, board.get("priority", 3)))

    # Sort: highest score first, then highest priority (lower number = higher).
    scored.sort(key=lambda r: (-r[1], r[2]))

    # Always at least 1 board even for unmatched products: fall back to
    # whole-home renovation (the safety net adjacency board).
    if not scored:
        return ["whole-home-renovation"]

    return [s for s, _, _ in scored[:3]]

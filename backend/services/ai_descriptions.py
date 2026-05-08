"""
Shared AI-description service.

Single source of truth for the per-product SEO description generation used
by the Marketing & SEO bulk tool (`/api/products/bulk-generate-descriptions`).
Designed to be called from multiple entry points so we don't maintain two
separate prompts or model-selection code paths.

HISTORICAL NOTE (Apr 30, 2026)
------------------------------
Three older, pre-existing generators still live inline in `server.py`:

    /api/products/generate-description          — per-product, OpenAI gpt-4o
    /api/products/generate-series-description   — per-series, OpenAI gpt-4o
    /api/products/generate-batch-series-descriptions — batch-of-series

Those were written before this service existed, are heavily entangled with
OpenAI function-calling, and currently power the `Suggest description` button
on the single-product editor + the `Bulk Edit Categories → AI Series
Description` tool. They work today so we intentionally do NOT rewrite them;
instead, the SEO-tab bulk tool uses the shared helper here and the UI
cross-links to the Bulk Edit flow for richer series-level copy.

When the next engineer touches one of those legacy endpoints, the recommended
next step is to migrate them into this service so there's exactly one prompt,
one model-selector, and one sibling-context pipeline.
"""
from __future__ import annotations

import os
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Optional, Iterable

# `emergentintegrations` wraps the Emergent universal LLM key and lets us
# swap providers (Anthropic / OpenAI / Google) behind a uniform interface.
from emergentintegrations.llm.chat import LlmChat, UserMessage


# Default model — Claude Haiku 4.5 is ~10× cheaper than gpt-4o and fast
# enough for hundreds of descriptions per minute. Callers can override for
# flagship products via `model=`.
DEFAULT_MODEL = ("anthropic", "claude-haiku-4-5-20251001")

# Mongo collections the bulk tool is allowed to target. Everything outside
# this set is rejected at the route layer to prevent accidental writes to
# ledger / audit data.
ALLOWED_PRODUCT_COLLECTIONS = {"products", "tiles", "supplier_products"}

_SYSTEM_MESSAGE = (
    "You are a UK-based copywriter for a tile e-commerce site. "
    "Write concise, factual, SEO-friendly product descriptions. "
    "Never invent attributes that aren't given. Plain prose only."
)


def _attr(prod: dict, *keys: str):
    """Coalesce top-level fields with the `attributes.*` nested schema used
    by imported tile / supplier rows."""
    for k in keys:
        v = prod.get(k)
        if v:
            return v
    a = prod.get("attributes") or {}
    for k in keys:
        v = a.get(k)
        if v:
            return v
    return None


def product_display_name(prod: dict) -> str:
    return (
        prod.get("our_product_name")
        or prod.get("display_name")
        or prod.get("name")
        or prod.get("product_name")
        or "Tile"
    )


def build_prompt(product: dict, siblings: Optional[Iterable[dict]] = None) -> str:
    """Assemble the per-product prompt. `siblings` is a list of
    `{"name": str, "path": str}` dicts — up to 4 options Claude can weave
    into a single natural in-prose link. Pass empty/None to skip linking."""
    bits = []
    if _attr(product, "material"): bits.append(f"Material: {_attr(product, 'material')}")
    if _attr(product, "finish"): bits.append(f"Finish: {_attr(product, 'finish')}")
    if _attr(product, "size"): bits.append(f"Size: {_attr(product, 'size')}")
    colors = _attr(product, "colors", "color")
    if colors:
        if isinstance(colors, (list, tuple)):
            bits.append(f"Colours: {', '.join(str(c) for c in colors[:5])}")
        else:
            bits.append(f"Colour: {colors}")
    if _attr(product, "suitability"): bits.append(f"Suitable for: {_attr(product, 'suitability')}")
    if product.get("category"): bits.append(f"Category: {product['category']}")
    if product.get("type"): bits.append(f"Type: {product['type']}")
    details = "\n".join(bits) if bits else "(no extra attributes provided)"

    link_block = ""
    sibling_list = list(siblings or [])
    if sibling_list:
        options = "\n".join(
            f"  - [{s['name']}]({s['path']})" for s in sibling_list[:4]
        )
        link_block = (
            "\n\nINTERNAL LINK REQUIREMENT: You MUST include "
            "exactly ONE of the links below, woven naturally into "
            "one sentence using standard markdown `[text](/path)` "
            "syntax. Pick whichever reads most naturally with the "
            "description you're writing. Do not invent links — "
            "use only the options given:\n" + options
        )

    return (
        "Write a single-paragraph SEO product description for this tile, "
        "around 55-65 words, no headings, no bullets, no clichés like "
        "'Introducing'. Use UK English spelling. Highlight likely use-cases "
        "(bathroom / kitchen / floor / wall) only when consistent with the "
        "product type. Mention material and finish naturally.\n\n"
        f"PRODUCT NAME: {product_display_name(product)}\n"
        f"DETAILS:\n{details}"
        f"{link_block}\n\n"
        "Description:"
    )


async def siblings_for(db, collection: str, product: dict, cache: Optional[dict] = None) -> list:
    """Return up to 4 link candidates — 3 sibling products in the same
    category + a category landing page fallback. Results are cached in
    the caller-provided dict (scoped to a single bulk-run) so the 2nd+
    products in the same category don't re-query Mongo."""
    if cache is None:
        cache = {}
    category = (product.get("category") or "").strip()
    if not category:
        return []

    key = f"{collection}::{category.lower()}"
    if key not in cache:
        cursor = db[collection].find(
            {"category": category, "id": {"$ne": product.get("id")}},
            {
                "_id": 0, "id": 1, "sku": 1, "name": 1,
                "our_product_name": 1, "display_name": 1,
                "slug": 1, "category_slug": 1,
            },
        ).limit(6)
        cache[key] = await cursor.to_list(6)

    own_id = product.get("id") or product.get("sku")
    out: list = []
    for s in cache[key]:
        if (s.get("id") or s.get("sku")) == own_id:
            continue
        name = s.get("our_product_name") or s.get("display_name") or s.get("name")
        slug = s.get("slug") or s.get("id") or s.get("sku")
        if name and slug:
            out.append({"name": name, "path": f"/tiles/{slug}"})
        if len(out) >= 3:
            break

    cat_slug = product.get("category_slug") or category.lower().replace(" ", "-")
    out.append({"name": f"our {category.lower()} collection", "path": f"/shop/category/{cat_slug}"})
    return out


async def generate_one(
    *,
    api_key: str,
    product: dict,
    siblings: Optional[Iterable[dict]] = None,
    model: tuple[str, str] = DEFAULT_MODEL,
) -> dict:
    """Call the LLM for a single product and return either the description
    or an error reason. Never raises — callers do their own logging."""
    try:
        prompt = build_prompt(product, siblings)
        chat = LlmChat(
            api_key=api_key,
            session_id=f"desc-{product.get('id', product.get('sku', 'x'))}-{uuid.uuid4().hex[:6]}",
            system_message=_SYSTEM_MESSAGE,
        ).with_model(*model)
        desc = await chat.send_message(UserMessage(text=prompt))
        desc = (desc or "").strip()
        if not desc:
            return {"ok": False, "error": "Empty response from LLM"}
        return {"ok": True, "description": desc}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:200]}


def missing_description_filter() -> dict:
    """The `$or` query block for 'this product has no description yet'."""
    return {
        "$or": [
            {"description": {"$exists": False}},
            {"description": ""},
            {"description": None},
        ]
    }


async def save_generated_description(db, collection: str, product: dict, description: str) -> None:
    """Persist a generated description + metadata. Matches on whichever
    identifier the doc uses — `id` for `products`, `sku` for imported rows."""
    match = {"id": product["id"]} if product.get("id") else {"sku": product.get("sku")}
    await db[collection].update_one(
        match,
        {"$set": {
            "description": description,
            "description_source": "ai_bulk_haiku",
            "description_generated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )

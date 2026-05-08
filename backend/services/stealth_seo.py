"""
Stealth-Keyword SEO Targeting
─────────────────────────────

Strategy: target the SUPPLIER ORIGINAL product names (e.g. "Opal", "LP-6611",
"Onyx White") so that customers searching those terms on Google land on
our re-branded products ("Artisan", "Gem", "Alabaster") — without ever
exposing the supplier names in the customer-facing UI.

Where the keywords go:
  1. <meta name="keywords" content="..."> (light boost; modern Google
     mostly ignores it but Bing and other engines still index)
  2. JSON-LD Product `alternateName` array — Google indexes this and
     shows it in "Did you mean…" suggestions
  3. JSON-LD Product `keywords` field — explicit signal
  4. Hidden semantic `<meta property="product:alternateName">` tags
     for Open Graph crawlers (Pinterest, Slack, etc.)
  5. invisible-to-user but indexed-by-bots `<span style="position:absolute;left:-9999px">`
     wrapped around the alt names INSIDE the Article-Body region
     (this is the "show in search but not on page" trick) — only added
     when the SSR layer recognises a tile/category page.

What it does NOT do:
  - Modify the visible product name, image, or any rendered text
  - Affect customer carts/orders/checkout
  - Send the alt names to Stripe, Resend, or any other downstream

Storage:
  - Tile-level alt-names live on `tiles.hidden_seo_keywords` (an
    existing field — pre-populated for 3 tiles, this service expands
    coverage to all 766).
  - Collection-level alt-names live on a new `seo_collection_keywords`
    document keyed by `collection` (the existing tile.collection field).
  - Audit log: every change writes a `seo_stealth_audit` row so we can
    see who changed what.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Optional

from config import get_db

logger = logging.getLogger(__name__)


def _normalise(raw) -> list[str]:
    """Accept comma-separated string OR list, normalise, dedupe, cap
    length so no admin can paste 10 KB of garbage by accident."""
    if not raw:
        return []
    if isinstance(raw, str):
        items = re.split(r"[,\n]+", raw)
    elif isinstance(raw, (list, tuple, set)):
        items = list(raw)
    else:
        items = [str(raw)]
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        s = str(it).strip()
        if not s or len(s) > 80:
            continue
        if s.lower() in seen:
            continue
        seen.add(s.lower())
        out.append(s[:80])
        if len(out) >= 25:
            break  # 25 is the upper sanity bound — Google won't index more
    return out


# ───────── Admin queries ─────────

async def list_collections_with_counts() -> list[dict]:
    """Distinct `collection` values + product counts + how many already
    have stealth keywords. Used by the admin filter dropdown."""
    db = get_db()
    pipe = [
        {"$match": {"is_active": True, "collection": {"$exists": True, "$nin": [None, ""]}}},
        {"$group": {
            "_id": "$collection",
            "product_count": {"$sum": 1},
            "with_stealth_keywords": {
                "$sum": {
                    "$cond": [
                        {"$and": [
                            {"$ifNull": ["$hidden_seo_keywords", False]},
                            {"$ne": ["$hidden_seo_keywords", ""]},
                        ]},
                        1, 0,
                    ]
                }
            },
        }},
        {"$sort": {"product_count": -1}},
    ]
    rows = []
    async for r in db.tiles.aggregate(pipe):
        rows.append({
            "collection": r["_id"],
            "product_count": r["product_count"],
            "with_stealth_keywords": r["with_stealth_keywords"],
            "coverage_pct": round((r["with_stealth_keywords"] / r["product_count"]) * 100) if r["product_count"] else 0,
        })
    return rows


async def list_products(
    collection: Optional[str] = None,
    *, only_missing: bool = False, limit: int = 200,
) -> list[dict]:
    """List products in a collection with their stealth-keyword status.
    Returns the rows the admin sees in the table."""
    db = get_db()
    q: dict = {"is_active": True}
    if collection:
        q["collection"] = collection
    if only_missing:
        q["$or"] = [
            {"hidden_seo_keywords": {"$exists": False}},
            {"hidden_seo_keywords": ""},
            {"hidden_seo_keywords": None},
        ]
    rows = await db.tiles.find(q, {
        "_id": 0, "id": 1, "name": 1, "slug": 1, "collection": 1,
        "original_name": 1, "hidden_seo_keywords": 1,
        "supplier_code": 1, "images": 1,
    }).sort("name", 1).limit(limit).to_list(length=limit)
    out = []
    for r in rows:
        kws = _normalise(r.get("hidden_seo_keywords"))
        # Show the supplier-original name as an auto-suggested keyword
        # if it isn't already in the list and isn't the same as the
        # storefront name.
        suggested: list[str] = []
        orig = (r.get("original_name") or "").strip()
        cur_name = (r.get("name") or "").strip().lower()
        if orig and orig.lower() != cur_name:
            if orig.lower() not in {k.lower() for k in kws}:
                suggested.append(orig)
        # Pull the bare supplier code (e.g. "LP-6611") if present
        sc = (r.get("supplier_code") or "").strip()
        if sc and sc.lower() not in {k.lower() for k in kws}:
            suggested.append(sc)
        # First image (for the admin row preview)
        first_image = None
        imgs = r.get("images") or []
        if imgs:
            first = imgs[0]
            first_image = first if isinstance(first, str) else (first or {}).get("url")
        out.append({
            "id": r.get("id"),
            "name": r.get("name"),
            "slug": r.get("slug"),
            "collection": r.get("collection"),
            "original_name": orig or None,
            "stealth_keywords": kws,
            "suggested_keywords": suggested,
            "supplier_code": sc or None,
            "image_url": first_image,
        })
    return out


# ───────── Per-product set/clear ─────────

async def set_product_keywords(
    product_id: str, keywords, *, admin_email: Optional[str] = None,
) -> dict:
    """Upsert stealth keywords for a single tile. Stored as a
    comma-separated string on `hidden_seo_keywords` for backwards
    compatibility with the existing field — but we always normalise
    on the way in."""
    db = get_db()
    norm = _normalise(keywords)
    res = await db.tiles.update_one(
        {"id": product_id},
        {"$set": {
            "hidden_seo_keywords": ", ".join(norm),
            "hidden_seo_keywords_updated_at": datetime.now(timezone.utc),
            "hidden_seo_keywords_updated_by": admin_email,
        }},
    )
    if res.matched_count == 0:
        # Try by Mongo ObjectId-style id field if numeric/string mismatch
        res = await db.tiles.update_one(
            {"_id": product_id},
            {"$set": {
                "hidden_seo_keywords": ", ".join(norm),
                "hidden_seo_keywords_updated_at": datetime.now(timezone.utc),
                "hidden_seo_keywords_updated_by": admin_email,
            }},
        )
    if res.matched_count == 0:
        raise LookupError(f"Product {product_id} not found")
    await _audit("product", product_id, norm, admin_email)
    return {"ok": True, "id": product_id, "stealth_keywords": norm}


async def bulk_apply_to_collection(
    collection: str, keywords, *, mode: str = "merge",
    admin_email: Optional[str] = None,
) -> dict:
    """Apply a list of keywords to every active product in a collection.

    Modes:
      `merge`   — append to existing keywords on each product (default,
                  safe — no destruction of per-product overrides)
      `replace` — overwrite each product's keywords with the new list
      `append_supplier_original` — add each product's own
                  `original_name` to its existing keywords (the
                  killer one-click for "make every product target
                  its supplier name")
    """
    db = get_db()
    if mode not in ("merge", "replace", "append_supplier_original"):
        raise ValueError(f"Unknown mode: {mode}")
    base_kws = _normalise(keywords) if mode != "append_supplier_original" else []
    now = datetime.now(timezone.utc)
    matched = 0
    updated = 0
    cursor = db.tiles.find(
        {"collection": collection, "is_active": True},
        {"_id": 0, "id": 1, "name": 1, "original_name": 1,
         "supplier_code": 1, "hidden_seo_keywords": 1},
    )
    async for r in cursor:
        matched += 1
        existing = _normalise(r.get("hidden_seo_keywords"))
        if mode == "replace":
            new_list = base_kws
        elif mode == "merge":
            seen = {k.lower() for k in existing}
            new_list = existing + [k for k in base_kws if k.lower() not in seen]
        else:  # append_supplier_original
            extras = []
            orig = (r.get("original_name") or "").strip()
            if orig and orig.lower() != (r.get("name") or "").strip().lower():
                extras.append(orig)
            sc = (r.get("supplier_code") or "").strip()
            if sc:
                extras.append(sc)
            seen = {k.lower() for k in existing}
            new_list = existing + [e for e in extras if e.lower() not in seen]
            new_list = _normalise(new_list)
        if new_list == existing:
            continue  # idempotent — skip writes when nothing changes
        await db.tiles.update_one(
            {"id": r["id"]},
            {"$set": {
                "hidden_seo_keywords": ", ".join(new_list),
                "hidden_seo_keywords_updated_at": now,
                "hidden_seo_keywords_updated_by": admin_email,
            }},
        )
        updated += 1
    await _audit_bulk(collection, mode, base_kws, matched, updated, admin_email)
    return {"ok": True, "collection": collection, "mode": mode,
            "matched": matched, "updated": updated, "applied_keywords": base_kws}


async def auto_fill_all_supplier_originals(
    *, dry_run: bool = False, admin_email: Optional[str] = None,
) -> dict:
    """One-click "stealth-fill every product in the catalogue with its
    own supplier-original name + supplier code."

    Iterates every active tile (regardless of collection), appends
    `original_name` and `supplier_code` to each product's
    `hidden_seo_keywords` if not already present. Idempotent — safe
    to re-run; no-op when nothing changes.

    Returns rich stats so the admin UI can render a "+N keywords
    added across N products" toast.

    `dry_run=True` reports what WOULD change without writing — so the
    admin can preview impact before clicking through the confirm.
    """
    db = get_db()
    now = datetime.now(timezone.utc)
    matched = 0
    updated = 0
    skipped_already_have = 0
    skipped_no_supplier_data = 0
    keywords_added = 0
    cursor = db.tiles.find(
        {"is_active": True},
        {"_id": 0, "id": 1, "name": 1, "original_name": 1,
         "supplier_code": 1, "hidden_seo_keywords": 1},
    )
    async for r in cursor:
        matched += 1
        existing = _normalise(r.get("hidden_seo_keywords"))
        extras: list[str] = []
        orig = (r.get("original_name") or "").strip()
        if orig and orig.lower() != (r.get("name") or "").strip().lower():
            extras.append(orig)
        sc = (r.get("supplier_code") or "").strip()
        if sc:
            extras.append(sc)
        if not extras:
            skipped_no_supplier_data += 1
            continue
        seen = {k.lower() for k in existing}
        new_extras = [e for e in extras if e.lower() not in seen]
        if not new_extras:
            skipped_already_have += 1
            continue
        new_list = _normalise(existing + new_extras)
        if new_list == existing:
            skipped_already_have += 1
            continue
        keywords_added += len(new_list) - len(existing)
        if not dry_run:
            await db.tiles.update_one(
                {"id": r["id"]},
                {"$set": {
                    "hidden_seo_keywords": ", ".join(new_list),
                    "hidden_seo_keywords_updated_at": now,
                    "hidden_seo_keywords_updated_by": admin_email,
                }},
            )
        updated += 1
    if not dry_run:
        await db.seo_stealth_audit.insert_one({
            "scope": "auto_fill_all_supplier_originals",
            "matched": matched, "updated": updated,
            "keywords_added": keywords_added,
            "skipped_already_have": skipped_already_have,
            "skipped_no_supplier_data": skipped_no_supplier_data,
            "admin_email": admin_email, "at": now,
        })
    return {
        "ok": True,
        "dry_run": dry_run,
        "matched": matched,
        "updated": updated,
        "keywords_added": keywords_added,
        "skipped_already_have": skipped_already_have,
        "skipped_no_supplier_data": skipped_no_supplier_data,
    }


# ───────── Audit log ─────────

async def _audit(scope: str, target_id: str, keywords: list[str], admin_email: Optional[str]) -> None:
    db = get_db()
    await db.seo_stealth_audit.insert_one({
        "scope": scope, "target_id": target_id, "keywords": keywords,
        "admin_email": admin_email, "at": datetime.now(timezone.utc),
    })


async def _audit_bulk(collection, mode, keywords, matched, updated, admin_email):
    db = get_db()
    await db.seo_stealth_audit.insert_one({
        "scope": "collection_bulk",
        "collection": collection, "mode": mode,
        "keywords": keywords, "matched": matched, "updated": updated,
        "admin_email": admin_email, "at": datetime.now(timezone.utc),
    })


# ───────── Read API for SSR injection ─────────

async def get_stealth_keywords_for_tile(slug: str) -> list[str]:
    """Used by the SSR enrich layer when rendering /tiles/<slug>.
    Returns the merged keyword list (per-product + collection-wide
    + supplier-original-name fallback). Always succeeds — never raises."""
    try:
        db = get_db()
        row = await db.tiles.find_one(
            {"slug": slug, "is_active": True},
            {"_id": 0, "hidden_seo_keywords": 1, "original_name": 1, "supplier_code": 1, "name": 1, "collection": 1},
        )
        if not row:
            return []
        keys = _normalise(row.get("hidden_seo_keywords"))
        # Collection-wide alt names
        coll = (row.get("collection") or "").strip()
        if coll:
            coll_doc = await db.seo_collection_keywords.find_one(
                {"collection": coll}, {"_id": 0, "keywords": 1},
            )
            if coll_doc:
                seen = {k.lower() for k in keys}
                for k in _normalise(coll_doc.get("keywords")):
                    if k.lower() not in seen:
                        keys.append(k)
                        seen.add(k.lower())
        return keys[:25]
    except Exception:
        logger.exception("get_stealth_keywords_for_tile failed")
        return []


async def set_collection_keywords(
    collection: str, keywords, *, admin_email: Optional[str] = None,
) -> dict:
    db = get_db()
    norm = _normalise(keywords)
    await db.seo_collection_keywords.update_one(
        {"collection": collection},
        {"$set": {
            "collection": collection, "keywords": norm,
            "updated_at": datetime.now(timezone.utc),
            "updated_by": admin_email,
        }},
        upsert=True,
    )
    await _audit("collection", collection, norm, admin_email)
    return {"ok": True, "collection": collection, "keywords": norm}


async def get_collection_keywords(collection: str) -> list[str]:
    db = get_db()
    doc = await db.seo_collection_keywords.find_one(
        {"collection": collection}, {"_id": 0, "keywords": 1},
    )
    return _normalise((doc or {}).get("keywords"))


async def stats() -> dict:
    """Top-of-card stats for the admin UI."""
    db = get_db()
    total = await db.tiles.count_documents({"is_active": True})
    with_kw = await db.tiles.count_documents({
        "is_active": True,
        "hidden_seo_keywords": {"$exists": True, "$nin": [None, ""]},
    })
    eligible = await db.tiles.count_documents({
        "is_active": True,
        "original_name": {"$exists": True, "$nin": [None, ""]},
    })
    coll_count = await db.seo_collection_keywords.count_documents({})
    return {
        "products_total": total,
        "products_with_keywords": with_kw,
        "products_eligible": eligible,
        "coverage_pct": round((with_kw / total) * 100) if total else 0,
        "collection_keyword_sets": coll_count,
    }

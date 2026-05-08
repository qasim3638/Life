"""
Stealth-Keyword Auto-Promote
────────────────────────────

Closes the loop: the weekly digest surfaces "missed wins" (GSC queries
we don't yet target), and this module *acts* on them — once a week,
when enabled, it picks the top new missed-win and promotes it into a
cleanly-matching collection's stealth keywords.

Constraints (safety rails so we never spam the catalogue):
  • Runs AT MOST ONCE per calendar week (the Monday cron calls it)
  • Only promotes ONE query per run (no "burst" of 10 keywords)
  • Must meet the configurable `auto_promote_min_impressions` floor
  • Must cleanly match an existing collection name (fuzzy token match)
  • Skips queries already in the target collection's keyword list
  • Writes a rollback row with a random URL-safe token — the digest
    email shows an "[Undo]" link that removes the keyword in one click

Storage:
  • `seo_stealth_auto_promotes` — one row per promotion:
      { id, query, collection, added_keyword, token, promoted_at,
        undone_at, promoted_by: "cron" }
  • The token is cryptographically random (secrets.token_urlsafe, 24
    bytes) — brute force is not feasible.

Undo is a public endpoint (no auth) — the token IS the credential.
This matches how "unsubscribe from newsletter" and "magic-link login"
work industry-wide. The blast radius of a leaked token is: one
stealth keyword is removed from one collection (low impact, fully
reversible by re-applying through the admin dashboard).
"""
from __future__ import annotations

import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from config import get_db

logger = logging.getLogger(__name__)


# ───────── Collection matcher ─────────

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {"tile", "tiles", "the", "a", "and", "uk", "buy", "shop",
              "near", "me", "best", "cheap", "sale"}


def _tokens(s: str) -> set[str]:
    if not s:
        return set()
    return {t for t in _TOKEN_RE.findall(s.lower())
            if len(t) >= 3 and t not in _STOPWORDS}


async def _find_matching_collection(query: str, active_collections: list[str]) -> Optional[str]:
    """Return the collection name that cleanly matches this query, or
    None if no unambiguous match.

    Match rule: every "meaningful" token of the collection name must
    appear in the query (stop-words + 'tile(s)' are stripped first).
    Example matches:
      "spanish tiles"  + collection "Spanish" → match (token {spanish} ⊆ {spanish})
      "terrazzo tiles" + collection "Terrazzo Effect" → match (token {terrazzo, effect}⊄ {terrazzo}) → NO match
      "calacatta marble tile uk" + collection "Marble Effect" → ambiguous, fallback below

    If multiple collections match, we take the one with the LONGEST
    meaningful-token set (most specific). Zero matches = None.
    """
    qtoks = _tokens(query)
    if not qtoks:
        return None

    best: tuple[int, Optional[str]] = (0, None)
    for coll in active_collections:
        ctoks = _tokens(coll)
        if not ctoks:
            continue
        if ctoks.issubset(qtoks):
            specificity = len(ctoks)
            if specificity > best[0]:
                best = (specificity, coll)
    return best[1]


async def _list_active_collections() -> list[str]:
    db = get_db()
    return await db.tiles.distinct("collection", {"is_active": True})


# ───────── Candidate picking ─────────

async def pick_candidates_from_digest(
    digest: dict, *, min_impressions: int,
    max_count: int = 1, impression_multiplier: float = 1.0,
) -> list[dict]:
    """Given the current week's digest, return up to `max_count`
    queries suitable for promotion. Each must have impressions ≥
    `min_impressions * impression_multiplier` and cleanly match an
    existing collection name.

    Single-mode: `max_count=1, impression_multiplier=1.0` → behaves
    exactly like the v1 single-promotion picker.

    Batch-mode: `max_count=5, impression_multiplier=2.0` → picks up
    to 5 strong candidates, each at the doubled-threshold bar so we
    don't promote noise.

    Each promotion is committed INTO the collection_keywords live as
    we iterate (via skip-if-already-present) so two batch-candidates
    mapping to the same collection + query aren't double-counted.
    """
    if not digest.get("gsc_connected"):
        return []
    new_missed = digest.get("new_missed") or []
    if not new_missed or max_count < 1:
        return []

    effective_min = int(round(min_impressions * max(1.0, impression_multiplier)))
    # Sort by impressions desc (defensive — _compute already does this)
    ranked = sorted(
        new_missed, key=lambda m: (m.get("impressions", 0), m.get("clicks", 0)), reverse=True,
    )
    active_collections = await _list_active_collections()

    from services.stealth_seo import get_collection_keywords
    # Track collections we've ALREADY picked for so batch mode doesn't
    # pick two different queries mapping to the same collection in
    # the same run. Also tracks (collection, query) pairs to prevent
    # dupes when the digest happens to have near-duplicate queries.
    picked_coll: set[str] = set()
    picked_kw_keys: set[str] = set()
    candidates: list[dict] = []

    for m in ranked:
        if len(candidates) >= max_count:
            break
        if (m.get("impressions", 0) or 0) < effective_min:
            continue
        q = (m.get("query") or "").strip()
        if not q:
            continue
        coll = await _find_matching_collection(q, active_collections)
        if not coll:
            continue
        if coll in picked_coll:
            # One promotion per collection per run — keeps the email
            # readable and avoids burying a single collection under
            # 3 new kws in one week.
            continue
        kw_key = f"{coll.lower()}::{q.lower()}"
        if kw_key in picked_kw_keys:
            continue
        existing = await get_collection_keywords(coll)
        if any(e.lower() == q.lower() for e in existing):
            continue
        picked_coll.add(coll)
        picked_kw_keys.add(kw_key)
        candidates.append({
            "query": q, "collection": coll,
            "impressions": m.get("impressions", 0),
            "clicks": m.get("clicks", 0),
            "position": m.get("position"),
        })
    return candidates


async def pick_candidate_from_digest(
    digest: dict, *, min_impressions: int,
) -> Optional[dict]:
    """Backward-compat wrapper around `pick_candidates_from_digest`
    for the single-promotion path (keeps existing tests + callers
    untouched)."""
    rows = await pick_candidates_from_digest(
        digest, min_impressions=min_impressions, max_count=1, impression_multiplier=1.0,
    )
    return rows[0] if rows else None


# ───────── Apply + record ─────────

async def apply_auto_promote(candidate: dict) -> dict:
    """Writes the keyword to the collection AND records a rollback
    row. Returns the full record (including token) for the digest email.
    """
    from services.stealth_seo import get_collection_keywords, set_collection_keywords

    db = get_db()
    existing = await get_collection_keywords(candidate["collection"])
    merged = [*existing, candidate["query"]]
    await set_collection_keywords(
        candidate["collection"], merged, admin_email="auto-promote@cron",
    )

    row = {
        "id": secrets.token_hex(8),
        "query": candidate["query"],
        "collection": candidate["collection"],
        "added_keyword": candidate["query"],
        "impressions": candidate["impressions"],
        "clicks": candidate["clicks"],
        "position": candidate.get("position"),
        "token": secrets.token_urlsafe(24),
        "promoted_at": datetime.now(timezone.utc),
        "undone_at": None,
        "promoted_by": "cron",
    }
    await db.seo_stealth_auto_promotes.insert_one(dict(row))
    logger.info(
        "Stealth auto-promote: %r → collection=%r (id=%s, impressions=%s)",
        row["query"], row["collection"], row["id"], row["impressions"],
    )
    return row


async def undo_by_token(token: str) -> dict:
    """Removes the promoted keyword from wherever it was applied
    (collection-wide keywords OR city-page hidden_seo_keywords) and
    stamps `undone_at`. Idempotent — second undo of the same token
    is a no-op returning the original record.

    Dispatches on the row's `scope` field: `"city_page"` delegates to
    `stealth_seo_local_seed.undo_city_seed`; anything else (default
    or explicit `"collection"`) uses the collection-keywords path.
    """
    db = get_db()
    row = await db.seo_stealth_auto_promotes.find_one({"token": token}, {"_id": 0})
    if not row:
        return {"ok": False, "reason": "not_found"}
    if row.get("undone_at"):
        return {"ok": True, "already_undone": True, "record": row}

    # City-page scope — delegate
    if row.get("scope") == "city_page":
        from services import stealth_seo_local_seed
        return await stealth_seo_local_seed.undo_city_seed(token, row)

    # Default: collection scope
    from services.stealth_seo import get_collection_keywords, set_collection_keywords
    collection = row["collection"]
    kw = row["added_keyword"]
    existing = await get_collection_keywords(collection)
    kw_was_present = any(e.lower() == kw.lower() for e in existing)
    remaining = [e for e in existing if e.lower() != kw.lower()]
    await set_collection_keywords(
        collection, remaining, admin_email="auto-promote-undo@cron",
    )
    now = datetime.now(timezone.utc)
    await db.seo_stealth_auto_promotes.update_one(
        {"token": token},
        {"$set": {"undone_at": now, "kw_was_present_at_undo": kw_was_present}},
    )
    row["undone_at"] = now
    row["kw_was_present_at_undo"] = kw_was_present
    return {
        "ok": True, "already_undone": False, "record": row,
        "kw_was_present_at_undo": kw_was_present,
    }


async def undo_by_record_id(record_id: str) -> dict:
    """Single-query undo helper — the admin "Undo" button in /admin/seo
    hits this. Avoids the extra round-trip of fetch-token-then-undo.
    """
    db = get_db()
    row = await db.seo_stealth_auto_promotes.find_one(
        {"id": record_id}, {"_id": 0},
    )
    if not row:
        return {"ok": False, "reason": "not_found"}
    return await undo_by_token(row["token"])


async def list_recent(limit: int = 10) -> list[dict]:
    db = get_db()
    cutoff = datetime.now(timezone.utc) - timedelta(days=60)
    rows = await db.seo_stealth_auto_promotes.find(
        {"promoted_at": {"$gte": cutoff}},
        {"_id": 0},
    ).sort("promoted_at", -1).limit(limit).to_list(length=limit)
    return rows


async def list_since(since: datetime) -> list[dict]:
    """List rows promoted AT or AFTER `since`. Used by the digest
    builder to surface "last week's auto-promotions" at the top of
    the email."""
    db = get_db()
    rows = await db.seo_stealth_auto_promotes.find(
        {"promoted_at": {"$gte": since}},
        {"_id": 0},
    ).sort("promoted_at", -1).to_list(length=20)
    return rows


# ───────── The runner ─────────

async def run_once(
    digest: dict, settings: dict,
) -> list[dict]:
    """Invoked by the weekly cron BEFORE sending the digest email.
    Returns the list of promotion records that were applied (empty
    list if auto-promote is disabled or nothing qualified).

    Single-mode (`auto_promote_batch_mode=False`): returns at most 1
    record at the base `min_impressions` threshold.

    Batch-mode (`auto_promote_batch_mode=True`): returns up to
    `auto_promote_batch_max` records (default 5), each having met
    the 2× base threshold.

    Fully defensive — any error is logged and an empty list returned
    so the digest email still sends.
    """
    if not settings.get("auto_promote_enabled", False):
        return []
    min_impr = int(settings.get("auto_promote_min_impressions") or 20)
    batch_mode = bool(settings.get("auto_promote_batch_mode", False))
    if batch_mode:
        max_count = int(settings.get("auto_promote_batch_max") or 5)
        multiplier = 2.0
    else:
        max_count = 1
        multiplier = 1.0
    try:
        candidates = await pick_candidates_from_digest(
            digest, min_impressions=min_impr,
            max_count=max_count, impression_multiplier=multiplier,
        )
    except Exception:  # noqa: BLE001
        logger.exception("auto-promote pick_candidates failed")
        return []
    if not candidates:
        return []
    applied: list[dict] = []
    for cand in candidates:
        try:
            rec = await apply_auto_promote(cand)
            applied.append(rec)
        except Exception:  # noqa: BLE001
            logger.exception("auto-promote apply failed for %r", cand.get("query"))
            continue
    return applied

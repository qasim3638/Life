"""
Stealth-Keyword Local Seeder
────────────────────────────

Specialised variant of auto-promote that targets *city landing pages*
instead of collections. The app already auto-generates 168 UK city
landing pages (34 towns × 8 intents like "tile-shop-gravesend",
"bathroom-tiles-brighton"). When GSC surfaces a local missed-win
query like "tiles gravesend" or "tile shop tunbridge wells", this
module promotes it directly into the matching city-page's
`hidden_seo_keywords` — so the right city-page (not a collection)
starts ranking for that query.

Why a separate module from `stealth_seo_auto_promote`?
  • Different target table (`city_landing_pages` vs `tiles` /
    `seo_collection_keywords`)
  • Different matching logic (town-name extraction + intent match
    vs collection-name token subset)
  • Different SSR injection path (city-page meta via
    `/api/shop/city-page/{slug}` vs collection meta)

But they SHARE the `seo_stealth_auto_promotes` audit collection +
undo token mechanic. A `scope` field on each row tells `undo_by_token`
which table to roll back against. This keeps the digest email's
[Undo] links + the admin history table working uniformly across
both flows.

Storage:
  • seo_stealth_auto_promotes.scope = "city_page"
  • seo_stealth_auto_promotes.city_slug = "tile-shop-gravesend" (the
    slug of the page that got the keyword)
"""
from __future__ import annotations

import logging
import re
import secrets
from datetime import datetime, timezone
from typing import Optional

from config import get_db

logger = logging.getLogger(__name__)


_TOKEN_RE = re.compile(r"[a-z0-9]+")
# Generic stopwords that shouldn't count toward intent matching
_STOPWORDS = {"the", "a", "and", "uk", "buy", "shop", "near", "me",
              "best", "cheap", "sale", "tile", "tiles", "for"}


def _tokens(s: str) -> list[str]:
    if not s:
        return []
    return _TOKEN_RE.findall(s.lower())


def _meaningful_tokens(s: str) -> set[str]:
    return {t for t in _tokens(s) if len(t) >= 3 and t not in _STOPWORDS}


# ───────── Load + match ─────────

async def _load_city_pages_index() -> list[dict]:
    """Returns `[{slug, town, town_lower, county, intent_slug, intent_tokens}]`
    for every eligible city-page (generated OR approved — we still want
    stealth keywords on pages that are queued for approval).
    """
    db = get_db()
    rows = await db.city_landing_pages.find(
        {"status": {"$in": ["generated", "approved", "published"]}},
        {"_id": 0, "slug": 1, "town": 1, "town_slug": 1,
         "county": 1, "intent_slug": 1, "intent_phrase": 1},
    ).to_list(length=500)
    out = []
    for r in rows:
        town = (r.get("town") or "").strip()
        if not town:
            continue
        out.append({
            "slug": r.get("slug"),
            "town": town,
            "town_lower": town.lower(),
            "town_slug": r.get("town_slug") or town.lower().replace(" ", "-"),
            "county": r.get("county"),
            "intent_slug": r.get("intent_slug"),
            "intent_tokens": _meaningful_tokens(r.get("intent_phrase") or r.get("intent_slug") or ""),
        })
    return out


def find_matching_city_page(query: str, pages: list[dict]) -> Optional[dict]:
    """Given a missed-win query string and a list of candidate city
    pages, return the single best-matching page (or None).

    Algorithm:
      1. The query MUST contain the town name as a whole-word token
         (or its town_slug with dashes treated as spaces). This is the
         hard gate — no town, no match.
      2. Among all pages for that town, pick the one whose intent
         phrase tokens have the largest overlap with the query tokens.
         Break ties by preferring the generic "tile-shop" intent (most
         broadly applicable).
    """
    qtoks = _meaningful_tokens(query)
    qnorm = " ".join(_tokens(query))
    if not qtoks or not qnorm:
        return None

    # Only towns that appear as whole-word tokens in the query
    hits: list[tuple[int, dict]] = []
    for p in pages:
        town_tokens = _tokens(p["town"])
        if not town_tokens:
            continue
        # Multi-word town: every town token must appear in the query.
        # We check BOTH the meaningful-token set (qtoks) AND the raw
        # token list (_tokens(query)) — the latter is needed because
        # short town tokens like "st" in "St Albans" are 2-char-short
        # and stopword-y, so they're filtered out of qtoks but ARE in
        # the raw _tokens(query) output. Leaving the second clause in
        # keeps multi-word town matching working for those cases.
        if not all(t in qtoks or t in _tokens(query) for t in town_tokens):
            continue
        intent_overlap = len(p["intent_tokens"] & qtoks)
        # Score: intent overlap + small bonus for being a tile-shop
        # intent (broadest fallback)
        score = intent_overlap * 10
        if p["intent_slug"] == "tile-shop":
            score += 1
        hits.append((score, p))

    if not hits:
        return None
    hits.sort(key=lambda x: x[0], reverse=True)
    return hits[0][1]


# ───────── Candidate picking ─────────

async def pick_local_candidates_from_digest(
    digest: dict, *, min_impressions: int,
    max_count: int = 1, impression_multiplier: float = 1.0,
) -> list[dict]:
    """Same shape as the collection picker but targets city pages.
    Returns `[{query, slug, town, intent_slug, impressions, clicks, position}]`.

    Enforces:
      • one seed per city-page per run
      • skips queries already in that page's hidden_seo_keywords
      • skips if impressions < `min_impressions * impression_multiplier`
    """
    if not digest.get("gsc_connected"):
        return []
    new_missed = digest.get("new_missed") or []
    if not new_missed or max_count < 1:
        return []

    effective_min = int(round(min_impressions * max(1.0, impression_multiplier)))
    ranked = sorted(
        new_missed, key=lambda m: (m.get("impressions", 0), m.get("clicks", 0)), reverse=True,
    )
    pages = await _load_city_pages_index()
    if not pages:
        return []

    picked_slugs: set[str] = set()
    candidates: list[dict] = []

    db = get_db()
    for m in ranked:
        if len(candidates) >= max_count:
            break
        if (m.get("impressions", 0) or 0) < effective_min:
            continue
        q = (m.get("query") or "").strip()
        if not q:
            continue
        page = find_matching_city_page(q, pages)
        if not page:
            continue
        if page["slug"] in picked_slugs:
            continue
        # Skip if already present in the city-page's kws
        row = await db.city_landing_pages.find_one(
            {"slug": page["slug"]},
            {"_id": 0, "hidden_seo_keywords": 1},
        )
        existing_raw = (row or {}).get("hidden_seo_keywords") or ""
        if isinstance(existing_raw, str):
            existing = [s.strip() for s in re.split(r"[,\n]+", existing_raw) if s.strip()]
        else:
            existing = [str(s).strip() for s in existing_raw if str(s).strip()]
        if any(e.lower() == q.lower() for e in existing):
            continue
        picked_slugs.add(page["slug"])
        candidates.append({
            "query": q,
            "slug": page["slug"],
            "town": page["town"],
            "intent_slug": page["intent_slug"],
            "impressions": m.get("impressions", 0),
            "clicks": m.get("clicks", 0),
            "position": m.get("position"),
        })
    return candidates


# ───────── Apply + record ─────────

async def apply_local_seed(candidate: dict) -> dict:
    """Writes the query to `city_landing_pages.hidden_seo_keywords`
    AND records a rollback row in `seo_stealth_auto_promotes` with
    `scope="city_page"` so the shared `undo_by_token` machinery can
    roll it back.
    """
    db = get_db()
    row = await db.city_landing_pages.find_one(
        {"slug": candidate["slug"]},
        {"_id": 0, "hidden_seo_keywords": 1},
    )
    existing_raw = (row or {}).get("hidden_seo_keywords") or ""
    if isinstance(existing_raw, str):
        existing = [s.strip() for s in re.split(r"[,\n]+", existing_raw) if s.strip()]
    else:
        existing = [str(s).strip() for s in existing_raw if str(s).strip()]
    merged = [*existing, candidate["query"]]
    # Cap at 25 kws per page (same bound as products/collections).
    # Keep the NEWEST 25 so fresh seeds never get silently dropped
    # when the page is at the cap — the oldest entries fall off
    # instead (easy to re-add from the admin UI if still relevant).
    if len(merged) > 25:
        dropped = len(merged) - 25
        logger.info(
            "Local seed: dropping %d oldest kw(s) from city-page %r to stay at 25-cap",
            dropped, candidate["slug"],
        )
    merged_capped = merged[-25:]
    now = datetime.now(timezone.utc)
    await db.city_landing_pages.update_one(
        {"slug": candidate["slug"]},
        {"$set": {
            "hidden_seo_keywords": ", ".join(merged_capped),
            "hidden_seo_keywords_updated_at": now,
            "hidden_seo_keywords_updated_by": "local-seeder@cron",
        }},
    )
    record = {
        "id": secrets.token_hex(8),
        "scope": "city_page",
        "query": candidate["query"],
        "city_slug": candidate["slug"],
        "collection": None,  # inherited field, N/A for city-page scope
        "town": candidate.get("town"),
        "intent_slug": candidate.get("intent_slug"),
        "added_keyword": candidate["query"],
        "impressions": candidate["impressions"],
        "clicks": candidate["clicks"],
        "position": candidate.get("position"),
        "token": secrets.token_urlsafe(24),
        "promoted_at": now,
        "undone_at": None,
        "promoted_by": "cron",
    }
    await db.seo_stealth_auto_promotes.insert_one(dict(record))
    logger.info(
        "Local seed: %r → city-page %r (town=%s, slug=%s, impressions=%s)",
        record["query"], record["city_slug"], record["town"], record["city_slug"],
        record["impressions"],
    )
    return record


async def undo_city_seed(token: str, row: dict) -> dict:
    """Scope-specific undo. Called by the shared `undo_by_token` when
    it detects `scope == 'city_page'`. Removes the kw from the city
    page's `hidden_seo_keywords` field and stamps `undone_at`.
    """
    db = get_db()
    slug = row.get("city_slug")
    kw = row.get("added_keyword") or row.get("query")
    page = await db.city_landing_pages.find_one(
        {"slug": slug}, {"_id": 0, "hidden_seo_keywords": 1},
    )
    existing_raw = (page or {}).get("hidden_seo_keywords") or ""
    if isinstance(existing_raw, str):
        existing = [s.strip() for s in re.split(r"[,\n]+", existing_raw) if s.strip()]
    else:
        existing = [str(s).strip() for s in existing_raw if str(s).strip()]
    kw_was_present = any(e.lower() == kw.lower() for e in existing)
    remaining = [e for e in existing if e.lower() != kw.lower()]
    now = datetime.now(timezone.utc)
    await db.city_landing_pages.update_one(
        {"slug": slug},
        {"$set": {
            "hidden_seo_keywords": ", ".join(remaining),
            "hidden_seo_keywords_updated_at": now,
            "hidden_seo_keywords_updated_by": "local-seeder-undo@cron",
        }},
    )
    await db.seo_stealth_auto_promotes.update_one(
        {"token": token},
        {"$set": {"undone_at": now, "kw_was_present_at_undo": kw_was_present}},
    )
    row["undone_at"] = now
    row["kw_was_present_at_undo"] = kw_was_present
    return {"ok": True, "already_undone": False, "record": row,
            "kw_was_present_at_undo": kw_was_present}


# ───────── The runner ─────────

async def run_once(digest: dict, settings: dict) -> list[dict]:
    """Invoked by the weekly cron (before the collection auto-promote
    runs). Returns the list of local seed records applied (empty when
    disabled / no qualifying candidates).

    Budget sharing: local seeds and collection auto-promotes pull
    from the SAME weekly quota — if batch_max=5 and local seeds
    consume 2, collections get at most 3. The cron coordinator
    (stealth_seo_digest.run_weekly_digest_if_due) enforces this by
    subtracting local-seed count from the remaining budget it passes
    to `stealth_seo_auto_promote.run_once`.

    Fully defensive — any error is logged and an empty list returned.
    """
    if not settings.get("auto_local_seed_enabled", False):
        return []
    if not settings.get("auto_promote_enabled", False):
        # Local seed piggy-backs on auto-promote being enabled so the
        # admin doesn't accidentally turn on one without the other.
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
        candidates = await pick_local_candidates_from_digest(
            digest, min_impressions=min_impr,
            max_count=max_count, impression_multiplier=multiplier,
        )
    except Exception:  # noqa: BLE001
        logger.exception("local seed pick failed")
        return []
    if not candidates:
        return []
    applied: list[dict] = []
    for cand in candidates:
        try:
            rec = await apply_local_seed(cand)
            applied.append(rec)
        except Exception:  # noqa: BLE001
            logger.exception("local seed apply failed for %r", cand.get("query"))
            continue
    return applied

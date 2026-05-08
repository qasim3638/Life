"""
Stealth-Keyword Performance — attribution layer
─────────────────────────────────────────────────

Joins two data sources:
  1. Google Search Console — every query that surfaced our site, with
     clicks + impressions + CTR + average position (last N days).
  2. Our own catalogue — every stealth keyword set on each tile
     (`hidden_seo_keywords`, `original_name`, `supplier_code`) and
     every collection-wide alt-name set (`seo_collection_keywords`).

For each GSC query we classify it as:
  • stealth_win  — query matched a stealth keyword (the supplier name
                   brought the customer in, even though we never showed
                   the supplier name on the visible page)
  • brand_win    — query matched a product/collection's customer-facing
                   name (the re-branded name worked on its own)
  • other        — neither (generic phrase like "marble tile UK")

Then we surface:
  • Top 20 winning supplier names by clicks    — proof the trick works
  • "Missed wins" — top GSC queries that DON'T yet match any stealth
                    keyword (the supplier names we should ADD)
  • "Underperformers" — stealth keywords set in DB but zero GSC traffic
                        (set them but Google never showed them; either
                        no demand or we need more crawl/backlinks)

Cached for 1 hour in `seo_stealth_perf_cache` (GSC data is daily, so
hour-fresh is plenty).
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from config import get_db
from services import gsc as gsc_service

logger = logging.getLogger(__name__)


CACHE_TTL_HOURS = 1
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_MIN_KW_LEN = 3  # ignore "tv" "x" etc. — too noisy


def _tokens(s: str) -> list[str]:
    if not s:
        return []
    return _TOKEN_RE.findall(s.lower())


def _normalise_for_match(s: str) -> str:
    """Lowercase + strip every non-alphanumeric so codes round-trip:
    "LP-6611" → "lp6611"   →   matches "lp 6611" → "lp6611"
                                       "lp/6611" → "lp6611"
    """
    if not s:
        return ""
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def _query_tokens(query: str) -> set[str]:
    return {t for t in _tokens(query) if len(t) >= _MIN_KW_LEN}


def _kw_tokens(keyword: str) -> tuple[str, set[str]]:
    """A keyword can be a phrase ("Onyx White Polished") or a code
    ("LP-6611"). We track BOTH the joined alphanumeric form (so codes
    match cleanly) AND the token set (so phrases match without
    requiring word-order)."""
    norm = _normalise_for_match(keyword)
    toks = {t for t in _tokens(keyword) if len(t) >= _MIN_KW_LEN}
    return norm, toks


def _query_matches_keyword(query: str, keyword: str) -> bool:
    """Does this GSC query MATCH this stealth keyword?

    Match rules (in order of strictness):
      1. Phrase match — every alphanumeric token of the keyword
         appears in the query (any order, length≥3 chars).
         Example: "onyx white polished" matches query "onyx white tile UK"
      2. Code match — for keywords without spaces (single token,
         common for SKUs like "LP-6611"), the joined alphanumeric
         form is found as a substring of the query's joined form.
         Example: "LP-6611" matches "lp6611 datasheet"
      3. Single-token phrase — fall through to token-in-tokens.
    """
    qnorm = _normalise_for_match(query)
    if not qnorm or not keyword:
        return False
    knorm, ktoks = _kw_tokens(keyword)
    if not knorm:
        return False
    qtoks = _query_tokens(query)

    # Code/SKU substring match — only when the keyword has no spaces
    # AND has a digit (real codes like LP-6611). Plain English single
    # words go through the token path so "marble" doesn't match
    # "marbleized".
    has_digit = any(c.isdigit() for c in knorm)
    if " " not in keyword.strip() and has_digit:
        if knorm in qnorm:
            return True

    # Phrase match — every keyword token in query tokens
    if ktoks and ktoks.issubset(qtoks):
        return True
    return False


# ───────── Loaders ─────────

async def _load_stealth_universe() -> dict:
    """Pull every stealth keyword in the catalogue + every product
    name (so we can classify queries against the brand-name corpus
    too). Returns a normalised structure ready for matching."""
    db = get_db()
    products = []
    cursor = db.tiles.find(
        {"is_active": True},
        {"_id": 0, "id": 1, "name": 1, "slug": 1, "collection": 1,
         "hidden_seo_keywords": 1, "original_name": 1, "supplier_code": 1},
    )
    async for p in cursor:
        kws_raw = p.get("hidden_seo_keywords") or ""
        if isinstance(kws_raw, str):
            kws = [s.strip() for s in re.split(r"[,\n]+", kws_raw) if s.strip()]
        elif isinstance(kws_raw, (list, tuple, set)):
            kws = [str(s).strip() for s in kws_raw if str(s).strip()]
        else:
            kws = []
        products.append({
            "id": p.get("id"),
            "name": (p.get("name") or "").strip(),
            "slug": p.get("slug"),
            "collection": (p.get("collection") or "").strip(),
            "stealth_keywords": kws,
            "original_name": (p.get("original_name") or "").strip(),
            "supplier_code": (p.get("supplier_code") or "").strip(),
        })

    # Collection-wide alt-names
    coll_kw_map: dict[str, list[str]] = {}
    async for c in db.seo_collection_keywords.find({}, {"_id": 0}):
        kws = c.get("keywords") or []
        if isinstance(kws, str):
            kws = [s.strip() for s in re.split(r"[,\n]+", kws) if s.strip()]
        coll_kw_map[c.get("collection") or ""] = [k for k in kws if k]

    return {"products": products, "collection_keywords": coll_kw_map}


# ───────── Attribution ─────────

def _attribute_query(query: str, universe: dict) -> dict:
    """Classify a single GSC query against the stealth universe.

    Returns a dict with one of:
      {"kind": "stealth_win", "matches": [{"keyword": ..., "product_id": ..., "scope": "product|collection"}]}
      {"kind": "brand_win", "product_id": ..., "name": ...}
      {"kind": "other"}
    """
    matches: list[dict] = []
    qtoks_full = _query_tokens(query)
    if not qtoks_full:
        return {"kind": "other"}

    # 1) Per-product stealth keywords
    for p in universe["products"]:
        for kw in p["stealth_keywords"]:
            if _query_matches_keyword(query, kw):
                matches.append({
                    "keyword": kw, "product_id": p["id"],
                    "product_name": p["name"], "product_slug": p["slug"],
                    "scope": "product",
                })

    # 2) Collection-wide stealth keywords
    for coll, kws in universe["collection_keywords"].items():
        for kw in kws:
            if _query_matches_keyword(query, kw):
                matches.append({
                    "keyword": kw, "collection": coll, "scope": "collection",
                })

    if matches:
        return {"kind": "stealth_win", "matches": matches}

    # 3) Brand name match — does the query match a product's
    #    customer-facing name? (Phrase token match.)
    for p in universe["products"]:
        if not p["name"]:
            continue
        if _query_matches_keyword(query, p["name"]):
            return {
                "kind": "brand_win",
                "product_id": p["id"],
                "product_name": p["name"],
                "product_slug": p["slug"],
            }

    return {"kind": "other"}


# ───────── Top-level runner + cache ─────────

async def get_performance(
    *, days: int = 28, force_refresh: bool = False,
) -> dict:
    """Returns the full performance report — cached for 1 hour."""
    db = get_db()
    cache_key = f"perf::{days}"
    if not force_refresh:
        cached = await db.seo_stealth_perf_cache.find_one(
            {"key": cache_key}, {"_id": 0},
        )
        if cached:
            cached_at = cached.get("cached_at")
            if isinstance(cached_at, datetime):
                if cached_at.tzinfo is None:
                    cached_at = cached_at.replace(tzinfo=timezone.utc)
                if (datetime.now(timezone.utc) - cached_at) < timedelta(hours=CACHE_TTL_HOURS):
                    return cached.get("report") or {}

    report = await _compute(days=days)
    await db.seo_stealth_perf_cache.update_one(
        {"key": cache_key},
        {"$set": {
            "key": cache_key,
            "cached_at": datetime.now(timezone.utc),
            "report": report,
        }},
        upsert=True,
    )
    return report


async def _compute(*, days: int) -> dict:
    """Pull GSC data, attribute each query, aggregate.

    Returns a `report` dict ready for the UI:
      {
        days, gsc_connected: bool,
        totals: {clicks, impressions, ctr, queries_count},
        stealth: {clicks, impressions, ctr, queries_count, share_pct},
        brand:   {clicks, impressions, ctr, queries_count, share_pct},
        other:   {clicks, impressions, ctr, queries_count, share_pct},
        top_winners: [{keyword, clicks, impressions, ctr, attribution_count, scope}, ...up to 20],
        missed_wins: [{query, clicks, impressions, ctr, position}, ...up to 20]
                       (queries with no stealth match but high traffic),
        underperformers: [{keyword, scope, product_name?, collection?},
                           ...keywords set but zero GSC traffic],
        generated_at: iso8601,
      }
    """
    admin_id = await gsc_service._pick_connected_admin()
    if not admin_id:
        return _empty_report(days, gsc_connected=False, reason="GSC not connected")

    try:
        # Pull 5000 queries — far more than the standard top-25 — so we
        # can attribute the long tail. GSC API caps at 25 000/day per
        # property, well within our budget.
        gsc_data = await gsc_service.get_top_queries(admin_id, days=days, limit=5000)
    except Exception as exc:
        logger.exception("get_top_queries failed for stealth perf")
        return _empty_report(days, gsc_connected=True, reason=f"gsc_error: {str(exc)[:200]}")

    rows = gsc_data.get("rows") or []
    universe = await _load_stealth_universe()

    bucket_stealth = _new_bucket()
    bucket_brand = _new_bucket()
    bucket_other = _new_bucket()

    # Aggregate by keyword for the "top winners" table
    keyword_agg: dict[str, dict] = {}
    missed: list[dict] = []
    seen_kws_with_traffic: set[str] = set()

    for r in rows:
        q = (r.get("query") or "").strip()
        if not q:
            continue
        clicks = int(r.get("clicks") or 0)
        impressions = int(r.get("impressions") or 0)
        ctr = float(r.get("ctr") or 0.0)
        position = float(r.get("position") or 0.0)

        att = _attribute_query(q, universe)
        if att["kind"] == "stealth_win":
            _bump(bucket_stealth, clicks, impressions)
            for m in att["matches"]:
                kw = m["keyword"]
                seen_kws_with_traffic.add(kw.lower())
                slot = keyword_agg.setdefault(kw, {
                    "keyword": kw, "scope": m.get("scope"),
                    "product_name": m.get("product_name"),
                    "product_slug": m.get("product_slug"),
                    "collection": m.get("collection"),
                    "clicks": 0, "impressions": 0, "queries": 0,
                })
                # Avoid double-counting the SAME query when matched by
                # multiple variants of the same keyword phrase: we
                # increment the slot once per (kw, query). The sum of
                # all slot clicks WILL exceed bucket_stealth total when
                # one query matches multiple kws — that's fine because
                # we're showing per-kw attribution, but we mark it.
                slot["clicks"] += clicks
                slot["impressions"] += impressions
                slot["queries"] += 1
        elif att["kind"] == "brand_win":
            _bump(bucket_brand, clicks, impressions)
        else:
            _bump(bucket_other, clicks, impressions)
            # Stash high-traffic non-matches as "missed wins"
            if impressions >= 5:  # noise filter
                missed.append({
                    "query": q, "clicks": clicks, "impressions": impressions,
                    "ctr": round(ctr, 4), "position": round(position, 1),
                })

    totals = _new_bucket()
    totals["clicks"] = bucket_stealth["clicks"] + bucket_brand["clicks"] + bucket_other["clicks"]
    totals["impressions"] = bucket_stealth["impressions"] + bucket_brand["impressions"] + bucket_other["impressions"]
    totals["queries_count"] = bucket_stealth["queries_count"] + bucket_brand["queries_count"] + bucket_other["queries_count"]
    totals["ctr"] = (totals["clicks"] / totals["impressions"]) if totals["impressions"] else 0.0

    for b in (bucket_stealth, bucket_brand, bucket_other):
        b["ctr"] = (b["clicks"] / b["impressions"]) if b["impressions"] else 0.0
        b["share_pct"] = round((b["clicks"] / totals["clicks"]) * 100) if totals["clicks"] else 0

    # Top winners — sort by clicks
    winners = sorted(keyword_agg.values(), key=lambda x: (x["clicks"], x["impressions"]), reverse=True)[:20]
    for w in winners:
        w["ctr"] = round((w["clicks"] / w["impressions"]) if w["impressions"] else 0.0, 4)

    # Missed wins — top by impressions then clicks. Drop dupes after
    # sorting (GSC sometimes splits casing).
    missed.sort(key=lambda x: (x["impressions"], x["clicks"]), reverse=True)
    seen_q: set[str] = set()
    missed_unique: list[dict] = []
    for m in missed:
        ql = m["query"].lower()
        if ql in seen_q:
            continue
        seen_q.add(ql)
        missed_unique.append(m)
        if len(missed_unique) >= 20:
            break

    # Underperformers — keywords set in DB but never seen with traffic.
    # Walk the universe, skip ones already in seen_kws_with_traffic.
    underperformers: list[dict] = []
    seen_added: set[str] = set()
    for p in universe["products"]:
        for kw in p["stealth_keywords"]:
            if kw.lower() in seen_kws_with_traffic:
                continue
            if kw.lower() in seen_added:
                continue
            seen_added.add(kw.lower())
            underperformers.append({
                "keyword": kw, "scope": "product",
                "product_id": p["id"], "product_name": p["name"],
                "product_slug": p["slug"],
            })
            if len(underperformers) >= 50:
                break
        if len(underperformers) >= 50:
            break
    for coll, kws in universe["collection_keywords"].items():
        if len(underperformers) >= 50:
            break
        for kw in kws:
            if kw.lower() in seen_kws_with_traffic:
                continue
            if kw.lower() in seen_added:
                continue
            seen_added.add(kw.lower())
            underperformers.append({
                "keyword": kw, "scope": "collection", "collection": coll,
            })
            if len(underperformers) >= 50:
                break

    return {
        "days": days,
        "gsc_connected": True,
        "totals": totals,
        "stealth": bucket_stealth,
        "brand": bucket_brand,
        "other": bucket_other,
        "top_winners": winners,
        "missed_wins": missed_unique,
        "underperformers": underperformers,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "site_url": gsc_data.get("site_url"),
        "start_date": gsc_data.get("start_date"),
        "end_date": gsc_data.get("end_date"),
    }


def _new_bucket() -> dict:
    return {"clicks": 0, "impressions": 0, "ctr": 0.0,
            "queries_count": 0, "share_pct": 0}


def _bump(bucket: dict, clicks: int, impressions: int) -> None:
    bucket["clicks"] += clicks
    bucket["impressions"] += impressions
    bucket["queries_count"] += 1


def _empty_report(days: int, *, gsc_connected: bool, reason: Optional[str] = None) -> dict:
    return {
        "days": days,
        "gsc_connected": gsc_connected,
        "reason": reason,
        "totals": _new_bucket(),
        "stealth": _new_bucket(),
        "brand": _new_bucket(),
        "other": _new_bucket(),
        "top_winners": [],
        "missed_wins": [],
        "underperformers": [],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

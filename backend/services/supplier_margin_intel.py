"""
Supplier Margin Intelligence
────────────────────────────

Closes the "storytelling" gap in the SEO/margin stack. For every
active product, joins:
  • `tiles.cost_price`   (what you pay the supplier)
  • `tiles.price`        (what customers pay you)
  • `tiles.supplier_name` / `original_supplier_name`  (who supplied it)
  • GSC impressions for this product's stealth keywords + original name
    (the product's share of organic traffic)

…and answers the question your sales reps can't answer today:

  "Which 20 products are driving BOTH the most margin AND the most
   organic traffic RIGHT NOW?"

Shape of each row:
  {
    product_id, slug, name, image_url,
    supplier_name, supplier_code,
    cost_price, price, margin_abs, margin_pct,
    impressions_this_week, impressions_last_week, impressions_delta_pct,
    clicks_this_week,
    score  (composite: margin_pct × log1p(impressions_this_week))
  }

Ranking: sorted by `score` desc so the top 20 are the products with
BOTH a fat margin AND real organic demand. Rev-gen collections to
expand in Q2. Low-score products with high impressions + low margin
are candidates for price testing ("can we raise the price?").

Aggregations are cached for 1 hour in `seo_supplier_margin_cache`.
GSC data is pulled from the same query→query-date dimension we
already use for attribution timelines (no extra quota cost).
"""
from __future__ import annotations

import logging
import math
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from config import get_db

logger = logging.getLogger(__name__)


CACHE_COLLECTION = "seo_supplier_margin_cache"
CACHE_TTL_HOURS = 1


# ───────── Helpers ─────────

def _safe_float(v) -> Optional[float]:
    try:
        if v is None:
            return None
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _split_kws(raw) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, (list, tuple, set)):
        return [str(k).strip() for k in raw if str(k).strip()]
    return [s.strip() for s in re.split(r"[,\n]+", str(raw)) if s.strip()]


def _product_query_set(p: dict) -> list[str]:
    """Return the keyword phrases we'll attribute GSC impressions to
    for this product: original_name + supplier_code + all
    hidden_seo_keywords. Deduped case-insensitively.
    """
    phrases: list[str] = []
    for src in ("original_name", "supplier_code"):
        v = (p.get(src) or "").strip()
        if v:
            phrases.append(v)
    for kw in _split_kws(p.get("hidden_seo_keywords")):
        phrases.append(kw)
    # Dedupe preserving order
    seen: set[str] = set()
    out: list[str] = []
    for p_ in phrases:
        lp = p_.lower()
        if lp in seen:
            continue
        seen.add(lp)
        out.append(p_)
    return out


def _composite_score(margin_pct: Optional[float], impressions: int) -> float:
    """Balances margin and organic demand.
    score = margin_pct × log(1 + impressions)
    - No impressions but 60% margin → score 0 (nobody's finding it, ignore for now)
    - 5% margin but 2000 impressions → small score (volume loss-leader)
    - 45% margin + 500 impressions → SWEET SPOT — highest scores
    """
    if margin_pct is None or margin_pct <= 0:
        return 0.0
    return margin_pct * math.log1p(max(0, impressions))


def _margin(price: Optional[float], cost: Optional[float]) -> tuple[Optional[float], Optional[float]]:
    """Returns (absolute_margin, margin_pct). Either can be None when
    the product is missing cost/price. Margin_pct expressed as 0-100 (not 0-1)."""
    if price is None or cost is None or price <= 0:
        return (None, None)
    abs_m = price - cost
    pct = (abs_m / price) * 100
    return (abs_m, pct)


# ───────── GSC query-matching (reuse the existing primitive) ─────────

from services.stealth_seo_performance import _query_matches_keyword  # noqa: E402


def _attribute_gsc_rows(rows: list[dict], phrases: list[str]) -> tuple[int, int]:
    """Returns (total_clicks, total_impressions) across GSC rows where
    the query matches any of the product's tracked phrases.
    Deduped by query so one query matching 3 phrases still counts once.
    """
    clicks = 0
    impressions = 0
    matched_queries: set[str] = set()
    for row in rows:
        q = (row.get("query") or "").strip()
        if not q or q.lower() in matched_queries:
            continue
        if any(_query_matches_keyword(q, kw) for kw in phrases):
            matched_queries.add(q.lower())
            clicks += int(row.get("clicks") or 0)
            impressions += int(row.get("impressions") or 0)
    return clicks, impressions


# ───────── Report builder ─────────

async def _compute_report(*, top_n: int = 20) -> dict:
    from services import gsc as gsc_service
    db = get_db()
    now = datetime.now(timezone.utc)

    # Pull GSC once for the 14-day window so we can slice this-week
    # vs last-week per-product via the same row set.
    admin_id = await gsc_service._pick_connected_admin()
    gsc_connected = bool(admin_id)
    this_week_rows: list[dict] = []
    last_week_rows: list[dict] = []
    if gsc_connected:
        try:
            # Two separate queries — this_week=7d, last_14_days covers both.
            this = await gsc_service.get_top_queries(admin_id, days=7, limit=5000)
            fortnight = await gsc_service.get_top_queries(admin_id, days=14, limit=5000)
            this_week_rows = this.get("rows") or []
            fortnight_rows = fortnight.get("rows") or []
            # last_week = fortnight - this_week per-query (approx since
            # GSC doesn't give us a strict date split without adding
            # a date dimension, which would blow up the row count)
            by_q_fort = {
                (r.get("query") or "").lower(): r for r in fortnight_rows
            }
            by_q_this = {
                (r.get("query") or "").lower(): r for r in this_week_rows
            }
            for ql, fr in by_q_fort.items():
                tr = by_q_this.get(ql, {})
                last_week_rows.append({
                    "query": fr.get("query"),
                    "clicks": max(0, int(fr.get("clicks") or 0) - int(tr.get("clicks") or 0)),
                    "impressions": max(0, int(fr.get("impressions") or 0) - int(tr.get("impressions") or 0)),
                })
        except Exception:  # noqa: BLE001
            logger.exception("GSC fetch failed in supplier margin report")
            gsc_connected = False

    # Pull catalogue once
    products: list[dict] = []
    async for p in db.tiles.find(
        {"is_active": True},
        {"_id": 0, "id": 1, "slug": 1, "name": 1, "images": 1,
         "supplier_name": 1, "original_supplier_name": 1, "supplier_code": 1,
         "original_name": 1, "hidden_seo_keywords": 1,
         "collection": 1, "price": 1, "cost_price": 1, "sale_active": 1},
    ):
        products.append(p)

    rows: list[dict] = []
    by_supplier: dict[str, dict] = {}
    catalogue_margin_pct_samples: list[float] = []
    for p in products:
        price = _safe_float(p.get("price"))
        cost = _safe_float(p.get("cost_price"))
        abs_m, pct = _margin(price, cost)
        phrases = _product_query_set(p)
        clicks_this, impr_this = _attribute_gsc_rows(this_week_rows, phrases)
        _, impr_last = _attribute_gsc_rows(last_week_rows, phrases)
        # Impressions delta %: handle divide-by-zero
        if impr_last > 0:
            impr_delta = round(((impr_this - impr_last) / impr_last) * 100, 1)
        elif impr_this > 0:
            impr_delta = 100.0
        else:
            impr_delta = 0.0
        supplier = (p.get("supplier_name") or p.get("original_supplier_name") or "").strip() or "—"
        score = _composite_score(pct, impr_this)
        if pct is not None:
            catalogue_margin_pct_samples.append(pct)
        image_url = None
        imgs = p.get("images") or []
        if isinstance(imgs, list) and imgs:
            image_url = imgs[0]
        rows.append({
            "product_id": p.get("id"),
            "slug": p.get("slug"),
            "name": p.get("name"),
            "image_url": image_url,
            "collection": p.get("collection"),
            "supplier_name": supplier,
            "supplier_code": (p.get("supplier_code") or "").strip(),
            "original_name": (p.get("original_name") or "").strip(),
            "price": price,
            "cost_price": cost,
            "margin_abs": round(abs_m, 2) if abs_m is not None else None,
            "margin_pct": round(pct, 1) if pct is not None else None,
            "clicks_this_week": clicks_this,
            "impressions_this_week": impr_this,
            "impressions_last_week": impr_last,
            "impressions_delta_pct": impr_delta,
            "score": round(score, 3),
        })
        # Supplier rollup
        if supplier and supplier != "—":
            s_slot = by_supplier.setdefault(supplier, {
                "supplier": supplier, "product_count": 0,
                "margin_pct_sum": 0.0, "margin_pct_n": 0,
                "impressions_this_week": 0, "clicks_this_week": 0,
                "score_sum": 0.0,
            })
            s_slot["product_count"] += 1
            if pct is not None:
                s_slot["margin_pct_sum"] += pct
                s_slot["margin_pct_n"] += 1
            s_slot["impressions_this_week"] += impr_this
            s_slot["clicks_this_week"] += clicks_this
            s_slot["score_sum"] += score

    # Top N by score
    rows.sort(key=lambda r: (r["score"], r["impressions_this_week"], r.get("margin_pct") or 0), reverse=True)
    top = rows[:top_n]
    # Also surface "price-test candidates": high impressions, low margin
    price_test_candidates = sorted(
        [r for r in rows if r["impressions_this_week"] >= 50 and (r.get("margin_pct") or 0) < 30],
        key=lambda r: r["impressions_this_week"], reverse=True,
    )[:10]

    # Supplier league table
    supplier_rows: list[dict] = []
    for s in by_supplier.values():
        avg_margin = s["margin_pct_sum"] / s["margin_pct_n"] if s["margin_pct_n"] else None
        supplier_rows.append({
            "supplier": s["supplier"],
            "product_count": s["product_count"],
            "avg_margin_pct": round(avg_margin, 1) if avg_margin is not None else None,
            "impressions_this_week": s["impressions_this_week"],
            "clicks_this_week": s["clicks_this_week"],
            "score_sum": round(s["score_sum"], 2),
        })
    supplier_rows.sort(key=lambda s: s["score_sum"], reverse=True)

    summary = {
        "total_products": len(products),
        "with_cost_data": sum(1 for r in rows if r.get("margin_pct") is not None),
        "with_organic_traffic": sum(1 for r in rows if r["impressions_this_week"] > 0),
        "median_margin_pct": round(
            sorted(catalogue_margin_pct_samples)[len(catalogue_margin_pct_samples) // 2], 1,
        ) if catalogue_margin_pct_samples else None,
        "gsc_connected": gsc_connected,
    }
    return {
        "summary": summary,
        "top_revenue_gen": top,
        "price_test_candidates": price_test_candidates,
        "suppliers": supplier_rows,
        "generated_at": now.isoformat(),
    }


async def get_margin_report(
    *, top_n: int = 20, force_refresh: bool = False,
) -> dict:
    """Cached for 1 hour in `seo_supplier_margin_cache`."""
    db = get_db()
    cache_key = f"margin::{top_n}"
    if not force_refresh:
        cached = await db[CACHE_COLLECTION].find_one(
            {"key": cache_key}, {"_id": 0},
        )
        if cached:
            cached_at = cached.get("cached_at")
            if isinstance(cached_at, datetime):
                if cached_at.tzinfo is None:
                    cached_at = cached_at.replace(tzinfo=timezone.utc)
                if (datetime.now(timezone.utc) - cached_at) < timedelta(hours=CACHE_TTL_HOURS):
                    return cached.get("report") or {}
    report = await _compute_report(top_n=top_n)
    await db[CACHE_COLLECTION].update_one(
        {"key": cache_key},
        {"$set": {
            "key": cache_key,
            "cached_at": datetime.now(timezone.utc),
            "report": report,
        }},
        upsert=True,
    )
    return report

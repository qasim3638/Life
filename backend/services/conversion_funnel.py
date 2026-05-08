"""
Conversion funnel analytics — feeds the admin home dashboard card.

Aggregates the existing `page_views` and `shop_orders` collections into a
4-stage funnel sliced by traffic source. No new event tracking required.

Stages (per session, then totalled):
  1. sessions         distinct session_id with any page_view
  2. product_viewers  sessions that hit a /tiles/* or /shop/(product|collection)/* URL
  3. checkout_reached sessions that hit /checkout* or /shop/checkout*
  4. paid_orders      shop_orders rows with payment_status=='paid' (or status in
                      completed/paid/shipped/confirmed) — UNATTRIBUTED to source
                      because we don't yet propagate session_id through the
                      Stripe redirect

Traffic-source classifier (`_classify_source`) groups referrers into:
  organic / social / email / direct / other

Why not Google Analytics?
  • We already log page_views and orders ourselves. Pulling from GA4 would
    add a 24h delay and another OAuth boundary.
  • This funnel can be enhanced over time by tagging events on the
    frontend (already groundwork for "add to cart" exists in
    routes/website_admin.py) — the response shape will stay the same.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

from config import get_db

logger = logging.getLogger(__name__)


# Source classifier — order matters, first match wins.
_SOURCE_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("organic", re.compile(r"google\.|bing\.|duckduckgo\.|yahoo\.|yandex\.|baidu\.|ecosia\.", re.I)),
    ("social", re.compile(r"facebook\.|instagram\.|twitter\.|x\.com|tiktok\.|pinterest\.|linkedin\.|reddit\.", re.I)),
    ("email", re.compile(r"mail\.|outlook\.|gmail\.", re.I)),
]


def _classify_source(referrer: str | None) -> str:
    if not referrer or referrer.strip().lower() in ("direct", ""):
        return "direct"
    text = referrer.strip().lower()
    if not text.startswith("http"):
        # Bare strings like "Direct" or unknown tag — treat as direct unless
        # the value still looks like a URL we can parse.
        if "://" not in text:
            return "direct"
    try:
        host = urlparse(text).hostname or text
    except Exception:
        host = text
    for label, pat in _SOURCE_PATTERNS:
        if pat.search(host):
            return label
    return "other"


def _path_of(url: str | None) -> str:
    """Extract just the path from a (sometimes relative, sometimes absolute) URL."""
    if not url:
        return "/"
    try:
        if url.startswith("http"):
            return urlparse(url).path or "/"
        return url.split("?", 1)[0]
    except Exception:
        return "/"


_PRODUCT_RE = re.compile(r"^/(tiles|shop/(product|collection))(/|$)")
_CHECKOUT_RE = re.compile(r"^/(checkout|shop/checkout)")


async def get_funnel(*, days: int = 28) -> dict[str, Any]:
    days = max(1, min(int(days), 365))
    db = get_db()
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    # ─── Aggregate page_views into sessions × stages × source ────────────
    pipeline = [
        {"$match": {"timestamp": {"$gte": start, "$lte": end}}},
        # Single doc per (session_id, source) with per-session arrays of
        # paths. Lighter than $group → $project chain.
        {"$group": {
            "_id": "$session_id",
            "first_referrer": {"$first": "$referrer"},
            "paths": {"$addToSet": "$page_url"},
        }},
    ]
    cursor = db.page_views.aggregate(pipeline)

    sources = ["organic", "social", "email", "direct", "other"]
    counts = {s: {"sessions": 0, "product_viewers": 0, "checkout_reached": 0} for s in sources}
    total = {"sessions": 0, "product_viewers": 0, "checkout_reached": 0}

    async for sess in cursor:
        source = _classify_source(sess.get("first_referrer"))
        if source not in counts:
            source = "other"
        counts[source]["sessions"] += 1
        total["sessions"] += 1

        paths = [_path_of(p) for p in (sess.get("paths") or [])]
        viewed_product = any(_PRODUCT_RE.search(p) for p in paths)
        reached_checkout = any(_CHECKOUT_RE.search(p) for p in paths)
        if viewed_product:
            counts[source]["product_viewers"] += 1
            total["product_viewers"] += 1
        if reached_checkout:
            counts[source]["checkout_reached"] += 1
            total["checkout_reached"] += 1

    # ─── Paid orders (unattributed) ──────────────────────────────────────
    paid_query = {
        "created_at": {"$gte": start, "$lte": end},
        "$or": [
            {"payment_status": "paid"},
            {"status": {"$in": ["completed", "paid", "shipped", "confirmed"]}},
        ],
    }
    paid_orders = await db.shop_orders.count_documents(paid_query)
    revenue_pipeline = [
        {"$match": paid_query},
        {"$group": {"_id": None, "rev": {"$sum": {"$ifNull": ["$total", 0]}}}},
    ]
    rev_rows = await db.shop_orders.aggregate(revenue_pipeline).to_list(1)
    revenue = float(rev_rows[0]["rev"]) if rev_rows else 0.0

    # ─── Conversion ratios — only emit when denominators are meaningful so
    #    the UI doesn't show a triumphant "100%" off 1 session. ──────────
    def ratio(num: int, denom: int, *, min_denom: int = 5) -> float | None:
        if denom < min_denom:
            return None
        return round(num / denom * 100, 2)

    rates = {
        "browse_to_product": ratio(total["product_viewers"], total["sessions"]),
        "product_to_checkout": ratio(total["checkout_reached"], total["product_viewers"]),
        "checkout_to_paid": ratio(paid_orders, total["checkout_reached"]),
        "session_to_paid": ratio(paid_orders, total["sessions"]),
    }

    return {
        "window_days": days,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "totals": {
            **total,
            "paid_orders": paid_orders,
            "revenue_total": round(revenue, 2),
        },
        "by_source": [
            {
                "source": s,
                **counts[s],
                "browse_to_checkout_pct": ratio(counts[s]["checkout_reached"], counts[s]["sessions"]),
            }
            for s in sources
            if counts[s]["sessions"] > 0
        ],
        "rates": rates,
    }

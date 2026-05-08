"""
Lifetime Savings Estimator
─────────────────────────

Quantifies how much money the autopilot stack has saved the business
versus the equivalent UK SEO/marketing agency cost. The numbers are
deliberately conservative — we use the *low* end of typical UK rates
so the headline £-figure is defensible if anyone (board, bank,
investors) asks "show me the working".

Counted assets (live in Mongo):
  • Editorial Autopilot articles (`blog_articles`, status=published)
      → £600/article (UK SEO copywriter rate, ~2k-word piece)
  • Auto-promoted stealth keywords (`seo_stealth_auto_promotes`)
      → £75/keyword (specialist SEO consultant minimum)
  • City landing pages (`city_landing_pages`, status in
    {generated, approved, published})
      → £200/page (local SEO consultancy rate for a single page)
  • Marketing Studio banners (`marketing_assets`, asset_type ~banner)
      → £150/banner (freelance designer, single hero/promo)
  • Sora 2 videos (`marketing_video_assets`, status=ready)
      → £400/video (basic videographer + edit, sub-15-second clip)
  • Stealth-keyword auto-fill (`tiles` with `hidden_seo_keywords`)
      → £15/product (SEO meta optimisation rate, batch)

Subtracts the *actual* AI spend tracked across the various
spend-budget collections so the final figure is **net savings**.

Returns a single resilient dict — individual section failures degrade
to zero, never 500 the whole report.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from config import get_db

logger = logging.getLogger(__name__)


# UK agency rate card — conservative low-end. Override via env if you
# want to model your local market more aggressively.
RATES_GBP = {
    "blog_article": 600,
    "stealth_keyword": 75,
    "city_page": 200,
    "marketing_banner": 150,
    "marketing_video": 400,
    "stealth_kw_filled_product": 15,
}


async def _safe(coro, label: str, default=0):
    try:
        return await coro
    except Exception:  # noqa: BLE001
        logger.exception("lifetime_savings — %s failed", label)
        return default


async def _count_blog_articles(db) -> int:
    return await db.blog_articles.count_documents({"status": "published"})


async def _count_stealth_promotions(db) -> int:
    return await db.seo_stealth_auto_promotes.count_documents({"undone_at": None})


async def _count_city_pages(db) -> int:
    return await db.city_landing_pages.count_documents(
        {"status": {"$in": ["generated", "approved", "published"]}},
    )


async def _count_banners(db) -> int:
    """Count marketing assets that are banners (heroes) — i.e. anything
    rendered through the Marketing Studio that displays on the
    storefront. Real schema uses `asset_kind` (e.g. 'hero') and
    `preset` (e.g. 'hero-wide-short') — there is no `asset_type`
    field. Excludes deleted assets. Each banner saves ~£150 vs hiring
    a freelance designer.
    """
    cols = await db.list_collection_names()
    if "marketing_assets" not in cols:
        return 0
    return await db.marketing_assets.count_documents({
        "deleted": {"$ne": True},
        "$or": [
            {"asset_kind": {"$regex": "hero|banner|promo", "$options": "i"}},
            {"preset": {"$regex": "hero|banner|promo", "$options": "i"}},
            {"asset_type": {"$regex": "hero|banner|promo", "$options": "i"}},  # legacy schema
        ],
    })


async def _count_videos(db) -> int:
    cols = await db.list_collection_names()
    if "marketing_video_assets" not in cols:
        return 0
    return await db.marketing_video_assets.count_documents({})


async def _count_stealth_filled_products(db) -> int:
    """Products with at least one hidden_seo_keyword — i.e. ones that
    have benefited from the auto-fill kill-shot."""
    return await db.tiles.count_documents({
        "is_active": {"$ne": False},
        "hidden_seo_keywords": {"$exists": True, "$ne": []},
    })


async def _ai_actual_spend(db) -> float:
    """Pull actual AI spend logged in the various budget caches.
    Defensive: any missing field/collection counts as 0.

    Sources of real AI spend:
      • Marketing Studio image-gen — sum of `cost_usd` across all
        non-deleted `marketing_assets` rows (Nano Banana renders cost
        ~$0.04/each, so 11 banners = $0.44)
      • Editorial Autopilot — `editorial_autopilot_settings.lifetime_spend_usd`
        OR fallback to summing `editorial_autopilot_runs.spend_usd`
      • Sora videos — sum of `cost_usd` on `marketing_video_assets`
      • Stealth-keyword auto-fill — `seo_stealth_metadata.lifetime_spend_usd`
        if present (typically pennies per product)
    """
    spend_usd = 0.0
    cols = await db.list_collection_names()

    # 1. Marketing Studio — sum cost_usd field across all assets
    try:
        if "marketing_assets" in cols:
            cur = db.marketing_assets.aggregate([
                {"$match": {
                    "deleted": {"$ne": True},
                    "cost_usd": {"$exists": True},
                }},
                {"$group": {"_id": None, "total": {"$sum": "$cost_usd"}}},
            ])
            row = await cur.to_list(1)
            if row:
                spend_usd += float(row[0].get("total") or 0)
    except Exception:  # noqa: BLE001
        pass

    # 2. Editorial Autopilot — try the settings doc first, then sum runs
    try:
        if "editorial_autopilot_settings" in cols:
            ed = await db.editorial_autopilot_settings.find_one(
                {"id": "main"},
                {"_id": 0, "month_spend_usd": 1, "lifetime_spend_usd": 1},
            )
            if ed and (ed.get("lifetime_spend_usd") or ed.get("month_spend_usd")):
                spend_usd += float(
                    ed.get("lifetime_spend_usd") or ed.get("month_spend_usd") or 0,
                )
            elif "editorial_autopilot_runs" in cols:
                # Fallback: sum spend_usd across all run rows
                cur = db.editorial_autopilot_runs.aggregate([
                    {"$match": {"spend_usd": {"$exists": True}}},
                    {"$group": {"_id": None, "total": {"$sum": "$spend_usd"}}},
                ])
                row = await cur.to_list(1)
                if row:
                    spend_usd += float(row[0].get("total") or 0)
    except Exception:  # noqa: BLE001
        pass

    # 3. Sora video spend
    try:
        if "marketing_video_assets" in cols:
            cur = db.marketing_video_assets.aggregate([
                {"$match": {"cost_usd": {"$exists": True}}},
                {"$group": {"_id": None, "total": {"$sum": "$cost_usd"}}},
            ])
            row = await cur.to_list(1)
            if row:
                spend_usd += float(row[0].get("total") or 0)
    except Exception:  # noqa: BLE001
        pass

    # USD → GBP conversion (current ~0.79 fx; tweaked here so the
    # whole report is internally consistent)
    return round(spend_usd * 0.79, 2)


def _compute_breakdown(counts: dict[str, int]) -> list[dict[str, Any]]:
    """Builds the line-item list used by the frontend table."""
    return [
        {
            "key": "blog_articles",
            "label": "AI-written blog articles",
            "explainer": "UK SEO copywriter ~£600 per ~2k-word article",
            "count": counts.get("blog_articles", 0),
            "rate_gbp": RATES_GBP["blog_article"],
            "value_gbp": counts.get("blog_articles", 0) * RATES_GBP["blog_article"],
        },
        {
            "key": "city_pages",
            "label": "Local city/town landing pages",
            "explainer": "Local SEO agency ~£200 per landing page",
            "count": counts.get("city_pages", 0),
            "rate_gbp": RATES_GBP["city_page"],
            "value_gbp": counts.get("city_pages", 0) * RATES_GBP["city_page"],
        },
        {
            "key": "stealth_kw_filled_products",
            "label": "Products with stealth keyword optimisation",
            "explainer": "SEO meta optimisation ~£15 per product",
            "count": counts.get("stealth_kw_filled_products", 0),
            "rate_gbp": RATES_GBP["stealth_kw_filled_product"],
            "value_gbp": counts.get("stealth_kw_filled_products", 0)
                         * RATES_GBP["stealth_kw_filled_product"],
        },
        {
            "key": "stealth_promotions",
            "label": "Auto-promoted stealth keywords",
            "explainer": "Specialist SEO consultant ~£75 per keyword research",
            "count": counts.get("stealth_promotions", 0),
            "rate_gbp": RATES_GBP["stealth_keyword"],
            "value_gbp": counts.get("stealth_promotions", 0) * RATES_GBP["stealth_keyword"],
        },
        {
            "key": "banners",
            "label": "AI marketing banners",
            "explainer": "Freelance designer ~£150 per banner",
            "count": counts.get("banners", 0),
            "rate_gbp": RATES_GBP["marketing_banner"],
            "value_gbp": counts.get("banners", 0) * RATES_GBP["marketing_banner"],
        },
        {
            "key": "videos",
            "label": "AI short-form videos (Sora)",
            "explainer": "Videographer ~£400 per <15s social clip",
            "count": counts.get("videos", 0),
            "rate_gbp": RATES_GBP["marketing_video"],
            "value_gbp": counts.get("videos", 0) * RATES_GBP["marketing_video"],
        },
    ]


async def get_savings_report() -> dict[str, Any]:
    """Top-level entrypoint — assembles the full savings report."""
    db = get_db()

    counts = {
        "blog_articles": await _safe(_count_blog_articles(db), "blog_articles"),
        "stealth_promotions": await _safe(_count_stealth_promotions(db), "stealth_promotions"),
        "city_pages": await _safe(_count_city_pages(db), "city_pages"),
        "banners": await _safe(_count_banners(db), "banners"),
        "videos": await _safe(_count_videos(db), "videos"),
        "stealth_kw_filled_products": await _safe(
            _count_stealth_filled_products(db), "stealth_kw_filled_products",
        ),
    }

    breakdown = _compute_breakdown(counts)
    total_agency_value = sum(b["value_gbp"] for b in breakdown)
    actual_ai_spend_gbp = await _safe(_ai_actual_spend(db), "ai_spend", default=0.0)
    net_savings = round(total_agency_value - actual_ai_spend_gbp, 2)

    # Estimate per-day savings since launch — pick the EARLIEST
    # creation timestamp across multiple anchor sources so we never
    # show a wildly-wrong "30 days running" when the system has been
    # live longer. Falls back to 30 days only when no anchors exist.
    days_running = 30
    earliest: datetime | None = None
    try:
        anchors_to_try = [
            (db.blog_articles, ["published_at", "created_at"]),
            (db.city_landing_pages, ["created_at", "published_at"]),
            (db.marketing_assets, ["created_at"]),
            (db.tiles, ["created_at"]),
        ]
        for col, fields in anchors_to_try:
            for field in fields:
                try:
                    doc = await col.find_one(
                        {field: {"$exists": True, "$ne": None}},
                        {"_id": 0, field: 1},
                        sort=[(field, 1)],
                    )
                except Exception:  # noqa: BLE001
                    continue
                if not doc:
                    continue
                ts = doc.get(field)
                if isinstance(ts, str):
                    try:
                        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    except Exception:  # noqa: BLE001
                        continue
                if not isinstance(ts, datetime):
                    continue
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if earliest is None or ts < earliest:
                    earliest = ts
        if earliest:
            delta = (datetime.now(timezone.utc) - earliest).days
            if delta > 0:
                days_running = delta
    except Exception:  # noqa: BLE001
        pass

    per_day_savings = round(net_savings / max(days_running, 1), 2)
    monthly_run_rate = round(per_day_savings * 30, 2)

    return {
        "currency": "GBP",
        "totals": {
            "agency_equivalent_gbp": round(total_agency_value, 2),
            "actual_ai_spend_gbp": actual_ai_spend_gbp,
            "net_savings_gbp": net_savings,
            "per_day_savings_gbp": per_day_savings,
            "monthly_run_rate_gbp": monthly_run_rate,
            "days_running": days_running,
        },
        "breakdown": breakdown,
        "rates_card": RATES_GBP,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

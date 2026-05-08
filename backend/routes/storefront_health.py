"""
Storefront Health Check - CRITICAL REGRESSION PREVENTION

This endpoint validates that all essential storefront elements and data
are present and functioning correctly. Run before every deployment.
"""
from fastapi import APIRouter
from datetime import datetime, timezone
import os

router = APIRouter(prefix="/storefront-health", tags=["health"])

from pymongo import MongoClient

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME", "tile_station")


def get_db():
    client = MongoClient(MONGO_URL)
    return client[DB_NAME]


@router.get("/check")
async def storefront_health_check():
    """
    Comprehensive storefront health check.
    Returns status of all critical storefront features.
    """
    db = get_db()
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall_status": "healthy",
        "checks": {}
    }
    failures = []

    # 1. Check tiles collection has data
    try:
        tiles_count = db.tiles.count_documents({})
        results["checks"]["tiles_collection"] = {
            "status": "pass" if tiles_count > 0 else "fail",
            "count": tiles_count,
            "description": "Storefront product catalog has data"
        }
        if tiles_count == 0:
            failures.append("tiles_collection: No products in storefront")
    except Exception as e:
        results["checks"]["tiles_collection"] = {"status": "error", "error": str(e)}
        failures.append(f"tiles_collection: {e}")

    # 2. Check collection_settings exists
    try:
        cs_count = db.collection_settings.count_documents({})
        results["checks"]["collection_settings"] = {
            "status": "pass" if cs_count > 0 else "warn",
            "count": cs_count,
            "description": "Collection display settings present"
        }
    except Exception as e:
        results["checks"]["collection_settings"] = {"status": "error", "error": str(e)}
        failures.append(f"collection_settings: {e}")

    # 3. Check tier pricing configuration exists
    try:
        tier_config = db.tier_pricing_config.find_one({})
        has_tiers = tier_config is not None and tier_config.get("tiers")
        results["checks"]["tier_pricing_config"] = {
            "status": "pass" if has_tiers else "warn",
            "has_config": has_tiers,
            "description": "Tier pricing configuration exists for volume discounts"
        }
    except Exception as e:
        results["checks"]["tier_pricing_config"] = {"status": "error", "error": str(e)}

    # 4. Check trade accounts system
    try:
        trade_count = db.trade_accounts.count_documents({})
        results["checks"]["trade_accounts"] = {
            "status": "pass",
            "count": trade_count,
            "description": "Trade account system operational"
        }
    except Exception as e:
        results["checks"]["trade_accounts"] = {"status": "error", "error": str(e)}

    # 5. Check for products with tier_pricing_disabled - audit
    try:
        disabled_count = db.tiles.count_documents({"tier_pricing_disabled": True})
        total_tiles = db.tiles.count_documents({})
        results["checks"]["tier_pricing_disabled_audit"] = {
            "status": "pass",
            "disabled_count": disabled_count,
            "total_products": total_tiles,
            "description": f"{disabled_count}/{total_tiles} products have tier pricing disabled"
        }
    except Exception as e:
        results["checks"]["tier_pricing_disabled_audit"] = {"status": "error", "error": str(e)}

    # 6. Check page settings (homepage config)
    try:
        page_settings = db.page_settings.find_one({})
        results["checks"]["page_settings"] = {
            "status": "pass" if page_settings else "warn",
            "exists": page_settings is not None,
            "description": "Homepage and page configuration present"
        }
    except Exception as e:
        results["checks"]["page_settings"] = {"status": "error", "error": str(e)}

    # 7. Check supplier_products sync status
    try:
        sp_count = db.supplier_products.count_documents({})
        published = db.tiles.count_documents({"show_on_website": True})
        results["checks"]["sync_status"] = {
            "status": "pass",
            "supplier_products": sp_count,
            "published_tiles": published,
            "description": f"{published} products published out of {sp_count} total"
        }
    except Exception as e:
        results["checks"]["sync_status"] = {"status": "error", "error": str(e)}

    # 8. Critical UI Elements Checklist (static - documents what frontend must show)
    results["checks"]["critical_ui_elements"] = {
        "status": "info",
        "description": "Frontend elements that MUST be visible on every product page",
        "elements": [
            {
                "name": "Trade Login Box",
                "test_id": "trade-customer-box",
                "pages": ["CollectionDetailPage", "TileDetailPage"],
                "visibility_rule": "Show when user is NOT logged in, regardless of tier pricing status",
                "component_file": "components/shop/TradeLoginPrompt.jsx"
            },
            {
                "name": "Trade Login Banner",
                "test_id": "trade-login-banner",
                "pages": ["TileDetailPage"],
                "visibility_rule": "Show when user is NOT a trade customer, regardless of tier pricing status",
                "component_file": "components/shop/TradeLoginPrompt.jsx"
            },
            {
                "name": "Volume Pricing Table",
                "test_id": "volume-pricing-table",
                "pages": ["CollectionDetailPage"],
                "visibility_rule": "Show when tierPricing array has data",
                "component_file": "components/shop/VolumePricingTable.jsx"
            },
            {
                "name": "Header Trade Tab",
                "test_id": "trade-tab",
                "pages": ["All pages (ShopLayout)"],
                "visibility_rule": "Always visible in header"
            },
            {
                "name": "Add to Cart Button",
                "test_id": "add-to-cart-btn",
                "pages": ["CollectionDetailPage", "TileDetailPage"],
                "visibility_rule": "Always visible on product pages"
            }
        ]
    }

    if failures:
        results["overall_status"] = "degraded"
        results["failures"] = failures

    return results

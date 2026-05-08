"""
Idempotent index creation for the tiles collection. Runs at app startup
and only creates indexes that don't already exist. Massively speeds up
the slow filter-based queries on /api/tiles/collections.

Why these fields?
  - is_active                — every storefront query filters on this
  - product_group            — every page filters by tab (tiles/materials/etc.)
  - category_ids             — primary category filter
  - sub_categories           — slug-based category filter (most-used path)
  - supplier_name            — supplier filter on /tiles
  - series + original_series — used in /collection/{name}
  - labels                   — sale filter (?sale=true)
  - is_active+product_group  — compound for the most common query

Run automatically on startup. Safe to run repeatedly.
"""
import logging
import os
from pymongo import ASCENDING, DESCENDING, MongoClient

logger = logging.getLogger(__name__)


def ensure_storefront_indexes() -> dict:
    """Idempotent. Returns {created: [...], existing: [...]}.

    Uses pymongo (sync) since this runs once at startup, not per-request.
    """
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        return {"error": "MONGO_URL or DB_NAME not set"}

    client = MongoClient(mongo_url)
    db = client[db_name]

    targets = [
        # Single-field indexes (fast equality / range)
        ([("is_active", ASCENDING)], "tiles_is_active"),
        ([("product_group", ASCENDING)], "tiles_product_group"),
        ([("category_ids", ASCENDING)], "tiles_category_ids"),
        ([("sub_categories", ASCENDING)], "tiles_sub_categories"),
        ([("supplier_name", ASCENDING)], "tiles_supplier_name"),
        ([("labels", ASCENDING)], "tiles_labels"),
        ([("series", ASCENDING)], "tiles_series"),
        ([("original_series", ASCENDING)], "tiles_original_series"),
        ([("display_name", ASCENDING)], "tiles_display_name"),
        # Compound — covers the most common storefront query path:
        # WHERE is_active=true AND product_group='tiles'
        ([("is_active", ASCENDING), ("product_group", ASCENDING)], "tiles_active_group"),
        # Compound for series-detail queries
        ([("is_active", ASCENDING), ("series", ASCENDING)], "tiles_active_series"),
    ]

    existing_index_names = {idx["name"] for idx in db.tiles.list_indexes()}

    created = []
    skipped = []
    for keys, name in targets:
        if name in existing_index_names:
            skipped.append(name)
            continue
        try:
            db.tiles.create_index(keys, name=name, background=True)
            created.append(name)
            logger.info(f"Created MongoDB index: {name}")
        except Exception as exc:
            logger.warning(f"Could not create index {name}: {exc}")

    client.close()
    # Also ensure client_errors TTL + lookup indexes
    try:
        ensure_client_errors_indexes()
    except Exception as exc:
        logger.warning(f"Could not ensure client_errors indexes: {exc}")
    # And page_views indexes used by Visitor History
    try:
        ensure_page_views_indexes()
    except Exception as exc:
        logger.warning(f"Could not ensure page_views indexes: {exc}")
    return {"created": created, "skipped": skipped}


def ensure_page_views_indexes() -> None:
    """Composite (session_id, timestamp) for the Visitor History journey
    reconstruction, plus a 90-day TTL on raw page-view rows so the
    collection doesn't grow unboundedly."""
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        return
    client = MongoClient(mongo_url)
    db = client[db_name]
    existing = {idx["name"] for idx in db.page_views.list_indexes()}
    if "page_views_session_ts" not in existing:
        db.page_views.create_index(
            [("session_id", ASCENDING), ("timestamp", ASCENDING)],
            name="page_views_session_ts",
            background=True,
        )
        logger.info("Created MongoDB index: page_views_session_ts")
    if "page_views_ts_desc" not in existing:
        db.page_views.create_index(
            [("timestamp", DESCENDING)],
            name="page_views_ts_desc",
            background=True,
        )
        logger.info("Created MongoDB index: page_views_ts_desc")
    if "page_views_ttl_90d" not in existing:
        db.page_views.create_index(
            [("timestamp", ASCENDING)],
            name="page_views_ttl_90d",
            expireAfterSeconds=60 * 60 * 24 * 90,
            background=True,
        )
        logger.info("Created MongoDB index: page_views_ttl_90d")
    client.close()


def ensure_client_errors_indexes() -> None:
    """TTL on `created_at` (30 days) + per-session lookup index."""
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        return
    client = MongoClient(mongo_url)
    db = client[db_name]
    existing = {idx["name"] for idx in db.client_errors.list_indexes()}
    if "client_errors_ttl_30d" not in existing:
        db.client_errors.create_index(
            [("created_at", ASCENDING)],
            name="client_errors_ttl_30d",
            expireAfterSeconds=60 * 60 * 24 * 30,
            background=True,
        )
        logger.info("Created MongoDB index: client_errors_ttl_30d")
    if "client_errors_session" not in existing:
        db.client_errors.create_index(
            [("session_id", ASCENDING), ("created_at", ASCENDING)],
            name="client_errors_session",
            background=True,
        )
        logger.info("Created MongoDB index: client_errors_session")
    client.close()


if __name__ == "__main__":
    # Allows manual run: python3 -m utils.ensure_indexes
    logging.basicConfig(level=logging.INFO)
    print(ensure_storefront_indexes())

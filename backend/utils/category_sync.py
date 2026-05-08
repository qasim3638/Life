"""
Category Sync Utility
Provides unified category management across:
- Supplier Products (product categories)
- Website Categories (website display)
- Shop Navigation (frontend tabs)

This ensures all category changes are synchronized automatically.

USAGE:
- For sync endpoints (using PyMongo directly): Use sync_* functions
- For async endpoints (using Motor): Use async functions
"""
from datetime import datetime, timezone
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# SYNCHRONOUS FUNCTIONS (for PyMongo / sync endpoints)
# =============================================================================

def sync_category_to_website_sync(db, category_name: str, auto_create: bool = True) -> Optional[dict]:
    """
    SYNC VERSION: Ensure a category exists in website_categories.
    If it doesn't exist and auto_create is True, create it.
    
    Args:
        db: PyMongo database instance (from MongoClient)
        category_name: Name of the category to sync
        auto_create: Whether to create the category if it doesn't exist
    
    Returns:
        The category document or None
    """
    if not category_name or not category_name.strip():
        return None
    
    category_name = category_name.strip()
    
    # Skip comma-separated values - these are data errors, not valid categories
    if ',' in category_name:
        logger.warning(f"Skipping invalid comma-separated category: {category_name}")
        return None
    
    slug = category_name.lower().replace(' ', '-').replace('&', 'and')
    slug = ''.join(c if c.isalnum() or c == '-' else '' for c in slug)
    
    # Check if category exists
    existing = db.website_categories.find_one({
        "$or": [
            {"slug": slug},
            {"name": {"$regex": f"^{category_name}$", "$options": "i"}}
        ]
    })
    
    if existing:
        existing["id"] = str(existing.pop("_id"))
        return existing
    
    if not auto_create:
        return None
    
    # Create new category
    new_category = {
        "name": category_name,
        "slug": slug,
        "description": f"{category_name} tile collection",
        "parent_id": None,
        "image_url": "",
        "display_order": 999,  # Will be sorted later
        "is_active": True,
        "show_on_homepage": False,
        "seo_title": category_name,
        "seo_description": f"Browse our {category_name} collection",
        "product_count": 0,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    result = db.website_categories.insert_one(new_category)
    new_category["id"] = str(result.inserted_id)
    if "_id" in new_category:
        del new_category["_id"]
    
    logger.info(f"Auto-created website category: {category_name}")
    return new_category


def sync_product_categories_batch_sync(db, categories: List[str]) -> dict:
    """
    SYNC VERSION: Sync multiple categories at once (more efficient for bulk operations).
    Returns stats about what was created/updated.
    """
    created = 0
    existing_count = 0
    
    for category_name in categories:
        if not category_name or not category_name.strip():
            continue
        
        # Check if exists first
        cat_name = category_name.strip()
        slug = cat_name.lower().replace(' ', '-').replace('&', 'and')
        slug = ''.join(c if c.isalnum() or c == '-' else '' for c in slug)
        
        existing = db.website_categories.find_one({
            "$or": [
                {"slug": slug},
                {"name": {"$regex": f"^{cat_name}$", "$options": "i"}}
            ]
        })
        
        if existing:
            existing_count += 1
        else:
            result = sync_category_to_website_sync(db, cat_name, auto_create=True)
            if result:
                created += 1
    
    return {"created": created, "existing": existing_count}


def update_category_product_counts_sync(db) -> dict:
    """
    SYNC VERSION: Update product counts for all website categories.
    This should be called periodically or after bulk product updates.
    """
    # Get all categories
    categories = list(db.website_categories.find({}))
    updated = 0
    
    for cat in categories:
        cat_name = cat["name"]
        cat_slug = cat.get("slug", "")
        
        # Build flexible query to match various naming patterns
        # Match: exact name, name without "Tiles" suffix, slug-based match
        name_without_tiles = cat_name.replace(" Tiles", "").strip()
        
        query_conditions = [
            {"category": cat_name},
            {"category": {"$regex": f"^{cat_name}$", "$options": "i"}},
            {"category": name_without_tiles},
            {"category": {"$regex": f"^{name_without_tiles}$", "$options": "i"}},
        ]
        
        # Also match by slug format (e.g., "floor-tiles")
        if cat_slug:
            query_conditions.append({"category": {"$regex": cat_slug.replace("-", "[ -]?"), "$options": "i"}})
        
        # Count products in supplier_products (all products, not just show_on_website)
        count = db.supplier_products.count_documents({
            "$or": query_conditions
        })
        
        # Also count in tiles collection
        tiles_count = db.tiles.count_documents({
            "$or": query_conditions
        })
        
        total_count = max(count, tiles_count)
        
        # Update the category
        db.website_categories.update_one(
            {"_id": cat["_id"]},
            {"$set": {"product_count": total_count, "updated_at": datetime.now(timezone.utc)}}
        )
        updated += 1
    
    return {"categories_updated": updated}


def get_all_website_categories_for_dropdown_sync(db) -> List[dict]:
    """
    SYNC VERSION: Get categories formatted for dropdown/select use in admin panel.
    """
    categories = list(db.website_categories.find(
        {"is_active": True},
        {"_id": 0, "name": 1, "slug": 1, "product_count": 1}
    ).sort("name", 1))
    
    return categories


def sync_category_on_product_save_sync(db, product_data: dict) -> dict:
    """
    SYNC VERSION: Called when a product is saved. Syncs the category to website_categories.
    Returns stats about what was synced.
    """
    synced = 0
    
    category = product_data.get("category")
    if category:
        result = sync_category_to_website_sync(db, category, auto_create=True)
        if result:
            synced += 1
    
    # Also sync material as a category if present
    material = product_data.get("material")
    if material:
        result = sync_category_to_website_sync(db, material, auto_create=True)
        if result:
            synced += 1
    
    return {"synced": synced}


def sync_bulk_update_categories_sync(db, updates: dict) -> dict:
    """
    SYNC VERSION: Sync categories from a bulk update operation.
    
    Args:
        db: PyMongo database instance
        updates: Dict with category, material, finish fields to sync
    
    Returns:
        Dict with sync stats
    """
    categories_to_sync = set()
    
    if updates.get("category"):
        categories_to_sync.add(updates["category"])
    if updates.get("material"):
        categories_to_sync.add(updates["material"])
    if updates.get("finish"):
        categories_to_sync.add(updates["finish"])
    
    synced = 0
    for cat_name in categories_to_sync:
        if cat_name and cat_name.strip():
            result = sync_category_to_website_sync(db, cat_name, auto_create=True)
            if result:
                synced += 1
    
    return {"categories_synced": synced}


# =============================================================================
# ASYNC FUNCTIONS (for Motor / async endpoints)
# =============================================================================

async def sync_category_to_website(db, category_name: str, auto_create: bool = True) -> Optional[dict]:
    """
    ASYNC VERSION: Ensure a category exists in website_categories.
    If it doesn't exist and auto_create is True, create it.
    
    Returns the category document or None.
    """
    if not category_name or not category_name.strip():
        return None
    
    category_name = category_name.strip()
    slug = category_name.lower().replace(' ', '-').replace('&', 'and')
    slug = ''.join(c if c.isalnum() or c == '-' else '' for c in slug)
    
    # Check if category exists
    existing = await db.website_categories.find_one({
        "$or": [
            {"slug": slug},
            {"name": {"$regex": f"^{category_name}$", "$options": "i"}}
        ]
    })
    
    if existing:
        existing["id"] = str(existing.pop("_id"))
        return existing
    
    if not auto_create:
        return None
    
    # Create new category
    new_category = {
        "name": category_name,
        "slug": slug,
        "description": f"{category_name} tile collection",
        "parent_id": None,
        "image_url": "",
        "display_order": 999,
        "is_active": True,
        "show_on_homepage": False,
        "seo_title": category_name,
        "seo_description": f"Browse our {category_name} collection",
        "product_count": 0,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    result = await db.website_categories.insert_one(new_category)
    new_category["id"] = str(result.inserted_id)
    if "_id" in new_category:
        del new_category["_id"]
    
    logger.info(f"Auto-created website category: {category_name}")
    return new_category


async def sync_product_categories_batch(db, categories: List[str]) -> dict:
    """
    ASYNC VERSION: Sync multiple categories at once (more efficient for bulk operations).
    Returns stats about what was created/updated.
    """
    created = 0
    existing_count = 0
    
    for category_name in categories:
        if not category_name or not category_name.strip():
            continue
        
        cat_name = category_name.strip()
        slug = cat_name.lower().replace(' ', '-').replace('&', 'and')
        slug = ''.join(c if c.isalnum() or c == '-' else '' for c in slug)
        
        existing = await db.website_categories.find_one({
            "$or": [
                {"slug": slug},
                {"name": {"$regex": f"^{cat_name}$", "$options": "i"}}
            ]
        })
        
        if existing:
            existing_count += 1
        else:
            result = await sync_category_to_website(db, cat_name, auto_create=True)
            if result:
                created += 1
    
    return {"created": created, "existing": existing_count}


async def update_category_product_counts(db) -> dict:
    """
    ASYNC VERSION: Update product counts for all website categories.
    """
    categories = await db.website_categories.find({}).to_list(1000)
    updated = 0
    
    for cat in categories:
        count = await db.supplier_products.count_documents({
            "$or": [
                {"category": cat["name"]},
                {"category": {"$regex": f"^{cat['name']}$", "$options": "i"}}
            ],
            "show_on_website": True
        })
        
        tiles_count = await db.tiles.count_documents({
            "$or": [
                {"category": cat["name"]},
                {"category": {"$regex": f"^{cat['name']}$", "$options": "i"}}
            ]
        })
        
        total_count = max(count, tiles_count)
        
        await db.website_categories.update_one(
            {"_id": cat["_id"]},
            {"$set": {"product_count": total_count, "updated_at": datetime.now(timezone.utc)}}
        )
        updated += 1
    
    return {"categories_updated": updated}


async def get_all_website_categories_for_dropdown(db) -> List[dict]:
    """
    ASYNC VERSION: Get categories formatted for dropdown/select use in admin panel.
    """
    categories = await db.website_categories.find(
        {"is_active": True},
        {"_id": 0, "name": 1, "slug": 1, "product_count": 1}
    ).sort("name", 1).to_list(1000)
    
    return categories


async def sync_category_on_product_save(db, product_data: dict):
    """
    ASYNC VERSION: Called when a product is saved. Syncs the category to website_categories.
    """
    category = product_data.get("category")
    if category:
        await sync_category_to_website(db, category, auto_create=True)
    
    material = product_data.get("material")
    if material:
        await sync_category_to_website(db, material, auto_create=True)


async def get_category_hierarchy(db) -> List[dict]:
    """
    Get categories with their hierarchy for navigation building.
    """
    categories = await db.website_categories.find(
        {"is_active": True}
    ).sort("display_order", 1).to_list(1000)
    
    # Build hierarchy
    root_categories = []
    children_map = {}
    
    for cat in categories:
        cat["id"] = str(cat.pop("_id"))
        parent_id = cat.get("parent_id")
        
        if not parent_id:
            root_categories.append(cat)
        else:
            if parent_id not in children_map:
                children_map[parent_id] = []
            children_map[parent_id].append(cat)
    
    # Attach children to parents
    for cat in root_categories:
        cat["children"] = children_map.get(cat["id"], [])
    
    return root_categories

"""
Attribute Sync Utility
Keeps filter_types and specification_types collections in sync for shared attributes
(color, material, finish, size, etc.)
"""

import logging
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# Mapping between filter slugs and specification slugs/field_names
# Key: attribute slug used in both filter_types and specification_types
# These are the shared attributes that need to be kept in sync
SHARED_ATTRIBUTES = {
    "color": {"filter_slug": "color", "spec_slug": "color", "spec_field": "color"},
    "material": {"filter_slug": "material", "spec_slug": "material", "spec_field": "material"},
    "finish": {"filter_slug": "finish", "spec_slug": "finish", "spec_field": "finish"},
    "size": {"filter_slug": "size", "spec_slug": "size", "spec_field": "size"},
}


async def sync_attribute_values(db: AsyncIOMotorDatabase, attribute_slug: str) -> dict:
    """
    Synchronize values for a shared attribute between filter_types and specification_types.
    
    This function:
    1. Gets all values from filter_types for the attribute
    2. Gets all values from specification_types for the attribute
    3. Merges them (union of both sets)
    4. Updates both collections with the merged values
    
    Args:
        db: AsyncIO MongoDB database instance
        attribute_slug: The slug of the attribute to sync (e.g., 'color', 'material')
        
    Returns:
        dict with sync results
    """
    if attribute_slug not in SHARED_ATTRIBUTES:
        return {
            "success": False,
            "message": f"Attribute '{attribute_slug}' is not a shared attribute",
            "shared_attributes": list(SHARED_ATTRIBUTES.keys())
        }
    
    mapping = SHARED_ATTRIBUTES[attribute_slug]
    filter_slug = mapping["filter_slug"]
    spec_slug = mapping["spec_slug"]
    
    # Get filter type
    filter_type = await db.filter_types.find_one({"slug": filter_slug})
    if not filter_type:
        logger.warning(f"Filter type '{filter_slug}' not found for sync")
        filter_values = []
    else:
        filter_values = filter_type.get("values", [])
    
    # Get specification type
    spec_type = await db.specification_types.find_one({"slug": spec_slug})
    if not spec_type:
        logger.warning(f"Specification type '{spec_slug}' not found for sync")
        spec_values = []
    else:
        spec_values = spec_type.get("values", [])
    
    # Build value maps (keyed by lowercase value for comparison)
    filter_value_map = {}
    for v in filter_values:
        key = v.get("value", "").lower()
        if key:
            filter_value_map[key] = v
    
    spec_value_map = {}
    for v in spec_values:
        key = v.get("value", "").lower()
        if key:
            spec_value_map[key] = v
    
    # Merge: find values only in filters and only in specs
    only_in_filters = set(filter_value_map.keys()) - set(spec_value_map.keys())
    only_in_specs = set(spec_value_map.keys()) - set(filter_value_map.keys())
    
    filter_additions = 0
    spec_additions = 0
    
    # Add missing values to specification_types
    if spec_type and only_in_filters:
        new_spec_values = list(spec_values)
        for key in only_in_filters:
            fv = filter_value_map[key]
            new_spec_values.append({
                "value": fv.get("value", key),
                "label": fv.get("label", fv.get("value", key)),
                "description": fv.get("description", ""),
                "is_active": fv.get("is_active", True)
            })
            spec_additions += 1
        
        await db.specification_types.update_one(
            {"slug": spec_slug},
            {"$set": {"values": new_spec_values, "updated_at": datetime.now(timezone.utc)}}
        )
        logger.info(f"Added {spec_additions} values to specification_types/{spec_slug} from filter_types")
    
    # Add missing values to filter_types
    if filter_type and only_in_specs:
        new_filter_values = list(filter_values)
        for key in only_in_specs:
            sv = spec_value_map[key]
            new_filter_values.append({
                "value": sv.get("value", key),
                "label": sv.get("label", sv.get("value", key)),
                "is_active": sv.get("is_active", True)
            })
            filter_additions += 1
        
        await db.filter_types.update_one(
            {"slug": filter_slug},
            {"$set": {"values": new_filter_values, "updated_at": datetime.now(timezone.utc)}}
        )
        logger.info(f"Added {filter_additions} values to filter_types/{filter_slug} from specification_types")
    
    return {
        "success": True,
        "attribute": attribute_slug,
        "filter_slug": filter_slug,
        "spec_slug": spec_slug,
        "values_added_to_specs": spec_additions,
        "values_added_to_filters": filter_additions,
        "total_filter_values": len(filter_value_map) + filter_additions,
        "total_spec_values": len(spec_value_map) + spec_additions
    }


async def sync_all_shared_attributes(db: AsyncIOMotorDatabase) -> dict:
    """
    Synchronize all shared attributes between filter_types and specification_types.
    
    Returns:
        dict with results for each attribute
    """
    results = []
    total_filter_additions = 0
    total_spec_additions = 0
    
    for attribute_slug in SHARED_ATTRIBUTES.keys():
        result = await sync_attribute_values(db, attribute_slug)
        results.append(result)
        if result.get("success"):
            total_filter_additions += result.get("values_added_to_filters", 0)
            total_spec_additions += result.get("values_added_to_specs", 0)
    
    return {
        "success": True,
        "message": f"Synced {len(SHARED_ATTRIBUTES)} shared attributes",
        "total_values_added_to_filters": total_filter_additions,
        "total_values_added_to_specs": total_spec_additions,
        "results": results
    }


async def sync_on_filter_value_add(db: AsyncIOMotorDatabase, filter_slug: str, value: str, label: str) -> dict:
    """
    Called when a value is added to a filter. If the filter is a shared attribute,
    automatically adds the value to the corresponding specification type.
    
    Args:
        db: Database instance
        filter_slug: Slug of the filter (e.g., 'color')
        value: The value being added (e.g., 'turquoise')
        label: The display label (e.g., 'Turquoise')
    
    Returns:
        dict with sync result
    """
    # Check if this filter is a shared attribute
    mapping = None
    for attr_slug, m in SHARED_ATTRIBUTES.items():
        if m["filter_slug"] == filter_slug:
            mapping = m
            break
    
    if not mapping:
        return {"synced": False, "reason": "Not a shared attribute"}
    
    spec_slug = mapping["spec_slug"]
    
    # Check if spec type exists
    spec_type = await db.specification_types.find_one({"slug": spec_slug})
    if not spec_type:
        return {"synced": False, "reason": f"Specification type '{spec_slug}' not found"}
    
    # Check if value already exists in specs
    existing_values = spec_type.get("values", [])
    value_lower = value.lower()
    for v in existing_values:
        if v.get("value", "").lower() == value_lower:
            return {"synced": False, "reason": "Value already exists in specifications"}
    
    # Add to specifications
    existing_values.append({
        "value": value,
        "label": label,
        "description": "",
        "is_active": True
    })
    
    await db.specification_types.update_one(
        {"slug": spec_slug},
        {"$set": {"values": existing_values, "updated_at": datetime.now(timezone.utc)}}
    )
    
    logger.info(f"Synced new filter value '{value}' to specification_types/{spec_slug}")
    return {"synced": True, "spec_slug": spec_slug, "value": value}


async def sync_on_spec_value_add(db: AsyncIOMotorDatabase, spec_slug: str, value: str, label: str) -> dict:
    """
    Called when a value is added to a specification. If the spec is a shared attribute,
    automatically adds the value to the corresponding filter type.
    
    Args:
        db: Database instance
        spec_slug: Slug of the specification (e.g., 'color')
        value: The value being added (e.g., 'turquoise')
        label: The display label (e.g., 'Turquoise')
    
    Returns:
        dict with sync result
    """
    # Check if this spec is a shared attribute
    mapping = None
    for attr_slug, m in SHARED_ATTRIBUTES.items():
        if m["spec_slug"] == spec_slug:
            mapping = m
            break
    
    if not mapping:
        return {"synced": False, "reason": "Not a shared attribute"}
    
    filter_slug = mapping["filter_slug"]
    
    # Check if filter type exists
    filter_type = await db.filter_types.find_one({"slug": filter_slug})
    if not filter_type:
        return {"synced": False, "reason": f"Filter type '{filter_slug}' not found"}
    
    # Check if value already exists in filters
    existing_values = filter_type.get("values", [])
    value_lower = value.lower()
    for v in existing_values:
        if v.get("value", "").lower() == value_lower:
            return {"synced": False, "reason": "Value already exists in filters"}
    
    # Add to filters
    existing_values.append({
        "value": value,
        "label": label,
        "is_active": True
    })
    
    await db.filter_types.update_one(
        {"slug": filter_slug},
        {"$set": {"values": existing_values, "updated_at": datetime.now(timezone.utc)}}
    )
    
    logger.info(f"Synced new spec value '{value}' to filter_types/{filter_slug}")
    return {"synced": True, "filter_slug": filter_slug, "value": value}


async def sync_on_filter_value_delete(db: AsyncIOMotorDatabase, filter_slug: str, value_slug: str) -> dict:
    """
    Called when a value is deleted from a filter. If the filter is a shared attribute,
    automatically removes the value from the corresponding specification type.
    
    Args:
        db: Database instance
        filter_slug: Slug of the filter (e.g., 'color')
        value_slug: The value being deleted (e.g., 'turquoise')
    
    Returns:
        dict with sync result
    """
    # Check if this filter is a shared attribute
    mapping = None
    for attr_slug, m in SHARED_ATTRIBUTES.items():
        if m["filter_slug"] == filter_slug:
            mapping = m
            break
    
    if not mapping:
        return {"synced": False, "reason": "Not a shared attribute"}
    
    spec_slug = mapping["spec_slug"]
    
    # Remove from specification_types
    result = await db.specification_types.update_one(
        {"slug": spec_slug},
        {
            "$pull": {"values": {"value": value_slug}},
            "$set": {"updated_at": datetime.now(timezone.utc)}
        }
    )
    
    if result.modified_count > 0:
        logger.info(f"Synced deletion of '{value_slug}' from specification_types/{spec_slug}")
        return {"synced": True, "spec_slug": spec_slug, "value": value_slug}
    
    return {"synced": False, "reason": "Value not found in specifications or already removed"}


async def sync_on_spec_value_delete(db: AsyncIOMotorDatabase, spec_slug: str, value_slug: str) -> dict:
    """
    Called when a value is deleted from a specification. If the spec is a shared attribute,
    automatically removes the value from the corresponding filter type.
    
    Args:
        db: Database instance
        spec_slug: Slug of the specification (e.g., 'color')
        value_slug: The value being deleted (e.g., 'turquoise')
    
    Returns:
        dict with sync result
    """
    # Check if this spec is a shared attribute
    mapping = None
    for attr_slug, m in SHARED_ATTRIBUTES.items():
        if m["spec_slug"] == spec_slug:
            mapping = m
            break
    
    if not mapping:
        return {"synced": False, "reason": "Not a shared attribute"}
    
    filter_slug = mapping["filter_slug"]
    
    # Remove from filter_types
    result = await db.filter_types.update_one(
        {"slug": filter_slug},
        {
            "$pull": {"values": {"value": value_slug}},
            "$set": {"updated_at": datetime.now(timezone.utc)}
        }
    )
    
    if result.modified_count > 0:
        logger.info(f"Synced deletion of '{value_slug}' from filter_types/{filter_slug}")
        return {"synced": True, "filter_slug": filter_slug, "value": value_slug}
    
    return {"synced": False, "reason": "Value not found in filters or already removed"}

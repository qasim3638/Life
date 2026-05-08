"""
Custom Mappings Service for Tile Station
=========================================
Handles persistence of manually edited product names.
When a user manually edits a product's display name (product_name),
this service saves that mapping so it won't be overwritten by automated syncs.

Works for ALL suppliers: Verona, Splendour, Wallcano, Ceramica Impex, LEPORCE, Plus39, Canopy, etc.

USAGE IN SYNC ENDPOINTS:
------------------------
Replace:
    from business_config.business_rules import get_display_name
    product_data["product_name"] = get_display_name(product.name, "Verona", product.finish)

With:
    from services.custom_mappings import get_display_name_with_custom_check
    product_data["product_name"] = get_display_name_with_custom_check(
        db, product.name, "Verona", sku, product.finish
    )
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import logging
import os

logger = logging.getLogger(__name__)


def _sanitise_display_name(name: str) -> str:
    """Apply business-rules name cleanup (drops duplicate mm-size trailing tokens,
    collapses whitespace, normalises finish-word casing, etc.)"""
    if not name:
        return name
    try:
        from business_config.business_rules import sanitise_display_name
        return sanitise_display_name(name)
    except Exception:
        return name


def get_custom_mapping(db, supplier: str, sku: str) -> Optional[Dict[str, Any]]:
    """
    Get a custom mapping for a product if it exists.
    
    Args:
        db: MongoDB database connection
        supplier: Supplier name (e.g., "Verona", "Splendour")
        sku: Product SKU
        
    Returns:
        Custom mapping document or None if not found
    """
    try:
        return db.custom_mappings.find_one({
            "supplier": supplier,
            "sku": sku
        }, {"_id": 0})
    except Exception as e:
        logger.error(f"Error getting custom mapping: {e}")
        return None


def save_custom_mapping(
    db,
    supplier: str,
    sku: str,
    original_name: str,
    custom_name: str,
    user_email: str = None,
    supplier_product_name: str = None
) -> Dict[str, Any]:
    """
    Save a custom name mapping for a product.
    
    This is called when a user manually edits a product name through
    Quick Edit or Full Edit. The custom mapping ensures the manual
    name is preserved during automated syncs.
    
    Args:
        db: MongoDB database connection
        supplier: Supplier name (e.g., "Verona", "Splendour")
        sku: Product SKU
        original_name: The supplier's original product name
        custom_name: The user's custom display name
        user_email: Email of the user who made the change (optional)
        supplier_product_name: Custom supplier product name override (optional)
        
    Returns:
        The saved/updated mapping document
    """
    now = datetime.now(timezone.utc).isoformat()
    
    mapping_data = {
        "supplier": supplier,
        "sku": sku,
        "original_name": original_name,
        "custom_name": _sanitise_display_name(custom_name),
        "updated_at": now,
        "updated_by": user_email
    }
    
    # Add supplier_product_name if provided
    if supplier_product_name is not None:
        mapping_data["supplier_product_name"] = supplier_product_name
    
    try:
        result = db.custom_mappings.update_one(
            {"supplier": supplier, "sku": sku},
            {
                "$set": mapping_data,
                "$setOnInsert": {"created_at": now, "created_by": user_email}
            },
            upsert=True
        )
        
        action = "created" if result.upserted_id else "updated"
        logger.info(f"Custom mapping {action} for {supplier}/{sku}: '{custom_name}'" + 
                   (f" (supplier_product_name: '{supplier_product_name}')" if supplier_product_name else ""))
        
        return mapping_data
    except Exception as e:
        logger.error(f"Error saving custom mapping: {e}")
        raise


def delete_custom_mapping(db, supplier: str, sku: str) -> bool:
    """
    Delete a custom mapping (used when user reverts to auto-generated name).
    
    Args:
        db: MongoDB database connection
        supplier: Supplier name
        sku: Product SKU
        
    Returns:
        True if mapping was deleted, False if it didn't exist
    """
    try:
        result = db.custom_mappings.delete_one({
            "supplier": supplier,
            "sku": sku
        })
        
        if result.deleted_count > 0:
            logger.info(f"Custom mapping deleted for {supplier}/{sku}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error deleting custom mapping: {e}")
        return False


def get_all_custom_mappings_for_supplier(db, supplier: str) -> list:
    """
    Get all custom mappings for a specific supplier.
    
    Args:
        db: MongoDB database connection
        supplier: Supplier name
        
    Returns:
        List of custom mapping documents
    """
    try:
        return list(db.custom_mappings.find({"supplier": supplier}, {"_id": 0}))
    except Exception as e:
        logger.error(f"Error getting custom mappings for supplier: {e}")
        return []


def get_display_name_with_custom_check(db, original_name: str, supplier: str, sku: str, finish: str = None) -> str:
    """
    Get display name for a product, checking custom mappings first.
    
    This is the KEY FUNCTION for sync endpoints. Use this instead of 
    calling get_display_name directly. It checks for custom mappings first
    and only falls back to auto-generation if no custom mapping exists.
    
    Args:
        db: MongoDB database connection
        original_name: The supplier's original product name
        supplier: Supplier name
        sku: Product SKU
        finish: Product finish (optional, for auto-generation)
        
    Returns:
        Custom name if mapping exists, otherwise auto-generated name
    """
    # Check for custom mapping first
    custom_mapping = get_custom_mapping(db, supplier, sku)
    
    if custom_mapping:
        logger.debug(f"Using custom mapping for {supplier}/{sku}: {custom_mapping['custom_name']}")
        return _sanitise_display_name(custom_mapping["custom_name"])
    
    # No custom mapping - use auto-generated name from business rules
    try:
        from business_config.business_rules import get_display_name
        return get_display_name(original_name, supplier, finish)
    except Exception as e:
        logger.error(f"Error generating auto name: {e}")
        return original_name


def get_custom_mapping_full(db, supplier: str, sku: str) -> dict:
    """
    Get the full custom mapping including supplier_product_name.
    
    Args:
        db: MongoDB database connection
        supplier: Supplier name
        sku: Product SKU
        
    Returns:
        Dictionary with:
        - custom_name: The custom display name (or None)
        - supplier_product_name: Custom supplier_product_name if set (or None)
        - has_mapping: Boolean indicating if custom mapping exists
    """
    custom_mapping = get_custom_mapping(db, supplier, sku)
    
    if custom_mapping:
        return {
            "custom_name": custom_mapping.get("custom_name"),
            "supplier_product_name": custom_mapping.get("supplier_product_name"),
            "has_mapping": True
        }
    
    return {
        "custom_name": None,
        "supplier_product_name": None,
        "has_mapping": False
    }


def apply_custom_mapping_if_exists(db, product_data: dict, supplier: str) -> dict:
    """
    Apply custom mapping to a product during sync if one exists.
    
    This is an alternative helper that modifies product_data in place.
    Use get_display_name_with_custom_check for most cases.
    
    Args:
        db: MongoDB database connection
        product_data: Product data dictionary
        supplier: Supplier name
        
    Returns:
        Updated product_data with custom name if mapping exists
    """
    sku = product_data.get("sku")
    if not sku:
        return product_data
    
    # Check for custom mapping
    custom_mapping = get_custom_mapping(db, supplier, sku)
    
    if custom_mapping:
        # Apply custom name - this overrides auto-generated name
        product_data["product_name"] = _sanitise_display_name(custom_mapping["custom_name"])
        product_data["has_custom_mapping"] = True
        logger.debug(f"Applied custom mapping for {supplier}/{sku}: {custom_mapping['custom_name']}")
    
    return product_data

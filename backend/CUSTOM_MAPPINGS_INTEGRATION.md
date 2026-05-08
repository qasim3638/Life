# Custom Mappings Feature - Integration Guide

## Overview
This feature ensures that when you manually edit a product's display name (via Quick Edit or Full Edit), 
the change is saved permanently and won't be overwritten by automated syncs.

**How it works:**
1. When you edit a product's `product_name` via Quick Edit → it saves to `custom_mappings` collection
2. When any sync runs (Verona, Splendour, etc.) → it checks `custom_mappings` FIRST
3. If a custom mapping exists → use the custom name
4. If no custom mapping → use the auto-generated name from business rules

---

## Files to Add

### 1. `/backend/services/custom_mappings.py` (NEW FILE)
This file has already been created. Copy from:
`/app/backend/services/custom_mappings.py`

### 2. `/backend/services/__init__.py` (UPDATE if exists, or CREATE)
Add this line:
```python
from services.custom_mappings import *
```

---

## Changes to `/backend/routes/supplier_sync.py`

### Step 1: Add Import at Top
```python
# Add this import near the top with other imports
from services.custom_mappings import save_custom_mapping, get_custom_mapping, get_display_name_with_custom_check
```

### Step 2: Add/Update the Quick Update Endpoint
Find and REPLACE the existing `quick-update` endpoint (or ADD if it doesn't exist):

```python
@router.put("/products/quick-update")
async def quick_update_product(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Quick update endpoint for Supplier Products page Quick Edit modal.
    When product_name is changed, automatically saves custom mapping.
    """
    try:
        db = get_db()
        body = await request.json()
        
        sku = body.get('sku')
        supplier = body.get('supplier')
        
        if not sku or not supplier:
            raise HTTPException(status_code=400, detail="SKU and supplier are required")
        
        # Get the current product to compare names
        current_product = db.supplier_products.find_one({
            "sku": sku,
            "supplier": supplier
        })
        
        if not current_product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        # Build update data
        update_fields = {
            "updated_at": datetime.now(timezone.utc)
        }
        
        # Fields that can be updated
        updatable_fields = [
            'name', 'product_name', 'supplier_product_name', 'original_series',
            'price', 'cost_price', 'stock_quantity', 'stock_m2',
            'category', 'finish', 'in_stock', 'always_in_stock'
        ]
        
        for field in updatable_fields:
            if field in body:
                value = body[field]
                if value == '' and field in ['original_series', 'category', 'finish']:
                    value = None
                update_fields[field] = value
        
        # *** KEY CHANGE: Check if product_name was changed - save custom mapping ***
        new_product_name = body.get('product_name')
        original_name = current_product.get('name') or current_product.get('supplier_product_name', '')
        
        if new_product_name and new_product_name != current_product.get('product_name'):
            # Save custom mapping so this name persists across syncs
            save_custom_mapping(
                db=db,
                supplier=supplier,
                sku=sku,
                original_name=original_name,
                custom_name=new_product_name,
                user_email=current_user.get('email')
            )
            logger.info(f"Saved custom mapping for {supplier}/{sku}: '{new_product_name}'")
        
        # Update supplier_products collection
        result = db.supplier_products.update_one(
            {"sku": sku, "supplier": supplier},
            {"$set": update_fields}
        )
        
        # Also update sync_staging if product exists there
        db.sync_staging.update_one(
            {"sku": sku, "supplier": supplier},
            {"$set": update_fields}
        )
        
        # Also update main products collection if product exists there
        main_update = {k: v for k, v in update_fields.items()}
        if 'product_name' in main_update:
            main_update['name'] = main_update['product_name']
        
        db.products.update_one(
            {"sku": sku},
            {"$set": main_update}
        )
        
        # Return updated product
        updated_product = db.supplier_products.find_one(
            {"sku": sku, "supplier": supplier},
            {"_id": 0}
        )
        
        return {
            "success": True,
            "message": "Product updated successfully",
            "product": updated_product,
            "custom_mapping_saved": new_product_name and new_product_name != current_product.get('product_name')
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Quick update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### Step 3: Update ALL Sync Endpoints to Check Custom Mappings First

In each sync endpoint (Verona, Splendour, Wallcano, Ceramica Impex, LEPORCE, Plus39, Canopy):

**FIND this pattern:**
```python
from business_config.business_rules import get_display_name
product_data["product_name"] = get_display_name(product.name, "Verona", product.finish)
```

**REPLACE with:**
```python
from services.custom_mappings import get_display_name_with_custom_check
product_data["product_name"] = get_display_name_with_custom_check(
    db, product.name, "Verona", sku, product.finish
)
```

**Do this for ALL suppliers:**
- `receive_verona_products` → change "Verona"
- `sync_splendour_products` → change "Splendour"  
- `sync_wallcano_products` → change "Wallcano"
- etc.

---

## New MongoDB Collection

A new collection `custom_mappings` will be automatically created with this structure:

```json
{
    "supplier": "Verona",
    "sku": "product-sku-123",
    "original_name": "Brook Grey 60x60 Matt",
    "custom_name": "Orvieto Grey 60x60cm Matt",
    "created_at": "2025-12-10T10:00:00Z",
    "created_by": "user@email.com",
    "updated_at": "2025-12-10T10:00:00Z",
    "updated_by": "user@email.com"
}
```

---

## Testing the Feature

1. **Test Quick Edit saves mapping:**
   - Edit a product's name via Quick Edit modal
   - Check MongoDB: `db.custom_mappings.find({supplier: "Verona"})`
   - Verify the mapping was created

2. **Test sync respects custom mapping:**
   - Run a sync for that supplier
   - Verify the custom name was NOT overwritten
   - The `has_custom_mapping: true` flag should be set on the product

3. **Test reverting to auto-name:**
   - Delete the custom mapping from MongoDB
   - Run a sync
   - Product should get the auto-generated name again

---

## Optional: Add Management Endpoints

Add these endpoints to view/manage custom mappings:

```python
@router.get("/custom-mappings")
async def get_all_custom_mappings(
    supplier: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all custom mappings, optionally filtered by supplier."""
    db = get_db()
    query = {"supplier": supplier} if supplier else {}
    mappings = list(db.custom_mappings.find(query, {"_id": 0}))
    return {"success": True, "count": len(mappings), "mappings": mappings}


@router.delete("/custom-mappings/{supplier}/{sku}")
async def delete_custom_mapping_endpoint(
    supplier: str, sku: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a custom mapping (revert to auto-generated name)."""
    from services.custom_mappings import delete_custom_mapping
    require_admin_access(current_user)
    db = get_db()
    deleted = delete_custom_mapping(db, supplier, sku)
    if deleted:
        return {"success": True, "message": f"Custom mapping deleted for {supplier}/{sku}"}
    raise HTTPException(status_code=404, detail="Custom mapping not found")
```

---

## Summary of Changes

| File | Action | Purpose |
|------|--------|---------|
| `/backend/services/custom_mappings.py` | CREATE | Core custom mappings logic |
| `/backend/services/__init__.py` | UPDATE | Export custom mappings module |
| `/backend/routes/supplier_sync.py` | UPDATE | Add import + modify quick-update + modify all sync endpoints |

---

## Questions?

If you need help with any specific supplier's sync endpoint modification, let me know which supplier and I'll provide the exact code change.

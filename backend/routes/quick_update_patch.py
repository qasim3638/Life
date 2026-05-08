"""
Quick Update Endpoint with Custom Mappings Support
===================================================
This endpoint handles quick edits from the Supplier Products page.
When product_name is changed, it automatically saves a custom mapping
so the change persists across syncs.

Add this endpoint to your supplier_sync.py file.
"""

# =============================================================================
# ADD THIS TO: backend/routes/supplier_sync.py
# =============================================================================

# 1. First, add this import at the top of supplier_sync.py:
#    from services.custom_mappings import save_custom_mapping, get_custom_mapping

# 2. Then add this endpoint:

@router.put("/products/quick-update")
async def quick_update_product(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Quick update endpoint for Supplier Products page Quick Edit modal.
    
    IMPORTANT: When product_name is changed, this endpoint automatically
    saves a custom mapping so the name persists across syncs.
    
    Expects:
    {
        "sku": "product-sku",
        "supplier": "Verona",
        "name": "Original supplier name",
        "product_name": "Custom display name",  # <- This is what we save to custom_mappings
        "supplier_product_name": "Original name from supplier",
        "original_series": "Series name",
        "price": 29.99,
        "cost_price": 15.00,
        "stock_quantity": 100,
        "stock_m2": 50,
        "category": "Floor Tiles",
        "finish": "Matt",
        "in_stock": true,
        "always_in_stock": false
    }
    """
    try:
        from services.custom_mappings import save_custom_mapping, get_custom_mapping
        
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
                # Handle empty strings for optional fields
                if value == '' and field in ['original_series', 'category', 'finish']:
                    value = None
                update_fields[field] = value
        
        # Check if product_name was changed - if so, save custom mapping
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
            main_update['name'] = main_update['product_name']  # Main products uses 'name' for display
        
        db.products.update_one(
            {"sku": sku},
            {"$set": main_update}
        )
        
        if result.modified_count == 0 and result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Product not found or no changes made")
        
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


# =============================================================================
# 3. MODIFY YOUR SYNC ENDPOINTS to check custom mappings before auto-naming
# =============================================================================

# In each sync endpoint (Verona, Splendour, Wallcano, etc.), 
# REPLACE this pattern:
#
#     from business_config.business_rules import get_display_name
#     product_data["product_name"] = get_display_name(product.name, "Verona", product.finish)
#
# WITH this:
#
#     from services.custom_mappings import get_display_name_with_custom_check
#     product_data["product_name"] = get_display_name_with_custom_check(
#         db, product.name, "Verona", product.sku, product.finish
#     )

# =============================================================================
# 4. EXAMPLE: Modified Verona sync receive endpoint
# =============================================================================

# In the receive_verona_products function, change:
#
# BEFORE:
#     from business_config.business_rules import get_display_name
#     product_data["product_name"] = get_display_name(product.name, "Verona", product.finish)
#
# AFTER:
#     from services.custom_mappings import get_display_name_with_custom_check
#     product_data["product_name"] = get_display_name_with_custom_check(
#         db, product.name, "Verona", sku, product.finish
#     )

# =============================================================================
# 5. CUSTOM MAPPINGS MANAGEMENT ENDPOINTS (Optional but useful)
# =============================================================================

@router.get("/custom-mappings")
async def get_all_custom_mappings(
    supplier: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Get all custom mappings, optionally filtered by supplier.
    Useful for reviewing what manual name changes have been made.
    """
    try:
        db = get_db()
        
        query = {}
        if supplier:
            query["supplier"] = supplier
        
        mappings = list(db.custom_mappings.find(query, {"_id": 0}).sort([
            ("supplier", 1),
            ("updated_at", -1)
        ]))
        
        return {
            "success": True,
            "count": len(mappings),
            "mappings": mappings
        }
        
    except Exception as e:
        logger.error(f"Get custom mappings error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/custom-mappings/{supplier}/{sku}")
async def delete_custom_mapping_endpoint(
    supplier: str,
    sku: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a custom mapping (revert to auto-generated name).
    After deletion, the next sync will apply the default naming rules.
    """
    try:
        from services.custom_mappings import delete_custom_mapping
        
        require_admin_access(current_user)
        db = get_db()
        
        deleted = delete_custom_mapping(db, supplier, sku)
        
        if deleted:
            return {
                "success": True,
                "message": f"Custom mapping deleted for {supplier}/{sku}. Next sync will apply default naming."
            }
        else:
            raise HTTPException(status_code=404, detail="Custom mapping not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete custom mapping error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

"""
Bulk Stock Update API - Update stock for multiple products at once
"""
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from config import get_db
from services import get_current_user, require_admin_access, log_audit

router = APIRouter(prefix="/bulk-stock", tags=["Bulk Stock"])


class StockUpdate(BaseModel):
    product_id: str
    showroom_id: str
    quantity: int
    operation: str = "set"  # "set" (replace), "add" (increment), "subtract" (decrement)


class BulkStockUpdateRequest(BaseModel):
    updates: List[StockUpdate]
    dry_run: bool = False


class BulkStockUpdateResponse(BaseModel):
    success: bool
    updated_count: int
    errors: List[dict]
    preview: List[dict]


@router.post("/update", response_model=BulkStockUpdateResponse)
async def bulk_update_stock(
    request: BulkStockUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Update stock for multiple products across different showrooms in a single request.
    
    Supports three operations:
    - "set": Set the stock to the exact quantity
    - "add": Add quantity to existing stock
    - "subtract": Subtract quantity from existing stock
    """
    require_admin_access(current_user)
    
    db = get_db()
    
    # Get all affected product IDs
    product_ids = list(set(u.product_id for u in request.updates))
    
    # Fetch all products in one query
    products = await db.products.find(
        {"id": {"$in": product_ids}},
        {"_id": 0}
    ).to_list(len(product_ids))
    
    products_map = {p["id"]: p for p in products}
    
    # Process updates
    results = []
    errors = []
    updated_count = 0
    
    # Group updates by product_id to handle multiple showroom updates per product
    updates_by_product = {}
    for update in request.updates:
        if update.product_id not in updates_by_product:
            updates_by_product[update.product_id] = []
        updates_by_product[update.product_id].append(update)
    
    for product_id, product_updates in updates_by_product.items():
        product = products_map.get(product_id)
        
        if not product:
            errors.append({
                "product_id": product_id,
                "error": "Product not found"
            })
            continue
        
        # Get current showroom stock as a dict for easier manipulation
        showroom_stock = product.get("showroom_stock", [])
        if isinstance(showroom_stock, dict):
            # Convert old dict format to list format
            showroom_stock = [
                {"showroom_id": k, "quantity": v}
                for k, v in showroom_stock.items()
            ]
        elif not isinstance(showroom_stock, list):
            showroom_stock = []
        
        # Build a map for easy access
        stock_map = {s.get("showroom_id"): s.get("quantity", 0) for s in showroom_stock}
        
        # Apply each update for this product
        for update in product_updates:
            current_qty = stock_map.get(update.showroom_id, 0)
            
            if update.operation == "set":
                new_qty = update.quantity
            elif update.operation == "add":
                new_qty = current_qty + update.quantity
            elif update.operation == "subtract":
                new_qty = max(0, current_qty - update.quantity)
            else:
                errors.append({
                    "product_id": product_id,
                    "showroom_id": update.showroom_id,
                    "error": f"Invalid operation: {update.operation}"
                })
                continue
            
            stock_map[update.showroom_id] = new_qty
            
            results.append({
                "product_id": product_id,
                "product_name": product.get("name"),
                "product_sku": product.get("sku"),
                "showroom_id": update.showroom_id,
                "previous_quantity": current_qty,
                "new_quantity": new_qty,
                "operation": update.operation
            })
        
        # Apply to database if not dry run
        if not request.dry_run:
            # Convert back to list format
            new_showroom_stock = [
                {"showroom_id": k, "quantity": v}
                for k, v in stock_map.items()
                if v > 0  # Only keep non-zero entries
            ]
            
            # Calculate total stock
            total_stock = sum(v for v in stock_map.values())
            
            await db.products.update_one(
                {"id": product_id},
                {
                    "$set": {
                        "showroom_stock": new_showroom_stock,
                        "stock": total_stock,
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }
                }
            )
            updated_count += 1
    
    # Log audit if changes were made
    if not request.dry_run and updated_count > 0:
        await log_audit(
            action="BULK_STOCK_UPDATE",
            entity_type="products",
            user=current_user,
            details=f"Bulk stock update: {updated_count} products updated, {len(results)} showroom allocations changed"
        )
    
    return BulkStockUpdateResponse(
        success=len(errors) == 0,
        updated_count=updated_count if not request.dry_run else 0,
        errors=errors,
        preview=results
    )


@router.get("/products-with-stock")
async def get_products_with_showroom_stock(
    search: Optional[str] = None,
    showroom_id: Optional[str] = None,
    supplier_name: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: dict = Depends(get_current_user)
):
    """
    Get products with their showroom stock allocations.
    Optimized for bulk stock editing UI.
    """
    db = get_db()
    
    # Build query
    query = {}
    
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"sku": {"$regex": search, "$options": "i"}}
        ]
    
    if supplier_name:
        query["supplier_name"] = {"$regex": supplier_name, "$options": "i"}
    
    # Get total count
    total = await db.products.count_documents(query)
    
    # Fetch products
    products = await db.products.find(
        query,
        {"_id": 0, "id": 1, "name": 1, "sku": 1, "stock": 1, "showroom_stock": 1, "supplier_name": 1}
    ).skip(offset).limit(limit).to_list(limit)
    
    # Get showrooms for reference
    showrooms = await db.showrooms.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(100)
    showrooms_map = {s["id"]: s["name"] for s in showrooms}
    
    # Format response
    formatted_products = []
    for p in products:
        showroom_stock = p.get("showroom_stock", [])
        
        # Handle both dict and list formats
        if isinstance(showroom_stock, dict):
            stock_list = [
                {
                    "showroom_id": k,
                    "showroom_name": showrooms_map.get(k, "Unknown"),
                    "quantity": v
                }
                for k, v in showroom_stock.items()
            ]
        elif isinstance(showroom_stock, list):
            stock_list = [
                {
                    "showroom_id": s.get("showroom_id"),
                    "showroom_name": showrooms_map.get(s.get("showroom_id"), "Unknown"),
                    "quantity": s.get("quantity", 0)
                }
                for s in showroom_stock
            ]
        else:
            stock_list = []
        
        formatted_products.append({
            "id": p.get("id"),
            "name": p.get("name"),
            "sku": p.get("sku"),
            "total_stock": p.get("stock", 0),
            "supplier_name": p.get("supplier_name"),
            "showroom_allocations": stock_list
        })
    
    return {
        "products": formatted_products,
        "showrooms": showrooms,
        "total": total,
        "limit": limit,
        "offset": offset
    }

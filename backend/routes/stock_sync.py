"""
Stock Sync API Routes
Provides endpoints for managing stock synchronization.
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from typing import Dict, Optional
from datetime import datetime
import asyncio

from services.sync.stock_sync_service import get_sync_service, SyncResult
from services.auth import get_current_user, require_admin_access

router = APIRouter(prefix="/stock-sync", tags=["Stock Sync"])


@router.get("/status")
async def get_sync_status(current_user: dict = Depends(get_current_user)):
    """Get current sync status for all suppliers"""
    service = get_sync_service()
    return service.get_sync_status()


@router.post("/sync-all")
async def trigger_full_sync(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(require_admin_access)
):
    """
    Trigger a full sync of all suppliers.
    Runs in background - check status endpoint for progress.
    """
    service = get_sync_service()
    
    # Run sync in background
    background_tasks.add_task(service.sync_all)
    
    return {
        "message": "Full sync started",
        "started_at": datetime.utcnow().isoformat(),
        "note": "Check /status endpoint for progress"
    }


@router.post("/sync/{supplier}")
async def trigger_supplier_sync(
    supplier: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(require_admin_access)
):
    """
    Trigger sync for a specific supplier.
    
    Suppliers: wallcano, splendour, verona, ceramica_impex
    """
    valid_suppliers = ["wallcano", "splendour", "verona", "ceramica_impex"]
    
    if supplier not in valid_suppliers:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid supplier. Must be one of: {valid_suppliers}"
        )
    
    service = get_sync_service()
    
    # Run sync in background
    background_tasks.add_task(service.sync_supplier, supplier)
    
    return {
        "message": f"Sync started for {supplier}",
        "started_at": datetime.utcnow().isoformat()
    }


@router.get("/products/{supplier}")
async def get_supplier_products(
    supplier: str,
    skip: int = 0,
    limit: int = 50,
    current_user: dict = Depends(get_current_user)
):
    """
    Get products from a specific supplier.
    """
    from database import get_database
    
    db = get_database()
    collection = db.supplier_products
    
    # Get products
    cursor = collection.find(
        {"supplier": supplier},
        {"_id": 0}
    ).skip(skip).limit(limit)
    
    products = await cursor.to_list(length=limit)
    total = await collection.count_documents({"supplier": supplier})
    
    return {
        "supplier": supplier,
        "products": products,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/products/{supplier}/stock-summary")
async def get_stock_summary(
    supplier: str,
    current_user: dict = Depends(get_current_user)
):
    """Get stock summary for a supplier"""
    from database import get_database
    
    db = get_database()
    collection = db.supplier_products
    
    # Aggregate stock stats
    pipeline = [
        {"$match": {"supplier": supplier}},
        {"$group": {
            "_id": "$stock_status",
            "count": {"$sum": 1},
            "total_sqm": {"$sum": "$stock_sqm"}
        }}
    ]
    
    cursor = collection.aggregate(pipeline)
    results = await cursor.to_list(length=10)
    
    summary = {
        "supplier": supplier,
        "in_stock": {"count": 0, "sqm": 0},
        "low_stock": {"count": 0, "sqm": 0},
        "out_of_stock": {"count": 0, "sqm": 0}
    }
    
    for r in results:
        status_key = r["_id"].lower().replace(" ", "_")
        if status_key in summary:
            summary[status_key] = {
                "count": r["count"],
                "sqm": r["total_sqm"]
            }
    
    return summary


@router.get("/history")
async def get_sync_history(
    limit: int = 10,
    current_user: dict = Depends(get_current_user)
):
    """Get recent sync history"""
    import os
    import json
    from pathlib import Path
    
    results_dir = Path("/app/sync_results")
    
    if not results_dir.exists():
        return {"history": []}
    
    # Get all sync result files
    files = sorted(results_dir.glob("sync_*.json"), reverse=True)[:limit]
    
    history = []
    for file in files:
        with open(file) as f:
            data = json.load(f)
            history.append(data)
    
    return {"history": history}

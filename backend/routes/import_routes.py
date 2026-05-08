"""
Product Import API Routes
Admin routes for importing products from supplier portals
"""
import uuid
import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query
from pydantic import BaseModel, Field

from config import get_db
from services import get_current_user, require_permission
from services.product_importer import SplendourTilesImporter, TileStationWixImporter
from services.scrapers.wallcano_scraper import WallcanoScraper
from services.scrapers.ceramica_impex_scraper import CeramicaImpexScraper
from services.scheduler import (
    add_scheduled_job,
    remove_scheduled_job,
    calculate_next_run,
    get_scheduler_status,
    scheduled_job_history
)

router = APIRouter(prefix="/import", tags=["Product Import"])
logger = logging.getLogger(__name__)

# Store for import jobs status
import_jobs = {}


class ImportCredentials(BaseModel):
    """Credentials for supplier portal"""
    email: Optional[str] = None
    password: Optional[str] = None


class ImportJob(BaseModel):
    """Import job configuration"""
    supplier: str = Field(..., description="Supplier name: splendour_tiles, wix")
    credentials: Optional[ImportCredentials] = None
    limit: Optional[int] = Field(None, description="Max products to import")
    category_filter: Optional[str] = Field(None, description="Filter by category")
    dry_run: bool = Field(False, description="Preview without saving")


class ImportSchedule(BaseModel):
    """Schedule for automatic imports"""
    supplier: str
    credentials: ImportCredentials
    frequency: str = Field(..., description="daily, weekly, monthly")
    time: str = Field("03:00", description="Time to run (HH:MM)")
    enabled: bool = True
    category_filter: Optional[str] = None


class ProductMapping(BaseModel):
    """Map imported product fields to local schema"""
    source_sku: str
    local_product_id: Optional[str] = None
    action: str = Field("create", description="create, update, skip")
    price_multiplier: float = Field(1.5, description="Cost to retail price multiplier")
    category_id: Optional[str] = None


# ============ IMPORT ENDPOINTS ============

@router.post("/start")
async def start_import_job(
    job: ImportJob,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user)
):
    """Start a product import job"""
    # Check admin permission
    if current_user.get("role") not in ["super_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Create job ID
    job_id = str(uuid.uuid4())[:8]
    
    # Get credentials (optional for Wix)
    email = job.credentials.email if job.credentials else None
    password = job.credentials.password if job.credentials else None
    
    # Initialize job status
    import_jobs[job_id] = {
        "id": job_id,
        "status": "starting",
        "supplier": job.supplier,
        "dry_run": job.dry_run,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "started_by": current_user.get("email"),
        "progress": {
            "stage": "initializing",
            "current": 0,
            "total": 0,
            "message": "Starting import..."
        },
        "products_found": 0,
        "products_imported": 0,
        "products_updated": 0,
        "products_skipped": 0,
        "errors": [],
        "completed_at": None
    }
    
    # Start background import
    background_tasks.add_task(
        run_import_job,
        job_id,
        job.supplier,
        email,
        password,
        job.limit,
        job.dry_run,
        job.category_filter
    )
    
    return {
        "job_id": job_id,
        "status": "started",
        "message": f"Import job started for {job.supplier}"
    }


@router.get("/status/{job_id}")
async def get_import_status(
    job_id: str,
    current_user = Depends(get_current_user)
):
    """Get status of an import job"""
    if job_id not in import_jobs:
        raise HTTPException(status_code=404, detail="Import job not found")
    
    return import_jobs[job_id]


@router.get("/jobs")
async def list_import_jobs(
    current_user = Depends(get_current_user),
    limit: int = Query(20, le=100)
):
    """List recent import jobs"""
    if current_user.get("role") not in ["super_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Sort by start time descending
    sorted_jobs = sorted(
        import_jobs.values(),
        key=lambda x: x.get("started_at", ""),
        reverse=True
    )[:limit]
    
    return sorted_jobs


@router.delete("/jobs/{job_id}")
async def cancel_import_job(
    job_id: str,
    current_user = Depends(get_current_user)
):
    """Cancel a running import job"""
    if current_user.get("role") not in ["super_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if job_id not in import_jobs:
        raise HTTPException(status_code=404, detail="Import job not found")
    
    import_jobs[job_id]["status"] = "cancelled"
    import_jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
    
    return {"message": "Import job cancelled"}


@router.get("/preview/{job_id}")
async def get_import_preview(
    job_id: str,
    current_user = Depends(get_current_user),
    skip: int = 0,
    limit: int = 50
):
    """Get preview of imported products (for dry run)"""
    if job_id not in import_jobs:
        raise HTTPException(status_code=404, detail="Import job not found")
    
    job = import_jobs[job_id]
    products = job.get("preview_products", [])
    
    return {
        "total": len(products),
        "products": products[skip:skip + limit]
    }


@router.post("/confirm/{job_id}")
async def confirm_import(
    job_id: str,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user)
):
    """Confirm and save products from a dry run"""
    if current_user.get("role") not in ["super_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if job_id not in import_jobs:
        raise HTTPException(status_code=404, detail="Import job not found")
    
    job = import_jobs[job_id]
    
    if not job.get("dry_run"):
        raise HTTPException(status_code=400, detail="Not a dry run job")
    
    if job.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Job not completed yet")
    
    products = job.get("preview_products", [])
    
    if not products:
        raise HTTPException(status_code=400, detail="No products to import")
    
    # Start saving in background
    background_tasks.add_task(
        save_imported_products,
        job_id,
        products
    )
    
    return {
        "message": f"Saving {len(products)} products",
        "job_id": job_id
    }


# ============ SCHEDULE ENDPOINTS ============

@router.post("/schedule")
async def create_import_schedule(
    schedule: ImportSchedule,
    current_user = Depends(get_current_user)
):
    """Create a scheduled import job"""
    if current_user.get("role") not in ["super_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    db = get_db()
    
    # Calculate next run time
    next_run = calculate_next_run(schedule.frequency, schedule.time)
    
    schedule_doc = {
        "id": str(uuid.uuid4()),
        "supplier": schedule.supplier,
        "credentials": {
            "email": schedule.credentials.email,
            "password": schedule.credentials.password  # In production, encrypt this!
        },
        "frequency": schedule.frequency,
        "time": schedule.time,
        "enabled": schedule.enabled,
        "category_filter": schedule.category_filter,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user.get("email"),
        "last_run": None,
        "last_run_status": None,
        "last_run_error": None,
        "last_run_products_found": 0,
        "last_run_products_imported": 0,
        "last_run_products_updated": 0,
        "next_run": next_run.isoformat() if next_run else None
    }
    
    await db.import_schedules.insert_one(schedule_doc)
    
    # Add to scheduler if enabled
    if schedule.enabled:
        await add_scheduled_job(schedule_doc["id"], schedule.frequency, schedule.time)
    
    return {
        "message": "Schedule created",
        "schedule_id": schedule_doc["id"],
        "next_run": schedule_doc["next_run"]
    }


@router.get("/schedules")
async def list_import_schedules(
    current_user = Depends(get_current_user)
):
    """List all import schedules"""
    if current_user.get("role") not in ["super_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    db = get_db()
    schedules = await db.import_schedules.find({}, {"_id": 0, "credentials.password": 0}).to_list(100)
    
    return schedules


@router.get("/schedules/{schedule_id}")
async def get_import_schedule(
    schedule_id: str,
    current_user = Depends(get_current_user)
):
    """Get a specific import schedule"""
    if current_user.get("role") not in ["super_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    db = get_db()
    schedule = await db.import_schedules.find_one(
        {"id": schedule_id}, 
        {"_id": 0, "credentials.password": 0}
    )
    
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    return schedule


class ImportScheduleUpdate(BaseModel):
    """Update model for import schedule"""
    frequency: Optional[str] = None
    time: Optional[str] = None
    enabled: Optional[bool] = None
    category_filter: Optional[str] = None


@router.put("/schedules/{schedule_id}")
async def update_import_schedule(
    schedule_id: str,
    update_data: ImportScheduleUpdate,
    current_user = Depends(get_current_user)
):
    """Update an import schedule"""
    if current_user.get("role") not in ["super_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    db = get_db()
    schedule = await db.import_schedules.find_one({"id": schedule_id})
    
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    # Build update dict
    updates = {}
    if update_data.frequency is not None:
        updates["frequency"] = update_data.frequency
    if update_data.time is not None:
        updates["time"] = update_data.time
    if update_data.enabled is not None:
        updates["enabled"] = update_data.enabled
    if update_data.category_filter is not None:
        updates["category_filter"] = update_data.category_filter
    
    # Recalculate next run if frequency or time changed
    frequency = update_data.frequency or schedule.get("frequency", "daily")
    time_str = update_data.time or schedule.get("time", "03:00")
    next_run = calculate_next_run(frequency, time_str)
    updates["next_run"] = next_run.isoformat() if next_run else None
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.import_schedules.update_one({"id": schedule_id}, {"$set": updates})
    
    # Update scheduler job
    enabled = update_data.enabled if update_data.enabled is not None else schedule.get("enabled", True)
    if enabled:
        await add_scheduled_job(schedule_id, frequency, time_str)
    else:
        await remove_scheduled_job(schedule_id)
    
    return {"message": "Schedule updated", "next_run": updates["next_run"]}


@router.delete("/schedules/{schedule_id}")
async def delete_import_schedule(
    schedule_id: str,
    current_user = Depends(get_current_user)
):
    """Delete an import schedule"""
    if current_user.get("role") not in ["super_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    db = get_db()
    result = await db.import_schedules.delete_one({"id": schedule_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    # Remove from scheduler
    await remove_scheduled_job(schedule_id)
    
    return {"message": "Schedule deleted"}


# Supplier credentials — passwords sourced from env vars (Feb 2026 security)
SUPPLIER_CREDENTIALS = {
    "splendour_tiles": {
        "email": "accounts@tilestation.co.uk",
        "password": os.environ.get("SPLENDOUR_PORTAL_PASSWORD", "")
    },
    "wallcano_tiles": {
        "email": "accounts@tilestation.co.uk",
        "password": os.environ.get("WALLCANO_PORTAL_PASSWORD", "")
    },
    "ceramica_impex": {
        "email": "qasim@tilestation.co.uk",
        "password": os.environ.get("CERAMICA_PORTAL_PASSWORD", "")
    }
}


@router.post("/schedules/{supplier_id}/run")
async def run_scraper_by_supplier(
    supplier_id: str,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user)
):
    """
    Run scraper by supplier ID (e.g., 'splendour_tiles', 'wallcano_tiles')
    This is the endpoint called by the ScrapingPortal frontend.
    """
    if current_user.get("role") not in ["super_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    db = get_db()
    
    # First check if there's a schedule for this supplier
    schedule = await db.import_schedules.find_one({"supplier": supplier_id})
    
    if schedule:
        # Use credentials from schedule
        credentials = schedule.get("credentials", {})
        email = credentials.get("email")
        password = credentials.get("password")
    else:
        # Use default credentials
        creds = SUPPLIER_CREDENTIALS.get(supplier_id, {})
        email = creds.get("email")
        password = creds.get("password")
        
        if not email or not password:
            raise HTTPException(
                status_code=400, 
                detail=f"No credentials configured for {supplier_id}. Please create a schedule with credentials first."
            )
    
    # Create a manual job
    job_id = str(uuid.uuid4())[:8]
    
    import_jobs[job_id] = {
        "id": job_id,
        "status": "starting",
        "supplier": supplier_id,
        "dry_run": False,
        "scheduled": False,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "started_by": current_user.get("email"),
        "progress": {
            "stage": "initializing",
            "current": 0,
            "total": 0,
            "message": f"Starting {supplier_id} scraper..."
        },
        "products_found": 0,
        "products_imported": 0,
        "products_updated": 0,
        "products_skipped": 0,
        "errors": [],
        "completed_at": None
    }
    
    # Run import in background
    background_tasks.add_task(
        run_import_job,
        job_id,
        supplier_id,
        email,
        password,
        None,  # No limit
        False,  # Not a dry run
        None   # No category filter
    )
    
    return {
        "message": f"Import started for {supplier_id}",
        "job_id": job_id
    }


@router.post("/schedules/{schedule_id}/run-now")
async def run_schedule_now(
    schedule_id: str,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user)
):
    """Manually trigger a scheduled import to run immediately"""
    if current_user.get("role") not in ["super_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    db = get_db()
    schedule = await db.import_schedules.find_one({"id": schedule_id})
    
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    credentials = schedule.get("credentials", {})
    
    # Create a manual job based on the schedule
    job_id = str(uuid.uuid4())[:8]
    
    import_jobs[job_id] = {
        "id": job_id,
        "status": "starting",
        "supplier": schedule.get("supplier"),
        "dry_run": False,
        "scheduled": True,
        "schedule_id": schedule_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "started_by": current_user.get("email"),
        "progress": {
            "stage": "initializing",
            "current": 0,
            "total": 0,
            "message": "Starting manual run..."
        },
        "products_found": 0,
        "products_imported": 0,
        "products_updated": 0,
        "products_skipped": 0,
        "errors": [],
        "completed_at": None
    }
    
    # Run import in background
    background_tasks.add_task(
        run_import_job,
        job_id,
        schedule.get("supplier"),
        credentials.get("email"),
        credentials.get("password"),
        None,  # No limit for manual runs
        False,  # Not a dry run
        schedule.get("category_filter")
    )
    
    return {
        "message": "Import started",
        "job_id": job_id
    }


@router.get("/scheduler/status")
async def get_scheduler_status_endpoint(
    current_user = Depends(get_current_user)
):
    """Get the current status of the scheduler"""
    if current_user.get("role") not in ["super_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return get_scheduler_status()


# ============ BACKGROUND TASKS ============

async def run_import_job(
    job_id: str,
    supplier: str,
    email: str,
    password: str,
    limit: Optional[int],
    dry_run: bool,
    category_filter: Optional[str]
):
    """Run the actual import job in background"""
    try:
        import_jobs[job_id]["status"] = "running"
        
        async def progress_callback(progress):
            import_jobs[job_id]["progress"] = {
                "stage": progress.get("stage", ""),
                "current": progress.get("current", 0),
                "total": progress.get("total", 0),
                "message": progress.get("product") or progress.get("range") or progress.get("category", "")
            }
        
        products = []
        
        if supplier == "splendour_tiles":
            async with SplendourTilesImporter(
                base_url="https://www.splendourtiles.co.uk",
                credentials={'email': email, 'password': password}
            ) as importer:
                
                logged_in = await importer.login()
                if not logged_in:
                    import_jobs[job_id]["status"] = "failed"
                    import_jobs[job_id]["errors"].append("Login failed - check credentials")
                    return
                
                products = await importer.import_all_products(
                    progress_callback=progress_callback,
                    limit=limit
                )
        
        elif supplier == "wix" or supplier == "tilestation_wix":
            # Wix import - no credentials required
            async with TileStationWixImporter(
                base_url="https://www.tilestation.co.uk"
            ) as importer:
                
                connected = await importer.login()
                if not connected:
                    import_jobs[job_id]["status"] = "failed"
                    import_jobs[job_id]["errors"].append("Failed to connect to Wix site")
                    return
                
                products = await importer.import_all_products(
                    progress_callback=progress_callback,
                    limit=limit
                )
        
        elif supplier == "wallcano_tiles":
            # Wallcano scraper
            try:
                scraper = WallcanoScraper(email, password)
                
                import_jobs[job_id]["progress"]["message"] = "Logging in to Wallcano..."
                logged_in = await scraper.login()
                
                if not logged_in:
                    import_jobs[job_id]["status"] = "failed"
                    import_jobs[job_id]["errors"].append("Login failed to Wallcano - check credentials")
                    return
                
                import_jobs[job_id]["progress"]["message"] = "Fetching products from Wallcano..."
                scraper_products = await scraper.get_all_products()
                
                # Convert scraper products to import format
                products = []
                for p in scraper_products:
                    products.append({
                        "sku": p.supplier_code,
                        "name": p.name,
                        "size": p.size,
                        "material": p.material,
                        "finish": p.finish,
                        "cost_price": p.room_lot_price,
                        "stock_sqm": p.stock_sqm,
                        "images": p.images,
                        "category": p.category,
                        "source": "wallcano_scraper"
                    })
                    
            except Exception as e:
                import_jobs[job_id]["status"] = "failed"
                import_jobs[job_id]["errors"].append(f"Wallcano scraper error: {str(e)}")
                return
        
        elif supplier == "ceramica_impex":
            # Ceramica Impex scraper
            try:
                scraper = CeramicaImpexScraper(email, password)
                
                import_jobs[job_id]["progress"]["message"] = "Logging in to Ceramica Impex..."
                logged_in = await scraper.login()
                
                if not logged_in:
                    import_jobs[job_id]["status"] = "failed"
                    import_jobs[job_id]["errors"].append("Login failed to Ceramica Impex - check credentials")
                    return
                
                import_jobs[job_id]["progress"]["message"] = "Fetching products from Ceramica Impex..."
                scraper_products = await scraper.get_all_products()
                
                # Convert scraper products to import format
                products = []
                for p in scraper_products:
                    products.append({
                        "sku": p.supplier_code,
                        "name": p.name,
                        "size": p.size,
                        "material": p.material,
                        "finish": p.finish,
                        "cost_price": p.room_lot_price,
                        "stock_sqm": p.stock_sqm,
                        "images": p.images,
                        "category": p.category,
                        "source": "ceramica_impex_scraper"
                    })
                    
            except Exception as e:
                import_jobs[job_id]["status"] = "failed"
                import_jobs[job_id]["errors"].append(f"Ceramica Impex scraper error: {str(e)}")
                return
        
        else:
            import_jobs[job_id]["status"] = "failed"
            import_jobs[job_id]["errors"].append(f"Unknown supplier: {supplier}")
            return
        
        import_jobs[job_id]["products_found"] = len(products)
        
        if dry_run:
            # Store for preview
            import_jobs[job_id]["preview_products"] = products
            import_jobs[job_id]["status"] = "completed"
            import_jobs[job_id]["progress"]["message"] = f"Preview ready: {len(products)} products"
        else:
            # Save directly
            saved_count = await save_imported_products(job_id, products)
            import_jobs[job_id]["products_imported"] = saved_count
            import_jobs[job_id]["status"] = "completed"
            import_jobs[job_id]["progress"]["message"] = f"Imported {saved_count} products"
        
        import_jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
        
    except Exception as e:
        logger.error(f"Import job {job_id} failed: {str(e)}")
        import_jobs[job_id]["status"] = "failed"
        import_jobs[job_id]["errors"].append(str(e))
        import_jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()


async def save_imported_products(job_id: str, products: List[dict]) -> int:
    """Save imported products to sync_staging for review in Sync Hub"""
    from motor.motor_asyncio import AsyncIOMotorClient
    import os
    
    logger.info(f"Starting save_imported_products for job {job_id} with {len(products)} products")
    
    # Use Motor for async MongoDB operations
    mongo_url = os.environ.get('MONGO_URL')
    if not mongo_url:
        raise ValueError("MONGO_URL environment variable is required")
    client = AsyncIOMotorClient(mongo_url)
    db = client[os.environ.get('DB_NAME', 'tile_station')]
    
    saved = 0
    updated = 0
    skipped = 0
    
    # Determine supplier name from first product
    supplier_name = "Unknown"
    if products:
        source = products[0].get("source", "")
        if "wallcano" in source.lower():
            supplier_name = "Wallcano"
        elif "splendour" in source.lower():
            supplier_name = "Splendour"
        elif "ceramica" in source.lower():
            supplier_name = "Ceramica Impex"
    
    for product in products:
        try:
            sku = product.get("sku", "")
            if not sku:
                logger.warning(f"Skipping product with no SKU: {product.get('name', 'Unknown')}")
                skipped += 1
                continue
            
            # Prepare staging data (flat structure matching existing format)
            staging_data = {
                "sku": sku,
                "supplier_code": sku,
                "name": product.get("name", ""),
                "supplier": supplier_name,
                "size": product.get("size", ""),
                "material": product.get("material", ""),
                "finish": product.get("finish", ""),
                "price": product.get("cost_price") or 0,
                "stock_m2": product.get("stock_sqm") or 0,
                "stock_quantity": product.get("stock_sqm") or 0,
                "images": product.get("images", []),
                "category": product.get("category", ""),
                "sync_source": "scraper",
                "synced_at": datetime.now(timezone.utc)
            }
            
            # Use upsert to simplify - update if exists, insert if not
            result = await db.sync_staging.update_one(
                {"supplier": supplier_name, "sku": sku},
                {"$set": staging_data},
                upsert=True
            )
            
            if result.upserted_id:
                logger.info(f"Inserted new staged product: {sku} for {supplier_name}, id={result.upserted_id}")
                saved += 1
            elif result.matched_count > 0:
                logger.info(f"Updated existing staged product: {sku} for {supplier_name}, matched={result.matched_count}, modified={result.modified_count}")
                updated += 1
            else:
                logger.warning(f"No match and no upsert for: {sku} for {supplier_name}, result={result.raw_result}")
                
        except Exception as e:
            logger.error(f"Error staging product {product.get('name')}: {str(e)}")
            skipped += 1
    
    # Update job stats
    if job_id in import_jobs:
        import_jobs[job_id]["products_imported"] = saved
        import_jobs[job_id]["products_updated"] = updated
        import_jobs[job_id]["products_skipped"] = skipped
        import_jobs[job_id]["progress"]["message"] = f"Staged {saved} new, updated {updated}"
    
    logger.info(f"Finished staging products for job {job_id}: saved={saved}, updated={updated}, skipped={skipped}")
    client.close()
    return saved + updated

"""
Web Scraper API routes for fetching product images from supplier websites
All scraped images are automatically uploaded to Cloudflare R2 cloud storage.
"""
import uuid
import asyncio
import os
import aiohttp
from datetime import datetime, timezone
from typing import List, Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel

from config import get_db
from services import get_current_user, require_admin_access
from services.scraper import SupplierScraperFactory

# Import R2 uploader for automatic image upload
try:
    from services.storage.r2_uploader import process_product_images, R2ImageUploader
    R2_AVAILABLE = R2ImageUploader.is_configured()
except ImportError:
    R2_AVAILABLE = False
    process_product_images = None

import logging
logger = logging.getLogger(__name__)

router = APIRouter(tags=["Scraper"])

# Upload directory for downloaded images
UPLOAD_DIR = Path("/app/backend/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class ScrapeRequest(BaseModel):
    """Request to scrape a single product"""
    supplier_name: str
    sku: str
    product_name: Optional[str] = ""


class BatchScrapeRequest(BaseModel):
    """Request to scrape multiple products"""
    products: List[ScrapeRequest]
    update_products: bool = True  # Whether to update product images in database


class ScrapeResult(BaseModel):
    """Result of a scrape operation"""
    sku: str
    supplier: str
    success: bool
    images: List[str] = []
    description: Optional[str] = None
    product_url: Optional[str] = None
    error: Optional[str] = None


class ScrapeJobStatus(BaseModel):
    """Status of a background scrape job"""
    job_id: str
    status: str  # pending, running, completed, failed
    total: int
    processed: int
    successful: int
    failed: int
    results: List[dict] = []
    created_at: datetime
    completed_at: Optional[datetime] = None


# In-memory job storage (in production, use Redis or database)
scrape_jobs: dict = {}


@router.post("/scraper/single", response_model=ScrapeResult)
async def scrape_single_product(
    request: ScrapeRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Scrape a single product from a supplier website.
    Images are automatically uploaded to R2 cloud storage.
    Returns images, description, and product URL if found.
    """
    require_admin_access(current_user)
    
    result = await SupplierScraperFactory.scrape_product(
        request.supplier_name,
        request.sku,
        request.product_name or ""
    )
    
    # Upload images to R2 cloud storage (use product name for image naming)
    images = result.get("images", [])
    if R2_AVAILABLE and process_product_images and images:
        try:
            # Use product name for R2 image naming, fallback to SKU
            product_display_name = request.product_name or result.get("name") or request.sku
            processed_images, uploaded_count = await process_product_images(
                images,
                request.supplier_name,
                product_display_name  # Use display name, not SKU
            )
            images = processed_images
            if uploaded_count > 0:
                logger.info(f"Uploaded {uploaded_count} images to R2 for {product_display_name}")
        except Exception as e:
            logger.warning(f"Failed to upload images to R2: {e}")
    
    return ScrapeResult(
        sku=result.get("sku", request.sku),
        supplier=result.get("supplier", request.supplier_name),
        success=result.get("success", False),
        images=images,
        description=result.get("description"),
        product_url=result.get("product_url"),
        error=result.get("error")
    )


@router.post("/scraper/batch")
async def scrape_batch_products(
    request: BatchScrapeRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    Start a background job to scrape multiple products.
    Returns a job ID that can be used to check status.
    """
    require_admin_access(current_user)
    
    if len(request.products) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 products per batch")
    
    job_id = str(uuid.uuid4())
    
    scrape_jobs[job_id] = ScrapeJobStatus(
        job_id=job_id,
        status="pending",
        total=len(request.products),
        processed=0,
        successful=0,
        failed=0,
        results=[],
        created_at=datetime.now(timezone.utc)
    )
    
    background_tasks.add_task(
        run_batch_scrape,
        job_id,
        request.products,
        request.update_products
    )
    
    return {"job_id": job_id, "message": f"Started scraping {len(request.products)} products"}


async def run_batch_scrape(
    job_id: str,
    products: List[ScrapeRequest],
    update_products: bool
):
    """Background task to run batch scraping with R2 image upload"""
    job = scrape_jobs.get(job_id)
    if not job:
        return
    
    job.status = "running"
    db = get_db()
    
    try:
        products_data = [
            {
                "supplier_name": p.supplier_name,
                "sku": p.sku,
                "product_name": p.product_name or ""
            }
            for p in products
        ]
        
        results = await SupplierScraperFactory.scrape_products_batch(
            products_data,
            delay=1.5  # Rate limiting
        )
        
        for result in results:
            job.processed += 1
            
            if result.get("success"):
                job.successful += 1
                images = result.get("images", [])
                
                # Upload images to R2 cloud storage (use product name for image naming)
                if R2_AVAILABLE and process_product_images and images:
                    try:
                        # Use product name for R2 image naming, fallback to SKU
                        product_display_name = result.get("name") or result.get("sku", "product")
                        processed_images, uploaded_count = await process_product_images(
                            images,
                            result.get("supplier", "unknown"),
                            product_display_name  # Use display name, not SKU
                        )
                        result["images"] = processed_images
                        if uploaded_count > 0:
                            result["images_uploaded_to_r2"] = True
                            logger.debug(f"Uploaded {uploaded_count} images to R2 for {product_display_name}")
                    except Exception as e:
                        logger.warning(f"Failed to upload images to R2: {e}")
                
                # Update product in database if requested
                if update_products and result.get("images"):
                    await db.products.update_one(
                        {"sku": result.get("sku")},
                        {
                            "$set": {
                                "images": result.get("images"),
                                "scraped_at": datetime.now(timezone.utc).isoformat(),
                                "scraped_from": result.get("product_url"),
                                "images_uploaded_to_r2": result.get("images_uploaded_to_r2", False)
                            }
                        }
                    )
            else:
                job.failed += 1
            
            job.results.append(result)
        
        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        
    except Exception as e:
        job.status = "failed"
        job.completed_at = datetime.now(timezone.utc)
        job.results.append({"error": str(e)})


@router.get("/scraper/job/{job_id}")
async def get_scrape_job_status(
    job_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get the status of a background scrape job"""
    require_admin_access(current_user)
    
    job = scrape_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        "job_id": job.job_id,
        "status": job.status,
        "total": job.total,
        "processed": job.processed,
        "successful": job.successful,
        "failed": job.failed,
        "results": job.results[:20],  # Limit results in response
        "created_at": job.created_at.isoformat(),
        "completed_at": job.completed_at.isoformat() if job.completed_at else None
    }


@router.post("/scraper/scrape-by-supplier/{supplier_name}")
async def scrape_products_by_supplier(
    supplier_name: str,
    background_tasks: BackgroundTasks,
    limit: int = 50,
    current_user: dict = Depends(get_current_user)
):
    """
    Find all products from a supplier and scrape their images.
    Useful for bulk image updates.
    """
    require_admin_access(current_user)
    
    db = get_db()
    
    # Find products from this supplier that don't have images
    products = await db.products.find(
        {
            "supplier_name": {"$regex": supplier_name, "$options": "i"},
            "$or": [
                {"images": {"$exists": False}},
                {"images": {"$size": 0}}
            ]
        },
        {"sku": 1, "name": 1, "supplier_name": 1}
    ).limit(limit).to_list(limit)
    
    if not products:
        return {"message": "No products found without images for this supplier"}
    
    job_id = str(uuid.uuid4())
    
    scrape_jobs[job_id] = ScrapeJobStatus(
        job_id=job_id,
        status="pending",
        total=len(products),
        processed=0,
        successful=0,
        failed=0,
        results=[],
        created_at=datetime.now(timezone.utc)
    )
    
    scrape_requests = [
        ScrapeRequest(
            supplier_name=p.get("supplier_name", supplier_name),
            sku=p.get("sku", ""),
            product_name=p.get("name", "")
        )
        for p in products if p.get("sku")
    ]
    
    background_tasks.add_task(
        run_batch_scrape,
        job_id,
        scrape_requests,
        True  # Always update products
    )
    
    return {
        "job_id": job_id,
        "message": f"Started scraping {len(products)} products from {supplier_name}",
        "products_found": len(products)
    }


@router.get("/scraper/supported-suppliers")
async def get_supported_suppliers(current_user: dict = Depends(get_current_user)):
    """Get list of suppliers that support web scraping"""
    return {
        "suppliers": [
            {
                "name": "Tile Rite",
                "website": "https://www.tilerite.co.uk",
                "notes": "Product images scraped by SKU. Best results with exact product codes."
            },
            {
                "name": "Trimline",
                "website": "https://shop.trimlinegroup.com",
                "notes": "Shopify-based store. Products found via search."
            },
            {
                "name": "Ultra Tile",
                "website": "https://www.instarmac.co.uk/products/ultratile/",
                "notes": "Part of Instarmac. Products found via category browsing."
            }
        ]
    }


@router.post("/scraper/test/{supplier}")
async def test_scraper(
    supplier: str,
    sku: str = "BGL596",
    current_user: dict = Depends(get_current_user)
):
    """
    Test a scraper with a known product.
    Useful for debugging scraper functionality.
    """
    require_admin_access(current_user)
    
    # Test SKUs for each supplier
    test_skus = {
        "tilerite": ("BGL596", "12MM LSHAPE BRIGHT GOLD"),
        "trimline": ("atrim-10mm", "Atrim 10mm Straight Edge"),
        "ultratile": ("proflex", "ProFlex S2 Tile Adhesive")
    }
    
    supplier_lower = supplier.lower()
    test_sku, test_name = test_skus.get(supplier_lower, (sku, ""))
    
    result = await SupplierScraperFactory.scrape_product(
        supplier,
        test_sku,
        test_name
    )
    
    return {
        "test_sku": test_sku,
        "test_name": test_name,
        "result": result
    }


# SKU patterns to detect supplier
SKU_SUPPLIER_PATTERNS = {
    "TIL-": "Tile Rite",      # TIL-RHS973, TIL-TCS444
    "TIL": "Tile Rite",       # TILXXX format
    "TR-": "Trimline",        # TR-XXX format
    "TRIM": "Trimline",       # TRIMXXX format
    "UT-": "Ultra Tile",      # UT-XXX format
    "PRO": "Ultra Tile",      # ProFlex, ProGrout etc
}


def detect_supplier_from_sku(sku: str, product_name: str = "") -> str:
    """
    Detect supplier from SKU pattern or product name.
    Returns supplier name or None if not detected.
    """
    if not sku:
        return None
    
    sku_upper = sku.upper()
    name_lower = (product_name or "").lower()
    
    # Check SKU patterns
    for pattern, supplier in SKU_SUPPLIER_PATTERNS.items():
        if sku_upper.startswith(pattern):
            return supplier
    
    # Check product name for supplier hints
    if "tile rite" in name_lower or "tilerite" in name_lower:
        return "Tile Rite"
    if "trimline" in name_lower:
        return "Trimline"
    if "ultra" in name_lower or "instarmac" in name_lower:
        return "Ultra Tile"
    
    return None


@router.post("/scraper/scrape-all")
async def scrape_all_products_without_images(
    background_tasks: BackgroundTasks,
    limit: int = 100,
    current_user: dict = Depends(get_current_user)
):
    """
    Find all products without images and attempt to scrape them.
    Automatically detects supplier from SKU patterns.
    """
    require_admin_access(current_user)
    
    db = get_db()
    
    # Find products that don't have images
    products = await db.products.find(
        {
            "$or": [
                {"images": {"$exists": False}},
                {"images": {"$size": 0}},
                {"images": None}
            ]
        },
        {"sku": 1, "name": 1, "supplier_name": 1}
    ).limit(limit).to_list(limit)
    
    if not products:
        return {"message": "No products found without images"}
    
    # Group products by detected supplier
    scrapable_products = []
    skipped_products = []
    
    for product in products:
        sku = product.get("sku", "")
        name = product.get("name", "")
        supplier = product.get("supplier_name") or detect_supplier_from_sku(sku, name)
        
        if supplier and SupplierScraperFactory.get_scraper(supplier):
            scrapable_products.append({
                "sku": sku,
                "name": name,
                "supplier_name": supplier,
                "detected": not product.get("supplier_name")  # Was supplier auto-detected?
            })
        else:
            skipped_products.append({
                "sku": sku,
                "name": name,
                "reason": "Unknown or unsupported supplier"
            })
    
    if not scrapable_products:
        return {
            "message": "No products with supported suppliers found",
            "skipped": len(skipped_products),
            "skipped_samples": skipped_products[:10]
        }
    
    job_id = str(uuid.uuid4())
    
    scrape_jobs[job_id] = ScrapeJobStatus(
        job_id=job_id,
        status="pending",
        total=len(scrapable_products),
        processed=0,
        successful=0,
        failed=0,
        results=[],
        created_at=datetime.now(timezone.utc)
    )
    
    scrape_requests = [
        ScrapeRequest(
            supplier_name=p["supplier_name"],
            sku=p["sku"],
            product_name=p["name"]
        )
        for p in scrapable_products
    ]
    
    background_tasks.add_task(
        run_batch_scrape,
        job_id,
        scrape_requests,
        True  # Always update products
    )
    
    return {
        "job_id": job_id,
        "message": f"Started scraping {len(scrapable_products)} products",
        "products_to_scrape": len(scrapable_products),
        "products_skipped": len(skipped_products),
        "skipped_samples": skipped_products[:5] if skipped_products else []
    }


@router.get("/scraper/products-status")
async def get_scraper_products_status(current_user: dict = Depends(get_current_user)):
    """
    Get overview of products by image status and supplier.
    Useful for planning bulk scrapes.
    """
    require_admin_access(current_user)
    
    db = get_db()
    
    # Total products
    total = await db.products.count_documents({})
    
    # Products with images
    with_images = await db.products.count_documents({
        "images": {"$exists": True, "$not": {"$size": 0}, "$ne": None}
    })
    
    # Products without images
    without_images = total - with_images
    
    # Products by supplier (without images)
    pipeline = [
        {
            "$match": {
                "$or": [
                    {"images": {"$exists": False}},
                    {"images": {"$size": 0}},
                    {"images": None}
                ]
            }
        },
        {
            "$group": {
                "_id": "$supplier_name",
                "count": {"$sum": 1}
            }
        },
        {"$sort": {"count": -1}}
    ]
    by_supplier = await db.products.aggregate(pipeline).to_list(20)
    
    # Detect scrapable products from SKU patterns
    products_without_images = await db.products.find(
        {
            "$or": [
                {"images": {"$exists": False}},
                {"images": {"$size": 0}},
                {"images": None}
            ]
        },
        {"sku": 1, "name": 1, "supplier_name": 1}
    ).to_list(10000)
    
    # Count how many can be scraped
    scrapable_count = 0
    by_detected_supplier = {}
    
    for product in products_without_images:
        sku = product.get("sku", "")
        name = product.get("name", "")
        supplier = product.get("supplier_name") or detect_supplier_from_sku(sku, name)
        
        if supplier and SupplierScraperFactory.get_scraper(supplier):
            scrapable_count += 1
            by_detected_supplier[supplier] = by_detected_supplier.get(supplier, 0) + 1
    
    return {
        "total_products": total,
        "with_images": with_images,
        "without_images": without_images,
        "scrapable": scrapable_count,
        "not_scrapable": without_images - scrapable_count,
        "by_supplier": [{"supplier": s["_id"] or "Unknown", "count": s["count"]} for s in by_supplier],
        "scrapable_by_supplier": [{"supplier": k, "count": v} for k, v in sorted(by_detected_supplier.items(), key=lambda x: x[1], reverse=True)]
    }


class DownloadAndLinkRequest(BaseModel):
    """Request to download images and link to an existing product"""
    sku: str
    image_urls: List[str]
    product_id: Optional[str] = None  # If provided, link to specific product; otherwise find by SKU


@router.post("/scraper/download-and-link")
async def download_and_link_images(
    request: DownloadAndLinkRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Download scraped images to local storage and link them to an existing product.
    This allows importing images from suppliers into the system.
    """
    require_admin_access(current_user)
    
    db = get_db()
    
    if not request.image_urls:
        raise HTTPException(status_code=400, detail="No image URLs provided")
    
    # Find the product
    product = None
    if request.product_id:
        product = await db.products.find_one({"id": request.product_id})
    if not product:
        product = await db.products.find_one({"sku": request.sku})
    
    if not product:
        raise HTTPException(status_code=404, detail=f"Product not found with SKU: {request.sku}")
    
    # Download images
    downloaded_urls = []
    errors = []
    
    async with aiohttp.ClientSession() as session:
        for idx, url in enumerate(request.image_urls):
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        content = await response.read()
                        
                        # Determine file extension
                        content_type = response.headers.get('content-type', '')
                        if 'png' in content_type:
                            ext = '.png'
                        elif 'gif' in content_type:
                            ext = '.gif'
                        elif 'webp' in content_type:
                            ext = '.webp'
                        else:
                            ext = '.jpg'
                        
                        # Generate unique filename based on SKU
                        filename = f"{request.sku.replace('/', '-').replace(' ', '_')}_{idx + 1}_{uuid.uuid4().hex[:8]}{ext}"
                        file_path = UPLOAD_DIR / filename
                        
                        # Save file
                        with open(file_path, 'wb') as f:
                            f.write(content)
                        
                        # Build URL using environment variable
                        base_url = os.environ.get("BACKEND_URL", "")
                        if base_url:
                            image_url = f"{base_url}/uploads/{filename}"
                        else:
                            image_url = f"/uploads/{filename}"
                        
                        downloaded_urls.append(image_url)
                    else:
                        errors.append(f"Failed to download {url}: HTTP {response.status}")
            except asyncio.TimeoutError:
                errors.append(f"Timeout downloading {url}")
            except Exception as e:
                errors.append(f"Error downloading {url}: {str(e)}")
    
    if not downloaded_urls:
        raise HTTPException(status_code=500, detail=f"Failed to download any images. Errors: {'; '.join(errors)}")
    
    # Update product with new images
    existing_images = product.get("images", []) or []
    updated_images = existing_images + downloaded_urls
    
    await db.products.update_one(
        {"id": product["id"]},
        {
            "$set": {
                "images": updated_images,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
        }
    )
    
    return {
        "success": True,
        "message": f"Downloaded {len(downloaded_urls)} images and linked to product '{product.get('name', request.sku)}'",
        "product_id": product["id"],
        "product_sku": product.get("sku"),
        "product_name": product.get("name"),
        "downloaded_images": downloaded_urls,
        "total_images": len(updated_images),
        "errors": errors if errors else None
    }


@router.get("/scraper/find-product/{sku}")
async def find_product_by_sku(
    sku: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Find a product by SKU to verify it exists before downloading images.
    """
    require_admin_access(current_user)
    
    db = get_db()
    
    # Try exact match first
    product = await db.products.find_one({"sku": sku}, {"_id": 0, "id": 1, "sku": 1, "name": 1, "images": 1})
    
    if not product:
        # Try partial match
        product = await db.products.find_one(
            {"sku": {"$regex": sku, "$options": "i"}},
            {"_id": 0, "id": 1, "sku": 1, "name": 1, "images": 1}
        )
    
    if not product:
        return {
            "found": False,
            "message": f"No product found with SKU: {sku}"
        }
    
    return {
        "found": True,
        "product": {
            "id": product.get("id"),
            "sku": product.get("sku"),
            "name": product.get("name"),
            "existing_images": len(product.get("images", []) or [])
        }
    }


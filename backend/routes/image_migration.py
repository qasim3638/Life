"""
Image Migration Routes
Handles migration of supplier product images to Cloudflare R2 storage.
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime, timezone
import os
import asyncio
import aiohttp
import boto3
from botocore.config import Config
from pymongo import MongoClient
from PIL import Image
from io import BytesIO
from pathlib import Path
import logging
import hashlib

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/image-migration", tags=["Image Migration"])

# R2 Configuration
R2_ACCOUNT_ID = os.environ.get('R2_ACCOUNT_ID', '')
R2_ACCESS_KEY_ID = os.environ.get('R2_ACCESS_KEY_ID', '')
R2_SECRET_ACCESS_KEY = os.environ.get('R2_SECRET_ACCESS_KEY', '')
R2_BUCKET_NAME = os.environ.get('R2_BUCKET_NAME', 'tilestation-images')
R2_PUBLIC_URL = os.environ.get('R2_PUBLIC_URL', '')

# Migration state (in-memory for now, could be moved to Redis/DB)
migration_state = {
    "is_running": False,
    "should_stop": False,
    "current_supplier": None,
    "progress": {
        "total_products": 0,
        "processed_products": 0,
        "total_images": 0,
        "uploaded_images": 0,
        "failed_images": 0,
        "skipped_images": 0
    },
    "started_at": None,
    "errors": [],
    "last_updated": None
}

BATCH_SIZE = 10
MAX_RETRIES = 3
TIMEOUT_SECONDS = 30


class R2Client:
    """Singleton R2 client"""
    _instance = None
    
    @classmethod
    def get_client(cls):
        if cls._instance is None and all([R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY]):
            cls._instance = boto3.client(
                's3',
                endpoint_url=f'https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com',
                aws_access_key_id=R2_ACCESS_KEY_ID,
                aws_secret_access_key=R2_SECRET_ACCESS_KEY,
                config=Config(signature_version='s3v4', retries={'max_attempts': 3})
            )
        return cls._instance


def get_db():
    """Get sync MongoDB client"""
    mongo_url = os.environ.get('MONGO_URL')
    if not mongo_url:
        raise ValueError("MONGO_URL not configured")
    client = MongoClient(mongo_url)
    db_name = os.environ.get('DB_NAME', 'tile_station')
    return client, client[db_name]


def is_r2_url(url: str) -> bool:
    """Check if URL is already an R2/cloud URL"""
    if not url:
        return False
    cloud_patterns = [
        'r2.dev',
        'r2.cloudflarestorage.com',
        R2_PUBLIC_URL,
        'images.tilestation.co.uk',
        'cloudflare',
        'amazonaws.com',
        'blob.core.windows.net'
    ]
    return any(pattern in url.lower() for pattern in cloud_patterns if pattern)


def generate_r2_key(supplier: str, product_code: str, image_index: int, original_url: str) -> str:
    """Generate a unique key for R2 storage"""
    # Get file extension
    ext = Path(original_url.split('?')[0]).suffix.lower()
    if ext not in ['.jpg', '.jpeg', '.png', '.webp', '.gif']:
        ext = '.jpg'
    
    # Clean up product code for use in path
    clean_code = product_code.replace('/', '_').replace(' ', '_').replace('\\', '_')[:50]
    clean_supplier = supplier.lower().replace(' ', '_')
    
    # Add hash of original URL to ensure uniqueness
    url_hash = hashlib.md5(original_url.encode()).hexdigest()[:8]
    
    return f"products/{clean_supplier}/{clean_code}_{image_index}_{url_hash}{ext}"


async def download_image(session: aiohttp.ClientSession, url: str) -> Optional[bytes]:
    """Download image from URL with retry logic"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'image/*,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    
    for attempt in range(MAX_RETRIES):
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=TIMEOUT_SECONDS), headers=headers, ssl=False) as response:
                if response.status == 200:
                    return await response.read()
                logger.warning(f"HTTP {response.status} for {url}")
        except asyncio.TimeoutError:
            logger.warning(f"Timeout downloading {url} (attempt {attempt + 1})")
        except Exception as e:
            logger.warning(f"Error downloading {url}: {e} (attempt {attempt + 1})")
        
        if attempt < MAX_RETRIES - 1:
            await asyncio.sleep(1 * (attempt + 1))
    
    return None


def optimize_image(image_data: bytes, max_size: int = 1200) -> bytes:
    """Optimize image for web"""
    try:
        img = Image.open(BytesIO(image_data))
        
        # Convert to RGB if necessary
        if img.mode in ('RGBA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'RGBA':
                background.paste(img, mask=img.split()[3])
            else:
                background.paste(img)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Resize if too large
        if max(img.size) > max_size:
            ratio = max_size / max(img.size)
            new_size = tuple(int(dim * ratio) for dim in img.size)
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        
        output = BytesIO()
        img.save(output, format='JPEG', quality=85, optimize=True)
        return output.getvalue()
    except Exception as e:
        logger.warning(f"Failed to optimize image: {e}")
        return image_data


def upload_to_r2(image_data: bytes, key: str) -> Optional[str]:
    """Upload image to R2 and return public URL"""
    client = R2Client.get_client()
    if not client:
        logger.error("R2 client not configured")
        return None
    
    try:
        client.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=key,
            Body=image_data,
            ContentType='image/jpeg',
            CacheControl='public, max-age=31536000'
        )
        
        if R2_PUBLIC_URL:
            return f"{R2_PUBLIC_URL}/{key}"
        return f"https://{R2_BUCKET_NAME}.{R2_ACCOUNT_ID}.r2.dev/{key}"
    except Exception as e:
        logger.error(f"Failed to upload to R2: {e}")
        return None


async def migrate_supplier_images(supplier_name: str, collection_name: str = "supplier_products"):
    """Background task to migrate images for a supplier"""
    global migration_state
    
    migration_state["is_running"] = True
    migration_state["should_stop"] = False
    migration_state["current_supplier"] = supplier_name
    migration_state["started_at"] = datetime.now(timezone.utc).isoformat()
    migration_state["errors"] = []
    migration_state["progress"] = {
        "total_products": 0,
        "processed_products": 0,
        "total_images": 0,
        "uploaded_images": 0,
        "failed_images": 0,
        "skipped_images": 0
    }
    
    try:
        mongo_client, db = get_db()
        collection = db[collection_name]
        
        # Build query
        query = {"images": {"$exists": True, "$ne": []}}
        if supplier_name != "all":
            query["supplier_name"] = supplier_name
        
        # Get total count
        total_products = collection.count_documents(query)
        migration_state["progress"]["total_products"] = total_products
        
        logger.info(f"Starting migration for {supplier_name}: {total_products} products")
        
        # Process in batches
        processed = 0
        async with aiohttp.ClientSession() as session:
            cursor = collection.find(query, batch_size=BATCH_SIZE)
            
            for product in cursor:
                if migration_state["should_stop"]:
                    logger.info("Migration stopped by user")
                    break
                
                product_id = product.get("_id")
                product_code = product.get("supplier_code") or product.get("name") or str(product_id)
                supplier = product.get("supplier_name", "unknown")
                images = product.get("images", [])
                
                new_images = []
                for idx, url in enumerate(images):
                    if migration_state["should_stop"]:
                        break
                    
                    if not url or not isinstance(url, str):
                        continue
                    
                    # Skip if already migrated
                    if is_r2_url(url):
                        new_images.append(url)
                        migration_state["progress"]["skipped_images"] += 1
                        continue
                    
                    migration_state["progress"]["total_images"] += 1
                    
                    # Download image
                    image_data = await download_image(session, url)
                    
                    if image_data:
                        # Optimize
                        optimized = optimize_image(image_data)
                        
                        # Generate key and upload
                        key = generate_r2_key(supplier, product_code, idx, url)
                        r2_url = upload_to_r2(optimized, key)
                        
                        if r2_url:
                            new_images.append(r2_url)
                            migration_state["progress"]["uploaded_images"] += 1
                        else:
                            new_images.append(url)  # Keep original on failure
                            migration_state["progress"]["failed_images"] += 1
                            migration_state["errors"].append({
                                "product": product_code,
                                "url": url,
                                "error": "Upload failed"
                            })
                    else:
                        new_images.append(url)  # Keep original on failure
                        migration_state["progress"]["failed_images"] += 1
                        migration_state["errors"].append({
                            "product": product_code,
                            "url": url,
                            "error": "Download failed"
                        })
                
                # Update product with new image URLs
                if new_images:
                    collection.update_one(
                        {"_id": product_id},
                        {"$set": {
                            "images": new_images,
                            "images_migrated": True,
                            "images_migrated_at": datetime.now(timezone.utc)
                        }}
                    )
                
                processed += 1
                migration_state["progress"]["processed_products"] = processed
                migration_state["last_updated"] = datetime.now(timezone.utc).isoformat()
                
                # Small delay to avoid overwhelming external servers
                if processed % 10 == 0:
                    await asyncio.sleep(0.5)
        
        mongo_client.close()
        logger.info(f"Migration completed: {migration_state['progress']}")
        
    except Exception as e:
        logger.error(f"Migration error: {e}")
        migration_state["errors"].append({"error": str(e)})
    finally:
        migration_state["is_running"] = False
        migration_state["current_supplier"] = None
        migration_state["last_updated"] = datetime.now(timezone.utc).isoformat()


async def migrate_tiles_images():
    """Migrate images in the tiles collection (published products)"""
    global migration_state
    
    migration_state["is_running"] = True
    migration_state["should_stop"] = False
    migration_state["current_supplier"] = "tiles_collection"
    migration_state["started_at"] = datetime.now(timezone.utc).isoformat()
    migration_state["errors"] = []
    migration_state["progress"] = {
        "total_products": 0,
        "processed_products": 0,
        "total_images": 0,
        "uploaded_images": 0,
        "failed_images": 0,
        "skipped_images": 0
    }
    
    try:
        mongo_client, db = get_db()
        collection = db["tiles"]
        
        # Get products with external images
        total_products = collection.count_documents({"images": {"$exists": True, "$ne": []}})
        migration_state["progress"]["total_products"] = total_products
        
        logger.info(f"Starting tiles migration: {total_products} products")
        
        processed = 0
        async with aiohttp.ClientSession() as session:
            cursor = collection.find({"images": {"$exists": True, "$ne": []}}, batch_size=BATCH_SIZE)
            
            for product in cursor:
                if migration_state["should_stop"]:
                    logger.info("Migration stopped by user")
                    break
                
                product_id = product.get("_id")
                product_name = product.get("display_name") or product.get("name") or str(product_id)
                supplier = product.get("supplier", "tiles")
                images = product.get("images", [])
                
                new_images = []
                for idx, url in enumerate(images):
                    if migration_state["should_stop"]:
                        break
                    
                    if not url or not isinstance(url, str):
                        continue
                    
                    # Skip if already migrated
                    if is_r2_url(url):
                        new_images.append(url)
                        migration_state["progress"]["skipped_images"] += 1
                        continue
                    
                    migration_state["progress"]["total_images"] += 1
                    
                    # Download image
                    image_data = await download_image(session, url)
                    
                    if image_data:
                        optimized = optimize_image(image_data)
                        key = generate_r2_key(supplier or "tiles", product_name, idx, url)
                        r2_url = upload_to_r2(optimized, key)
                        
                        if r2_url:
                            new_images.append(r2_url)
                            migration_state["progress"]["uploaded_images"] += 1
                        else:
                            new_images.append(url)
                            migration_state["progress"]["failed_images"] += 1
                    else:
                        new_images.append(url)
                        migration_state["progress"]["failed_images"] += 1
                
                if new_images:
                    collection.update_one(
                        {"_id": product_id},
                        {"$set": {
                            "images": new_images,
                            "images_migrated": True,
                            "images_migrated_at": datetime.now(timezone.utc)
                        }}
                    )
                
                processed += 1
                migration_state["progress"]["processed_products"] = processed
                migration_state["last_updated"] = datetime.now(timezone.utc).isoformat()
                
                if processed % 10 == 0:
                    await asyncio.sleep(0.5)
        
        mongo_client.close()
        logger.info(f"Tiles migration completed: {migration_state['progress']}")
        
    except Exception as e:
        logger.error(f"Tiles migration error: {e}")
        migration_state["errors"].append({"error": str(e)})
    finally:
        migration_state["is_running"] = False
        migration_state["current_supplier"] = None
        migration_state["last_updated"] = datetime.now(timezone.utc).isoformat()


# API Routes

@router.get("/status")
async def get_migration_status():
    """Get current migration status"""
    return {
        "is_running": migration_state["is_running"],
        "current_supplier": migration_state["current_supplier"],
        "progress": migration_state["progress"],
        "started_at": migration_state["started_at"],
        "last_updated": migration_state["last_updated"],
        "recent_errors": migration_state["errors"][-10:] if migration_state["errors"] else []
    }


@router.get("/config")
async def get_r2_config():
    """Check R2 configuration status"""
    is_configured = all([R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY])
    return {
        "is_configured": is_configured,
        "bucket_name": R2_BUCKET_NAME if is_configured else None,
        "public_url": R2_PUBLIC_URL if is_configured else None,
        "missing": [] if is_configured else [
            k for k, v in [
                ("R2_ACCOUNT_ID", R2_ACCOUNT_ID),
                ("R2_ACCESS_KEY_ID", R2_ACCESS_KEY_ID),
                ("R2_SECRET_ACCESS_KEY", R2_SECRET_ACCESS_KEY)
            ] if not v
        ]
    }


@router.get("/suppliers")
async def get_suppliers_for_migration():
    """Get list of suppliers with image counts"""
    try:
        mongo_client, db = get_db()
        
        # Get supplier stats
        pipeline = [
            {"$match": {"images": {"$exists": True, "$ne": []}}},
            {"$group": {
                "_id": "$supplier_name",
                "product_count": {"$sum": 1},
                "image_count": {"$sum": {"$size": "$images"}}
            }},
            {"$sort": {"product_count": -1}}
        ]
        
        suppliers = list(db.supplier_products.aggregate(pipeline))
        
        # Check migration status for each
        result = []
        for s in suppliers:
            migrated_count = db.supplier_products.count_documents({
                "supplier_name": s["_id"],
                "images_migrated": True
            })
            result.append({
                "supplier_name": s["_id"],
                "product_count": s["product_count"],
                "image_count": s["image_count"],
                "migrated_count": migrated_count,
                "pending_count": s["product_count"] - migrated_count
            })
        
        # Also check tiles collection
        tiles_total = db.tiles.count_documents({"images": {"$exists": True, "$ne": []}})
        tiles_migrated = db.tiles.count_documents({"images_migrated": True})
        
        mongo_client.close()
        
        return {
            "suppliers": result,
            "tiles_collection": {
                "total": tiles_total,
                "migrated": tiles_migrated,
                "pending": tiles_total - tiles_migrated
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class MigrationRequest(BaseModel):
    supplier_name: str = "all"
    collection: str = "supplier_products"


@router.post("/start")
async def start_migration(request: MigrationRequest, background_tasks: BackgroundTasks):
    """Start image migration for a supplier"""
    global migration_state
    
    if migration_state["is_running"]:
        raise HTTPException(status_code=400, detail="Migration already in progress")
    
    # Check R2 config
    if not all([R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY]):
        raise HTTPException(status_code=400, detail="R2 storage not configured")
    
    if request.collection == "tiles":
        background_tasks.add_task(migrate_tiles_images)
    else:
        background_tasks.add_task(migrate_supplier_images, request.supplier_name, request.collection)
    
    return {
        "message": f"Migration started for {request.supplier_name}",
        "collection": request.collection
    }


@router.post("/stop")
async def stop_migration():
    """Stop the current migration"""
    global migration_state
    
    if not migration_state["is_running"]:
        return {"message": "No migration in progress"}
    
    migration_state["should_stop"] = True
    return {"message": "Stop signal sent. Migration will stop after current batch."}


@router.post("/reset")
async def reset_migration_flags(supplier_name: str = "all"):
    """Reset migration flags to allow re-migration"""
    try:
        mongo_client, db = get_db()
        
        query = {}
        if supplier_name != "all":
            query["supplier_name"] = supplier_name
        
        result = db.supplier_products.update_many(
            query,
            {"$unset": {"images_migrated": "", "images_migrated_at": ""}}
        )
        
        mongo_client.close()
        
        return {
            "message": f"Reset migration flags for {supplier_name}",
            "modified_count": result.modified_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

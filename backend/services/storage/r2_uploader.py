"""
Centralized R2 Image Upload Service
====================================
This module provides automatic image upload to Cloudflare R2 for all sync services.
When products are synced from any source (server-side sync, browser extension, single URL),
images are automatically downloaded and uploaded to R2 cloud storage.

Image naming uses product DISPLAY names (not supplier product names) for better organization.
"""
import asyncio
import aiohttp
import boto3
from botocore.config import Config
import os
import re
import hashlib
import logging
from typing import List, Optional, Tuple
from pathlib import Path
from PIL import Image
from io import BytesIO

logger = logging.getLogger(__name__)

# Settings
MAX_RETRIES = 3
TIMEOUT_SECONDS = 30
MAX_IMAGE_SIZE = 1200  # Max dimension in pixels


def get_r2_config():
    """Get R2 configuration from environment variables (always fresh)"""
    return {
        'account_id': os.environ.get('R2_ACCOUNT_ID', ''),
        'access_key_id': os.environ.get('R2_ACCESS_KEY_ID', ''),
        'secret_access_key': os.environ.get('R2_SECRET_ACCESS_KEY', ''),
        'bucket_name': os.environ.get('R2_BUCKET_NAME', 'tilestation-images'),
        'public_url': os.environ.get('R2_PUBLIC_URL', '')
    }


class R2ImageUploader:
    """Singleton class for R2 image uploads"""
    _client = None
    
    @classmethod
    def get_client(cls):
        """Get or create S3 client for R2"""
        config = get_r2_config()
        if cls._client is None and cls.is_configured():
            cls._client = boto3.client(
                's3',
                endpoint_url=f"https://{config['account_id']}.r2.cloudflarestorage.com",
                aws_access_key_id=config['access_key_id'],
                aws_secret_access_key=config['secret_access_key'],
                config=Config(signature_version='s3v4', retries={'max_attempts': 3})
            )
        return cls._client
    
    @classmethod
    def is_configured(cls) -> bool:
        """Check if R2 is properly configured (checks fresh each time)"""
        config = get_r2_config()
        return all([config['account_id'], config['access_key_id'], config['secret_access_key']])
    
    @classmethod
    def get_public_url(cls) -> str:
        """Get the public URL base for R2 images"""
        config = get_r2_config()
        if config['public_url']:
            return config['public_url']
        return f"https://{config['bucket_name']}.{config['account_id']}.r2.dev"
    
    @classmethod
    def get_bucket_name(cls) -> str:
        """Get the R2 bucket name"""
        return get_r2_config()['bucket_name']


def is_already_cloud_url(url: str) -> bool:
    """Check if URL is already a cloud storage URL (R2, S3, etc.)"""
    if not url:
        return True  # Treat empty as "already processed"
    
    cloud_patterns = [
        'r2.dev',
        'r2.cloudflarestorage.com',
        'images.tilestation.co.uk',
        'cloudflare',
        'amazonaws.com',
        's3.',
        'blob.core.windows.net',
        'storage.googleapis.com'
    ]
    url_lower = url.lower()
    return any(pattern in url_lower for pattern in cloud_patterns)


def generate_image_key(supplier: str, product_name: str, image_index: int, original_url: str) -> str:
    """
    Generate a unique key for storing the image in R2.
    Uses product display name (not supplier product name) for better organization.
    The URL hash ensures unique filenames and handles image updates.
    """
    # Get file extension from original URL
    ext = Path(original_url.split('?')[0]).suffix.lower()
    if ext not in ['.jpg', '.jpeg', '.png', '.webp', '.gif']:
        ext = '.jpg'
    
    # Clean up identifiers - use product display name
    clean_supplier = supplier.lower().replace(' ', '_').replace('/', '_')[:30] if supplier else 'unknown'
    
    # Clean product name - remove special characters, keep it readable
    clean_product = product_name if product_name else 'product'
    clean_product = re.sub(r'[^\w\s-]', '', clean_product)  # Remove special chars except dash
    clean_product = re.sub(r'\s+', '_', clean_product.strip())  # Replace spaces with underscores
    clean_product = clean_product[:60]  # Limit length
    
    # Add hash of original URL for uniqueness (handles image updates)
    url_hash = hashlib.md5(original_url.encode()).hexdigest()[:8]
    
    return f"products/{clean_supplier}/{clean_product}_{image_index}_{url_hash}{ext}"


def check_image_needs_update(current_r2_url: str, new_source_url: str, stored_source_urls: List[str] = None) -> bool:
    """
    Check if an image needs to be re-uploaded to R2.
    
    Returns True if:
    - Current image is not an R2 URL (needs initial upload)
    - Source URL has changed since last sync (supplier updated the image)
    """
    # If current image is not from R2, it needs upload
    if not is_already_cloud_url(current_r2_url):
        return True
    
    # If we have stored source URLs, check if the new source is different
    if stored_source_urls:
        # New source URL not in stored sources = image changed
        if new_source_url and new_source_url not in stored_source_urls:
            return True
    
    return False


def optimize_image(image_data: bytes, max_size: int = MAX_IMAGE_SIZE) -> bytes:
    """Optimize image for web - resize and compress"""
    try:
        img = Image.open(BytesIO(image_data))
        
        # Convert to RGB if necessary (handles RGBA, P mode)
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
        
        # Save with compression
        output = BytesIO()
        img.save(output, format='JPEG', quality=85, optimize=True)
        return output.getvalue()
    except Exception as e:
        logger.warning(f"Failed to optimize image: {e}")
        return image_data


async def download_image(url: str, session: aiohttp.ClientSession = None) -> Optional[bytes]:
    """Download image from URL with retry logic"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'image/*,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    
    close_session = False
    if session is None:
        session = aiohttp.ClientSession()
        close_session = True
    
    try:
        for attempt in range(MAX_RETRIES):
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=TIMEOUT_SECONDS), headers=headers, ssl=False) as response:
                    if response.status == 200:
                        return await response.read()
                    logger.warning(f"HTTP {response.status} downloading {url}")
            except asyncio.TimeoutError:
                logger.warning(f"Timeout downloading {url} (attempt {attempt + 1})")
            except Exception as e:
                logger.warning(f"Error downloading {url}: {e} (attempt {attempt + 1})")
            
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(1 * (attempt + 1))
        
        return None
    finally:
        if close_session:
            await session.close()


def upload_to_r2(image_data: bytes, key: str) -> Optional[str]:
    """Upload image to R2 and return public URL"""
    client = R2ImageUploader.get_client()
    if not client:
        logger.error("R2 client not configured")
        return None
    
    try:
        bucket_name = R2ImageUploader.get_bucket_name()
        client.put_object(
            Bucket=bucket_name,
            Key=key,
            Body=image_data,
            ContentType='image/jpeg',
            CacheControl='public, max-age=31536000'  # Cache for 1 year
        )
        
        return f"{R2ImageUploader.get_public_url()}/{key}"
    except Exception as e:
        logger.error(f"Failed to upload to R2: {e}")
        return None


async def process_single_image(
    url: str, 
    supplier: str, 
    product_identifier: str, 
    image_index: int,
    session: aiohttp.ClientSession = None
) -> Tuple[str, bool]:
    """
    Process a single image: download, optimize, upload to R2.
    
    Args:
        url: Original image URL
        supplier: Supplier name
        product_identifier: SKU or product name
        image_index: Index for multiple images
        session: Optional aiohttp session for reuse
    
    Returns:
        Tuple of (final_url, was_uploaded)
        - If R2 not configured or upload fails, returns original URL
        - If already a cloud URL, returns original URL
    """
    # Skip if already a cloud URL
    if is_already_cloud_url(url):
        return url, False
    
    # Skip if R2 not configured
    if not R2ImageUploader.is_configured():
        logger.debug("R2 not configured, keeping original URL")
        return url, False
    
    # Download image
    image_data = await download_image(url, session)
    if not image_data:
        logger.warning(f"Failed to download image: {url}")
        return url, False
    
    # Optimize image
    optimized_data = optimize_image(image_data)
    
    # Generate R2 key
    key = generate_image_key(supplier, product_identifier, image_index, url)
    
    # Upload to R2
    r2_url = upload_to_r2(optimized_data, key)
    
    if r2_url:
        logger.debug(f"Uploaded to R2: {url} -> {r2_url}")
        return r2_url, True
    
    return url, False


async def process_product_images(
    images: List[str],
    supplier: str,
    product_identifier: str,
    session: aiohttp.ClientSession = None,
    force_update: bool = False,
    existing_source_urls: List[str] = None
) -> Tuple[List[str], int, List[str]]:
    """
    Process all images for a product.
    
    Args:
        images: List of image URLs (source URLs from supplier)
        supplier: Supplier name
        product_identifier: Product display name
        session: Optional aiohttp session for reuse
        force_update: If True, re-upload all images even if already in R2
        existing_source_urls: Previously stored source URLs to detect changes
    
    Returns:
        Tuple of (processed_image_urls, count_uploaded, source_urls)
        - processed_image_urls: List of R2 URLs (or original on failure)
        - count_uploaded: Number of images uploaded this run
        - source_urls: Original source URLs for storage (for future change detection)
    """
    if not images:
        return [], 0, []
    
    processed_images = []
    uploaded_count = 0
    source_urls = []  # Track original URLs for change detection
    
    close_session = False
    if session is None:
        session = aiohttp.ClientSession()
        close_session = True
    
    try:
        for idx, url in enumerate(images):
            if not url:
                continue
                
            # Track source URL
            source_urls.append(url)
            
            # Check if this is already a cloud URL
            if is_already_cloud_url(url):
                # Already uploaded - check if source changed
                if existing_source_urls and idx < len(existing_source_urls):
                    stored_source = existing_source_urls[idx]
                    if stored_source and stored_source != url:
                        # Source URL changed! This shouldn't happen if URL is R2
                        # This means the product's images array already has R2 URLs
                        processed_images.append(url)
                        continue
                
                if not force_update:
                    processed_images.append(url)
                    continue
            
            # Check if image needs update (source URL changed)
            needs_upload = True
            if existing_source_urls and idx < len(existing_source_urls):
                stored_source = existing_source_urls[idx]
                # If source URL is the same, skip re-upload (already in R2)
                if stored_source == url and not force_update:
                    # Find existing R2 URL - generate the same key
                    key = generate_image_key(supplier, product_identifier, idx, url)
                    existing_r2_url = f"{R2ImageUploader.get_public_url()}/{key}"
                    processed_images.append(existing_r2_url)
                    needs_upload = False
            
            if needs_upload:
                new_url, was_uploaded = await process_single_image(
                    url, supplier, product_identifier, idx, session
                )
                processed_images.append(new_url)
                if was_uploaded:
                    uploaded_count += 1
                    
    finally:
        if close_session:
            await session.close()
    
    return processed_images, uploaded_count, source_urls


async def process_product_images_for_deep_sync(
    new_source_images: List[str],
    supplier: str,
    product_name: str,
    existing_product: dict = None,
    session: aiohttp.ClientSession = None
) -> Tuple[List[str], int, List[str]]:
    """
    Process images during a deep sync, handling updates properly.
    
    This function:
    1. Compares new source URLs with stored source URLs
    2. Only uploads images that have changed
    3. Keeps existing R2 URLs for unchanged images
    4. Returns both R2 URLs and source URLs for storage
    
    Args:
        new_source_images: New image URLs from supplier
        supplier: Supplier name
        product_name: Product display name
        existing_product: Existing product data from DB (optional)
        session: aiohttp session for reuse
    
    Returns:
        Tuple of (r2_urls, uploaded_count, source_urls_to_store)
    """
    if not new_source_images:
        return [], 0, []
    
    # Get existing source URLs if available
    existing_source_urls = []
    existing_r2_urls = []
    if existing_product:
        existing_source_urls = existing_product.get('image_source_urls', [])
        existing_r2_urls = existing_product.get('images', [])
    
    processed_images = []
    uploaded_count = 0
    source_urls = []
    
    close_session = False
    if session is None:
        session = aiohttp.ClientSession()
        close_session = True
    
    try:
        for idx, source_url in enumerate(new_source_images):
            if not source_url:
                continue
            
            source_urls.append(source_url)
            
            # Check if source URL has changed
            image_changed = True
            if idx < len(existing_source_urls):
                if existing_source_urls[idx] == source_url:
                    image_changed = False
                    # Use existing R2 URL if available
                    if idx < len(existing_r2_urls) and is_already_cloud_url(existing_r2_urls[idx]):
                        processed_images.append(existing_r2_urls[idx])
                        logger.debug(f"Image unchanged, keeping existing R2 URL for {product_name}")
                        continue
            
            # New or changed image - upload to R2
            new_url, was_uploaded = await process_single_image(
                source_url, supplier, product_name, idx, session
            )
            processed_images.append(new_url)
            if was_uploaded:
                uploaded_count += 1
                if image_changed and idx < len(existing_source_urls):
                    logger.info(f"Image updated for {product_name}: {existing_source_urls[idx][:50]} -> {source_url[:50]}")
                    
    finally:
        if close_session:
            await session.close()
    
    return processed_images, uploaded_count, source_urls


def process_product_images_sync(
    images: List[str],
    supplier: str,
    product_identifier: str,
    existing_source_urls: List[str] = None
) -> Tuple[List[str], List[str]]:
    """
    Synchronous wrapper for process_product_images.
    Use this in sync contexts (non-async functions).
    
    Returns:
        Tuple of (processed_image_urls, source_urls)
    """
    if not images:
        return [], []
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        processed, _, source_urls = loop.run_until_complete(
            process_product_images(images, supplier, product_identifier, existing_source_urls=existing_source_urls)
        )
        loop.close()
        return processed, source_urls
    except Exception as e:
        logger.error(f"Error processing images synchronously: {e}")
        return images, images  # Return originals on failure


# Convenience function for single product sync
async def upload_product_images_to_r2(
    product_data: dict,
    supplier_field: str = 'supplier',
    identifier_field: str = 'sku',
    images_field: str = 'images'
) -> dict:
    """
    Process a product dict and upload its images to R2.
    Modifies the product_data in place and returns it.
    
    Args:
        product_data: Product dictionary with images
        supplier_field: Key name for supplier in product_data
        identifier_field: Key name for product identifier (SKU/name)
        images_field: Key name for images list
    
    Returns:
        Modified product_data with R2 URLs
    """
    images = product_data.get(images_field, [])
    if not images:
        return product_data
    
    supplier = product_data.get(supplier_field, 'unknown')
    identifier = product_data.get(identifier_field) or product_data.get('name', 'product')
    
    processed_images, uploaded = await process_product_images(images, supplier, identifier)
    
    product_data[images_field] = processed_images
    
    if uploaded > 0:
        product_data['images_uploaded_to_r2'] = True
        logger.info(f"Uploaded {uploaded} images to R2 for {identifier}")
    
    return product_data

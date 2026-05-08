#!/usr/bin/env python3
"""
Run image download to R2 with progress logging.
Designed to run in background and resume if interrupted.
"""
import asyncio
import sys
import os
import logging
from datetime import datetime

# Add backend to path
sys.path.insert(0, '/app/backend')
os.chdir('/app/backend')

# Load environment manually
env_file = '/app/backend/.env'
if os.path.exists(env_file):
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                # Remove quotes
                value = value.strip('"').strip("'")
                os.environ[key] = value

# Set up logging
log_dir = '/app/image_download_logs'
os.makedirs(log_dir, exist_ok=True)
log_file = f'{log_dir}/download_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

async def main():
    logger.info("=" * 60)
    logger.info("STARTING IMAGE DOWNLOAD TO CLOUDFLARE R2")
    logger.info("=" * 60)
    
    from services.storage.r2_image_service import ImageDownloadService
    
    service = ImageDownloadService()
    
    # Check if R2 is configured
    if not service.r2.is_configured():
        logger.error("R2 is not configured! Check environment variables.")
        return
    
    logger.info("R2 connection verified")
    
    # Start download
    result = await service.download_all_images()
    
    logger.info("=" * 60)
    logger.info(f"DOWNLOAD COMPLETE")
    logger.info(f"Result: {result}")
    logger.info("=" * 60)
    
    return result

if __name__ == "__main__":
    asyncio.run(main())

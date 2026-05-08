"""
Object Storage Service - R2/Emergent Storage
Handles file uploads and downloads via Emergent's object storage API.
"""
import os
import logging
import requests

logger = logging.getLogger(__name__)

STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
APP_NAME = "tile-station"

storage_key = None


def _get_emergent_key():
    """Get EMERGENT_LLM_KEY at call time (not import time) so it works even if set after startup."""
    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        raise ValueError(
            "EMERGENT_LLM_KEY environment variable is not set. "
            "Add it to your Railway production environment variables. "
            "You can find the key in your Emergent profile under Universal Key."
        )
    return key


def init_storage(force=False):
    """Initialize storage - call once at startup. Returns reusable storage_key."""
    global storage_key
    if storage_key and not force:
        return storage_key
    emergent_key = _get_emergent_key()
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": emergent_key}, timeout=30)
    resp.raise_for_status()
    storage_key = resp.json()["storage_key"]
    logger.info("Object storage initialized successfully")
    return storage_key


def put_object(path: str, data: bytes, content_type: str) -> dict:
    """Upload file to storage with retry on auth failure."""
    for attempt in range(2):
        key = init_storage(force=(attempt > 0))
        try:
            resp = requests.put(
                f"{STORAGE_URL}/objects/{path}",
                headers={"X-Storage-Key": key, "Content-Type": content_type},
                data=data,
                timeout=120,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError:
            if attempt == 0 and resp.status_code in (401, 403):
                logger.warning("Storage auth failed, re-initializing key...")
                continue
            raise
    raise Exception("Storage upload failed after retries")


def get_object(path: str) -> tuple:
    """Download file from storage with retry. Returns (content_bytes, content_type)."""
    for attempt in range(2):
        key = init_storage(force=(attempt > 0))
        try:
            resp = requests.get(
                f"{STORAGE_URL}/objects/{path}",
                headers={"X-Storage-Key": key},
                timeout=60,
            )
            resp.raise_for_status()
            return resp.content, resp.headers.get("Content-Type", "application/octet-stream")
        except requests.exceptions.HTTPError:
            if attempt == 0 and resp.status_code in (401, 403):
                logger.warning("Storage download auth failed, re-initializing key...")
                continue
            raise
    raise Exception("Storage download failed after retries")


MIME_TYPES = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
    "gif": "image/gif", "webp": "image/webp", "svg": "image/svg+xml",
    "pdf": "application/pdf",
    "mp4": "video/mp4", "webm": "video/webm", "mov": "video/quicktime",
    "avi": "video/x-msvideo", "mkv": "video/x-matroska",
}

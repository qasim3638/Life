"""
Redis Caching Utility
Provides caching for frequently accessed data to improve performance.
Falls back to in-memory cache if Redis is not available.
"""
import os
import json
import logging
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, Any, Callable
from functools import wraps
import asyncio

# Try to import Redis
try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    aioredis = None

# Configuration
REDIS_URL = os.environ.get("REDIS_URL")
CACHE_ENABLED = os.environ.get("CACHE_ENABLED", "true").lower() == "true"
DEFAULT_TTL = 300  # 5 minutes default

# In-memory fallback cache
_memory_cache = {}
_memory_cache_expiry = {}

# Redis client singleton
_redis_client = None

async def get_redis_client():
    """Get or create Redis client"""
    global _redis_client
    
    if not REDIS_AVAILABLE or not REDIS_URL:
        return None
    
    if _redis_client is None:
        try:
            _redis_client = aioredis.from_url(
                REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5
            )
            # Test connection
            await _redis_client.ping()
            logging.info("Redis connection established")
        except Exception as e:
            logging.warning(f"Redis connection failed, using in-memory cache: {e}")
            _redis_client = None
    
    return _redis_client


def generate_cache_key(*args, **kwargs) -> str:
    """Generate a cache key from arguments"""
    key_parts = [str(arg) for arg in args]
    key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
    key_string = ":".join(key_parts)
    return hashlib.md5(key_string.encode()).hexdigest()


async def cache_get(key: str) -> Optional[Any]:
    """Get value from cache"""
    if not CACHE_ENABLED:
        return None
    
    redis_client = await get_redis_client()
    
    if redis_client:
        try:
            value = await redis_client.get(f"tilestation:{key}")
            if value:
                return json.loads(value)
        except Exception as e:
            logging.warning(f"Redis get failed: {e}")
    
    # Fallback to memory cache
    if key in _memory_cache:
        expiry = _memory_cache_expiry.get(key)
        if expiry and datetime.now(timezone.utc) < expiry:
            return _memory_cache[key]
        else:
            # Expired
            _memory_cache.pop(key, None)
            _memory_cache_expiry.pop(key, None)
    
    return None


async def cache_set(key: str, value: Any, ttl: int = DEFAULT_TTL) -> bool:
    """Set value in cache"""
    if not CACHE_ENABLED:
        return False
    
    redis_client = await get_redis_client()
    
    if redis_client:
        try:
            await redis_client.setex(
                f"tilestation:{key}",
                ttl,
                json.dumps(value, default=str)
            )
            return True
        except Exception as e:
            logging.warning(f"Redis set failed: {e}")
    
    # Fallback to memory cache
    _memory_cache[key] = value
    _memory_cache_expiry[key] = datetime.now(timezone.utc) + timedelta(seconds=ttl)
    
    # Clean up old entries (keep max 1000)
    if len(_memory_cache) > 1000:
        # Remove oldest entries
        sorted_keys = sorted(_memory_cache_expiry.keys(), key=lambda k: _memory_cache_expiry[k])
        for old_key in sorted_keys[:100]:
            _memory_cache.pop(old_key, None)
            _memory_cache_expiry.pop(old_key, None)
    
    return True


async def cache_delete(key: str) -> bool:
    """Delete value from cache"""
    redis_client = await get_redis_client()
    
    if redis_client:
        try:
            await redis_client.delete(f"tilestation:{key}")
        except Exception as e:
            logging.warning(f"Redis delete failed: {e}")
    
    _memory_cache.pop(key, None)
    _memory_cache_expiry.pop(key, None)
    
    return True


async def cache_clear_pattern(pattern: str) -> int:
    """Clear all cache keys matching pattern"""
    count = 0
    redis_client = await get_redis_client()
    
    if redis_client:
        try:
            keys = await redis_client.keys(f"tilestation:{pattern}")
            if keys:
                count = await redis_client.delete(*keys)
        except Exception as e:
            logging.warning(f"Redis clear pattern failed: {e}")
    
    # Also clear from memory cache
    keys_to_delete = [k for k in _memory_cache.keys() if pattern.replace("*", "") in k]
    for key in keys_to_delete:
        _memory_cache.pop(key, None)
        _memory_cache_expiry.pop(key, None)
        count += 1
    
    return count


def cached(ttl: int = DEFAULT_TTL, key_prefix: str = ""):
    """Decorator to cache function results"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            func_name = func.__name__
            cache_key = f"{key_prefix}{func_name}:{generate_cache_key(*args, **kwargs)}"
            
            # Try to get from cache
            cached_value = await cache_get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # Call function
            result = await func(*args, **kwargs)
            
            # Cache result
            await cache_set(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator


async def get_cache_stats() -> dict:
    """Get cache statistics"""
    redis_client = await get_redis_client()
    
    stats = {
        "cache_enabled": CACHE_ENABLED,
        "redis_available": REDIS_AVAILABLE,
        "redis_connected": redis_client is not None,
        "memory_cache_size": len(_memory_cache)
    }
    
    if redis_client:
        try:
            info = await redis_client.info("memory")
            stats["redis_used_memory"] = info.get("used_memory_human")
            stats["redis_keys"] = await redis_client.dbsize()
        except Exception:
            pass
    
    return stats


# Cache key prefixes for different data types
class CacheKeys:
    PRODUCTS = "products:"
    PRODUCT_DETAIL = "product:"
    CATEGORIES = "categories"
    SHOWROOMS = "showrooms"
    ANALYTICS = "analytics:"
    RECOMMENDATIONS = "recommendations:"
    REVIEWS = "reviews:"
    STOCK = "stock:"
    
    @staticmethod
    def product_list(category: str = None, page: int = 1) -> str:
        return f"{CacheKeys.PRODUCTS}list:{category or 'all'}:page{page}"
    
    @staticmethod
    def product_detail(product_id: str) -> str:
        return f"{CacheKeys.PRODUCT_DETAIL}{product_id}"
    
    @staticmethod
    def analytics(report_type: str, period: str) -> str:
        return f"{CacheKeys.ANALYTICS}{report_type}:{period}"
    
    @staticmethod
    def recommendations(product_id: str) -> str:
        return f"{CacheKeys.RECOMMENDATIONS}{product_id}"


# Utility to invalidate related caches when data changes
async def invalidate_product_caches(product_id: str = None):
    """Invalidate all product-related caches"""
    await cache_clear_pattern(f"{CacheKeys.PRODUCTS}*")
    if product_id:
        await cache_delete(CacheKeys.product_detail(product_id))
        await cache_delete(CacheKeys.recommendations(product_id))


async def invalidate_analytics_caches():
    """Invalidate analytics caches"""
    await cache_clear_pattern(f"{CacheKeys.ANALYTICS}*")

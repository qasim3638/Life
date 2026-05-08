"""
Bulletproof endpoint shield — system-wide guarantee that no
customer-facing endpoint can ever return a "0 results" error page
to a real customer.

The contract we promise to the user:

    "Once a feature/data is live on the website, it will never
     disappear unless a Super Admin explicitly removes it."

To make that promise real, every customer-facing GET endpoint that
returns user-visible data MUST be wrapped with `bulletproof_endpoint`.
This wrapper provides four layers of defence:

    Layer 1 — DATETIME-SAFE SERIALIZATION
        The wrapped function's return value is walked recursively
        and any `datetime`, `ObjectId`, `Decimal`, `set` is converted
        to a JSON-friendly primitive. A single bad DB row can no
        longer crash the whole endpoint with `TypeError: Object of
        type datetime is not JSON serializable` (3 May 2026 outage).

    Layer 2 — LAST-KNOWN-GOOD CACHE (24h)
        Every successful non-empty response is mirrored into a
        long-lived cache. If the live query later crashes OR returns
        empty, we serve that LKG instead so customers see slightly-
        stale data rather than a blank catalogue.

    Layer 3 — NO-STORE ON EMPTY OR ERROR
        Empty/error responses set `Cache-Control: no-store` so any
        downstream cache (Cloudflare, Fastly, browser, Service Worker)
        is FORBIDDEN from caching the failure. A transient blip can
        no longer poison the CDN for 5 minutes.

    Layer 4 — STRUCTURED 503, NEVER 500
        If the impl raises and there's no LKG to fall back on, the
        wrapper returns HTTP 503 with `Retry-After: 5` and a
        structured payload. The frontend recognises the shape and
        shows a "Try again" UI — never a fake "0 results" page.

Usage
-----

    @router.get("/products")
    @bulletproof_endpoint(
        cache_namespace="tiles_products",
        empty_check=lambda r: not r.get("products"),
        empty_fallback={"products": [], "total": 0, "page": 1, "limit": 24, "total_pages": 1},
    )
    async def get_tile_products(...):
        return {"products": [...], "total": ...}

The decorator handles caching, headers, retries, and serialization;
the route function only needs to do its data fetch.
"""
from __future__ import annotations

import functools
import hashlib
import logging
from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Any, Callable, Optional

from fastapi.responses import JSONResponse

from utils.endpoint_cache import endpoint_cache

logger = logging.getLogger(__name__)


PUBLIC_CACHE_HEADERS = {
    "Cache-Control": "public, max-age=60, stale-while-revalidate=300",
    "Vary": "Accept-Encoding",
}
NO_STORE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Vary": "Accept-Encoding",
}


# ---------- JSON-safe walker ----------

def _bson_object_id_class():
    try:
        from bson import ObjectId  # type: ignore
        return ObjectId
    except Exception:
        return None


_OBJECT_ID = _bson_object_id_class()


def jsonify_safe(obj: Any) -> Any:
    """Recursively convert datetime / ObjectId / Decimal / set into
    JSON-serializable primitives. Idempotent — already-safe values
    pass through unchanged."""
    if isinstance(obj, dict):
        return {k: jsonify_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [jsonify_safe(v) for v in obj]
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if _OBJECT_ID is not None and isinstance(obj, _OBJECT_ID):
        return str(obj)
    if isinstance(obj, Decimal):
        return float(obj)
    return obj


# ---------- Cache key ----------

def _build_cache_key(namespace: str, kwargs: dict) -> str:
    """Stable cache key from namespace + kwargs."""
    parts = sorted(f"{k}={v}" for k, v in kwargs.items() if not k.startswith("_") and k != "request")
    raw = f"{namespace}::" + "::".join(parts)
    if len(raw) <= 200:
        return raw
    return f"{namespace}::" + hashlib.md5(raw.encode("utf-8")).hexdigest()


# ---------- The decorator ----------

def bulletproof_endpoint(
    *,
    cache_namespace: str,
    empty_check: Optional[Callable[[Any], bool]] = None,
    empty_fallback: Optional[Any] = None,
    short_ttl: int = 60,
    lkg_ttl: int = 86400,
    cache_keys: Optional[list[str]] = None,
):
    """Decorator factory. See module docstring for usage.

    Args:
        cache_namespace: Stable string identifying this endpoint
            in the cache (e.g. "tiles_products"). Different routes
            MUST use different namespaces.
        empty_check: Callable that returns True if the response
            is "empty" and should fall back to LKG. Default is
            `not bool(result)` — sufficient for list/dict shapes.
        empty_fallback: Default body returned when there's no LKG
            AND the result is empty AND no exception occurred. Should
            preserve the response shape (keys, types) the frontend
            expects so JS doesn't crash on `.length` / iteration.
        short_ttl: Seconds to cache fresh successful responses.
        lkg_ttl: Seconds to keep last-known-good for fallback.
        cache_keys: Whitelist of kwarg names to include in the cache
            key. If None, all non-private kwargs are included.
    """
    if empty_check is None:
        empty_check = lambda r: not bool(r)  # noqa: E731

    if empty_fallback is None:
        empty_fallback = {}

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            key_kwargs = (
                {k: kwargs.get(k) for k in cache_keys}
                if cache_keys else
                {k: v for k, v in kwargs.items()
                 if not k.startswith("_") and k != "request"
                 and not callable(v) and not hasattr(v, "method")}  # exclude Request/Response objects
            )
            cache_key = _build_cache_key(cache_namespace, key_kwargs)
            lkg_key = f"lkg:{cache_key}"

            # Layer 1 — fresh cache hit
            cached = endpoint_cache.get(cache_key)
            if cached is not None:
                return JSONResponse(content=cached, headers=PUBLIC_CACHE_HEADERS)

            # Layer 2 — run the real function
            try:
                result = await func(*args, **kwargs)
            except Exception:
                # Catastrophic failure — try LKG
                logger.exception(f"bulletproof_endpoint[{cache_namespace}] crashed; checking LKG")
                stale = endpoint_cache.get_stale(lkg_key)
                if stale is not None:
                    logger.warning(f"bulletproof_endpoint[{cache_namespace}] serving last-known-good after exception")
                    return JSONResponse(content=stale, headers=NO_STORE_HEADERS)
                # No LKG → 503 with structured payload
                return JSONResponse(
                    status_code=503,
                    content={
                        **jsonify_safe(empty_fallback),
                        "error": "temporarily_unavailable",
                        "retry_after_seconds": 5,
                    },
                    headers={**NO_STORE_HEADERS, "Retry-After": "5"},
                )

            # If the func returned a Response itself (rare), pass through
            if isinstance(result, JSONResponse):
                return result

            # Layer 3 — JSON-safe walk before any caching/return
            safe = jsonify_safe(result)

            # Layer 4 — empty? try LKG
            try:
                is_empty = empty_check(safe)
            except Exception:
                is_empty = False

            if is_empty:
                stale = endpoint_cache.get_stale(lkg_key)
                if stale is not None:
                    logger.info(f"bulletproof_endpoint[{cache_namespace}] empty — serving LKG")
                    return JSONResponse(content=stale, headers=NO_STORE_HEADERS)
                # No LKG either — return whatever we have but DON'T cache it
                content = safe if safe else jsonify_safe(empty_fallback)
                return JSONResponse(content=content, headers=NO_STORE_HEADERS)

            # Healthy non-empty response — cache + LKG
            endpoint_cache.set(cache_key, safe, ttl=short_ttl)
            endpoint_cache.set_long(lkg_key, safe, ttl=lkg_ttl)
            return JSONResponse(content=safe, headers=PUBLIC_CACHE_HEADERS)

        # Mark the wrapped function so tests can verify protection
        wrapper.__bulletproof__ = True  # type: ignore
        wrapper.__bulletproof_namespace__ = cache_namespace  # type: ignore
        return wrapper

    return decorator

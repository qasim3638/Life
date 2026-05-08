"""
Monitoring Routes - System health, caching, and error tracking status
"""
from fastapi import APIRouter, Depends
from routes.auth import get_current_user

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])

@router.get("/status")
async def get_monitoring_status(current_user: dict = Depends(get_current_user)):
    """Get overall monitoring status"""
    if current_user.get("role") != "super_admin":
        return {"message": "Admin access required for detailed status"}
    
    status = {
        "services": {}
    }
    
    # Check cache status
    try:
        from utils.cache import get_cache_stats
        cache_stats = await get_cache_stats()
        status["services"]["cache"] = {
            "status": "operational" if cache_stats.get("cache_enabled") else "disabled",
            **cache_stats
        }
    except Exception as e:
        status["services"]["cache"] = {"status": "error", "error": str(e)}
    
    # Check Sentry status
    try:
        from utils.sentry_config import get_sentry_status
        sentry_status = get_sentry_status()
        status["services"]["sentry"] = {
            "status": "operational" if sentry_status.get("initialized") else "not_configured",
            **sentry_status
        }
    except Exception as e:
        status["services"]["sentry"] = {"status": "error", "error": str(e)}
    
    return status


@router.get("/cache")
async def get_cache_status(current_user: dict = Depends(get_current_user)):
    """Get cache status and statistics"""
    if current_user.get("role") != "super_admin":
        return {"message": "Admin access required"}
    
    try:
        from utils.cache import get_cache_stats
        return await get_cache_stats()
    except Exception as e:
        return {"error": str(e), "status": "unavailable"}


@router.post("/cache/clear")
async def clear_cache(pattern: str = "*", current_user: dict = Depends(get_current_user)):
    """Clear cache entries matching pattern"""
    if current_user.get("role") != "super_admin":
        return {"message": "Admin access required"}
    
    try:
        from utils.cache import cache_clear_pattern
        cleared = await cache_clear_pattern(pattern)
        return {"cleared": cleared, "pattern": pattern}
    except Exception as e:
        return {"error": str(e)}


@router.get("/sentry")
async def get_sentry_status(current_user: dict = Depends(get_current_user)):
    """Get Sentry error monitoring status"""
    if current_user.get("role") != "super_admin":
        return {"message": "Admin access required"}
    
    try:
        from utils.sentry_config import get_sentry_status
        return get_sentry_status()
    except Exception as e:
        return {"error": str(e), "status": "unavailable"}


@router.post("/sentry/test")
async def test_sentry(current_user: dict = Depends(get_current_user)):
    """Send a test message to Sentry"""
    if current_user.get("role") != "super_admin":
        return {"message": "Admin access required"}
    
    try:
        from utils.sentry_config import capture_message
        event_id = capture_message(
            f"Test message from {current_user.get('email', 'Admin')}",
            level="info",
            context={"triggered_by": current_user.get("email")}
        )
        return {
            "success": True,
            "event_id": event_id,
            "message": "Test message sent to Sentry"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

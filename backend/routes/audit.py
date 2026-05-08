"""
Audit log routes (Super Admin Only)
"""
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends

from config import get_db
from services import get_current_user

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


@router.get("")
async def get_audit_logs(
    entity_type: Optional[str] = None,
    action: Optional[str] = None,
    user_email: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
    skip: int = 0,
    current_user: dict = Depends(get_current_user)
):
    """Get audit logs with optional filters (super_admin only)"""
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")
    
    db = get_db()
    
    # Build query
    query = {}
    
    if entity_type:
        query["entity_type"] = entity_type
    if action:
        query["action"] = action
    if user_email:
        query["user_email"] = {"$regex": user_email, "$options": "i"}
    if start_date:
        query["timestamp"] = {"$gte": start_date}
    if end_date:
        if "timestamp" in query:
            query["timestamp"]["$lte"] = end_date
        else:
            query["timestamp"] = {"$lte": end_date}
    
    # Get total count
    total = await db.audit_logs.count_documents(query)
    
    # Get logs with pagination
    logs = await db.audit_logs.find(query, {"_id": 0}).sort("timestamp", -1).skip(skip).limit(limit).to_list(limit)
    
    return {
        "logs": logs,
        "total": total,
        "limit": limit,
        "skip": skip
    }


@router.get("/stats")
async def get_audit_stats(current_user: dict = Depends(get_current_user)):
    """Get audit log statistics (super_admin only)"""
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")
    
    db = get_db()
    
    # Get counts by entity type
    pipeline = [
        {"$group": {"_id": "$entity_type", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    entity_stats = await db.audit_logs.aggregate(pipeline).to_list(20)
    
    # Get counts by action
    pipeline = [
        {"$group": {"_id": "$action", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    action_stats = await db.audit_logs.aggregate(pipeline).to_list(20)
    
    # Get recent activity count (last 24 hours)
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    recent_count = await db.audit_logs.count_documents({"timestamp": {"$gte": yesterday}})
    
    # Total logs
    total_logs = await db.audit_logs.count_documents({})
    
    return {
        "total_logs": total_logs,
        "recent_activity": recent_count,
        "by_entity_type": {stat["_id"]: stat["count"] for stat in entity_stats},
        "by_action": {stat["_id"]: stat["count"] for stat in action_stats}
    }


@router.get("/{log_id}")
async def get_audit_log_detail(log_id: str, current_user: dict = Depends(get_current_user)):
    """Get detailed audit log entry with before/after values (super_admin only)"""
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")
    
    db = get_db()
    log = await db.audit_logs.find_one({"id": log_id}, {"_id": 0})
    if not log:
        raise HTTPException(status_code=404, detail="Audit log not found")
    
    return log


@router.get("/entity/{entity_type}/{entity_id}")
async def get_entity_audit_history(
    entity_type: str, 
    entity_id: str, 
    current_user: dict = Depends(get_current_user)
):
    """Get audit history for a specific entity (super_admin only)"""
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")
    
    db = get_db()
    logs = await db.audit_logs.find(
        {"entity_type": entity_type, "entity_id": entity_id},
        {"_id": 0}
    ).sort("timestamp", -1).to_list(10000)
    
    return logs

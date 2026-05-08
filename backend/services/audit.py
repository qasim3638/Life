"""
Audit logging service
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from config import get_db


async def log_audit(
    action: str,
    entity_type: str,
    user: dict,
    entity_id: str = "",
    entity_name: str = "",
    before_data: Optional[Dict[str, Any]] = None,
    after_data: Optional[Dict[str, Any]] = None,
    details: str = "",
    ip_address: str = ""
):
    """
    Log an audit entry for tracking changes and user actions.
    
    Args:
        action: The action performed (CREATE, UPDATE, DELETE, LOGIN, etc.)
        entity_type: The type of entity affected (user, product, invoice, etc.)
        user: The user performing the action
        entity_id: The ID of the affected entity
        entity_name: A human-readable name for the entity
        before_data: The state of the entity before the action (for updates)
        after_data: The state of the entity after the action
        details: Additional details about the action
        ip_address: The IP address of the request
    """
    db = get_db()
    
    audit_entry = {
        "id": str(uuid.uuid4()),
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "entity_name": entity_name,
        "user_id": user.get("id", ""),
        "user_email": user.get("email", "system"),
        "user_name": user.get("name", "System"),
        "user_role": user.get("role", "system"),
        "before_data": before_data,
        "after_data": after_data,
        "details": details,
        "ip_address": ip_address,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    await db.audit_logs.insert_one(audit_entry)
    return audit_entry

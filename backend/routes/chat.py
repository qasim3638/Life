"""
Staff Chat routes - Real-time messaging between staff across stores
"""
import uuid
import os
import base64
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File, Form
from pydantic import BaseModel

from config import get_db
from services import get_current_user

router = APIRouter(prefix="/chat", tags=["Chat"])

# Allowed file types for attachments
ALLOWED_EXTENSIONS = {
    'pdf': 'application/pdf',
    'doc': 'application/msword',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'xls': 'application/vnd.ms-excel',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'png': 'image/png',
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'gif': 'image/gif',
    'txt': 'text/plain',
    'csv': 'text/csv',
}

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


class MessageCreate(BaseModel):
    content: str
    channel: str = "general"  # general, store-specific, or direct
    recipient_id: Optional[str] = None  # For direct messages


class AttachmentInfo(BaseModel):
    id: str
    filename: str
    file_type: str
    file_size: int
    mime_type: str


class MessageResponse(BaseModel):
    id: str
    content: str
    channel: str
    sender_id: str
    sender_name: str
    sender_store: Optional[str] = None
    recipient_id: Optional[str] = None
    created_at: str
    read_by: List[str] = []


# Get messages for a channel
@router.get("")
async def get_messages(
    channel: str = Query("general"),
    limit: int = Query(50, le=100),
    before: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get messages from a channel"""
    db = get_db()
    
    query = {"channel": channel}
    
    user_id = current_user.get("id") or current_user.get("user_id") or str(current_user.get("_id", ""))
    
    # For direct messages, only show if user is sender or recipient
    if channel == "direct":
        query["$or"] = [
            {"sender_id": user_id},
            {"recipient_id": user_id}
        ]
    
    if before:
        query["created_at"] = {"$lt": before}
    
    messages = await db.chat_messages.find(
        query,
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    # Return in chronological order
    messages.reverse()
    
    return messages


# Send a message
@router.post("")
async def send_message(
    message: MessageCreate,
    current_user: dict = Depends(get_current_user)
):
    """Send a new message"""
    db = get_db()
    
    user_id = current_user.get("id") or current_user.get("user_id") or str(current_user.get("_id", ""))
    
    # Get user's store info
    user_store = None
    if current_user.get("assigned_showroom"):
        store = await db.showrooms.find_one(
            {"id": current_user["assigned_showroom"]},
            {"_id": 0, "name": 1}
        )
        if store:
            user_store = store.get("name")
    
    new_message = {
        "id": str(uuid.uuid4()),
        "content": message.content,
        "channel": message.channel,
        "sender_id": user_id,
        "sender_name": current_user.get("name") or current_user.get("email", "Unknown"),
        "sender_store": user_store,
        "recipient_id": message.recipient_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "read_by": [user_id],
        "attachments": []
    }
    
    await db.chat_messages.insert_one(new_message)
    
    # Remove _id before returning
    new_message.pop("_id", None)
    
    return new_message


# Send message with file attachment
@router.post("/with-attachment")
async def send_message_with_attachment(
    content: str = Form(""),
    channel: str = Form("general"),
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Send a message with file attachment"""
    db = get_db()
    
    user_id = current_user.get("id") or current_user.get("user_id") or str(current_user.get("_id", ""))
    
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    # Get file extension
    file_ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400, 
            detail=f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS.keys())}"
        )
    
    # Read file content
    file_content = await file.read()
    
    # Check file size
    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 10MB")
    
    # Get user's store info
    user_store = None
    if current_user.get("assigned_showroom"):
        store = await db.showrooms.find_one(
            {"id": current_user["assigned_showroom"]},
            {"_id": 0, "name": 1}
        )
        if store:
            user_store = store.get("name")
    
    # Create attachment record
    attachment_id = str(uuid.uuid4())
    attachment = {
        "id": attachment_id,
        "filename": file.filename,
        "file_type": file_ext,
        "file_size": len(file_content),
        "mime_type": ALLOWED_EXTENSIONS.get(file_ext, 'application/octet-stream'),
        "data": base64.b64encode(file_content).decode('utf-8')
    }
    
    # Store attachment separately
    await db.chat_attachments.insert_one({
        "id": attachment_id,
        "filename": file.filename,
        "file_type": file_ext,
        "file_size": len(file_content),
        "mime_type": attachment["mime_type"],
        "data": attachment["data"],
        "uploaded_by": user_id,
        "uploaded_at": datetime.now(timezone.utc).isoformat()
    })
    
    # Create message with attachment reference
    new_message = {
        "id": str(uuid.uuid4()),
        "content": content or f"📎 Shared a file: {file.filename}",
        "channel": channel,
        "sender_id": user_id,
        "sender_name": current_user.get("name") or current_user.get("email", "Unknown"),
        "sender_store": user_store,
        "recipient_id": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "read_by": [user_id],
        "attachments": [{
            "id": attachment_id,
            "filename": file.filename,
            "file_type": file_ext,
            "file_size": len(file_content),
            "mime_type": attachment["mime_type"]
        }]
    }
    
    await db.chat_messages.insert_one(new_message)
    
    # Remove _id before returning
    new_message.pop("_id", None)
    
    return new_message


# Download attachment
@router.get("/attachment/{attachment_id}")
async def download_attachment(
    attachment_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Download a chat attachment"""
    db = get_db()
    
    attachment = await db.chat_attachments.find_one(
        {"id": attachment_id},
        {"_id": 0}
    )
    
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    
    # Return file data
    return {
        "filename": attachment["filename"],
        "mime_type": attachment["mime_type"],
        "data": attachment["data"]
    }


# Typing indicator models
class TypingIndicator(BaseModel):
    channel: str


# Set typing indicator
@router.post("/typing")
async def set_typing(
    data: TypingIndicator,
    current_user: dict = Depends(get_current_user)
):
    """Set typing indicator for a user"""
    db = get_db()
    
    user_id = current_user.get("id") or current_user.get("user_id") or str(current_user.get("_id", ""))
    user_name = current_user.get("name") or current_user.get("email", "Unknown")
    
    # Upsert typing indicator with TTL
    await db.chat_typing.update_one(
        {"user_id": user_id, "channel": data.channel},
        {
            "$set": {
                "user_id": user_id,
                "user_name": user_name,
                "channel": data.channel,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        },
        upsert=True
    )
    
    return {"status": "ok"}


# Get typing users
@router.get("/typing")
async def get_typing_users(
    channel: str = Query("general"),
    current_user: dict = Depends(get_current_user)
):
    """Get users currently typing in a channel"""
    db = get_db()
    
    # Get typing indicators from last 5 seconds
    five_seconds_ago = datetime.now(timezone.utc)
    from datetime import timedelta
    five_seconds_ago = (five_seconds_ago - timedelta(seconds=5)).isoformat()
    
    typing_users = await db.chat_typing.find(
        {
            "channel": channel,
            "timestamp": {"$gte": five_seconds_ago}
        },
        {"_id": 0, "user_id": 1, "user_name": 1}
    ).to_list(20)
    
    return typing_users


# Mark messages as read
@router.post("/read")
async def mark_as_read(
    message_ids: List[str],
    current_user: dict = Depends(get_current_user)
):
    """Mark messages as read"""
    db = get_db()
    
    user_id = current_user.get("id") or current_user.get("user_id") or str(current_user.get("_id", ""))
    
    await db.chat_messages.update_many(
        {"id": {"$in": message_ids}},
        {"$addToSet": {"read_by": user_id}}
    )
    
    return {"message": "Messages marked as read"}


# Get unread count
@router.get("/unread")
async def get_unread_count(
    current_user: dict = Depends(get_current_user)
):
    """Get count of unread messages"""
    db = get_db()
    
    user_id = current_user.get("id") or current_user.get("user_id") or str(current_user.get("_id", ""))
    
    # Count messages not read by current user
    unread_count = await db.chat_messages.count_documents({
        "read_by": {"$ne": user_id},
        "$or": [
            {"channel": "general"},
            {"recipient_id": user_id}
        ]
    })
    
    return {"unread": unread_count}


# Get online users (users who sent messages in last 5 minutes)
@router.get("/online")
async def get_online_users(
    current_user: dict = Depends(get_current_user)
):
    """Get list of recently active users"""
    db = get_db()
    
    five_minutes_ago = datetime.now(timezone.utc).isoformat()
    
    # Get unique senders from recent messages
    pipeline = [
        {"$match": {"created_at": {"$gte": five_minutes_ago}}},
        {"$group": {
            "_id": "$sender_id",
            "name": {"$last": "$sender_name"},
            "store": {"$last": "$sender_store"},
            "last_seen": {"$max": "$created_at"}
        }}
    ]
    
    online_users = await db.chat_messages.aggregate(pipeline).to_list(50)
    
    return [
        {
            "id": u["_id"],
            "name": u["name"],
            "store": u["store"],
            "last_seen": u["last_seen"]
        }
        for u in online_users
    ]


# Get available channels
@router.get("/channels")
async def get_channels(
    current_user: dict = Depends(get_current_user)
):
    """Get available chat channels"""
    db = get_db()
    
    channels = [
        {"id": "general", "name": "General", "description": "All staff chat", "icon": "users"},
        {"id": "announcements", "name": "Announcements", "description": "Important updates", "icon": "megaphone"},
    ]
    
    # Add store-specific channels
    stores = await db.showrooms.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(20)
    for store in stores:
        channels.append({
            "id": f"store-{store['id']}",
            "name": store["name"],
            "description": f"{store['name']} team chat",
            "icon": "store"
        })
    
    return channels

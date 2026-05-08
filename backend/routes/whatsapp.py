"""
WhatsApp admin routes for managing automated trade welcome messages.
"""
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])

# UK timezone offset (GMT/BST handled simply)
UK_UTC_OFFSET = 0  # Adjust to 1 during BST if needed


def get_db():
    from server import db
    return db


class WhatsAppSettingsUpdate(BaseModel):
    enabled: bool = False
    template_name: str = ""
    language_code: str = "en"
    message_preview: str = ""


class TestMessageRequest(BaseModel):
    phone: str
    name: str = "Test"


class SendToCustomerRequest(BaseModel):
    customer_id: str
    template_name: Optional[str] = None


class BulkSendRequest(BaseModel):
    customer_ids: List[str]
    template_name: Optional[str] = None


class CustomMessageRequest(BaseModel):
    customer_ids: List[str]
    message: str


def calculate_send_time(registration_time_utc: datetime) -> datetime:
    """
    Calculate when to send the WhatsApp message based on registration time.

    Rules (all times in UK local / UTC for simplicity):
    - Registration 6pm-8:59am  -> Send at 9am next morning
    - Registration 9am-5:59pm  -> Send 1 hour after registration
    """
    # Convert to UK time (simplified: UTC + UK_UTC_OFFSET)
    uk_time = registration_time_utc + timedelta(hours=UK_UTC_OFFSET)
    hour = uk_time.hour

    if 9 <= hour < 18:
        # Between 9am and 5:59pm -> send 1 hour later
        send_time = registration_time_utc + timedelta(hours=1)
    else:
        # Between 6pm and 8:59am -> send at 9am next morning
        if hour >= 18:
            # Evening: next day 9am
            next_day = uk_time + timedelta(days=1)
        else:
            # Early morning (midnight to 8:59am): same day 9am
            next_day = uk_time
        send_time = next_day.replace(hour=9, minute=0, second=0, microsecond=0)
        # Convert back to UTC
        send_time = send_time - timedelta(hours=UK_UTC_OFFSET)

    return send_time


async def queue_trade_welcome_message(customer_doc: dict):
    """
    Queue a WhatsApp welcome message for a newly registered trade customer.
    Called from the trade registration endpoint.
    """
    db = get_db()

    settings = await db.whatsapp_settings.find_one({"_id": "config"})
    if not settings or not settings.get("enabled", False):
        logger.info("WhatsApp messaging disabled - skipping queue")
        return

    phone = customer_doc.get("phone", "")
    if not phone:
        logger.warning(f"No phone number for trade customer {customer_doc.get('email')}")
        return

    # Normalize phone to E.164 format
    phone = phone.strip().replace(" ", "")
    if not phone.startswith("+"):
        if phone.startswith("0"):
            phone = "+44" + phone[1:]
        else:
            phone = "+" + phone

    now = datetime.now(timezone.utc)
    send_time = calculate_send_time(now)

    msg_doc = {
        "id": str(uuid.uuid4()),
        "customer_id": customer_doc.get("id"),
        "customer_name": customer_doc.get("name", ""),
        "customer_email": customer_doc.get("email", ""),
        "business_name": customer_doc.get("business_name", ""),
        "phone": phone,
        "status": "pending",
        "scheduled_at": send_time.isoformat(),
        "queued_at": now.isoformat(),
        "retry_count": 0,
    }

    await db.whatsapp_queue.insert_one(msg_doc)
    logger.info(
        f"WhatsApp message queued for {phone} "
        f"(send at {send_time.strftime('%Y-%m-%d %H:%M')} UTC)"
    )


# -------- Admin API Routes --------

@router.get("/settings")
async def get_whatsapp_settings(request: Request):
    """Get current WhatsApp messaging settings."""
    db = get_db()
    settings = await db.whatsapp_settings.find_one({"_id": "config"})
    if not settings:
        return {
            "enabled": False,
            "template_name": "",
            "language_code": "en",
            "message_preview": "Hi {name}, welcome to Tile Station Trade! Your trade account is now active.",
            "credentials_configured": False,
        }

    import os
    has_creds = bool(os.environ.get("WHATSAPP_PHONE_NUMBER_ID")) and bool(os.environ.get("WHATSAPP_ACCESS_TOKEN"))

    return {
        "enabled": settings.get("enabled", False),
        "template_name": settings.get("template_name", ""),
        "language_code": settings.get("language_code", "en"),
        "message_preview": settings.get("message_preview", ""),
        "credentials_configured": has_creds,
    }


@router.post("/settings")
async def save_whatsapp_settings(data: WhatsAppSettingsUpdate, request: Request):
    """Save WhatsApp messaging settings."""
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()

    await db.whatsapp_settings.update_one(
        {"_id": "config"},
        {"$set": {
            "enabled": data.enabled,
            "template_name": data.template_name,
            "language_code": data.language_code,
            "message_preview": data.message_preview,
            "updated_at": now,
        }},
        upsert=True,
    )
    return {"success": True}


@router.get("/queue")
async def get_message_queue(
    status: Optional[str] = None,
    limit: int = 50,
    request: Request = None,
):
    """Get recent messages from the queue."""
    db = get_db()
    query = {}
    if status:
        query["status"] = status

    messages = await db.whatsapp_queue.find(
        query, {"_id": 0}
    ).sort("queued_at", -1).to_list(limit)

    # Get counts
    total = await db.whatsapp_queue.count_documents({})
    pending = await db.whatsapp_queue.count_documents({"status": "pending"})
    sent = await db.whatsapp_queue.count_documents({"status": "sent"})
    failed = await db.whatsapp_queue.count_documents({"status": "failed"})

    return {
        "messages": messages,
        "counts": {"total": total, "pending": pending, "sent": sent, "failed": failed},
    }


@router.delete("/queue/{message_id}")
async def cancel_queued_message(message_id: str, request: Request):
    """Cancel a pending message."""
    db = get_db()
    result = await db.whatsapp_queue.update_one(
        {"id": message_id, "status": "pending"},
        {"$set": {"status": "cancelled", "cancelled_at": datetime.now(timezone.utc).isoformat()}},
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Message not found or already processed")
    return {"success": True}


@router.post("/test")
async def send_test_message(data: TestMessageRequest, request: Request):
    """Send a test WhatsApp message immediately."""
    from services.whatsapp_service import send_whatsapp_template_message

    db = get_db()
    settings = await db.whatsapp_settings.find_one({"_id": "config"})
    if not settings or not settings.get("template_name"):
        raise HTTPException(status_code=400, detail="Configure a template name first")

    phone = data.phone.strip().replace(" ", "")
    if not phone.startswith("+"):
        if phone.startswith("0"):
            phone = "+44" + phone[1:]
        else:
            phone = "+" + phone

    first_name = data.name.split()[0] if data.name else "there"

    result = await send_whatsapp_template_message(
        recipient_phone=phone,
        template_name=settings["template_name"],
        language_code=settings.get("language_code", "en"),
        parameters=[first_name],
    )

    # Log the test
    await db.whatsapp_queue.insert_one({
        "id": str(uuid.uuid4()),
        "customer_name": data.name,
        "phone": phone,
        "status": "sent" if result.get("success") else "failed",
        "scheduled_at": datetime.now(timezone.utc).isoformat(),
        "queued_at": datetime.now(timezone.utc).isoformat(),
        "sent_at": datetime.now(timezone.utc).isoformat() if result.get("success") else None,
        "message_id": result.get("message_id"),
        "error": result.get("error"),
        "is_test": True,
        "retry_count": 0,
    })

    if result.get("success"):
        return {"success": True, "message_id": result["message_id"]}
    else:
        raise HTTPException(status_code=500, detail=result.get("error", "Send failed"))



def _normalize_phone(phone: str) -> str:
    """Normalize a phone number to E.164 format."""
    phone = phone.strip().replace(" ", "").replace("-", "")
    if not phone.startswith("+"):
        if phone.startswith("0"):
            phone = "+44" + phone[1:]
        else:
            phone = "+" + phone
    return phone


async def _get_customer_by_id(db, customer_id: str) -> dict:
    """Fetch a trade customer from shop_customers or trade_accounts by ID."""
    customer = await db.shop_customers.find_one({"id": customer_id}, {"_id": 0})
    if not customer:
        customer = await db.trade_accounts.find_one({"id": customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
    return customer


def _get_customer_phone(customer: dict) -> str:
    """Extract and normalize phone from customer record."""
    phone = customer.get("phone") or customer.get("contact_phone") or customer.get("mobile")
    if not phone:
        raise HTTPException(status_code=400, detail=f"No phone number for customer {customer.get('business_name') or customer.get('name')}")
    return _normalize_phone(phone)


def _get_customer_name(customer: dict) -> str:
    """Extract first name from customer record."""
    name = customer.get("contact_name") or customer.get("name") or customer.get("business_name") or "there"
    return name.split()[0]


async def _send_and_log(db, customer: dict, phone: str, template_name: str, language_code: str, parameters: list, is_custom: bool = False, custom_message: str = None):
    """Send a WhatsApp message and log it to the queue."""
    from services.whatsapp_service import send_whatsapp_template_message

    result = await send_whatsapp_template_message(
        recipient_phone=phone,
        template_name=template_name,
        language_code=language_code,
        parameters=parameters,
    )

    log_entry = {
        "id": str(uuid.uuid4()),
        "customer_name": customer.get("contact_name") or customer.get("name") or customer.get("business_name"),
        "customer_email": customer.get("contact_email") or customer.get("email"),
        "customer_id": customer.get("id"),
        "phone": phone,
        "status": "sent" if result.get("success") else "failed",
        "scheduled_at": datetime.now(timezone.utc).isoformat(),
        "queued_at": datetime.now(timezone.utc).isoformat(),
        "sent_at": datetime.now(timezone.utc).isoformat() if result.get("success") else None,
        "message_id": result.get("message_id"),
        "error": result.get("error"),
        "is_test": False,
        "is_custom": is_custom,
        "custom_message": custom_message,
        "template_name": template_name,
        "retry_count": 0,
    }
    await db.whatsapp_queue.insert_one(log_entry)
    return result


@router.post("/send-to-customer")
async def send_to_customer(data: SendToCustomerRequest, request: Request):
    """Send a WhatsApp template message to a specific trade customer."""
    db = get_db()
    settings = await db.whatsapp_settings.find_one({"_id": "config"})
    template_name = data.template_name or (settings.get("template_name") if settings else None)
    if not template_name:
        raise HTTPException(status_code=400, detail="No template name configured")

    language_code = settings.get("language_code", "en") if settings else "en"
    customer = await _get_customer_by_id(db, data.customer_id)
    phone = _get_customer_phone(customer)
    first_name = _get_customer_name(customer)

    result = await _send_and_log(db, customer, phone, template_name, language_code, [first_name])

    if result.get("success"):
        return {"success": True, "message_id": result["message_id"], "phone": phone}
    else:
        raise HTTPException(status_code=500, detail=result.get("error", "Send failed"))


@router.post("/bulk-send")
async def bulk_send(data: BulkSendRequest, request: Request):
    """Send a WhatsApp template message to multiple trade customers at once."""
    db = get_db()
    settings = await db.whatsapp_settings.find_one({"_id": "config"})
    template_name = data.template_name or (settings.get("template_name") if settings else None)
    if not template_name:
        raise HTTPException(status_code=400, detail="No template name configured")

    language_code = settings.get("language_code", "en") if settings else "en"
    results = {"sent": 0, "failed": 0, "skipped": 0, "details": []}

    for cid in data.customer_ids:
        try:
            customer = await _get_customer_by_id(db, cid)
            phone = _get_customer_phone(customer)
            first_name = _get_customer_name(customer)
            result = await _send_and_log(db, customer, phone, template_name, language_code, [first_name])
            if result.get("success"):
                results["sent"] += 1
                results["details"].append({"customer_id": cid, "status": "sent"})
            else:
                results["failed"] += 1
                results["details"].append({"customer_id": cid, "status": "failed", "error": result.get("error")})
        except HTTPException as e:
            results["skipped"] += 1
            results["details"].append({"customer_id": cid, "status": "skipped", "error": e.detail})

    return {"success": True, **results}


@router.post("/send-custom")
async def send_custom_message(data: CustomMessageRequest, request: Request):
    """Send a custom WhatsApp message to one or more trade customers using the custom_message template."""
    db = get_db()
    if not data.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    template_name = "custom_message"
    language_code = "en"
    results = {"sent": 0, "failed": 0, "skipped": 0, "details": []}

    for cid in data.customer_ids:
        try:
            customer = await _get_customer_by_id(db, cid)
            phone = _get_customer_phone(customer)
            result = await _send_and_log(
                db, customer, phone, template_name, language_code,
                [data.message.strip()],
                is_custom=True, custom_message=data.message.strip()
            )
            if result.get("success"):
                results["sent"] += 1
                results["details"].append({"customer_id": cid, "status": "sent"})
            else:
                results["failed"] += 1
                results["details"].append({"customer_id": cid, "status": "failed", "error": result.get("error")})
        except HTTPException as e:
            results["skipped"] += 1
            results["details"].append({"customer_id": cid, "status": "skipped", "error": e.detail})

    return {"success": True, **results}


@router.get("/customer-history/{customer_id}")
async def get_customer_message_history(customer_id: str, request: Request):
    """Get WhatsApp message history for a specific customer."""
    db = get_db()
    messages = await db.whatsapp_queue.find(
        {"customer_id": customer_id}, {"_id": 0}
    ).sort("queued_at", -1).to_list(50)
    return {"messages": messages}

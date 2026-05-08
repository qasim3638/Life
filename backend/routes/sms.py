"""
SMS notification routes for order collection notifications
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import os
import logging

router = APIRouter(prefix="/sms", tags=["SMS"])

# Lazy imports to avoid circular dependency
def get_dependencies():
    from config import get_db
    from server import get_current_user, twilio_client, TWILIO_PHONE_NUMBER, log_audit
    return get_current_user, get_db, twilio_client, TWILIO_PHONE_NUMBER, log_audit


class SMSNotificationRequest(BaseModel):
    phone_number: str
    message: str
    invoice_id: Optional[str] = None
    invoice_no: Optional[str] = None
    customer_name: Optional[str] = None


class SMSTemplateRequest(BaseModel):
    template_name: str
    template_text: str
    is_default: bool = False


# Default SMS templates
DEFAULT_TEMPLATES = {
    "order_ready": {
        "name": "Order Ready for Collection",
        "text": "Hi {customer_name}, your order {invoice_no} is ready for collection at {showroom_name}. Please bring your ID and order confirmation. Thank you! - Tile Station"
    },
    "order_dispatched": {
        "name": "Order Dispatched",
        "text": "Hi {customer_name}, your order {invoice_no} has been dispatched and is on its way! Expected delivery: {delivery_date}. Thank you! - Tile Station"
    },
    "payment_reminder": {
        "name": "Payment Reminder",
        "text": "Hi {customer_name}, this is a reminder that your order {invoice_no} has an outstanding balance of £{outstanding_amount}. Please contact us to arrange payment. - Tile Station"
    }
}


def format_phone_for_uk(phone: str) -> str:
    """Format phone number for UK (add +44 if needed)"""
    phone = phone.strip().replace(" ", "").replace("-", "")
    
    if phone.startswith("+"):
        return phone
    elif phone.startswith("00"):
        return "+" + phone[2:]
    elif phone.startswith("0"):
        return "+44" + phone[1:]
    else:
        return "+44" + phone


@router.post("/send")
async def send_sms_notification(request: SMSNotificationRequest):
    """Send SMS notification to customer"""
    get_current_user, get_db, twilio_client, TWILIO_PHONE_NUMBER, log_audit = get_dependencies()
    
    # Manual auth check
    from fastapi import Request
    from server import get_current_user as auth_func
    
    if not twilio_client:
        raise HTTPException(status_code=503, detail="SMS service not available. Twilio not configured.")
    
    if not TWILIO_PHONE_NUMBER:
        raise HTTPException(status_code=503, detail="SMS service not configured. No sender phone number set.")
    
    # Format phone number
    to_phone = format_phone_for_uk(request.phone_number)
    
    # Validate phone number format
    if not to_phone.startswith("+"):
        raise HTTPException(status_code=400, detail="Invalid phone number format")
    
    try:
        # Send SMS via Twilio
        message = twilio_client.messages.create(
            body=request.message,
            from_=TWILIO_PHONE_NUMBER,
            to=to_phone
        )
        
        # Log the SMS in database
        db = get_db()
        import uuid
        sms_log = {
            "id": str(uuid.uuid4()),
            "message_sid": message.sid,
            "to_phone": to_phone,
            "from_phone": TWILIO_PHONE_NUMBER,
            "message": request.message,
            "invoice_id": request.invoice_id,
            "invoice_no": request.invoice_no,
            "customer_name": request.customer_name,
            "status": message.status,
            "sent_at": datetime.now(timezone.utc).isoformat()
        }
        await db.sms_logs.insert_one(sms_log)
        
        return {
            "success": True,
            "message": "SMS sent successfully",
            "message_sid": message.sid,
            "status": message.status
        }
        
    except Exception as e:
        logging.error(f"Failed to send SMS: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send SMS: {str(e)}")


@router.get("/templates")
async def get_sms_templates():
    """Get SMS templates (default + custom)"""
    get_current_user, get_db, twilio_client, TWILIO_PHONE_NUMBER, log_audit = get_dependencies()
    db = get_db()
    
    # Get custom templates from database
    custom_templates = await db.sms_templates.find({}, {"_id": 0}).to_list(100)
    
    # Combine with defaults
    templates = []
    for key, template in DEFAULT_TEMPLATES.items():
        templates.append({
            "id": key,
            "name": template["name"],
            "text": template["text"],
            "is_default": True
        })
    
    # Add custom templates
    for template in custom_templates:
        templates.append({
            "id": template.get("id"),
            "name": template.get("name"),
            "text": template.get("text"),
            "is_default": False
        })
    
    return templates


@router.post("/templates")
async def create_sms_template(request: SMSTemplateRequest):
    """Create a custom SMS template"""
    get_current_user, get_db, twilio_client, TWILIO_PHONE_NUMBER, log_audit = get_dependencies()
    db = get_db()
    
    import uuid
    template_id = str(uuid.uuid4())
    
    template = {
        "id": template_id,
        "name": request.template_name,
        "text": request.template_text,
        "is_default": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.sms_templates.insert_one(template)
    
    return {"message": "Template created", "id": template_id}


@router.delete("/templates/{template_id}")
async def delete_sms_template(template_id: str):
    """Delete a custom SMS template"""
    get_current_user, get_db, twilio_client, TWILIO_PHONE_NUMBER, log_audit = get_dependencies()
    db = get_db()
    
    result = await db.sms_templates.delete_one({"id": template_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Template not found or is a default template")
    
    return {"message": "Template deleted"}


@router.get("/logs")
async def get_sms_logs(limit: int = 50):
    """Get SMS sending history"""
    get_current_user, get_db, twilio_client, TWILIO_PHONE_NUMBER, log_audit = get_dependencies()
    db = get_db()
    
    logs = await db.sms_logs.find({}, {"_id": 0}).sort("sent_at", -1).limit(limit).to_list(limit)
    return logs


@router.get("/status")
async def get_sms_status():
    """Check if SMS service is available"""
    get_current_user, get_db, twilio_client, TWILIO_PHONE_NUMBER, log_audit = get_dependencies()
    
    return {
        "available": twilio_client is not None and TWILIO_PHONE_NUMBER is not None,
        "has_client": twilio_client is not None,
        "has_phone_number": TWILIO_PHONE_NUMBER is not None,
        "message": "SMS service is ready" if (twilio_client and TWILIO_PHONE_NUMBER) else "SMS service not fully configured. Please add TWILIO_PHONE_NUMBER to .env"
    }

"""
Customer and Staff Invite routes
"""
import os
import uuid
import jwt
import secrets
import string
import random
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Request, BackgroundTasks
from pydantic import BaseModel

from config import get_db, JWT_SECRET
from models import CustomerInvite, InviteCreate, InviteEmailRequest, StaffInviteCreate, StaffRegistration
from services import get_current_user, is_admin_user, log_audit, hash_password

# Try to import resend
try:
    import resend
    RESEND_AVAILABLE = True
except ImportError:
    RESEND_AVAILABLE = False
    resend = None

RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "gravesend@tilestation.co.uk")

if RESEND_AVAILABLE and RESEND_API_KEY:
    try:
        resend.api_key = RESEND_API_KEY
    except Exception as e:
        logging.warning(f"Failed to initialize Resend: {e}")

# Available permissions list - matches frontend permission keys
AVAILABLE_PERMISSIONS = [
    "dashboard",
    "products",
    "categories",
    "orders",
    "epos",
    "customer_pricing",
    "customer_invites",
    "bulk_inquiries",
    "marketing",
    "showrooms",
    "reports",
    "user_management",
    # Legacy permissions (still supported for backward compatibility)
    "create_invoice",
    "edit_invoice",
    "delete_invoice",
    "view_reports",
    "manage_inventory",
    "manage_categories",
    "manage_customers",
    "manage_orders",
    "export_data",
    "view_analytics",
    "manage_showrooms",
    "send_marketing",
    "view_cost_price",
    "manage_pricing",
    "view_audit_logs",
    "manage_staff_pins"
]

router = APIRouter(tags=["Invites"])


# ============ CUSTOMER INVITES ============

@router.post("/invites", response_model=CustomerInvite)
async def create_invite(input: InviteCreate, current_user: dict = Depends(get_current_user)):
    """Create a new customer invite link (admin only)"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    db = get_db()
    
    # Generate a short, memorable invite code
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    now = datetime.now(timezone.utc)
    expires_at = None
    if input.expires_in_days:
        expires_at = now + timedelta(days=input.expires_in_days)
    
    invite_dict = {
        "id": str(uuid.uuid4()),
        "code": code,
        "created_by": current_user["email"],
        "note": input.note,
        "used": False,
        "used_by": None,
        "used_at": None,
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat() if expires_at else None
    }
    
    await db.invites.insert_one(invite_dict)
    
    # Log audit for create
    await log_audit(
        action="CREATE",
        entity_type="customer_invite",
        user=current_user,
        entity_id=invite_dict["id"],
        entity_name=f"Invite {code}",
        after_data={"code": code, "note": input.note, "expires_in_days": input.expires_in_days},
        details=f"Created customer invite link: {code}"
    )
    
    invite_dict['created_at'] = now
    invite_dict['expires_at'] = expires_at
    
    return CustomerInvite(**invite_dict)


@router.get("/invites", response_model=List[CustomerInvite])
async def get_invites(current_user: dict = Depends(get_current_user)):
    """Get all invites (admin only)"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    db = get_db()
    invites = await db.invites.find({}, {"_id": 0}).sort("created_at", -1).to_list(100000)
    
    for invite in invites:
        if isinstance(invite.get('created_at'), str):
            invite['created_at'] = datetime.fromisoformat(invite['created_at'])
        if invite.get('expires_at') and isinstance(invite['expires_at'], str):
            invite['expires_at'] = datetime.fromisoformat(invite['expires_at'])
        if invite.get('used_at') and isinstance(invite['used_at'], str):
            invite['used_at'] = datetime.fromisoformat(invite['used_at'])
    
    return invites


@router.get("/invites/validate/{code}")
async def validate_invite(code: str):
    """Validate an invite code (public endpoint)"""
    db = get_db()
    invite = await db.invites.find_one({"code": code}, {"_id": 0})
    
    if not invite:
        raise HTTPException(status_code=404, detail="Invalid invite code")
    
    if invite.get("used"):
        raise HTTPException(status_code=400, detail="This invite has already been used")
    
    if invite.get("expires_at"):
        expires_at = invite["expires_at"]
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        if datetime.now(timezone.utc) > expires_at:
            raise HTTPException(status_code=400, detail="This invite has expired")
    
    return {"valid": True, "note": invite.get("note")}


@router.delete("/invites/{invite_id}")
async def delete_invite(invite_id: str, current_user: dict = Depends(get_current_user)):
    """Delete an invite (admin only)"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    db = get_db()
    
    # Get invite info before deleting for audit
    invite = await db.invites.find_one({"id": invite_id}, {"_id": 0})
    
    result = await db.invites.delete_one({"id": invite_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Invite not found")
    
    # Log audit for delete
    if invite:
        await log_audit(
            action="DELETE",
            entity_type="customer_invite",
            user=current_user,
            entity_id=invite_id,
            entity_name=f"Invite {invite.get('code')}",
            before_data={"code": invite.get("code"), "used": invite.get("used")},
            details=f"Deleted customer invite: {invite.get('code')}"
        )
    
    return {"message": "Invite deleted successfully"}


@router.post("/invites/send-email")
async def send_invite_email(input: InviteEmailRequest, current_user: dict = Depends(get_current_user)):
    """Create an invite and send it via email (admin only)"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if not RESEND_API_KEY:
        raise HTTPException(status_code=500, detail="Email service not configured")
    
    db = get_db()
    
    # Generate a short, memorable invite code
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    now = datetime.now(timezone.utc)
    expires_at = None
    if input.expires_in_days:
        expires_at = now + timedelta(days=input.expires_in_days)
    
    # Create the invite in database
    invite_dict = {
        "id": str(uuid.uuid4()),
        "code": code,
        "created_by": current_user["email"],
        "note": input.note or f"Sent to {input.recipient_email}",
        "used": False,
        "used_by": None,
        "used_at": None,
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat() if expires_at else None,
        "sent_to_email": input.recipient_email
    }
    
    await db.invites.insert_one(invite_dict)
    
    # Generate invite link
    frontend_url = os.environ.get("FRONTEND_URL", "https://feature-verification-7.preview.emergentagent.com")
    invite_link = f"{frontend_url}?invite={code}"
    
    # Prepare email content
    recipient_name = input.recipient_name or "Customer"
    expires_text = f"This invite expires on {expires_at.strftime('%d %B %Y')}." if expires_at else ""
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
    </head>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f5f5f5;">
        <div style="background-color: #ffffff; border-radius: 8px; padding: 40px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <div style="text-align: center; margin-bottom: 30px;">
                <h1 style="color: #1e40af; margin: 0; font-size: 28px;">Tile Station</h1>
                <p style="color: #666; margin: 5px 0 0 0; font-size: 14px;">One Stop for Luxury and Quality Tiles</p>
            </div>
            
            <h2 style="color: #333; margin-bottom: 20px;">You're Invited!</h2>
            
            <p style="color: #555; line-height: 1.6;">
                Hello {recipient_name},
            </p>
            
            <p style="color: #555; line-height: 1.6;">
                You have been invited to join <strong>Tile Station</strong>, our exclusive warehouse inventory platform 
                where you can browse our premium tile collection and place orders.
            </p>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="{invite_link}" 
                   style="display: inline-block; background-color: #f97316; color: #ffffff; text-decoration: none; 
                          padding: 15px 40px; border-radius: 8px; font-weight: bold; font-size: 16px;">
                    Create Your Account
                </a>
            </div>
            
            <p style="color: #888; font-size: 13px; text-align: center;">
                Or copy this link: <br>
                <span style="color: #1e40af; word-break: break-all;">{invite_link}</span>
            </p>
            
            <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
            
            <p style="color: #888; font-size: 12px; text-align: center;">
                {expires_text}<br>
                This invitation was sent by {current_user.get('name', current_user['email'])}.
            </p>
        </div>
    </body>
    </html>
    """
    
    # Send email
    try:
        params = {
            "from": SENDER_EMAIL,
            "to": [input.recipient_email],
            "subject": "You're Invited to Join Tile Station",
            "html": html_content
        }
        
        email_result = await asyncio.to_thread(resend.Emails.send, params)
        
        return {
            "status": "success",
            "message": f"Invite sent to {input.recipient_email}",
            "invite_code": code,
            "invite_link": invite_link,
            "email_id": email_result.get("id") if isinstance(email_result, dict) else str(email_result)
        }
    except Exception as e:
        logging.error(f"Failed to send invite email: {str(e)}")
        # Invite is still created, just email failed
        return {
            "status": "partial",
            "message": f"Invite created but email failed: {str(e)}",
            "invite_code": code,
            "invite_link": invite_link
        }


# ============ STAFF INVITES ============

@router.post("/staff-invites")
async def create_staff_invite(input: StaffInviteCreate, current_user: dict = Depends(get_current_user)):
    """Create a staff/admin invite link (super_admin only)"""
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")
    
    db = get_db()
    
    # Validate role
    if input.role not in ["admin", "manager", "staff"]:
        raise HTTPException(status_code=400, detail="Invalid role. Use: admin, manager, or staff")
    
    # Validate permissions
    invalid = [p for p in input.permissions if p not in AVAILABLE_PERMISSIONS]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Invalid permissions: {invalid}")
    
    # Get showroom name if provided
    showroom_name = None
    if input.showroom_id:
        showroom = await db.showrooms.find_one({"id": input.showroom_id}, {"_id": 0})
        if showroom:
            showroom_name = showroom["name"]
    
    # Generate unique invite code
    invite_code = secrets.token_urlsafe(16)
    
    invite_dict = {
        "id": str(uuid.uuid4()),
        "code": invite_code,
        "role": input.role,
        "showroom_id": input.showroom_id,
        "showroom_name": showroom_name,
        "permissions": input.permissions,
        "note": input.note,
        "created_by": current_user["email"],
        "used": False,
        "used_by": None,
        "used_at": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=input.expires_days)).isoformat()
    }
    
    await db.staff_invites.insert_one(invite_dict)
    
    # Return without _id
    invite = await db.staff_invites.find_one({"id": invite_dict["id"]}, {"_id": 0})
    return invite


@router.get("/staff-invites")
async def get_staff_invites(current_user: dict = Depends(get_current_user)):
    """Get all staff invites (super_admin only)"""
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")
    
    db = get_db()
    invites = await db.staff_invites.find({}, {"_id": 0}).sort("created_at", -1).to_list(100000)
    return invites


@router.get("/staff-invites/{code}/validate")
async def validate_staff_invite(code: str):
    """Validate a staff invite code (public endpoint for registration)"""
    db = get_db()
    invite = await db.staff_invites.find_one({"code": code}, {"_id": 0})
    
    if not invite:
        raise HTTPException(status_code=404, detail="Invalid invite code")
    
    if invite.get("used"):
        raise HTTPException(status_code=400, detail="This invite has already been used")
    
    # Check expiration
    if invite.get("expires_at"):
        expires_at = datetime.fromisoformat(invite["expires_at"].replace("Z", "+00:00"))
        if datetime.now(timezone.utc) > expires_at:
            raise HTTPException(status_code=400, detail="This invite has expired")
    
    return {
        "valid": True,
        "role": invite["role"],
        "showroom_id": invite.get("showroom_id"),
        "showroom_name": invite.get("showroom_name"),
        "permissions": invite.get("permissions", [])
    }


@router.post("/staff-invites/{code}/register")
async def register_with_staff_invite(code: str, registration: StaffRegistration):
    """Register a new staff/admin user using an invite code"""
    db = get_db()
    
    invite = await db.staff_invites.find_one({"code": code}, {"_id": 0})
    
    if not invite:
        raise HTTPException(status_code=404, detail="Invalid invite code")
    
    if invite.get("used"):
        raise HTTPException(status_code=400, detail="This invite has already been used")
    
    # Check expiration
    if invite.get("expires_at"):
        expires_at = datetime.fromisoformat(invite["expires_at"].replace("Z", "+00:00"))
        if datetime.now(timezone.utc) > expires_at:
            raise HTTPException(status_code=400, detail="This invite has expired")
    
    # Check if email already exists
    existing = await db.users.find_one({"email": registration.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create user with invite details
    user_dict = {
        "id": str(uuid.uuid4()),
        "email": registration.email,
        "password": hash_password(registration.password),
        "name": registration.name,
        "role": invite["role"],
        "showroom_id": invite.get("showroom_id"),
        "showroom_name": invite.get("showroom_name"),
        "permissions": invite.get("permissions", []),
        "invited_by": invite["created_by"],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.users.insert_one(user_dict)
    
    # Mark invite as used
    await db.staff_invites.update_one(
        {"code": code},
        {"$set": {
            "used": True,
            "used_by": registration.email,
            "used_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    # Generate token
    token = jwt.encode(
        {"sub": registration.email, "role": invite["role"], "exp": datetime.now(timezone.utc) + timedelta(days=7)},
        JWT_SECRET,
        algorithm="HS256"
    )
    
    # Send notification for staff invite accepted
    try:
        from services.notifications import notify_staff_invite_accepted
        await notify_staff_invite_accepted(db, user_dict)
    except Exception as e:
        logging.error(f"Failed to send staff invite accepted notification: {e}")
    
    return {
        "token": token,
        "user": {
            "email": registration.email,
            "name": registration.name,
            "role": invite["role"],
            "showroom_id": invite.get("showroom_id"),
            "showroom_name": invite.get("showroom_name"),
            "permissions": invite.get("permissions", [])
        }
    }


@router.delete("/staff-invites/{invite_id}")
async def delete_staff_invite(invite_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a staff invite (super_admin only)"""
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")
    
    db = get_db()
    result = await db.staff_invites.delete_one({"id": invite_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Invite not found")
    
    return {"message": "Invite deleted successfully"}


# Pydantic model for staff invite email request
class StaffInviteEmailRequest(BaseModel):
    invite_id: str
    recipient_email: str
    recipient_name: Optional[str] = None


@router.post("/staff-invites/send-email")
async def send_staff_invite_email_endpoint(
    data: StaffInviteEmailRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """Send staff invite via email (super_admin only)"""
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")
    
    db = get_db()
    
    # Find the invite
    invite = await db.staff_invites.find_one({"id": data.invite_id}, {"_id": 0})
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    
    if invite.get("used"):
        raise HTTPException(status_code=400, detail="This invite has already been used")
    
    # Check if expired
    if invite.get("expires_at"):
        expires_at = invite["expires_at"]
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="This invite has expired")
    
    # Build invite URL
    base_url = str(request.base_url).rstrip('/')
    frontend_url = os.environ.get("FRONTEND_URL", base_url.replace("/api", "").replace(":8001", ":3000"))
    invite_url = f"{frontend_url}/staff-register/{invite['code']}"
    
    # Import and send email
    from services.email import send_staff_invite_email
    
    background_tasks.add_task(
        send_staff_invite_email,
        recipient_email=data.recipient_email,
        recipient_name=data.recipient_name,
        invite_url=invite_url,
        role=invite.get("role", "staff"),
        showroom_name=invite.get("showroom_name"),
        permissions=invite.get("permissions", []),
        note=invite.get("note")
    )
    
    # Update invite with email info
    await db.staff_invites.update_one(
        {"id": data.invite_id},
        {"$set": {
            "email_sent_to": data.recipient_email,
            "email_sent_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    # Log audit
    await log_audit(
        action="CREATE",
        entity_type="staff_invite_email",
        user=current_user,
        entity_id=data.invite_id,
        entity_name=f"Email to {data.recipient_email}",
        details=f"Staff invite email sent to {data.recipient_email} for {invite.get('role')} role"
    )
    
    return {
        "message": f"Invite email sent to {data.recipient_email}",
        "invite_id": data.invite_id,
        "recipient_email": data.recipient_email
    }

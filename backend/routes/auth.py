"""
Authentication routes
"""
import uuid
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, HTTPException, Depends

from config import get_db
from models import (
    UserRegister, UserLogin, User, TokenResponse,
    StaffRegistration, UserPermissionsUpdate
)
from services import (
    hash_password, verify_password, create_access_token,
    get_current_user, is_admin_user, require_admin_access, log_audit
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse)
async def register(input: UserRegister):
    """Register a new user"""
    db = get_db()
    
    # Check if user already exists
    existing = await db.users.find_one({"email": input.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Determine role and permissions based on invite code
    role = "customer"
    permissions = []
    showroom_id = None
    showroom_name = None
    
    if input.invite_code:
        # Check customer invite
        invite = await db.invites.find_one({
            "code": input.invite_code,
            "is_used": False
        })
        
        if not invite:
            # Check staff invite
            staff_invite = await db.staff_invites.find_one({
                "code": input.invite_code,
                "is_used": False
            })
            
            if staff_invite:
                if staff_invite.get("valid_until") and datetime.fromisoformat(staff_invite["valid_until"].replace("Z", "+00:00")) < datetime.now(timezone.utc):
                    raise HTTPException(status_code=400, detail="Invite code has expired")
                
                role = staff_invite.get("role", "staff")
                permissions = staff_invite.get("permissions", [])
                showroom_id = staff_invite.get("showroom_id")
                showroom_name = staff_invite.get("showroom_name")
                
                # Mark invite as used
                await db.staff_invites.update_one(
                    {"code": input.invite_code},
                    {"$set": {"is_used": True, "used_by": input.email}}
                )
        else:
            # Customer invite found
            if invite.get("valid_until") and datetime.fromisoformat(invite["valid_until"].replace("Z", "+00:00")) < datetime.now(timezone.utc):
                raise HTTPException(status_code=400, detail="Invite code has expired")
            
            # Mark invite as used
            await db.invites.update_one(
                {"code": input.invite_code},
                {"$set": {"is_used": True, "used_by": input.email}}
            )
    
    # Create user
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    
    user_doc = {
        "id": user_id,
        "email": input.email,
        "password": hash_password(input.password),
        "name": input.name,
        "phone": input.phone,
        "address": input.address.model_dump() if input.address else None,
        "role": role,
        "permissions": permissions,
        "showroom_id": showroom_id,
        "showroom_name": showroom_name,
        "created_at": now.isoformat()
    }
    
    await db.users.insert_one(user_doc)
    
    # Create token
    token = create_access_token({"sub": input.email, "role": role})
    
    # Log audit
    await log_audit(
        action="CREATE",
        entity_type="user",
        user={"id": user_id, "email": input.email, "name": input.name, "role": role},
        entity_id=user_id,
        entity_name=input.name,
        after_data={"email": input.email, "role": role},
        details=f"User registered: {input.email}"
    )
    
    user_response = User(
        id=user_id,
        email=input.email,
        name=input.name,
        phone=input.phone,
        address=input.address,
        role=role,
        permissions=permissions,
        showroom_id=showroom_id,
        showroom_name=showroom_name,
        created_at=now
    )
    
    return TokenResponse(token=token, user=user_response)


@router.post("/login", response_model=TokenResponse)
async def login(input: UserLogin):
    """Login a user"""
    db = get_db()
    
    user = await db.users.find_one({"email": input.email})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not verify_password(input.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_access_token({"sub": input.email, "role": user.get("role", "customer")})
    await log_audit(
        action="LOGIN",
        entity_type="user",
        user=user,
        entity_id=user["id"],
        entity_name=user["name"],
        details=f"User logged in: {input.email}"
    )
    
    user_response = User(
        id=user["id"],
        email=user["email"],
        name=user["name"],
        phone=user.get("phone", ""),
        role=user.get("role", "customer"),
        permissions=user.get("permissions", []),
        showroom_id=user.get("showroom_id"),
        showroom_name=user.get("showroom_name"),
        created_at=datetime.fromisoformat(user["created_at"]) if isinstance(user.get("created_at"), str) else user.get("created_at", datetime.now(timezone.utc))
    )
    
    return TokenResponse(token=token, user=user_response)


@router.get("/me", response_model=User)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get current user profile"""
    return User(**current_user)


@router.post("/refresh-token")
async def refresh_token(current_user: dict = Depends(get_current_user)):
    """Refresh the access token - returns a new token with extended expiry"""
    new_token = create_access_token({"sub": current_user["email"], "role": current_user.get("role", "customer")})
    
    user_response = User(
        id=current_user["id"],
        email=current_user["email"],
        name=current_user["name"],
        phone=current_user.get("phone", ""),
        role=current_user.get("role", "customer"),
        permissions=current_user.get("permissions", []),
        showroom_id=current_user.get("showroom_id"),
        showroom_name=current_user.get("showroom_name"),
        created_at=datetime.fromisoformat(current_user["created_at"]) if isinstance(current_user.get("created_at"), str) else current_user.get("created_at", datetime.now(timezone.utc))
    )
    
    return TokenResponse(token=new_token, user=user_response)

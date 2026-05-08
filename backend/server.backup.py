from fastapi import FastAPI, APIRouter, HTTPException, Depends, status, UploadFile, File, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import io
import csv
import asyncio
import uuid
import shutil
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from passlib.context import CryptContext
import bcrypt
import jwt
import secrets

# Create uploads directory
UPLOAD_DIR = Path("/app/backend/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Optional imports
try:
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    TwilioClient = None

try:
    import resend
    RESEND_AVAILABLE = True
except ImportError:
    RESEND_AVAILABLE = False
    resend = None

# PDF generation
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

ROOT_DIR = Path(__file__).parent
env_file = ROOT_DIR / '.env'
if env_file.exists():
    load_dotenv(env_file)

mongo_url = os.environ.get('MONGO_URL')
if not mongo_url:
    raise ValueError("MONGO_URL environment variable is required")
client = AsyncIOMotorClient(mongo_url)
db_name = os.environ.get('DB_NAME', 'tile_station')
db = client[db_name]

# Twilio configuration
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_VERIFY_SERVICE_SID = os.environ.get("TWILIO_VERIFY_SERVICE_SID")

# Initialize Twilio client if credentials are available
twilio_client = None
if TWILIO_AVAILABLE and TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    try:
        twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    except Exception as e:
        logging.warning(f"Failed to initialize Twilio client: {e}")

# Resend configuration
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
if RESEND_AVAILABLE and RESEND_API_KEY:
    try:
        resend.api_key = RESEND_API_KEY
    except Exception as e:
        logging.warning(f"Failed to initialize Resend: {e}")

app = FastAPI()

# Add CORS middleware immediately after app creation
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

api_router = APIRouter(prefix="/api")

security = HTTPBearer()
SECRET_KEY = os.environ.get("JWT_SECRET", "your-secret-key-change-in-production")
ALGORITHM = "HS256"

# OTP storage (in production, use Redis or database with TTL)
otp_storage = {}

def generate_otp():
    """Generate a 6-digit OTP"""
    return ''.join([str(secrets.randbelow(10)) for _ in range(6)])

def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its bcrypt hash"""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=7)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid authentication")
        user = await db.users.find_one({"email": email}, {"_id": 0})
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

class Address(BaseModel):
    line1: str
    line2: Optional[str] = None
    city: str
    postcode: str
    country: str = "United Kingdom"

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: str = "customer"
    phone: Optional[str] = None
    invite_code: Optional[str] = None
    company_name: Optional[str] = None
    company_reg_number: Optional[str] = None
    vat_number: Optional[str] = None
    address: Optional[Address] = None
    showroom_id: Optional[str] = None
    marketing_opt_in: bool = True

class UserLogin(BaseModel):
    email: EmailStr
    password: str

# Available permissions
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
    "user_management"
]

class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    email: EmailStr
    name: str
    role: str  # super_admin, admin, manager, staff, customer
    phone: Optional[str] = None
    company_name: Optional[str] = None
    company_reg_number: Optional[str] = None
    vat_number: Optional[str] = None
    address: Optional[dict] = None
    showroom_id: Optional[str] = None
    showroom_name: Optional[str] = None
    permissions: List[str] = []  # List of permission keys
    marketing_opt_in: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserPermissionsUpdate(BaseModel):
    role: Optional[str] = None
    permissions: Optional[List[str]] = None
    showroom_id: Optional[str] = None

class StaffRegistration(BaseModel):
    name: str
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    token: str
    user: User

# Store Models
class Store(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StoreCreate(BaseModel):
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None

# Sales Target Models
class SalesTarget(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    showroom_id: Optional[str] = None  # None = all showrooms
    month: int  # 1-12
    year: int
    monthly_target: float
    daily_target: float  # Auto-calculated
    weekly_target: float  # Auto-calculated
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class SalesTargetCreate(BaseModel):
    showroom_id: Optional[str] = None
    month: int
    year: int
    monthly_target: float

class SalesTargetUpdate(BaseModel):
    monthly_target: float

# Marketing Campaign Models
class MarketingCampaign(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    subject: str
    content: str
    campaign_type: str  # promotional, newsletter, custom
    target_audience: str  # all, showroom, opted_in
    target_showroom_id: Optional[str] = None
    status: str = "draft"  # draft, sent
    sent_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sent_at: Optional[datetime] = None

class MarketingCampaignCreate(BaseModel):
    name: str
    subject: str
    content: str
    campaign_type: str = "promotional"
    target_audience: str = "all"
    target_showroom_id: Optional[str] = None

class Category(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class CategoryCreate(BaseModel):
    name: str
    description: Optional[str] = None

class Product(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    sku: str
    description: Optional[str] = None
    category_id: Optional[str] = None
    category_name: Optional[str] = None
    stock: int
    m2_quantity: Optional[float] = None
    # Tile size for m² calculation (e.g., "30x60" for 30cm x 60cm)
    tile_width: Optional[float] = None  # Width in cm
    tile_height: Optional[float] = None  # Height in cm
    tile_m2_per_piece: Optional[float] = None  # Calculated m² per piece
    # Box configuration
    tiles_per_box: Optional[int] = None  # Number of tiles in a box
    box_m2_coverage: Optional[float] = None  # m² coverage per box (auto-calculated)
    price: float
    cost: Optional[float] = None  # Cost price for profit calculation
    # Room lot pricing
    room_lot_enabled: bool = False
    room_lot_quantity: Optional[int] = None  # Minimum quantity for room lot price
    room_lot_price: Optional[float] = None   # Price per piece when buying room lot
    # Pallet pricing
    pallet_enabled: bool = False
    pallet_quantity: Optional[int] = None    # Minimum quantity for pallet price
    pallet_price: Optional[float] = None     # Price per piece when buying full pallet
    # Clearance
    clearance: bool = False
    clearance_price: Optional[float] = None
    # Maximum discount allowed (percentage, e.g., 20 means 20% max discount)
    max_discount: Optional[float] = None
    reorder_level: int = 10
    images: List[str] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ProductCreate(BaseModel):
    name: str
    sku: str
    description: Optional[str] = None
    category_id: Optional[str] = None
    stock: int
    m2_quantity: Optional[float] = None
    # Tile size for m² calculation
    tile_width: Optional[float] = None  # Width in cm
    tile_height: Optional[float] = None  # Height in cm
    # Box configuration
    tiles_per_box: Optional[int] = None  # Number of tiles in a box
    price: float
    cost: Optional[float] = None  # Cost price for profit calculation
    # Room lot pricing
    room_lot_enabled: bool = False
    room_lot_quantity: Optional[int] = None
    room_lot_price: Optional[float] = None
    # Pallet pricing
    pallet_enabled: bool = False
    pallet_quantity: Optional[int] = None
    pallet_price: Optional[float] = None
    # Clearance
    clearance: bool = False
    clearance_price: Optional[float] = None
    # Maximum discount allowed (percentage, e.g., 20 means 20% max discount)
    max_discount: Optional[float] = None
    reorder_level: int = 10
    images: List[str] = []

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    sku: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[str] = None
    stock: Optional[int] = None
    m2_quantity: Optional[float] = None
    # Tile size for m² calculation
    tile_width: Optional[float] = None
    tile_height: Optional[float] = None
    # Box configuration
    tiles_per_box: Optional[int] = None
    price: Optional[float] = None
    cost: Optional[float] = None  # Cost price for profit calculation
    # Room lot pricing
    room_lot_enabled: Optional[bool] = None
    room_lot_quantity: Optional[int] = None
    room_lot_price: Optional[float] = None
    # Pallet pricing
    pallet_enabled: Optional[bool] = None
    pallet_quantity: Optional[int] = None
    pallet_price: Optional[float] = None
    # Clearance
    clearance: Optional[bool] = None
    clearance_price: Optional[float] = None
    # Maximum discount allowed (percentage, e.g., 20 means 20% max discount)
    max_discount: Optional[float] = None
    reorder_level: Optional[int] = None
    images: Optional[List[str]] = None

class OrderItem(BaseModel):
    product_id: str
    product_name: str
    quantity: int
    price: float

class BulkInquiry(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    customer_email: str
    customer_name: str
    customer_phone: Optional[str] = None
    product_id: str
    product_name: str
    product_sku: str
    quantity_needed: int
    message: Optional[str] = None
    status: str = "pending"  # pending, contacted, quoted, closed
    admin_notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class BulkInquiryCreate(BaseModel):
    product_id: str
    quantity_needed: int
    phone: Optional[str] = None
    message: Optional[str] = None

class BulkInquiryUpdate(BaseModel):
    status: Optional[str] = None
    admin_notes: Optional[str] = None

# Invoice Models
class InvoiceLineItem(BaseModel):
    product_id: str
    product_name: str
    sku: Optional[str] = None
    quantity: float
    m2: Optional[float] = 0
    price: float              # Original/List price
    due_price: Optional[float] = None  # Custom/Negotiated/Due price (if different from price)
    total: Optional[float] = None  # Total for this line item
    discount: float = 0

class DepositEntry(BaseModel):
    date: str
    amount: float
    note: Optional[str] = None

class InvoiceCreate(BaseModel):
    invoice_no: str
    date: str
    time: str
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    customer_address: Optional[str] = None
    notes: Optional[str] = None
    sales_person: Optional[str] = None
    payment_method: str = "Card"
    showroom_id: Optional[str] = None
    showroom_name: Optional[str] = None
    deposits: List[DepositEntry] = []  # Multiple deposits on different days
    line_items: List[InvoiceLineItem]
    subtotal: float
    vat: float
    gross_total: float
    total_savings: float = 0
    staff_pin: Optional[str] = None  # PIN verification for staff
    # Order status: open_order -> processing -> completed
    # If paid in full (no outstanding) -> status follows normal flow
    # If deposit taken with outstanding -> deposit_order status
    status: str = "open_order"  # open_order, deposit_order, processing, completed

class InvoiceUpdate(BaseModel):
    invoice_no: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    customer_address: Optional[str] = None
    notes: Optional[str] = None
    sales_person: Optional[str] = None
    payment_method: Optional[str] = None
    showroom_id: Optional[str] = None
    showroom_name: Optional[str] = None
    deposits: Optional[List[DepositEntry]] = None  # Multiple deposits
    line_items: Optional[List[InvoiceLineItem]] = None
    subtotal: Optional[float] = None
    vat: Optional[float] = None
    gross_total: Optional[float] = None
    total_savings: Optional[float] = None
    staff_pin: Optional[str] = None  # PIN verification for edit
    status: Optional[str] = None  # open_order, deposit_order, processing, completed

# Staff PIN Models
class StaffPinCreate(BaseModel):
    name: str
    pin: str  # 4-6 digit PIN
    role: str = "staff"  # staff, manager, admin
    active: bool = True
    showroom_id: Optional[str] = None

class StaffPinUpdate(BaseModel):
    name: Optional[str] = None
    pin: Optional[str] = None
    role: Optional[str] = None
    active: Optional[bool] = None
    showroom_id: Optional[str] = None

class StaffPinVerify(BaseModel):
    pin: str

class CustomerInvite(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    code: str
    created_by: str
    note: Optional[str] = None
    used: bool = False
    used_by: Optional[str] = None
    used_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None

# Staff/Admin Invite Models
class StaffInviteCreate(BaseModel):
    role: str = "staff"  # staff, manager, admin
    showroom_id: Optional[str] = None
    permissions: List[str] = []
    note: Optional[str] = None
    expires_days: int = 7  # Link expires in X days

class StaffInvite(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    code: str
    role: str
    showroom_id: Optional[str] = None
    showroom_name: Optional[str] = None
    permissions: List[str] = []
    note: Optional[str] = None
    created_by: str
    used: bool = False
    used_by: Optional[str] = None
    used_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None

class InviteCreate(BaseModel):
    note: Optional[str] = None
    expires_in_days: Optional[int] = 30

class InviteEmailRequest(BaseModel):
    recipient_email: EmailStr
    recipient_name: Optional[str] = None
    note: Optional[str] = None
    expires_in_days: Optional[int] = 30

class Order(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    customer_email: str
    customer_name: str
    items: List[OrderItem]
    total_amount: float
    status: str = "pending"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class OrderCreate(BaseModel):
    items: List[OrderItem]

class OrderStatusUpdate(BaseModel):
    status: str

class CustomerPricing(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    customer_email: str
    product_id: str
    custom_price: float
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class CustomerPricingCreate(BaseModel):
    customer_email: str
    product_id: str
    custom_price: float

class BulkPricingItem(BaseModel):
    customer_email: str
    product_id: str
    custom_price: float

class BulkPricingImport(BaseModel):
    items: List[BulkPricingItem]

class BulkImportResult(BaseModel):
    total: int
    successful: int
    failed: int
    errors: List[str]

class OTPRequest(BaseModel):
    order_data: OrderCreate
    phone_number: str  # Phone number in E.164 format (e.g., +44XXXXXXXXXX)

class OTPVerification(BaseModel):
    order_data: OrderCreate
    otp: str
    phone_number: str  # Phone number used for OTP verification

class DashboardStats(BaseModel):
    total_products: int
    low_stock_count: int
    total_orders: int
    pending_orders: int
    total_revenue: float

class StoreAnalytics(BaseModel):
    showroom_id: str
    showroom_name: str
    total_revenue: float
    invoice_count: int
    average_order_value: float
    top_products: List[dict]
    percentage_of_total: float

class AnalyticsResponse(BaseModel):
    period: str
    start_date: str
    end_date: str
    total_revenue: float
    total_invoices: int
    average_order_value: float
    showroom_analytics: List[StoreAnalytics]
    daily_trends: List[dict]

class InvoiceEmailRequest(BaseModel):
    email: EmailStr
    message: Optional[str] = None

class AuditLogEntry(BaseModel):
    id: str
    action: str  # CREATE, UPDATE, DELETE, LOGIN, LOGOUT, STATUS_CHANGE
    entity_type: str  # invoice, product, order, user, showroom, price, auth
    entity_id: Optional[str] = None
    entity_name: Optional[str] = None
    user_email: str
    user_name: Optional[str] = None
    user_role: Optional[str] = None
    before_data: Optional[dict] = None
    after_data: Optional[dict] = None
    changes: Optional[List[dict]] = None  # List of field changes
    ip_address: Optional[str] = None
    showroom_id: Optional[str] = None
    showroom_name: Optional[str] = None
    timestamp: str
    details: Optional[str] = None

# Audit logging helper
async def log_audit(
    action: str,
    entity_type: str,
    user: dict,
    entity_id: str = None,
    entity_name: str = None,
    before_data: dict = None,
    after_data: dict = None,
    details: str = None,
    request = None
):
    """Log an action to the audit trail"""
    from uuid import uuid4
    
    # Calculate changes if before and after data provided
    changes = []
    if before_data and after_data:
        all_keys = set(before_data.keys()) | set(after_data.keys())
        for key in all_keys:
            if key in ['_id', 'password', 'created_at', 'updated_at']:
                continue
            old_val = before_data.get(key)
            new_val = after_data.get(key)
            if old_val != new_val:
                changes.append({
                    "field": key,
                    "old_value": old_val,
                    "new_value": new_val
                })
    
    audit_entry = {
        "id": str(uuid4()),
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "entity_name": entity_name,
        "user_email": user.get("email", "system"),
        "user_name": user.get("name"),
        "user_role": user.get("role"),
        "before_data": before_data,
        "after_data": after_data,
        "changes": changes if changes else None,
        "showroom_id": user.get("showroom_id"),
        "showroom_name": user.get("showroom_name"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "details": details
    }
    
    await db.audit_logs.insert_one(audit_entry)
    return audit_entry

# Helper function to check admin access (admin or super_admin)
def is_admin_user(user: dict) -> bool:
    """Check if user has admin-level access (admin, super_admin, manager with permissions)"""
    return user.get("role") in ["admin", "super_admin", "manager", "staff"]

def require_admin_access(user: dict):
    """Raise 403 if user doesn't have admin access"""
    if not is_admin_user(user):
        raise HTTPException(status_code=403, detail="Admin access required")

def has_permission(user: dict, permission: str) -> bool:
    """Check if user has a specific permission"""
    if user.get("role") == "super_admin":
        return True
    return permission in (user.get("permissions") or [])

def require_permission(user: dict, permission: str):
    """Raise 403 if user doesn't have the required permission"""
    if not has_permission(user, permission):
        raise HTTPException(status_code=403, detail=f"Permission '{permission}' required")

@api_router.post("/auth/register", response_model=TokenResponse)
async def register(input: UserRegister):
    existing_user = await db.users.find_one({"email": input.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # If invite code provided, validate and mark as used
    if input.invite_code:
        invite = await db.invites.find_one({"code": input.invite_code}, {"_id": 0})
        if not invite:
            raise HTTPException(status_code=400, detail="Invalid invite code")
        if invite.get("used"):
            raise HTTPException(status_code=400, detail="This invite has already been used")
        if invite.get("expires_at"):
            expires_at = invite["expires_at"]
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)
            if datetime.now(timezone.utc) > expires_at:
                raise HTTPException(status_code=400, detail="This invite has expired")
        
        # Mark invite as used
        await db.invites.update_one(
            {"code": input.invite_code},
            {"$set": {
                "used": True,
                "used_by": input.email,
                "used_at": datetime.now(timezone.utc).isoformat()
            }}
        )
    
    hashed_pwd = hash_password(input.password)
    
    # Prepare address data
    address_data = None
    if input.address:
        address_data = {
            "line1": input.address.line1,
            "line2": input.address.line2,
            "city": input.address.city,
            "postcode": input.address.postcode,
            "country": input.address.country
        }
    
    user_dict = {
        "email": input.email,
        "password": hashed_pwd,
        "name": input.name,
        "role": input.role,
        "phone": input.phone,
        "company_name": input.company_name,
        "company_reg_number": input.company_reg_number,
        "vat_number": input.vat_number,
        "address": address_data,
        "invite_code": input.invite_code,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.users.insert_one(user_dict)
    
    user_obj = User(
        email=input.email, 
        name=input.name, 
        role=input.role, 
        phone=input.phone,
        company_name=input.company_name,
        company_reg_number=input.company_reg_number,
        vat_number=input.vat_number,
        address=address_data
    )
    token = create_access_token({"sub": input.email, "role": input.role})
    
    return TokenResponse(token=token, user=user_obj)

@api_router.post("/auth/login", response_model=TokenResponse)
async def login(input: UserLogin):
    user = await db.users.find_one({"email": input.email}, {"_id": 0})
    if not user or not verify_password(input.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    if isinstance(user['created_at'], str):
        user['created_at'] = datetime.fromisoformat(user['created_at'])
    
    user_obj = User(**{k: v for k, v in user.items() if k != 'password'})
    token = create_access_token({"sub": user["email"], "role": user["role"]})
    
    # Log audit trail for login
    await log_audit(
        action="LOGIN",
        entity_type="auth",
        user=user,
        entity_id=user.get("id"),
        entity_name=user.get("email"),
        details=f"User '{user.get('name')}' ({user.get('role')}) logged in"
    )
    
    return TokenResponse(token=token, user=user_obj)

# Health check endpoint (no auth required)
@api_router.get("/health")
async def health_check():
    """Health check endpoint to verify the backend is ready."""
    try:
        # Quick DB ping to verify connection
        await db.command("ping")
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

@api_router.get("/auth/me", response_model=User)
async def get_me(current_user: dict = Depends(get_current_user)):
    if isinstance(current_user['created_at'], str):
        current_user['created_at'] = datetime.fromisoformat(current_user['created_at'])
    return User(**{k: v for k, v in current_user.items() if k != 'password'})

@api_router.post("/categories", response_model=Category)
async def create_category(input: CategoryCreate, current_user: dict = Depends(get_current_user)):
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    from uuid import uuid4
    category_id = str(uuid4())
    category_dict = {
        "id": category_id,
        "name": input.name,
        "description": input.description,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.categories.insert_one(category_dict)
    category_dict['created_at'] = datetime.fromisoformat(category_dict['created_at'])
    return Category(**category_dict)

@api_router.get("/categories", response_model=List[Category])
async def get_categories(current_user: dict = Depends(get_current_user)):
    categories = await db.categories.find({}, {"_id": 0}).to_list(1000)
    for cat in categories:
        if isinstance(cat['created_at'], str):
            cat['created_at'] = datetime.fromisoformat(cat['created_at'])
    return categories

# ============ IMAGE UPLOAD ENDPOINT ============

@api_router.post("/upload-image")
async def upload_image(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    """Upload an image file and return the URL"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid file type. Allowed: JPEG, PNG, GIF, WEBP")
    
    # Validate file size (max 10MB)
    MAX_SIZE = 10 * 1024 * 1024  # 10MB
    contents = await file.read()
    if len(contents) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 10MB")
    
    # Generate unique filename
    ext = Path(file.filename).suffix.lower() if file.filename else ".jpg"
    if ext not in [".jpg", ".jpeg", ".png", ".gif", ".webp"]:
        ext = ".jpg"
    unique_filename = f"{uuid.uuid4()}{ext}"
    
    # Save file
    file_path = UPLOAD_DIR / unique_filename
    with open(file_path, "wb") as f:
        f.write(contents)
    
    # Return URL - use environment variable for base URL
    base_url = os.environ.get("BACKEND_URL", "")
    if not base_url:
        # Fallback to constructing from request
        base_url = os.environ.get("REACT_APP_BACKEND_URL", "")
    
    image_url = f"{base_url}/uploads/{unique_filename}" if base_url else f"/uploads/{unique_filename}"
    
    return {"url": image_url, "filename": unique_filename}

@api_router.post("/products", response_model=Product)
async def create_product(input: ProductCreate, current_user: dict = Depends(get_current_user)):
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    from uuid import uuid4
    product_id = str(uuid4())
    
    category_name = None
    if input.category_id:
        category = await db.categories.find_one({"id": input.category_id}, {"_id": 0})
        if category:
            category_name = category["name"]
    
    # Calculate m² per piece from tile dimensions (cm to m²)
    tile_m2_per_piece = None
    if input.tile_width and input.tile_height:
        # Convert cm to meters and calculate area
        tile_m2_per_piece = (input.tile_width / 100) * (input.tile_height / 100)
    
    # Calculate box m² coverage
    box_m2_coverage = None
    if tile_m2_per_piece and input.tiles_per_box:
        box_m2_coverage = round(tile_m2_per_piece * input.tiles_per_box, 3)
    
    now = datetime.now(timezone.utc)
    product_dict = {
        "id": product_id,
        "name": input.name,
        "sku": input.sku,
        "description": input.description,
        "category_id": input.category_id,
        "category_name": category_name,
        "stock": input.stock,
        "m2_quantity": input.m2_quantity,
        # Tile size fields
        "tile_width": input.tile_width,
        "tile_height": input.tile_height,
        "tile_m2_per_piece": tile_m2_per_piece,
        # Box configuration
        "tiles_per_box": input.tiles_per_box,
        "box_m2_coverage": box_m2_coverage,
        "price": input.price,
        "cost": input.cost,  # Cost price for profit calculation
        # Room lot pricing
        "room_lot_enabled": input.room_lot_enabled,
        "room_lot_quantity": input.room_lot_quantity,
        "room_lot_price": input.room_lot_price,
        # Pallet pricing
        "pallet_enabled": input.pallet_enabled,
        "pallet_quantity": input.pallet_quantity,
        "pallet_price": input.pallet_price,
        # Clearance
        "clearance": input.clearance,
        "clearance_price": input.clearance_price,
        "max_discount": input.max_discount,
        "reorder_level": input.reorder_level,
        "images": input.images if input.images else [],
        "created_at": now.isoformat(),
        "updated_at": now.isoformat()
    }
    
    await db.products.insert_one(product_dict)
    
    # Log audit trail
    await log_audit(
        action="CREATE",
        entity_type="product",
        user=current_user,
        entity_id=product_id,
        entity_name=input.name,
        after_data={
            "name": input.name,
            "sku": input.sku,
            "price": input.price,
            "cost": input.cost,
            "stock": input.stock,
            "category": category_name
        },
        details=f"Product '{input.name}' (SKU: {input.sku}) created"
    )
    
    product_dict['created_at'] = datetime.fromisoformat(product_dict['created_at'])
    product_dict['updated_at'] = datetime.fromisoformat(product_dict['updated_at'])
    return Product(**product_dict)

@api_router.get("/products", response_model=List[Product])
async def get_products(
    search: Optional[str] = None,
    category_id: Optional[str] = None,
    low_stock: Optional[bool] = None,
    current_user: dict = Depends(get_current_user)
):
    query = {}
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"sku": {"$regex": search, "$options": "i"}}
        ]
    if category_id:
        query["category_id"] = category_id
    
    products = await db.products.find(query, {"_id": 0}).to_list(1000)
    
    # Hide cost field for non-super-admin users
    is_super_admin = current_user.get("role") == "super_admin"
    
    for prod in products:
        if isinstance(prod['created_at'], str):
            prod['created_at'] = datetime.fromisoformat(prod['created_at'])
        if isinstance(prod['updated_at'], str):
            prod['updated_at'] = datetime.fromisoformat(prod['updated_at'])
        # Remove cost for non-super-admin
        if not is_super_admin:
            prod['cost'] = None
    
    if low_stock:
        products = [p for p in products if p['stock'] <= p['reorder_level']]
    
    return products

@api_router.get("/products/{product_id}", response_model=Product)
async def get_product(product_id: str, current_user: dict = Depends(get_current_user)):
    product = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    if isinstance(product['created_at'], str):
        product['created_at'] = datetime.fromisoformat(product['created_at'])
    if isinstance(product['updated_at'], str):
        product['updated_at'] = datetime.fromisoformat(product['updated_at'])
    
    # Hide cost field for non-super-admin users
    is_super_admin = current_user.get("role") == "super_admin"
    if not is_super_admin:
        product['cost'] = None
    
    return Product(**product)

@api_router.put("/products/{product_id}", response_model=Product)
async def update_product(product_id: str, input: ProductUpdate, current_user: dict = Depends(get_current_user)):
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    product = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Get all non-None fields, but also include explicitly set boolean fields
    update_data = {}
    input_dict = input.model_dump()
    for k, v in input_dict.items():
        # Include field if it's not None, OR if it's a boolean (to allow setting False)
        if v is not None or (k in ['room_lot_enabled', 'pallet_enabled', 'clearance'] and v is not None):
            update_data[k] = v
    
    if "category_id" in update_data and update_data["category_id"]:
        category = await db.categories.find_one({"id": update_data["category_id"]}, {"_id": 0})
        if category:
            update_data["category_name"] = category["name"]
    
    # Recalculate m² per piece if tile dimensions are updated
    tile_width = update_data.get("tile_width", product.get("tile_width"))
    tile_height = update_data.get("tile_height", product.get("tile_height"))
    if tile_width and tile_height:
        update_data["tile_m2_per_piece"] = (tile_width / 100) * (tile_height / 100)
    elif "tile_width" in update_data or "tile_height" in update_data:
        # If one dimension is being cleared, clear the calculation
        if not tile_width or not tile_height:
            update_data["tile_m2_per_piece"] = None
    
    # Recalculate box m² coverage if tiles_per_box or tile dimensions are updated
    tiles_per_box = update_data.get("tiles_per_box", product.get("tiles_per_box"))
    tile_m2_per_piece = update_data.get("tile_m2_per_piece", product.get("tile_m2_per_piece"))
    if tile_m2_per_piece and tiles_per_box:
        update_data["box_m2_coverage"] = round(tile_m2_per_piece * tiles_per_box, 3)
    elif "tiles_per_box" in update_data or "tile_m2_per_piece" in update_data:
        if not tile_m2_per_piece or not tiles_per_box:
            update_data["box_m2_coverage"] = None
    
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.products.update_one({"id": product_id}, {"$set": update_data})
    
    # Log audit trail
    before_summary = {
        "name": product.get("name"),
        "sku": product.get("sku"),
        "price": product.get("price"),
        "stock": product.get("stock")
    }
    after_summary = {
        "name": update_data.get("name", product.get("name")),
        "sku": update_data.get("sku", product.get("sku")),
        "price": update_data.get("price", product.get("price")),
        "stock": update_data.get("stock", product.get("stock"))
    }
    await log_audit(
        action="UPDATE",
        entity_type="product",
        user=current_user,
        entity_id=product_id,
        entity_name=product.get("name"),
        before_data=before_summary,
        after_data=after_summary,
        details=f"Product '{product.get('name')}' updated"
    )
    
    updated_product = await db.products.find_one({"id": product_id}, {"_id": 0})
    if isinstance(updated_product['created_at'], str):
        updated_product['created_at'] = datetime.fromisoformat(updated_product['created_at'])
    if isinstance(updated_product['updated_at'], str):
        updated_product['updated_at'] = datetime.fromisoformat(updated_product['updated_at'])
    
    return Product(**updated_product)

@api_router.delete("/products/{product_id}")
async def delete_product(product_id: str, current_user: dict = Depends(get_current_user)):
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    product = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    result = await db.products.delete_one({"id": product_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Log audit trail
    await log_audit(
        action="DELETE",
        entity_type="product",
        user=current_user,
        entity_id=product_id,
        entity_name=product.get("name"),
        before_data={
            "name": product.get("name"),
            "sku": product.get("sku"),
            "price": product.get("price"),
            "stock": product.get("stock")
        },
        details=f"Product '{product.get('name')}' (SKU: {product.get('sku')}) deleted"
    )
    
    return {"message": "Product deleted successfully"}

@api_router.post("/orders/request-otp")
async def request_otp(input: OTPRequest, current_user: dict = Depends(get_current_user)):
    """Generate and send OTP via SMS for order verification"""
    
    # Validate phone number format (should start with +)
    if not input.phone_number.startswith('+'):
        raise HTTPException(status_code=400, detail="Phone number must be in international format (e.g., +44XXXXXXXXXX)")
    
    # Store order data for later verification
    otp_key = f"{current_user['email']}_order_otp"
    otp_storage[otp_key] = {
        "phone_number": input.phone_number,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
        "order_data": input.order_data.model_dump()
    }
    
    # Send OTP via Twilio Verify
    if twilio_client and TWILIO_VERIFY_SERVICE_SID:
        try:
            verification = twilio_client.verify.v2.services(TWILIO_VERIFY_SERVICE_SID) \
                .verifications.create(to=input.phone_number, channel="sms")
            
            return {
                "message": "OTP sent successfully via SMS",
                "status": verification.status,
                "expires_in_minutes": 5,
                "sms_sent": True
            }
        except Exception as e:
            # Log the error but fall back to demo mode
            logging.error(f"Twilio error: {str(e)}")
            # Fall back to demo mode
            otp = generate_otp()
            otp_storage[otp_key]["otp"] = otp
            return {
                "message": "OTP generated (SMS service unavailable)",
                "otp": otp,
                "expires_in_minutes": 5,
                "sms_sent": False,
                "error": str(e)
            }
    else:
        # Demo mode - generate OTP locally
        otp = generate_otp()
        otp_storage[otp_key]["otp"] = otp
        return {
            "message": "OTP generated (demo mode)",
            "otp": otp,
            "expires_in_minutes": 5,
            "sms_sent": False
        }

@api_router.post("/orders/verify-otp", response_model=Order)
async def verify_otp_and_create_order(input: OTPVerification, current_user: dict = Depends(get_current_user)):
    """Verify OTP and create order"""
    otp_key = f"{current_user['email']}_order_otp"
    
    if otp_key not in otp_storage:
        raise HTTPException(status_code=400, detail="No OTP request found")
    
    stored_otp_data = otp_storage[otp_key]
    
    # Check if OTP expired
    if datetime.now(timezone.utc) > stored_otp_data["expires_at"]:
        del otp_storage[otp_key]
        raise HTTPException(status_code=400, detail="OTP expired")
    
    # Verify OTP using Twilio Verify or local storage
    otp_valid = False
    
    if twilio_client and TWILIO_VERIFY_SERVICE_SID and "otp" not in stored_otp_data:
        # Verify with Twilio
        try:
            verification_check = twilio_client.verify.v2.services(TWILIO_VERIFY_SERVICE_SID) \
                .verification_checks.create(to=input.phone_number, code=input.otp)
            otp_valid = verification_check.status == "approved"
        except Exception as e:
            logging.error(f"Twilio verification error: {str(e)}")
            raise HTTPException(status_code=400, detail=f"OTP verification failed: {str(e)}")
    else:
        # Verify with local storage (demo mode)
        otp_valid = input.otp == stored_otp_data.get("otp")
    
    if not otp_valid:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    
    # OTP verified, create order
    from uuid import uuid4
    order_id = str(uuid4())
    
    # Use the order data from OTP request
    order_items = [OrderItem(**item) for item in stored_otp_data["order_data"]["items"]]
    total_amount = sum(item.quantity * item.price for item in order_items)
    
    now = datetime.now(timezone.utc)
    order_dict = {
        "id": order_id,
        "customer_email": current_user["email"],
        "customer_name": current_user["name"],
        "phone_number": input.phone_number,
        "items": [item.model_dump() for item in order_items],
        "total_amount": total_amount,
        "status": "pending",
        "created_at": now.isoformat(),
        "updated_at": now.isoformat()
    }
    
    await db.orders.insert_one(order_dict)
    
    # Update product stock
    for item in order_items:
        await db.products.update_one(
            {"id": item.product_id},
            {"$inc": {"stock": -item.quantity}, "$set": {"updated_at": now.isoformat()}}
        )
    
    # Clean up OTP
    del otp_storage[otp_key]
    
    order_dict['created_at'] = datetime.fromisoformat(order_dict['created_at'])
    order_dict['updated_at'] = datetime.fromisoformat(order_dict['updated_at'])
    return Order(**order_dict)

@api_router.post("/orders", response_model=Order)
async def create_order(input: OrderCreate, current_user: dict = Depends(get_current_user)):
    from uuid import uuid4
    order_id = str(uuid4())
    
    total_amount = sum(item.quantity * item.price for item in input.items)
    
    now = datetime.now(timezone.utc)
    order_dict = {
        "id": order_id,
        "customer_email": current_user["email"],
        "customer_name": current_user["name"],
        "items": [item.model_dump() for item in input.items],
        "total_amount": total_amount,
        "status": "pending",
        "created_at": now.isoformat(),
        "updated_at": now.isoformat()
    }
    
    await db.orders.insert_one(order_dict)
    
    for item in input.items:
        await db.products.update_one(
            {"id": item.product_id},
            {"$inc": {"stock": -item.quantity}, "$set": {"updated_at": now.isoformat()}}
        )
    
    order_dict['created_at'] = datetime.fromisoformat(order_dict['created_at'])
    order_dict['updated_at'] = datetime.fromisoformat(order_dict['updated_at'])
    return Order(**order_dict)

@api_router.get("/orders", response_model=List[Order])
async def get_orders(current_user: dict = Depends(get_current_user)):
    if current_user["role"] == "admin":
        orders = await db.orders.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    else:
        orders = await db.orders.find({"customer_email": current_user["email"]}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    
    for order in orders:
        if isinstance(order['created_at'], str):
            order['created_at'] = datetime.fromisoformat(order['created_at'])
        if isinstance(order['updated_at'], str):
            order['updated_at'] = datetime.fromisoformat(order['updated_at'])
    
    return orders

@api_router.put("/orders/{order_id}/status", response_model=Order)
async def update_order_status(order_id: str, input: OrderStatusUpdate, current_user: dict = Depends(get_current_user)):
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    update_data = {
        "status": input.status,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    result = await db.orders.update_one({"id": order_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Order not found")
    
    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if isinstance(order['created_at'], str):
        order['created_at'] = datetime.fromisoformat(order['created_at'])
    if isinstance(order['updated_at'], str):
        order['updated_at'] = datetime.fromisoformat(order['updated_at'])
    
    return Order(**order)

@api_router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(current_user: dict = Depends(get_current_user)):
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    total_products = await db.products.count_documents({})
    
    products = await db.products.find({}, {"_id": 0, "stock": 1, "reorder_level": 1}).to_list(10000)
    low_stock_count = sum(1 for p in products if p['stock'] <= p['reorder_level'])
    
    total_orders = await db.orders.count_documents({})
    pending_orders = await db.orders.count_documents({"status": "pending"})
    
    orders = await db.orders.find({}, {"_id": 0, "total_amount": 1}).to_list(10000)
    total_revenue = sum(order['total_amount'] for order in orders)
    
    return DashboardStats(
        total_products=total_products,
        low_stock_count=low_stock_count,
        total_orders=total_orders,
        pending_orders=pending_orders,
        total_revenue=total_revenue
    )

@api_router.get("/dashboard/best-sellers")
async def get_best_selling_products(
    period: str = "month",
    limit: int = 5,
    current_user: dict = Depends(get_current_user)
):
    """Get best selling products based on invoice data"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    from collections import defaultdict
    
    # Check if user is super admin (only super admin can see cost/profit)
    is_super_admin = current_user.get("role") == "super_admin"
    
    # Calculate date range
    now = datetime.now(timezone.utc)
    if period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        start = now - timedelta(days=7)
    elif period == "month":
        start = now - timedelta(days=30)
    elif period == "year":
        start = now - timedelta(days=365)
    else:
        start = now - timedelta(days=30)
    
    start_str = start.isoformat()
    
    # Get invoices in date range
    invoices = await db.invoices.find(
        {"created_at": {"$gte": start_str}},
        {"_id": 0, "line_items": 1}
    ).to_list(10000)
    
    # Aggregate product sales
    product_sales = defaultdict(lambda: {"quantity": 0, "revenue": 0, "name": "", "sku": ""})
    
    for invoice in invoices:
        for item in invoice.get("line_items", []):
            product_id = item.get("product_id")
            if product_id:
                qty = item.get("quantity", 0)
                price = item.get("price", 0)
                discount = item.get("discount", 0)
                item_revenue = qty * price * (1 - discount / 100)
                
                product_sales[product_id]["quantity"] += qty
                product_sales[product_id]["revenue"] += item_revenue
                product_sales[product_id]["name"] = item.get("product_name", "Unknown")
                product_sales[product_id]["sku"] = item.get("sku", "")
    
    # Sort by quantity sold (or revenue)
    top_by_quantity = sorted(
        [{"product_id": pid, **data} for pid, data in product_sales.items()],
        key=lambda x: x["quantity"],
        reverse=True
    )[:limit]
    
    top_by_revenue = sorted(
        [{"product_id": pid, **data} for pid, data in product_sales.items()],
        key=lambda x: x["revenue"],
        reverse=True
    )[:limit]
    
    # Get product details (images, cost) and calculate profit for top sellers (super admin only)
    total_profit = 0
    total_cost = 0
    
    for product in top_by_quantity + top_by_revenue:
        prod = await db.products.find_one({"id": product["product_id"]}, {"_id": 0, "images": 1, "cost": 1})
        product["image"] = prod.get("images", [None])[0] if prod else None
        product["revenue"] = round(product["revenue"], 2)
        
        # Calculate profit (only for super admin)
        if is_super_admin:
            cost = prod.get("cost", 0) if prod else 0
            product["cost"] = cost
            product["total_cost"] = round(cost * product["quantity"], 2)
            product["profit"] = round(product["revenue"] - product["total_cost"], 2)
            product["margin"] = round((product["profit"] / product["revenue"] * 100), 1) if product["revenue"] > 0 else 0
    
    # Calculate overall totals (only for super admin)
    if is_super_admin:
        for pid, data in product_sales.items():
            prod = await db.products.find_one({"id": pid}, {"_id": 0, "cost": 1})
            cost = prod.get("cost", 0) if prod else 0
            item_cost = cost * data["quantity"]
            total_cost += item_cost
            total_profit += data["revenue"] - item_cost
        
        overall_margin = round((total_profit / sum(p["revenue"] for p in product_sales.values()) * 100), 1) if product_sales else 0
    else:
        overall_margin = None
    
    response = {
        "period": period,
        "top_by_quantity": top_by_quantity,
        "top_by_revenue": top_by_revenue,
        "total_products_sold": sum(p["quantity"] for p in product_sales.values()),
        "total_revenue": round(sum(p["revenue"] for p in product_sales.values()), 2),
    }
    
    # Include profit data only for super admin
    if is_super_admin:
        response["total_cost"] = round(total_cost, 2)
        response["total_profit"] = round(total_profit, 2)
        response["overall_margin"] = overall_margin
        response["show_profit"] = True
    else:
        response["show_profit"] = False
    
    return response

@api_router.get("/analytics/showrooms")
async def get_showroom_analytics(
    period: str = "month",  # today, week, month, quarter, year, custom
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get showroom-level sales analytics with time filters.
    Super Admins see all showrooms, other users only see their assigned showroom."""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    from collections import defaultdict
    
    # Check if user is restricted to their showroom
    is_super_admin = current_user.get("role") == "super_admin"
    user_showroom_id = current_user.get("showroom_id")
    
    # Calculate date range based on period
    now = datetime.now(timezone.utc)
    
    if period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now
    elif period == "week":
        start = now - timedelta(days=7)
        end = now
    elif period == "month":
        start = now - timedelta(days=30)
        end = now
    elif period == "quarter":
        start = now - timedelta(days=90)
        end = now
    elif period == "year":
        start = now - timedelta(days=365)
        end = now
    elif period == "custom" and start_date and end_date:
        try:
            start = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        except:
            start = now - timedelta(days=30)
            end = now
    else:
        start = now - timedelta(days=30)
        end = now
    
    # Format dates for query (using string comparison since dates are stored as ISO strings)
    start_str = start.isoformat()
    end_str = end.isoformat()
    
    # Build invoice query - filter by showroom for non-super-admin users
    invoice_query = {"created_at": {"$gte": start_str, "$lte": end_str}}
    
    if not is_super_admin and user_showroom_id:
        # Staff/Manager can only see their showroom's data
        invoice_query["showroom_id"] = user_showroom_id
    
    # Get invoices based on user's access level
    invoices = await db.invoices.find(invoice_query, {"_id": 0}).to_list(10000)
    
    # Get all showrooms
    showrooms = await db.showrooms.find({}, {"_id": 0}).to_list(100)
    showroom_map = {s["id"]: s["name"] for s in showrooms}
    
    # Aggregate data by showroom
    showroom_data = defaultdict(lambda: {
        "revenue": 0,  # Gross total (inc VAT) for display
        "revenue_ex_vat": 0,  # Ex VAT for profit calculation
        "cost": 0,
        "count": 0,
        "total_m2": 0,  # Total square meters sold
        "products": defaultdict(lambda: {"quantity": 0, "m2": 0, "revenue": 0, "revenue_ex_vat": 0, "cost": 0, "name": "", "product_id": ""})
    })
    
    # Daily trends
    daily_data = defaultdict(lambda: {"revenue": 0, "revenue_ex_vat": 0, "cost": 0, "count": 0, "total_m2": 0})
    
    # Cache product costs for super admin profit calculation
    product_costs = {}
    if is_super_admin:
        products = await db.products.find({}, {"_id": 0, "id": 1, "cost": 1}).to_list(10000)
        product_costs = {p["id"]: p.get("cost", 0) or 0 for p in products}
    
    total_revenue = 0
    total_revenue_ex_vat = 0
    total_cost = 0
    total_invoices = len(invoices)
    
    for invoice in invoices:
        showroom_id = invoice.get("showroom_id", "unassigned")
        showroom_name = invoice.get("showroom_name") or showroom_map.get(showroom_id, "Unassigned")
        gross_total = invoice.get("gross_total", 0)
        subtotal = invoice.get("subtotal", 0)  # Ex VAT amount
        
        showroom_data[showroom_id]["revenue"] += gross_total
        showroom_data[showroom_id]["revenue_ex_vat"] += subtotal
        showroom_data[showroom_id]["count"] += 1
        showroom_data[showroom_id]["name"] = showroom_name
        total_revenue += gross_total
        total_revenue_ex_vat += subtotal
        
        # Aggregate top products and calculate cost
        for item in invoice.get("line_items", []):
            product_id = item.get("product_id", "unknown")
            qty = item.get("quantity", 0)
            item_m2 = item.get("m2", 0) or 0  # Square meters for this line item
            price = item.get("price", 0)
            discount = item.get("discount", 0)
            item_revenue = qty * price * (1 - discount / 100)  # This is ex-VAT (line item total)
            
            # Calculate cost for super admin
            item_cost = 0
            if is_super_admin and product_id in product_costs:
                item_cost = qty * product_costs[product_id]
                showroom_data[showroom_id]["cost"] += item_cost
                total_cost += item_cost
            
            # Track m² sold
            showroom_data[showroom_id]["total_m2"] += item_m2
            
            showroom_data[showroom_id]["products"][product_id]["quantity"] += qty
            showroom_data[showroom_id]["products"][product_id]["m2"] += item_m2
            showroom_data[showroom_id]["products"][product_id]["revenue"] += item_revenue  # Ex-VAT revenue
            showroom_data[showroom_id]["products"][product_id]["revenue_ex_vat"] += item_revenue
            showroom_data[showroom_id]["products"][product_id]["cost"] += item_cost
            showroom_data[showroom_id]["products"][product_id]["name"] = item.get("product_name", "Unknown")
            showroom_data[showroom_id]["products"][product_id]["product_id"] = product_id
        
        # Daily trends
        invoice_date = invoice.get("date", "")[:10]  # Get YYYY-MM-DD
        if invoice_date:
            daily_data[invoice_date]["revenue"] += gross_total
            daily_data[invoice_date]["revenue_ex_vat"] += subtotal
            daily_data[invoice_date]["count"] += 1
            # Track daily m² sold
            for item in invoice.get("line_items", []):
                daily_data[invoice_date]["total_m2"] += item.get("m2", 0) or 0
            if is_super_admin:
                # Calculate daily cost
                for item in invoice.get("line_items", []):
                    pid = item.get("product_id", "")
                    qty = item.get("quantity", 0)
                    if pid in product_costs:
                        daily_data[invoice_date]["cost"] += qty * product_costs[pid]
    
    # Build response
    showroom_analytics = []
    for showroom_id, data in showroom_data.items():
        # Get top 5 products by revenue
        top_products = sorted(
            [{"product_id": pid, **pdata} for pid, pdata in data["products"].items()],
            key=lambda x: x["revenue"],
            reverse=True
        )[:5]
        
        # Add profit to top products for super admin (using ex-VAT revenue)
        if is_super_admin:
            for prod in top_products:
                # Profit = Ex-VAT Revenue - Cost
                prod["profit"] = round(prod["revenue_ex_vat"] - prod["cost"], 2)
                prod["margin"] = round((prod["profit"] / prod["revenue_ex_vat"] * 100), 1) if prod["revenue_ex_vat"] > 0 else 0
                prod["cost_per_unit"] = round(prod["cost"] / prod["quantity"], 2) if prod["quantity"] > 0 else 0
                prod["profit_per_unit"] = round(prod["profit"] / prod["quantity"], 2) if prod["quantity"] > 0 else 0
                # Profit per m² - key metric for tiles
                prod["profit_per_m2"] = round(prod["profit"] / prod["m2"], 2) if prod["m2"] > 0 else 0
                prod["revenue_per_m2"] = round(prod["revenue_ex_vat"] / prod["m2"], 2) if prod["m2"] > 0 else 0
                prod["cost_per_m2"] = round(prod["cost"] / prod["m2"], 2) if prod["m2"] > 0 else 0
        
        avg_order = data["revenue"] / data["count"] if data["count"] > 0 else 0
        pct_of_total = (data["revenue"] / total_revenue * 100) if total_revenue > 0 else 0
        
        showroom_entry = {
            "showroom_id": showroom_id,
            "showroom_name": data["name"],
            "total_revenue": round(data["revenue"], 2),  # Gross (inc VAT) for display
            "total_revenue_ex_vat": round(data["revenue_ex_vat"], 2),  # Ex VAT
            "total_m2": round(data["total_m2"], 2),  # Total m² sold
            "invoice_count": data["count"],
            "average_order_value": round(avg_order, 2),
            "top_products": top_products,
            "percentage_of_total": round(pct_of_total, 1)
        }
        
        # Add profit data for super admin (using ex-VAT revenue)
        if is_super_admin:
            showroom_entry["total_cost"] = round(data["cost"], 2)
            # Profit = Ex VAT Revenue - Cost
            showroom_profit = data["revenue_ex_vat"] - data["cost"]
            showroom_entry["total_profit"] = round(showroom_profit, 2)
            showroom_entry["profit_margin"] = round((showroom_profit / data["revenue_ex_vat"] * 100), 1) if data["revenue_ex_vat"] > 0 else 0
            # Profit per m² for the showroom
            showroom_entry["profit_per_m2"] = round(showroom_profit / data["total_m2"], 2) if data["total_m2"] > 0 else 0
        
        showroom_analytics.append(showroom_entry)
    
    # Sort by revenue descending
    showroom_analytics.sort(key=lambda x: x["total_revenue"], reverse=True)
    
    # Build daily trends (last 30 days or period)
    daily_trends = []
    for date in sorted(daily_data.keys()):
        trend_entry = {
            "date": date,
            "revenue": round(daily_data[date]["revenue"], 2),
            "revenue_ex_vat": round(daily_data[date]["revenue_ex_vat"], 2),
            "total_m2": round(daily_data[date]["total_m2"], 2),
            "invoices": daily_data[date]["count"]
        }
        if is_super_admin:
            trend_entry["cost"] = round(daily_data[date]["cost"], 2)
            # Profit = Ex VAT Revenue - Cost
            daily_profit = daily_data[date]["revenue_ex_vat"] - daily_data[date]["cost"]
            trend_entry["profit"] = round(daily_profit, 2)
            trend_entry["profit_per_m2"] = round(daily_profit / daily_data[date]["total_m2"], 2) if daily_data[date]["total_m2"] > 0 else 0
            # VAT for this day
            trend_entry["vat"] = round(daily_data[date]["revenue"] - daily_data[date]["revenue_ex_vat"], 2)
        daily_trends.append(trend_entry)
    
    # Calculate total m² sold
    total_m2 = sum(data["total_m2"] for data in showroom_data.values())
    
    # Calculate VAT amount
    total_vat = total_revenue - total_revenue_ex_vat
    
    avg_order_value = total_revenue / total_invoices if total_invoices > 0 else 0
    
    # Get user's showroom name if restricted
    user_showroom_name = None
    if not is_super_admin and user_showroom_id:
        showroom = await db.showrooms.find_one({"id": user_showroom_id}, {"_id": 0, "name": 1})
        user_showroom_name = showroom.get("name") if showroom else None
    
    response = {
        "period": period,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "total_revenue": round(total_revenue, 2),  # Inc VAT (Gross)
        "total_revenue_ex_vat": round(total_revenue_ex_vat, 2),  # Ex VAT (Net)
        "total_vat": round(total_vat, 2),  # VAT amount
        "total_m2": round(total_m2, 2),
        "total_invoices": total_invoices,
        "average_order_value": round(avg_order_value, 2),
        "showroom_analytics": showroom_analytics,
        "daily_trends": daily_trends,
        "access_level": "all" if is_super_admin else "store",
        "user_showroom_id": user_showroom_id if not is_super_admin else None,
        "user_showroom_name": user_showroom_name
    }
    
    # Add overall profit metrics for super admin (using ex-VAT revenue)
    if is_super_admin:
        total_profit = total_revenue_ex_vat - total_cost
        avg_margin = round((total_profit / total_revenue_ex_vat * 100), 1) if total_revenue_ex_vat > 0 else 0
        response["total_cost"] = round(total_cost, 2)
        response["total_profit"] = round(total_profit, 2)
        response["average_margin"] = avg_margin
        response["profit_per_m2"] = round(total_profit / total_m2, 2) if total_m2 > 0 else 0
        response["show_profit"] = True
    else:
        response["show_profit"] = False
    
    return response

# Sales Target Endpoints
@api_router.get("/sales-targets")
async def get_sales_targets(
    month: Optional[int] = None,
    year: Optional[int] = None,
    showroom_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get sales targets. If no month/year specified, returns current month."""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    now = datetime.now(timezone.utc)
    target_month = month or now.month
    target_year = year or now.year
    
    query = {"month": target_month, "year": target_year}
    if showroom_id:
        query["showroom_id"] = showroom_id
    
    targets = await db.sales_targets.find(query, {"_id": 0}).to_list(100)
    return targets

@api_router.get("/sales-targets/current")
async def get_current_sales_target(
    showroom_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get current month's sales target with progress."""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    import calendar
    now = datetime.now(timezone.utc)
    
    # Get target
    query = {"month": now.month, "year": now.year}
    if showroom_id:
        query["showroom_id"] = showroom_id
    else:
        query["showroom_id"] = None  # Overall target
    
    target = await db.sales_targets.find_one(query, {"_id": 0})
    
    # Calculate actual sales for this period
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=now.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Build query for invoices
    invoice_query = {"created_at": {"$gte": month_start.isoformat()}}
    if showroom_id:
        invoice_query["showroom_id"] = showroom_id
    
    invoices = await db.invoices.find(invoice_query, {"_id": 0, "subtotal": 1, "created_at": 1}).to_list(10000)
    
    monthly_sales = sum(inv.get("subtotal", 0) or 0 for inv in invoices)
    weekly_sales = sum(
        inv.get("subtotal", 0) or 0 for inv in invoices 
        if inv.get("created_at", "") >= week_start.isoformat()
    )
    daily_sales = sum(
        inv.get("subtotal", 0) or 0 for inv in invoices 
        if inv.get("created_at", "") >= today_start.isoformat()
    )
    
    # Days info
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    day_of_month = now.day
    days_remaining = days_in_month - day_of_month
    
    if target:
        monthly_target = target.get("monthly_target", 0)
        daily_target = target.get("daily_target", 0)
        weekly_target = target.get("weekly_target", 0)
    else:
        monthly_target = 0
        daily_target = 0
        weekly_target = 0
    
    return {
        "month": now.month,
        "year": now.year,
        "month_name": now.strftime("%B"),
        "days_in_month": days_in_month,
        "day_of_month": day_of_month,
        "days_remaining": days_remaining,
        "target": {
            "monthly": monthly_target,
            "weekly": weekly_target,
            "daily": daily_target
        },
        "actual": {
            "monthly": round(monthly_sales, 2),
            "weekly": round(weekly_sales, 2),
            "daily": round(daily_sales, 2)
        },
        "progress": {
            "monthly": round((monthly_sales / monthly_target * 100), 1) if monthly_target > 0 else 0,
            "weekly": round((weekly_sales / weekly_target * 100), 1) if weekly_target > 0 else 0,
            "daily": round((daily_sales / daily_target * 100), 1) if daily_target > 0 else 0
        },
        "remaining": {
            "monthly": round(max(monthly_target - monthly_sales, 0), 2),
            "weekly": round(max(weekly_target - weekly_sales, 0), 2),
            "daily": round(max(daily_target - daily_sales, 0), 2)
        },
        "has_target": target is not None
    }

@api_router.post("/sales-targets")
async def create_or_update_sales_target(
    input: SalesTargetCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create or update a sales target. Only Super Admin can set targets."""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can set sales targets")
    
    import calendar
    from uuid import uuid4
    
    # Calculate daily and weekly targets
    days_in_month = calendar.monthrange(input.year, input.month)[1]
    daily_target = round(input.monthly_target / days_in_month, 2)
    weekly_target = round(input.monthly_target / 4, 2)  # Approximate 4 weeks per month
    
    # Check if target exists
    query = {"month": input.month, "year": input.year, "showroom_id": input.showroom_id}
    existing = await db.sales_targets.find_one(query)
    
    if existing:
        # Update existing
        await db.sales_targets.update_one(
            query,
            {"$set": {
                "monthly_target": input.monthly_target,
                "daily_target": daily_target,
                "weekly_target": weekly_target,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        target = await db.sales_targets.find_one(query, {"_id": 0})
    else:
        # Create new
        target_dict = {
            "id": str(uuid4()),
            "showroom_id": input.showroom_id,
            "month": input.month,
            "year": input.year,
            "monthly_target": input.monthly_target,
            "daily_target": daily_target,
            "weekly_target": weekly_target,
            "created_by": current_user.get("email"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        await db.sales_targets.insert_one(target_dict)
        target = {k: v for k, v in target_dict.items() if k != "_id"}
    
    return target

@api_router.delete("/sales-targets/{target_id}")
async def delete_sales_target(target_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a sales target."""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can delete sales targets")
    
    result = await db.sales_targets.delete_one({"id": target_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Target not found")
    
    return {"message": "Target deleted"}

# Customer Pricing Endpoints
@api_router.post("/customer-pricing", response_model=CustomerPricing)
async def create_customer_pricing(input: CustomerPricingCreate, current_user: dict = Depends(get_current_user)):
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    from uuid import uuid4
    pricing_id = str(uuid4())
    
    # Check if pricing already exists for this customer-product combination
    existing = await db.customer_pricing.find_one({
        "customer_email": input.customer_email,
        "product_id": input.product_id
    })
    
    if existing:
        # Update existing pricing
        await db.customer_pricing.update_one(
            {"customer_email": input.customer_email, "product_id": input.product_id},
            {"$set": {"custom_price": input.custom_price}}
        )
        pricing = await db.customer_pricing.find_one({
            "customer_email": input.customer_email,
            "product_id": input.product_id
        }, {"_id": 0})
    else:
        # Create new pricing
        pricing_dict = {
            "id": pricing_id,
            "customer_email": input.customer_email,
            "product_id": input.product_id,
            "custom_price": input.custom_price,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.customer_pricing.insert_one(pricing_dict)
        pricing = pricing_dict
    
    if isinstance(pricing['created_at'], str):
        pricing['created_at'] = datetime.fromisoformat(pricing['created_at'])
    
    return CustomerPricing(**pricing)

@api_router.get("/customer-pricing/{customer_email}", response_model=List[CustomerPricing])
async def get_customer_pricing(customer_email: str, current_user: dict = Depends(get_current_user)):
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    pricing_list = await db.customer_pricing.find(
        {"customer_email": customer_email},
        {"_id": 0}
    ).to_list(1000)
    
    for pricing in pricing_list:
        if isinstance(pricing['created_at'], str):
            pricing['created_at'] = datetime.fromisoformat(pricing['created_at'])
    
    return pricing_list

@api_router.delete("/customer-pricing/{pricing_id}")
async def delete_customer_pricing(pricing_id: str, current_user: dict = Depends(get_current_user)):
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = await db.customer_pricing.delete_one({"id": pricing_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Pricing not found")
    
    return {"message": "Customer pricing deleted successfully"}

@api_router.post("/customer-pricing/bulk-import", response_model=BulkImportResult)
async def bulk_import_customer_pricing(input: BulkPricingImport, current_user: dict = Depends(get_current_user)):
    """Bulk import customer-specific pricing from CSV data"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    from uuid import uuid4
    
    total = len(input.items)
    successful = 0
    failed = 0
    errors = []
    
    # Get all valid product IDs
    products = await db.products.find({}, {"_id": 0, "id": 1}).to_list(10000)
    valid_product_ids = {p["id"] for p in products}
    
    for idx, item in enumerate(input.items, 1):
        try:
            # Validate product exists
            if item.product_id not in valid_product_ids:
                errors.append(f"Row {idx}: Product ID '{item.product_id}' not found")
                failed += 1
                continue
            
            # Validate price
            if item.custom_price < 0:
                errors.append(f"Row {idx}: Invalid price '{item.custom_price}' (must be >= 0)")
                failed += 1
                continue
            
            # Validate email format (basic check)
            if '@' not in item.customer_email:
                errors.append(f"Row {idx}: Invalid email '{item.customer_email}'")
                failed += 1
                continue
            
            # Check if pricing already exists
            existing = await db.customer_pricing.find_one({
                "customer_email": item.customer_email,
                "product_id": item.product_id
            })
            
            if existing:
                # Update existing pricing
                await db.customer_pricing.update_one(
                    {"customer_email": item.customer_email, "product_id": item.product_id},
                    {"$set": {"custom_price": item.custom_price}}
                )
            else:
                # Create new pricing
                pricing_dict = {
                    "id": str(uuid4()),
                    "customer_email": item.customer_email,
                    "product_id": item.product_id,
                    "custom_price": item.custom_price,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                await db.customer_pricing.insert_one(pricing_dict)
            
            successful += 1
            
        except Exception as e:
            errors.append(f"Row {idx}: {str(e)}")
            failed += 1
    
    return BulkImportResult(
        total=total,
        successful=successful,
        failed=failed,
        errors=errors[:20]  # Limit errors to first 20
    )

@api_router.get("/customer-pricing/template")
async def get_pricing_template(current_user: dict = Depends(get_current_user)):
    """Get list of products for CSV template"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    products = await db.products.find({}, {"_id": 0, "id": 1, "name": 1, "sku": 1, "price": 1}).to_list(1000)
    
    return {
        "products": products,
        "csv_headers": ["customer_email", "product_id", "custom_price"],
        "example_row": ["customer@example.com", products[0]["id"] if products else "product-id-here", "19.99"]
    }

@api_router.get("/products-with-custom-pricing", response_model=List[Product])
async def get_products_with_custom_pricing(current_user: dict = Depends(get_current_user)):
    """Get products with custom pricing applied for the current customer"""
    products = await db.products.find({}, {"_id": 0}).to_list(1000)
    
    for prod in products:
        if isinstance(prod['created_at'], str):
            prod['created_at'] = datetime.fromisoformat(prod['created_at'])
        if isinstance(prod['updated_at'], str):
            prod['updated_at'] = datetime.fromisoformat(prod['updated_at'])
    
    # If customer, check for custom pricing
    if current_user["role"] == "customer":
        custom_pricing = await db.customer_pricing.find(
            {"customer_email": current_user["email"]},
            {"_id": 0}
        ).to_list(1000)
        
        # Create a map of product_id to custom_price
        custom_price_map = {cp["product_id"]: cp["custom_price"] for cp in custom_pricing}
        
        # Apply custom pricing to products
        for product in products:
            if product["id"] in custom_price_map:
                product["price"] = custom_price_map[product["id"]]
    
    return products

# Bulk Inquiry Endpoints
@api_router.post("/bulk-inquiries", response_model=BulkInquiry)
async def create_bulk_inquiry(input: BulkInquiryCreate, current_user: dict = Depends(get_current_user)):
    """Submit a bulk order inquiry"""
    from uuid import uuid4
    
    # Get product details
    product = await db.products.find_one({"id": input.product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    inquiry_id = str(uuid4())
    now = datetime.now(timezone.utc)
    
    inquiry_dict = {
        "id": inquiry_id,
        "customer_email": current_user["email"],
        "customer_name": current_user["name"],
        "customer_phone": input.phone,
        "product_id": input.product_id,
        "product_name": product["name"],
        "product_sku": product["sku"],
        "quantity_needed": input.quantity_needed,
        "message": input.message,
        "status": "pending",
        "admin_notes": None,
        "created_at": now.isoformat()
    }
    
    await db.bulk_inquiries.insert_one(inquiry_dict)
    inquiry_dict['created_at'] = now
    
    return BulkInquiry(**inquiry_dict)

@api_router.get("/bulk-inquiries", response_model=List[BulkInquiry])
async def get_bulk_inquiries(
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get bulk inquiries - admin sees all, customer sees their own"""
    query = {}
    
    if not is_admin_user(current_user):
        query["customer_email"] = current_user["email"]
    
    if status:
        query["status"] = status
    
    inquiries = await db.bulk_inquiries.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    
    for inquiry in inquiries:
        if isinstance(inquiry.get('created_at'), str):
            inquiry['created_at'] = datetime.fromisoformat(inquiry['created_at'])
    
    return inquiries

@api_router.put("/bulk-inquiries/{inquiry_id}", response_model=BulkInquiry)
async def update_bulk_inquiry(
    inquiry_id: str,
    input: BulkInquiryUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update bulk inquiry status (admin only)"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    inquiry = await db.bulk_inquiries.find_one({"id": inquiry_id}, {"_id": 0})
    if not inquiry:
        raise HTTPException(status_code=404, detail="Inquiry not found")
    
    update_data = {k: v for k, v in input.model_dump().items() if v is not None}
    
    if update_data:
        await db.bulk_inquiries.update_one({"id": inquiry_id}, {"$set": update_data})
    
    updated_inquiry = await db.bulk_inquiries.find_one({"id": inquiry_id}, {"_id": 0})
    if isinstance(updated_inquiry.get('created_at'), str):
        updated_inquiry['created_at'] = datetime.fromisoformat(updated_inquiry['created_at'])
    
    return BulkInquiry(**updated_inquiry)

@api_router.delete("/bulk-inquiries/{inquiry_id}")
async def delete_bulk_inquiry(inquiry_id: str, current_user: dict = Depends(get_current_user)):
    """Delete bulk inquiry (admin only)"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = await db.bulk_inquiries.delete_one({"id": inquiry_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Inquiry not found")
    
    return {"message": "Inquiry deleted successfully"}

# Customer Invite Endpoints
@api_router.post("/invites", response_model=CustomerInvite)
async def create_invite(input: InviteCreate, current_user: dict = Depends(get_current_user)):
    """Create a new customer invite link (admin only)"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    from uuid import uuid4
    import string
    import random
    
    # Generate a short, memorable invite code
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    now = datetime.now(timezone.utc)
    expires_at = None
    if input.expires_in_days:
        expires_at = now + timedelta(days=input.expires_in_days)
    
    invite_dict = {
        "id": str(uuid4()),
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
    
    invite_dict['created_at'] = now
    invite_dict['expires_at'] = expires_at
    
    return CustomerInvite(**invite_dict)

@api_router.get("/invites", response_model=List[CustomerInvite])
async def get_invites(current_user: dict = Depends(get_current_user)):
    """Get all invites (admin only)"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    invites = await db.invites.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    
    for invite in invites:
        if isinstance(invite.get('created_at'), str):
            invite['created_at'] = datetime.fromisoformat(invite['created_at'])
        if invite.get('expires_at') and isinstance(invite['expires_at'], str):
            invite['expires_at'] = datetime.fromisoformat(invite['expires_at'])
        if invite.get('used_at') and isinstance(invite['used_at'], str):
            invite['used_at'] = datetime.fromisoformat(invite['used_at'])
    
    return invites

@api_router.get("/invites/validate/{code}")
async def validate_invite(code: str):
    """Validate an invite code (public endpoint)"""
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

@api_router.delete("/invites/{invite_id}")
async def delete_invite(invite_id: str, current_user: dict = Depends(get_current_user)):
    """Delete an invite (admin only)"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = await db.invites.delete_one({"id": invite_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Invite not found")
    
    return {"message": "Invite deleted successfully"}

@api_router.post("/invites/send-email")
async def send_invite_email(input: InviteEmailRequest, current_user: dict = Depends(get_current_user)):
    """Create an invite and send it via email (admin only)"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if not RESEND_API_KEY:
        raise HTTPException(status_code=500, detail="Email service not configured")
    
    from uuid import uuid4
    import string
    import random
    
    # Generate a short, memorable invite code
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    now = datetime.now(timezone.utc)
    expires_at = None
    if input.expires_in_days:
        expires_at = now + timedelta(days=input.expires_in_days)
    
    # Create the invite in database
    invite_dict = {
        "id": str(uuid4()),
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
    
    # Generate invite link (using frontend URL from environment or default)
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

# Export Endpoints
@api_router.get("/export/inventory/csv")
async def export_inventory_csv(current_user: dict = Depends(get_current_user)):
    """Export inventory to CSV"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    products = await db.products.find({}, {"_id": 0}).to_list(10000)
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header row
    writer.writerow([
        'SKU', 'Name', 'Category', 'Stock', 'm² per Piece', 'Price (£/m²)',
        'Room Lot Qty', 'Room Lot Price', 'Pallet Qty', 'Pallet Price',
        'Clearance', 'Clearance Price', 'Reorder Level', 'Status'
    ])
    
    # Data rows
    for p in products:
        status = 'Low Stock' if p.get('stock', 0) <= p.get('reorder_level', 10) else 'OK'
        writer.writerow([
            p.get('sku', ''),
            p.get('name', ''),
            p.get('category_name', ''),
            p.get('stock', 0),
            p.get('m2_quantity', ''),
            p.get('price', 0),
            p.get('room_lot_quantity', '') if p.get('room_lot_enabled') else '',
            p.get('room_lot_price', '') if p.get('room_lot_enabled') else '',
            p.get('pallet_quantity', '') if p.get('pallet_enabled') else '',
            p.get('pallet_price', '') if p.get('pallet_enabled') else '',
            'Yes' if p.get('clearance') else 'No',
            p.get('clearance_price', '') if p.get('clearance') else '',
            p.get('reorder_level', 10),
            status
        ])
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=inventory_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        }
    )

@api_router.get("/export/inventory/pdf")
async def export_inventory_pdf(current_user: dict = Depends(get_current_user)):
    """Export inventory to PDF"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    
    products = await db.products.find({}, {"_id": 0}).to_list(10000)
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=20
    )
    elements.append(Paragraph("Tile Station - Inventory Report", title_style))
    elements.append(Paragraph(f"Generated: {datetime.now().strftime('%d %B %Y, %H:%M')}", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # Summary stats
    total_products = len(products)
    low_stock = len([p for p in products if p.get('stock', 0) <= p.get('reorder_level', 10)])
    total_stock = sum(p.get('stock', 0) for p in products)
    
    summary_data = [
        ['Total Products', 'Low Stock Items', 'Total Stock Pieces'],
        [str(total_products), str(low_stock), str(total_stock)]
    ]
    summary_table = Table(summary_data, colWidths=[2*inch, 2*inch, 2*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('FONTSIZE', (0, 1), (-1, 1), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 1), (-1, 1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 30))
    
    # Products table
    elements.append(Paragraph("Product Inventory", styles['Heading2']))
    elements.append(Spacer(1, 10))
    
    # Table header
    table_data = [['SKU', 'Product Name', 'Category', 'Stock', 'Price (£/m²)', 'Reorder', 'Status']]
    
    for p in products:
        status = 'LOW STOCK' if p.get('stock', 0) <= p.get('reorder_level', 10) else 'OK'
        table_data.append([
            p.get('sku', '')[:15],
            p.get('name', '')[:30],
            (p.get('category_name', '') or '-')[:15],
            str(p.get('stock', 0)),
            f"£{p.get('price', 0):.2f}",
            str(p.get('reorder_level', 10)),
            status
        ])
    
    col_widths = [1.2*inch, 2.5*inch, 1.3*inch, 0.8*inch, 1*inch, 0.8*inch, 0.9*inch]
    table = Table(table_data, colWidths=col_widths)
    
    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (3, 0), (5, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
    ])
    
    # Highlight low stock rows
    for i, p in enumerate(products, start=1):
        if p.get('stock', 0) <= p.get('reorder_level', 10):
            table_style.add('BACKGROUND', (6, i), (6, i), colors.HexColor('#fee2e2'))
            table_style.add('TEXTCOLOR', (6, i), (6, i), colors.HexColor('#dc2626'))
            table_style.add('FONTNAME', (6, i), (6, i), 'Helvetica-Bold')
    
    table.setStyle(table_style)
    elements.append(table)
    
    # Low stock section if any
    low_stock_products = [p for p in products if p.get('stock', 0) <= p.get('reorder_level', 10)]
    if low_stock_products:
        elements.append(Spacer(1, 30))
        elements.append(Paragraph("⚠️ Low Stock Alert", styles['Heading2']))
        elements.append(Spacer(1, 10))
        
        alert_data = [['SKU', 'Product Name', 'Current Stock', 'Reorder Level', 'Shortage']]
        for p in low_stock_products:
            shortage = p.get('reorder_level', 10) - p.get('stock', 0)
            alert_data.append([
                p.get('sku', ''),
                p.get('name', '')[:35],
                str(p.get('stock', 0)),
                str(p.get('reorder_level', 10)),
                str(max(0, shortage))
            ])
        
        alert_table = Table(alert_data, colWidths=[1.2*inch, 3*inch, 1.2*inch, 1.2*inch, 1*inch])
        alert_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#dc2626')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (2, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#fecaca')),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#fef2f2')),
        ]))
        elements.append(alert_table)
    
    doc.build(elements)
    buffer.seek(0)
    
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=inventory_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        }
    )

@api_router.get("/export/orders/csv")
async def export_orders_csv(current_user: dict = Depends(get_current_user)):
    """Export orders to CSV"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    orders = await db.orders.find({}, {"_id": 0}).sort("created_at", -1).to_list(10000)
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header row
    writer.writerow([
        'Order ID', 'Date', 'Customer Name', 'Customer Email', 'Phone',
        'Items', 'Total Amount (£)', 'Status'
    ])
    
    # Data rows
    for o in orders:
        items_str = '; '.join([f"{i.get('product_name', '')} x{i.get('quantity', 0)}" for i in o.get('items', [])])
        created_at = o.get('created_at', '')
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at).strftime('%d/%m/%Y %H:%M')
            except:
                pass
        
        writer.writerow([
            o.get('id', '')[-8:].upper(),
            created_at,
            o.get('customer_name', ''),
            o.get('customer_email', ''),
            o.get('phone_number', ''),
            items_str,
            f"{o.get('total_amount', 0):.2f}",
            o.get('status', 'pending').title()
        ])
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=orders_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        }
    )

@api_router.get("/export/orders/pdf")
async def export_orders_pdf(current_user: dict = Depends(get_current_user)):
    """Export orders to PDF"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    
    orders = await db.orders.find({}, {"_id": 0}).sort("created_at", -1).to_list(10000)
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1e40af'),
        spaceAfter=20
    )
    elements.append(Paragraph("Tile Station - Orders Report", title_style))
    elements.append(Paragraph(f"Generated: {datetime.now().strftime('%d %B %Y, %H:%M')}", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # Summary stats
    total_orders = len(orders)
    pending_orders = len([o for o in orders if o.get('status') == 'pending'])
    completed_orders = len([o for o in orders if o.get('status') == 'completed'])
    total_revenue = sum(o.get('total_amount', 0) for o in orders)
    
    summary_data = [
        ['Total Orders', 'Pending', 'Completed', 'Total Revenue'],
        [str(total_orders), str(pending_orders), str(completed_orders), f"£{total_revenue:.2f}"]
    ]
    summary_table = Table(summary_data, colWidths=[1.8*inch, 1.5*inch, 1.5*inch, 1.8*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('FONTSIZE', (0, 1), (-1, 1), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 1), (-1, 1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 30))
    
    # Orders table
    elements.append(Paragraph("Order Details", styles['Heading2']))
    elements.append(Spacer(1, 10))
    
    # Table header
    table_data = [['Order ID', 'Date', 'Customer', 'Items', 'Total', 'Status']]
    
    for o in orders:
        created_at = o.get('created_at', '')
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at).strftime('%d/%m/%Y')
            except:
                created_at = ''
        elif hasattr(created_at, 'strftime'):
            created_at = created_at.strftime('%d/%m/%Y')
        
        items_list = o.get('items', [])
        items_str = ', '.join([f"{i.get('product_name', '')[:20]} x{i.get('quantity', 0)}" for i in items_list[:3]])
        if len(items_list) > 3:
            items_str += f" +{len(items_list) - 3} more"
        
        status = o.get('status', 'pending').title()
        
        table_data.append([
            o.get('id', '')[-8:].upper(),
            created_at,
            o.get('customer_name', '')[:25],
            items_str[:40],
            f"£{o.get('total_amount', 0):.2f}",
            status
        ])
    
    col_widths = [1.1*inch, 0.9*inch, 2*inch, 3*inch, 1*inch, 1*inch]
    table = Table(table_data, colWidths=col_widths)
    
    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (4, 0), (5, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
    ])
    
    # Color code status column
    for i, o in enumerate(orders, start=1):
        status = o.get('status', 'pending')
        if status == 'pending':
            table_style.add('BACKGROUND', (5, i), (5, i), colors.HexColor('#fef3c7'))
            table_style.add('TEXTCOLOR', (5, i), (5, i), colors.HexColor('#92400e'))
        elif status == 'completed':
            table_style.add('BACKGROUND', (5, i), (5, i), colors.HexColor('#d1fae5'))
            table_style.add('TEXTCOLOR', (5, i), (5, i), colors.HexColor('#065f46'))
        elif status == 'cancelled':
            table_style.add('BACKGROUND', (5, i), (5, i), colors.HexColor('#fee2e2'))
            table_style.add('TEXTCOLOR', (5, i), (5, i), colors.HexColor('#dc2626'))
        elif status == 'processing':
            table_style.add('BACKGROUND', (5, i), (5, i), colors.HexColor('#dbeafe'))
            table_style.add('TEXTCOLOR', (5, i), (5, i), colors.HexColor('#1e40af'))
    
    table.setStyle(table_style)
    elements.append(table)
    
    doc.build(elements)
    buffer.seek(0)
    
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=orders_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        }
    )

# ============ SHOWROOM ENDPOINTS ============

@api_router.get("/showrooms")
async def get_showrooms(current_user: dict = Depends(get_current_user)):
    """Get all showrooms (admin only)"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    showrooms = await db.showrooms.find({}, {"_id": 0}).to_list(1000)
    return showrooms

@api_router.post("/showrooms")
async def create_showroom(input: StoreCreate, current_user: dict = Depends(get_current_user)):
    """Create a new showroom (admin only)"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    from uuid import uuid4
    showroom_id = str(uuid4())
    
    showroom_dict = {
        "id": showroom_id,
        "name": input.name,
        "address": input.address,
        "phone": input.phone,
        "email": input.email,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.showrooms.insert_one(showroom_dict)
    # Return without _id
    showroom = await db.showrooms.find_one({"id": showroom_id}, {"_id": 0})
    return showroom

@api_router.put("/showrooms/{showroom_id}")
async def update_showroom(showroom_id: str, input: StoreCreate, current_user: dict = Depends(get_current_user)):
    """Update a showroom (admin only)"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = await db.showrooms.update_one(
        {"id": showroom_id},
        {"$set": {
            "name": input.name,
            "address": input.address,
            "phone": input.phone,
            "email": input.email
        }}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Store not found")
    
    showroom = await db.showrooms.find_one({"id": showroom_id}, {"_id": 0})
    return showroom

@api_router.delete("/showrooms/{showroom_id}")
async def delete_showroom(showroom_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a showroom (admin only)"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = await db.showrooms.delete_one({"id": showroom_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Store not found")
    
    # Remove showroom association from customers
    await db.users.update_many(
        {"showroom_id": showroom_id},
        {"$set": {"showroom_id": None}}
    )
    
    return {"message": "Store deleted successfully"}

# ============ CUSTOMER MANAGEMENT ENDPOINTS ============

@api_router.get("/customers")
async def get_customers(
    showroom_id: Optional[str] = None,
    marketing_opt_in: Optional[bool] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all customers with optional filters (admin only)"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    query = {"role": "customer"}
    
    if showroom_id:
        query["showroom_id"] = showroom_id
    
    if marketing_opt_in is not None:
        query["marketing_opt_in"] = marketing_opt_in
    
    customers = await db.users.find(query, {"_id": 0, "password": 0}).to_list(10000)
    
    # Add showroom names
    showrooms = {s["id"]: s["name"] for s in await db.showrooms.find({}, {"_id": 0}).to_list(1000)}
    for customer in customers:
        if customer.get("showroom_id"):
            customer["showroom_name"] = showrooms.get(customer["showroom_id"], "Unknown")
    
    return customers

@api_router.put("/customers/{customer_email}/showroom")
async def assign_customer_showroom(
    customer_email: str,
    showroom_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Assign a customer to a showroom (admin only)"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = await db.users.update_one(
        {"email": customer_email, "role": "customer"},
        {"$set": {"showroom_id": showroom_id}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    return {"message": "Customer showroom updated"}

# ============ USER MANAGEMENT ENDPOINTS (Super Admin Only) ============

@api_router.get("/admin/users")
async def get_admin_users(current_user: dict = Depends(get_current_user)):
    """Get all admin/staff users (super_admin only)"""
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")
    
    # Get users who are not customers
    users = await db.users.find(
        {"role": {"$in": ["super_admin", "admin", "manager", "staff"]}},
        {"_id": 0, "password": 0}
    ).to_list(1000)
    
    # Add showroom names
    showrooms = {s["id"]: s["name"] for s in await db.showrooms.find({}, {"_id": 0}).to_list(1000)}
    for user in users:
        if user.get("showroom_id"):
            user["showroom_name"] = showrooms.get(user["showroom_id"], "Unknown")
    
    return users

@api_router.get("/admin/permissions")
async def get_available_permissions(current_user: dict = Depends(get_current_user)):
    """Get list of available permissions (super_admin only)"""
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")
    
    return {
        "permissions": AVAILABLE_PERMISSIONS,
        "roles": ["super_admin", "admin", "manager", "staff"]
    }

@api_router.put("/admin/users/{user_email}/permissions")
async def update_user_permissions(
    user_email: str,
    input: UserPermissionsUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update user role and permissions (super_admin only)"""
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")
    
    # Prevent modifying own super_admin role
    if user_email == current_user["email"] and input.role and input.role != "super_admin":
        raise HTTPException(status_code=400, detail="Cannot demote yourself from Super Admin")
    
    user = await db.users.find_one({"email": user_email}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_data = {}
    if input.role is not None:
        update_data["role"] = input.role
    if input.permissions is not None:
        # Validate permissions
        invalid = [p for p in input.permissions if p not in AVAILABLE_PERMISSIONS]
        if invalid:
            raise HTTPException(status_code=400, detail=f"Invalid permissions: {invalid}")
        update_data["permissions"] = input.permissions
    if input.showroom_id is not None:
        update_data["showroom_id"] = input.showroom_id
        # Get showroom name
        if input.showroom_id:
            showroom = await db.showrooms.find_one({"id": input.showroom_id}, {"_id": 0})
            update_data["showroom_name"] = showroom["name"] if showroom else None
        else:
            update_data["showroom_name"] = None
    
    if update_data:
        await db.users.update_one({"email": user_email}, {"$set": update_data})
    
    return {"message": "User permissions updated successfully"}

@api_router.post("/admin/users")
async def create_admin_user(input: UserRegister, current_user: dict = Depends(get_current_user)):
    """Create a new admin/staff user (super_admin only)"""
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")
    
    # Check if email already exists
    existing = await db.users.find_one({"email": input.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Validate role
    if input.role not in ["admin", "manager", "staff"]:
        raise HTTPException(status_code=400, detail="Invalid role. Use: admin, manager, or staff")
    
    from uuid import uuid4
    
    # Get showroom name if provided
    showroom_name = None
    if input.showroom_id:
        showroom = await db.showrooms.find_one({"id": input.showroom_id}, {"_id": 0})
        if showroom:
            showroom_name = showroom["name"]
    
    user_dict = {
        "id": str(uuid4()),
        "email": input.email,
        "password": hash_password(input.password),
        "name": input.name,
        "role": input.role,
        "phone": input.phone,
        "showroom_id": input.showroom_id,
        "showroom_name": showroom_name,
        "permissions": [],  # Empty by default, super admin will set
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.users.insert_one(user_dict)
    
    return {
        "message": "User created successfully",
        "email": input.email,
        "role": input.role
    }

@api_router.delete("/admin/users/{user_email}")
async def delete_admin_user(user_email: str, current_user: dict = Depends(get_current_user)):
    """Delete an admin/staff user (super_admin only)"""
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")
    
    # Prevent self-deletion
    if user_email == current_user["email"]:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    user = await db.users.find_one({"email": user_email}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent deleting other super admins
    if user.get("role") == "super_admin":
        raise HTTPException(status_code=400, detail="Cannot delete Super Admin accounts")
    
    result = await db.users.delete_one({"email": user_email})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "User deleted successfully"}

# ============ AUDIT LOG ENDPOINTS (Super Admin Only) ============

@api_router.get("/audit-logs")
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

@api_router.get("/audit-logs/{log_id}")
async def get_audit_log_detail(log_id: str, current_user: dict = Depends(get_current_user)):
    """Get detailed audit log entry with before/after values (super_admin only)"""
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")
    
    log = await db.audit_logs.find_one({"id": log_id}, {"_id": 0})
    if not log:
        raise HTTPException(status_code=404, detail="Audit log not found")
    
    return log

@api_router.get("/audit-logs/entity/{entity_type}/{entity_id}")
async def get_entity_audit_history(
    entity_type: str, 
    entity_id: str, 
    current_user: dict = Depends(get_current_user)
):
    """Get audit history for a specific entity (super_admin only)"""
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")
    
    logs = await db.audit_logs.find(
        {"entity_type": entity_type, "entity_id": entity_id},
        {"_id": 0}
    ).sort("timestamp", -1).to_list(100)
    
    return logs

@api_router.get("/audit-logs/stats")
async def get_audit_stats(current_user: dict = Depends(get_current_user)):
    """Get audit log statistics (super_admin only)"""
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")
    
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

# ============ STAFF INVITE ENDPOINTS (Super Admin Only) ============

@api_router.post("/staff-invites")
async def create_staff_invite(input: StaffInviteCreate, current_user: dict = Depends(get_current_user)):
    """Create a staff/admin invite link (super_admin only)"""
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")
    
    # Validate role
    if input.role not in ["admin", "manager", "staff"]:
        raise HTTPException(status_code=400, detail="Invalid role. Use: admin, manager, or staff")
    
    # Validate permissions
    invalid = [p for p in input.permissions if p not in AVAILABLE_PERMISSIONS]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Invalid permissions: {invalid}")
    
    from uuid import uuid4
    import secrets
    
    # Get showroom name if provided
    showroom_name = None
    if input.showroom_id:
        showroom = await db.showrooms.find_one({"id": input.showroom_id}, {"_id": 0})
        if showroom:
            showroom_name = showroom["name"]
    
    # Generate unique invite code
    invite_code = secrets.token_urlsafe(16)
    
    invite_dict = {
        "id": str(uuid4()),
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

@api_router.get("/staff-invites")
async def get_staff_invites(current_user: dict = Depends(get_current_user)):
    """Get all staff invites (super_admin only)"""
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")
    
    invites = await db.staff_invites.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return invites

@api_router.get("/staff-invites/{code}/validate")
async def validate_staff_invite(code: str):
    """Validate a staff invite code (public endpoint for registration)"""
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

@api_router.post("/staff-invites/{code}/register")
async def register_with_staff_invite(code: str, registration: StaffRegistration):
    """Register a new staff/admin user using an invite code"""
    from uuid import uuid4
    
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
        "id": str(uuid4()),
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
    
    # Generate token - use "sub" key to match get_current_user expectation
    token = jwt.encode(
        {"sub": registration.email, "role": invite["role"], "exp": datetime.now(timezone.utc) + timedelta(days=7)},
        SECRET_KEY,
        algorithm="HS256"
    )
    
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

@api_router.delete("/staff-invites/{invite_id}")
async def delete_staff_invite(invite_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a staff invite (super_admin only)"""
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")
    
    result = await db.staff_invites.delete_one({"id": invite_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Invite not found")
    
    return {"message": "Invite deleted successfully"}

# ============ MARKETING CAMPAIGN ENDPOINTS ============

@api_router.get("/marketing/campaigns")
async def get_campaigns(current_user: dict = Depends(get_current_user)):
    """Get all marketing campaigns (admin only)"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    campaigns = await db.marketing_campaigns.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return campaigns

@api_router.post("/marketing/campaigns")
async def create_campaign(input: MarketingCampaignCreate, current_user: dict = Depends(get_current_user)):
    """Create a new marketing campaign (admin only)"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    from uuid import uuid4
    campaign_id = str(uuid4())
    
    campaign_dict = {
        "id": campaign_id,
        "name": input.name,
        "subject": input.subject,
        "content": input.content,
        "campaign_type": input.campaign_type,
        "target_audience": input.target_audience,
        "target_showroom_id": input.target_showroom_id,
        "status": "draft",
        "sent_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sent_at": None
    }
    
    await db.marketing_campaigns.insert_one(campaign_dict)
    return campaign_dict

@api_router.post("/marketing/campaigns/{campaign_id}/send")
async def send_campaign(campaign_id: str, current_user: dict = Depends(get_current_user)):
    """Send a marketing campaign to targeted customers (admin only)"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    campaign = await db.marketing_campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    if campaign.get("status") == "sent":
        raise HTTPException(status_code=400, detail="Campaign already sent")
    
    # Build query for target customers
    query = {"role": "customer"}
    
    if campaign.get("target_audience") == "opted_in":
        query["marketing_opt_in"] = True
    elif campaign.get("target_audience") == "store" and campaign.get("target_showroom_id"):
        query["showroom_id"] = campaign["target_showroom_id"]
        query["marketing_opt_in"] = True
    
    customers = await db.users.find(query, {"_id": 0, "email": 1, "name": 1}).to_list(10000)
    
    if not customers:
        raise HTTPException(status_code=400, detail="No customers match the target criteria")
    
    # Send emails using Resend
    sent_count = 0
    failed_count = 0
    
    if RESEND_AVAILABLE and RESEND_API_KEY:
        for customer in customers:
            try:
                params = {
                    "from": SENDER_EMAIL,
                    "to": [customer["email"]],
                    "subject": campaign["subject"],
                    "html": f"""
                    <!DOCTYPE html>
                    <html>
                    <head><meta charset="utf-8"></head>
                    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                        <div style="text-align: center; margin-bottom: 30px;">
                            <h1 style="color: #1e40af;">Tile Station</h1>
                        </div>
                        <p>Dear {customer.get('name', 'Valued Customer')},</p>
                        <div style="margin: 20px 0;">
                            {campaign['content']}
                        </div>
                        <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                        <p style="color: #888; font-size: 12px; text-align: center;">
                            You received this email because you opted in to marketing communications from Tile Station.
                            <br>To unsubscribe, please contact us.
                        </p>
                    </body>
                    </html>
                    """
                }
                
                await asyncio.to_thread(resend.Emails.send, params)
                sent_count += 1
            except Exception as e:
                logging.error(f"Failed to send email to {customer['email']}: {e}")
                failed_count += 1
    else:
        # Demo mode - just count customers
        sent_count = len(customers)
    
    # Update campaign status
    await db.marketing_campaigns.update_one(
        {"id": campaign_id},
        {"$set": {
            "status": "sent",
            "sent_count": sent_count,
            "sent_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    return {
        "message": f"Campaign sent successfully",
        "sent_count": sent_count,
        "failed_count": failed_count,
        "total_recipients": len(customers)
    }

@api_router.delete("/marketing/campaigns/{campaign_id}")
async def delete_campaign(campaign_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a marketing campaign (admin only)"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = await db.marketing_campaigns.delete_one({"id": campaign_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    return {"message": "Campaign deleted successfully"}

@api_router.get("/marketing/stats")
async def get_marketing_stats(current_user: dict = Depends(get_current_user)):
    """Get marketing statistics (admin only)"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    total_customers = await db.users.count_documents({"role": "customer"})
    opted_in_customers = await db.users.count_documents({"role": "customer", "marketing_opt_in": True})
    total_campaigns = await db.marketing_campaigns.count_documents({})
    sent_campaigns = await db.marketing_campaigns.count_documents({"status": "sent"})
    
    # Get customers by showroom
    showrooms = await db.showrooms.find({}, {"_id": 0}).to_list(1000)
    showroom_stats = []
    for showroom in showrooms:
        count = await db.users.count_documents({"role": "customer", "showroom_id": showroom["id"]})
        showroom_stats.append({
            "showroom_id": showroom["id"],
            "showroom_name": showroom["name"],
            "customer_count": count
        })
    
    return {
        "total_customers": total_customers,
        "opted_in_customers": opted_in_customers,
        "total_campaigns": total_campaigns,
        "sent_campaigns": sent_campaigns,
        "showroom_stats": showroom_stats
    }

# ============ INVOICE ENDPOINTS ============

@api_router.post("/invoices")
async def save_invoice(input: InvoiceCreate, current_user: dict = Depends(get_current_user)):
    """Save invoice and update product stock (admin only)"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    from uuid import uuid4
    
    # Verify staff PIN if provided
    staff_member = None
    if input.staff_pin:
        staff_member = await db.staff_pins.find_one({"pin": input.staff_pin, "active": True}, {"_id": 0})
        if not staff_member:
            raise HTTPException(status_code=401, detail="Invalid staff PIN")
    
    # Update stock for each item (allow negative stock)
    for item in input.line_items:
        product = await db.products.find_one({"id": item.product_id}, {"_id": 0})
        if not product:
            raise HTTPException(status_code=404, detail=f"Product not found: {item.product_name}")
        
        new_stock = product.get("stock", 0) - int(item.quantity)
        # Allow negative stock - just update it
        
        # Update product stock
        await db.products.update_one(
            {"id": item.product_id},
            {"$set": {"stock": new_stock}}
        )
    
    # Save invoice
    invoice_dict = {
        "id": str(uuid4()),
        "invoice_no": input.invoice_no,
        "date": input.date,
        "time": input.time,
        "customer_name": input.customer_name,
        "customer_phone": input.customer_phone,
        "customer_email": input.customer_email,
        "customer_address": input.customer_address,
        "notes": input.notes,
        "sales_person": staff_member["name"] if staff_member else input.sales_person,
        "staff_id": staff_member["id"] if staff_member else None,
        "staff_name": staff_member["name"] if staff_member else None,
        "payment_method": input.payment_method,
        "showroom_id": input.showroom_id,
        "showroom_name": input.showroom_name,
        "deposits": [d.dict() for d in input.deposits] if input.deposits else [],
        "line_items": [item.dict() for item in input.line_items],
        "subtotal": input.subtotal,
        "vat": input.vat,
        "gross_total": input.gross_total,
        "total_savings": input.total_savings,
        "created_by": current_user["email"],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    # Calculate status based on payment
    # If deposits exist, calculate total deposits and outstanding
    total_deposits = sum(d.amount for d in input.deposits) if input.deposits else 0
    amount_outstanding = input.gross_total - total_deposits
    
    # Determine status:
    # - If paid in full (no outstanding) -> "open_order" (can progress to processing -> completed)
    # - If deposit taken with outstanding amount -> "deposit_order"
    if total_deposits > 0 and amount_outstanding > 0.01:  # Small threshold for float comparison
        invoice_dict["status"] = "deposit_order"
    else:
        invoice_dict["status"] = "open_order"
    
    # Store calculated values
    invoice_dict["total_deposits"] = total_deposits
    invoice_dict["amount_outstanding"] = max(0, amount_outstanding)
    
    await db.invoices.insert_one(invoice_dict)
    
    # Log audit trail
    await log_audit(
        action="CREATE",
        entity_type="invoice",
        user=current_user,
        entity_id=invoice_dict["id"],
        entity_name=invoice_dict["invoice_no"],
        after_data={
            "invoice_no": invoice_dict["invoice_no"],
            "customer_name": invoice_dict.get("customer_name"),
            "gross_total": invoice_dict["gross_total"],
            "showroom_name": invoice_dict.get("showroom_name"),
            "items_count": len(invoice_dict["line_items"])
        },
        details=f"Invoice {invoice_dict['invoice_no']} created for £{invoice_dict['gross_total']:.2f}"
    )
    
    # Send order confirmation email if customer email is provided
    email_sent = False
    if input.customer_email and RESEND_AVAILABLE and RESEND_API_KEY:
        try:
            await send_order_confirmation_email(invoice_dict)
            email_sent = True
        except Exception as e:
            logging.error(f"Failed to send order confirmation email: {e}")
    
    return {
        "message": "Invoice saved and stock updated",
        "invoice_id": invoice_dict["id"],
        "invoice_no": invoice_dict["invoice_no"],
        "staff_name": staff_member["name"] if staff_member else None,
        "email_sent": email_sent
    }

@api_router.get("/invoices")
async def get_invoices(
    current_user: dict = Depends(get_current_user),
    search: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    staff_id: Optional[str] = None
):
    """Get all invoices with optional search and filters (admin only)"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Build query
    query = {}
    
    if search:
        # Search in invoice_no, customer_name, customer_phone, customer_email, staff_name
        query["$or"] = [
            {"invoice_no": {"$regex": search, "$options": "i"}},
            {"customer_name": {"$regex": search, "$options": "i"}},
            {"customer_phone": {"$regex": search, "$options": "i"}},
            {"customer_email": {"$regex": search, "$options": "i"}},
            {"staff_name": {"$regex": search, "$options": "i"}},
        ]
    
    if staff_id:
        query["staff_id"] = staff_id
    
    invoices = await db.invoices.find(query, {"_id": 0}).sort("created_at", -1).to_list(10000)
    return invoices

@api_router.get("/invoices/{invoice_id}")
async def get_invoice(invoice_id: str, current_user: dict = Depends(get_current_user)):
    """Get single invoice (admin only)"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    invoice = await db.invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    return invoice

@api_router.put("/invoices/{invoice_id}")
async def update_invoice(invoice_id: str, input: InvoiceUpdate, current_user: dict = Depends(get_current_user)):
    """Update an existing invoice (admin only)"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Get existing invoice
    existing = await db.invoices.find_one({"id": invoice_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Verify staff PIN if provided
    staff_member = None
    if input.staff_pin:
        staff_member = await db.staff_pins.find_one({"pin": input.staff_pin, "active": True}, {"_id": 0})
        if not staff_member:
            raise HTTPException(status_code=401, detail="Invalid staff PIN")
    
    # Handle stock adjustments if line items changed
    if input.line_items is not None:
        old_items = {item["product_id"]: item["quantity"] for item in existing.get("line_items", [])}
        new_items = {item.product_id: item.quantity for item in input.line_items}
        
        # Restore old stock and apply new stock
        for product_id, old_qty in old_items.items():
            await db.products.update_one(
                {"id": product_id},
                {"$inc": {"stock": int(old_qty)}}  # Restore old quantity
            )
        
        for item in input.line_items:
            product = await db.products.find_one({"id": item.product_id}, {"_id": 0})
            if not product:
                raise HTTPException(status_code=404, detail=f"Product not found: {item.product_name}")
            
            new_stock = product.get("stock", 0) - int(item.quantity)
            # Allow negative stock
            
            await db.products.update_one(
                {"id": item.product_id},
                {"$set": {"stock": new_stock}}
            )
    
    # Build update data
    update_data = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": current_user["email"]
    }
    
    if input.invoice_no is not None:
        update_data["invoice_no"] = input.invoice_no
    if input.date is not None:
        update_data["date"] = input.date
    if input.time is not None:
        update_data["time"] = input.time
    if input.customer_name is not None:
        update_data["customer_name"] = input.customer_name
    if input.customer_phone is not None:
        update_data["customer_phone"] = input.customer_phone
    if input.customer_email is not None:
        update_data["customer_email"] = input.customer_email
    if input.customer_address is not None:
        update_data["customer_address"] = input.customer_address
    if input.notes is not None:
        update_data["notes"] = input.notes
    if input.payment_method is not None:
        update_data["payment_method"] = input.payment_method
    if input.line_items is not None:
        update_data["line_items"] = [item.dict() for item in input.line_items]
    if input.subtotal is not None:
        update_data["subtotal"] = input.subtotal
    if input.vat is not None:
        update_data["vat"] = input.vat
    if input.gross_total is not None:
        update_data["gross_total"] = input.gross_total
    if input.total_savings is not None:
        update_data["total_savings"] = input.total_savings
    if input.deposits is not None:
        update_data["deposits"] = [d.dict() for d in input.deposits]
    
    # Update staff info if PIN provided
    if staff_member:
        update_data["sales_person"] = staff_member["name"]
        update_data["staff_id"] = staff_member["id"]
        update_data["staff_name"] = staff_member["name"]
    elif input.sales_person is not None:
        update_data["sales_person"] = input.sales_person
    
    # Handle status update
    if input.status is not None:
        # Validate status transitions
        valid_statuses = ["open_order", "deposit_order", "processing", "completed"]
        if input.status in valid_statuses:
            update_data["status"] = input.status
    
    # Recalculate status based on deposits if deposits are being updated
    if input.deposits is not None:
        total_deposits = sum(d.amount for d in input.deposits) if input.deposits else 0
        gross_total = input.gross_total if input.gross_total is not None else existing.get("gross_total", 0)
        amount_outstanding = gross_total - total_deposits
        
        update_data["total_deposits"] = total_deposits
        update_data["amount_outstanding"] = max(0, amount_outstanding)
        
        # Auto-update status based on payment if not explicitly set
        if input.status is None:
            current_status = existing.get("status", "open_order")
            # If was deposit_order and now paid in full, move to open_order
            if current_status == "deposit_order" and amount_outstanding <= 0.01:
                update_data["status"] = "open_order"
            # If deposits taken with outstanding, set to deposit_order
            elif total_deposits > 0 and amount_outstanding > 0.01:
                update_data["status"] = "deposit_order"
    
    await db.invoices.update_one({"id": invoice_id}, {"$set": update_data})
    
    # Log audit trail
    before_summary = {
        "invoice_no": existing.get("invoice_no"),
        "customer_name": existing.get("customer_name"),
        "gross_total": existing.get("gross_total"),
        "payment_method": existing.get("payment_method")
    }
    after_summary = {
        "invoice_no": update_data.get("invoice_no", existing.get("invoice_no")),
        "customer_name": update_data.get("customer_name", existing.get("customer_name")),
        "gross_total": update_data.get("gross_total", existing.get("gross_total")),
        "payment_method": update_data.get("payment_method", existing.get("payment_method"))
    }
    await log_audit(
        action="UPDATE",
        entity_type="invoice",
        user=current_user,
        entity_id=invoice_id,
        entity_name=existing.get("invoice_no"),
        before_data=before_summary,
        after_data=after_summary,
        details=f"Invoice {existing.get('invoice_no')} updated"
    )
    
    return {
        "message": "Invoice updated successfully",
        "invoice_id": invoice_id,
        "staff_name": staff_member["name"] if staff_member else None
    }

@api_router.delete("/invoices/{invoice_id}")
async def delete_invoice(invoice_id: str, current_user: dict = Depends(get_current_user)):
    """Delete an invoice and restore stock (admin only)"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Get existing invoice
    invoice = await db.invoices.find_one({"id": invoice_id})
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Restore stock for all line items
    for item in invoice.get("line_items", []):
        await db.products.update_one(
            {"id": item["product_id"]},
            {"$inc": {"stock": int(item["quantity"])}}
        )
    
    # Delete the invoice
    await db.invoices.delete_one({"id": invoice_id})
    
    # Log audit trail
    await log_audit(
        action="DELETE",
        entity_type="invoice",
        user=current_user,
        entity_id=invoice_id,
        entity_name=invoice.get("invoice_no"),
        before_data={
            "invoice_no": invoice.get("invoice_no"),
            "customer_name": invoice.get("customer_name"),
            "gross_total": invoice.get("gross_total"),
            "items_count": len(invoice.get("line_items", []))
        },
        details=f"Invoice {invoice.get('invoice_no')} deleted, stock restored"
    )
    
    return {"message": "Invoice deleted and stock restored"}

@api_router.patch("/invoices/{invoice_id}/status")
async def update_invoice_status(
    invoice_id: str, 
    status: str,
    current_user: dict = Depends(get_current_user)
):
    """Update invoice status (admin only).
    Status flow: open_order -> processing -> completed
    Or if deposit: deposit_order -> (paid in full) -> open_order -> processing -> completed
    """
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    valid_statuses = ["open_order", "deposit_order", "processing", "completed"]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    
    invoice = await db.invoices.find_one({"id": invoice_id})
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    old_status = invoice.get("status", "open_order")
    
    # Update status
    await db.invoices.update_one(
        {"id": invoice_id},
        {"$set": {
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_by": current_user["email"]
        }}
    )
    
    # Log audit trail
    await log_audit(
        action="UPDATE",
        entity_type="invoice",
        user=current_user,
        entity_id=invoice_id,
        entity_name=invoice.get("invoice_no"),
        before_data={"status": old_status},
        after_data={"status": status},
        details=f"Invoice {invoice.get('invoice_no')} status changed: {old_status} -> {status}"
    )
    
    return {
        "message": f"Invoice status updated to {status}",
        "invoice_id": invoice_id,
        "old_status": old_status,
        "new_status": status
    }


@api_router.get("/invoices/{invoice_id}/pdf")
async def generate_invoice_pdf(invoice_id: str, current_user: dict = Depends(get_current_user)):
    """Generate PDF for an invoice"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if not REPORTLAB_AVAILABLE:
        raise HTTPException(status_code=500, detail="PDF generation not available")
    
    # Get the invoice
    invoice = await db.invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Create PDF in memory
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=15*mm, bottomMargin=15*mm, leftMargin=15*mm, rightMargin=15*mm)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=24, alignment=TA_CENTER, spaceAfter=5*mm)
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=10, alignment=TA_CENTER, textColor=colors.grey)
    header_style = ParagraphStyle('Header', parent=styles['Heading2'], fontSize=12, spaceAfter=3*mm)
    normal_style = ParagraphStyle('Normal', parent=styles['Normal'], fontSize=10)
    small_style = ParagraphStyle('Small', parent=styles['Normal'], fontSize=8, textColor=colors.grey)
    
    # Company Header
    elements.append(Paragraph("TILE STATION", title_style))
    elements.append(Paragraph("Unit 3 Trade City Coldharbour Road, Northfleet Gravesend DA11 8AB", subtitle_style))
    elements.append(Paragraph("Tel: 01474 878 989 | Email: gravesend@tilestation.co.uk", subtitle_style))
    elements.append(Paragraph("Company No: 11982550 | VAT No: 324 251 828", subtitle_style))
    elements.append(Spacer(1, 10*mm))
    
    # Invoice Title
    elements.append(Paragraph(f"<b>INVOICE</b>", ParagraphStyle('InvTitle', fontSize=18, alignment=TA_CENTER, spaceAfter=5*mm)))
    elements.append(Spacer(1, 5*mm))
    
    # Invoice Details & Customer Details side by side
    invoice_info = [
        ["Invoice No:", invoice.get("invoice_no", "N/A")],
        ["Date:", invoice.get("date", "N/A")],
        ["Time:", invoice.get("time", "N/A")],
        ["Payment Method:", invoice.get("payment_method", "N/A")],
        ["Sales Person:", invoice.get("sales_person") or invoice.get("staff_name") or "N/A"],
    ]
    
    customer_info = [
        ["Customer:", invoice.get("customer_name") or "N/A"],
        ["Phone:", invoice.get("customer_phone") or "N/A"],
        ["Email:", invoice.get("customer_email") or "N/A"],
        ["Address:", invoice.get("customer_address") or "N/A"],
    ]
    
    # Create two column layout for details
    left_table = Table(invoice_info, colWidths=[35*mm, 50*mm])
    left_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    
    right_table = Table(customer_info, colWidths=[30*mm, 55*mm])
    right_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    
    details_table = Table([[left_table, right_table]], colWidths=[90*mm, 90*mm])
    elements.append(details_table)
    elements.append(Spacer(1, 8*mm))
    
    # Line Items Table
    line_items = invoice.get("line_items", [])
    table_data = [["Qty", "m²", "Product", "Unit Price", "Discount", "Total"]]
    
    for item in line_items:
        qty = item.get("quantity", 0)
        m2 = item.get("m2", 0)
        price = item.get("price", 0)
        discount = item.get("discount", 0)
        subtotal = qty * price
        discount_amount = subtotal * (discount / 100)
        total = subtotal - discount_amount
        
        table_data.append([
            str(int(qty)) if qty == int(qty) else str(qty),
            f"{m2:.2f}" if m2 else "-",
            item.get("product_name", "N/A"),
            f"£{price:.2f}",
            f"{discount}%" if discount else "-",
            f"£{total:.2f}"
        ])
    
    # Add totals rows
    subtotal = invoice.get("subtotal", 0)
    vat = invoice.get("vat", 0)
    gross_total = invoice.get("gross_total", 0)
    total_savings = invoice.get("total_savings", 0)
    
    table_data.append(["", "", "", "", "Subtotal:", f"£{subtotal:.2f}"])
    if total_savings > 0:
        table_data.append(["", "", "", "", "Savings:", f"£{total_savings:.2f}"])
    table_data.append(["", "", "", "", "VAT (20%):", f"£{vat:.2f}"])
    table_data.append(["", "", "", "", "GROSS TOTAL:", f"£{gross_total:.2f}"])
    
    items_table = Table(table_data, colWidths=[15*mm, 15*mm, 70*mm, 25*mm, 25*mm, 30*mm])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (1, -1), 'CENTER'),
        ('ALIGN', (3, 0), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, len(line_items)), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        # Totals styling
        ('FONTNAME', (4, len(line_items)+1), (4, -1), 'Helvetica-Bold'),
        ('FONTNAME', (5, -1), (5, -1), 'Helvetica-Bold'),
        ('LINEABOVE', (4, len(line_items)+1), (-1, len(line_items)+1), 1, colors.black),
        ('BACKGROUND', (4, -1), (-1, -1), colors.HexColor('#f5f5f5')),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 5*mm))
    
    # Deposits section
    deposits = invoice.get("deposits", [])
    if deposits and len(deposits) > 0:
        valid_deposits = [d for d in deposits if d.get("amount") and float(d.get("amount", 0)) > 0]
        if valid_deposits:
            elements.append(Spacer(1, 3*mm))
            deposit_data = [["Date", "Amount Taken", "Outstanding"]]
            running_balance = gross_total
            for dep in valid_deposits:
                amount = float(dep.get("amount", 0))
                running_balance -= amount
                deposit_data.append([
                    dep.get("date", "N/A"),
                    f"£{amount:.2f}",
                    f"£{running_balance:.2f}"
                ])
            
            deposit_table = Table(deposit_data, colWidths=[50*mm, 50*mm, 50*mm])
            deposit_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('ALIGN', (0, 0), (0, -1), 'CENTER'),
                ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
            ]))
            elements.append(deposit_table)
            
            # Deposit Order warning
            total_deposits = sum(float(d.get("amount", 0)) for d in valid_deposits)
            if running_balance > 0:
                elements.append(Spacer(1, 3*mm))
                warning_style = ParagraphStyle('Warning', fontSize=10, textColor=colors.HexColor('#92400e'), alignment=TA_CENTER)
                elements.append(Paragraph(f"<b>⚠ DEPOSIT ORDER - Outstanding Balance: £{running_balance:.2f}</b>", warning_style))
    
    elements.append(Spacer(1, 8*mm))
    
    # Tagline
    tagline_style = ParagraphStyle('Tagline', fontSize=11, alignment=TA_CENTER, spaceAfter=5*mm)
    elements.append(Paragraph("<b>Amazing Tiles - Beautiful Bathrooms - Excellent Service</b>", tagline_style))
    elements.append(Spacer(1, 5*mm))
    
    # Terms and Conditions
    elements.append(Paragraph("<b>Terms and Conditions:</b>", ParagraphStyle('Terms', fontSize=9, spaceAfter=2*mm)))
    terms = """REFUNDS: Any unwanted Full packs of STOCKED TILES will occur a 20% restocking charge. Only 10% of total tiles purchased will be refunded within 28 days. SPECIAL-ORDER TILES will occur a 50% restocking charge. BATHROOM PRODUCTS are non-refundable. CANCELLATIONS: STOCKED TILES 20% charge, SPECIAL-ORDER TILES 30% charge, BATHROOM PRODUCTS 50% charge within 28 days. DELIVERY: Kerbside delivery only. Assistance required to unload. Re-delivery will occur additional charges. Broken tiles must be reported within 48 hours with photo proof."""
    elements.append(Paragraph(terms, ParagraphStyle('TermsText', fontSize=7, textColor=colors.grey, leading=9)))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    # Return PDF
    filename = f"Invoice_{invoice.get('invoice_no', 'unknown')}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# Helper function to generate PDF bytes (reused by email endpoint)
async def generate_invoice_pdf_bytes(invoice: dict) -> bytes:
    """Generate PDF bytes for an invoice"""
    if not REPORTLAB_AVAILABLE:
        raise HTTPException(status_code=500, detail="PDF generation not available")
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=15*mm, bottomMargin=15*mm, leftMargin=15*mm, rightMargin=15*mm)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=24, alignment=TA_CENTER, spaceAfter=5*mm)
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=10, alignment=TA_CENTER, textColor=colors.grey)
    
    # Company Header
    elements.append(Paragraph("TILE STATION", title_style))
    elements.append(Paragraph("Unit 3 Trade City Coldharbour Road, Northfleet Gravesend DA11 8AB", subtitle_style))
    elements.append(Paragraph("Tel: 01474 878 989 | Email: gravesend@tilestation.co.uk", subtitle_style))
    elements.append(Paragraph("Company No: 11982550 | VAT No: 324 251 828", subtitle_style))
    elements.append(Spacer(1, 10*mm))
    
    # Invoice Title
    elements.append(Paragraph(f"<b>INVOICE</b>", ParagraphStyle('InvTitle', fontSize=18, alignment=TA_CENTER, spaceAfter=5*mm)))
    elements.append(Spacer(1, 5*mm))
    
    # Invoice Details & Customer Details
    invoice_info = [
        ["Invoice No:", invoice.get("invoice_no", "N/A")],
        ["Date:", invoice.get("date", "N/A")],
        ["Time:", invoice.get("time", "N/A")],
        ["Payment Method:", invoice.get("payment_method", "N/A")],
        ["Sales Person:", invoice.get("sales_person") or invoice.get("staff_name") or "N/A"],
    ]
    
    customer_info = [
        ["Customer:", invoice.get("customer_name") or "N/A"],
        ["Phone:", invoice.get("customer_phone") or "N/A"],
        ["Email:", invoice.get("customer_email") or "N/A"],
        ["Address:", invoice.get("customer_address") or "N/A"],
    ]
    
    left_table = Table(invoice_info, colWidths=[35*mm, 50*mm])
    left_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    
    right_table = Table(customer_info, colWidths=[30*mm, 55*mm])
    right_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    
    details_table = Table([[left_table, right_table]], colWidths=[90*mm, 90*mm])
    elements.append(details_table)
    elements.append(Spacer(1, 8*mm))
    
    # Line Items Table
    line_items = invoice.get("line_items", [])
    table_data = [["Qty", "m²", "Product", "Unit Price", "Discount", "Total"]]
    
    for item in line_items:
        qty = item.get("quantity", 0)
        m2 = item.get("m2", 0)
        price = item.get("price", 0)
        discount = item.get("discount", 0)
        subtotal = qty * price
        discount_amount = subtotal * (discount / 100)
        total = subtotal - discount_amount
        
        table_data.append([
            str(int(qty)) if qty == int(qty) else str(qty),
            f"{m2:.2f}" if m2 else "-",
            item.get("product_name", "N/A"),
            f"£{price:.2f}",
            f"{discount}%" if discount else "-",
            f"£{total:.2f}"
        ])
    
    subtotal_val = invoice.get("subtotal", 0)
    vat = invoice.get("vat", 0)
    gross_total = invoice.get("gross_total", 0)
    total_savings = invoice.get("total_savings", 0)
    
    table_data.append(["", "", "", "", "Subtotal:", f"£{subtotal_val:.2f}"])
    if total_savings > 0:
        table_data.append(["", "", "", "", "Savings:", f"£{total_savings:.2f}"])
    table_data.append(["", "", "", "", "VAT (20%):", f"£{vat:.2f}"])
    table_data.append(["", "", "", "", "GROSS TOTAL:", f"£{gross_total:.2f}"])
    
    items_table = Table(table_data, colWidths=[15*mm, 15*mm, 70*mm, 25*mm, 25*mm, 30*mm])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (1, -1), 'CENTER'),
        ('ALIGN', (3, 0), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, len(line_items)), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('FONTNAME', (4, len(line_items)+1), (4, -1), 'Helvetica-Bold'),
        ('FONTNAME', (5, -1), (5, -1), 'Helvetica-Bold'),
        ('LINEABOVE', (4, len(line_items)+1), (-1, len(line_items)+1), 1, colors.black),
        ('BACKGROUND', (4, -1), (-1, -1), colors.HexColor('#f5f5f5')),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 5*mm))
    
    # Deposits section
    deposits = invoice.get("deposits", [])
    if deposits and len(deposits) > 0:
        valid_deposits = [d for d in deposits if d.get("amount") and float(d.get("amount", 0)) > 0]
        if valid_deposits:
            elements.append(Spacer(1, 3*mm))
            deposit_data = [["Date", "Amount Taken", "Outstanding"]]
            running_balance = gross_total
            for dep in valid_deposits:
                amount = float(dep.get("amount", 0))
                running_balance -= amount
                deposit_data.append([
                    dep.get("date", "N/A"),
                    f"£{amount:.2f}",
                    f"£{running_balance:.2f}"
                ])
            
            deposit_table = Table(deposit_data, colWidths=[50*mm, 50*mm, 50*mm])
            deposit_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('ALIGN', (0, 0), (0, -1), 'CENTER'),
                ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
            ]))
            elements.append(deposit_table)
            
            if running_balance > 0:
                elements.append(Spacer(1, 3*mm))
                warning_style = ParagraphStyle('Warning', fontSize=10, textColor=colors.HexColor('#92400e'), alignment=TA_CENTER)
                elements.append(Paragraph(f"<b>DEPOSIT ORDER - Outstanding Balance: £{running_balance:.2f}</b>", warning_style))
    
    elements.append(Spacer(1, 8*mm))
    
    # Tagline
    tagline_style = ParagraphStyle('Tagline', fontSize=11, alignment=TA_CENTER, spaceAfter=5*mm)
    elements.append(Paragraph("<b>Amazing Tiles - Beautiful Bathrooms - Excellent Service</b>", tagline_style))
    elements.append(Spacer(1, 5*mm))
    
    # Terms
    elements.append(Paragraph("<b>Terms and Conditions:</b>", ParagraphStyle('Terms', fontSize=9, spaceAfter=2*mm)))
    terms = """REFUNDS: Any unwanted Full packs of STOCKED TILES will occur a 20% restocking charge. Only 10% of total tiles purchased will be refunded within 28 days. SPECIAL-ORDER TILES will occur a 50% restocking charge. BATHROOM PRODUCTS are non-refundable. CANCELLATIONS: STOCKED TILES 20% charge, SPECIAL-ORDER TILES 30% charge, BATHROOM PRODUCTS 50% charge within 28 days. DELIVERY: Kerbside delivery only. Assistance required to unload. Re-delivery will occur additional charges. Broken tiles must be reported within 48 hours with photo proof."""
    elements.append(Paragraph(terms, ParagraphStyle('TermsText', fontSize=7, textColor=colors.grey, leading=9)))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


async def send_order_confirmation_email(invoice: dict):
    """Send order confirmation email to customer after invoice creation"""
    customer_email = invoice.get("customer_email")
    if not customer_email:
        return
    
    invoice_no = invoice.get("invoice_no", "N/A")
    customer_name = invoice.get("customer_name", "Customer")
    gross_total = invoice.get("gross_total", 0)
    showroom_name = invoice.get("showroom_name", "Tile Station")
    line_items = invoice.get("line_items", [])
    
    # Calculate deposits and outstanding
    deposits = invoice.get("deposits", [])
    total_deposits = sum(float(d.get("amount", 0)) for d in deposits if d.get("amount"))
    outstanding = gross_total - total_deposits
    
    # Build items table HTML
    items_html = ""
    for item in line_items:
        items_html += f"""
        <tr>
            <td style="padding: 8px; border-bottom: 1px solid #eee;">{item.get('product_name', '')}</td>
            <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: center;">{item.get('quantity', 0)}</td>
            <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">£{item.get('total', 0):.2f}</td>
        </tr>
        """
    
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #1a1a2e; color: white; padding: 20px; text-align: center;">
            <h1 style="margin: 0; color: #f0c14b;">TILE STATION</h1>
            <p style="margin: 5px 0 0 0; font-size: 14px;">Amazing Tiles - Beautiful Bathrooms - Excellent Service</p>
        </div>
        
        <div style="padding: 30px; background: #f9f9f9;">
            <h2 style="color: #1a1a2e; margin-top: 0;">Order Confirmation</h2>
            <p>Dear {customer_name},</p>
            
            <p>Thank you for your order! We're pleased to confirm that we have received your order <strong>#{invoice_no}</strong>.</p>
            
            <div style="background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #f0c14b;">
                <h3 style="margin-top: 0; color: #1a1a2e;">Order Summary</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr style="background: #f5f5f5;">
                            <th style="padding: 10px; text-align: left;">Product</th>
                            <th style="padding: 10px; text-align: center;">Qty</th>
                            <th style="padding: 10px; text-align: right;">Total</th>
                        </tr>
                    </thead>
                    <tbody>
                        {items_html}
                    </tbody>
                </table>
                
                <div style="margin-top: 15px; padding-top: 15px; border-top: 2px solid #1a1a2e;">
                    <table style="width: 100%;">
                        <tr>
                            <td style="padding: 5px 0;"><strong>Order Total:</strong></td>
                            <td style="text-align: right; font-size: 18px; color: #1a1a2e;"><strong>£{gross_total:.2f}</strong></td>
                        </tr>
                        {'<tr><td style="padding: 5px 0;">Amount Paid:</td><td style="text-align: right;">£' + f'{total_deposits:.2f}' + '</td></tr>' if total_deposits > 0 else ''}
                        {'<tr style="color: #d97706;"><td style="padding: 5px 0;"><strong>Outstanding:</strong></td><td style="text-align: right;"><strong>£' + f'{outstanding:.2f}' + '</strong></td></tr>' if outstanding > 0.01 else ''}
                    </table>
                </div>
            </div>
            
            <div style="background: #e8f4e8; padding: 15px; border-radius: 8px; margin: 20px 0;">
                <p style="margin: 0; color: #2d5a2d;"><strong>What's Next?</strong></p>
                <p style="margin: 10px 0 0 0; color: #2d5a2d;">Our team at <strong>{showroom_name}</strong> will process your order shortly. We'll be in touch if we need any additional information.</p>
            </div>
            
            <p>If you have any questions about your order, please don't hesitate to contact us.</p>
            
            <p style="margin-top: 30px;">
                Best regards,<br>
                <strong>Tile Station Team</strong><br>
                Tel: 01474 878 989<br>
                Email: gravesend@tilestation.co.uk
            </p>
        </div>
        
        <div style="background: #1a1a2e; color: #888; padding: 15px; text-align: center; font-size: 12px;">
            <p style="margin: 0;">Unit 3 Trade City, Coldharbour Road, Northfleet, Gravesend DA11 8AB</p>
            <p style="margin: 5px 0 0 0;">Company No: 11982550 | VAT No: 324 251 828</p>
        </div>
    </div>
    """
    
    resend.api_key = RESEND_API_KEY
    await asyncio.to_thread(resend.Emails.send, {
        "from": "Tile Station <orders@resend.dev>",
        "to": [customer_email],
        "subject": f"Order Confirmation #{invoice_no} - Tile Station",
        "html": html_content
    })


@api_router.post("/invoices/{invoice_id}/email")
async def email_invoice_pdf(invoice_id: str, request: InvoiceEmailRequest, current_user: dict = Depends(get_current_user)):
    """Send invoice PDF via email"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if not RESEND_AVAILABLE:
        raise HTTPException(status_code=500, detail="Email service not available")
    
    # Get the invoice
    invoice = await db.invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Generate PDF
    try:
        pdf_bytes = await generate_invoice_pdf_bytes(invoice)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")
    
    # Send email with attachment
    import base64
    
    invoice_no = invoice.get("invoice_no", "N/A")
    customer_name = invoice.get("customer_name", "Customer")
    gross_total = invoice.get("gross_total", 0)
    
    # Calculate outstanding
    deposits = invoice.get("deposits", [])
    total_deposits = sum(float(d.get("amount", 0)) for d in deposits if d.get("amount"))
    outstanding = gross_total - total_deposits
    
    custom_message = request.message or ""
    if custom_message:
        custom_message = f"<p style='margin-bottom: 20px;'>{custom_message}</p>"
    
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #1a1a2e; color: white; padding: 20px; text-align: center;">
            <h1 style="margin: 0;">TILE STATION</h1>
            <p style="margin: 5px 0 0 0; font-size: 14px;">Amazing Tiles - Beautiful Bathrooms - Excellent Service</p>
        </div>
        
        <div style="padding: 30px; background: #f9f9f9;">
            {custom_message}
            <p>Dear {customer_name},</p>
            
            <p>Please find attached your invoice <strong>#{invoice_no}</strong> from Tile Station.</p>
            
            <div style="background: white; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <table style="width: 100%;">
                    <tr>
                        <td style="padding: 8px 0;"><strong>Invoice No:</strong></td>
                        <td style="text-align: right;">{invoice_no}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0;"><strong>Total Amount:</strong></td>
                        <td style="text-align: right;">£{gross_total:.2f}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0;"><strong>Amount Paid:</strong></td>
                        <td style="text-align: right;">£{total_deposits:.2f}</td>
                    </tr>
                    <tr style="{'color: #d97706; font-weight: bold;' if outstanding > 0 else ''}">
                        <td style="padding: 8px 0;"><strong>Outstanding:</strong></td>
                        <td style="text-align: right;">£{outstanding:.2f}</td>
                    </tr>
                </table>
            </div>
            
            <p>If you have any questions about this invoice, please don't hesitate to contact us.</p>
            
            <p>Thank you for choosing Tile Station!</p>
            
            <p style="margin-top: 30px;">
                Best regards,<br>
                <strong>Tile Station Team</strong><br>
                Tel: 01474 878 989<br>
                Email: gravesend@tilestation.co.uk
            </p>
        </div>
        
        <div style="background: #1a1a2e; color: #888; padding: 15px; text-align: center; font-size: 12px;">
            <p style="margin: 0;">Unit 3 Trade City, Coldharbour Road, Northfleet, Gravesend DA11 8AB</p>
            <p style="margin: 5px 0 0 0;">Company No: 11982550 | VAT No: 324 251 828</p>
        </div>
    </div>
    """
    
    try:
        resend.api_key = os.environ.get("RESEND_API_KEY")
        
        response = resend.Emails.send({
            "from": "Tile Station <invoices@resend.dev>",
            "to": [request.email],
            "subject": f"Invoice #{invoice_no} from Tile Station",
            "html": html_content,
            "attachments": [
                {
                    "filename": f"Invoice_{invoice_no}.pdf",
                    "content": base64.b64encode(pdf_bytes).decode("utf-8")
                }
            ]
        })
        
        return {"message": "Invoice sent successfully", "email": request.email}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

# ============ STAFF PIN ENDPOINTS ============

@api_router.post("/staff-pins")
async def create_staff_pin(input: StaffPinCreate, current_user: dict = Depends(get_current_user)):
    """Create a new staff PIN (admin only)"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    from uuid import uuid4
    
    # Validate PIN format (4-6 digits)
    if not input.pin.isdigit() or len(input.pin) < 4 or len(input.pin) > 6:
        raise HTTPException(status_code=400, detail="PIN must be 4-6 digits")
    
    # Check if PIN already exists
    existing = await db.staff_pins.find_one({"pin": input.pin})
    if existing:
        raise HTTPException(status_code=400, detail="This PIN is already in use")
    
    # Get showroom name if showroom_id provided
    showroom_name = None
    if input.showroom_id:
        showroom = await db.showrooms.find_one({"id": input.showroom_id}, {"_id": 0})
        if showroom:
            showroom_name = showroom["name"]
    
    staff_pin = {
        "id": str(uuid4()),
        "name": input.name,
        "pin": input.pin,
        "role": input.role,
        "active": input.active,
        "showroom_id": input.showroom_id,
        "showroom_name": showroom_name,
        "created_by": current_user["email"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.staff_pins.insert_one(staff_pin)
    
    # Return without pin for security
    return {
        "id": staff_pin["id"],
        "name": staff_pin["name"],
        "role": staff_pin["role"],
        "active": staff_pin["active"],
        "showroom_id": staff_pin["showroom_id"],
        "showroom_name": staff_pin["showroom_name"],
        "created_at": staff_pin["created_at"]
    }

@api_router.get("/staff-pins")
async def get_staff_pins(current_user: dict = Depends(get_current_user)):
    """Get all staff PINs (admin only) - without showing actual PINs"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    staff_pins = await db.staff_pins.find({}, {"_id": 0}).sort("name", 1).to_list(1000)
    
    # Mask the PINs for security - show only last 2 digits
    # Also add showroom names
    showrooms = {s["id"]: s["name"] for s in await db.showrooms.find({}, {"_id": 0}).to_list(1000)}
    for staff in staff_pins:
        if "pin" in staff:
            staff["pin_masked"] = "**" + staff["pin"][-2:]
            del staff["pin"]
        # Update showroom name in case it changed
        if staff.get("showroom_id"):
            staff["showroom_name"] = showrooms.get(staff["showroom_id"], "Unknown")
    
    return staff_pins

@api_router.get("/staff-pins/{staff_id}")
async def get_staff_pin(staff_id: str, current_user: dict = Depends(get_current_user)):
    """Get a specific staff PIN (admin only)"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    staff = await db.staff_pins.find_one({"id": staff_id}, {"_id": 0})
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    
    # Mask PIN
    if "pin" in staff:
        staff["pin_masked"] = "**" + staff["pin"][-2:]
        del staff["pin"]
    
    return staff

@api_router.put("/staff-pins/{staff_id}")
async def update_staff_pin(staff_id: str, input: StaffPinUpdate, current_user: dict = Depends(get_current_user)):
    """Update a staff PIN (admin only)"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    staff = await db.staff_pins.find_one({"id": staff_id})
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    
    update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
    
    if input.name is not None:
        update_data["name"] = input.name
    if input.role is not None:
        update_data["role"] = input.role
    if input.active is not None:
        update_data["active"] = input.active
    if input.showroom_id is not None:
        update_data["showroom_id"] = input.showroom_id
        # Get showroom name
        if input.showroom_id:
            showroom = await db.showrooms.find_one({"id": input.showroom_id}, {"_id": 0})
            update_data["showroom_name"] = showroom["name"] if showroom else None
        else:
            update_data["showroom_name"] = None
    if input.pin is not None:
        # Validate new PIN
        if not input.pin.isdigit() or len(input.pin) < 4 or len(input.pin) > 6:
            raise HTTPException(status_code=400, detail="PIN must be 4-6 digits")
        # Check if new PIN already exists (excluding current staff)
        existing = await db.staff_pins.find_one({"pin": input.pin, "id": {"$ne": staff_id}})
        if existing:
            raise HTTPException(status_code=400, detail="This PIN is already in use")
        update_data["pin"] = input.pin
    
    await db.staff_pins.update_one({"id": staff_id}, {"$set": update_data})
    
    return {"message": "Staff PIN updated successfully"}

@api_router.delete("/staff-pins/{staff_id}")
async def delete_staff_pin(staff_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a staff PIN (admin only)"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = await db.staff_pins.delete_one({"id": staff_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Staff member not found")
    
    return {"message": "Staff PIN deleted successfully"}

@api_router.post("/staff-pins/verify")
async def verify_staff_pin(input: StaffPinVerify, current_user: dict = Depends(get_current_user)):
    """Verify a staff PIN and return staff details"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    staff = await db.staff_pins.find_one({"pin": input.pin, "active": True}, {"_id": 0, "pin": 0})
    if not staff:
        raise HTTPException(status_code=401, detail="Invalid PIN")
    
    return {
        "valid": True,
        "staff_id": staff["id"],
        "staff_name": staff["name"],
        "staff_role": staff["role"]
    }

# Health check endpoint for Kubernetes
@app.get("/health")
async def health_check():
    try:
        # Test MongoDB connection
        await client.admin.command('ping')
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": str(e)}

# Simple root endpoint for testing
@app.get("/")
async def root():
    return {"message": "Tile Station API is running"}

# Include the router in the main app
app.include_router(api_router)

# Mount static files for uploaded images
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

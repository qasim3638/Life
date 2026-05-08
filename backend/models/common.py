"""
Pydantic models for Stores, Analytics, and other entities
"""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone


class Store(BaseModel):
    id: str
    name: str
    address: str = ""
    phone: str = ""
    email: str = ""
    lat: Optional[float] = None
    lng: Optional[float] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StoreCreate(BaseModel):
    name: str
    address: str = ""
    phone: str = ""
    email: str = ""
    lat: Optional[float] = None
    lng: Optional[float] = None
    is_active: bool = True


class SalesTarget(BaseModel):
    id: str
    year: int
    month: int
    monthly_target: float
    weekly_target: float = 0
    daily_target: float = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SalesTargetCreate(BaseModel):
    year: int
    month: int
    monthly_target: float


class SalesTargetUpdate(BaseModel):
    monthly_target: float


class DashboardStats(BaseModel):
    total_products: int
    low_stock_count: int
    total_orders: int
    revenue: float


class StoreAnalytics(BaseModel):
    showroom_id: str
    showroom_name: str
    order_count: int
    gross_revenue: float
    net_revenue: float
    vat_amount: float
    items_sold: int
    top_products: List[Dict]


class AnalyticsResponse(BaseModel):
    total_orders: int
    total_gross: float
    total_net: float
    total_vat: float
    total_items_sold: int
    average_order_value: float
    showroom_analytics: List[StoreAnalytics]
    show_profit: bool = False


class BulkInquiry(BaseModel):
    id: str
    customer_name: str
    customer_email: str
    customer_phone: str
    project_details: str
    product_interests: List[str] = []
    estimated_quantity: str = ""
    timeline: str = ""
    notes: str = ""
    status: str = "new"
    admin_notes: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BulkInquiryCreate(BaseModel):
    customer_name: str
    customer_email: str
    customer_phone: str
    project_details: str
    product_interests: List[str] = []
    estimated_quantity: str = ""
    timeline: str = ""


class BulkInquiryUpdate(BaseModel):
    status: Optional[str] = None
    admin_notes: Optional[str] = None


class CustomerInvite(BaseModel):
    id: str
    code: str
    customer_email: Optional[str] = None
    customer_name: Optional[str] = None
    discount_percentage: float = 0
    valid_until: Optional[datetime] = None
    is_used: bool = False
    used_by: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = ""


class StaffInviteCreate(BaseModel):
    email: Optional[str] = None
    role: str = "staff"
    permissions: List[str] = []
    showroom_id: Optional[str] = None
    note: Optional[str] = ""
    expires_days: int = 7


class StaffInvite(BaseModel):
    id: str
    code: str
    email: Optional[str] = None
    role: str = "staff"
    permissions: List[str] = []
    showroom_id: Optional[str] = None
    showroom_name: Optional[str] = None
    valid_until: datetime
    is_used: bool = False
    used_by: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = ""


class InviteCreate(BaseModel):
    discount_percentage: float = 0
    valid_days: int = 30


class InviteEmailRequest(BaseModel):
    invite_id: str
    recipient_email: EmailStr
    recipient_name: str = ""


class CustomerPricing(BaseModel):
    id: str
    customer_email: str
    product_id: str
    product_name: str
    custom_price: float
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = ""


class CustomerPricingCreate(BaseModel):
    customer_email: str
    product_id: str
    custom_price: float


class BulkPricingItem(BaseModel):
    product_id: str
    custom_price: float


class BulkPricingImport(BaseModel):
    customer_email: str
    items: List[BulkPricingItem]


class BulkImportResult(BaseModel):
    success_count: int
    error_count: int
    errors: List[str] = []


class MarketingCampaign(BaseModel):
    id: str
    name: str
    subject: str
    content: str
    target_audience: str = "all"
    status: str = "draft"
    sent_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sent_at: Optional[datetime] = None


class MarketingCampaignCreate(BaseModel):
    name: str
    subject: str
    content: str
    target_audience: str = "all"


class AuditLogEntry(BaseModel):
    id: str
    action: str
    entity_type: str
    entity_id: str
    entity_name: str
    user_id: str
    user_email: str
    user_name: str
    user_role: str
    before_data: Optional[Dict[str, Any]] = None
    after_data: Optional[Dict[str, Any]] = None
    details: str = ""
    ip_address: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

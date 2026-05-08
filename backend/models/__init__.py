"""
Models package - exports all Pydantic models
"""
from .user import (
    UserRole,
    Address,
    UserRegister,
    UserLogin,
    User,
    UserPermissionsUpdate,
    StaffRegistration,
    TokenResponse,
    StaffPinCreate,
    StaffPinUpdate,
    StaffPinVerify,
)

from .product import (
    Category,
    CategoryCreate,
    Product,
    ProductCreate,
    ProductUpdate,
)

from .invoice import (
    InvoiceStatus,
    InvoiceLineItem,
    DepositEntry,
    InvoiceCreate,
    InvoiceUpdate,
    InvoiceEmailRequest,
)

from .order import (
    OrderItem,
    Order,
    OrderCreate,
    OrderStatusUpdate,
    OTPRequest,
    OTPVerification,
)

from .common import (
    Store,
    StoreCreate,
    SalesTarget,
    SalesTargetCreate,
    SalesTargetUpdate,
    DashboardStats,
    StoreAnalytics,
    AnalyticsResponse,
    BulkInquiry,
    BulkInquiryCreate,
    BulkInquiryUpdate,
    CustomerInvite,
    StaffInviteCreate,
    StaffInvite,
    InviteCreate,
    InviteEmailRequest,
    CustomerPricing,
    CustomerPricingCreate,
    BulkPricingItem,
    BulkPricingImport,
    BulkImportResult,
    MarketingCampaign,
    MarketingCampaignCreate,
    AuditLogEntry,
)

__all__ = [
    # User models
    "UserRole", "Address", "UserRegister", "UserLogin", "User",
    "UserPermissionsUpdate", "StaffRegistration", "TokenResponse",
    "StaffPinCreate", "StaffPinUpdate", "StaffPinVerify",
    # Product models
    "Category", "CategoryCreate", "Product", "ProductCreate", "ProductUpdate",
    # Invoice models
    "InvoiceStatus", "InvoiceLineItem", "DepositEntry", 
    "InvoiceCreate", "InvoiceUpdate", "InvoiceEmailRequest",
    # Order models
    "OrderItem", "Order", "OrderCreate", "OrderStatusUpdate",
    "OTPRequest", "OTPVerification",
    # Common models
    "Store", "StoreCreate", "SalesTarget", "SalesTargetCreate", "SalesTargetUpdate",
    "DashboardStats", "StoreAnalytics", "AnalyticsResponse",
    "BulkInquiry", "BulkInquiryCreate", "BulkInquiryUpdate",
    "CustomerInvite", "StaffInviteCreate", "StaffInvite", "InviteCreate", "InviteEmailRequest",
    "CustomerPricing", "CustomerPricingCreate", "BulkPricingItem", "BulkPricingImport", "BulkImportResult",
    "MarketingCampaign", "MarketingCampaignCreate", "AuditLogEntry",
]

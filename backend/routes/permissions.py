"""
Role-based permissions management.

Super Admin always has full access.
Other roles (system: admin/manager/staff, plus custom roles) have explicit page + action permissions stored in the `roles` collection.
"""
from datetime import datetime, timezone
from typing import List, Optional, Dict
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from config import get_db
from services import get_current_user

router = APIRouter(prefix="/permissions", tags=["Permissions"])


# ---------------------------------------------------------------------------
# Permission registry — single source of truth for what can be controlled.
# ---------------------------------------------------------------------------

PAGE_REGISTRY: List[Dict] = [
    # Sales & EPOS
    {"key": "dashboard", "label": "Dashboard", "group": "Main"},
    {"key": "epos", "label": "EPOS", "group": "Sales & EPOS"},
    {"key": "cash_counter", "label": "Cash Counter", "group": "Sales & EPOS"},
    {"key": "showroom_dashboard", "label": "Store Dashboard", "group": "Sales & EPOS"},
    {"key": "sales_hub", "label": "Sales Hub", "group": "Sales & EPOS"},
    {"key": "invoice", "label": "Invoice (Create)", "group": "Sales & EPOS"},
    {"key": "invoice_history", "label": "Invoice History", "group": "Sales & EPOS"},
    {"key": "quotation", "label": "Quotation (Create)", "group": "Sales & EPOS"},
    {"key": "quotation_history", "label": "Quotation History", "group": "Sales & EPOS"},
    {"key": "cash_quotation", "label": "Cash Quotation", "group": "Sales & EPOS"},
    {"key": "cash_quotation_history", "label": "Cash Quotation History", "group": "Sales & EPOS"},
    {"key": "refund", "label": "Refund", "group": "Sales & EPOS"},
    {"key": "refund_history", "label": "Refund History", "group": "Sales & EPOS"},
    {"key": "credit_note", "label": "Credit Note", "group": "Sales & EPOS"},
    {"key": "credit_note_history", "label": "Credit Note History", "group": "Sales & EPOS"},
    {"key": "orders", "label": "Orders", "group": "Sales & EPOS"},
    {"key": "order_management", "label": "Order Management", "group": "Sales & EPOS"},
    {"key": "delivery_management", "label": "Delivery Management", "group": "Sales & EPOS"},
    {"key": "online_orders", "label": "Online Orders", "group": "Sales & EPOS"},

    # Products & Suppliers
    {"key": "products_hub", "label": "Products Hub", "group": "Products & Suppliers"},
    {"key": "supplier_products", "label": "Supplier Products", "group": "Products & Suppliers"},
    {"key": "supplier_health", "label": "Supplier Health", "group": "Products & Suppliers"},
    {"key": "sync_hub", "label": "Sync Hub", "group": "Products & Suppliers"},
    {"key": "suppliers", "label": "Supplier Contacts", "group": "Products & Suppliers"},
    {"key": "supplier_sync", "label": "Supplier Sync Dashboard", "group": "Products & Suppliers"},
    {"key": "categories", "label": "Categories", "group": "Products & Suppliers"},
    {"key": "manage_categories", "label": "Product Categories", "group": "Products & Suppliers"},
    {"key": "scraping_portal", "label": "Scraping Portal", "group": "Products & Suppliers"},
    {"key": "image_scraper", "label": "Image Scraper", "group": "Products & Suppliers"},
    {"key": "image_migration", "label": "Image Migration", "group": "Products & Suppliers"},
    {"key": "product_documents", "label": "Product Documents", "group": "Products & Suppliers"},

    # Stock
    {"key": "stock_hub", "label": "Stock Hub", "group": "Stock"},
    {"key": "stock_allocation", "label": "Stock Allocation", "group": "Stock"},
    {"key": "bulk_stock", "label": "Bulk Stock Edit", "group": "Stock"},
    {"key": "stock_import", "label": "Stock Import", "group": "Stock"},
    {"key": "delivery_check_in", "label": "Delivery Check-In", "group": "Stock"},
    {"key": "stock_transfers", "label": "Stock Transfers", "group": "Stock"},
    {"key": "reorder_suggestions", "label": "Reorder Suggestions", "group": "Stock"},
    {"key": "batch_tracking", "label": "Batch Tracking", "group": "Stock"},
    {"key": "to_order_report", "label": "To Order Report", "group": "Stock"},
    {"key": "stock_cost", "label": "Stock Value", "group": "Stock"},
    {"key": "stocktake_report", "label": "Stocktake Report", "group": "Stock"},
    {"key": "clearance_products", "label": "Clearance Products", "group": "Stock"},
    {"key": "new_collection_products", "label": "New Collection Products", "group": "Stock"},

    # Customers
    {"key": "customers_hub", "label": "Customers Hub", "group": "Customers"},
    {"key": "trade_accounts", "label": "Trade Accounts", "group": "Customers"},
    {"key": "customer_pricing", "label": "Customer Pricing", "group": "Customers"},
    {"key": "customer_invites", "label": "Invite Customers", "group": "Customers"},
    {"key": "bulk_inquiries", "label": "Bulk Inquiries", "group": "Customers"},
    {"key": "trade_list", "label": "Trade List (Legacy)", "group": "Customers"},
    {"key": "loyalty", "label": "Loyalty Dashboard", "group": "Customers"},
    {"key": "quote_requests", "label": "Quote Requests", "group": "Customers"},

    # Communication
    {"key": "communication_hub", "label": "Communication Hub", "group": "Communication"},
    {"key": "staff_chat", "label": "Staff Chat", "group": "Communication"},
    {"key": "tasks", "label": "Tasks & Notes", "group": "Communication"},
    {"key": "inbox", "label": "Inbox", "group": "Communication"},
    {"key": "email_composer", "label": "Send Email", "group": "Communication"},
    {"key": "marketing", "label": "Marketing", "group": "Communication"},
    {"key": "notifications", "label": "Notifications", "group": "Communication"},
    {"key": "live_chat", "label": "Live Chat (Customer)", "group": "Communication"},
    {"key": "live_visitors", "label": "Live Visitors", "group": "Communication"},
    {"key": "whatsapp", "label": "WhatsApp", "group": "Communication"},

    # Reports
    {"key": "reports_hub", "label": "Reports Hub", "group": "Reports"},
    {"key": "analytics", "label": "Analytics", "group": "Reports"},
    {"key": "reports", "label": "Sales Reports", "group": "Reports"},
    {"key": "audit_trail", "label": "Audit Trail", "group": "Reports"},
    {"key": "staff_performance", "label": "Staff Performance", "group": "Reports"},
    {"key": "website_analytics", "label": "Website Analytics", "group": "Reports"},
    {"key": "website_sales_dashboard", "label": "Website Sales Dashboard", "group": "Reports"},

    # Admin Settings
    {"key": "settings_hub", "label": "Settings Hub", "group": "Admin Settings"},
    {"key": "showrooms", "label": "Stores", "group": "Admin Settings"},
    {"key": "user_management", "label": "User Management", "group": "Admin Settings"},
    {"key": "permissions_admin", "label": "Permissions", "group": "Admin Settings"},
    {"key": "staff_pins", "label": "Staff PINs", "group": "Admin Settings"},
    {"key": "staff_invites", "label": "Staff Invites", "group": "Admin Settings"},
    {"key": "trash", "label": "Trash", "group": "Admin Settings"},
    {"key": "general_settings", "label": "General Settings", "group": "Admin Settings"},
    {"key": "security_settings", "label": "Security Settings", "group": "Admin Settings"},
    {"key": "pricing_settings", "label": "Pricing Settings", "group": "Admin Settings"},

    # Website
    {"key": "website_hub", "label": "Website Hub", "group": "Website"},
    {"key": "website_preview", "label": "Preview Website", "group": "Website"},
    {"key": "homepage_content", "label": "Homepage Content", "group": "Website"},
    {"key": "homepage_manager", "label": "Homepage Manager", "group": "Website"},
    {"key": "collections", "label": "Collections", "group": "Website"},
    {"key": "collection_manager", "label": "Collection Manager", "group": "Website"},
    {"key": "trade_account_settings", "label": "Trade Account Page", "group": "Website"},
    {"key": "customer_account_settings", "label": "Customer Account Page", "group": "Website"},
    {"key": "checkout_settings", "label": "Checkout Page", "group": "Website"},
    {"key": "navigation_menu", "label": "Navigation Menu", "group": "Website"},
    {"key": "navigation_structure", "label": "Navigation Structure", "group": "Website"},
    {"key": "website_categories", "label": "Website Categories", "group": "Website"},
    {"key": "website_filters", "label": "Filters", "group": "Website"},
    {"key": "website_products", "label": "Website Products Editor", "group": "Website"},
    {"key": "publish_products", "label": "Publish Products", "group": "Website"},
    {"key": "sample_service_content", "label": "Sample Service Content", "group": "Website"},
    {"key": "website_settings", "label": "Settings & Branding", "group": "Website"},
    {"key": "page_maintenance", "label": "Page Maintenance", "group": "Website"},
    {"key": "welcome_popup", "label": "Welcome Popup", "group": "Website"},
    {"key": "tile_calculator_settings", "label": "Tile Calculator Settings", "group": "Website"},
    {"key": "bathroom_page", "label": "Bathroom Page", "group": "Website"},
    {"key": "sitemap", "label": "Sitemap", "group": "Website"},
]

ACTION_REGISTRY: List[Dict] = [
    # Supplier Products page — granular control (matches the recently added super-admin gates)
    {"key": "supplier_products.cost_column", "label": "View Cost column", "page": "supplier_products"},
    {"key": "supplier_products.live_column", "label": "View Live column", "page": "supplier_products"},
    {"key": "supplier_products.status_column", "label": "View Status column", "page": "supplier_products"},
    {"key": "supplier_products.checkbox_column", "label": "Bulk select checkbox column", "page": "supplier_products"},
    {"key": "supplier_products.action.visibility", "label": "Set product visibility (online / in-store / hidden)", "page": "supplier_products"},
    {"key": "supplier_products.action.always_in_stock", "label": "Toggle Always In Stock", "page": "supplier_products"},
    {"key": "supplier_products.action.add_to_db", "label": "Add product to database", "page": "supplier_products"},
    {"key": "supplier_products.action.quick_edit", "label": "Quick Edit (popup)", "page": "supplier_products"},
    {"key": "supplier_products.action.sale_labels", "label": "Manage Sale & Labels", "page": "supplier_products"},
    {"key": "supplier_products.action.full_edit", "label": "Edit product (full page)", "page": "supplier_products"},
    {"key": "supplier_products.action.pdf_documents", "label": "Manage PDF documents", "page": "supplier_products"},
    {"key": "supplier_products.action.preview", "label": "Preview on website (eye icon)", "page": "supplier_products"},
    {"key": "supplier_products.action.copy", "label": "Copy product (creates draft)", "page": "supplier_products"},
    {"key": "supplier_products.action.delete", "label": "Delete product", "page": "supplier_products"},
]


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class RolePayload(BaseModel):
    role_id: str = Field(..., min_length=1, max_length=64)
    role_name: str = Field(..., min_length=1, max_length=80)
    pages: List[str] = []
    actions: List[str] = []
    is_super_admin: bool = False


class RoleUpdate(BaseModel):
    role_name: Optional[str] = None
    pages: Optional[List[str]] = None
    actions: Optional[List[str]] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SYSTEM_ROLE_IDS = {"super_admin", "admin", "manager", "staff"}

# Default page+action grants for system roles (preserves current observed behaviour).
# super_admin is special and bypasses all checks regardless of this seed.
SYSTEM_ROLE_DEFAULTS: Dict[str, Dict[str, List[str]]] = {
    "super_admin": {
        "pages": [p["key"] for p in PAGE_REGISTRY],
        "actions": [a["key"] for a in ACTION_REGISTRY],
    },
    "admin": {
        "pages": [
            p["key"] for p in PAGE_REGISTRY
            if p["key"] not in {"audit_trail", "permissions_admin", "user_management", "staff_pins", "staff_invites", "trash", "stock_import", "notifications"}
        ],
        # Admin keeps preview only by default — matches the recently-shipped restriction
        "actions": ["supplier_products.action.preview"],
    },
    "manager": {
        "pages": [
            "dashboard", "epos", "cash_counter", "showroom_dashboard", "sales_hub",
            "invoice", "invoice_history", "quotation", "quotation_history",
            "cash_quotation", "cash_quotation_history", "refund", "refund_history",
            "credit_note", "credit_note_history", "orders", "order_management",
            "delivery_management", "online_orders",
            "products_hub", "supplier_products", "stock_hub", "stock_allocation",
            "bulk_stock", "delivery_check_in", "stock_transfers", "reorder_suggestions",
            "batch_tracking", "to_order_report",
            "customers_hub", "trade_accounts", "customer_pricing", "bulk_inquiries",
            "communication_hub", "staff_chat", "tasks", "inbox",
            "reports_hub", "analytics", "reports",
        ],
        "actions": ["supplier_products.action.preview"],
    },
    "staff": {
        "pages": [
            "dashboard", "epos", "cash_counter", "showroom_dashboard",
            "invoice", "quotation", "cash_quotation",
            "orders", "online_orders",
            "supplier_products",
            "stock_allocation", "delivery_check_in", "batch_tracking",
            "customers_hub", "trade_accounts",
            "staff_chat", "tasks",
        ],
        "actions": ["supplier_products.action.preview"],
    },
}


def _serialize_role(doc: dict) -> dict:
    return {
        "role_id": doc.get("role_id"),
        "role_name": doc.get("role_name"),
        "is_system": doc.get("is_system", False),
        "is_super_admin": doc.get("is_super_admin", False),
        "pages": doc.get("pages", []),
        "actions": doc.get("actions", []),
        "created_at": (doc.get("created_at").isoformat() if isinstance(doc.get("created_at"), datetime) else doc.get("created_at")),
        "updated_at": (doc.get("updated_at").isoformat() if isinstance(doc.get("updated_at"), datetime) else doc.get("updated_at")),
    }


async def _ensure_system_roles(db) -> None:
    """Seed system roles on first read if they're missing. Idempotent — never overwrites existing rows."""
    for role_id in SYSTEM_ROLE_IDS:
        existing = await db.roles.find_one({"role_id": role_id})
        if not existing:
            defaults = SYSTEM_ROLE_DEFAULTS.get(role_id, {"pages": [], "actions": []})
            now = datetime.now(timezone.utc)
            await db.roles.insert_one({
                "role_id": role_id,
                "role_name": role_id.replace("_", " ").title(),
                "is_system": True,
                "is_super_admin": role_id == "super_admin",
                "pages": defaults["pages"],
                "actions": defaults["actions"],
                "created_at": now,
                "updated_at": now,
            })


def _require_super_admin(current_user: dict):
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/registry")
async def get_registry(current_user: dict = Depends(get_current_user)):
    """Return the catalogue of pages + actions (any logged-in admin user)."""
    return {"pages": PAGE_REGISTRY, "actions": ACTION_REGISTRY}


@router.get("/me")
async def get_my_permissions(current_user: dict = Depends(get_current_user)):
    """Return the current user's effective pages + actions."""
    db = get_db()
    await _ensure_system_roles(db)
    role_id = current_user.get("role") or "staff"

    if role_id == "super_admin":
        return {
            "role": role_id,
            "is_super_admin": True,
            "pages": [p["key"] for p in PAGE_REGISTRY],
            "actions": [a["key"] for a in ACTION_REGISTRY],
        }

    role = await db.roles.find_one({"role_id": role_id}, {"_id": 0})
    if not role:
        return {"role": role_id, "is_super_admin": False, "pages": [], "actions": []}
    return {
        "role": role_id,
        "is_super_admin": role.get("is_super_admin", False),
        "pages": role.get("pages", []),
        "actions": role.get("actions", []),
    }


@router.get("/roles")
async def list_roles(current_user: dict = Depends(get_current_user)):
    _require_super_admin(current_user)
    db = get_db()
    await _ensure_system_roles(db)
    roles = await db.roles.find({}, {"_id": 0}).sort("role_id", 1).to_list(1000)
    return [_serialize_role(r) for r in roles]


@router.post("/roles")
async def create_role(payload: RolePayload, current_user: dict = Depends(get_current_user)):
    _require_super_admin(current_user)
    db = get_db()
    await _ensure_system_roles(db)

    role_id = payload.role_id.strip().lower().replace(" ", "_")
    if not role_id:
        raise HTTPException(status_code=400, detail="role_id is required")
    if await db.roles.find_one({"role_id": role_id}):
        raise HTTPException(status_code=409, detail=f"Role '{role_id}' already exists")

    valid_pages = {p["key"] for p in PAGE_REGISTRY}
    valid_actions = {a["key"] for a in ACTION_REGISTRY}

    now = datetime.now(timezone.utc)
    doc = {
        "role_id": role_id,
        "role_name": payload.role_name.strip(),
        "is_system": False,
        "is_super_admin": False,
        "pages": [p for p in payload.pages if p in valid_pages],
        "actions": [a for a in payload.actions if a in valid_actions],
        "created_at": now,
        "updated_at": now,
    }
    await db.roles.insert_one(doc)
    return _serialize_role(doc)


@router.put("/roles/{role_id}")
async def update_role(role_id: str, payload: RoleUpdate, current_user: dict = Depends(get_current_user)):
    _require_super_admin(current_user)
    db = get_db()
    await _ensure_system_roles(db)

    existing = await db.roles.find_one({"role_id": role_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Role not found")
    if existing.get("is_super_admin"):
        raise HTTPException(status_code=400, detail="Super Admin role cannot be edited")

    valid_pages = {p["key"] for p in PAGE_REGISTRY}
    valid_actions = {a["key"] for a in ACTION_REGISTRY}

    update_doc = {"updated_at": datetime.now(timezone.utc)}
    if payload.role_name is not None and not existing.get("is_system", False):
        update_doc["role_name"] = payload.role_name.strip()
    if payload.pages is not None:
        update_doc["pages"] = [p for p in payload.pages if p in valid_pages]
    if payload.actions is not None:
        update_doc["actions"] = [a for a in payload.actions if a in valid_actions]

    await db.roles.update_one({"role_id": role_id}, {"$set": update_doc})
    updated = await db.roles.find_one({"role_id": role_id}, {"_id": 0})
    return _serialize_role(updated)


@router.delete("/roles/{role_id}")
async def delete_role(role_id: str, current_user: dict = Depends(get_current_user)):
    _require_super_admin(current_user)
    db = get_db()

    existing = await db.roles.find_one({"role_id": role_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Role not found")
    if existing.get("is_system"):
        raise HTTPException(status_code=400, detail="System roles cannot be deleted")

    in_use = await db.users.count_documents({"role": role_id})
    if in_use > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete role '{role_id}' — {in_use} user(s) currently assigned to it. Reassign them first.",
        )

    await db.roles.delete_one({"role_id": role_id})
    return {"success": True, "role_id": role_id}

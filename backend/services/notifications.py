"""
Email Notification Service
Handles all automated email notifications for the Tile Station app
"""
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import asyncio

# Notification types
NOTIFICATION_TYPES = {
    # Order & Sales
    "new_order": {
        "name": "New Customer Order",
        "description": "When a new order is placed by a customer",
        "category": "orders"
    },
    "order_status_change": {
        "name": "Order Status Change",
        "description": "When an order status is updated",
        "category": "orders"
    },
    "payment_received": {
        "name": "Payment Received",
        "description": "When a payment/deposit is recorded",
        "category": "orders"
    },
    "payment_outstanding": {
        "name": "Outstanding Payment Reminder",
        "description": "When an invoice has outstanding balance",
        "category": "orders"
    },
    
    # Inventory
    "low_stock": {
        "name": "Low Stock Alert",
        "description": "When product stock falls below threshold",
        "category": "inventory"
    },
    "out_of_stock": {
        "name": "Out of Stock Alert",
        "description": "When a product goes out of stock",
        "category": "inventory"
    },
    
    # Customers
    "new_customer": {
        "name": "New Customer Registration",
        "description": "When a new customer registers",
        "category": "customers"
    },
    "new_bulk_inquiry": {
        "name": "New Bulk Inquiry",
        "description": "When a customer submits a bulk inquiry",
        "category": "customers"
    },
    
    # Staff
    "staff_invite_accepted": {
        "name": "Staff Invite Accepted",
        "description": "When a staff member accepts an invitation",
        "category": "staff"
    },
    "daily_summary": {
        "name": "Daily Sales Summary",
        "description": "Daily summary of sales and orders",
        "category": "reports"
    },
    "weekly_summary": {
        "name": "Weekly Sales Summary",
        "description": "Weekly summary of sales and performance",
        "category": "reports"
    }
}

def get_default_settings():
    """Get default notification settings"""
    return {
        "enabled": True,
        "recipients": [],  # Admin emails to receive notifications
        "notifications": {
            "new_order": True,
            "order_status_change": True,
            "payment_received": True,
            "payment_outstanding": True,
            "low_stock": True,
            "out_of_stock": True,
            "new_customer": True,
            "new_bulk_inquiry": True,
            "staff_invite_accepted": True,
            "daily_summary": False,
            "weekly_summary": False
        },
        "low_stock_threshold": 10,  # Alert when stock below this
        "showroom_specific": True,  # Send from showroom-specific email
    }


async def get_notification_settings(db):
    """Get notification settings from database"""
    settings = await db.notification_settings.find_one({"type": "global"}, {"_id": 0})
    if not settings:
        settings = get_default_settings()
        settings["type"] = "global"
        await db.notification_settings.insert_one(settings)
    return settings


async def update_notification_settings(db, updates: dict):
    """Update notification settings"""
    await db.notification_settings.update_one(
        {"type": "global"},
        {"$set": updates},
        upsert=True
    )


async def send_notification_email(
    db,
    notification_type: str,
    subject: str,
    body_html: str,
    showroom_id: Optional[str] = None,
    extra_recipients: List[str] = None
):
    """Send a notification email if enabled"""
    from services.email import send_email_notification, RESEND_AVAILABLE, get_showroom_email
    
    if not RESEND_AVAILABLE:
        logging.warning("Email service not available for notifications")
        return False
    
    settings = await get_notification_settings(db)
    
    # Check if notifications are enabled globally
    if not settings.get("enabled", False):
        return False
    
    # Check if this specific notification type is enabled
    if not settings.get("notifications", {}).get(notification_type, False):
        return False
    
    # Get recipients
    recipients = settings.get("recipients", [])
    if extra_recipients:
        recipients = list(set(recipients + extra_recipients))
    
    if not recipients:
        logging.warning(f"No recipients configured for notification: {notification_type}")
        return False
    
    # Get showroom email if specified
    from_email = None
    from_name = "Tile Station"
    if showroom_id and settings.get("showroom_specific", True):
        showroom = await db.showrooms.find_one({"id": showroom_id}, {"_id": 0})
        if showroom:
            from_name = f"{showroom['name']} - Tile Station"
            from_email = get_showroom_email(showroom['name'])
    
    try:
        await send_email_notification(
            to_emails=recipients,
            subject=subject,
            html_content=body_html,
            from_name=from_name,
            from_email=from_email
        )
        
        # Log the notification
        await db.notification_logs.insert_one({
            "type": notification_type,
            "subject": subject,
            "recipients": recipients,
            "showroom_id": showroom_id,
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "success": True
        })
        
        return True
    except Exception as e:
        logging.error(f"Failed to send notification email: {e}")
        
        # Log the failure
        await db.notification_logs.insert_one({
            "type": notification_type,
            "subject": subject,
            "recipients": recipients,
            "showroom_id": showroom_id,
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "success": False,
            "error": str(e)
        })
        
        return False


# ============ NOTIFICATION TEMPLATES ============

def get_notification_html(title: str, content: str, footer_text: str = None):
    """Generate HTML template for notifications"""
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #1a1a2e; color: white; padding: 20px; text-align: center;">
            <h1 style="margin: 0; color: #f0c14b;">TILE STATION</h1>
            <p style="margin: 5px 0 0 0; font-size: 14px;">Notification</p>
        </div>
        
        <div style="padding: 30px; background: #f9f9f9;">
            <h2 style="color: #1a1a2e; margin-top: 0;">{title}</h2>
            {content}
        </div>
        
        <div style="background: #1a1a2e; color: #888; padding: 15px; text-align: center; font-size: 12px;">
            <p style="margin: 0;">{footer_text or 'Tile Station Notification System'}</p>
            <p style="margin: 5px 0 0 0;">This is an automated message</p>
        </div>
    </div>
    """


# ============ SPECIFIC NOTIFICATION FUNCTIONS ============

async def notify_new_order(db, order: dict, showroom_id: str = None):
    """Send notification for new order"""
    customer_name = order.get("customer_name", "Customer")
    order_id = order.get("id", order.get("order_number", "N/A"))
    total = order.get("total", 0)
    
    content = f"""
    <p>A new order has been placed:</p>
    <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
        <tr style="background: #e9e9e9;">
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Order ID</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">{order_id}</td>
        </tr>
        <tr>
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Customer</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">{customer_name}</td>
        </tr>
        <tr style="background: #e9e9e9;">
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Total</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">£{total:.2f}</td>
        </tr>
        <tr>
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Items</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">{len(order.get('items', []))} item(s)</td>
        </tr>
    </table>
    <p>Please review and process this order.</p>
    """
    
    await send_notification_email(
        db,
        "new_order",
        f"🛒 New Order #{order_id} from {customer_name}",
        get_notification_html("New Order Received", content),
        showroom_id
    )


async def notify_order_status_change(db, order: dict, old_status: str, new_status: str, showroom_id: str = None):
    """Send notification for order status change"""
    order_id = order.get("id", order.get("order_number", "N/A"))
    customer_name = order.get("customer_name", "Customer")
    
    content = f"""
    <p>An order status has been updated:</p>
    <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
        <tr style="background: #e9e9e9;">
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Order ID</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">{order_id}</td>
        </tr>
        <tr>
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Customer</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">{customer_name}</td>
        </tr>
        <tr style="background: #e9e9e9;">
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Previous Status</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">{old_status}</td>
        </tr>
        <tr>
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>New Status</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd; color: #2563eb; font-weight: bold;">{new_status}</td>
        </tr>
    </table>
    """
    
    await send_notification_email(
        db,
        "order_status_change",
        f"📦 Order #{order_id} Status: {new_status}",
        get_notification_html("Order Status Updated", content),
        showroom_id
    )


async def notify_payment_received(db, invoice: dict, payment_amount: float, showroom_id: str = None):
    """Send notification for payment received"""
    invoice_number = invoice.get("invoice_number", invoice.get("id", "N/A"))
    customer_name = invoice.get("customer_name", "Customer")
    total = invoice.get("gross_total", 0)
    outstanding = invoice.get("amount_outstanding", 0)
    
    content = f"""
    <p>A payment has been recorded:</p>
    <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
        <tr style="background: #e9e9e9;">
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Invoice</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">{invoice_number}</td>
        </tr>
        <tr>
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Customer</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">{customer_name}</td>
        </tr>
        <tr style="background: #dcfce7;">
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Payment Amount</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd; color: #16a34a; font-weight: bold;">£{payment_amount:.2f}</td>
        </tr>
        <tr>
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Invoice Total</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">£{total:.2f}</td>
        </tr>
        <tr style="background: #e9e9e9;">
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Outstanding</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">£{outstanding:.2f}</td>
        </tr>
    </table>
    """
    
    await send_notification_email(
        db,
        "payment_received",
        f"💰 Payment Received: £{payment_amount:.2f} for Invoice #{invoice_number}",
        get_notification_html("Payment Received", content),
        showroom_id
    )


async def notify_low_stock(db, product: dict, current_stock: float, threshold: float):
    """Send notification for low stock"""
    product_name = product.get("name", "Unknown Product")
    product_code = product.get("product_code", "N/A")
    
    content = f"""
    <p style="color: #d97706;">⚠️ Low stock alert:</p>
    <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
        <tr style="background: #fef3c7;">
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Product</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">{product_name}</td>
        </tr>
        <tr>
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Product Code</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">{product_code}</td>
        </tr>
        <tr style="background: #fef3c7;">
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Current Stock</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd; color: #d97706; font-weight: bold;">{current_stock} m²</td>
        </tr>
        <tr>
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Threshold</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">{threshold} m²</td>
        </tr>
    </table>
    <p>Please consider restocking this product.</p>
    """
    
    await send_notification_email(
        db,
        "low_stock",
        f"⚠️ Low Stock Alert: {product_name} ({current_stock} m² remaining)",
        get_notification_html("Low Stock Alert", content)
    )


async def notify_out_of_stock(db, product: dict):
    """Send notification for out of stock"""
    product_name = product.get("name", "Unknown Product")
    product_code = product.get("product_code", "N/A")
    
    content = f"""
    <p style="color: #dc2626;">🚨 Out of stock alert:</p>
    <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
        <tr style="background: #fee2e2;">
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Product</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">{product_name}</td>
        </tr>
        <tr>
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Product Code</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">{product_code}</td>
        </tr>
        <tr style="background: #fee2e2;">
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Status</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd; color: #dc2626; font-weight: bold;">OUT OF STOCK</td>
        </tr>
    </table>
    <p>This product is now out of stock and unavailable for sale.</p>
    """
    
    await send_notification_email(
        db,
        "out_of_stock",
        f"🚨 Out of Stock: {product_name}",
        get_notification_html("Out of Stock Alert", content)
    )


async def notify_new_customer(db, customer: dict):
    """Send notification for new customer registration"""
    customer_name = customer.get("name", "Unknown")
    customer_email = customer.get("email", "N/A")
    customer_phone = customer.get("phone", "N/A")
    
    content = f"""
    <p>A new customer has registered:</p>
    <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
        <tr style="background: #e9e9e9;">
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Name</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">{customer_name}</td>
        </tr>
        <tr>
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Email</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">{customer_email}</td>
        </tr>
        <tr style="background: #e9e9e9;">
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Phone</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">{customer_phone}</td>
        </tr>
    </table>
    """
    
    await send_notification_email(
        db,
        "new_customer",
        f"👤 New Customer Registration: {customer_name}",
        get_notification_html("New Customer Registered", content)
    )


async def notify_new_bulk_inquiry(db, inquiry: dict, showroom_id: str = None):
    """Send notification for new bulk inquiry"""
    customer_name = inquiry.get("customer_name", inquiry.get("name", "Unknown"))
    customer_email = inquiry.get("email", "N/A")
    product_name = inquiry.get("product_name", "N/A")
    quantity = inquiry.get("quantity", "N/A")
    message = inquiry.get("message", inquiry.get("notes", "No message"))
    
    content = f"""
    <p>A new bulk inquiry has been submitted:</p>
    <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
        <tr style="background: #dbeafe;">
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Customer</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">{customer_name}</td>
        </tr>
        <tr>
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Email</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">{customer_email}</td>
        </tr>
        <tr style="background: #dbeafe;">
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Product</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">{product_name}</td>
        </tr>
        <tr>
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Quantity</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">{quantity}</td>
        </tr>
        <tr style="background: #dbeafe;">
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Message</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">{message}</td>
        </tr>
    </table>
    <p>Please respond to this inquiry promptly.</p>
    """
    
    await send_notification_email(
        db,
        "new_bulk_inquiry",
        f"📋 New Bulk Inquiry from {customer_name}",
        get_notification_html("New Bulk Inquiry", content),
        showroom_id
    )


async def notify_staff_invite_accepted(db, staff: dict):
    """Send notification when staff accepts invite"""
    staff_name = staff.get("name", "Unknown")
    staff_email = staff.get("email", "N/A")
    staff_role = staff.get("role", "staff")
    
    content = f"""
    <p>A staff member has accepted their invitation:</p>
    <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
        <tr style="background: #dcfce7;">
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Name</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">{staff_name}</td>
        </tr>
        <tr>
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Email</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">{staff_email}</td>
        </tr>
        <tr style="background: #dcfce7;">
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Role</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">{staff_role.title()}</td>
        </tr>
    </table>
    <p>They can now access the system with their assigned permissions.</p>
    """
    
    await send_notification_email(
        db,
        "staff_invite_accepted",
        f"✅ Staff Joined: {staff_name} ({staff_role})",
        get_notification_html("Staff Invite Accepted", content)
    )


async def notify_daily_summary(db, summary: dict):
    """Send daily sales summary"""
    date = summary.get("date", datetime.now().strftime("%Y-%m-%d"))
    total_orders = summary.get("total_orders", 0)
    total_revenue = summary.get("total_revenue", 0)
    total_invoices = summary.get("total_invoices", 0)
    new_customers = summary.get("new_customers", 0)
    
    content = f"""
    <p>Here's your daily summary for {date}:</p>
    <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
        <tr style="background: #e9e9e9;">
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>📦 Orders</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">{total_orders}</td>
        </tr>
        <tr>
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>🧾 Invoices</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">{total_invoices}</td>
        </tr>
        <tr style="background: #dcfce7;">
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>💰 Revenue</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd; color: #16a34a; font-weight: bold;">£{total_revenue:.2f}</td>
        </tr>
        <tr>
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>👤 New Customers</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">{new_customers}</td>
        </tr>
    </table>
    """
    
    await send_notification_email(
        db,
        "daily_summary",
        f"📊 Daily Summary for {date}",
        get_notification_html(f"Daily Summary - {date}", content)
    )

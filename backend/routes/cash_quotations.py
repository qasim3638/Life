"""
Cash Quotation management routes - No VAT calculations
Total is subtotal without VAT. Counts towards daily/weekly/monthly sales.
"""
import uuid
import io
import os
import base64
import logging
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config import get_db
from services import get_current_user, is_admin_user, log_audit

# Check for reportlab availability
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    logging.warning("reportlab not available - PDF generation disabled")

router = APIRouter(prefix="/cash-quotations", tags=["Cash Quotations"])


class CashQuotationLineItem(BaseModel):
    product_id: Optional[str] = None
    product_name: str
    sku: Optional[str] = None
    quantity: float
    m2: Optional[float] = 0
    price: float
    due_price: Optional[float] = None
    total: Optional[float] = None
    discount: float = 0


class CompanyInfo(BaseModel):
    name: str
    address: str
    city: str
    telephone: str
    email: str
    companyNo: str
    vatNo: str


class CashQuotationCreate(BaseModel):
    quotation_no: str
    date: str
    time: str
    showroom_id: Optional[str] = None
    showroom_name: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    customer_address: Optional[str] = None
    sales_person: Optional[str] = None
    validity_days: int = 30
    notes: Optional[str] = None
    line_items: List[CashQuotationLineItem]
    subtotal: Optional[float] = 0
    # No VAT for cash quotations - total equals subtotal
    total: Optional[float] = 0
    total_savings: Optional[float] = 0
    company_info: Optional[CompanyInfo] = None


class CashQuotationUpdate(BaseModel):
    quotation_no: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    showroom_id: Optional[str] = None
    showroom_name: Optional[str] = None
    showroom_id: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    customer_address: Optional[str] = None
    sales_person: Optional[str] = None
    validity_days: Optional[int] = None
    notes: Optional[str] = None
    line_items: Optional[List[CashQuotationLineItem]] = None
    subtotal: Optional[float] = None
    total: Optional[float] = None
    total_savings: Optional[float] = None
    company_info: Optional[CompanyInfo] = None
    status: Optional[str] = None


@router.get("")
async def get_cash_quotations(
    showroom_id: Optional[str] = None,
    status: Optional[str] = None,
    include_deleted: bool = False,
    current_user: dict = Depends(get_current_user)
):
    """Get all cash quotations with optional filters"""
    db = get_db()
    
    query = {}
    
    # Exclude deleted documents unless specifically requested (super_admin only)
    if include_deleted and current_user.get("role") == "super_admin":
        query["deleted_at"] = {"$exists": True}
    else:
        query["deleted_at"] = {"$exists": False}
    
    # Filter by showroom for non-super-admin users with assigned showroom
    user_showroom_id = current_user.get("showroom_id")
    is_super_admin = current_user.get("role") == "super_admin"
    
    if not is_super_admin and user_showroom_id:
        # Staff/Manager/Admin with assigned showroom can only see their showroom's quotations
        query["showroom_id"] = user_showroom_id
    elif showroom_id:
        # Super admin can filter by any showroom
        query["showroom_id"] = showroom_id
    
    if status:
        query["status"] = status
    
    quotations = await db.cash_quotations.find(query, {"_id": 0}).sort("created_at", -1).to_list(5000)
    return quotations


@router.get("/{quotation_id}")
async def get_cash_quotation(quotation_id: str, current_user: dict = Depends(get_current_user)):
    """Get a single cash quotation by ID"""
    db = get_db()
    quotation = await db.cash_quotations.find_one({"id": quotation_id}, {"_id": 0})
    if not quotation:
        raise HTTPException(status_code=404, detail="Cash quotation not found")
    return quotation


@router.post("")
async def create_cash_quotation(input: CashQuotationCreate, current_user: dict = Depends(get_current_user)):
    """Create a new cash quotation (no VAT)"""
    user_permissions = current_user.get("permissions", [])
    has_access = is_admin_user(current_user) or "epos" in user_permissions
    if not has_access:
        raise HTTPException(status_code=403, detail="Access denied")
    
    db = get_db()
    
    # Check for duplicate quotation number
    existing = await db.cash_quotations.find_one({"quotation_no": input.quotation_no}, {"_id": 0, "id": 1})
    if existing:
        raise HTTPException(status_code=400, detail=f"Cash Quotation {input.quotation_no} already exists.")
    
    quotation_id = str(uuid.uuid4())
    
    # Calculate expiry date
    from datetime import timedelta
    try:
        date_parts = input.date.split('/')
        if len(date_parts) == 3:
            quotation_date = datetime(int(date_parts[2]), int(date_parts[1]), int(date_parts[0]))
        else:
            quotation_date = datetime.now(timezone.utc)
    except (ValueError, IndexError):
        quotation_date = datetime.now(timezone.utc)
    
    expiry_date = quotation_date + timedelta(days=input.validity_days)
    
    # For cash quotations: total = subtotal (no VAT)
    total = input.subtotal or 0
    
    quotation_dict = {
        "id": quotation_id,
        "quotation_no": input.quotation_no,
        "type": "cash",  # Mark as cash quotation
        "date": input.date,
        "time": input.time,
        "showroom_id": input.showroom_id,
        "showroom_name": input.showroom_name,
        "customer_name": input.customer_name,
        "customer_phone": input.customer_phone,
        "customer_email": input.customer_email,
        "customer_address": input.customer_address,
        "sales_person": input.sales_person,
        "validity_days": input.validity_days,
        "expiry_date": expiry_date.isoformat(),
        "notes": input.notes,
        "line_items": [item.model_dump() for item in input.line_items],
        "subtotal": input.subtotal or 0,
        "vat": 0,  # No VAT for cash quotations
        "total": total,  # Total equals subtotal
        "total_savings": input.total_savings or 0,
        "company_info": input.company_info.model_dump() if input.company_info else None,
        "status": "active",
        "created_by": current_user.get("email"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.cash_quotations.insert_one(quotation_dict)
    
    # Audit log
    await log_audit(
        action="CREATE",
        entity_type="cash_quotation",
        user=current_user,
        entity_id=quotation_id,
        entity_name=input.quotation_no,
        after_data={"quotation_no": input.quotation_no, "customer": input.customer_name, "total": total},
        details=f"Cash Quotation created: {input.quotation_no}"
    )
    
    return {
        "id": quotation_id,
        "quotation_no": input.quotation_no,
        "message": "Cash quotation created successfully"
    }


@router.put("/{quotation_id}")
async def update_cash_quotation(
    quotation_id: str,
    input: CashQuotationUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update an existing cash quotation"""
    user_permissions = current_user.get("permissions", [])
    has_access = is_admin_user(current_user) or "epos" in user_permissions
    if not has_access:
        raise HTTPException(status_code=403, detail="Access denied")
    
    db = get_db()
    
    existing = await db.cash_quotations.find_one({"id": quotation_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Cash quotation not found")
    
    update_dict = {"updated_at": datetime.now(timezone.utc).isoformat()}
    
    # Update fields if provided
    for field in ["quotation_no", "date", "time", "showroom_id", "customer_name", 
                  "customer_phone", "customer_email", "customer_address", "sales_person",
                  "validity_days", "notes", "subtotal", "total", "total_savings", "status"]:
        value = getattr(input, field, None)
        if value is not None:
            update_dict[field] = value
    
    if input.line_items is not None:
        update_dict["line_items"] = [item.model_dump() for item in input.line_items]
    
    if input.company_info is not None:
        update_dict["company_info"] = input.company_info.model_dump()
    
    # Ensure VAT is always 0 for cash quotations
    update_dict["vat"] = 0
    
    # Recalculate expiry date if validity_days or date changed
    if input.validity_days is not None or input.date is not None:
        from datetime import timedelta
        date_str = input.date or existing.get("date", "")
        validity = input.validity_days if input.validity_days is not None else existing.get("validity_days", 30)
        try:
            date_parts = date_str.split('/')
            if len(date_parts) == 3:
                quotation_date = datetime(int(date_parts[2]), int(date_parts[1]), int(date_parts[0]))
                expiry_date = quotation_date + timedelta(days=validity)
                update_dict["expiry_date"] = expiry_date.isoformat()
        except (ValueError, IndexError):
            pass
    
    await db.cash_quotations.update_one({"id": quotation_id}, {"$set": update_dict})
    
    return {"message": "Cash quotation updated successfully", "id": quotation_id}


@router.delete("/{quotation_id}")
async def delete_cash_quotation(quotation_id: str, current_user: dict = Depends(get_current_user)):
    """Soft delete a cash quotation (Super Admin only) - moves to trash for 30 days"""
    # Only Super Admin can delete documents
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can delete documents")
    
    db = get_db()
    
    existing = await db.cash_quotations.find_one({"id": quotation_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Cash quotation not found")
    
    if existing.get("deleted_at"):
        raise HTTPException(status_code=400, detail="Cash quotation is already in trash")
    
    deleted_at = datetime.now(timezone.utc)
    await db.cash_quotations.update_one(
        {"id": quotation_id},
        {"$set": {
            "deleted_at": deleted_at.isoformat(),
            "deleted_by": current_user.get("email"),
            "deleted_by_name": current_user.get("name", current_user.get("email"))
        }}
    )
    
    await log_audit(
        action="SOFT_DELETE",
        entity_type="cash_quotation",
        user=current_user,
        entity_id=quotation_id,
        entity_name=existing.get("quotation_no"),
        details=f"Cash Quotation {existing.get('quotation_no')} moved to trash. Can be restored or permanently deleted from Trash."
    )
    
    return {"message": "Cash quotation moved to trash. It can be restored or permanently deleted from Trash."}


@router.post("/{quotation_id}/restore")
async def restore_cash_quotation(quotation_id: str, current_user: dict = Depends(get_current_user)):
    """Restore a soft-deleted cash quotation from trash (Super Admin only)"""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can restore documents")
    
    db = get_db()
    quotation = await db.cash_quotations.find_one({"id": quotation_id})
    if not quotation:
        raise HTTPException(status_code=404, detail="Cash quotation not found")
    
    if not quotation.get("deleted_at"):
        raise HTTPException(status_code=400, detail="Cash quotation is not in trash")
    
    await db.cash_quotations.update_one(
        {"id": quotation_id},
        {"$unset": {"deleted_at": "", "deleted_by": "", "deleted_by_name": ""}}
    )
    
    await log_audit(
        action="RESTORE",
        entity_type="cash_quotation",
        user=current_user,
        entity_id=quotation_id,
        entity_name=quotation.get("quotation_no"),
        details=f"Cash Quotation {quotation.get('quotation_no')} restored from trash."
    )
    
    return {"message": "Cash quotation restored successfully"}


@router.delete("/{quotation_id}/permanent")
async def permanent_delete_cash_quotation(quotation_id: str, current_user: dict = Depends(get_current_user)):
    """Permanently delete a cash quotation (Super Admin only)"""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can permanently delete documents")
    
    db = get_db()
    quotation = await db.cash_quotations.find_one({"id": quotation_id})
    if not quotation:
        raise HTTPException(status_code=404, detail="Cash quotation not found")
    
    await db.cash_quotations.delete_one({"id": quotation_id})
    
    await log_audit(
        action="PERMANENT_DELETE",
        entity_type="cash_quotation",
        user=current_user,
        entity_id=quotation_id,
        entity_name=quotation.get("quotation_no"),
        details=f"Cash Quotation {quotation.get('quotation_no')} permanently deleted"
    )
    
    return {"message": "Cash quotation permanently deleted"}


@router.post("/{quotation_id}/convert-to-invoice")
async def convert_to_invoice(quotation_id: str, current_user: dict = Depends(get_current_user)):
    """Mark cash quotation as converted - frontend will open invoice form with pre-filled data"""
    db = get_db()
    
    existing = await db.cash_quotations.find_one({"id": quotation_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Cash quotation not found")
    
    if existing.get("status") == "converted":
        raise HTTPException(status_code=400, detail="This quotation has already been converted")
    
    # Mark cash quotation as converted
    now = datetime.now(timezone.utc)
    await db.cash_quotations.update_one(
        {"id": quotation_id},
        {"$set": {
            "status": "converted",
            "converted_at": now.isoformat(),
            "updated_at": now.isoformat()
        }}
    )
    
    return {"message": "Cash quotation marked as converted", "quotation": existing}


@router.post("/{quotation_id}/revert-to-active")
async def revert_cash_quotation_to_active(quotation_id: str, current_user: dict = Depends(get_current_user)):
    """Revert a converted cash quotation back to active - Super Admin only"""
    # Only Super Admins can revert
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admins can revert quotations")
    
    db = get_db()
    
    existing = await db.cash_quotations.find_one({"id": quotation_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Cash quotation not found")
    
    if existing.get("status") != "converted":
        raise HTTPException(status_code=400, detail="Only converted quotations can be reverted")
    
    # Revert cash quotation back to active
    now = datetime.now(timezone.utc)
    await db.cash_quotations.update_one(
        {"id": quotation_id},
        {"$set": {
            "status": "active",
            "reverted_at": now.isoformat(),
            "reverted_by": current_user.get("email"),
            "updated_at": now.isoformat()
        },
        "$unset": {
            "converted_at": ""
        }}
    )
    
    # Log audit
    await log_audit(
        action="REVERT_CASH_QUOTATION",
        entity_type="cash_quotation",
        user=current_user,
        entity_id=quotation_id,
        entity_name=existing.get("quotation_no"),
        details=f"Cash Quotation {existing.get('quotation_no')} reverted from converted to active"
    )
    
    return {"message": "Cash quotation reverted to active", "quotation_no": existing.get("quotation_no")}


@router.get("/summary/sales")
async def get_cash_quotation_sales_summary(
    period: str = "daily",  # daily, weekly, monthly
    showroom_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get cash quotation sales summary for daily/weekly/monthly reports"""
    db = get_db()
    
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    
    # Determine date range based on period
    if period == "daily":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "weekly":
        # Week runs Sunday to Saturday
        days_since_sunday = (now.weekday() + 1) % 7
        start_date = now - timedelta(days=days_since_sunday)
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "monthly":
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    query = {
        "created_at": {"$gte": start_date.isoformat()},
        "status": {"$in": ["active", "converted"]}
    }
    
    if showroom_id:
        query["showroom_id"] = showroom_id
    
    quotations = await db.cash_quotations.find(query, {"_id": 0, "total": 1, "subtotal": 1}).to_list(100000)
    
    total_sales = sum(q.get("total", q.get("subtotal", 0)) for q in quotations)
    count = len(quotations)
    
    return {
        "period": period,
        "start_date": start_date.isoformat(),
        "total_sales": total_sales,
        "count": count,
        "showroom_id": showroom_id
    }


# ============ PDF GENERATION ============

async def generate_cash_quotation_pdf_bytes(quotation: dict) -> bytes:
    """Generate PDF bytes for a cash quotation"""
    if not REPORTLAB_AVAILABLE:
        raise Exception("PDF generation not available")
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, 
                          rightMargin=15*mm, leftMargin=15*mm,
                          topMargin=15*mm, bottomMargin=15*mm)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle('CustomTitle', parent=styles['Title'], 
                                  fontSize=18, spaceAfter=20)
    elements.append(Paragraph(f"Cash Quotation: {quotation.get('quotation_no', 'N/A')}", title_style))
    elements.append(Spacer(1, 10*mm))
    
    # Customer Info
    customer_data = [
        ["Customer:", quotation.get("customer_name", "-")],
        ["Phone:", quotation.get("customer_phone", "-")],
        ["Date:", quotation.get("date", "-")],
        ["Valid Until:", datetime.fromisoformat(quotation.get("expiry_date", datetime.now(timezone.utc).isoformat())).strftime("%d/%m/%Y") if quotation.get("expiry_date") else "-"],
    ]
    customer_table = Table(customer_data, colWidths=[80, 200])
    customer_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(customer_table)
    elements.append(Spacer(1, 10*mm))
    
    # Line Items Table
    # Style for product names to allow wrapping
    product_style = ParagraphStyle('ProductName', fontSize=9, leading=11)
    
    items_data = [["Product", "SKU", "Qty", "Price", "Total"]]
    for item in quotation.get("line_items", []):
        product_name = item.get("product_name", "-")
        product_para = Paragraph(product_name, product_style)
        items_data.append([
            product_para,
            item.get("sku", "-"),
            str(item.get("quantity", 0)),
            f"£{item.get('price', 0):.2f}",
            f"£{item.get('total', 0):.2f}"
        ])
    
    items_table = Table(items_data, colWidths=[200, 60, 40, 50, 50])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 10*mm))
    
    # Totals (No VAT for cash quotations)
    totals_data = [
        ["Total (No VAT):", f"£{quotation.get('total', quotation.get('subtotal', 0)):.2f}"]
    ]
    totals_table = Table(totals_data, colWidths=[340, 60])
    totals_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
    ]))
    elements.append(totals_table)
    
    # Notes
    if quotation.get("notes"):
        elements.append(Spacer(1, 10*mm))
        elements.append(Paragraph(f"<b>Notes:</b> {quotation.get('notes')}", styles['Normal']))
    
    doc.build(elements)
    return buffer.getvalue()


@router.get("/{quotation_id}/pdf")
async def generate_cash_quotation_pdf(quotation_id: str, current_user: dict = Depends(get_current_user)):
    """Generate PDF for a cash quotation"""
    if not REPORTLAB_AVAILABLE:
        raise HTTPException(status_code=500, detail="PDF generation not available")
    
    db = get_db()
    quotation = await db.cash_quotations.find_one({"id": quotation_id}, {"_id": 0})
    if not quotation:
        raise HTTPException(status_code=404, detail="Cash quotation not found")
    
    pdf_bytes = await generate_cash_quotation_pdf_bytes(quotation)
    filename = f"CashQuotation_{quotation.get('quotation_no', 'unknown')}.pdf"
    
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ============ EMAIL CASH QUOTATION ============

class CashQuotationEmailRequest(BaseModel):
    email: str
    subject: Optional[str] = None
    message: Optional[str] = None


@router.post("/{quotation_id}/email")
async def email_cash_quotation_pdf(quotation_id: str, request: CashQuotationEmailRequest, current_user: dict = Depends(get_current_user)):
    """Send cash quotation PDF via email"""
    try:
        import resend
        RESEND_AVAILABLE = True
    except ImportError:
        RESEND_AVAILABLE = False
    
    if not RESEND_AVAILABLE:
        raise HTTPException(status_code=500, detail="Email service not available")
    
    db = get_db()
    quotation = await db.cash_quotations.find_one({"id": quotation_id}, {"_id": 0})
    if not quotation:
        raise HTTPException(status_code=404, detail="Cash quotation not found")
    
    # Generate PDF
    try:
        pdf_bytes = await generate_cash_quotation_pdf_bytes(quotation)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")
    
    quotation_no = quotation.get("quotation_no", "N/A")
    customer_name = quotation.get("customer_name", "Customer")
    total = quotation.get("total", quotation.get("subtotal", 0))
    
    custom_message = request.message or ""
    if custom_message:
        custom_message = f"<p style='margin-bottom: 20px; padding: 15px; background: #f0f9ff; border-left: 4px solid #2563eb;'>{custom_message}</p>"
    
    subject = request.subject or f"Your Cash Quotation {quotation_no} from Tile Station"
    
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #1e40af;">Cash Quotation {quotation_no}</h2>
        <p>Dear {customer_name},</p>
        {custom_message}
        <p>Please find attached your cash quotation.</p>
        <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
            <tr><td><strong>Quotation No:</strong></td><td>{quotation_no}</td></tr>
            <tr><td><strong>Total (No VAT):</strong></td><td style="font-size: 18px; color: #1e40af;">£{total:.2f}</td></tr>
        </table>
        <p>Thank you for your interest!</p>
        <p><strong>Tile Station</strong><br/>
        Tel: 01474 878 989<br/>
        Email: info@tilestation.co.uk</p>
    </body>
    </html>
    """
    
    resend_api_key = os.environ.get("RESEND_API_KEY")
    if not resend_api_key:
        raise HTTPException(status_code=500, detail="Email service not configured")
    
    resend.api_key = resend_api_key
    
    try:
        params = {
            "from": "Tile Station <noreply@tilestation.co.uk>",
            "to": [request.email],
            "subject": subject,
            "html": html_content,
            "attachments": [{
                "filename": f"{quotation_no}.pdf",
                "content": base64.b64encode(pdf_bytes).decode()
            }]
        }
        resend.Emails.send(params)
        return {"message": "Email sent successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

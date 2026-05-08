"""
CreditNote management routes
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from config import get_db
from services import get_current_user, is_admin_user, log_audit

router = APIRouter(prefix="/credit_notes", tags=["CreditNotes"])


# ============ MODELS ============

class CreditNoteLineItem(BaseModel):
    product_id: Optional[str] = None
    product_name: str
    sku: Optional[str] = None
    quantity: float
    original_price: float
    credit_note_price: float
    total: float
    reason: Optional[str] = ""

class CreditNoteCreate(BaseModel):
    credit_note_no: str
    date: str
    time: Optional[str] = None
    original_invoice_no: Optional[str] = None
    original_invoice_id: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    customer_address: Optional[str] = None
    notes: Optional[str] = None
    sales_person: Optional[str] = None
    staff_pin: Optional[str] = None
    credit_note_method: Optional[str] = None  # Cash, Card, Bank Transfer, Store Credit
    credit_note_type: Optional[str] = None  # Full CreditNote, Partial CreditNote, Exchange
    showroom_id: Optional[str] = None
    showroom_name: Optional[str] = None
    line_items: List[CreditNoteLineItem]
    subtotal: float
    vat: float
    gross_total: float
    restocking_fee: Optional[float] = 0
    net_credit_note: Optional[float] = None  # gross_total - restocking_fee

class CreditNoteUpdate(BaseModel):
    credit_note_no: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    customer_address: Optional[str] = None
    notes: Optional[str] = None
    sales_person: Optional[str] = None
    credit_note_method: Optional[str] = None
    credit_note_type: Optional[str] = None
    line_items: Optional[List[CreditNoteLineItem]] = None
    subtotal: Optional[float] = None
    vat: Optional[float] = None
    gross_total: Optional[float] = None
    restocking_fee: Optional[float] = None
    net_credit_note: Optional[float] = None
    status: Optional[str] = None


# ============ ROUTES ============

@router.post("")
async def create_credit_note(input: CreditNoteCreate, current_user: dict = Depends(get_current_user)):
    """Create a new credit note and restore stock"""
    # Allow admin users OR users with epos permission
    user_permissions = current_user.get("permissions", [])
    has_access = is_admin_user(current_user) or "epos" in user_permissions
    if not has_access:
        raise HTTPException(status_code=403, detail="Access denied. You need admin role or EPOS permission.")
    
    # Validate line items
    if not input.line_items or len(input.line_items) == 0:
        raise HTTPException(status_code=400, detail="CreditNote must have at least one line item")
    
    db = get_db()
    
    # Check for duplicate credit note number
    existing_cn = await db.credit_notes.find_one({"credit_note_no": input.credit_note_no}, {"_id": 0, "id": 1})
    if existing_cn:
        raise HTTPException(status_code=400, detail=f"Credit Note {input.credit_note_no} already exists. Cannot save duplicate.")
    
    # Verify staff PIN if provided
    staff_member = None
    if input.staff_pin:
        staff_member = await db.staff_pins.find_one({"pin": input.staff_pin, "active": True}, {"_id": 0})
        if not staff_member:
            raise HTTPException(status_code=401, detail="Invalid staff PIN")
    
    # Restore stock for each credit_noteed item
    for item in input.line_items:
        if item.product_id and item.product_id.strip():
            product = await db.products.find_one({"id": item.product_id}, {"_id": 0})
            if product:
                new_stock = product.get("stock", 0) + int(item.quantity)
                await db.products.update_one(
                    {"id": item.product_id},
                    {"$set": {"stock": new_stock}}
                )
    
    # Calculate net credit_note
    net_credit_note = input.gross_total - (input.restocking_fee or 0)
    
    # Save credit_note
    credit_note_dict = {
        "id": str(uuid.uuid4()),
        "credit_note_no": input.credit_note_no,
        "date": input.date,
        "time": input.time,
        "original_invoice_no": input.original_invoice_no,
        "original_invoice_id": input.original_invoice_id,
        "customer_name": input.customer_name,
        "customer_phone": input.customer_phone,
        "customer_email": input.customer_email,
        "customer_address": input.customer_address,
        "notes": input.notes,
        "sales_person": staff_member["name"] if staff_member else input.sales_person,
        "staff_id": staff_member["id"] if staff_member else None,
        "staff_name": staff_member["name"] if staff_member else None,
        "credit_note_method": input.credit_note_method,
        "credit_note_type": input.credit_note_type,
        "showroom_id": input.showroom_id,
        "showroom_name": input.showroom_name,
        "line_items": [item.model_dump() for item in input.line_items],
        "subtotal": input.subtotal,
        "vat": input.vat,
        "gross_total": input.gross_total,
        "restocking_fee": input.restocking_fee or 0,
        "net_credit_note": net_credit_note,
        "status": "completed",
        "created_by": current_user["email"],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.credit_notes.insert_one(credit_note_dict)
    
    # Log audit trail
    await log_audit(
        action="CREATE",
        entity_type="credit_note",
        user=current_user,
        entity_id=credit_note_dict["id"],
        entity_name=credit_note_dict["credit_note_no"],
        after_data={
            "credit_note_no": credit_note_dict["credit_note_no"],
            "customer_name": credit_note_dict.get("customer_name"),
            "gross_total": credit_note_dict["gross_total"],
            "net_credit_note": credit_note_dict["net_credit_note"],
            "showroom_name": credit_note_dict.get("showroom_name"),
            "items_count": len(credit_note_dict["line_items"])
        },
        details=f"CreditNote {credit_note_dict['credit_note_no']} created for £{credit_note_dict['net_credit_note']:.2f}"
    )
    
    return {
        "message": "CreditNote processed and stock restored",
        "credit_note_id": credit_note_dict["id"],
        "credit_note_no": credit_note_dict["credit_note_no"],
        "net_credit_note": credit_note_dict["net_credit_note"],
        "staff_name": staff_member["name"] if staff_member else None
    }


@router.get("")
async def get_credit_notes(
    current_user: dict = Depends(get_current_user),
    search: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    showroom_id: Optional[str] = None,
    include_deleted: bool = False
):
    """Get all credit notes with optional search and filters"""
    user_permissions = current_user.get("permissions", [])
    has_access = is_admin_user(current_user) or "epos" in user_permissions
    if not has_access:
        raise HTTPException(status_code=403, detail="Access denied. You need admin role or EPOS permission.")
    
    db = get_db()
    query = {}
    
    # Exclude deleted documents unless specifically requested (super_admin only)
    if include_deleted and current_user.get("role") == "super_admin":
        query["deleted_at"] = {"$exists": True}
    else:
        query["deleted_at"] = {"$exists": False}
    
    # Filter by showroom for non-super-admin users
    user_showroom_id = current_user.get("showroom_id")
    if current_user.get("role") != "super_admin" and user_showroom_id:
        query["showroom_id"] = user_showroom_id
    elif showroom_id:
        query["showroom_id"] = showroom_id
    
    if search:
        search_query = [
            {"credit_note_no": {"$regex": search, "$options": "i"}},
            {"original_invoice_no": {"$regex": search, "$options": "i"}},
            {"customer_name": {"$regex": search, "$options": "i"}},
            {"customer_phone": {"$regex": search, "$options": "i"}},
            {"staff_name": {"$regex": search, "$options": "i"}},
        ]
        if "$or" not in query:
            query["$or"] = search_query
        else:
            query = {"$and": [query, {"$or": search_query}]}
    
    credit_notes = await db.credit_notes.find(query, {"_id": 0}).sort("created_at", -1).to_list(100000)
    return credit_notes


@router.get("/{credit_note_id}")
async def get_credit_note(credit_note_id: str, current_user: dict = Depends(get_current_user)):
    """Get single credit_note (admin only)"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    db = get_db()
    credit_note = await db.credit_notes.find_one({"id": credit_note_id}, {"_id": 0})
    if not credit_note:
        raise HTTPException(status_code=404, detail="CreditNote not found")
    
    return credit_note


@router.put("/{credit_note_id}")
async def update_credit_note(credit_note_id: str, input: CreditNoteUpdate, current_user: dict = Depends(get_current_user)):
    """Update an existing credit_note (admin only)"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    db = get_db()
    existing = await db.credit_notes.find_one({"id": credit_note_id})
    if not existing:
        raise HTTPException(status_code=404, detail="CreditNote not found")
    
    # Handle stock adjustments if line items changed
    if input.line_items is not None:
        old_items = {item["product_id"]: item["quantity"] for item in existing.get("line_items", []) if item.get("product_id")}
        
        # Reverse old stock restoration
        for product_id, old_qty in old_items.items():
            if product_id and product_id.strip():
                await db.products.update_one(
                    {"id": product_id},
                    {"$inc": {"stock": -int(old_qty)}}
                )
        
        # Apply new stock restoration
        for item in input.line_items:
            if item.product_id and item.product_id.strip():
                await db.products.update_one(
                    {"id": item.product_id},
                    {"$inc": {"stock": int(item.quantity)}}
                )
    
    # Build update data
    update_data = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": current_user["email"]
    }
    
    for field in ["credit_note_no", "date", "time", "customer_name", "customer_phone", 
                  "customer_email", "customer_address", "notes", "sales_person",
                  "credit_note_method", "credit_note_type", "subtotal", "vat", "gross_total",
                  "restocking_fee", "status"]:
        value = getattr(input, field, None)
        if value is not None:
            update_data[field] = value
    
    if input.line_items is not None:
        update_data["line_items"] = [item.model_dump() for item in input.line_items]
    
    # Recalculate net credit_note
    if input.gross_total is not None or input.restocking_fee is not None:
        gross = input.gross_total if input.gross_total is not None else existing.get("gross_total", 0)
        fee = input.restocking_fee if input.restocking_fee is not None else existing.get("restocking_fee", 0)
        update_data["net_credit_note"] = gross - fee
    
    await db.credit_notes.update_one({"id": credit_note_id}, {"$set": update_data})
    
    # Log audit
    await log_audit(
        action="UPDATE",
        entity_type="credit_note",
        user=current_user,
        entity_id=credit_note_id,
        entity_name=existing.get("credit_note_no"),
        before_data={"gross_total": existing.get("gross_total"), "net_credit_note": existing.get("net_credit_note")},
        after_data={"gross_total": update_data.get("gross_total", existing.get("gross_total")), 
                   "net_credit_note": update_data.get("net_credit_note", existing.get("net_credit_note"))},
        details=f"CreditNote {existing.get('credit_note_no')} updated"
    )
    
    return {"message": "CreditNote updated successfully", "credit_note_id": credit_note_id}


@router.delete("/{credit_note_id}")
async def delete_credit_note(credit_note_id: str, current_user: dict = Depends(get_current_user)):
    """Soft delete a credit note (Super Admin only) - moves to trash for 30 days"""
    # Only Super Admin can delete documents
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can delete documents")
    
    db = get_db()
    credit_note = await db.credit_notes.find_one({"id": credit_note_id})
    if not credit_note:
        raise HTTPException(status_code=404, detail="CreditNote not found")
    
    if credit_note.get("deleted_at"):
        raise HTTPException(status_code=400, detail="Credit note is already in trash")
    
    # Soft delete
    deleted_at = datetime.now(timezone.utc)
    await db.credit_notes.update_one(
        {"id": credit_note_id},
        {"$set": {
            "deleted_at": deleted_at.isoformat(),
            "deleted_by": current_user.get("email"),
            "deleted_by_name": current_user.get("name", current_user.get("email"))
        }}
    )
    
    # Reverse stock restoration for all line items
    for item in credit_note.get("line_items", []):
        product_id = item.get("product_id")
        if product_id and product_id.strip():
            await db.products.update_one(
                {"id": product_id},
                {"$inc": {"stock": -int(item["quantity"])}}
            )
    
    await log_audit(
        action="SOFT_DELETE",
        entity_type="credit_note",
        user=current_user,
        entity_id=credit_note_id,
        entity_name=credit_note.get("credit_note_no"),
        before_data={
            "credit_note_no": credit_note.get("credit_note_no"),
            "customer_name": credit_note.get("customer_name"),
            "net_credit_note": credit_note.get("net_credit_note")
        },
        details=f"CreditNote {credit_note.get('credit_note_no')} moved to trash, stock adjustments reversed. Can be restored or permanently deleted from Trash."
    )
    
    return {"message": "Credit note moved to trash. It can be restored or permanently deleted from Trash."}


@router.post("/{credit_note_id}/restore")
async def restore_credit_note(credit_note_id: str, current_user: dict = Depends(get_current_user)):
    """Restore a soft-deleted credit note from trash (Super Admin only)"""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can restore documents")
    
    db = get_db()
    credit_note = await db.credit_notes.find_one({"id": credit_note_id})
    if not credit_note:
        raise HTTPException(status_code=404, detail="Credit note not found")
    
    if not credit_note.get("deleted_at"):
        raise HTTPException(status_code=400, detail="Credit note is not in trash")
    
    await db.credit_notes.update_one(
        {"id": credit_note_id},
        {"$unset": {"deleted_at": "", "deleted_by": "", "deleted_by_name": ""}}
    )
    
    # Restore stock adjustments
    for item in credit_note.get("line_items", []):
        product_id = item.get("product_id")
        if product_id and product_id.strip():
            await db.products.update_one(
                {"id": product_id},
                {"$inc": {"stock": int(item["quantity"])}}
            )
    
    await log_audit(
        action="RESTORE",
        entity_type="credit_note",
        user=current_user,
        entity_id=credit_note_id,
        entity_name=credit_note.get("credit_note_no"),
        details=f"CreditNote {credit_note.get('credit_note_no')} restored from trash, stock adjustments restored."
    )
    
    return {"message": "Credit note restored successfully"}


@router.delete("/{credit_note_id}/permanent")
async def permanent_delete_credit_note(credit_note_id: str, current_user: dict = Depends(get_current_user)):
    """Permanently delete a credit note (Super Admin only)"""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can permanently delete documents")
    
    db = get_db()
    credit_note = await db.credit_notes.find_one({"id": credit_note_id})
    if not credit_note:
        raise HTTPException(status_code=404, detail="Credit note not found")
    
    await db.credit_notes.delete_one({"id": credit_note_id})
    
    await log_audit(
        action="PERMANENT_DELETE",
        entity_type="credit_note",
        user=current_user,
        entity_id=credit_note_id,
        entity_name=credit_note.get("credit_note_no"),
        details=f"CreditNote {credit_note.get('credit_note_no')} permanently deleted"
    )
    
    return {"message": "Credit note permanently deleted"}


@router.get("/summary/stats")
async def get_credit_note_stats(
    period: str = "month",
    showroom_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get credit_note statistics for analytics"""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    db = get_db()
    
    from datetime import timedelta
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
    
    query = {"created_at": {"$gte": start.isoformat()}}
    
    user_showroom_id = current_user.get("showroom_id")
    if current_user.get("role") != "super_admin" and user_showroom_id:
        query["showroom_id"] = user_showroom_id
    elif showroom_id:
        query["showroom_id"] = showroom_id
    
    credit_notes = await db.credit_notes.find(query, {"_id": 0}).to_list(100000)
    
    total_credit_notes = len(credit_notes)
    total_gross = sum(r.get("gross_total", 0) for r in credit_notes)
    total_net = sum(r.get("net_credit_note", 0) for r in credit_notes)
    total_restocking_fees = sum(r.get("restocking_fee", 0) for r in credit_notes)
    
    # Group by showroom
    by_showroom = {}
    for r in credit_notes:
        sid = r.get("showroom_id", "unassigned")
        sname = r.get("showroom_name", "Unassigned")
        if sid not in by_showroom:
            by_showroom[sid] = {"name": sname, "count": 0, "gross": 0, "net": 0, "fees": 0}
        by_showroom[sid]["count"] += 1
        by_showroom[sid]["gross"] += r.get("gross_total", 0)
        by_showroom[sid]["net"] += r.get("net_credit_note", 0)
        by_showroom[sid]["fees"] += r.get("restocking_fee", 0)
    
    return {
        "period": period,
        "total_credit_notes": total_credit_notes,
        "total_gross_credit_notes": round(total_gross, 2),
        "total_net_credit_notes": round(total_net, 2),
        "total_restocking_fees": round(total_restocking_fees, 2),
        "by_showroom": [{"showroom_id": k, **v} for k, v in by_showroom.items()]
    }


# ============ PDF GENERATION ============

import io
from fastapi.responses import StreamingResponse

# Try to import reportlab for PDF generation
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


async def generate_credit_note_pdf_bytes(credit_note: dict) -> bytes:
    """Generate PDF bytes for a credit note"""
    if not REPORTLAB_AVAILABLE:
        raise Exception("PDF generation not available")
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, 
                          rightMargin=15*mm, leftMargin=15*mm,
                          topMargin=15*mm, bottomMargin=15*mm)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Title Style (Red for Credit Note)
    title_style = ParagraphStyle('CreditNoteTitle', parent=styles['Title'], 
                                  fontSize=18, spaceAfter=10, textColor=colors.red)
    
    # Header
    elements.append(Paragraph("CREDIT NOTE", title_style))
    
    # Credit Note Number
    cn_no_style = ParagraphStyle('CNNo', parent=styles['Normal'], 
                                   fontSize=14, fontName='Helvetica-Bold', spaceAfter=20)
    elements.append(Paragraph(f"Credit Note No: {credit_note.get('credit_note_no', 'N/A')}", cn_no_style))
    elements.append(Spacer(1, 5*mm))
    
    # Customer and Credit Note Info (2 columns)
    info_data = [
        ["Customer:", credit_note.get("customer_name", "-"), "Date:", credit_note.get("date", "-")],
        ["Phone:", credit_note.get("customer_phone", "-"), "Original Invoice:", credit_note.get("original_invoice_no", "-")],
        ["Email:", credit_note.get("customer_email", "-"), "Method:", credit_note.get("credit_note_method", "-")],
        ["Store:", credit_note.get("showroom_name", "-"), "Type:", credit_note.get("credit_note_type", "-")],
    ]
    info_table = Table(info_data, colWidths=[60, 150, 80, 120])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 10*mm))
    
    # Line Items Table
    # Style for product names to allow wrapping
    product_style = ParagraphStyle('ProductName', fontSize=8, leading=10)
    
    items_data = [["Product", "SKU", "Qty", "Price", "Reason", "Total"]]
    for item in credit_note.get("line_items", []):
        product_name = item.get("product_name", "-")
        product_para = Paragraph(product_name, product_style)
        items_data.append([
            product_para,
            item.get("sku", "-")[:10] if item.get("sku") else "-",
            str(item.get("quantity", 0)),
            f"£{item.get('credit_note_price', item.get('creditNote_price', 0)):.2f}",
            (item.get("reason", "-") or "-")[:15],
            f"£{item.get('total', 0):.2f}"
        ])
    
    items_table = Table(items_data, colWidths=[160, 45, 35, 50, 60, 55])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.8, 0.2, 0.2)),  # Red header
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 10*mm))
    
    # Totals
    totals_data = [
        ["Subtotal:", f"£{credit_note.get('subtotal', 0):.2f}"],
        ["VAT (20%):", f"£{credit_note.get('vat', 0):.2f}"],
        ["Gross Total:", f"£{credit_note.get('gross_total', 0):.2f}"],
    ]
    
    # Add restocking fee if present
    restocking_fee = credit_note.get("restocking_fee", 0)
    if restocking_fee and restocking_fee > 0:
        totals_data.append(["Restocking Fee:", f"-£{restocking_fee:.2f}"])
    
    # Net Credit Note
    totals_data.append(["Net Credit Note:", f"£{credit_note.get('net_credit_note', credit_note.get('net_creditNote', 0)):.2f}"])
    
    totals_table = Table(totals_data, colWidths=[330, 70])
    totals_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -2), 'Helvetica'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.red),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.grey),
        ('TOPPADDING', (0, -1), (-1, -1), 8),
    ]))
    elements.append(totals_table)
    
    # Notes
    if credit_note.get("notes"):
        elements.append(Spacer(1, 10*mm))
        notes_style = ParagraphStyle('Notes', parent=styles['Normal'], fontSize=9)
        elements.append(Paragraph(f"<b>Notes:</b> {credit_note.get('notes')}", notes_style))
    
    # Footer
    elements.append(Spacer(1, 15*mm))
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.grey, alignment=TA_CENTER)
    elements.append(Paragraph("This credit note is valid as per our terms and conditions.", footer_style))
    elements.append(Paragraph(f"Processed by: {credit_note.get('staff_name', credit_note.get('processed_by', credit_note.get('created_by', '-')))}", footer_style))
    
    doc.build(elements)
    return buffer.getvalue()


@router.get("/{credit_note_id}/pdf")
async def generate_credit_note_pdf(credit_note_id: str, current_user: dict = Depends(get_current_user)):
    """Generate PDF for a credit note"""
    if not REPORTLAB_AVAILABLE:
        raise HTTPException(status_code=500, detail="PDF generation not available")
    
    db = get_db()
    credit_note = await db.credit_notes.find_one({"id": credit_note_id}, {"_id": 0})
    if not credit_note:
        raise HTTPException(status_code=404, detail="Credit note not found")
    
    pdf_bytes = await generate_credit_note_pdf_bytes(credit_note)
    filename = f"CreditNote_{credit_note.get('credit_note_no', 'unknown')}.pdf"
    
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

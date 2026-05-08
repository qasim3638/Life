"""
Proforma Invoice management routes
Includes VAT calculations. For pre-payment invoices with bank details.
"""
import uuid
import io
import os
import base64
import logging
from datetime import datetime, timezone, timedelta
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
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    logging.warning("reportlab not available - PDF generation disabled")

router = APIRouter(prefix="/proforma-invoices", tags=["Proforma Invoices"])

# Bank Details Constants
BANK_DETAILS = {
    "name": "TILE STATION LTD",
    "account_type": "Business",
    "account_number": "33604637",
    "sort_code": "23-05-80"
}


class ProformaLineItem(BaseModel):
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


class ProformaInvoiceCreate(BaseModel):
    proforma_no: str
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
    line_items: List[ProformaLineItem]
    subtotal: Optional[float] = 0
    vat: Optional[float] = 0
    gross_total: Optional[float] = 0
    total_savings: Optional[float] = 0
    company_info: Optional[CompanyInfo] = None


class ProformaInvoiceUpdate(BaseModel):
    proforma_no: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    showroom_id: Optional[str] = None
    showroom_name: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    customer_address: Optional[str] = None
    sales_person: Optional[str] = None
    validity_days: Optional[int] = None
    notes: Optional[str] = None
    line_items: Optional[List[ProformaLineItem]] = None
    subtotal: Optional[float] = None
    vat: Optional[float] = None
    gross_total: Optional[float] = None
    total_savings: Optional[float] = None
    company_info: Optional[CompanyInfo] = None
    status: Optional[str] = None


@router.get("")
async def get_proforma_invoices(
    current_user: dict = Depends(get_current_user),
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    skip: int = 0
):
    """Get all proforma invoices with optional filters"""
    db = get_db()
    query = {}
    
    if status and status != 'all':
        query["status"] = status
    
    if search:
        query["$or"] = [
            {"proforma_no": {"$regex": search, "$options": "i"}},
            {"customer_name": {"$regex": search, "$options": "i"}},
            {"customer_phone": {"$regex": search, "$options": "i"}}
        ]
    
    invoices = await db.proforma_invoices.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    total = await db.proforma_invoices.count_documents(query)
    
    return {"data": invoices, "total": total}


@router.get("/next-number")
async def get_next_proforma_number(current_user: dict = Depends(get_current_user)):
    """Get next proforma invoice number"""
    db = get_db()
    
    # Find the highest proforma number
    latest = await db.proforma_invoices.find_one(
        {},
        {"proforma_no": 1},
        sort=[("proforma_no", -1)]
    )
    
    if latest and latest.get("proforma_no"):
        # Extract number from format PI-XXXX
        try:
            num = int(latest["proforma_no"].replace("PI-", ""))
            next_num = num + 1
        except (ValueError, KeyError):
            next_num = 1
    else:
        next_num = 1
    
    return {"next_number": f"PI-{next_num:04d}"}


@router.get("/{invoice_id}")
async def get_proforma_invoice(invoice_id: str, current_user: dict = Depends(get_current_user)):
    """Get a single proforma invoice by ID"""
    db = get_db()
    invoice = await db.proforma_invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail="Proforma invoice not found")
    return invoice


@router.post("")
async def create_proforma_invoice(invoice: ProformaInvoiceCreate, current_user: dict = Depends(get_current_user)):
    """Create a new proforma invoice"""
    db = get_db()
    
    invoice_data = invoice.model_dump()
    invoice_data["id"] = str(uuid.uuid4())
    invoice_data["status"] = "active"
    invoice_data["created_at"] = datetime.now(timezone.utc).isoformat()
    invoice_data["created_by"] = current_user.get("email")
    
    # Calculate expiry date
    validity_days = invoice_data.get("validity_days", 30)
    invoice_data["expiry_date"] = (datetime.now(timezone.utc) + timedelta(days=validity_days)).isoformat()
    
    # Calculate totals if not provided
    line_items = invoice_data.get("line_items", [])
    if line_items:
        subtotal = sum(item.get("total", 0) or (item.get("quantity", 0) * item.get("price", 0)) for item in line_items)
        invoice_data["subtotal"] = subtotal
        invoice_data["vat"] = round(subtotal * 0.20, 2)
        invoice_data["gross_total"] = round(subtotal + invoice_data["vat"], 2)
    
    await db.proforma_invoices.insert_one(invoice_data)
    
    await log_audit(
        action="CREATE_PROFORMA_INVOICE",
        entity_type="proforma_invoice",
        user=current_user,
        entity_id=invoice_data.get("id", ""),
        entity_name=invoice_data.get('proforma_no', ''),
        details=f"Created proforma invoice {invoice_data.get('proforma_no')}"
    )
    
    # Return without _id
    invoice_data.pop("_id", None)
    return invoice_data


@router.put("/{invoice_id}")
async def update_proforma_invoice(
    invoice_id: str,
    invoice: ProformaInvoiceUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update a proforma invoice"""
    db = get_db()
    
    existing = await db.proforma_invoices.find_one({"id": invoice_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Proforma invoice not found")
    
    update_data = {k: v for k, v in invoice.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    update_data["updated_by"] = current_user.get("email")
    
    # Recalculate totals if line items updated
    if "line_items" in update_data and update_data["line_items"]:
        subtotal = sum(item.get("total", 0) or (item.get("quantity", 0) * item.get("price", 0)) for item in update_data["line_items"])
        update_data["subtotal"] = subtotal
        update_data["vat"] = round(subtotal * 0.20, 2)
        update_data["gross_total"] = round(subtotal + update_data["vat"], 2)
    
    await db.proforma_invoices.update_one({"id": invoice_id}, {"$set": update_data})
    
    await log_audit(
        action="UPDATE_PROFORMA_INVOICE",
        entity_type="proforma_invoice",
        user=current_user,
        entity_id=invoice_id,
        entity_name=existing.get('proforma_no', ''),
        details=f"Updated proforma invoice {existing.get('proforma_no')}"
    )
    
    updated = await db.proforma_invoices.find_one({"id": invoice_id}, {"_id": 0})
    return updated


@router.delete("/{invoice_id}")
async def delete_proforma_invoice(invoice_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a proforma invoice (soft delete)"""
    db = get_db()
    
    invoice = await db.proforma_invoices.find_one({"id": invoice_id})
    if not invoice:
        raise HTTPException(status_code=404, detail="Proforma invoice not found")
    
    await db.proforma_invoices.update_one(
        {"id": invoice_id},
        {"$set": {
            "status": "deleted",
            "deleted_at": datetime.now(timezone.utc).isoformat(),
            "deleted_by": current_user.get("email")
        }}
    )
    
    await log_audit(
        action="DELETE_PROFORMA_INVOICE",
        entity_type="proforma_invoice",
        user=current_user,
        entity_id=invoice_id,
        entity_name=invoice.get('proforma_no', ''),
        details=f"Deleted proforma invoice {invoice.get('proforma_no')}"
    )
    
    return {"message": "Proforma invoice deleted"}


@router.post("/{invoice_id}/restore")
async def restore_proforma_invoice(invoice_id: str, current_user: dict = Depends(get_current_user)):
    """Restore a deleted proforma invoice"""
    db = get_db()
    
    invoice = await db.proforma_invoices.find_one({"id": invoice_id})
    if not invoice:
        raise HTTPException(status_code=404, detail="Proforma invoice not found")
    
    await db.proforma_invoices.update_one(
        {"id": invoice_id},
        {"$set": {"status": "active"}, "$unset": {"deleted_at": "", "deleted_by": ""}}
    )
    
    await log_audit(
        action="RESTORE_PROFORMA_INVOICE",
        entity_type="proforma_invoice",
        user=current_user,
        entity_id=invoice_id,
        entity_name=invoice.get('proforma_no', ''),
        details=f"Restored proforma invoice {invoice.get('proforma_no')}"
    )
    
    return {"message": "Proforma invoice restored"}


@router.post("/{invoice_id}/convert")
async def convert_to_invoice(invoice_id: str, current_user: dict = Depends(get_current_user)):
    """Mark proforma invoice as converted to regular invoice"""
    db = get_db()
    
    invoice = await db.proforma_invoices.find_one({"id": invoice_id})
    if not invoice:
        raise HTTPException(status_code=404, detail="Proforma invoice not found")
    
    await db.proforma_invoices.update_one(
        {"id": invoice_id},
        {"$set": {
            "status": "converted",
            "converted_at": datetime.now(timezone.utc).isoformat(),
            "converted_by": current_user.get("email")
        }}
    )
    
    await log_audit(
        action="CONVERT_PROFORMA_INVOICE",
        entity_type="proforma_invoice",
        user=current_user,
        entity_id=invoice_id,
        entity_name=invoice.get('proforma_no', ''),
        details=f"Converted proforma invoice {invoice.get('proforma_no')} to invoice"
    )
    
    return {"message": "Proforma invoice marked as converted"}


# ============ PDF GENERATION ============

async def generate_proforma_invoice_pdf_bytes(invoice: dict) -> bytes:
    """Generate PDF bytes for a proforma invoice with bank details"""
    if not REPORTLAB_AVAILABLE:
        raise Exception("PDF generation not available")
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, 
                          rightMargin=15*mm, leftMargin=15*mm,
                          topMargin=15*mm, bottomMargin=15*mm)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Title Style
    title_style = ParagraphStyle('ProformaTitle', parent=styles['Title'], 
                                  fontSize=20, spaceAfter=5*mm, textColor=colors.HexColor('#1e3a5f'))
    subtitle_style = ParagraphStyle('ProformaSubtitle', parent=styles['Normal'], 
                                     fontSize=12, spaceAfter=15*mm, alignment=TA_CENTER,
                                     textColor=colors.grey)
    
    # Header
    elements.append(Paragraph("PROFORMA INVOICE", title_style))
    elements.append(Paragraph(f"Reference: {invoice.get('proforma_no', 'N/A')}", subtitle_style))
    
    # Company Info (Left) and Invoice Details (Right)
    company_info = invoice.get("company_info", {})
    company_name = company_info.get("name", "TILE STATION LTD")
    company_address = company_info.get("address", "")
    company_city = company_info.get("city", "")
    company_tel = company_info.get("telephone", "")
    company_email = company_info.get("email", "")
    company_vat = company_info.get("vatNo", "")
    
    left_style = ParagraphStyle('LeftInfo', fontSize=9, leading=12)
    right_style = ParagraphStyle('RightInfo', fontSize=9, leading=12, alignment=TA_RIGHT)
    
    left_info = f"""
    <b>{company_name}</b><br/>
    {company_address}<br/>
    {company_city}<br/>
    Tel: {company_tel}<br/>
    Email: {company_email}<br/>
    VAT No: {company_vat}
    """
    
    expiry_date = invoice.get("expiry_date", "")
    if expiry_date:
        try:
            expiry_formatted = datetime.fromisoformat(expiry_date.replace('Z', '+00:00')).strftime("%d/%m/%Y")
        except (ValueError, TypeError):
            expiry_formatted = expiry_date[:10] if len(expiry_date) >= 10 else "-"
    else:
        expiry_formatted = "-"
    
    right_info = f"""
    <b>Date:</b> {invoice.get('date', '-')}<br/>
    <b>Valid Until:</b> {expiry_formatted}<br/>
    <b>Sales Person:</b> {invoice.get('sales_person', '-')}
    """
    
    header_table = Table([
        [Paragraph(left_info, left_style), Paragraph(right_info, right_style)]
    ], colWidths=[100*mm, 80*mm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 8*mm))
    
    # Customer Details Box
    customer_header_style = ParagraphStyle('CustomerHeader', fontSize=10, fontName='Helvetica-Bold', 
                                           textColor=colors.white, spaceBefore=3, spaceAfter=3)
    customer_style = ParagraphStyle('CustomerDetail', fontSize=9, leading=12)
    
    customer_name = invoice.get("customer_name", "-")
    customer_phone = invoice.get("customer_phone", "-")
    customer_email = invoice.get("customer_email", "-")
    customer_address = invoice.get("customer_address", "-")
    
    customer_data = [
        [Paragraph("BILL TO", customer_header_style)],
        [Paragraph(f"<b>Name:</b> {customer_name}", customer_style)],
        [Paragraph(f"<b>Phone:</b> {customer_phone}", customer_style)],
        [Paragraph(f"<b>Email:</b> {customer_email}", customer_style)],
        [Paragraph(f"<b>Address:</b> {customer_address}", customer_style)],
    ]
    customer_table = Table(customer_data, colWidths=[180*mm])
    customer_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a5f')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#1e3a5f')),
    ]))
    elements.append(customer_table)
    elements.append(Spacer(1, 8*mm))
    
    # Line Items Table
    product_style = ParagraphStyle('ProductName', fontSize=9, leading=11)
    
    items_data = [["Product", "SKU", "Qty", "m²", "Unit Price", "Total"]]
    for item in invoice.get("line_items", []):
        product_name = item.get("product_name", "-")
        product_para = Paragraph(product_name, product_style)
        qty = item.get("quantity", 0)
        m2 = item.get("m2", 0)
        price = item.get("price", 0)
        total = item.get("total", qty * price)
        
        items_data.append([
            product_para,
            item.get("sku", "-") or "-",
            str(int(qty)) if qty == int(qty) else f"{qty:.2f}",
            f"{m2:.2f}" if m2 else "-",
            f"£{price:.2f}",
            f"£{total:.2f}"
        ])
    
    items_table = Table(items_data, colWidths=[75*mm, 25*mm, 18*mm, 18*mm, 22*mm, 22*mm])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a5f')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 5*mm))
    
    # Totals
    subtotal = invoice.get("subtotal", 0)
    vat = invoice.get("vat", 0)
    gross_total = invoice.get("gross_total", 0)
    total_savings = invoice.get("total_savings", 0)
    
    totals_data = [
        ["Subtotal:", f"£{subtotal:.2f}"],
    ]
    if total_savings > 0:
        totals_data.append(["Total Savings:", f"£{total_savings:.2f}"])
    totals_data.extend([
        ["VAT (20%):", f"£{vat:.2f}"],
        ["TOTAL DUE:", f"£{gross_total:.2f}"],
    ])
    
    totals_table = Table(totals_data, colWidths=[140*mm, 40*mm])
    totals_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -2), 'Helvetica'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f0f0f0')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(totals_table)
    elements.append(Spacer(1, 10*mm))
    
    # Bank Details Section
    bank_header_style = ParagraphStyle('BankHeader', fontSize=11, fontName='Helvetica-Bold',
                                        textColor=colors.HexColor('#1e3a5f'), spaceBefore=5, spaceAfter=5)
    
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#1e3a5f')))
    elements.append(Spacer(1, 5*mm))
    elements.append(Paragraph("PAYMENT DETAILS", bank_header_style))
    elements.append(Spacer(1, 3*mm))
    
    bank_data = [
        ["Account Name:", BANK_DETAILS["name"]],
        ["Account Type:", BANK_DETAILS["account_type"]],
        ["Account Number:", BANK_DETAILS["account_number"]],
        ["Sort Code:", BANK_DETAILS["sort_code"]],
    ]
    
    bank_table = Table(bank_data, colWidths=[40*mm, 60*mm])
    bank_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#1e3a5f')),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(bank_table)
    elements.append(Spacer(1, 5*mm))
    
    # Payment Reference Note
    ref_style = ParagraphStyle('RefNote', fontSize=9, textColor=colors.HexColor('#666666'))
    elements.append(Paragraph(f"<i>Please use your invoice reference <b>{invoice.get('proforma_no', '')}</b> as payment reference.</i>", ref_style))
    elements.append(Spacer(1, 8*mm))
    
    # Notes
    if invoice.get("notes"):
        notes_header_style = ParagraphStyle('NotesHeader', fontSize=10, fontName='Helvetica-Bold', spaceBefore=5)
        notes_style = ParagraphStyle('Notes', fontSize=9, leading=12)
        elements.append(Paragraph("NOTES:", notes_header_style))
        elements.append(Paragraph(invoice.get("notes"), notes_style))
        elements.append(Spacer(1, 5*mm))
    
    # Footer
    footer_style = ParagraphStyle('Footer', fontSize=8, alignment=TA_CENTER, textColor=colors.grey)
    elements.append(Spacer(1, 10*mm))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    elements.append(Paragraph("This is a proforma invoice and is not a demand for payment. A tax invoice will be issued upon receipt of payment.", footer_style))
    elements.append(Paragraph("Thank you for your business!", footer_style))
    
    doc.build(elements)
    return buffer.getvalue()


@router.get("/{invoice_id}/pdf")
async def generate_proforma_invoice_pdf(invoice_id: str, current_user: dict = Depends(get_current_user)):
    """Generate PDF for a proforma invoice"""
    if not REPORTLAB_AVAILABLE:
        raise HTTPException(status_code=500, detail="PDF generation not available")
    
    db = get_db()
    invoice = await db.proforma_invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail="Proforma invoice not found")
    
    pdf_bytes = await generate_proforma_invoice_pdf_bytes(invoice)
    filename = f"ProformaInvoice_{invoice.get('proforma_no', 'unknown')}.pdf"
    
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.post("/{invoice_id}/email")
async def email_proforma_invoice(
    invoice_id: str,
    email_to: str = Body(..., embed=True),
    message: str = Body("", embed=True),
    current_user: dict = Depends(get_current_user)
):
    """Email proforma invoice PDF to customer"""
    db = get_db()
    invoice = await db.proforma_invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail="Proforma invoice not found")
    
    # Import email service
    try:
        from services.email import RESEND_AVAILABLE, RESEND_API_KEY, get_showroom_email
        import resend
        import asyncio
    except ImportError:
        raise HTTPException(status_code=500, detail="Email service not available")
    
    if not RESEND_AVAILABLE or not RESEND_API_KEY:
        raise HTTPException(status_code=500, detail="Email service not configured")
    
    # Generate PDF
    try:
        pdf_bytes = await generate_proforma_invoice_pdf_bytes(invoice)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")
    
    # Get showroom email for sending
    showroom_name = invoice.get("showroom_name", "Tile Station")
    from_email = get_showroom_email(showroom_name)
    
    # Build email content
    proforma_no = invoice.get("proforma_no", "N/A")
    customer_name = invoice.get("customer_name", "Customer")
    gross_total = invoice.get("gross_total", 0)
    validity_days = invoice.get("validity_days", 30)
    
    # Build line items HTML
    line_items = invoice.get("line_items", [])
    items_html = ""
    for item in line_items:
        items_html += f"""
        <tr>
            <td style="padding: 8px; border-bottom: 1px solid #eee;">{item.get('product_name', '')}</td>
            <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: center;">{item.get('quantity', 0)}</td>
            <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">£{item.get('price', 0):.2f}</td>
        </tr>
        """
    
    # Custom message section
    custom_message_html = ""
    if message:
        custom_message_html = f"""
        <div style="background: #fff3cd; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #f0c14b;">
            <p style="margin: 0; color: #856404;"><strong>Message from Tile Station:</strong></p>
            <p style="margin: 10px 0 0 0; color: #856404;">{message}</p>
        </div>
        """
    
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #1e3a5f; color: white; padding: 20px; text-align: center;">
            <h1 style="margin: 0; color: #f0c14b;">TILE STATION</h1>
            <p style="margin: 5px 0 0 0; font-size: 14px;">Proforma Invoice</p>
        </div>
        
        <div style="padding: 30px; background: #f9f9f9;">
            <h2 style="color: #1e3a5f; margin-top: 0;">Proforma Invoice #{proforma_no}</h2>
            <p>Dear {customer_name},</p>
            
            <p>Please find attached your proforma invoice. This invoice is valid for <strong>{validity_days} days</strong>.</p>
            
            {custom_message_html}
            
            <div style="background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #1e3a5f;">
                <h3 style="margin-top: 0; color: #1e3a5f;">Order Summary</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr style="background: #f5f5f5;">
                            <th style="padding: 10px; text-align: left;">Product</th>
                            <th style="padding: 10px; text-align: center;">Qty</th>
                            <th style="padding: 10px; text-align: right;">Price</th>
                        </tr>
                    </thead>
                    <tbody>
                        {items_html}
                    </tbody>
                </table>
                
                <div style="margin-top: 15px; padding-top: 15px; border-top: 2px solid #1e3a5f;">
                    <table style="width: 100%;">
                        <tr>
                            <td style="padding: 5px 0;">Subtotal:</td>
                            <td style="text-align: right;">£{invoice.get('subtotal', 0):.2f}</td>
                        </tr>
                        <tr>
                            <td style="padding: 5px 0;">VAT (20%):</td>
                            <td style="text-align: right;">£{invoice.get('vat', 0):.2f}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px 0; font-weight: bold; font-size: 18px;"><strong>Total Due:</strong></td>
                            <td style="text-align: right; font-weight: bold; font-size: 18px; color: #1e3a5f;">£{gross_total:.2f}</td>
                        </tr>
                    </table>
                </div>
            </div>
            
            <div style="background: #e8f4fd; padding: 15px; border-radius: 8px; margin: 20px 0; border: 2px solid #1e3a5f;">
                <h3 style="margin: 0 0 10px 0; color: #1e3a5f;">Payment Details</h3>
                <table style="width: 100%;">
                    <tr>
                        <td style="padding: 4px 0; color: #1e3a5f;"><strong>Account Name:</strong></td>
                        <td style="padding: 4px 0;">{BANK_DETAILS["name"]}</td>
                    </tr>
                    <tr>
                        <td style="padding: 4px 0; color: #1e3a5f;"><strong>Account Number:</strong></td>
                        <td style="padding: 4px 0; font-family: monospace;">{BANK_DETAILS["account_number"]}</td>
                    </tr>
                    <tr>
                        <td style="padding: 4px 0; color: #1e3a5f;"><strong>Sort Code:</strong></td>
                        <td style="padding: 4px 0; font-family: monospace;">{BANK_DETAILS["sort_code"]}</td>
                    </tr>
                </table>
                <p style="margin: 10px 0 0 0; font-size: 12px; color: #666;">
                    Please use reference: <strong>{proforma_no}</strong> when making payment.
                </p>
            </div>
            
            <p style="color: #666; font-size: 14px;">
                This is a proforma invoice. Payment is required before goods will be dispatched. 
                A VAT invoice will be issued upon receipt of payment.
            </p>
            
            <p style="margin-top: 30px;">
                Best regards,<br>
                <strong>{showroom_name} - Tile Station</strong><br>
                Tel: 01474 878 989<br>
                Email: {from_email}
            </p>
        </div>
        
        <div style="background: #1e3a5f; color: #888; padding: 15px; text-align: center; font-size: 12px;">
            <p style="margin: 0; color: #ccc;">Amazing Tiles - Beautiful Bathrooms - Excellent Service</p>
        </div>
    </div>
    """
    
    # Send email with PDF attachment
    try:
        import base64
        pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
        
        resend.api_key = RESEND_API_KEY
        await asyncio.to_thread(resend.Emails.send, {
            "from": f"{showroom_name} - Tile Station <{from_email}>",
            "to": [email_to],
            "subject": f"Proforma Invoice #{proforma_no} - Tile Station",
            "html": html_content,
            "attachments": [
                {
                    "filename": f"ProformaInvoice_{proforma_no}.pdf",
                    "content": pdf_base64,
                }
            ]
        })
        
        logging.info(f"Proforma invoice email sent to {email_to} for invoice {proforma_no}")
        
    except Exception as e:
        logging.error(f"Failed to send proforma invoice email: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")
    
    await log_audit(
        action="EMAIL_PROFORMA_INVOICE",
        entity_type="proforma_invoice",
        user=current_user,
        entity_id=invoice_id,
        entity_name=invoice.get('proforma_no', ''),
        details=f"Emailed proforma invoice {invoice.get('proforma_no')} to {email_to}"
    )
    
    return {"message": f"Email sent successfully to {email_to}", "status": "sent"}


@router.get("/stats/summary")
async def get_proforma_stats(
    period: str = "today",
    showroom_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get proforma invoice statistics for a period"""
    db = get_db()
    
    now = datetime.now(timezone.utc)
    if period == "today":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        start_date = now - timedelta(days=now.weekday())
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "month":
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    query = {
        "created_at": {"$gte": start_date.isoformat()},
        "status": {"$in": ["active", "converted"]}
    }
    
    if showroom_id:
        query["showroom_id"] = showroom_id
    
    invoices = await db.proforma_invoices.find(query, {"_id": 0, "gross_total": 1, "subtotal": 1}).to_list(100000)
    
    total_value = sum(q.get("gross_total", q.get("subtotal", 0)) for q in invoices)
    count = len(invoices)
    
    return {
        "period": period,
        "start_date": start_date.isoformat(),
        "total_value": total_value,
        "count": count,
        "showroom_id": showroom_id
    }

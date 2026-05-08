"""
Trader-facing UK VAT-compliant invoice PDF generator.

A trader who logs into `/shop/trade/account` can download a per-order VAT
invoice — the kind their accountant expects: company VAT number, customer
trade reference, line items net + VAT @ 20%, totals, savings note.

Mounted at `GET /api/shop/orders/{order_id}/vat-invoice.pdf` from
`routes/shop.py`. The PDF generator itself lives in this module so we
don't bloat the already-large shop.py file.

UK VAT invoice requirements (HMRC):
  • Unique invoice number  → uses order_number
  • Tax point (date)       → order created_at
  • Supplier name + address → defaults below, overridable via env / settings
  • Supplier VAT registration number
  • Customer name + address → from order doc
  • Description + qty + unit price (ex-VAT) per line
  • Rate of VAT applied per line
  • Total ex-VAT per line
  • Subtotal ex-VAT, VAT amount, Gross total
"""
import io
import os
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
    REPORTLAB_AVAILABLE = True
except ImportError:  # pragma: no cover
    REPORTLAB_AVAILABLE = False
    logger.warning("reportlab not available — VAT invoice PDF disabled")


# ── Default supplier (Tile Station) — overridable via env vars ──────────
# These match the canonical company info used in the proforma builder so the
# admin tax invoice and customer-downloaded VAT invoice cannot drift.
DEFAULT_COMPANY = {
    "name": os.environ.get("COMPANY_NAME", "Tile Station"),
    "address_line_1": os.environ.get(
        "COMPANY_ADDRESS_1", "Unit 3 Trade City, Coldharbour Road"
    ),
    "address_line_2": os.environ.get(
        "COMPANY_ADDRESS_2", "Northfleet Gravesend DA11 8AB"
    ),
    "telephone": os.environ.get("COMPANY_TELEPHONE", "01234 567 890"),
    "email": os.environ.get("COMPANY_EMAIL", "info@tilestation.co.uk"),
    "company_no": os.environ.get("COMPANY_NUMBER", "00000000"),
    "vat_no": os.environ.get("COMPANY_VAT_NO", "GB 000 0000 00"),
    "website": os.environ.get("COMPANY_WEBSITE", "tilestation.co.uk"),
}


def _money(v) -> str:
    """Render £ with 2dp, handling None / strings safely."""
    try:
        return f"£{float(v or 0):.2f}"
    except (TypeError, ValueError):
        return "£0.00"


def _format_date(iso_str: Optional[str]) -> str:
    if not iso_str:
        return ""
    try:
        # MongoDB-stored ISO strings; we just want the date for the tax point.
        d = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return d.strftime("%d %B %Y")
    except (ValueError, AttributeError):
        return str(iso_str)[:10]


def _split_order_totals(order: dict) -> dict:
    """Derive net / VAT / gross figures from the stored order doc.

    Online orders store `subtotal` as ex-VAT and `total = subtotal + 20% VAT
    + delivery_fee`. We back-derive each component so the PDF tells the
    accountant the truth even when older orders are missing some fields.

    For in-store EPOS invoices that opted out of VAT (apply_vat=False) the
    caller stamps `_in_store_apply_vat=False` on the order dict; we honour
    that by zeroing the VAT line and treating subtotal == gross.
    """
    delivery = float(order.get("delivery_fee") or 0)
    apply_vat = order.get("_in_store_apply_vat", True)

    if "subtotal" in order and order.get("subtotal") is not None:
        net = float(order["subtotal"])
    elif order.get("total") is not None:
        gross_minus_delivery = float(order["total"]) - delivery
        if apply_vat:
            net = round(gross_minus_delivery / 1.20, 2)
        else:
            net = round(gross_minus_delivery, 2)
    else:
        net = 0.0

    if apply_vat:
        vat = round(net * 0.20, 2)
    else:
        vat = 0.0

    gross = round(net + vat + delivery, 2)
    stored_total = order.get("total")
    if stored_total is not None and abs(float(stored_total) - gross) > 0.01:
        gross = float(stored_total)
    return {"net": net, "vat": vat, "delivery": delivery, "gross": gross, "apply_vat": apply_vat}


def epos_invoice_to_order_and_customer(inv: dict) -> tuple[dict, dict]:
    """Adapt an EPOS `invoices` doc into the (order, customer) shape the PDF
    generator expects. Used by both the trader-facing download route and the
    auto-attach order-confirmation email path so neither side drifts.

    The customer block is derived from the invoice fields (name/email/address)
    so the helper works whether or not the invoice is linked to an online
    `shop_customers` document — guest sales still get a clean billing block.
    """
    apply_vat = bool(inv.get("apply_vat", True))
    net_subtotal = float(inv.get("subtotal") or 0)
    gross_total = float(inv.get("gross_total") or 0)
    if not apply_vat:
        net_for_pdf = gross_total
    else:
        net_for_pdf = net_subtotal if net_subtotal > 0 else round(gross_total / 1.20, 2)

    order = {
        "id": inv.get("id"),
        "order_number": inv.get("invoice_no"),
        "customer_id": inv.get("linked_shop_customer_id"),
        "customer_email": inv.get("customer_email"),
        "customer_name": inv.get("customer_name"),
        "delivery_address": inv.get("customer_address") or "",
        "items": [
            {
                "name": li.get("product_name") or li.get("description") or "Item",
                "variant": li.get("variant"),
                "price": float(li.get("due_price") or li.get("price") or 0),
                "quantity": float(li.get("quantity") or 0),
            }
            for li in (inv.get("line_items") or [])
        ],
        "subtotal": net_for_pdf,
        "delivery_fee": 0.0,
        "total": gross_total,
        "status": "delivered" if (inv.get("amount_outstanding") or 0) <= 0.01 else "processing",
        "created_at": inv.get("created_at") or inv.get("date"),
        "savings_meta": inv.get("savings_meta"),
        "_in_store_apply_vat": apply_vat,
        "_in_store_showroom": inv.get("showroom_name"),
        "_in_store_staff_name": inv.get("staff_name") or inv.get("sales_person"),
        "_in_store_invoice_date": inv.get("date"),
    }
    customer_stub = {
        "id": inv.get("linked_shop_customer_id"),
        "name": inv.get("customer_name") or "Customer",
        "email": inv.get("customer_email") or "",
        "phone": inv.get("customer_phone") or "",
        "business_name": inv.get("trade_business_name"),
        "trade_account_number": inv.get("trade_account_number"),
        "address": inv.get("customer_address") or "",
    }
    return order, customer_stub


def generate_vat_invoice_pdf_bytes(
    order: dict,
    customer: dict,
    supplier: Optional[dict] = None,
) -> bytes:
    """Generate a UK VAT invoice PDF for a single shop order.

    Args:
      order: shop_orders document.
      customer: shop_customers document of the trader (for billing block).
      supplier: optional override; falls back to DEFAULT_COMPANY.

    Returns: PDF bytes.
    """
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("PDF generation not available")

    sup = {**DEFAULT_COMPANY, **(supplier or {})}
    totals = _split_order_totals(order)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=f"VAT Invoice {order.get('order_number') or ''}",
        author=sup["name"],
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "VatInvoiceTitle",
        parent=styles["Title"],
        fontSize=22,
        spaceAfter=4,
        textColor=colors.HexColor("#171717"),
        alignment=TA_LEFT,
    )
    subtitle_style = ParagraphStyle(
        "VatSub",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#525252"),
        alignment=TA_LEFT,
    )
    label_style = ParagraphStyle(
        "Label",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#737373"),
        leading=11,
    )
    value_style = ParagraphStyle(
        "Value",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#171717"),
        leading=13,
    )
    footer_style = ParagraphStyle(
        "Footer",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#737373"),
        alignment=TA_CENTER,
    )

    elements = []

    # ── Header: "VAT INVOICE" + supplier details on the right ─────────────
    showroom_name = order.get("_in_store_showroom")
    title_label = (
        f"VAT INVOICE · {showroom_name}" if showroom_name else "VAT INVOICE"
    )
    subtitle_text = (
        "This is a VAT invoice — please retain for your records."
        if not showroom_name
        else f"Issued at {showroom_name} — please retain for your records."
    )
    header_left = [
        Paragraph(title_label, title_style),
        Paragraph(subtitle_text, subtitle_style),
    ]
    supplier_html = (
        f"<b>{sup['name']}</b><br/>"
        f"{sup['address_line_1']}<br/>"
        f"{sup['address_line_2']}<br/>"
        f"Tel: {sup['telephone']}<br/>"
        f"{sup['email']}<br/>"
        f"<font color='#737373'>VAT No: {sup['vat_no']}</font>"
    )
    header_table = Table(
        [[header_left, Paragraph(supplier_html, value_style)]],
        colWidths=[100 * mm, 80 * mm],
    )
    header_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ])
    )
    elements.append(header_table)
    elements.append(Spacer(1, 8 * mm))

    # ── Invoice meta + Bill-to block ──────────────────────────────────────
    invoice_no = order.get("order_number") or order.get("id", "")
    tax_point = _format_date(order.get("created_at"))
    customer_name = (
        customer.get("business_name")
        or customer.get("name")
        or order.get("customer_name")
        or ""
    )
    customer_email = customer.get("email") or order.get("customer_email") or ""
    delivery_addr = order.get("delivery_address") or ""
    if isinstance(delivery_addr, dict):
        delivery_addr = ", ".join(
            str(delivery_addr.get(k))
            for k in ("line_1", "line_2", "city", "postcode")
            if delivery_addr.get(k)
        )
    t_ref = (customer.get("trade_account_number") or "").strip()

    bill_to_html = f"<b>{customer_name}</b><br/>{customer_email}"
    if t_ref:
        bill_to_html += f"<br/><font color='#737373'>Trade Ref: {t_ref}</font>"
    if delivery_addr:
        bill_to_html += f"<br/>{delivery_addr}"

    invoice_meta_html = (
        f"<font color='#737373'>Invoice No</font><br/><b>{invoice_no}</b><br/><br/>"
        f"<font color='#737373'>Tax Point</font><br/>{tax_point}<br/><br/>"
        f"<font color='#737373'>Status</font><br/>{(order.get('status') or '—').title()}"
    )

    meta_table = Table(
        [[
            [Paragraph("BILL TO", label_style), Paragraph(bill_to_html, value_style)],
            Paragraph(invoice_meta_html, value_style),
        ]],
        colWidths=[110 * mm, 70 * mm],
    )
    meta_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fafaf9")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ])
    )
    elements.append(meta_table)
    elements.append(Spacer(1, 6 * mm))

    # ── Line items table ──────────────────────────────────────────────────
    vat_rate_label = "20%" if totals["apply_vat"] else "0%"
    line_data = [["Description", "Qty", "Unit (ex-VAT)", "VAT", "Total (ex-VAT)"]]
    items = order.get("items") or order.get("line_items") or []
    line_rows_added = 0
    for item in items:
        name = (
            item.get("name")
            or item.get("product_name")
            or item.get("description")
            or "Item"
        )
        variant = item.get("variant")
        if variant:
            name = f"{name} — {variant}"
        if len(name) > 60:
            name = name[:58] + "…"
        qty = float(item.get("quantity") or item.get("qty") or 0)
        unit = float(item.get("price") or item.get("unit_price") or 0)
        line_net = round(unit * qty, 2)
        line_data.append(
            [
                Paragraph(name, value_style),
                f"{qty:g}",
                _money(unit),
                vat_rate_label,
                _money(line_net),
            ]
        )
        line_rows_added += 1

    if line_rows_added == 0:
        # Defensive — show a single placeholder line so the table renders.
        line_data.append(
            [Paragraph("Order line items unavailable", value_style),
             "—", "—", "—", _money(totals["net"])]
        )

    items_table = Table(
        line_data,
        colWidths=[80 * mm, 18 * mm, 28 * mm, 18 * mm, 32 * mm],
    )
    items_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#171717")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafaf9")]),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#171717")),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ])
    )
    elements.append(items_table)
    elements.append(Spacer(1, 4 * mm))

    # ── Totals block ──────────────────────────────────────────────────────
    totals_rows = [
        ["Subtotal (ex-VAT)", _money(totals["net"])],
        [f"VAT @ {vat_rate_label}", _money(totals["vat"])],
    ]
    if totals["delivery"] > 0:
        totals_rows.append(["Delivery", _money(totals["delivery"])])
    totals_rows.append(["TOTAL (inc-VAT)", _money(totals["gross"])])

    totals_table = Table(totals_rows, colWidths=[100 * mm, 32 * mm], hAlign="RIGHT")
    totals_table.setStyle(
        TableStyle([
            ("FONTNAME", (0, 0), (-1, -2), "Helvetica"),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("LINEABOVE", (0, -1), (-1, -1), 1, colors.HexColor("#171717")),
            ("TOPPADDING", (0, -1), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])
    )
    elements.append(totals_table)
    elements.append(Spacer(1, 6 * mm))

    # ── Trade savings note (optional) ─────────────────────────────────────
    sm = order.get("savings_meta") or {}
    if sm and float(sm.get("total_saved") or 0) >= 0.01:
        savings_html = (
            f"<font color='#047857'><b>Trade savings on this order:</b></font> "
            f"You saved <b>£{float(sm.get('total_saved') or 0):.2f}</b> vs retail "
            f"({sm.get('percent_off_retail') or 0}% off across "
            f"{sm.get('lines_with_savings') or 0} line"
            f"{'' if (sm.get('lines_with_savings') or 0) == 1 else 's'})."
        )
        elements.append(Paragraph(savings_html, value_style))
        elements.append(Spacer(1, 4 * mm))

    # ── Footer ────────────────────────────────────────────────────────────
    elements.append(Spacer(1, 6 * mm))
    elements.append(Paragraph(
        f"Thank you for your business. {sup['name']} · "
        f"Co. No: {sup['company_no']} · VAT: {sup['vat_no']}",
        footer_style,
    ))
    # Issued-by line for in-store EPOS invoices — instant traceability when
    # a dispute lands. Only renders when staff name + showroom are both
    # present (i.e. it really came from the till, not the website).
    staff_name = order.get("_in_store_staff_name")
    issued_showroom = order.get("_in_store_showroom")
    if staff_name and issued_showroom:
        issue_date = (
            order.get("_in_store_invoice_date")
            or _format_date(order.get("created_at"))
        )
        elements.append(Paragraph(
            f"Issued by <b>{staff_name}</b> at {issued_showroom}"
            + (f" on {issue_date}" if issue_date else ""),
            footer_style,
        ))
    elements.append(Paragraph(
        "Goods remain the property of the supplier until payment is received in full.",
        footer_style,
    ))

    doc.build(elements)
    return buffer.getvalue()

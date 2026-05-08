"""
Comprehensive Staff Training Booklet — covers EVERY operational feature
(both EPOS/admin and customer-facing storefront) the staff need to
recognise and use in daily work. Targets ~60-80 pages with screenshots.

Output: /app/checklists/Staff_Training_Booklet.pdf
"""
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Image,
    PageBreak, Table, TableStyle, KeepTogether,
)
from reportlab.platypus.doctemplate import NextPageTemplate
from reportlab.lib.enums import TA_LEFT, TA_CENTER

OUT_PDF = Path("/app/checklists/Staff_Training_Booklet.pdf")
SCREENS = Path("/app/checklists/training_screens_compressed")
SCREEN_EXT = ".jpg"


# ----------------------------------------------------------------------
# DB-backed editable notes — super_admin can edit these via the admin
# Training Booklet page; the rest of this script (titles, screenshots,
# step lists) stays hardcoded.
# ----------------------------------------------------------------------
def _load_editable_notes():
    """Returns {key: content_html} from MongoDB, falling back to seeded defaults
    if the DB is unreachable. Never throws — booklet must always rebuild."""
    fallback = {
        "welcome": (
            "This is your <b>complete operations manual</b>. Every feature you will use during a normal "
            "shift is documented here with real screenshots and step-by-step instructions. "
            "Configuration / settings pages (managers only) are <b>NOT</b> covered."
        ),
        "refund_golden_rule": (
            "<b>A refund must always be linked to an invoice.</b> This is the golden rule. "
            "Never process a 'standalone' refund — it breaks the audit trail and the manager will not "
            "be able to reconcile the till at end of day."
        ),
        "refund_no_invoice_warn": (
            "If a customer wants money back but you cannot find their invoice, do NOT issue cash. "
            "Take their details, raise it with a manager, and tell the customer you'll call back "
            "within 24 hours. Manager approval is required for any refund without an invoice."
        ),
        "trade_pricing_tip": (
            "Don't manually type prices unless the manager has approved a discount. The till already "
            "knows trade prices for trade customers — they appear automatically once the trade customer "
            "is selected."
        ),
        "cash_variance_warn": (
            "Never pocket the variance — even small amounts. Always declare and explain. "
            "The system records every count, and managers cross-check against till logs daily."
        ),
        "delivery_promise_warn": (
            "Never promise a delivery time you can't see in the system. Drivers don't update times "
            "manually — they're set by the warehouse plan."
        ),
        "abandoned_baskets_tip": (
            "Best lead source you have. Always call the high-value baskets (£500+) within 24 hours — "
            "conversion rate is ~30%."
        ),
        "inbox_response_time": (
            "Always reply within 24 hours. Older than that = customers escalate to phone calls. "
            "The manager sees the unread queue daily."
        ),
        "golden_rules": (
            "1. Every refund must be linked to its invoice. <b>No exceptions.</b>\n"
            "2. Always log out at end of shift.\n"
            "3. Never share your password — even with a colleague.\n"
            "4. If you don't know, call a manager. Don't guess.\n"
            "5. Be polite even when wrong has been done — every word is recorded.\n"
            "6. Always check stock + batch before promising a customer extra tiles for a job in progress.\n"
            "7. Card refunds take 3–5 working days. Tell every customer this so they don't worry.\n"
            "8. Trade prices apply automatically once the trade customer is selected — never type the discount manually.\n"
            "9. If the system is slow or seems wrong, screenshot the page and message the manager. Don't keep clicking — you may double-charge.\n"
            "10. Sample orders (£1) are not for staff perks. They're customer service. Don't take samples for personal use."
        ),
    }
    try:
        import os
        from pymongo import MongoClient
        url = os.environ.get("MONGO_URL")
        dbn = os.environ.get("DB_NAME")
        if not url or not dbn:
            return fallback
        c = MongoClient(url, serverSelectionTimeoutMS=2000)
        db = c[dbn]
        out = dict(fallback)
        for row in db.training_booklet_content.find({}):
            key = row.get("_id")
            content = row.get("content")
            if key and content:
                out[key] = content
        c.close()
        return out
    except Exception:
        return fallback


NOTES = _load_editable_notes()

# Brand colours
DARK = colors.HexColor("#1C1917")
YELLOW = colors.HexColor("#F7EA1C")
INK = colors.HexColor("#0F172A")
GREY = colors.HexColor("#64748B")
GREEN = colors.HexColor("#059669")
ROSE = colors.HexColor("#9F1239")
AMBER = colors.HexColor("#D97706")
LIGHT = colors.HexColor("#F1F5F9")
BORDER = colors.HexColor("#E2E8F0")
NAVY = colors.HexColor("#1E40AF")

styles = getSampleStyleSheet()
H0 = ParagraphStyle("H0", parent=styles["Heading1"], fontName="Helvetica-Bold",
                    fontSize=32, leading=38, textColor=DARK, alignment=TA_LEFT,
                    spaceAfter=10)
H1 = ParagraphStyle("H1", parent=styles["Heading1"], fontName="Helvetica-Bold",
                    fontSize=22, leading=28, textColor=DARK, alignment=TA_LEFT,
                    spaceAfter=8, spaceBefore=4)
H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontName="Helvetica-Bold",
                    fontSize=16, leading=20, textColor=DARK,
                    spaceBefore=14, spaceAfter=6)
H3 = ParagraphStyle("H3", parent=styles["Heading3"], fontName="Helvetica-Bold",
                    fontSize=12, leading=16, textColor=DARK,
                    spaceBefore=10, spaceAfter=4)
PART = ParagraphStyle("Part", parent=H1, fontSize=11, leading=14,
                      textColor=AMBER, spaceAfter=2,
                      fontName="Helvetica-Bold")
BODY = ParagraphStyle("Body", parent=styles["BodyText"], fontName="Helvetica",
                      fontSize=10.5, leading=15, textColor=INK, alignment=TA_LEFT,
                      spaceAfter=5)
STEP = ParagraphStyle("Step", parent=BODY, fontSize=10.5, leading=16,
                      leftIndent=18, spaceAfter=5)
TIP = ParagraphStyle("Tip", parent=BODY, fontSize=9.5, leading=13,
                     textColor=DARK, leftIndent=8, borderPadding=7,
                     backColor=colors.HexColor("#FEF3C7"),
                     borderColor=AMBER, borderWidth=0.5,
                     spaceBefore=4, spaceAfter=8)
WARN = ParagraphStyle("Warn", parent=TIP,
                      backColor=colors.HexColor("#FEE2E2"),
                      borderColor=ROSE)
DO = ParagraphStyle("Do", parent=TIP,
                    backColor=colors.HexColor("#D1FAE5"),
                    borderColor=GREEN)
CAPTION = ParagraphStyle("Cap", parent=BODY, fontSize=8.5, leading=11,
                         textColor=GREY, alignment=TA_CENTER, spaceBefore=3,
                         spaceAfter=10, fontName="Helvetica-Oblique")


def cover_canvas(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(DARK)
    canvas.rect(0, 0, A4[0], A4[1], stroke=0, fill=1)
    canvas.setFillColor(YELLOW)
    canvas.rect(0, 0, A4[0], 60*mm, stroke=0, fill=1)
    canvas.restoreState()


def header_footer(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(DARK)
    canvas.rect(0, A4[1] - 12*mm, A4[0], 12*mm, stroke=0, fill=1)
    canvas.setFillColor(YELLOW)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(15*mm, A4[1] - 8*mm, "TILE STATION  ·  STAFF TRAINING BOOKLET")
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(A4[0] - 15*mm, A4[1] - 8*mm, "Comprehensive Operations Manual")
    canvas.setFillColor(GREY)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(15*mm, 8*mm, "Internal — not for public distribution")
    canvas.drawRightString(A4[0] - 15*mm, 8*mm, f"Page {doc.page}")
    canvas.restoreState()


def img(slug, width_mm=160, caption=None):
    p = SCREENS / f"{slug}{SCREEN_EXT}"
    if not p.exists():
        return Paragraph(f"<i>(image missing: {slug})</i>", BODY)
    from PIL import Image as PILImage
    with PILImage.open(p) as pim:
        ow, oh = pim.size
    target_w = width_mm * mm
    target_h = target_w * oh / ow
    f = [Image(str(p), width=target_w, height=target_h, hAlign="CENTER")]
    if caption:
        f.append(Paragraph(caption, CAPTION))
    return KeepTogether(f)


def steps(items):
    out = []
    for i, txt in enumerate(items, 1):
        out.append(Paragraph(f"<b>{i}.</b>&nbsp;&nbsp;{txt}", STEP))
    return out


def tip(text, kind="tip"):
    label = {"tip": "💡 TIP", "warn": "⚠ WATCH OUT", "do": "✓ DO THIS"}[kind]
    style = {"tip": TIP, "warn": WARN, "do": DO}[kind]
    return Paragraph(f"<b>{label}:</b>&nbsp; {text}", style)


def feature_table(rows, col_widths=(50*mm, 122*mm)):
    """Two-column table — bold first column, wrapped text in second."""
    wrapped = []
    for row in rows:
        wrapped.append([
            Paragraph(f"<b>{row[0]}</b>", BODY),
            Paragraph(row[1], BODY),
        ])
    t = Table(wrapped, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 7),
        ("RIGHTPADDING", (0,0), (-1,-1), 7),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LINEBELOW", (0,0), (-1,-1), 0.3, BORDER),
        ("BACKGROUND", (0,0), (0,-1), LIGHT),
    ]))
    return t


def section_break(part_label, title):
    """Dark page-break divider used between major sections."""
    return [
        PageBreak(),
        Paragraph(part_label, PART),
        Paragraph(title, H0),
        Spacer(1, 4*mm),
    ]


# ============================================================================
# CONTENT BUILDER
# ============================================================================

story = []

# ── COVER ──
story.append(Spacer(1, 60*mm))
story.append(Paragraph('<font color="#F7EA1C">STAFF TRAINING<br/>BOOKLET</font>',
                       ParagraphStyle("CT", parent=H0, fontSize=44, leading=54)))
story.append(Spacer(1, 6*mm))
story.append(Paragraph('<font color="#FFFFFF">Tile Station — Complete Operations Manual</font>',
                       ParagraphStyle("CSub", parent=BODY, fontSize=18, leading=24, textColor=colors.white)))
story.append(Spacer(1, 24*mm))
story.append(Paragraph('<font color="#1C1917"><b>Every feature you will use day-to-day</b></font>',
                       ParagraphStyle("ct1", parent=BODY, fontSize=14, textColor=DARK)))
story.append(Paragraph('<font color="#1C1917">EPOS · Invoices · Refunds · Stock · Customers · Marketing · Reports · Website</font>',
                       ParagraphStyle("ct2", parent=BODY, fontSize=11, textColor=DARK, leading=15)))
story.append(Spacer(1, 18*mm))
story.append(Paragraph(f'<font color="#1C1917"><b>Version:</b> {datetime.utcnow().strftime("%d %b %Y")}  ·  <b>Audience:</b> All counter, showroom &amp; warehouse staff</font>',
                       ParagraphStyle("cv", parent=BODY, fontSize=10, textColor=DARK)))

# ── INTRODUCTION ──
story += [NextPageTemplate("default"), PageBreak()]
story.append(Paragraph("Welcome to Tile Station", H0))
story.append(Paragraph(NOTES["welcome"], BODY))
story.append(Spacer(1, 4*mm))
story.append(Paragraph("How this booklet is organised", H3))
story.append(Paragraph(
    "The system is divided into <b>9 areas</b>, mirroring the sidebar of the admin app. "
    "Each area has its own Hub page (a launchpad) and a number of feature pages underneath. "
    "Read the area you need, or read it cover-to-cover during your first week.", BODY))
story.append(Spacer(1, 4*mm))
story.append(Paragraph("Icon legend", H3))
story.append(Table([
    [Paragraph('<font color="#D97706"><b>💡 TIP</b></font>', BODY),
     Paragraph("Helpful shortcut or detail to make your life easier.", BODY)],
    [Paragraph('<font color="#9F1239"><b>⚠ WATCH OUT</b></font>', BODY),
     Paragraph("Common mistake — please read carefully.", BODY)],
    [Paragraph('<font color="#059669"><b>✓ DO THIS</b></font>', BODY),
     Paragraph("The correct action when in doubt.", BODY)],
], colWidths=[42*mm, 130*mm], style=[
    ("VALIGN", (0,0), (-1,-1), "TOP"),
    ("LEFTPADDING", (0,0), (-1,-1), 8),
    ("RIGHTPADDING", (0,0), (-1,-1), 8),
    ("TOPPADDING", (0,0), (-1,-1), 7),
    ("BOTTOMPADDING", (0,0), (-1,-1), 7),
    ("LINEBELOW", (0,0), (-1,-1), 0.3, BORDER),
]))

# ── TABLE OF CONTENTS ──
story.append(Spacer(1, 8*mm))
story.append(Paragraph("Contents", H2))
toc = [
    ("Part 1",  "Logging in & getting around"),
    ("Part 2",  "Sales & EPOS"),
    ("Part 3",  "Quotations, Invoices & Refunds"),
    ("Part 4",  "Orders & Deliveries"),
    ("Part 5",  "Products & Suppliers"),
    ("Part 6",  "Stock Management"),
    ("Part 7",  "Customers"),
    ("Part 8",  "Communication"),
    ("Part 9",  "Reports & Analytics"),
    ("Part 10", "The customer website (storefront)"),
    ("Part 11", "System Maintenance & Health"),
    ("Part 12", "Glossary & Quick Reference"),
]
story.append(Table(toc, colWidths=[22*mm, 150*mm], style=[
    ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
    ("TEXTCOLOR", (0,0), (0,-1), AMBER),
    ("FONTSIZE", (0,0), (-1,-1), 11),
    ("LEADING", (0,0), (-1,-1), 18),
    ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ("LEFTPADDING", (0,0), (-1,-1), 8),
    ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ("TOPPADDING", (0,0), (-1,-1), 4),
    ("LINEBELOW", (0,0), (-1,-1), 0.3, BORDER),
]))


# ============================================================================
# PART 1 — LOGGING IN
# ============================================================================
story += section_break("PART 1", "Logging in & getting around")

story.append(Paragraph("1.1 · How to log in", H2))
story += steps([
    "Open your browser. The system works best on Chrome, Edge or Safari.",
    "Go to <b>tilestation.co.uk/admin/login</b>.",
    "Enter the email address your manager set up for you.",
    "Enter your password. <i>Never share it.</i>",
    "Click <b>Sign in</b>. You'll land on the Dashboard.",
])
story.append(tip("Forgot your password? Click <b>Forgot password</b> on the login screen — a reset email arrives within a minute.", "tip"))
story.append(tip("Always sign <b>OUT</b> at the end of your shift so the next person's sales are tracked under their own login.", "warn"))

story.append(PageBreak())
story.append(Paragraph("1.2 · The Dashboard", H2))
story.append(img("30_admin_dashboard", 165, "The Dashboard — your at-a-glance overview when you sign in."))
story.append(Paragraph("What's on the Dashboard:", H3))
story.append(feature_table([
    ("Today's sales",      "How much has been rung up so far today (cash + card)."),
    ("Live activity",      "Recent transactions, refunds, online orders."),
    ("Low-stock alerts",   "Products running out — pass these to the manager."),
    ("Quick links",        "Shortcuts to EPOS, Cash Counter, Invoice search."),
    ("Tasks for me",       "Anything assigned to you today (see Part 8)."),
]))

story.append(PageBreak())
story.append(Paragraph("1.3 · The Sidebar (left menu)", H2))
story.append(Paragraph(
    "The sidebar groups every page into <b>9 areas</b>. Click an area heading to expand it. "
    "Each area also has a <b>Hub</b> page (the colourful tile launchpad) reachable from the area heading itself. "
    "If you can't see an area, you don't have permission for it — that's normal.", BODY))
story.append(Paragraph("The 9 areas:", H3))
story.append(feature_table([
    ("Sales & EPOS",        "Till, cash drawer, store dashboard, invoices, quotations, refunds, orders."),
    ("Products & Suppliers", "Product catalogue, supplier health, sync hub, supplier contact details."),
    ("Stock Management",    "Stock levels, transfers, deliveries in, batch tracking, reorder suggestions."),
    ("Customers",           "Trade accounts, retail customers, custom pricing, customer invitations."),
    ("Communication",       "Staff chat, tasks, inbox, email tools, marketing, abandoned baskets, promo codes."),
    ("Reports",             "Sales analytics, performance reports."),
    ("Admin Settings",      "(Manager / super-admin only) — store config, users, PIN management."),
    ("Website",             "(Manager / super-admin only) — pages, branding, navigation, content."),
    ("Maintenance",         "System health, daily checks, launch checklists (read-only for staff)."),
]))


# ============================================================================
# PART 2 — SALES & EPOS
# ============================================================================
story += section_break("PART 2", "Sales & EPOS")

story.append(Paragraph("2.1 · The Sales Hub", H2))
story.append(img("31_sales_hub", 165, "Sales Hub — your launchpad for everything counter-related."))
story.append(Paragraph(
    "Click any tile to start a task. Bookmark this page so you never lose your way.", BODY))
story.append(feature_table([
    ("EPOS",            "Open the till to ring up a sale."),
    ("Cash Counter",    "Open / close the cash drawer at start &amp; end of shift."),
    ("Store Dashboard", "Today's sales total at a glance, broken down by staff."),
    ("Invoices",        "View, print, email or refund any past invoice."),
    ("Quotations",      "Create or look up customer price quotes."),
    ("Refunds",         "Process a refund — always linked to an invoice."),
    ("Online Orders",   "Orders that came in from the website."),
    ("Tile Calculator", "Help a customer work out how many m² they need."),
]))

story.append(PageBreak())
story.append(Paragraph("2.2 · The EPOS till", H2))
story.append(img("32_epos_till", 165, "The EPOS till. Search products on the left, basket on the right."))
story.append(Paragraph("How to ring up a sale", H3))
story += steps([
    "Click <b>EPOS</b> on the Sales Hub.",
    "Search for the product by <b>name</b>, <b>SKU</b> or <b>scan the barcode</b>. Click it to add to the basket.",
    "Adjust the <b>quantity</b> using + / − or by typing the number directly.",
    "Repeat for each product the customer wants.",
    "Click <b>Customer</b> at the top — search by name or phone. If new, click <b>Add new customer</b>.",
    "Apply a <b>discount</b> (manager approval required for anything over 10 %).",
    "Click <b>Pay</b>. Choose payment method: card, cash, or split (e.g. £100 cash + £200 card).",
    "After payment is approved, an <b>invoice is automatically created</b>. Print or email to customer.",
    "The basket clears — you're ready for the next sale.",
])
story.append(tip("Always attach a customer to the sale, even for cash transactions. This lets you find their invoice later if they need a receipt or refund.", "tip"))
story.append(tip(NOTES["trade_pricing_tip"], "warn"))
story.append(tip("If a customer wants to <b>hold</b> a basket and pay later, click <b>Save Quote</b> instead of Pay. It becomes a quotation (Part 3.1).", "do"))

story.append(PageBreak())
story.append(Paragraph("2.3 · Cash Counter — opening &amp; closing the drawer", H2))
story.append(img("33_cash_counter", 165, "Cash Counter. Match the physical cash to what the system thinks."))
story.append(Paragraph("At the start of your shift", H3))
story += steps([
    "Open <b>Sales Hub → Cash Counter</b>.",
    "Click <b>Open Drawer</b>.",
    "Count the float (the cash already in the drawer) by denomination: £50, £20, £10, £5, £2, £1, 50p, 20p, 10p, 5p, 2p, 1p.",
    "Type each count into its box. The system shows the total automatically.",
    "Click <b>Confirm Open</b>. The shift is now active under your login.",
])
story.append(Paragraph("At the end of your shift", H3))
story += steps([
    "Click <b>Close Drawer</b>.",
    "Count physical cash again. Type each count.",
    "The system shows <b>Expected vs Actual</b>. If they match — perfect.",
    "If short / over by more than £2, write a note in the <b>Variance reason</b> box (e.g. 'gave £20 change instead of £10').",
    "Click <b>Confirm Close</b>. A summary prints — sign it and pass to the manager.",
])
story.append(tip(NOTES["cash_variance_warn"], "warn"))

story.append(PageBreak())
story.append(Paragraph("2.4 · Store Dashboard", H2))
story.append(img("34_store_dashboard", 165, "Store Dashboard — the day's performance, staff by staff."))
story.append(Paragraph(
    "The Store Dashboard shows <b>your shop's sales today</b>. Useful at the end of shift to "
    "see how the day went. Don't worry if your numbers vary — slow days happen.", BODY))
story.append(feature_table([
    ("Sales today",        "Total revenue across all tills (cash + card + online)."),
    ("Refunds today",      "Total refunded today — should be a small fraction of sales."),
    ("By staff member",    "Each staff member's contribution today."),
    ("Avg basket size",    "Useful: if it drops, customers are buying less per visit."),
    ("Compared to yesterday", "Quick green/red indicator showing whether the day is up or down."),
]))


# ============================================================================
# PART 3 — QUOTATIONS, INVOICES & REFUNDS
# ============================================================================
story += section_break("PART 3", "Quotations, Invoices & Refunds")

story.append(Paragraph("3.1 · Quotations", H2))
story.append(img("36_quotations", 165, "Quotations list — every saved quote, with status and expiry."))
story.append(Paragraph(
    "A <b>quotation</b> is a written price the customer can take away. It does NOT take "
    "payment, does NOT reserve stock, and expires after 30 days.", BODY))

story.append(Paragraph("To create a new quote", H3))
story += steps([
    "Sales Hub → <b>Quotations</b>.",
    "Click <b>New Quotation</b> (top-right).",
    "Add the customer (search or create new).",
    "Add products and quantities — same as the EPOS basket.",
    "Optional: add notes (e.g. 'customer wants delivery week of 12 May').",
    "Click <b>Save &amp; Send</b>. The quote is emailed automatically.",
])

story.append(Paragraph("To convert a quote to a sale", H3))
story += steps([
    "Open the quote from the list.",
    "Click <b>Convert to Invoice</b>.",
    "The basket pre-fills on the EPOS till. Take payment as normal.",
])
story.append(tip("Quotations expire after 30 days. If a customer brings an old quote, check the date — prices may have changed. Always re-quote if expired.", "tip"))
story.append(tip("Some quotes have a <b>deposit required</b> flag. This means the customer paid 10–50 % up front. The remainder is due before the order leaves the warehouse.", "do"))

story.append(PageBreak())
story.append(Paragraph("3.2 · Invoices", H2))
story.append(img("35_invoices", 165, "Invoice list — every paid sale ends up here."))
story.append(Paragraph(
    "An <b>invoice</b> is the receipt of a paid sale. The till creates one automatically with every "
    "EPOS payment. Your job is to find, print, email or refund them.", BODY))

story.append(Paragraph("Finding an invoice", H3))
story += steps([
    "Sales Hub → <b>Invoices</b>.",
    "Search by <b>invoice number</b>, <b>customer name</b>, <b>phone</b>, or use the <b>date range</b> picker.",
    "Click the row to open it.",
])

story.append(Paragraph("What you can do with an open invoice", H3))
story.append(feature_table([
    ("Print",       "Sends to the receipt printer (small) or to A4 (full page)."),
    ("Email",       "Re-sends the PDF to the customer's email on file."),
    ("Download",    "Saves the PDF to your computer."),
    ("Refund",      "Starts a refund linked to this invoice (see 3.3)."),
    ("Add note",    "Internal note (e.g. 'customer reported damage on delivery')."),
    ("Resend SMS",  "Texts the order link again, in case the original SMS was missed."),
]))

story.append(PageBreak())
story.append(Paragraph("3.3 · Refunds — the most important page", H2))
story.append(img("37_refunds", 165, "Refunds list — every refund here is linked to its source invoice."))
story.append(Paragraph(NOTES["refund_golden_rule"], BODY))
story.append(tip(NOTES["refund_no_invoice_warn"], "warn"))

story.append(Paragraph("How to process a linked refund", H3))
story += steps([
    "Find the customer's <b>invoice</b> first (3.2). Open it.",
    "On the open invoice, click the <b>Refund</b> button.",
    "A refund form appears. The invoice line items are listed.",
    "<b>Tick the items</b> the customer is returning.",
    "Adjust the quantity if they're returning <b>part</b> of a line (e.g. 5 of 12 tiles).",
    "Choose the <b>refund method</b>:<br/>"
    "&nbsp;&nbsp;<b>Card</b> — money goes back to the original card automatically (3-5 days).<br/>"
    "&nbsp;&nbsp;<b>Cash</b> — open the cash drawer and hand the money over.<br/>"
    "&nbsp;&nbsp;<b>Credit note</b> — issues a voucher they can use later (no money out).",
    "Add a <b>reason</b> from the dropdown (damaged, wrong size, customer changed mind, etc.).",
    "Click <b>Confirm Refund</b>. A refund receipt prints automatically.",
    "Hand the receipt to the customer. The original invoice is marked '<b>Partially refunded</b>' or '<b>Fully refunded</b>'.",
])
story.append(tip("Card refunds take 3-5 working days to appear in the customer's bank. Tell them this so they don't call back panicking on day 2.", "tip"))

story.append(PageBreak())
story.append(Paragraph("3.4 · Refund decision tree", H2))
story.append(Paragraph("Use this if you're unsure what to do:", BODY))
story.append(Spacer(1, 3*mm))
story.append(Table([
    [Paragraph("<b>Customer says…</b>", BODY), Paragraph("<b>What you do</b>", BODY)],
    [Paragraph("“I changed my mind, I want a refund.”", BODY),
     Paragraph("Find invoice → Refund button → tick items → original payment method. <b>Within 14 days only.</b>", BODY)],
    [Paragraph("“Some tiles arrived broken.”", BODY),
     Paragraph("Find invoice → Refund only the broken qty → reason '<b>damaged in transit</b>' → photo evidence on file.", BODY)],
    [Paragraph("“The colour is wrong.”", BODY),
     Paragraph("Find invoice → Refund. Customer's choice = normal refund; website error = flag to manager.", BODY)],
    [Paragraph("“I don't have a receipt.”", BODY),
     Paragraph("Search by name or phone → find the invoice → continue. <b>Never</b> issue a no-invoice refund.", BODY)],
    [Paragraph("“It's been 3 months since I bought it.”", BODY),
     Paragraph("Outside our 30-day return window — manager approval required. Don't promise the refund.", BODY)],
    [Paragraph("“I want store credit, not cash.”", BODY),
     Paragraph("Refund method = <b>credit note</b>. They get a voucher code, not money.", BODY)],
    [Paragraph("“The fitter ordered too many — can I return the unopened boxes?”", BODY),
     Paragraph("Yes, within 30 days. Find invoice → refund full boxes only (opened boxes can't be refunded).", BODY)],
    [Paragraph("“I'm a trade customer — can I return without a restocking fee?”", BODY),
     Paragraph("Trade customers — manager approval. Some trade contracts include free returns; check their account first.", BODY)],
], colWidths=[60*mm, 112*mm], style=[
    ("BACKGROUND", (0,0), (-1,0), DARK),
    ("TEXTCOLOR", (0,0), (-1,0), YELLOW),
    ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
    ("VALIGN", (0,0), (-1,-1), "TOP"),
    ("LEFTPADDING", (0,0), (-1,-1), 6),
    ("RIGHTPADDING", (0,0), (-1,-1), 6),
    ("TOPPADDING", (0,0), (-1,-1), 7),
    ("BOTTOMPADDING", (0,0), (-1,-1), 7),
    ("LINEBELOW", (0,0), (-1,-1), 0.3, BORDER),
    ("LINEBEFORE", (0,0), (-1,-1), 0.3, BORDER),
    ("LINEAFTER", (0,0), (-1,-1), 0.3, BORDER),
]))


# ============================================================================
# PART 4 — ORDERS & DELIVERIES
# ============================================================================
story += section_break("PART 4", "Orders & Deliveries")

story.append(Paragraph("4.1 · Orders", H2))
story.append(img("38_orders", 165, "Orders list — combines counter sales and online orders."))
story.append(Paragraph(
    "An <b>order</b> is anything that needs to leave the building — whether the customer paid in-store "
    "or online. The Orders page shows everything in one place, with status flags.", BODY))
story.append(feature_table([
    ("New",          "Just placed — not yet picked."),
    ("Picked",       "Warehouse has it ready."),
    ("Out for delivery", "Driver collected."),
    ("Delivered",    "Customer signed."),
    ("Failed",       "No-one home / refused. Will be retried."),
    ("Cancelled",    "Customer cancelled before pick."),
]))

story.append(PageBreak())
story.append(Paragraph("4.2 · Online Orders", H2))
story.append(img("39_online_orders", 165, "Online Orders — orders placed via the customer website."))
story.append(Paragraph(
    "Every order placed on the website lands here automatically. The first task each morning "
    "is to scan this list and confirm yesterday's online orders are picked + dispatched.", BODY))
story += steps([
    "Sales Hub → <b>Online Orders</b>.",
    "Filter by status: <b>Awaiting pick</b> first.",
    "Click an order to view items, address, customer notes.",
    "Click <b>Mark as picked</b> when warehouse confirms.",
    "Click <b>Assign driver</b> to add it to a delivery run.",
])
story.append(tip("Customers can see the status update in real-time on /shop/track — so update statuses promptly. A 24-hour-old 'awaiting pick' looks bad and triggers complaint emails.", "warn"))

story.append(PageBreak())
story.append(Paragraph("4.3 · Delivery Management", H2))
story.append(img("54_delivery_mgmt", 165, "Delivery Management — every order out for delivery."))
story.append(Paragraph(
    "When a customer phones asking 'where's my delivery?', this is your answer screen.", BODY))
story += steps([
    "Sidebar → <b>Stock Management → Delivery Management</b>.",
    "Filter by <b>date</b>, <b>driver</b>, or <b>status</b>.",
    "Click any row to see the customer's address, phone, and items.",
    "If you need to call the customer (e.g. driver can't find house), the phone number is one click away.",
])
story.append(tip(NOTES["delivery_promise_warn"], "warn"))


# ============================================================================
# PART 5 — PRODUCTS & SUPPLIERS
# ============================================================================
story += section_break("PART 5", "Products & Suppliers")

story.append(Paragraph("5.1 · Products Hub", H2))
story.append(img("41_products_hub", 165, "Products Hub — launchpad for everything product-related."))

story.append(PageBreak())
story.append(Paragraph("5.2 · Products list", H2))
story.append(img("42_supplier_products", 165, "Products list — the master catalogue."))
story.append(Paragraph(
    "The Products list shows every tile, accessory and adhesive we sell. You'll mostly use it to "
    "<b>look up a product's stock level, price or supplier</b>.", BODY))
story += steps([
    "Sidebar → <b>Products &amp; Suppliers → Products</b>.",
    "Search by <b>name</b>, <b>SKU</b>, <b>finish</b>, or <b>size</b>.",
    "Filter by <b>supplier</b>, <b>category</b>, <b>in-stock-only</b>, etc.",
    "Click a product row to see all details on one page.",
])
story.append(feature_table([
    ("Stock level",       "How many we have. Trade customers see live stock; retail customers see 'in stock' or 'out of stock'."),
    ("Cost price",        "What we pay the supplier. <b>Never</b> show this to customers."),
    ("Retail price",      "What we charge retail customers."),
    ("Trade price",       "What trade customers pay (typically 15-25 % less)."),
    ("Supplier",          "Who makes it. Useful when ordering in more."),
    ("Lead time",         "How long to restock. 'Now' = stocked; '4-6 weeks' = imported on-demand."),
]))

story.append(PageBreak())
story.append(Paragraph("5.3 · Supplier Health", H2))
story.append(img("43_supplier_health", 165, "Supplier Health dashboard — sync status for every supplier."))
story.append(Paragraph(
    "Shows whether each supplier's stock feed is live and current. If a supplier is red "
    "or amber, the manager should know — pricing or stock data may be stale.", BODY))
story.append(tip("If you spot a supplier flagged red and a customer is asking for one of their products, double-check stock before promising — it might be out-of-date.", "warn"))

story.append(PageBreak())
story.append(Paragraph("5.4 · Sync Hub", H2))
story.append(img("44_sync_hub", 165, "Sync Hub — manually trigger a supplier feed refresh."))
story.append(Paragraph(
    "Most syncs run automatically overnight. The Sync Hub lets a manager force a re-sync if a "
    "supplier just emailed updated prices. Staff usually don't need this — but you should know it exists.", BODY))


# ============================================================================
# PART 6 — STOCK MANAGEMENT
# ============================================================================
story += section_break("PART 6", "Stock Management")

story.append(Paragraph("6.1 · Stock Hub", H2))
story.append(img("45_stock_hub", 165, "Stock Hub — every stock-related task in one place."))

story.append(PageBreak())
story.append(Paragraph("6.2 · Stock Allocation", H2))
story.append(img("46_stock_allocation", 165, "Stock Allocation — split stock between stores."))
story.append(Paragraph(
    "If you have multiple shops, stock is allocated between them here. Useful when a customer at one "
    "store wants something held at another — you can see exactly where each box is.", BODY))

story.append(PageBreak())
story.append(Paragraph("6.3 · Bulk Stock Edit", H2))
story.append(img("47_bulk_stock", 165, "Bulk Stock Edit — adjust many products at once."))
story.append(Paragraph(
    "Used during stocktakes. Select a category, then update the on-hand count for every product. "
    "Saves doing one-at-a-time edits.", BODY))
story.append(tip("Always double-check before clicking <b>Save</b>. There's no undo on bulk stock edits — you'd have to re-count.", "warn"))

story.append(PageBreak())
story.append(Paragraph("6.4 · Delivery Check-In", H2))
story.append(img("48_delivery_check_in", 165, "Delivery Check-In — booking incoming stock from suppliers."))
story.append(Paragraph(
    "When a supplier truck arrives at the warehouse, this is where you check in what came off the truck.", BODY))
story += steps([
    "Sidebar → <b>Stock Management → Delivery Check-In</b>.",
    "Find the expected delivery (it's there if the supplier sent an ASN — Advance Ship Notice).",
    "Click <b>Check in</b>.",
    "Tick each item and confirm the quantity. If something's missing, leave the qty as 0.",
    "Note any damage (photos if possible — drag-drop into the form).",
    "Click <b>Confirm</b>. Stock is added to the system, and any backorders are auto-allocated to the customers waiting.",
])

story.append(PageBreak())
story.append(Paragraph("6.5 · Stock Transfers", H2))
story.append(img("49_stock_transfers", 165, "Stock Transfers — move boxes between stores or warehouse."))
story.append(Paragraph(
    "When a customer at Store A asks for an item only held at Store B, this is how you arrange it.", BODY))

story.append(PageBreak())
story.append(Paragraph("6.6 · Reorder Suggestions", H2))
story.append(img("50_reorder_suggestions", 165, "Reorder Suggestions — products running low."))
story.append(Paragraph(
    "The system suggests items to reorder based on velocity and lead time. The manager reviews and "
    "places the order. Staff don't act on these directly — but you should glance at them so you "
    "know which lines are running low (and not over-promise to customers).", BODY))

story.append(PageBreak())
story.append(Paragraph("6.7 · Batch Tracking", H2))
story.append(img("51_batch_tracking", 165, "Batch Tracking — for tile-shade and tone matching."))
story.append(Paragraph(
    "Tiles vary slightly between manufacturing batches. If a customer needs more of a tile they bought "
    "before, batch tracking shows whether we have <b>matching-batch</b> stock.", BODY))
story.append(tip("Always check batch when a customer is buying additional tiles for an existing job. Mismatched batches = visible shade lines on the floor.", "do"))

story.append(PageBreak())
story.append(Paragraph("6.8 · To-Order Report", H2))
story.append(img("52_to_order", 165, "To-Order Report — items the customer wants but we don't stock."))
story.append(Paragraph(
    "Special-order items (e.g. tiles imported on-demand) live here. Each row shows the customer waiting, "
    "the supplier ordered from, and the expected arrival date.", BODY))

story.append(PageBreak())
story.append(Paragraph("6.9 · Stocktake Report", H2))
story.append(img("53_stocktake", 165, "Stocktake Report — variance after a count."))
story.append(Paragraph(
    "After a stocktake (Bulk Stock Edit, 6.3), this report shows what changed and the variance value. "
    "The manager reviews and explains any large discrepancies.", BODY))


# ============================================================================
# PART 7 — CUSTOMERS
# ============================================================================
story += section_break("PART 7", "Customers")

story.append(Paragraph("7.1 · Customers Hub", H2))
story.append(img("55_customers_hub", 165, "Customers Hub — launchpad."))

story.append(PageBreak())
story.append(Paragraph("7.2 · Trade Accounts", H2))
story.append(img("56_trade_accounts", 165, "Trade Accounts — the registered builders &amp; fitters list."))
story.append(Paragraph(
    "Trade customers (builders, fitters, retailers) get <b>discounted prices automatically</b> when "
    "selected on the till or logged in on the website. This page is the master list.", BODY))
story.append(feature_table([
    ("Active",       "Approved trade customer — discount applies automatically."),
    ("Pending",      "Just registered — manager needs to verify trade status before approval."),
    ("Suspended",    "Account paused (typically unpaid invoice). No trade discount until resolved."),
    ("VIP",          "Premium trade — extra discount tier. Rare. Manager sets these."),
]))
story.append(tip("If a trade customer queries their price, click into their account and check the <b>Tier</b> field. Some have higher discounts than others.", "tip"))

story.append(PageBreak())
story.append(Paragraph("7.3 · Customer Pricing", H2))
story.append(img("57_customer_pricing", 165, "Customer Pricing — bespoke prices for individual accounts."))
story.append(Paragraph(
    "A handful of large customers have <b>negotiated prices</b> beyond the standard trade tier. Each row "
    "is one product + one customer + the agreed price. Don't change anything here — refer to manager.", BODY))

story.append(PageBreak())
story.append(Paragraph("7.4 · Invite Customers", H2))
story.append(img("58_invites", 165, "Invite Customers — send sign-up links to leads."))
story.append(Paragraph(
    "If you meet a trade lead at the counter, send them an invite link from this page. They click it, "
    "fill in the form, and become a pending trade account.", BODY))

story.append(PageBreak())
story.append(Paragraph("7.5 · Bulk Inquiries", H2))
story.append(img("59_inquiries", 165, "Bulk Inquiries — large quote requests from the website."))
story.append(Paragraph(
    "When a customer fills the 'request a quote for 200 m²' form on the website, it lands here. "
    "Manager assigns to a sales rep — staff respond from the <b>Inbox</b> (Part 8.3).", BODY))


# ============================================================================
# PART 8 — COMMUNICATION
# ============================================================================
story += section_break("PART 8", "Communication")

story.append(Paragraph("8.1 · Communication Hub", H2))
story.append(img("60_communication_hub", 165, "Communication Hub — chat, tasks, email, marketing."))

story.append(PageBreak())
story.append(Paragraph("8.2 · Staff Chat", H2))
story.append(img("61_staff_chat", 165, "Staff Chat — for internal team messages."))
story += steps([
    "Sidebar → <b>Communication → Staff Chat</b>.",
    "Choose a channel (e.g. <b>#warehouse</b>) or DM a colleague.",
    "Type your message. Tag <b>@username</b> to alert someone.",
    "Pictures and files can be drag-dropped into the message box.",
])
story.append(tip("Use Staff Chat for work questions, not WhatsApp — chat history is stored on the system and audit-trailed.", "do"))

story.append(PageBreak())
story.append(Paragraph("8.3 · Tasks &amp; Notes", H2))
story.append(img("62_tasks", 165, "Tasks — assigned to-dos, with due dates."))
story.append(Paragraph(
    "Anything assigned to you shows on the Dashboard. The full task list lives here. Tick when done.", BODY))

story.append(PageBreak())
story.append(Paragraph("8.4 · Inbox", H2))
story.append(img("63_inbox", 165, "Inbox — every customer email and contact-form message."))
story.append(Paragraph(
    "All emails to <b>info@tilestation.co.uk</b> + every website contact form lands here. "
    "Reply directly from the system — replies thread by customer.", BODY))
story += steps([
    "Sidebar → <b>Communication → Inbox</b>.",
    "Filter by <b>unread</b>, <b>assigned to me</b>, or by tag (sample-request, complaint, etc.).",
    "Click a message to read.",
    "Click <b>Reply</b> — your draft is auto-saved as you type.",
    "Click <b>Send</b>. The message is sent from <b>info@</b> with your name in the footer.",
])
story.append(tip(NOTES["inbox_response_time"], "do"))

story.append(PageBreak())
story.append(Paragraph("8.5 · Send Email", H2))
story.append(img("64_send_email", 165, "Send Email — broadcast or one-off email tools."))
story.append(Paragraph(
    "For sending a one-off email to a specific customer (e.g. 'your special order has arrived'). "
    "Mass marketing emails go through Marketing (Part 8.6).", BODY))

story.append(PageBreak())
story.append(Paragraph("8.6 · Marketing", H2))
story.append(img("65_marketing", 165, "Marketing — campaigns and segments."))
story.append(Paragraph(
    "Manager-led — staff usually don't create campaigns, but you should understand the segments "
    "so you can tell customers why they got a particular offer.", BODY))

story.append(PageBreak())
story.append(Paragraph("8.7 · Abandoned Baskets", H2))
story.append(img("66_abandoned_baskets", 165, "Abandoned Baskets — customers who left without checking out."))
story.append(Paragraph(
    "Customers who added items to the basket on the website but didn't pay land here. The system "
    "auto-emails them after 1 hour, then 24 hours. Counter staff can also call them — there's a "
    "<b>Phone</b> button if their number is on file.", BODY))
story.append(tip(NOTES["abandoned_baskets_tip"], "do"))

story.append(PageBreak())
story.append(Paragraph("8.8 · Promo Codes", H2))
story.append(img("67_promo_codes", 165, "Promo Codes — discount codes for marketing."))
story.append(Paragraph(
    "If a customer says 'I have a promo code', this is where you check it's valid. Enter the code "
    "in the search box — the page shows whether it's active, what it does, and how many times it's been used.", BODY))


# ============================================================================
# PART 9 — REPORTS & ANALYTICS
# ============================================================================
story += section_break("PART 9", "Reports & Analytics")

story.append(Paragraph("9.1 · Reports Hub", H2))
story.append(img("68_reports_hub", 165, "Reports Hub — every report in one place."))

story.append(PageBreak())
story.append(Paragraph("9.2 · Analytics", H2))
story.append(img("69_analytics", 165, "Analytics — sales trends and top products."))
story.append(Paragraph(
    "High-level trends — week-on-week revenue, top products, top customers, top staff. "
    "Useful at end-of-month reviews. Don't act on these directly — managers do.", BODY))

story.append(PageBreak())
story.append(Paragraph("9.3 · Sales Reports", H2))
story.append(img("70_sales_reports", 165, "Sales Reports — detailed line-by-line breakdowns."))
story.append(Paragraph(
    "Granular reports: by date range, staff, payment method, product category. "
    "If accounts ever ask 'what was the cash total on 14 March', this is your answer.", BODY))


# ============================================================================
# PART 10 — STOREFRONT
# ============================================================================
story += section_break("PART 10", "The customer website (storefront)")
story.append(Paragraph(
    "When customers ring asking 'I can't find delivery info on your website' or 'how do I see my order' — "
    "they're looking at one of these pages. Knowing the layout helps you guide them over the phone.", BODY))

story.append(Paragraph("10.1 · Homepage", H2))
story.append(img("01_storefront_home", 165, "/shop — what every visitor lands on."))
story.append(Paragraph(
    "Top: navigation bar (All Tiles, Wall Tiles, Floor Tiles, Sale).<br/>"
    "Big banner: featured collection.<br/>"
    "Below: shop categories, brand marquee, video showroom, customer reviews.<br/>"
    "Footer: delivery info, returns, contact.", BODY))

story.append(PageBreak())
story.append(Paragraph("10.2 · Catalogue", H2))
story.append(img("02_storefront_catalog", 165, "/shop/tiles — every tile, with filters on the left."))
story.append(Paragraph(
    "Customers filter by <b>colour, size, finish, room, sale, in-stock-only</b>. "
    "If they say “I can't find anything in matt 60×60” — guide them to the left filters.", BODY))

story.append(PageBreak())
story.append(Paragraph("10.3 · Product page (PDP)", H2))
story.append(img("03_storefront_pdp", 165, "Product detail page. Big photo, description, prices, add-to-basket."))
story.append(Paragraph("Key features customers see on the PDP:", H3))
story.append(feature_table([
    ("Image gallery",     "Multiple photos, hover-zoom, lifestyle shots."),
    ("Trade pricing",     "Logged-in trade customers see their tier price automatically."),
    ("Volume pricing",    "Buy more = pay less per m²; the table is shown on the page."),
    ("Sample request",    "£1 sample with free postage — customers can order this."),
    ("Delivery cost",     "Postcode-based estimate before they checkout."),
    ("Stock status",      "Live in-stock / lead-time text."),
    ("You may also need", "Cross-sells: grout, adhesive, trim. (Operational only — staff don't edit)."),
    ("Recently viewed",   "Last 6 tiles the customer looked at, sticky across pages."),
    ("Reviews",           "Star rating + customer photos."),
]))

story.append(PageBreak())
story.append(Paragraph("10.4 · Tile Calculator", H2))
story.append(img("04_storefront_calculator", 165, "/shop/calculator — works out how many tiles for an area."))
story.append(Paragraph(
    "Customers type in the room dimensions; the calculator returns m² + recommended waste %. "
    "There's a <b>same calculator</b> in the admin (5.2 / Sales Hub) so you can run it for them over the phone.", BODY))

story.append(PageBreak())
story.append(Paragraph("10.5 · Sample service", H2))
story.append(img("05_storefront_samples", 165, "/shop/tile-samples — order a sample for £1."))
story.append(img("06_storefront_sample_svc", 165, "/shop/sample-service — bespoke sample request form."))

story.append(PageBreak())
story.append(Paragraph("10.6 · Cart, Wishlist &amp; Compare", H2))
story.append(img("07_storefront_cart", 145, "Cart — items the customer is about to buy."))
story.append(img("08_storefront_wishlist", 145, "Wishlist — saved-for-later products."))
story.append(img("09_storefront_compare", 145, "Compare — side-by-side spec comparison (up to 4)."))
story.append(tip("If a customer says 'I added it but it's gone', they may be looking at the Wishlist instead of the Cart. Walk them through both.", "tip"))

story.append(PageBreak())
story.append(Paragraph("10.7 · Checkout", H2))
story.append(img("10_storefront_checkout", 165, "Checkout — three steps: address, delivery, payment."))
story.append(Paragraph("Three steps customers go through:", H3))
story += steps([
    "<b>Step 1 — Address</b>: shipping address, billing address (auto-filled from postcode).",
    "<b>Step 2 — Delivery</b>: choose pallet, kerbside, or click-and-collect. Price varies by postcode.",
    "<b>Step 3 — Payment</b>: card (Stripe), PayPal, or trade-account 30-day terms (trade only).",
])
story.append(tip("If a customer says payment is failing, ask them <b>which step</b> the error appears on. Step 1 = address typo, Step 2 = postcode/delivery zone issue, Step 3 = card declined.", "tip"))

story.append(PageBreak())
story.append(Paragraph("10.8 · Order tracking", H2))
story.append(img("11_storefront_track", 165, "Public tracking — order number + email, no login required."))
story.append(Paragraph("Two ways customers find their order online:", H3))
story += steps([
    "<b>Anonymous tracking</b> — <b>tilestation.co.uk/shop/track</b>, enter order number + email. Status only.",
    "<b>Logged-in account</b> — sign in at <b>/shop/tile-login</b>. Full history, addresses, downloadable invoices.",
])

story.append(PageBreak())
story.append(Paragraph("10.9 · Customer accounts", H2))
story.append(img("12_storefront_login", 145, "Customer login screen."))
story.append(img("13_storefront_register", 145, "Customer register screen."))
story.append(Paragraph(
    "Retail customers can register for a free account — gives them order history, saved addresses, and faster checkout.", BODY))

story.append(PageBreak())
story.append(Paragraph("10.10 · Trade accounts", H2))
story.append(img("14_storefront_trade_reg", 145, "Trade registration — for builders &amp; fitters."))
story.append(img("15_storefront_trade_login", 145, "Trade login — separate from retail."))
story.append(Paragraph(
    "Trade customers have their own login. After registration, an admin approves them (Customers → Trade Accounts, Part 7.2). "
    "Approved trade customers get discounted pricing automatically on every page.", BODY))

story.append(PageBreak())
story.append(Paragraph("10.11 · Refer-a-friend", H2))
story.append(img("16_storefront_refer", 165, "Refer-a-friend — earn store credit for referrals."))
story.append(Paragraph(
    "Customers share a unique link. When the friend buys, both get £20 credit. "
    "If a customer asks 'I referred my mate but no credit appeared', check the friend completed their first order >£100.", BODY))

story.append(PageBreak())
story.append(Paragraph("10.12 · Contact &amp; info pages", H2))
story.append(img("17_storefront_contact", 145, "Contact page — store addresses, phone, hours."))
story.append(img("18_storefront_returns", 145, "Returns policy."))
story.append(img("19_storefront_delivery", 145, "Delivery info."))
story.append(img("20_storefront_faq", 145, "FAQ — common customer questions."))
story.append(Paragraph(
    "Bookmark these pages — when a customer asks 'do you deliver to Cornwall?' or 'what's your returns policy', "
    "you can paste them the link rather than reading from memory.", BODY))


# ============================================================================
# PART 11 — MAINTENANCE
# ============================================================================
story += section_break("PART 11", "System maintenance & health")

story.append(Paragraph("11.1 · Maintenance dashboard", H2))
story.append(img("71_maintenance", 165, "Maintenance — for managers / super-admin to monitor system health."))
story.append(Paragraph(
    "Mostly read-only for staff. Worth knowing it exists in case the manager asks you to "
    "screenshot it during an incident.", BODY))
story.append(feature_table([
    ("UI Health checks",  "18 critical pages tested every night by a robot. Green = all good."),
    ("Sentry status",     "Error tracking — green pill = errors are being captured."),
    ("Maintenance migrators", "One-shot data fixes. Manager runs these — never click yourself."),
    ("Launch checklists", "Downloadable PDFs (this booklet, the post-launch roadmap, etc.)."),
]))


# ============================================================================
# PART 12 — QUICK REFERENCE
# ============================================================================
story += section_break("PART 12", "Glossary & Quick Reference")

story.append(Paragraph("12.1 · Glossary", H2))
glossary_rows = [
    ("PDP",        "Product Detail Page — the page on the website that shows one tile."),
    ("EPOS",       "Electronic Point Of Sale — the till."),
    ("SKU",        "Stock-Keeping Unit — the unique product code (e.g. tile-LP-6611)."),
    ("ASN",        "Advance Ship Notice — a heads-up from the supplier about an incoming delivery."),
    ("Variance",   "Difference between expected cash and actual cash at end of shift."),
    ("Trade tier", "Discount level for a trade customer (Standard, Premium, VIP)."),
    ("Pallet",     "Heavy delivery for big tile orders. Uses a pallet truck."),
    ("Kerbside",   "Light delivery — driver leaves at the kerb, customer carries inside."),
    ("Click & collect", "Customer pays online, picks up in store. No delivery fee."),
    ("Backorder",  "Customer paid; item not in stock; we order from supplier; ship when arrived."),
    ("Float",      "Cash already in the till at the start of the shift."),
    ("Credit note", "Voucher code worth £X — customer can use it on any future purchase."),
    ("Stocktake",  "Physical count of every product to reconcile against system numbers."),
    ("Lead time",  "How long after a customer orders until we can ship it."),
    ("Volume pricing", "Tier-based discount: more m² = lower £/m²."),
]
story.append(feature_table(glossary_rows))

story.append(PageBreak())
story.append(Paragraph("12.2 · Quick reference card", H2))
story.append(Paragraph("Pin this page to the till.", BODY))
story.append(Spacer(1, 4*mm))
story.append(Table([
    ["Task",                          "Where to click"],
    ["Ring up a sale",                "Sales Hub → EPOS"],
    ["Find an invoice",               "Sales Hub → Invoices → search"],
    ["Issue a refund",                "Open invoice → Refund button → tick items → confirm"],
    ["Email a receipt",               "Open invoice → Email button"],
    ["Create a quote",                "Sales Hub → Quotations → New"],
    ["Convert a quote to sale",       "Open quote → Convert to Invoice"],
    ["Check a delivery",              "Sidebar → Stock → Delivery Management"],
    ["Open / close drawer",           "Sales Hub → Cash Counter"],
    ["Find a customer",               "EPOS → Customer search"],
    ["Print a tile calculation",      "Sales Hub → Tile Calculator → Print"],
    ["Look up product stock",         "Sidebar → Products → search"],
    ["Check batch (shade matching)",  "Sidebar → Stock → Batch Tracking"],
    ["Reply to customer email",       "Sidebar → Communication → Inbox"],
    ["Check a promo code",            "Sidebar → Communication → Promo Codes"],
    ["Find an online order",          "Sales Hub → Online Orders"],
    ["Reset my password",             "Login page → Forgot password"],
], colWidths=[80*mm, 92*mm], style=[
    ("BACKGROUND", (0,0), (-1,0), DARK),
    ("TEXTCOLOR", (0,0), (-1,0), YELLOW),
    ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
    ("FONTNAME", (0,1), (0,-1), "Helvetica-Bold"),
    ("FONTSIZE", (0,0), (-1,-1), 10),
    ("LEADING", (0,0), (-1,-1), 14),
    ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ("LEFTPADDING", (0,0), (-1,-1), 7),
    ("RIGHTPADDING", (0,0), (-1,-1), 7),
    ("TOPPADDING", (0,0), (-1,-1), 7),
    ("BOTTOMPADDING", (0,0), (-1,-1), 7),
    ("LINEBELOW", (0,0), (-1,-1), 0.3, BORDER),
]))

story.append(Spacer(1, 8*mm))
story.append(Paragraph("12.3 · Golden rules", H2))
# Parse the editable golden_rules text. Each non-empty line becomes a row.
# Lines may be prefixed "1. " / "1) " — strip the number; we re-number for layout.
import re as _re_rules
_rules_text = NOTES.get("golden_rules", "")
_rules = []
for ln in _rules_text.splitlines():
    s = ln.strip()
    if not s:
        continue
    s = _re_rules.sub(r"^\s*\d+[\.\)]\s*", "", s)
    _rules.append(s)
_golden_table = [[f"{i+1}.", r] for i, r in enumerate(_rules)] or [["1.", "(no rules configured)"]]
story.append(Table(_golden_table, colWidths=[10*mm, 162*mm], style=[
    ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
    ("TEXTCOLOR", (0,0), (0,-1), ROSE),
    ("FONTSIZE", (0,0), (-1,-1), 10.5),
    ("LEADING", (0,0), (-1,-1), 16),
    ("VALIGN", (0,0), (-1,-1), "TOP"),
    ("LEFTPADDING", (0,0), (-1,-1), 4),
    ("RIGHTPADDING", (0,0), (-1,-1), 4),
    ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ("TOPPADDING", (0,0), (-1,-1), 3),
]))

story.append(Spacer(1, 12*mm))
story.append(Paragraph(
    f'<i>Booklet generated {datetime.utcnow().strftime("%d %b %Y")} · '
    f'Tile Station Operations · Internal use only</i>',
    ParagraphStyle("end", parent=BODY, fontSize=9, textColor=GREY, alignment=TA_CENTER)
))


# ============================================================================
# RENDER
# ============================================================================
def main():
    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    doc = BaseDocTemplate(
        str(OUT_PDF), pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=20*mm, bottomMargin=15*mm,
        title="Tile Station — Staff Training Booklet (Comprehensive)",
        author="Tile Station",
    )
    cover_frame = Frame(0, 0, A4[0], A4[1], id="cover",
                        leftPadding=15*mm, rightPadding=15*mm,
                        topPadding=15*mm, bottomPadding=15*mm)
    body_frame = Frame(doc.leftMargin, doc.bottomMargin,
                       doc.width, doc.height, id="body")
    doc.addPageTemplates([
        PageTemplate(id="cover", frames=cover_frame, onPage=cover_canvas),
        PageTemplate(id="default", frames=body_frame, onPage=header_footer),
    ])
    doc.build(story)
    size_kb = OUT_PDF.stat().st_size / 1024
    print(f"Generated: {OUT_PDF}  ({size_kb:.0f} KB)")


if __name__ == "__main__":
    main()

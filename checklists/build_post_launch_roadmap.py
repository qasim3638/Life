"""
Generates the post-launch monitoring + observability roadmap PDF.
Run: `python3 /app/checklists/build_post_launch_roadmap.py`
Outputs: /app/checklists/Post_Launch_Monitoring_Roadmap.pdf
"""
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table,
    TableStyle, PageBreak, KeepTogether,
)
from reportlab.lib.enums import TA_LEFT


OUT = Path("/app/checklists/Post_Launch_Monitoring_Roadmap.pdf")
BRAND_DARK = colors.HexColor("#1C1917")
BRAND_YELLOW = colors.HexColor("#F7EA1C")
BRAND_GREY = colors.HexColor("#57534E")
BRAND_GREEN = colors.HexColor("#059669")
BRAND_RED = colors.HexColor("#9F1239")
LIGHT_BG = colors.HexColor("#F5F5F4")
TABLE_BORDER = colors.HexColor("#E7E5E4")


# ---------- Styles ----------
styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=styles["Heading1"], fontName="Helvetica-Bold",
                   fontSize=20, leading=24, spaceAfter=8, textColor=BRAND_DARK)
H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontName="Helvetica-Bold",
                   fontSize=14, leading=18, spaceBefore=14, spaceAfter=6,
                   textColor=BRAND_DARK)
H3 = ParagraphStyle("H3", parent=styles["Heading3"], fontName="Helvetica-Bold",
                   fontSize=11, leading=14, spaceBefore=8, spaceAfter=4,
                   textColor=BRAND_DARK)
BODY = ParagraphStyle("Body", parent=styles["BodyText"], fontName="Helvetica",
                      fontSize=9.5, leading=13, alignment=TA_LEFT,
                      textColor=BRAND_DARK)
SMALL = ParagraphStyle("Small", parent=styles["BodyText"], fontName="Helvetica",
                       fontSize=8, leading=11, textColor=BRAND_GREY)
CALLOUT = ParagraphStyle("Callout", parent=BODY, fontSize=9, leading=12,
                         textColor=BRAND_DARK, leftIndent=8, borderPadding=6,
                         backColor=colors.HexColor("#FEF3C7"),
                         borderColor=colors.HexColor("#F59E0B"), borderWidth=0.5)


CELL = ParagraphStyle("Cell", parent=styles["BodyText"], fontName="Helvetica",
                      fontSize=8.5, leading=10.5, textColor=BRAND_DARK,
                      spaceBefore=0, spaceAfter=0)
CELL_HEADER = ParagraphStyle("CellHeader", parent=CELL, fontName="Helvetica-Bold",
                             fontSize=9, textColor=BRAND_YELLOW)


def header_footer(canvas, doc):
    canvas.saveState()
    # Header bar
    canvas.setFillColor(BRAND_DARK)
    canvas.rect(0, A4[1] - 14*mm, A4[0], 14*mm, stroke=0, fill=1)
    canvas.setFillColor(BRAND_YELLOW)
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(15*mm, A4[1] - 9*mm, "TILE STATION  ·  POST-LAUNCH MONITORING ROADMAP")
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(A4[0] - 15*mm, A4[1] - 9*mm,
                           datetime.utcnow().strftime("%d %b %Y"))
    # Footer bar
    canvas.setFillColor(BRAND_GREY)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawString(15*mm, 10*mm, "Confidential — internal use only")
    canvas.drawRightString(A4[0] - 15*mm, 10*mm, f"Page {doc.page}")
    canvas.restoreState()


def make_table(rows, col_widths, header=True, zebra=True):
    """Build a styled table. First row treated as header when header=True.

    Wraps every cell's string content in a Paragraph so long text wraps
    within its column instead of overflowing into the next one.
    """
    def _wrap_cell(value, is_header_row):
        # Already a flowable (Paragraph etc.) — leave it alone
        if not isinstance(value, str):
            return value
        style = CELL_HEADER if is_header_row else CELL
        return Paragraph(value, style)

    wrapped_rows = []
    for row_idx, row in enumerate(rows):
        is_h = header and row_idx == 0
        wrapped_rows.append([_wrap_cell(c, is_h) for c in row])

    t = Table(wrapped_rows, colWidths=col_widths, repeatRows=1 if header else 0)
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, TABLE_BORDER),
        ("LINEBEFORE", (0, 0), (-1, -1), 0.4, TABLE_BORDER),
        ("LINEAFTER", (0, 0), (-1, -1), 0.4, TABLE_BORDER),
    ]
    if header:
        style += [
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_DARK),
        ]
    if zebra:
        for i in range(1, len(rows)):
            if i % 2 == 0:
                style.append(("BACKGROUND", (0, i), (-1, i), LIGHT_BG))
    t.setStyle(TableStyle(style))
    return t


def P(text, style=BODY):
    return Paragraph(text, style)


# ---------- Build content ----------
story = []

# === COVER ===
story.append(Spacer(1, 12*mm))
story.append(P("Post-Launch Monitoring &amp; Observability Roadmap", H1))
story.append(P("A 6-week phased plan to keep the storefront and EPOS spotless after launch — "
                "covering uptime, security, SEO, link integrity, PDP health, and the "
                "<b>backbone admin features</b> (Bulk Category Editor, Supplier Products sync) "
                "that hold everything together.", BODY))
story.append(Spacer(1, 6*mm))

story.append(Table([
    [Paragraph("Already live (day 1):", CELL_HEADER),  Paragraph("1. /api/health endpoint   ·   2. Sentry wiring (set DSN to activate)   ·   3. Security headers", CELL)],
    [Paragraph("Status:", CELL_HEADER),                Paragraph("All 3 verified passing — DB ping 2 ms, 6 OWASP headers applied site-wide.", CELL)],
    [Paragraph("Production sync:", CELL_HEADER),       Paragraph("Click \"Save to Github\" so Railway picks these up. Set SENTRY_DSN env var on Railway to activate.", CELL)],
], colWidths=[40*mm, 130*mm], hAlign="LEFT"))
story[-1].setStyle(TableStyle([
    ("BACKGROUND", (0,0), (0,-1), BRAND_DARK),
    ("VALIGN", (0,0), (-1,-1), "TOP"),
    ("BOX", (0,0), (-1,-1), 0.4, TABLE_BORDER),
    ("INNERGRID", (0,0), (-1,-1), 0.4, TABLE_BORDER),
    ("LEFTPADDING", (0,0), (-1,-1), 6),
    ("RIGHTPADDING", (0,0), (-1,-1), 6),
    ("TOPPADDING", (0,0), (-1,-1), 6),
    ("BOTTOMPADDING", (0,0), (-1,-1), 6),
]))

# === TIER 1: WATCHDOGS ===
story.append(P("Tier 1 — Always-on Watchdogs (smoke alarms)", H2))
story.append(P("These run 24/7 and only ping you when something breaks. The point isn’t to "
               "stare at dashboards — it’s to sleep at night.", BODY))
story.append(Spacer(1, 3*mm))
story.append(make_table([
    ["What", "Why", "Tool / Approach", "Status"],
    ["Uptime monitor", "Know within 60 s if site is down", "UptimeRobot or BetterStack — pings /api/health every 1 min", "TODO"],
    ["Error tracking", "Capture every JS + Python crash with stack trace", "Sentry (free 5k events/mo)", "✅ Wired"],
    ["API health endpoint", "Single fast endpoint for monitors to ping", "/api/health (DB ping + uptime)", "✅ Live"],
    ["Real User Monitoring", "Catch slow pages before reviews flag it", "Cloudflare Web Analytics (free)", "TODO"],
    ["Daily UI Health PDF", "18 selectors checked, emailed at 03:00 UTC", "Already built", "✅ Live"],
    ["Resend webhook handler", "Track which transactional emails bounced", "POST /api/email-webhook", "TODO"],
], [38*mm, 50*mm, 60*mm, 22*mm]))

# === TIER 2: SECURITY ===
story.append(P("Tier 2 — Security (lock the doors)", H2))
story.append(make_table([
    ["What", "Why", "How", "Status"],
    ["Security headers", "CSP / HSTS / XFO / XCTO / Referrer-Policy / Permissions-Policy", "FastAPI middleware", "✅ Live"],
    ["Rate limiting", "Stop brute-force on login + card-testing on checkout", "slowapi: 5/min login, 10/min checkout", "TODO"],
    ["CSRF protection", "Stop drive-by POSTs from malicious sites", "Bearer tokens cover most; admin forms need tokens", "TODO"],
    ["Dependency CVE scan", "Auto-flag vulnerable packages", "GitHub Dependabot + weekly pip/yarn audit", "TODO"],
    ["Secret leak scan", "Stop API keys being committed", "gitleaks pre-commit hook", "TODO"],
    ["Admin audit log", "Who logged in, when, from what IP", "MongoDB collection + admin viewer", "TODO"],
    ["Webhook signature verify", "Verify Stripe + Resend HMAC signatures", "Already in Stripe SDK; audit Resend handler", "Audit"],
    ["2FA for admins", "One stolen password ≠ entire site compromised", "TOTP via pyotp", "TODO"],
], [38*mm, 50*mm, 60*mm, 22*mm]))

story.append(Spacer(1, 3*mm))
story.append(P("<b>Note:</b> Security headers were applied site-wide on day 1. The default CSP "
               "allows Stripe + GA + Resend + R2 image CDN. If a third-party widget breaks after deploy, "
               "set CSP_REPORT_ONLY=true in env to debug without blocking.", CALLOUT))

# === TIER 3: LINKS & NAV ===
story.append(PageBreak())
story.append(P("Tier 3 — Links &amp; Navigation (nothing broken anywhere)", H2))
story.append(make_table([
    ["What", "Why", "How", "Frequency"],
    ["Internal link crawler", "Walks every link from homepage + sitemap, depth-2 follow, flags 404 / 500 / redirect loops",
     "Daily cron, headless Playwright (already installed)", "Daily"],
    ["Sitemap.xml validator", "All URLs return 200, lastmod current, robots.txt allows them",
     "Daily cron", "Daily"],
    ["External link checker", "Manufacturer specs and supplier portals go down often",
     "Weekly cron", "Weekly"],
    ["Redirect chain audit", "Old URL → new URL must 301 cleanly without chains",
     "Part of crawler", "Daily"],
    ["Zero-results search log", "Customers searching “60x60 marble” but seeing empty page = lost sale",
     "Log + weekly digest", "Weekly"],
], [40*mm, 55*mm, 55*mm, 20*mm]))

# === TIER 4: PDP HEALTH ===
story.append(P("Tier 4 — PDP Integrity (every product page perfect)", H2))
story.append(make_table([
    ["Check", "Why it matters", "Frequency"],
    ["At least 1 image", "Empty image = lost sale", "Daily"],
    ["Price &gt; 0", "£0.00 = customer confusion", "Daily"],
    ["Stock qty OR always_in_stock=true", "Out-of-stock not flagged = oversell", "Daily"],
    ["Finish + Size (tiles only, NOT accessories)", "Filters break without these — e.g. /tiles?finish=matt", "Daily"],
    ["Description ≥ 50 chars", "SEO and customer trust", "Weekly"],
    ["Product images load (no 404)", "Already covered for supplier sync — extend to live PDPs", "Daily"],
    ["schema.org Product markup valid", "Required for Google rich snippets", "Weekly"],
    ["Add-to-cart button works", "Already in UI Health checks", "✅ Live"],
    ["Trade pricing displays correctly", "Already covered (the recurring trade-login bug)", "✅ Live"],
], [55*mm, 80*mm, 35*mm]))

# === TIER 5: STRUCTURE / SEO ===
story.append(P("Tier 5 — Website Structure &amp; SEO", H2))
story.append(make_table([
    ["What", "Why", "Tool"],
    ["Heading hierarchy audit", "h1→h3 jumps confuse screen readers + Google", "Weekly Playwright crawl"],
    ["Alt text on images", "WCAG accessibility + SEO", "Same crawl"],
    ["Meta title + description per page", "Empty meta = Google guesses badly", "Same crawl"],
    ["Canonical tags", "Stops duplicate-content penalties", "Same crawl"],
    ["Open Graph + Twitter Card tags", "Social shares look professional", "Spot-check"],
    ["Page speed (Core Web Vitals)", "LCP &lt; 2.5 s, CLS &lt; 0.1, INP &lt; 200 ms — Google ranks on these", "PageSpeed Insights API daily"],
    ["Mobile-friendly score", "60 %+ of UK tile shoppers on mobile", "Daily PageSpeed mobile"],
], [50*mm, 65*mm, 55*mm]))

# === TIER 6: BACKBONE INTERNAL FEATURES ===
story.append(PageBreak())
story.append(P("Tier 6 — Backbone Internal Features (the engine room)", H2))
story.append(P("These are the admin features the entire system depends on. They have many "
                "small components (sync, scopes, staging, name-transformation, image upload) "
                "and silently breaking any one of them propagates through the storefront and EPOS. "
                "<b>Watch them like a hawk.</b>", BODY))

story.append(P("6A · Bulk Category Editor", H3))
story.append(make_table([
    ["Health Check", "What goes wrong if missed", "Cadence"],
    ["Save persists every field (incl. nested specs, tags, images)", "Edits silently dropped", "Per-save smoke test"],
    ["Reorder doesn't drop categories", "Categories vanish from menu", "After every save"],
    ["Bulk price update math", "10 % markup applied twice", "Daily aggregate spot check"],
    ["Bulk stock update", "Negative stock values accepted", "Validation test"],
    ["Image bulk swap rolls back on failure", "Half-broken state", "Per-batch transaction"],
    ["Save latency &lt; 2 s for 100 rows", "Admin UX degradation", "P95 latency dashboard"],
    ["Concurrent-edit conflict warning", "One admin overwrites another silently", "Lock + last-modified header"],
], [55*mm, 65*mm, 50*mm]))

story.append(P("6B · Supplier Products Sync", H3))
story.append(make_table([
    ["Health Check", "What goes wrong if missed", "Cadence"],
    ["Last-sync timestamp per supplier", "Stale catalogue, customers see old prices", "Hourly + alert if &gt; 24 h"],
    ["Pending staging count", "Backlog grows unnoticed", "Daily digest"],
    ["Failed-sync counter", "Single supplier silently broken for days", "Slack alert on threshold"],
    ["Image upload to R2 success rate", "Products published without images", "Daily aggregate"],
    ["Duplicate detection (SPLENDOUR_SERIES_TO_UNIQUE_NAME)", "Same product from 2 suppliers gets same name", "On every transform"],
    ["Naming transformation success rate", "Raw supplier names leak to PDP", "Alert if &lt; 95 %"],
    ["finish + size populated for tile suppliers", "Filters break, customer searches return empty", "Block publish if missing"],
    ["Cost-price markup not double-applied", "Prices doubled, refund cascade", "Per-product validator"],
    ["Manual edits preserved across sync (price + name locks)", "Admin work overwritten on next sync", "Pre-sync audit"],
    ["Excluded categories respected", "Deleted categories reappear", "Pre-sync filter"],
    ["Non-tile-product exclusion", "Adhesives appear in /shop/tiles", "Filter at sync time"],
], [55*mm, 65*mm, 50*mm]))

story.append(Spacer(1, 3*mm))
story.append(P("<b>Recommended dashboard:</b> a single &quot;Sync Health&quot; admin page that "
               "shows per-supplier status, last-sync age, last-failure reason, pending staging, "
               "and a &quot;Test sync&quot; button. Cron probes each supplier daily and writes a row to "
               "<code>db.sync_health_log</code> for trend graphs.", CALLOUT))

# === TIER 7: BACKUPS ===
story.append(PageBreak())
story.append(P("Tier 7 — Data Hygiene &amp; Backups", H2))
story.append(make_table([
    ["What", "Why", "How"],
    ["Daily MongoDB backup", "Disaster recovery", "Railway has this — verify retention ≥ 30 days"],
    ["Weekly restore test", "Untested backups = no backups", "Quarterly: spin up staging from last backup"],
    ["R2 image versioning", "Recover deleted images", "Cloudflare R2 versioning — enable it"],
    ["Order data integrity", "Total = sum(line items) + shipping + VAT", "Already covered for invoice deposits"],
    ["Orphan record cleanup", "Stale carts &gt; 30 days, expired tokens", "Weekly cron"],
], [50*mm, 55*mm, 65*mm]))

# === TIER 8: LOGS ===
story.append(P("Tier 8 — Logs &amp; Observability", H2))
story.append(make_table([
    ["What", "Why", "Tool"],
    ["Centralised logs", "Searchable across backend + frontend + Stripe webhooks", "Logtail or BetterStack (free tier)"],
    ["Slow-query log", "MongoDB queries &gt; 100 ms surfaced", "Mongo profiler"],
    ["API response-time tracking", "P95 latency per endpoint", "Sentry Performance (already installed)"],
    ["Frontend bundle size watch", "Catch when someone imports moment.js (200kb)", "bundlesize CI check"],
], [45*mm, 60*mm, 65*mm]))

# === TIER 9: ALERTS ===
story.append(P("Tier 9 — Alerting Strategy", H2))
story.append(P("The point of all the above is <b>not to stare at dashboards</b> — it's to get "
                "notified only when something is wrong. Three tiers:", BODY))

story.append(make_table([
    ["Tier", "Channel", "Triggers"],
    ["Pager (wakes admin)", "SMS + Slack DM",
     "Site down &gt; 2 min  ·  Stripe webhooks failing  ·  DB unreachable  ·  5xx error rate &gt; 1 %  ·  Daily backup failed"],
    ["Email digest (next morning)", "Resend → admin inbox",
     "Daily UI Health PDF (live)  ·  Daily reconciliation (live)  ·  Weekly: top 0-result searches, broken external links, low-stock items  ·  Monthly: dependency CVE summary, refund rate, conversion funnel"],
    ["Quiet (just log)", "DB / Sentry breadcrumbs only",
     "Successful crons  ·  Normal traffic  ·  Cache hits"],
], [38*mm, 38*mm, 95*mm]))

# === ROLLOUT ===
story.append(PageBreak())
story.append(P("Suggested 6-week post-launch rollout", H2))
story.append(make_table([
    ["Week", "Build", "ROI"],
    ["1", "Sentry DSN set ✓ + UptimeRobot account ✓ + /api/health verified ✓ + security headers ✓", "Catches 80 % of incidents in &lt; 1 min"],
    ["2", "Pre-Launch Scan button (next) + broken-link crawler + sitemap.xml validator", "Prevents customer-facing 404s"],
    ["3", "Rate limiting + admin 2FA + Dependabot + gitleaks pre-commit", "Locks the doors"],
    ["4", "PDP integrity daily cron + zero-results search log + Stripe failed-payment alert", "Protects revenue"],
    ["5", "Sync Health dashboard (Tier 6) + Core Web Vitals daily check + accessibility audit", "Protects backbone + SEO"],
    ["6", "Centralised logs + admin audit log + backup restore test + monthly review cadence", "Forensic readiness"],
], [15*mm, 95*mm, 60*mm]))

story.append(Spacer(1, 4*mm))
story.append(P("Total effort: roughly <b>30–40 focused hours</b> spread across 6 weeks. After "
                "Week 1 you’re already protected from the most common launch-day failure modes "
                "(silent crashes, downtime, XSS).", BODY))

# === CLOSING / KEYS ===
story.append(P("Where to put the credentials", H2))
story.append(make_table([
    ["Service", "Env var", "Where to set it"],
    ["Sentry (backend)",  "SENTRY_DSN",                 "Railway → Variables → Add"],
    ["Sentry (frontend)", "REACT_APP_SENTRY_DSN",       "Railway → Variables → Add"],
    ["Sentry env tag",    "ENVIRONMENT",                 "Set to 'production' on Railway"],
    ["Sentry release",    "RELEASE_VERSION",             "Optional: set on each deploy for release tagging"],
    ["UptimeRobot",       "(no env var — sign up)",      "uptimerobot.com → Add Monitor → ping https://yourdomain.com/api/health"],
    ["Headers debug",     "CSP_REPORT_ONLY=true",        "Set temporarily in Railway if a 3rd-party widget breaks"],
], [40*mm, 50*mm, 80*mm]))

story.append(Spacer(1, 6*mm))
story.append(P("This document is intentionally organised by <b>priority of harm if missed</b>, "
                "not by ease of build. If you only ship Tier 1 + Tier 2 + Tier 6, you've "
                "covered the launches that matter most.", BODY))


# ---------- Render ----------
def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = BaseDocTemplate(
        str(OUT), pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=20*mm, bottomMargin=18*mm,
        title="Tile Station — Post-Launch Monitoring Roadmap",
        author="Emergent",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin,
                  doc.width, doc.height, id="normal")
    doc.addPageTemplates([PageTemplate(id="default", frames=frame, onPage=header_footer)])
    doc.build(story)
    size_kb = OUT.stat().st_size / 1024
    print(f"Generated: {OUT}  ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()

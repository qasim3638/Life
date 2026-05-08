"""Generate a daily PDF report from a UI health run."""
from __future__ import annotations

from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def _fmt_iso(iso: str) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y, %H:%M UTC")
    except Exception:
        return iso


def render_ui_health_pdf(run: dict) -> bytes:
    """Returns a PDF (bytes) summarising a single UI health run."""
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title="Tile Station — UI Health Report",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleX", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=18, textColor=colors.HexColor("#0F172A"), alignment=0, spaceAfter=2,
    )
    sub_style = ParagraphStyle(
        "Sub", parent=styles["Normal"], fontSize=9,
        textColor=colors.HexColor("#64748B"), spaceAfter=10,
    )
    cell_style = ParagraphStyle(
        "Cell", parent=styles["Normal"], fontSize=8.5, leading=11,
        textColor=colors.HexColor("#0F172A"),
    )
    mono_style = ParagraphStyle(
        "Mono", parent=styles["Normal"], fontName="Courier",
        fontSize=7.5, leading=10, textColor=colors.HexColor("#475569"),
    )

    results = run.get("results") or []
    passed = run.get("passed_count", 0)
    failed = run.get("failed_count", 0)
    skipped = run.get("skipped_count", sum(1 for r in results if r.get("status") == "skipped"))
    total = len(results)
    overall = "ALL PASSING" if failed == 0 and total > 0 else f"{failed} FAILING" if failed > 0 else "NO CHECKS RAN"
    overall_color = "#059669" if failed == 0 and total > 0 else "#DC2626"

    story = [
        Paragraph("Tile Station — Daily UI Health Report", title_style),
        Paragraph(
            f"Run at <b>{_fmt_iso(run.get('ran_at', ''))}</b> &nbsp;·&nbsp; "
            f"Probed <b>{run.get('base_url', '')}</b> &nbsp;·&nbsp; "
            f"Duration: {run.get('duration_ms', 0)} ms",
            sub_style,
        ),
    ]

    # Big status banner
    banner_data = [[
        Paragraph(
            f"<font size=14 color='white'><b>{overall}</b></font>",
            ParagraphStyle("B", fontName="Helvetica-Bold"),
        ),
        Paragraph(
            f"<font size=10 color='white'>{passed} pass · {failed} fail"
            + (f" · {skipped} skipped" if skipped else "")
            + f" · {total} total</font>",
            ParagraphStyle("B2"),
        ),
    ]]
    banner = Table(banner_data, colWidths=[100 * mm, 82 * mm])
    banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(overall_color)),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(banner)
    story.append(Spacer(1, 8))

    if run.get("error"):
        story.append(Paragraph(
            f"<font color='#DC2626'><b>Runner error:</b> {run['error']}</font>",
            sub_style,
        ))

    # Detailed results table
    head_row = ["#", "Status", "Check", "URL", "Missing selectors"]
    data: list = [head_row]
    rules = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("ALIGN", (0, 1), (1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 1), (-1, -1), 8.5),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E8F0")),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 1), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 3),
    ]
    pass_bg = colors.HexColor("#DCFCE7")
    fail_bg = colors.HexColor("#FEE2E2")
    skip_bg = colors.HexColor("#E0E7FF")  # blue-tinted = "skipped, not failed"

    for idx, r in enumerate(results, start=1):
        status = r.get("status", "?")
        missing = r.get("missing") or []
        if status == "pass":
            symbol = "✓"
        elif status == "skipped":
            symbol = "⊘"
        else:
            symbol = "✗"
        if status == "skipped":
            missing_text = "skipped — " + (r.get("skip_reason") or "admin-paused or not configured")
        else:
            missing_text = "—" if not missing else "<br/>".join(missing[:3])
            if len(missing) > 3:
                missing_text += f"<br/>+{len(missing) - 3} more"
        data.append([
            str(idx),
            symbol,
            Paragraph(r.get("label") or r.get("id"), cell_style),
            Paragraph(r.get("url") or "", mono_style),
            Paragraph(missing_text, mono_style),
        ])
        if status == "pass":
            bg = pass_bg
            text_color = "#166534"
        elif status == "skipped":
            bg = skip_bg
            text_color = "#3730A3"
        else:
            bg = fail_bg
            text_color = "#991B1B"
        rules.append(("BACKGROUND", (1, idx), (1, idx), bg))
        rules.append(("FONTNAME", (1, idx), (1, idx), "Helvetica-Bold"))
        rules.append(("TEXTCOLOR", (1, idx), (1, idx), colors.HexColor(text_color)))

    tbl = Table(
        data,
        colWidths=[8 * mm, 14 * mm, 60 * mm, 50 * mm, 50 * mm],
        repeatRows=1,
    )
    tbl.setStyle(TableStyle(rules))
    story.append(tbl)

    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "<font color='#64748B' size=8>Run automatically at 03:00 UTC every day. "
        "If any row is red, the storefront has lost a critical element — visit "
        "<a href='/admin/maintenance' color='#475569'>/admin/maintenance</a> "
        "to investigate and re-run.</font>",
        sub_style,
    ))

    doc.build(story)
    return buf.getvalue()

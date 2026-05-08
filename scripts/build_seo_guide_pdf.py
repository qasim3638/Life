"""
Convert /app/memory/seo_guide.md → /app/memory/seo_guide.pdf

Hand-rolled markdown→PDF converter using ReportLab. We don't render
the full markdown spec — just headings, paragraphs, code blocks,
bullet lists, ordered lists, blockquotes, tables, bold, and italic.
That's everything seo_guide.md uses, and the output looks nicer than
generic pandoc styling.

Run: `python /app/scripts/build_seo_guide_pdf.py`
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Preformatted,
    Table, TableStyle, KeepTogether,
)


SRC = Path("/app/memory/seo_guide.md")
DST = Path("/app/memory/seo_guide.pdf")


# ───────── Styles ─────────

def make_styles():
    base = getSampleStyleSheet()
    fuchsia = colors.HexColor("#86198f")
    slate900 = colors.HexColor("#0f172a")
    slate600 = colors.HexColor("#475569")
    slate100 = colors.HexColor("#f1f5f9")
    emerald700 = colors.HexColor("#047857")

    return {
        "title": ParagraphStyle(
            "title", parent=base["Title"], fontSize=24, leading=30,
            textColor=fuchsia, spaceAfter=10, alignment=0,
            fontName="Helvetica-Bold",
        ),
        "subtitle": ParagraphStyle(
            "subtitle", parent=base["Normal"], fontSize=13, leading=18,
            textColor=slate600, spaceAfter=24, fontName="Helvetica",
        ),
        "h1": ParagraphStyle(
            "h1", parent=base["Heading1"], fontSize=20, leading=26,
            textColor=fuchsia, spaceBefore=22, spaceAfter=8,
            fontName="Helvetica-Bold",
            borderWidth=0, borderColor=fuchsia, borderPadding=0,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontSize=15, leading=20,
            textColor=slate900, spaceBefore=14, spaceAfter=6,
            fontName="Helvetica-Bold",
        ),
        "h3": ParagraphStyle(
            "h3", parent=base["Heading3"], fontSize=12, leading=16,
            textColor=emerald700, spaceBefore=10, spaceAfter=4,
            fontName="Helvetica-Bold",
        ),
        "body": ParagraphStyle(
            "body", parent=base["BodyText"], fontSize=10.5, leading=15,
            textColor=slate900, spaceAfter=6, fontName="Helvetica",
            alignment=0,
        ),
        "bullet": ParagraphStyle(
            "bullet", parent=base["BodyText"], fontSize=10.5, leading=14,
            textColor=slate900, spaceAfter=2, fontName="Helvetica",
            leftIndent=18, bulletIndent=4,
        ),
        "blockquote": ParagraphStyle(
            "blockquote", parent=base["BodyText"], fontSize=10.5, leading=14,
            textColor=slate600, spaceAfter=8, fontName="Helvetica-Oblique",
            leftIndent=14, borderColor=fuchsia, borderWidth=0,
            borderPadding=(0, 0, 0, 8),
        ),
        "code_inline": ParagraphStyle(
            "code_inline", parent=base["Normal"], fontName="Courier",
            fontSize=9.5, textColor=slate900, backColor=slate100,
        ),
        "code_block": ParagraphStyle(
            "code_block", parent=base["Code"], fontName="Courier",
            fontSize=9, leading=12, textColor=slate900,
            backColor=slate100, leftIndent=6, rightIndent=6,
            spaceBefore=6, spaceAfter=8, borderPadding=8,
        ),
        "footer_meta": ParagraphStyle(
            "footer", parent=base["Normal"], fontSize=8, leading=10,
            textColor=slate600, fontName="Helvetica-Oblique",
        ),
    }


# ───────── Inline markdown → HTML mini-renderer ─────────

INLINE_CODE_RE = re.compile(r"`([^`]+)`")
BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
ITALIC_RE = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def _esc(t: str) -> str:
    """Escape characters that would break ReportLab's mini-HTML
    (it's stricter than browser HTML — & < > all need escaping)."""
    return (t.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;"))


def render_inline(text: str) -> str:
    """Convert inline markdown (bold, italic, code, links) to the
    subset of HTML ReportLab understands.

    Run inline-code FIRST so we can stash `<code>` chunks before the
    bold/italic regexes mangle backticks inside them.
    """
    text = _esc(text)
    # Backticks → courier code spans (placeholder swap so the bold
    # regex can't see them)
    placeholders: dict[str, str] = {}

    def stash_code(match: re.Match) -> str:
        key = f"§§§CODE{len(placeholders)}§§§"
        placeholders[key] = (
            f'<font face="Courier" size="9.5" backColor="#f1f5f9">'
            f'{match.group(1)}</font>'
        )
        return key

    text = INLINE_CODE_RE.sub(stash_code, text)
    text = BOLD_RE.sub(r"<b>\1</b>", text)
    text = ITALIC_RE.sub(r"<i>\1</i>", text)
    # Links — render visible text + colour, no real anchor since
    # ReportLab's link rendering is fragile in tables
    text = LINK_RE.sub(
        r'<font color="#6d28d9"><u>\1</u></font>', text,
    )
    for k, v in placeholders.items():
        text = text.replace(k, v)
    return text


# ───────── Block parser ─────────

def parse_blocks(md: str) -> list[tuple[str, object]]:
    """Returns a list of (kind, payload) tuples in document order.
    Kinds: h1 h2 h3 p ul ol code blockquote table hr."""
    blocks: list[tuple[str, object]] = []
    lines = md.splitlines()
    i = 0
    n = len(lines)

    def is_table_row(s: str) -> bool:
        return s.strip().startswith("|") and s.strip().endswith("|") and "|" in s.strip()[1:-1]

    while i < n:
        line = lines[i]
        stripped = line.rstrip()

        # Blank line → skip
        if not stripped.strip():
            i += 1
            continue

        # Horizontal rule
        if re.fullmatch(r"-{3,}|_{3,}|\*{3,}", stripped.strip()):
            blocks.append(("hr", None))
            i += 1
            continue

        # Heading
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            level = len(m.group(1))
            kind = f"h{min(level, 3)}"
            blocks.append((kind, m.group(2).strip()))
            i += 1
            continue

        # Code fence
        if stripped.startswith("```"):
            lang = stripped[3:].strip() or None
            i += 1
            buf: list[str] = []
            while i < n and not lines[i].rstrip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1  # closing fence
            blocks.append(("code", {"lang": lang, "text": "\n".join(buf)}))
            continue

        # Blockquote
        if stripped.startswith("> "):
            buf: list[str] = []
            while i < n and lines[i].rstrip().startswith("> "):
                buf.append(lines[i].rstrip()[2:])
                i += 1
            blocks.append(("blockquote", " ".join(buf)))
            continue

        # Table
        if is_table_row(stripped) and i + 1 < n and is_table_row(lines[i + 1]):
            tbuf: list[str] = []
            while i < n and is_table_row(lines[i].rstrip()):
                tbuf.append(lines[i].rstrip())
                i += 1
            # parse: first row=header, second row=separator, rest=body
            rows: list[list[str]] = []
            for j, tline in enumerate(tbuf):
                if j == 1:  # separator row like |---|---|
                    if all(set(c.strip()) <= set("-: ") for c in tline.strip("|").split("|")):
                        continue
                cells = [c.strip() for c in tline.strip("|").split("|")]
                rows.append(cells)
            blocks.append(("table", rows))
            continue

        # Unordered list
        if re.match(r"^[-*]\s+", stripped):
            items: list[str] = []
            while i < n and re.match(r"^[-*]\s+", lines[i].rstrip()):
                items.append(re.sub(r"^[-*]\s+", "", lines[i].rstrip()))
                i += 1
            blocks.append(("ul", items))
            continue

        # Ordered list
        if re.match(r"^\d+\.\s+", stripped):
            items: list[str] = []
            while i < n and re.match(r"^\d+\.\s+", lines[i].rstrip()):
                items.append(re.sub(r"^\d+\.\s+", "", lines[i].rstrip()))
                i += 1
            blocks.append(("ol", items))
            continue

        # Default: paragraph (collapse consecutive non-empty non-special lines)
        start_i = i
        buf: list[str] = []
        while i < n and lines[i].strip() and not (
            lines[i].lstrip().startswith(("#", "-", "*", "> ", "```"))
            or re.match(r"^\d+\.\s+", lines[i].lstrip())
            or is_table_row(lines[i].strip())
        ):
            buf.append(lines[i].rstrip())
            i += 1
        if buf:
            blocks.append(("p", " ".join(buf)))
        # Safety: if we made zero progress on this iteration, force-
        # advance so we never infinite-loop. (Catches edge cases like
        # a stray `|` on a line by itself.)
        if i == start_i:
            i += 1

    return blocks


# ───────── Build PDF ─────────

def build_pdf():
    md = SRC.read_text(encoding="utf-8")
    s = make_styles()
    blocks = parse_blocks(md)

    doc = SimpleDocTemplate(
        str(DST), pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
        title="Tile Station SEO Guide",
        author="Tile Station Engineering",
    )
    story: list = []

    for kind, payload in blocks:
        if kind == "h1":
            # Page break before each top-level heading except the first one
            if story and any(isinstance(b, Paragraph) for b in story):
                story.append(PageBreak())
            story.append(Paragraph(render_inline(str(payload)), s["h1"]))
        elif kind == "h2":
            story.append(Paragraph(render_inline(str(payload)), s["h2"]))
        elif kind == "h3":
            story.append(Paragraph(render_inline(str(payload)), s["h3"]))
        elif kind == "p":
            text = str(payload)
            # First two paragraphs of the doc are the subtitle block
            if len(story) <= 2:
                story.append(Paragraph(render_inline(text), s["subtitle"]))
            else:
                story.append(Paragraph(render_inline(text), s["body"]))
        elif kind == "blockquote":
            story.append(Paragraph(render_inline(str(payload)), s["blockquote"]))
        elif kind == "code":
            txt = payload["text"] if isinstance(payload, dict) else str(payload)
            story.append(Preformatted(txt, s["code_block"]))
        elif kind == "ul":
            for it in payload:  # type: ignore[union-attr]
                story.append(Paragraph(
                    f"• {render_inline(it)}", s["bullet"],
                ))
        elif kind == "ol":
            for idx, it in enumerate(payload, 1):  # type: ignore[union-attr]
                story.append(Paragraph(
                    f"{idx}. {render_inline(it)}", s["bullet"],
                ))
        elif kind == "table":
            rows = payload  # type: ignore[assignment]
            if not rows:
                continue
            data = [
                [Paragraph(render_inline(c), s["body"]) for c in row]
                for row in rows
            ]
            tbl = Table(data, repeatRows=1, hAlign="LEFT", colWidths=None)
            tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f5f3ff")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#4c1d95")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            story.append(KeepTogether([Spacer(1, 4), tbl, Spacer(1, 8)]))
        elif kind == "hr":
            story.append(Spacer(1, 8))

    # Footer on every page
    def on_page(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica-Oblique", 7.5)
        canvas.setFillColor(colors.HexColor("#94a3b8"))
        canvas.drawString(2 * cm, 1.2 * cm, "Tile Station — Internal SEO Guide · May 2026")
        canvas.drawRightString(
            doc_.pagesize[0] - 2 * cm, 1.2 * cm,
            f"Page {doc_.page}",
        )
        canvas.restoreState()

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return DST


if __name__ == "__main__":
    out = build_pdf()
    print(f"Wrote {out} ({out.stat().st_size:,} bytes)")

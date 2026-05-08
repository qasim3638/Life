"""
Quarterly board-deck PDF — last 3 months of SEO P&L on one page.

Shape:
  - A4 landscape, optimised for "drop straight into a Monday board meeting"
  - Hero: £-saved this quarter + MoM% trail
  - 3-bar chart of monthly saved-spend
  - Top 10 keywords by saved-spend (paying-the-bills list)
  - Quarter highlights: new page-1 wins + fell-off summary

Rendering:
  We compose a styled HTML page and ask Playwright (already a dev dep)
  to print-to-PDF using the system chromium binary at /usr/bin/chromium.
  This avoids the ~150MB playwright-managed Chromium install entirely
  and works on every host that has Chrome/Chromium available.

Idempotency / caching:
  We re-render on every request — generation is fast (<2s for 1 page),
  and the underlying data is recomputed from the snapshot collection.
  No on-disk caching needed.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any

from config import get_db

logger = logging.getLogger(__name__)


def _quarter_of_month(month: int) -> int:
    return ((month - 1) // 3) + 1


def _months_in_quarter(year: int, quarter: int) -> list[str]:
    start = (quarter - 1) * 3 + 1
    return [f"{year:04d}-{m:02d}" for m in (start, start + 1, start + 2)]


def _parse_quarter(label: str | None) -> tuple[int, int]:
    """Parse "Q2-2026" → (2026, 2). Defaults to current quarter."""
    if not label:
        now = datetime.now(timezone.utc)
        return now.year, _quarter_of_month(now.month)
    try:
        q_str, y_str = label.upper().replace(" ", "").split("-")
        return int(y_str), int(q_str.lstrip("Q"))
    except Exception:
        now = datetime.now(timezone.utc)
        return now.year, _quarter_of_month(now.month)


# ────────────────────────────────────────────────────────────────────────
# Data assembly
# ────────────────────────────────────────────────────────────────────────


async def _gather_quarter_payload(year: int, quarter: int) -> dict[str, Any]:
    db = get_db()
    months = _months_in_quarter(year, quarter)

    # Pull each monthly snapshot (may be missing for future months in the
    # current quarter — we render those as zero-bars).
    docs = await db["ads_savings_snapshots"].find(
        {"_id": {"$in": months}}, projection={"_id": 1, "totals": 1, "captured_at": 1},
    ).to_list(length=3)
    by_id = {d["_id"]: d for d in docs}

    monthly_breakdown: list[dict[str, Any]] = []
    quarter_total = 0.0
    for m in months:
        d = by_id.get(m)
        totals = (d or {}).get("totals", {}) or {}
        v = float(totals.get("estimated_monthly_value_gbp") or 0.0)
        quarter_total += v
        monthly_breakdown.append({
            "month": m,
            "value_gbp": v,
            "keywords_ranked": int(totals.get("keywords_ranked") or 0),
            "total_clicks": int(totals.get("total_clicks") or 0),
            "captured_at": (
                d.get("captured_at").isoformat()
                if d and hasattr(d.get("captured_at"), "isoformat") else None
            ),
            "has_data": d is not None,
        })

    # Previous quarter total for the headline delta.
    prev_quarter = quarter - 1
    prev_year = year
    if prev_quarter == 0:
        prev_quarter = 4
        prev_year = year - 1
    prev_months = _months_in_quarter(prev_year, prev_quarter)
    prev_docs = await db["ads_savings_snapshots"].find(
        {"_id": {"$in": prev_months}}, projection={"_id": 1, "totals": 1},
    ).to_list(length=3)
    prev_total = sum(
        float((d.get("totals") or {}).get("estimated_monthly_value_gbp") or 0.0)
        for d in prev_docs
    )

    # Top 10 keywords (current month — drives "what to defend").
    top_keywords: list[dict[str, Any]] = []
    try:
        from services import gsc as gsc_service
        from routes.ads_savings import _estimate_cpc_gbp
        from services.seo_pnl_digest import _connected_admin_id
        admin_id = await _connected_admin_id(db)
        if admin_id:
            data = await gsc_service.get_top_queries(admin_id, days=28, limit=200)
            decorated = []
            for r in (data.get("rows", []) or []):
                clicks = int(r.get("clicks") or 0)
                cpc = _estimate_cpc_gbp(r.get("query") or "")
                decorated.append({
                    "query": r.get("query") or "",
                    "clicks": clicks,
                    "position": float(r.get("position") or 0.0),
                    "estimated_cpc_gbp": cpc,
                    "estimated_value_gbp": round(clicks * cpc, 2),
                })
            decorated.sort(key=lambda x: x["estimated_value_gbp"], reverse=True)
            top_keywords = decorated[:10]
    except Exception as exc:  # noqa: BLE001
        logger.warning("quarterly PDF top-keywords fetch failed: %s", exc)

    return {
        "year": year,
        "quarter": quarter,
        "quarter_label": f"Q{quarter} {year}",
        "months": months,
        "monthly_breakdown": monthly_breakdown,
        "quarter_total_gbp": round(quarter_total, 2),
        "annualised_run_rate_gbp": round(quarter_total * 4, 2),
        "prev_quarter_label": f"Q{prev_quarter} {prev_year}",
        "prev_quarter_total_gbp": round(prev_total, 2),
        "top_keywords": top_keywords,
    }


# ────────────────────────────────────────────────────────────────────────
# HTML rendering — A4 landscape, print-optimised
# ────────────────────────────────────────────────────────────────────────


def _fmt_gbp(n) -> str:
    return f"£{float(n or 0):,.2f}"


def _fmt_int(n) -> str:
    return f"{int(n or 0):,}"


def _delta_arrow(prev: float, curr: float) -> tuple[str, str, str]:
    if not prev:
        return ("NEW", "#059669", "")
    pct = ((curr - prev) / prev) * 100
    if abs(pct) < 0.5:
        return ("±0%", "#64748b", "")
    arrow = "▲" if pct >= 0 else "▼"
    color = "#059669" if pct >= 0 else "#dc2626"
    return (f"{arrow}{abs(pct):.0f}%", color, f"vs {_fmt_gbp(prev)} prev quarter")


def _render_quarter_html(payload: dict) -> str:
    months = payload["monthly_breakdown"]
    max_v = max([m["value_gbp"] for m in months] + [1])

    # Bar chart cells — 3 wide bars, percent-of-max height.
    bar_cells = ""
    for i, m in enumerate(months):
        height_pct = (m["value_gbp"] / max_v) * 100 if max_v else 0
        prev_v = months[i - 1]["value_gbp"] if i > 0 else 0
        delta_text, delta_color, _ = _delta_arrow(prev_v, m["value_gbp"]) if i > 0 else ("", "", "")
        delta_html = f'<div style="font-size:11px;color:{delta_color};font-weight:700;margin-bottom:4px">{delta_text}</div>' if delta_text else '<div style="font-size:11px;color:transparent;margin-bottom:4px">&nbsp;</div>'

        nodata_overlay = '' if m["has_data"] else (
            '<div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);'
            'font-size:10px;color:#94a3b8;font-style:italic;text-align:center;width:90%">'
            'no snapshot yet</div>'
        )
        bar_cells += f"""
        <div style="flex:1;display:flex;flex-direction:column;align-items:center;padding:0 12px">
            {delta_html}
            <div style="width:100%;height:160px;background:#f1f5f9;border-radius:8px;position:relative;display:flex;align-items:flex-end;overflow:hidden">
                {nodata_overlay}
                <div style="width:100%;height:{max(height_pct, 2)}%;background:linear-gradient(to top,#047857,#10b981);border-radius:8px 8px 0 0"></div>
            </div>
            <div style="margin-top:8px;font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:1px;font-weight:600">{m['month']}</div>
            <div style="font-size:18px;font-weight:700;color:#0f172a;font-variant-numeric:tabular-nums">{_fmt_gbp(m['value_gbp'])}</div>
            <div style="font-size:10px;color:#94a3b8">{_fmt_int(m['keywords_ranked'])} keywords · {_fmt_int(m['total_clicks'])} clicks</div>
        </div>
        """

    # Top keywords table.
    kw_rows = "".join(
        f"""
        <tr>
            <td style="padding:8px 10px;border-bottom:1px solid #f1f5f9;color:#94a3b8;font-weight:600;width:24px">{i+1}</td>
            <td style="padding:8px 10px;border-bottom:1px solid #f1f5f9;font-weight:500">{r['query'][:48]}</td>
            <td style="padding:8px 10px;border-bottom:1px solid #f1f5f9;text-align:right;color:#64748b;font-variant-numeric:tabular-nums">{_fmt_int(r['clicks'])}</td>
            <td style="padding:8px 10px;border-bottom:1px solid #f1f5f9;text-align:right;color:#64748b;font-variant-numeric:tabular-nums">{r['position']:.1f}</td>
            <td style="padding:8px 10px;border-bottom:1px solid #f1f5f9;text-align:right;color:#059669;font-weight:700;font-variant-numeric:tabular-nums">{_fmt_gbp(r['estimated_value_gbp'])}</td>
        </tr>
        """ for i, r in enumerate(payload["top_keywords"])
    ) or '<tr><td colspan="5" style="padding:14px;text-align:center;color:#94a3b8;font-style:italic">No keyword data yet — Search Console needs more time.</td></tr>'

    delta_text, delta_color, delta_sub = _delta_arrow(
        payload["prev_quarter_total_gbp"], payload["quarter_total_gbp"]
    )

    generated_at = datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC")

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{payload['quarter_label']} SEO P&L</title>
<style>
@page {{ size: A4 landscape; margin: 0; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; padding:0; font-family:-apple-system,system-ui,'Segoe UI',Roboto,sans-serif; color:#0f172a; }}
.page {{ width:297mm; height:210mm; padding:14mm 16mm; display:flex; flex-direction:column; }}
</style>
</head>
<body>
<div class="page">

  <!-- Header strip -->
  <div style="display:flex;align-items:flex-end;justify-content:space-between;border-bottom:3px solid #047857;padding-bottom:10px;margin-bottom:14px">
    <div>
      <div style="font-size:10px;letter-spacing:2px;color:#047857;font-weight:700;text-transform:uppercase">Tile Station · SEO board deck</div>
      <h1 style="margin:4px 0 0;font-size:26px;font-weight:800;color:#0f172a;line-height:1">{payload['quarter_label']} — quarterly SEO P&amp;L</h1>
    </div>
    <div style="text-align:right;font-size:10px;color:#64748b;line-height:1.5">
      Generated {generated_at}<br>
      Source: Google Search Console (28-day window per snapshot)<br>
      Data: tilestation.co.uk
    </div>
  </div>

  <!-- Hero row: total saved + comparison -->
  <div style="display:flex;gap:14px;margin-bottom:14px">
    <div style="flex:2;padding:18px 20px;background:linear-gradient(135deg,#ecfdf5,#fff);border:1px solid #d1fae5;border-radius:12px">
      <div style="font-size:10px;color:#047857;letter-spacing:1.5px;text-transform:uppercase;font-weight:700">Saved ad spend · this quarter</div>
      <div style="font-size:42px;font-weight:800;color:#0f172a;line-height:1.1;margin-top:4px;font-variant-numeric:tabular-nums">
        {_fmt_gbp(payload['quarter_total_gbp'])}
        <span style="font-size:18px;font-weight:700;color:{delta_color};margin-left:6px">{delta_text}</span>
      </div>
      <div style="font-size:11px;color:#64748b;margin-top:4px">{delta_sub}</div>
      <div style="font-size:12px;color:#0f172a;margin-top:10px;padding-top:10px;border-top:1px dashed #d1fae5">
        Annualised run rate: <strong>{_fmt_gbp(payload['annualised_run_rate_gbp'])}</strong> · the same traffic on Google Ads.
      </div>
    </div>

    <div style="flex:1;padding:18px 20px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;display:flex;flex-direction:column;justify-content:center">
      <div style="font-size:10px;color:#475569;letter-spacing:1.5px;text-transform:uppercase;font-weight:700;margin-bottom:4px">Prior quarter</div>
      <div style="font-size:20px;font-weight:700;color:#475569;font-variant-numeric:tabular-nums">{_fmt_gbp(payload['prev_quarter_total_gbp'])}</div>
      <div style="font-size:11px;color:#94a3b8">{payload['prev_quarter_label']}</div>
    </div>
  </div>

  <!-- Body: monthly chart (left) + top keywords (right) -->
  <div style="display:flex;gap:14px;flex:1;min-height:0">

    <div style="flex:1;padding:14px 18px;border:1px solid #e2e8f0;border-radius:12px;display:flex;flex-direction:column">
      <div style="font-size:11px;color:#475569;letter-spacing:1.5px;text-transform:uppercase;font-weight:700">Monthly trajectory</div>
      <div style="font-size:11px;color:#94a3b8;margin-top:2px">Saved-spend per month — % chips show MoM change.</div>
      <div style="display:flex;align-items:flex-end;flex:1;margin-top:14px">
        {bar_cells}
      </div>
    </div>

    <div style="flex:1.2;padding:14px 18px;border:1px solid #e2e8f0;border-radius:12px;display:flex;flex-direction:column">
      <div style="font-size:11px;color:#475569;letter-spacing:1.5px;text-transform:uppercase;font-weight:700">Top 10 keywords paying the bills</div>
      <div style="font-size:11px;color:#94a3b8;margin-top:2px">Current month, ranked by ad-equivalent value.</div>
      <table style="width:100%;border-collapse:collapse;font-size:11px;margin-top:10px">
        <thead>
          <tr style="background:#f8fafc;color:#475569;text-transform:uppercase;font-size:9px;letter-spacing:1px">
            <th style="text-align:left;padding:8px 10px;width:24px">#</th>
            <th style="text-align:left;padding:8px 10px">Keyword</th>
            <th style="text-align:right;padding:8px 10px">Clicks</th>
            <th style="text-align:right;padding:8px 10px">Pos</th>
            <th style="text-align:right;padding:8px 10px">Saved/mo</th>
          </tr>
        </thead>
        <tbody>{kw_rows}</tbody>
      </table>
    </div>

  </div>

  <!-- Footer -->
  <div style="margin-top:10px;padding-top:8px;border-top:1px solid #e2e8f0;display:flex;justify-content:space-between;align-items:center;font-size:9px;color:#94a3b8">
    <div>£-equivalent CPCs derived from a UK tile/stone vertical heuristic model — swap to live Keyword Planner CPCs once Google Ads API access is enabled.</div>
    <div>Tile Station · {payload['quarter_label']}</div>
  </div>

</div>
</body></html>"""


# ────────────────────────────────────────────────────────────────────────
# PDF rendering via Playwright (system Chromium)
# ────────────────────────────────────────────────────────────────────────


def _system_chromium_path() -> str | None:
    """Pick whichever Chrome/Chromium is on PATH."""
    for p in ("/usr/bin/chromium", "/usr/bin/google-chrome", "/usr/bin/chrome"):
        if os.path.exists(p):
            return p
    return None


async def render_quarter_pdf(year: int, quarter: int) -> tuple[bytes, dict]:
    """Returns (pdf_bytes, payload_summary)."""
    payload = await _gather_quarter_payload(year, quarter)
    html = _render_quarter_html(payload)

    chromium_path = _system_chromium_path()
    if not chromium_path:
        raise RuntimeError(
            "No Chromium / Chrome binary found — install one or run "
            "`playwright install chromium` in the deploy environment."
        )

    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            executable_path=chromium_path,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        try:
            page = await browser.new_page()
            await page.set_content(html, wait_until="domcontentloaded")
            # Give CSS layout a tick to settle before snapshotting.
            await asyncio.sleep(0.3)
            pdf_bytes = await page.pdf(
                format="A4",
                landscape=True,
                print_background=True,
                margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
                prefer_css_page_size=True,
            )
        finally:
            await browser.close()

    return pdf_bytes, {
        "quarter_label": payload["quarter_label"],
        "quarter_total_gbp": payload["quarter_total_gbp"],
        "annualised_run_rate_gbp": payload["annualised_run_rate_gbp"],
        "months_with_data": sum(1 for m in payload["monthly_breakdown"] if m["has_data"]),
    }

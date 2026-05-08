## 2026-05-02 — 🟢 Conversion funnel card + SEO metric explainer tooltips

### A. Conversion funnel on admin home (`/admin`)
First operational analytics card on the admin home — sessions → product views → checkout → paid orders, sliced by traffic source.

**Backend** (`services/conversion_funnel.py` + `routes/conversion.py`):
- Single endpoint `GET /api/admin/conversion/funnel?days=N` (7 / 28 / 90 windows)
- Aggregates from existing collections: `page_views` for sessions/product/checkout stages, `shop_orders` for paid + revenue total. No new event tracking required.
- Source classifier groups referrers into `organic / social / email / direct / other` via regex against the URL hostname
- Conversion ratios suppress when denominator < 5 (returns `null`) so the UI never shows misleading "100%" off a single visitor
- Stage detection via path regex: `/tiles/*` or `/shop/(product|collection)/*` → product viewer; `/checkout*` or `/shop/checkout*` → checkout reached
- Paid orders matched on `payment_status==paid` OR `status in [completed/paid/shipped/confirmed]`

**Frontend** (`pages/admin/ConversionFunnelCard.jsx`):
- 4-stage horizontal funnel bars (no chart library — pure CSS for sub-1KB cost)
- Per-source breakdown panel with mini-progress-bars + share % + click-to-checkout %
- 4 conversion rate chips (visitor→product / product→checkout / checkout→paid / visitor→paid with emerald accent on the bottom-line)
- Window picker (Last 7/28/90 days)
- Mounted at top of `pages/admin/Dashboard.js` so it loads first when an admin opens `/admin`

**Verified live:** `GET /api/admin/conversion/funnel?days=28` returned 7 sessions (4 organic, 3 direct), 1 product viewer, 0 checkouts, 14.29% visitor→product rate. UI rendered perfectly with all data points + correctly suppressed ratios for sub-5 denominators.

### B. SEO metric explainer tooltips
User asked: *"add an easy to understand detailed box on each SEO value, for example 'CTR' explain in plain English what it does, what it is, benefits etc — hover over them and a box should open."*

**New shared component** (`components/admin/MetricInfoTooltip.jsx`):
- ⓘ button next to each metric label / table column header
- Tooltip uses Radix-UI's `Tooltip` (already in shadcn/ui at `components/ui/tooltip.jsx`) for accessibility (keyboard focus, ARIA labels, collision-aware positioning)
- Dark slate-900 card with structured copy: **title** · **what it is** · **why it matters** (amber accent) · **a good number** (emerald accent) · **example** (italic footer)
- Single `SEO_EXPLAINERS` object holds all copy so non-developers can edit without touching JSX

**11 explainers shipped:**
1. `clicks` — what clicks are + why each = a chance at revenue + benchmark + worked example
2. `impressions` — visibility metric + watch trends not absolute numbers
3. `ctr` — formula + why title quality matters more than position alone + position-bench averages
4. `avg_position` — how it works + why moving from #11 to #9 doubles clicks
5. `queries_tracked` — keyword breadth signal + drop diagnosis
6. `query_row` — search-query mining for product/FAQ ideas
7. `page_row` — landing-page winners deserve doubling-down
8. `position_row` — page-2 (positions 11-20) is the cheapest win
9. `sitemap` — what it is + how auto-update accelerates discovery
10. `url_inspect_verdict` — PASS/NEUTRAL/FAIL/PARTIAL meanings + cost of FAIL
11. `canonical` — duplicate-content prevention + mismatch warning interpretation

**Mounted on:**
- `GscAnalyticsPanel.jsx` — every metric card label + every table column header (top queries + city pages)
- `GscSitemapCard.jsx` — Sitemap submission heading + Verdict + Google canonical fields

**Verified live:** Hovered the ⓘ next to CLICKS metric on `/admin/seo`, tooltip rendered with all 5 sections (title, what, why, good, example). Same icon appears on every metric and column.

### Files touched
- `backend/services/conversion_funnel.py` — new
- `backend/routes/conversion.py` — new
- `backend/routes/__init__.py` — wires conversion_router
- `frontend/src/pages/admin/ConversionFunnelCard.jsx` — new
- `frontend/src/pages/admin/Dashboard.js` — mounts ConversionFunnelCard at top
- `frontend/src/components/admin/MetricInfoTooltip.jsx` — new
- `frontend/src/pages/admin/GscAnalyticsPanel.jsx` — wraps metrics + table headers
- `frontend/src/pages/admin/GscSitemapCard.jsx` — wraps section headings + inspector fields

### Production deploy
Save-to-GitHub → Railway redeploys → both features go live. No new env vars or migrations required.

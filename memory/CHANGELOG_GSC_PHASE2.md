## 2026-05-02 — 🟢 GSC Phase 2 LIVE: Search Analytics dashboard

Phase 2 ships the in-app dashboard that consumes the OAuth refresh token saved in Phase 1.

### Backend (`services/gsc.py` + `routes/gsc_auth.py`)
Five new GET endpoints under `/api/admin/gsc/analytics/*`:
- `overview?days=N` — single aggregate row (clicks/impressions/CTR/avg-position) for the 4 metric cards
- `top-queries?days=N&limit=K` — ranked queries
- `top-pages?days=N&limit=K` — ranked landing pages
- `page-queries?page=URL&days=N` — drill-down (queries that surfaced a specific page)
- `city-pages?days=N` — pre-filtered to URLs containing `/tiles/`, sorted by clicks desc

Implementation notes:
- Always queries the **Domain property** `sc-domain:tilestation.co.uk` (covers www + apex + http + https + future subdomains)
- Window helper accounts for GSC's ~2-day data delay so empty days at the head of the window don't dilute the totals shown
- Results normalised into `{query|page, clicks, impressions, ctr, position}` — the FE gets a uniform shape across endpoints
- Auth: re-uses Phase 1's `get_credentials_for_admin(...)` which auto-refreshes expired access tokens and stamps `last_used_at`

### Frontend (`pages/admin/GscAnalyticsPanel.jsx`)
New component mounted under `GscConnectCard` on `/admin/seo`, gated on `connected={true}` so it never spends an API call when no token exists.
- Header with date-range pill (7/28/90 days) + loading spinner
- 4 metric cards (Clicks · Impressions · Avg Position · Queries Tracked)
- Top queries table (top 25)
- City landing pages table — every `/tiles/` URL with traffic, sorted by clicks
- Friendly empty-state hourglass card when there are 0 rows yet
- Bubble-up: `GscConnectCard` now accepts `onConnectionChange` callback so the parent can mount/unmount the panel without a second status round-trip

### Verified live (preview env)
Real production data already flowing for the connected GSC account:
- **15 clicks · 812 impressions · 1.85% CTR · avg position 29.7** (last 28 days)
- Top queries include `tile station tonbridge` (40% CTR, pos #1), `tile shops near me`, `tile showrooms near me`, `spanish floor tiles`
- City landing pages: 0 rows (Googlebot hasn't crawled enough of the AI-generated `/tiles/<city>` set yet — will appear automatically as crawl coverage grows)

### Files touched
- `backend/services/gsc.py` — 5 new helpers (`_query`, `_date_range`, `get_overview`, `get_top_queries`, `get_top_pages`, `get_page_queries`, `get_city_pages_summary`)
- `backend/routes/gsc_auth.py` — 5 new endpoints under `/analytics/*`
- `frontend/src/pages/admin/GscAnalyticsPanel.jsx` (new, ~280 LOC)
- `frontend/src/pages/admin/GscConnectCard.jsx` — `onConnectionChange` prop
- `frontend/src/pages/admin/SeoCommandCentre.jsx` — wires panel below the connect card

### Phase 3 + 4 still pending
- Phase 3: URL Inspection API + auto-submit `/sitemap.xml` on every deploy + indexed-vs-not-indexed coverage report
- Phase 4: Weekly digest email (Resend) + CTR-drop alerts (Telegram)

### Production deploy still required
The Phase 2 endpoints are only on the preview backend right now. To ship to production:
1. Click **Save to GitHub** in Emergent chat → Railway auto-redeploys both services
2. No new env vars needed (Phase 2 reuses Phase 1's `GOOGLE_CLIENT_ID`/`_SECRET`/redirect URI already on Railway)
3. Hard-refresh `tilestation.co.uk/admin/seo` and the dashboard appears with the same live data

## 2026-05-02 — 🟢 GSC Phase 3 LIVE: Sitemaps auto-submit + URL inspector

Phase 3 closes the second-biggest SEO funnel gap after Phase 1 OAuth: telling Google *when* the sitemap has changed instead of waiting for it to discover the change naturally (which can take weeks).

### Backend (`services/gsc.py` + `routes/gsc_auth.py`)
Five new endpoints + a background hook:
- `GET /api/admin/gsc/sitemaps` — list every sitemap registered against the property with last-submitted/last-fetched timestamps + error/warning counts
- `POST /api/admin/gsc/sitemaps/submit` — submit our public `https://tilestation.co.uk/sitemap.xml` (or any feedpath query arg)
- `DELETE /api/admin/gsc/sitemaps?feedpath=…` — un-register a stale sitemap (we have a `http://tilestation.co.uk/...` from 2019 still in the list)
- `GET /api/admin/gsc/inspect?url=…` — URL Inspection API single-URL drilldown (verdict, coverage state, last crawl time, canonical mismatch, mobile usability) with 6h Mongo cache to respect the 2k/day quota
- `services.gsc.maybe_auto_submit_sitemap(reason=…)` — internal helper that picks the most-recently-active connected admin and submits, throttled to once per 12 hours.

**Auto-submit hooks wired in two places:**
1. **Backend startup** (`server.py @app.on_event('startup')`) — kicks off in background asyncio task, never blocks boot, gracefully no-ops when GSC isn't connected yet.
2. **City-pages auto-drainer** (`services/city_pages_autogen.py`) — fires after every drain run that auto-approved at least one new page. The 12h throttle prevents spamming Google when several drain runs happen the same day.

### Frontend (`pages/admin/GscSitemapCard.jsx`)
New card mounted under `GscAnalyticsPanel` on `/admin/seo`. Two sections:
- **Sitemap submission table** — each sitemap registered with Google, with last submitted/fetched dates, error/warning counts, status pill (OK / Pending / Errors). "Resubmit to Google" button at the top-right manually re-triggers a submit.
- **URL inspector** — text input + Inspect button. Returns verdict (PASS / NEUTRAL / FAIL / PARTIAL with colour-coded pill), coverage state, indexing state, robots.txt state, page-fetch state, mobile usability, last crawl time, Google's canonical, your canonical (with mismatch warning), and a deep-link to open the full report in Search Console.

### Verified live (preview env)
- Backend startup auto-submitted at 12:30:02 — Google fetched the sitemap 2 seconds later (12:30:04), 0 errors, 0 warnings, **396 URLs submitted**
- 3 sitemaps now registered against `sc-domain:tilestation.co.uk`:
  - `https://tilestation.co.uk/sitemap.xml` — newly submitted, OK, 396 URLs
  - `https://www.tilestation.co.uk/sitemap.xml` — historical (Jul 2025), OK, sitemap-index
  - `http://tilestation.co.uk/sitemap.xml` — pending since Jul 2019 (legacy ghost — admin can DELETE via the API)

### Files touched
- `backend/services/gsc.py` — 4 helpers (`list_sitemaps`, `submit_sitemap`, `delete_sitemap`, `inspect_url`) + `maybe_auto_submit_sitemap` background helper + `_pick_connected_admin`
- `backend/routes/gsc_auth.py` — 4 new endpoints
- `backend/server.py` — startup hook for `_gsc_kickstart()` running auto-submit in background
- `backend/services/city_pages_autogen.py` — fires `maybe_auto_submit_sitemap` after auto-approve runs
- `frontend/src/pages/admin/GscSitemapCard.jsx` (new, ~270 LOC)
- `frontend/src/pages/admin/SeoCommandCentre.jsx` — mounts the new card

### Phase 4 still pending
- Weekly digest email (Resend) — top queries that gained, top queries that dropped, new pages getting impressions, sitemap errors → admin inbox every Mon
- CTR-drop alerts (Telegram) — admin-defined threshold; e.g. fire when a city page's CTR drops 50%+ vs its 28-day rolling baseline

### Production deploy
Push to GitHub via Save-to-GitHub → Railway redeploys → no new env vars needed → on first boot the auto-submit will fire on the production backend too.

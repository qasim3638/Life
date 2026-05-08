## 2026-05-02 — 🟢 30-day uptime sparkline + GSC daily digest (was weekly)

### Two changes shipped together:

#### A. GSC digest cadence flipped weekly → daily
User asked for daily insights, not weekly. Three changes:
- Cron trigger: removed `day_of_week="mon"` so the job fires every day at 09:30 Europe/London.
- Idempotency key changed from ISO-week (`%G-W%V`) to ISO-date (`%Y-%m-%d`) so the digest still de-dupes on multi-fires within a single day but won't suppress later days.
- Email subject + footer copy updated: "SEO daily" instead of "SEO weekly", "Cron: daily" instead of "Cron: every Monday".
- Frontend description on the GscSitemapCard digest pill updated to say "Every day at 09:30 UK time".

#### B. 30-day uptime sparkline widget on /admin/maintenance
Operational reliability win — admin no longer has to dig through logs to know if anything's been flapping.

**Backend** (`services/uptime.py` ~280 LOC + `routes/uptime.py`):
- 5 probes per tick: storefront (public sitemap URL), backend (`/api/health/uptime` via internal `localhost:8001`), database (Mongo `ping`), Stripe (`/v1/balance`), Telegram (`getMe`)
- Probes run in parallel via `asyncio.gather` to cap each tick at the slowest probe
- `_probe_stripe()` and `_probe_telegram()` no-op when no API key is configured (rather than fake outages on stage envs)
- Persists one row per service per tick into `uptime_probes` collection. Lazy-GC older than 60 days every 6th tick.
- New endpoints: `GET /api/admin/uptime/rollup?days=30` (per-service per-day uptime % + summary), `GET /api/admin/uptime/incidents?limit=20`, `POST /api/admin/uptime/probe-now` (manual trigger)
- 30-day rollup uses Mongo aggregation pipeline (group-by service+day, divide ok/total) for O(1) reads even at 200k+ probe rows

**Scheduler** (`services/scheduler.py`):
- New `uptime_probe_5min` job (IntervalTrigger every 5 min) registered at startup
- First run scheduled 10 seconds after boot so it doesn't pile on the cold-start request burst

**Frontend** (`pages/admin/UptimeSparklineWidget.jsx` ~200 LOC):
- One row per service: icon + label + current/avg uptime % + 31-cell SVG sparkline + ALL GOOD/incidents pill
- Cell colour ladder: ≥99.9% green · 99-99.9% amber · <99% red · null grey
- Hover tooltip on each cell shows date + exact uptime %
- "Probe now" button to fire a manual one-off without waiting 5 min
- Mounted at the top of `/admin/maintenance` above the existing tasks list

**Verified live (preview env):**
- `POST /probe-now` returned `{ok: true}` for all 5 services with realistic latencies (storefront 341ms, backend 52ms, database 23ms, stripe 253ms, telegram 0ms-skipped)
- `GET /rollup?days=30` returns 31 days × 5 services with 1 data point each (the manual probe), summary `{current: 100%, avg: 100%, incidents: 0}`
- Maintenance dashboard screenshot shows the widget rendering with one green cell at the right edge of each sparkline

### Files touched
- `backend/services/gsc_digest.py` — iso_week → iso_date, daily wording
- `backend/services/scheduler.py` — daily cron + new uptime probe job
- `backend/services/uptime.py` — new (5 probes + rollup helpers)
- `backend/routes/uptime.py` — new (3 endpoints)
- `backend/routes/__init__.py` — wires `uptime_router` into the app
- `frontend/src/pages/admin/UptimeSparklineWidget.jsx` — new
- `frontend/src/pages/admin/MaintenanceTasks.jsx` — mounts the widget
- `frontend/src/pages/admin/GscSitemapCard.jsx` — copy update

### Production deploy
Save-to-GitHub → Railway redeploys → on first boot the uptime cron starts collecting probes. After ~24 hours each sparkline will have 288 data points (5-min × 24 hrs), enough to show a clean trend line. After 30 days the widget hits its design intent: a one-glance trust signal.

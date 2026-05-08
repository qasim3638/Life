## 2026-05-02 — 🟢 GSC Phase 4 LIVE: Weekly digest + CTR-drop alerts

Closes the SEO loop: admins now get pushed insights instead of having to log in.

### Backend (`services/gsc_digest.py` + `routes/gsc_auth.py`)
Two scheduled jobs registered on backend boot via `services/scheduler.py`:

**1. `gsc_weekly_digest` — Mondays 09:30 Europe/London**
- Pulls 7-day overview + top queries + top pages from GSC
- Computes prior-week deltas (clicks/impressions ▲▼ chip)
- Renders HTML email mirroring the existing seo_digest brand
- Sends to all `admin` + `super_admin` users via Resend (existing email infra)
- Idempotent on `iso_week` so a redeploy on Monday doesn't double-send
- Skips silently when (a) no admin connected, (b) no data yet, (c) already sent this week
- Subject: `[Tile Station] SEO weekly · 15 clicks · 812 impressions`

**2. `gsc_ctr_drop_daily` — Daily 08:00 Europe/London**
- Compares each page's last-7d CTR vs its 28-day baseline
- Filters: ≥50 impressions/wk to ignore noise, ≥50% CTR drop to fire
- Dedupes per `(url, iso_week)` so a flapping page doesn't spam Telegram
- Sends a single batched Telegram message with up to 10 drops + deep-link to /admin/seo
- Reuses `services.telegram_notify.send_telegram` (already wired for orders/payment-failures)

### Manual triggers (admin endpoints)
- `POST /api/admin/gsc/digest/send-now?force=true` — re-fire digest immediately
- `POST /api/admin/gsc/ctr-drop/check-now?force=true` — re-fire alerts immediately

### Frontend (`pages/admin/GscSitemapCard.jsx`)
Added a yellow "Weekly digest + CTR-drop alerts" mini-card at the bottom with explanatory copy + a "Send test digest now" button (force=true) so an admin can preview the email format without waiting until Monday. Toast surfaces success/skip/failure.

### Verified live (preview env)
- `digest/send-now?force=true` → `{ok: true, recipients: 5, totals: {clicks: 15, impressions: 812, ctr: 1.85%, avg_position: 29.7}}` ✅
- `ctr-drop/check-now` → `{ok: true, drops_detected: 0, fresh_alerts: 0}` ✅ (expected — site is on the rise, not declining)
- Both scheduled jobs registered at startup
- Lint clean across all touched files

### Files touched
- `backend/services/gsc_digest.py` — new (~330 LOC); two job entry-points
- `backend/services/scheduler.py` — registered 2 new APScheduler jobs
- `backend/routes/gsc_auth.py` — 2 new manual-trigger endpoints
- `frontend/src/pages/admin/GscSitemapCard.jsx` — added "Send test digest now" button + handler

### What's left (truly P3+ tail)
With Phases 1-4 in production the SEO loop is closed:
- Connection ✅
- Live dashboard ✅
- Auto-recrawl on every deploy ✅
- Pushed insights every week ✅
- Real-time regression alerts ✅

Future enhancements (non-blocking):
- Per-page hover-to-reveal "top query" on the city pages table
- Anchor-text/backlink monitoring (would need separate Ahrefs hook)
- "Send digest as PDF" archival mode
- Slack mirror of CTR-drop alerts (we ship Telegram; Slack is just a webhook swap)

### Production deploy
Save-to-GitHub → Railway redeploys → on first boot, both APScheduler jobs register automatically. No new env vars needed (reuses Resend + Telegram + GOOGLE_* already on Railway).

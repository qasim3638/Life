## 2026-05-02 — 🟢 Google Search Console Phase 1 LIVE on production

After completing the Phase 1 OAuth scaffolding (services/gsc.py, routes/gsc_auth.py, GscConnectCard) yesterday in preview, deployed to production today. Three blockers surfaced and were resolved live:

### 1. PKCE mismatch (`InvalidGrantError: Missing code verifier`)
`google-auth-oauthlib==1.3.1` auto-generates a PKCE code_verifier in `Flow.authorization_url()`. The verifier was kept in the local Flow instance and lost when the callback created a fresh Flow. Two-line fix: pass `autogenerate_code_verifier=False` when building the Flow (since the confidential Web client already uses client_secret), and persist whatever verifier is generated alongside the state token in `gsc_oauth_states` so the callback can replay it. Both belt-and-braces.

### 2. Frontend redirect bounced to wrong env
`_frontend_origin()` was reading `SHOP_WEBSITE_URL` first, which is hard-coded to `https://tilestation.co.uk`. Result: a successful preview-env OAuth was bouncing the admin to the production frontend after callback, where the production card still said "Not connected" (different DB). Fixed `_frontend_origin()` to derive the origin from `GOOGLE_OAUTH_REDIRECT_URI` (same env as the callback always wins) before falling back to `SHOP_WEBSITE_URL`.

### 3. `tilestation.co.uk/api/admin/gsc/callback` was returning the SPA, not the backend
Production frontend runs `node server.js` (Express proxy) which only proxied `/sitemap.xml` and `/robots.txt` to the backend. Everything else `/api/*` fell through to `app.get('*')` and returned `index.html` (HTTP 200). So Google's redirect to `tilestation.co.uk/api/admin/gsc/callback?code=...` never reached FastAPI — the user just landed on a blank-ish SPA page and the tokens were never exchanged. Fix: added a second proxy rule in `frontend/server.js` for `/api/admin/gsc` → backend Railway URL.

### Datetime tz mismatch (minor)
`gsc_oauth_states.expires_at` was being read back as naive from MongoDB (depending on driver version), then compared to a tz-aware `datetime.now(timezone.utc)`. Reattached `tzinfo=timezone.utc` on read.

### Verification
- `curl GET tilestation.co.uk/api/admin/gsc/status` returns `{connected: true, configured: true, google_account_email: qasim3637@gmail.com}`
- `curl GET tilestation.co.uk/api/admin/gsc/sites` returns both `sc-domain:tilestation.co.uk` and `https://www.tilestation.co.uk/` with `siteOwner` permission
- Admin UI screenshot shows the green CONNECTED badge with both property chips

### Files touched (Phase 1 final)
- `backend/services/gsc.py` — PKCE off, optional verifier handover, refresh-token persistence
- `backend/routes/gsc_auth.py` — frontend origin derivation, PKCE state plumbing, tz fix
- `frontend/server.js` — added /api/admin/gsc proxy
- `frontend/src/pages/admin/GscConnectCard.jsx` (no changes from yesterday)
- `frontend/src/pages/admin/SeoCommandCentre.jsx` (no changes from yesterday)

### Phases not yet built
- Phase 2: Search Analytics API — top queries per /tiles/<city> page, dashboard cards, nightly cron caching
- Phase 3: URL Inspection API + Sitemaps API auto-submit on every deploy + indexed/not-indexed coverage report
- Phase 4: Weekly digest email (Resend) + CTR-drop Telegram alerts

### Notes for ops
- Google Cloud project: `tile-station-seo` · OAuth client name: `Tile Station Backend`
- Test users (Audience tab): `qasim3637@gmail.com` (must remain there while app is in Testing mode — adding another tester is `+ Add users`)
- 100-user lifetime cap before Google forces verification — not an issue for our internal use
- Refresh token is bound to Google account `qasim3637@gmail.com` — if that account is later disabled, run "Disconnect" then reconnect with a new account

# SEO Lock-in Runbook — King's-Right-Hand Status Board

These four items must be 100% green before SEO Autopilot can be declared "watch like a king" complete.

Live status: **`/admin/seo` → "King's-Right-Hand Status" card** at the top.
Backed by `GET /api/admin/seo-health/status` (parallel checks against
Stripe, Resend, Mongo `gbp_oauth_tokens`, and env vars).

---

## (1) 🔴 Stripe webhook — currently MISSING

**Verified [May 2 2026]**: Stripe API call confirms **0 webhook endpoints** exist on the live account `Tile Station Ltd`. Payments confirm via the client-side success redirect only — fragile if the customer closes the tab before redirect lands.

**Steps:**

1. https://dashboard.stripe.com/webhooks → click **+ Add destination**.
2. **Events**: tick `payment_intent.succeeded`, `payment_intent.payment_failed`, `charge.refunded`, `checkout.session.completed`.
3. **Destination type**: Webhook endpoint.
4. **Endpoint URL**: `https://<railway-backend>.up.railway.app/api/webhooks/stripe`. Find the Railway URL under backend service → Settings → Networking → Public Domain.
5. Click **Create destination**.
6. Click **Reveal signing secret** (starts `whsec_…`).
7. Paste secret into Railway backend env:
   ```
   STRIPE_WEBHOOK_SECRET=whsec_…
   ```
   Railway → backend service → Variables → Add → Save → service auto-redeploys.
8. **Test**: in Stripe webhook page, click **Send test event** → `payment_intent.succeeded` → look for green 200 OK in 2 seconds.

When green, the status board card flips to GREEN automatically on next re-check.

---

## (2) 🔴 Resend custom domain — API KEY INVALID

**Verified [May 2 2026]**: Resend API returns 401 with the current `RESEND_API_KEY`. Either the key has been revoked or it was never valid. Until fixed, ALL transactional emails (order receipts, SEO digests, autopilot summary) are failing silently.

**Steps:**

1. Open https://resend.com/api-keys (log in as the account that owns Tile Station).
2. If no valid key listed → click **Create API Key** → "Full access" → name `tilestation-prod-<date>` → copy the value (starts `re_…`).
3. Paste into both:
   - Railway backend service → Variables → `RESEND_API_KEY`
   - The local `.env` (only if testing locally — production uses Railway env)
4. Confirm domain status at https://resend.com/domains.
   - If `tilestation.co.uk` already shows **Verified**, you're done.
   - Otherwise: **Add domain** → tilestation.co.uk → region **London (eu-west-2)** → add the 3 DNS records (1 MX + 2 TXT) at your DNS host (Cloudflare = grey-cloud only) → click **Verify** after 5-30 min.
5. The backend `.env` already has `SENDER_EMAIL=online@tilestation.co.uk`. No code change needed — emails will route from your verified domain automatically.
6. **Test**: log into admin → `/admin/seo` → click **Send digest now**. Email lands within 60s with `From: Tile Station <online@tilestation.co.uk>`. Gmail "show original" → DKIM=pass, SPF=pass.

When green, the status board flips to GREEN.

---

## (3) 🟡 Google Business Profile API — applied May 2 2026

**Status:** SUBMITTED. Google support case ID: **`5-2034000040234`**.
**Expected approval:** 7-10 working days (per Google support response).
**Project:** Tile Station SEO · Project number `199653351384`.
**Applicant:** Hafiz Qasim · qasim@tilestation.co.uk.
**Selected business:** Tile Station - Tonbridge (Vale Road).
**Listings covered:** all 4 verified Tile Station locations (Tonbridge, Gravesend, Chingford, Sydenham).

When approval email arrives → click **Connect** on `/admin/gbp` → run OAuth.
Status board flips to GREEN automatically on next re-check.

The backend + admin UI are built and waiting at `/admin/gbp`. Google has us on their allowlist queue.

**Steps:**

1. https://support.google.com/business/contact/api_default
2. Sign in with the Google account that owns the Tile Station GBP listings.
3. Form fields:
   - **Project name**: Tile Station Internal Admin
   - **Use case**: "Single-business management — display business profile data, posts, insights, and reviews inside our internal admin panel for Tile Station Ltd. We manage 4 showroom locations (Gravesend, Tonbridge, Chingford, Sydenham)."
   - **APIs**: Business Profile Performance API, Business Profile API (Account Management), Business Information API, Posts API.
   - **Project number**: open https://console.cloud.google.com/ → click project dropdown → copy the ID of the existing GSC OAuth project (we reuse the same project).
   - **Estimated daily quota**: 200 reads, 20 writes
4. Submit. Google replies in 5-30 days.
5. When approved, admin clicks **Connect** on `/admin/gbp` and reviews + insights + posts go live. The status board flips to GREEN.

While waiting, GBP still works via https://business.google.com/ for manual edits.

---

## (4) 🟡 Google Ads developer token — apply now, ~1-2 weeks wait

Unlocks real Keyword Planner CPCs (currently using a transparent heuristic that returns ~£13.34/mo saved).

**Step A — Create MCC manager account (5 min):**

1. https://ads.google.com/aw/signup/landing → **Create a manager account**.
2. Name: Tile Station MCC · Country UK · Currency GBP · Timezone London.
3. **Important**: when asked "What will you use this account for?" → choose **Manage other people's accounts** (this is the MCC).
4. Skip ad creation. Save.
5. From the MCC dashboard, copy the 10-digit **Customer ID** at top.

**Step B — Apply for developer token:**

1. Inside the MCC, click **Tools** (top-right wrench) → **API Center** under Setup.
2. Form fields:
   - Company: Tile Station Ltd · Website: tilestation.co.uk
   - Use case: "Internal SEO ↔ paid analytics dashboard. Read keyword CPCs (Keyword Planner, Search Term Insights) to calculate equivalent Ads spend saved by organic rankings. Read-only, single-account use."
   - Tools: Keyword Planner, Search Term Insights.
   - Estimated calls/day: 500
3. Submit. Google returns a developer token in 1-2 weeks (Test mode is sufficient).

When the token lands, paste it into Railway backend env:
```
GOOGLE_ADS_DEVELOPER_TOKEN=…
```
The status board flips to GREEN. Backend code already has the swap stubbed in `routes/ads_savings.py`.

---

## What's already running automatically (no human action)

✅ **9 SEO Autopilot cron jobs** — verified live at `/api/health/deep` (33 total scheduled jobs, 9 with prefix `seo_autopilot_*`).
✅ Sitemap auto-submit, GSC daily digest, weekly digest, CTR-drop alerts, monthly P&L digest, quarterly board-deck PDF.
✅ City landing pages auto-generation @ 20/day, auto-publish at confidence ≥90.
✅ React 19 native metadata hoisting on every storefront route.
✅ JSON-LD structured data on products, categories, info, city pages.
✅ Real `/sitemap.xml` and `/robots.txt` from `/api/sitemap.xml` proxy.
✅ Uptime probes every 5 min (storefront, backend, Mongo, Stripe, Telegram).

---

## Where to look once green

Single-pane: `/admin/seo` → "King's-Right-Hand Status" card at top. The card stays visible permanently — if anything regresses (token rotated, webhook deleted, domain unverified) you'll see it on the next page load.

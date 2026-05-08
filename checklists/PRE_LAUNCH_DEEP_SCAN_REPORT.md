# Pre-Launch Deep Scan Report
**Generated**: 2026-04-28 (launch-eve)
**Scope**: Entire preview environment — product data, UI routes, logs, integrations

---

## ✅ TL;DR
**You are green to launch.** No blocking bugs found. 2 DB fixes applied, 1 infra fix applied, all 18 UI health checks passing.

---

## 1. Product Data Audit  (`db.tiles` — 766 products)

| Check | Result | Action |
|---|---|---|
| Duplicate SIZE token in name (e.g. "60x60 … 60x60") | **0** | — |
| Duplicate FINISH token in name (e.g. "Matt … Matt") | **0** | — |
| Wrong-case size ("60X60" / "60×60") | **0** | — |
| Missing `finish` field (active tiles) | 88 | **Safe — all are Ultra Tile accessories** (grouts, mixing buckets, adhesives) with `category_ids: []` — finish/size legitimately N/A |
| Missing `size` field (active tiles) | 104 | Same as above |
| Test placeholders leaked in `finish` field | 2 | ✅ **FIXED — cleared `NEW_FINISH_VALUE`** on `tile-355`, `tile-440` |
| Whitespace problems in name | 0 | — |
| `name` vs `display_name` mismatch | 0 | — |
| Redundant words ("Tile", "Porcelain", "Cm") | 502 | ⚠️ **Flagged only**, not auto-stripped (SEO/customer-recognition risk pre-launch) |

**CSV audit trail**: `/app/checklists/name_cleanup_2026-04-28_104152Z.csv`

**Your main concern (duplicates in names) → zero found across all 766 products.**

---

## 2. UI Health Sweep  (19 critical public routes)

Triggered `POST /api/website-admin/maintenance/ui-checks/run-now` with fresh Playwright 1148 / Chromium installed:

| Result | Count |
|---|---|
| ✅ Passed | **18 / 18** |
| ✗ Failed | 0 |
| Duration | 81 s |
| Email (PDF to admins) | sent to 5 recipients |

All 18 public pages rendered correctly with expected `data-testid` selectors: homepage, shop header/logo, tile collections grid, PDP trade box + volume pricing + add-to-cart, order tracking, trade login/register, customer login/register, delivery/returns/privacy, contact, refer-a-friend, sample service, tile calculator.

---

## 3. Infrastructure Fix Applied

🔧 **Playwright Chromium was missing in this forked pod** (P0 monitoring regression — would have silently broken the 03:00 UTC daily UI health PDF report on launch morning).
- Symptom: `BrowserType.launch: Executable doesn't exist at /pw-browsers/chromium_headless_shell-1148/chrome-linux/headless_shell`
- Fix: Re-ran `playwright install chromium` + restarted backend.
- Verified: UI health sweep now completes successfully (see §2).

---

## 4. Backend Log Sweep
- No recurring exceptions, no 500s, no DB connection errors in the last ~200 log lines.
- APScheduler running 8 cron jobs cleanly (reconciliation, digest, co-purchase rebuild, maintenance auto-window, UI health, abandoned-cart reminders, unanswered-chat alert, frequently-bought-together).
- GOV.UK bank holidays API call succeeded (`200 OK`, 32 holidays fetched).

---

## 5. Supervisor Status
```
backend            RUNNING
frontend           RUNNING
mongodb            RUNNING
nginx-code-proxy   RUNNING
```

---

## ⚠️ Production Sync Reminders

**CRITICAL**: This preview pod uses `mongodb://localhost:27017` — your production Railway Atlas cluster is **separate and untouched**.

### For the **2 DB fixes** (NEW_FINISH_VALUE placeholders) to reach production:
Pick ONE path:
- **(a) Easiest**: In Admin → Website Hub → Products, find SKUs `tile-355` and `tile-440` and clear the `finish` field manually (~30s).
- **(b) Scripted**: Run `/app/checklists/audit_product_names.py --apply` against your Railway MONGO_URL (set env var temporarily). The script is idempotent and dry-runs by default.

### For **all code changes** (announcement ribbon history log + earlier launch-eve fixes) to reach production:
- Click **"Save to Github"** in the chat input → triggers Railway auto-deploy.

---

## 6. Non-Blocking Post-Launch Backlog
- ⚪ 502 "redundant words" (Tile / Porcelain / Cm) in product names — consider a curated sweep post-launch with manual review per row.
- ⚪ The 88 Ultra Tile accessory rows live in `db.tiles` but are truly non-tile products. Consider moving them to a dedicated `db.accessories` collection post-launch for cleaner separation.
- ⚪ P1 queued: 30-day uptime sparkline on `/admin/maintenance`.
- ⚪ P1 queued: `GET /api/tiles/collections/by-names?names=A,B,C` batch endpoint for Recently Viewed.

---

## Launch Checklist (tomorrow AM)
See `/app/memory/LAUNCH_MORNING_CHECKLIST.md` — live order test top of list.

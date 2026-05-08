# Tile Station - Product Requirements Document

## Overview
Full-stack application for managing supplier product data with React frontend, FastAPI backend, and MongoDB.

## Core Features

### 1. Sync Hub & Supplier Products
- Dashboard for managing supplier data from multiple sources
- Quick edit modal for products on Supplier Products page
- On-the-fly data correction for categories

### 2. Server-Side Sync Services
- Wallcano sync
- Splendour sync
- Ceramica Impex sync
- (Pending) Verona server-side sync

### 3. Browser Extensions
- **Verona Extension v4.4** (UPDATED Mar 4, 2026)
  - Quick Sync (Names Only)
  - Full Sync (Stock & Prices)
- Splendour Extension
- Wallcano Extension
- Ceramica Impex Extension

### 4. Universal Naming Logic
Location: `/app/backend/business_config/business_rules.py`
Format: `{unique_name} {colour} {size} {finish}`
Applied to: All sync services, extension endpoints, Excel/JSON imports

### 5. Data Collections
- `sync_staging` - Raw data from supplier syncs (Sync Hub display)
- `supplier_products` - Processed/staged products (contains `in_products_db` flag)
- `products` - Final collection for EPOS/website

---

## Completed Work

### Mar 5, 2026 (Session 2)
- ✅ **Fixed "Failed to load product" bug (P0)**
- ✅ **Created `/api/version` endpoint (P0)**
- ✅ **Added Material & Finish sub-categories**
- ✅ **Category pages consolidated under Website section**
- ✅ **Category sync feature added**
- ✅ **AI Description Generator** with controls (Shorter, Longer, Regenerate, New)
- ✅ **Hidden SEO Keywords System**
  - Auto-generates SEO keywords from Supplier Product Name
  - Includes supplier name, SKU, company name as alternate keywords
  - Schema.org markup with `alternateName` for search indexing
  - Keywords visible to search engines but hidden from customers
  - Endpoint: `/api/products/{id}/seo` - returns all SEO metadata
  - Bulk regenerate: `/api/products/regenerate-seo/all`

### Mar 5, 2026 (Session 1)
- ✅ Added Category Autocomplete to Quick Edit modal
- ✅ Created **Manage Categories** page (`/admin/manage-categories`)
- ✅ Added **Edit Stock** feature to Sync Hub
  - "Add Stock" button for products with missing stock data
  - Edit Stock modal with m² and Units fields
  - `PUT /api/sync-staging/{id}/update-stock` endpoint
- ✅ Added 322 series name mappings for ALL suppliers:
  - Wallcano: 45 series (Thunder→Murano, Grande→Rimini, etc.)
  - Splendour: 56 additional series (Colonial→Savannah, Geneva→Swiss, etc.)
- ✅ Fixed naming logic bugs:
  - "glass" → "Gloss" finish normalization
  - Added "rose" and 30+ colors to COLOUR_KEYWORDS
  - Fixed color vs series name conflict (Black treated as color, not series)
- ✅ Fixed category extraction (rejects finish words as categories)
- ✅ Removed unused extensions for Wallcano/Splendour/Ceramica Impex (server sync only)
- ✅ Kept only Verona extension (CloudFlare blocks server sync)

### Mar 4, 2026
- ✅ Fixed Verona Extension v4.4
  - Updated version from 3.1.0 to 4.4.0
  - Fixed button labels: "Quick Sync (Names Only)" and "Full Sync (Stock & Prices)"
  - Updated download endpoint

### Previous Session
- ✅ Quick Edit Modal on Supplier Products page
- ✅ Category logic refactor (extract_proper_category)
- ✅ Naming logic refactor (generate_unique_product_name)
- ✅ Fixed "Add to Database" flow to write to both collections
- ✅ Data migration endpoints (/fix-categories, /fix-product-names)

---

## Pending Issues (P0)

### Issue 1: Comprehensive Verification of Naming & Category Logic
**Status:** TESTING PENDING
- Clear sync_staging and supplier_products
- Run server-side sync for Wallcano and Splendour
- Verify product_name format: `{unique_name} {colour} {size} {finish}`
- Verify valid categories (not product line names)
- Test extension data processing

### Issue 2: Verify "Add to Database" Flow and UI Icon
**Status:** TESTING PENDING
- After adding products, they should show ✓ checkmark (not + icon)
- Products should exist in both supplier_products and products collections

### Issue 3: Production Environment Drift
**Status:** RESOLVED
- **Solution:** `/api/version` endpoint created
- After deployment, call: `curl https://your-domain.com/api/version`
- Verify commit hash matches latest code

### Issue 4: "Add All to Database" UI Progress Feedback
**Status:** NOT STARTED
- Backend task completes but UI doesn't update in real-time
- Need to improve polling logic or switch to WebSockets

---

## Upcoming Tasks (P1)
- Deploy all fixes to Railway production
- Implement Server-Side Sync for Verona
- Implement pause/stop functionality for syncs

## Future Tasks (P2-P3)
- Generic bulk price/name rule application script
- Scheduled scraping for all suppliers
- Verify Batch 4 Inventory Features
- Trade Account Credit Limits

---

## Key Files Reference
- `/app/backend/business_config/business_rules.py` - Naming logic
- `/app/backend/routes/sync_staging.py` - Category extraction, Add to DB flow
- `/app/backend/routes/supplier_sync.py` - Extension endpoints, imports
- `/app/backend/routes/products.py` - Product CRUD endpoints
- `/app/backend/server.py` - Main server with product endpoints (lines 1764-1811)
- `/app/backend/services/{wallcano,splendour,ceramica_impex}_sync.py` - Server syncs
- `/app/extensions-final/TileStation-Verona/` - Verona extension source
- `/app/frontend/src/pages/admin/SupplierProducts.js` - Quick edit UI

## Test Credentials
- Email: admin@test.com
- Password: test

## 3rd Party Integrations
- Cloudflare R2 (image storage)
- Playwright (web scraping)
- Resend (email - feature flagged off)

---

## Version Endpoint
**NEW:** `/api/version` endpoint added for deployment verification.
- No authentication required
- Returns: version, commit hash, commit date, build timestamp, server time
- Use after each deployment to confirm production is running latest code

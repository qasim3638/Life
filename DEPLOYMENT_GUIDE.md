# Tile Station - Production Deployment Guide

## Overview

This guide will help you deploy the latest fixes from this Emergent preview environment to your Railway production.

## Critical Bugs Fixed in This Release

### 1. Session Logout Bug (CRITICAL)
**Root Cause**: Inconsistent JWT secret keys across different backend files
- `server.py` used: `JWT_SECRET` with fallback `"your-secret-key-change-in-production"`
- `shop.py` used: `JWT_SECRET` with fallback `"secret"` (DIFFERENT!)
- `supplier_sync.py` used: `SECRET_KEY` with fallback `"tilestation-secret-key-change-in-production"` (DIFFERENT!)

**Fix**: All files now use the same `JWT_SECRET` environment variable with consistent fallback.

### 2. Box Price Calculation Bug
**Root Cause**: Wrong formula - was multiplying price by tiles count instead of m² coverage
**Fix**: Correct formula: `boxPrice = price × boxM2Coverage`

### 3. Tile Dimensions 10x Error
**Root Cause**: Dimensions entered in mm but stored as cm (e.g., 300x600 instead of 30x60)
**Fix**: Added auto-conversion in frontend + validation warnings + database fix script

### 4. New Features
- 6-part product page overhaul (specifications, series field, stock levels, collapsible calculator)
- Bi-directional data sync between Bulk Editor and Full Page Editor

---

## Step 1: Save Code to GitHub

1. In the Emergent chat, look for **"Save to GitHub"** button at the bottom of the chat input
2. Click it and follow the prompts to push to your GitHub repository
3. Wait for confirmation that the code was pushed successfully

---

## Step 2: Deploy on Railway

### Option A: Automatic Deploy (if you have auto-deploy enabled)
- Railway should automatically detect the GitHub push and start deploying
- Check Railway dashboard for deployment status

### Option B: Manual Deploy
1. Go to your Railway dashboard: https://railway.app/dashboard
2. Click on your project
3. Go to **Deployments** tab
4. Click **"Deploy"** or **"Redeploy"** button
5. Select the latest commit from your GitHub repo

---

## Step 3: Verify Environment Variables on Railway

Make sure these are set in Railway (Settings → Variables):

```
JWT_SECRET=<your-secure-secret-key>
MONGO_URL=<your-mongodb-atlas-connection-string>
DB_NAME=tile_station
```

**IMPORTANT**: The `JWT_SECRET` must be set! If it's not set, the default fallback will be used, but all services MUST use the same secret.

---

## Step 4: Fix Database Data (One-Time)

After deployment, run the tile dimension fix script to correct the 10x error in existing products.

### Option A: Run via Railway Shell
1. In Railway dashboard, click on your backend service
2. Go to **"Shell"** or use Railway CLI
3. Run:
```bash
cd /app
python scripts/fix_tile_dimensions.py
```

### Option B: Use the API Endpoint (Safer - Recommended)
After deployment, call this endpoint with admin authentication:

**Step 1: Get your auth token**
Login to the admin panel and use browser dev tools to copy your Bearer token, OR use curl:
```bash
TOKEN=$(curl -s -X POST "https://your-railway-url.up.railway.app/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"qasim@tilestation.co.uk","password":"YOUR_PASSWORD"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('token',''))")
```

**Step 2: Run DRY RUN first (preview only)**
```bash
curl -X POST "https://your-railway-url.up.railway.app/api/admin/fix-tile-dimensions?dry_run=true" \
  -H "Authorization: Bearer $TOKEN"
```

**Step 3: Apply the fix (after reviewing dry run)**
```bash
curl -X POST "https://your-railway-url.up.railway.app/api/admin/fix-tile-dimensions?dry_run=false" \
  -H "Authorization: Bearer $TOKEN"
```

**Optional: Filter by supplier**
```bash
curl -X POST "https://your-railway-url.up.railway.app/api/admin/fix-tile-dimensions?dry_run=false&supplier=LEPORCE" \
  -H "Authorization: Bearer $TOKEN"
```

---

## Step 5: Verify the Fixes

### Test 1: Session Persistence
1. Login to admin panel
2. Navigate to different pages
3. Scroll up and down on edit product page
4. Verify you're NOT logged out

### Test 2: Box Price Calculation
1. Go to Products → Edit a tile product
2. Check Tile Size & Box Configuration section
3. Verify: `Box Price = Price per m² × Box Coverage (m²)`
4. Example: £28.99/m² × 0.9 m² = £26.09 per box

### Test 3: Tile Dimensions
1. Edit a product with 30x60cm tile
2. Verify dimensions show 30x60 (not 300x600)
3. Verify m² per piece shows 0.18m² (not 18m²)

---

## Rollback (if needed)

If something goes wrong:
1. In Railway dashboard, go to Deployments
2. Find the previous working deployment
3. Click **"Rollback"** on that deployment

---

## Support

If you encounter issues after deployment:
1. Check Railway logs for errors
2. Verify environment variables are set correctly
3. Contact Emergent support with error details

---

## Files Changed in This Release

### Backend
- `server.py` - Box price formula fix, series field sync
- `routes/shop.py` - JWT secret consistency fix
- `routes/supplier_sync.py` - JWT secret consistency fix
- `scripts/fix_tile_dimensions.py` - Database fix script

### Frontend
- `pages/admin/ProductForm.js` - Series field, dimension validation
- `pages/shop/TileDetailPage.js` - 6-part product page update

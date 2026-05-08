# Tile Station — SEO Crawl Setup Deployment

## What changed and why

**Problem found**: `tilestation.co.uk/sitemap.xml` and `tilestation.co.uk/robots.txt`
were returning the React HTML shell instead of real XML/text. Google could
not discover any of our 776 indexable pages (homepage + 5 info pages + 3
approved AI city pages + 761 active product pages).

**Fix**:
1. New backend routes `GET /api/sitemap.xml` and `GET /api/robots.txt`
   that emit real XML/plain-text against the canonical
   `https://tilestation.co.uk` host.
2. Replaced the production frontend server (`serve -s build`) with a
   thin Express server (`frontend/server.js`) that:
   - Proxies `/sitemap.xml` and `/robots.txt` to the backend.
   - Serves the React SPA for everything else, with proper cache headers.
3. `Procfile`, `nixpacks.toml`, `railway.json` and `package.json`
   updated so Railway runs `node server.js` in production. Local
   supervisor still uses `craco start` (unchanged — local dev untouched).

## Files touched

| File | Change |
|------|--------|
| `backend/routes/seo_public.py` | NEW — sitemap.xml + robots.txt endpoints |
| `backend/routes/__init__.py` | Register `seo_public_router` |
| `frontend/server.js` | NEW — Express static server + SEO proxy |
| `frontend/Procfile` | `node server.js` |
| `frontend/nixpacks.toml` | `cmd = "node server.js"` |
| `frontend/railway.json` | `startCommand: node server.js` |
| `frontend/package.json` | Added `express`, `http-proxy-middleware`, new `start:prod` script |

## Required environment variable on Railway frontend service

The proxy in `server.js` reads `REACT_APP_BACKEND_URL` to know where to
forward sitemap/robots requests. This is **already set** in Railway
because the React app uses the same variable. No new secret needed.

## Deploy steps

1. **Save to GitHub** from the chat input (commit + push).
2. Railway frontend service auto-deploys on push.
3. Watch the deploy log for `[server] Tile Station storefront listening on :3000`
   and `[server] Proxying /sitemap.xml + /robots.txt → https://...`.
4. Verify production:
   ```bash
   curl -I https://tilestation.co.uk/sitemap.xml
   #   HTTP/2 200
   #   content-type: application/xml
   curl https://tilestation.co.uk/sitemap.xml | grep -c "<url>"
   #   ~776 (will grow as more city pages are approved)
   curl https://tilestation.co.uk/robots.txt
   #   sitemap: https://tilestation.co.uk/sitemap.xml
   ```

## After deploy — submit to Google Search Console

1. Go to <https://search.google.com/search-console>.
2. Select the **tilestation.co.uk** property (or add it if not yet added).
3. Sidebar → **Sitemaps** → enter `sitemap.xml` → **Submit**.
4. Within ~24 hours Google will crawl all 776 URLs and start indexing.

## Rollback (if anything goes wrong)

The previous start command was `npx serve -s build -l $PORT`. If the new
Express server fails on Railway, revert these three lines:

- `frontend/Procfile`: `web: npx serve -s build -l ${PORT:-3000}`
- `frontend/nixpacks.toml`: `cmd = "npx serve -s build -l 3000"`
- `frontend/railway.json`: `"startCommand": "npx serve -s build -l $PORT"`

Then redeploy. Sitemap.xml / robots.txt would go back to broken but
nothing else breaks.

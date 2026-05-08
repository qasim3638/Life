# Tile Station - Business Rules

## Image Management Rules

### 1. Cloud Storage Configuration
- **Provider**: Cloudflare R2
- **Bucket**: `tilestation-images`
- **Public URL**: `https://images.tilestation.co.uk`
- **Cache**: 1 year (`max-age=31536000`)

### 2. Image Naming Convention
Images are stored using **product display names** (not supplier SKUs or codes):

```
Format: products/{supplier}/{Product_Display_Name}_{index}_{hash}.jpg

Examples:
- products/wallcano/Nero_Marquina_Polished_60x60_0_a1b2c3d4.jpg
- products/verona/Calacatta_Gold_Matt_120x60_1_e5f6g7h8.jpg
- products/splendour/Urban_Grey_Concrete_Effect_0_i9j0k1l2.jpg
```

**Naming Rules:**
- Supplier name: lowercase, underscores replace spaces (max 30 chars)
- Product name: special characters removed, spaces become underscores (max 60 chars)
- Index: 0-based image position for products with multiple images
- Hash: 8-char MD5 of original source URL (ensures uniqueness)

### 3. Automatic R2 Upload Triggers
Images are automatically uploaded to R2 when products are added/synced via:

| Sync Method | Status | Uses Display Name |
|-------------|--------|-------------------|
| Wallcano Server-Side Sync | ✅ Active | Yes |
| Ceramica Impex Server-Side Sync | ✅ Active | Yes |
| Verona Browser Extension | ✅ Active | Yes |
| Single URL Product Sync | ✅ Active | Yes |
| Batch Scraper | ✅ Active | Yes |
| Scheduled Imports | ✅ Active | Yes |
| Image Migration Tool | ✅ Active | Yes |

### 4. Image Change Detection & Updates
To prevent duplicates and handle supplier image updates:

**Database Fields:**
```javascript
{
  "images": ["https://images.tilestation.co.uk/..."],     // R2 URLs (displayed)
  "image_source_urls": ["https://supplier.com/..."],      // Original source URLs (tracking)
  "images_uploaded_to_r2": true                            // Migration status flag
}
```

**Update Logic:**
1. **First Sync**: 
   - Download image from supplier URL
   - Optimize (resize to max 1200px, compress to 85% quality JPEG)
   - Upload to R2
   - Store both R2 URL and original source URL

2. **Subsequent Syncs**:
   - Compare new source URL with stored `image_source_urls`
   - If **same** → Keep existing R2 URL (no re-upload, no duplicate)
   - If **different** → Download new image → Upload to R2 → Update both URLs

3. **Deep Sync / Full Refresh**:
   - Always checks for image changes
   - Only uploads images that have actually changed
   - Logs when images are updated: `"Image updated for {product}: {old_url} -> {new_url}"`

### 5. Image Processing Pipeline
```
Source URL → Download → Validate → Optimize → Upload to R2 → Store URLs
```

**Optimization Settings:**
- Max dimension: 1200px (maintains aspect ratio)
- Format: JPEG
- Quality: 85%
- Color mode: RGB (converts RGBA/P mode with white background)

### 6. Skip Conditions
Images are NOT re-uploaded when:
- URL already points to R2/cloud storage (checked via `is_already_cloud_url()`)
- Source URL matches stored `image_source_urls` (no change detected)
- R2 is not configured (falls back to original URLs)

**Cloud URL Patterns (auto-skipped):**
- `r2.dev`
- `r2.cloudflarestorage.com`
- `images.tilestation.co.uk`
- `cloudflare`
- `amazonaws.com`
- `s3.`
- `blob.core.windows.net`
- `storage.googleapis.com`

### 7. Error Handling
- **Download failure**: Keep original URL, log warning, continue with next image
- **Upload failure**: Keep original URL, log error, continue with next image
- **Optimization failure**: Upload original unoptimized image
- **Timeout**: 30 seconds per image, 3 retry attempts with exponential backoff

### 8. Migration Tool Rules
Located at: **Admin → Website Hub → Image Migration**

**Features:**
- Migrate tiles collection (published products)
- Migrate supplier_products collection (staging)
- Real-time progress tracking
- Pause/Stop capability
- Skip already-migrated images
- Error reporting

**Migration Priority:**
1. Tiles collection (live website) - HIGH
2. Supplier products (staging) - MEDIUM

---

## Price Rules

### Markup Calculations
- Default markup: 50% over cost price
- Trade accounts: Custom discounts applied
- Clearance items: Special pricing rules apply

### Price Fields
```javascript
{
  "cost_price": 10.00,        // Supplier cost
  "price": 15.00,             // Calculated list price
  "price_per_sqm": 15.00,     // Price per square meter
  "price_per_box": null       // Price per box (if applicable)
}
```

---

## Sync Rules

### Supplier Priority
1. Verona - Primary supplier
2. Wallcano - Secondary supplier
3. Splendour - Tertiary supplier
4. Ceramica Impex - Additional supplier

### Server-Side Sync Features (March 2026)

All server-side syncs now include:
- **Live Product Display**: Shows current product being synced with image, name, SKU, stock, and price
- **Image Column**: Product images displayed in Existing Product Updates and New Products tables
- **Progress Tracking**: Real-time progress percentage and products synced count
- **Stop Capability**: Graceful stop signal for long-running syncs

#### Splendour Server-Side Sync
| Mode | Duration | Description |
|------|----------|-------------|
| Light Sync | 10-15 min | Updates stock & prices only |
| Full Sync | 30-45 min | All details + images to R2 |

#### Ceramica Impex Server-Side Sync
| Mode | Duration | Description |
|------|----------|-------------|
| Light Sync | 10-15 min | Updates stock & prices only |
| Full Sync | 30-45 min | All details + images to R2 |

**Price Extraction Logic:**
1. JavaScript DOM extraction (dynamic price elements)
2. HTML regex patterns (price break tables, data attributes)
3. Text pattern matching (fallback)
4. Price range filter: £0 - £500 to avoid false matches

**Stock Extraction Format:**
- Supports decimal values (e.g., `612.86574 m²`)
- Patterns: `{number} m² in stock`, `Stock: {number} m²`

#### Wallcano Server-Side Sync
| Mode | Duration | Description |
|------|----------|-------------|
| Full Sync | 20-30 min | Stock + images (NO PRICES) |

**Important:** Wallcano portal does NOT display prices. Prices must be set manually after sync using the Price Import feature.

### SKU Generation
```
Format: {SUPPLIER_PREFIX}-{PRODUCT_ID}-{HASH}
Examples:
- SPL-marble-white-60x60 (Splendour)
- WLC-12345-a1b2 (Wallcano)
- CI-TR734596 (Ceramica Impex)
```

### Stock Updates
- Real-time sync from supplier portals
- Stock levels stored in `stock_sqm`, `stock_m2`, `stock_quantity`
- Supports decimal stock values (e.g., 612.86574 m²)
- Out-of-stock products remain visible but marked as unavailable

### Sync State Structure
All server-side syncs track:
```javascript
{
  "is_running": boolean,
  "phase": "idle" | "scanning" | "syncing" | "complete" | "error" | "stopped",
  "progress": 0-100,
  "message": "Status message",
  "products_found": number,
  "products_synced": number,
  "products_failed": number,
  "products_skipped": number,  // Non-tile products skipped
  "current_product": {
    "name": "Product Name",
    "sku": "SKU-123",
    "image": "https://...",
    "price": 15.99,
    "cost_price": 10.50,
    "stock_m2": 612.86
  }
}
```

### Sync Hub Search & Filter (March 2026)

**Search Box:**
- Searches by: Product Name, SKU, Category
- Real-time filtering as you type
- Clear button (X) to reset search

**Filter Dropdown Options:**
- **All Products**: Shows all staged products
- **Updates Only**: Shows only existing product updates
- **New Products Only**: Shows only newly detected products
- **Has Stock**: Shows products with stock available
- **No Stock (Blocked)**: Shows products blocked due to missing stock

**Filter Results Display:**
- Shows count of filtered results
- Shows "(filtered from X total)" when filter is active
- "Clear Filters" button to reset both search and filter

**Behavior:**
- Filters reset when switching suppliers
- Stats cards update to reflect filtered data
- Works across all supplier tabs (Verona, Splendour, Ceramica Impex, Wallcano, etc.)

### Expandable Product Images (March 2026)

**All product images in Sync Hub are clickable:**
- Thumbnail images in product tables
- Current syncing product images (Splendour, Ceramica, Wallcano)
- New Products section images
- Existing Updates section images

**Image Preview Modal:**
- Click any product image to open full-size preview
- Dark overlay background (80% opacity)
- Image displayed at max 85% viewport height
- Product name shown below the image
- Click anywhere outside image or X button to close
- Hover effect (ring) indicates clickable images

### Bulk Add New Products to Database (March 2026)

**Location:** Sync Hub > Stats Cards > "New Products" card

**Button:** "+ Add All to Database" (green button, only shows when new products > 0)

**What it does:**
1. Adds ALL new synced products to `supplier_products` collection
2. **Applies unique product naming** (Title Case, supplier-specific transforms)
3. Applies pricing rules ONLY if not already calculated during sync:
   - Checks if `price > cost_price × 1.5` (indicates already calculated)
   - If not calculated: `List Price = Cost × 1.90 (markup) × 1.20 (VAT)`
4. Saves product images
5. Marks products as "new_collection" type
6. Removes products from staging after successful add

**Price Double-Calculation Prevention (March 2026):**
The system now detects if price markup was already applied during sync:
- If `staged_price > cost_price × 1.5` → Price already calculated, use as-is
- Otherwise → Apply standard markup formula

**API Endpoint:** `POST /api/sync-staging/{supplier}/add-all-new-products`

---

### Unique Product Naming System (March 2026 - Updated)

**Problem:** Products from different suppliers can have same/similar names, causing confusion and duplicates.

**Solution:** ALL tiling suppliers use `SPLENDOUR_SERIES_TO_UNIQUE_NAME` mapping (208 series) with `ALTERNATIVE_SERIES_NAMES` for **completely different unique names** when duplicates are detected.

---

#### Product Name Structure Format

**Format:** `{unique_name} {colour} {size} {finish} {characteristics}`

**Structure Breakdown:**
1. **Unique Name** - Transformed series name from SPLENDOUR_SERIES_TO_UNIQUE_NAME mapping
2. **Colour** - Extracted colour (Grey, White, Beige, Crema, Anthracite, etc.)
3. **Size** - Dimensions in format (30x60, 60x60, 80x120, etc.)
4. **Finish** - Surface finish from product `finish` field OR extracted from name (Matt, Polished, Gloss, etc.)
5. **Characteristics** - Additional descriptors (Pulpis, Marble, Rectified, etc.)

**IMPORTANT:** The `finish` parameter MUST be passed from the product's `finish` field when calling the naming function. This ensures products like "Terra Ghr Crema 80x120" with finish="Matt" become "Verona Crema 80x120 Matt".

---

#### Implementation for New Suppliers

**To add naming for a new supplier, update these locations in `/app/backend/business_config/business_rules.py`:**

1. **Add to TILING_SUPPLIERS list** (in `get_display_name` function, ~line 2260):
   ```python
   TILING_SUPPLIERS = [
       "Splendour", "Ceramica Impex", "Wallcano", "Verona",
       "YourNewSupplier"  # Add here
   ]
   ```

2. **Add series mappings** to `SPLENDOUR_SERIES_TO_UNIQUE_NAME` (~line 1405):
   ```python
   # YourNewSupplier series
   "NewSeriesName": "ItalianUniqueName",
   ```

3. **Add alternatives** to `ALTERNATIVE_SERIES_NAMES` (~line 1710):
   ```python
   "NewSeriesName": ["Name1", "Name2", "Name3", ...],
   ```

4. **In your sync service/endpoint**, call with finish:
   ```python
   from business_config.business_rules import get_display_name
   
   product_name = get_display_name(
       raw_name=product.get('name'),
       supplier="YourSupplier",
       finish=product.get('finish')  # ALWAYS pass finish!
   )
   product_data["product_name"] = product_name
   ```

---

#### Examples

| Original Supplier Name | Transformed Name | Breakdown |
|------------------------|------------------|-----------|
| `CEMENT GREY 60X60` | `Mesa Grey 60x60 Polished` | Mesa (Unique) + Grey (Colour) + 60x60 (Size) + Polished (Finish) |
| `ROYAL PULPIS BONE RECTIFIED POLISHED 80X80` | `Armani Pulpis Bone 80x80 Polished` | Armani (Unique) + Pulpis (Characteristic) + Bone (Colour) + 80x80 (Size) + Polished (Finish) |
| `CALACATTA WHITE MATT 120X60` | `Mykonos White 120x60 Matt` | Mykonos (Unique) + White (Colour) + 120x60 (Size) + Matt (Finish) |
| `TRAVERTINO CREAM POLISHED 60X60` | `Tahiti Cream 60x60 Polished` | Tahiti (Unique) + Cream (Colour) + 60x60 (Size) + Polished (Finish) |
| `MARBLE STATUARIO GLOSSY 80X160` | `Marmo Statuario 80x160 Gloss` | Marmo (Unique) + Statuario (Characteristic) + 80x160 (Size) + Gloss (Finish) |

**Characteristic Handling:**
- Characteristics are dynamic and normally go NEXT to the unique name
- Common characteristics: Pulpis, Statuario, Marquina, Carrara, Onyx, Emperador, Rectified
- These describe the marble/stone pattern and should be preserved

**Fields Saved:**
- `product_name`: The unique, transformed name following the structure above
- `original_name`: The raw supplier name for reference

---

#### Name Transformation Logic

**How it works (SAME for ALL tiling suppliers):**
1. **Parse the original name** into components (series, colour, size, finish, characteristics)
2. **Find matching series** in SPLENDOUR_SERIES_TO_UNIQUE_NAME
3. **Replace series** with unique destination name
4. **Reconstruct name** in format: `Unique Name + Characteristic + Colour + Size + Finish`
5. **Format**: Title Case, fix size formats (60X60 → 60x60)
6. **Remove redundant words**: Tile, Tiles, Porcelain, Ceramic, Cm, Mm
7. **DUPLICATE CHECK** - If name exists, use next name from `ALTERNATIVE_SERIES_NAMES`

**Alternative Series Names (sample):**
| Series | Alternative Names |
|--------|-------------------|
| Cement | Mesa, Mosca, London, Tulip, Berlin, Prague, Warsaw, Dublin |
| Calacatta | Mykonos, Santorini, Capri, Portofino, Positano, Sorrento, Taormina, Ravello |
| Carrara | Ridge, Alpine, Nordic, Arctic, Polar, Glacier, Frost, Crystal |
| Snow | Positano, Capri, Ischia, Procida, Anacapri, Ravello, Maiori, Minori |
| Travertino | Tahiti, Bali, Fiji, Samoa, Tonga, Vanuatu, Moorea, Palau |
| Concrete | Luxe, Metro, Urban, Civic, Centro, District, Quarter, Borough |

**Example - Same product from 5 suppliers gets 5 DIFFERENT names:**
| Supplier | Input | Output |
|----------|-------|--------|
| Wallcano | `CEMENT GREY 60X60` | `Mesa Grey 60x60` |
| Splendour | `CEMENT GREY 60X60` | `Mosca Grey 60x60` |
| Verona | `CEMENT GREY 60X60` | `London Grey 60x60` |
| Ceramica Impex | `CEMENT GREY 60X60` | `Tulip Grey 60x60` |
| Tile Rite | `CEMENT GREY 60X60` | `Berlin Grey 60x60` |

**Tiling suppliers WITH naming transformation:**
- Splendour, Ceramica Impex, Wallcano, Verona
- Le Porce, H Martin, Tilebase, Bloomstone, Boyden, Eagle

**Suppliers EXCLUDED (keep original names):**
- Tile Rite, Ultra Tile, Trimline, Regulus

**Fields saved:**
- `product_name`: The unique, transformed name (guaranteed unique across all suppliers)
- `original_name`: The raw supplier name for reference

---

### Splendour Image Extraction (March 2026 - Enhanced)

**Problem:** ~71% of products were missing images during sync.

**Root Cause:** Website uses multiple CDN patterns that weren't all detected:
- `https://m2wholesale...` (old pattern)
- `https://m2.wallsandfloors.co.uk/...` (current pattern)
- `https://www.splendourtiles.co.uk/_ipx/...` (proxy wrapper)

**Solution - Multi-stage image extraction:**
1. High-res `<a>` tags with m2wholesale OR m2.wallsandfloors
2. Direct `<img>` tags including `_ipx` proxy URLs
3. Lazy-loaded images via `data-src` attribute
4. Gallery/slider containers (swiper, product-gallery, etc.)

**Logging added:**
- Success: "Extracted X images for ProductName"
- Warning: "No images found for ProductName at URL"

---

### URL-Based Supplier Persistence (March 2026)

**Problem:** Refreshing Sync Hub page would always reset to Verona tab.

**Solution:** Supplier selection is now stored in URL as query parameter.

**How it works:**
- Switching suppliers updates URL: `/admin/sync-hub?supplier=Ceramica%20Impex`
- Refreshing page loads the supplier from URL
- Bookmarkable links to specific suppliers
- Browser back/forward works with supplier changes

### Unique Product Names During Sync (March 2026)

**Problem:** Raw supplier names shown during sync didn't match final product names.

**Solution:** Display transformed/unique names during sync with original shown below.

**Display format:**
```
Miami Grey 60x60 Polished       <- Display Name (transformed)
Original: MIAMI GRIS 60X60 POL  <- Original supplier name
SKU: SPL-123
Stock: 612.86 m²
```

**Transformation logic (SAME for ALL tiling suppliers):**
- Uses `SPLENDOUR_SERIES_TO_UNIQUE_NAME` mapping (208 series → unique names)
- Applied via `generate_unique_product_name()` and `get_display_name()` functions
- File: `/app/backend/business_config/business_rules.py`

---

### Non-Tile Product Exclusion (All Syncs)

**Applied To:**
- ✅ Splendour Server Sync
- ✅ Ceramica Impex Server Sync  
- ✅ Wallcano Server Sync (added March 2026)
- ✅ Verona Browser Extension (added March 2026)

**What Gets EXCLUDED:**
- Adhesives, grout, sealants
- Tools (trowels, cutters, blades)
- Installation products (levelling, underlay, membranes)
- Cleaning/maintenance products
- Heating mats, thermostats
- Safety equipment

**What Gets INCLUDED:**
- All tiles (wall, floor, mosaic, porcelain, ceramic, etc.)
- **Flooring products** (SPC, LVT, laminate, vinyl, herringbone, parquet)
- **Flooring accessories**
- Cladding, splitface
- Natural stone (marble, slate, travertine, etc.)

### Sync Phases & Real-Time Display (March 2026)

**Phase 1: Discovery (0-25% progress)**
- Scans all categories and subcategories
- UI displays: `"{progress}% | {products_found} found"`
- No products appear in staging tables yet
- This phase finds ALL products before syncing

**Phase 2: Syncing (25-100% progress)**  
- Visits each product page and extracts full data
- UI displays: `"{progress}% | {products_synced} synced"`
- Products appear in tables in **real-time** as they're synced
- Current product being synced shown with image preview

**Real-Time Table Updates:**
- Frontend polls sync status every 2 seconds
- During syncing phase, staging tables refresh automatically
- Products appear in "Existing Product Updates" or "New Products Detected" as they're saved
- No need to wait for sync completion to see results

**Why "0 synced" at 17%?**
- At 17%, sync is still in **discovery phase** (scanning categories)
- This is normal - must find ALL products before syncing them
- Products will start appearing once progress reaches ~25%

---

## Data Flow

```
Supplier Portal
      ↓
[Sync Service] → Images → [R2 Uploader] → Cloudflare R2
      ↓
supplier_products (staging)
      ↓
[Publish to Website]
      ↓
tiles (live collection)
      ↓
Website Display
```

---

*Last Updated: March 2, 2026*
*Version: 3.8 - Fixed double price calculation, added unique product naming system for all suppliers*

---

## Search-Based Product Discovery

### Overview
All supplier sync services now include a search-based discovery feature that searches for known product series names to catch products that might be missed by category navigation.

### How It Works
1. After category-based sync completes, the system searches for known series names
2. Results are deduplicated against already-found products
3. New products are added to the sync

### Known Series Names
Series names are centralized in `/app/backend/business_config/business_rules.py`:

- **KNOWN_SERIES_NAMES**: 80+ series names including Italian cities, stone types, effects, patterns
- **SUPPLIER_SPECIFIC_SERIES**: Additional series names specific to each supplier

### Adding New Series Names
When you notice products missing from sync, add the series name to:

```python
# In business_rules.py

# Global series names (searched for all suppliers)
KNOWN_SERIES_NAMES = [
    "YourNewSeries",  # Add here
    ...
]

# Or supplier-specific series
SUPPLIER_SPECIFIC_SERIES = {
    "Wallcano": ["WallcanoSeries", ...],
    "Splendour": ["SplendourSeries", ...],
    "Ceramica Impex": ["CeramicaSeries", ...],
}
```

### Supported Suppliers
| Supplier | Search Feature | Series Count |
|----------|---------------|--------------|
| Wallcano | ✅ Active | 80+ |
| Splendour | ✅ Active | 80+ |
| Ceramica Impex | ✅ Active | 80+ |
| Verona | ❌ Extension Only | N/A |

*Last Updated: March 5, 2026*
*Version: 3.9 - Added search-based product discovery for all suppliers*

---

## CRITICAL: Production Debugging Protocol

### MANDATORY FOR ALL AGENTS

When investigating ANY issue reported by the user:

1. **NEVER rely on preview environment** - It has different/empty data
2. **ALWAYS query PRODUCTION API directly** to see real data

### Production URLs
- **Frontend**: `https://carefree-friendship-production-ee2b.up.railway.app`
- **Backend API**: `https://tile-station-production.up.railway.app`

### Debug Commands

```bash
# Login to production
PROD_API="https://tile-station-production.up.railway.app"
TOKEN=$(curl -s -X POST "$PROD_API/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"qasim@tilestation.co.uk","password":"Tilestation_9614"}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")

# Query any endpoint
curl -s "$PROD_API/api/ENDPOINT" -H "Authorization: Bearer $TOKEN"
```

### Why This Matters
- Preview environment connects to a different database
- Production has real invoices, real refunds, real data
- Numbers that "don't match" can only be debugged by checking production data
- User screenshots are from PRODUCTION - compare API responses to what they see

### Example Investigation Flow
1. User reports: "Dashboard shows £601 but Invoice History shows £376"
2. Query production: `curl -s "$PROD_API/api/analytics/showrooms-breakdown" ...`
3. Query refunds: `curl -s "$PROD_API/api/refunds" ...`
4. Find discrepancy (e.g., £225 refund not subtracted)
5. Fix the code
6. Deploy to production

*Last Updated: March 12, 2026*
*Version: 4.0 - Added mandatory production debugging protocol*

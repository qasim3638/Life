# Tile Station - Verona Sync Extension v2.3

Chrome extension to sync product data from Verona Group trade portal to Tile Station.

## What's Fixed in v2.3

1. **Finds ALL products on page** - Now correctly detects all 12 products per page (previously only found 4-6)
2. **Stock m² parsing** - Correctly captures both units AND square meters separately
   - Example: "In stock: 382 (34m²)" → stock_quantity=382, stock_m2=34
3. **Better data extraction** - Improved selectors for code, price, and stock
4. **Debug logging** - Console shows exactly what's being found and extracted

## Installation (IMPORTANT: Clean Install!)

1. **REMOVE OLD EXTENSION FIRST**
   - Go to `chrome://extensions/`
   - Find "Tile Station - Verona Sync" and click **Remove**
   
2. **Download and extract**
   - Unzip this file to a folder on your computer
   
3. **Enable Developer Mode**
   - Go to `chrome://extensions/`
   - Toggle "Developer mode" in top right
   
4. **Load the new extension**
   - Click "Load unpacked"
   - Select the `browser-extension` folder
   
5. **Verify version**
   - Click the extension icon
   - Popup should show **"Verona Stock Sync v2.3"**

## How to Use

1. **Login to Verona** - Go to https://veronagroup.co.uk and login to your trade account
2. **Navigate to Tiles** - Go to the Tiles category (should show "Showing 1-12 of XXX items")
3. **Click extension icon** - Opens the sync popup
4. **Click "Sync This Page (With stock & prices)"** - This will:
   - Find ALL product URLs on the page (should be 12)
   - Visit each product page
   - Extract: code, price per m², stock units, stock m²
   - Send data to Tile Station
5. **Wait for completion** - Watch progress: "Syncing 1/12... 2/12..." etc
6. **Go to next page** - Click "Next" on Verona website, then sync again

## Troubleshooting

### Only finding 4-6 products instead of 12?
- Make sure you're on a **listing page** (shows multiple products)
- The page should say "Showing 1-12 of XXX items"
- Try scrolling down the page before clicking sync

### Products have missing data (code/price/stock)?
1. Open Chrome DevTools (Press F12)
2. Click the **Console** tab
3. Sync a page
4. Look for lines starting with "=== Tile Station v2.3"
5. These logs show what the extension found

### Extension not working at all?
- Make sure you're logged into Verona
- Try refreshing the Verona page
- Check you installed v2.3 (not an older version)

## What Data is Captured

For each product:
- **Name** - Product title
- **Code/SKU** - e.g., D11197
- **Price** - Per m² price (e.g., £32.77)
- **Stock Quantity** - Number of units (e.g., 382)
- **Stock m²** - Square meters available (e.g., 34)
- **In Stock** - Yes/No status
- **Image** - Product photo URL

## Version History

- **v2.3** - Fixed product detection (finds all 12 products), improved data extraction
- **v2.2** - Fixed stock m² parsing
- **v2.1** - Added debug logging
- **v2.0** - Simplified to page-by-page sync
- **v1.x** - Initial versions with various issues

## Support

Contact Tile Station IT for support.

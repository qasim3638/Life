# TILE STATION - E-COMMERCE & STOCK MANAGEMENT PLANNING DOCUMENT

**Document Version:** 1.0  
**Created Date:** _______________  
**Last Updated:** _______________  
**Prepared By:** _______________

---

## TABLE OF CONTENTS

1. [Stock Structure Options](#1-stock-structure-options)
2. [3rd Party Supplier Integration](#2-3rd-party-supplier-integration)
3. [Product Mapping Strategy](#3-product-mapping-strategy)
4. [Web Scraping Full Catalog Sync](#4-web-scraping-full-catalog-sync)
5. [Supplier API Requirements](#5-supplier-api-requirements)
6. [Sync Schedule & Accuracy](#6-sync-schedule--accuracy)
7. [Implementation Priority & Timeline](#7-implementation-priority--timeline)
8. [Supplier Information Sheet](#8-supplier-information-sheet)

---

## 1. STOCK STRUCTURE OPTIONS

### 1.1 Current Stock Fields
| Field | Currently Exists | Notes |
|-------|------------------|-------|
| Total stock per product | ☐ Yes ☐ No | |
| Showroom allocations | ☐ Yes ☐ No | |
| Stock deduction on invoice | ☐ Yes ☐ No | |
| Low stock alerts | ☐ Yes ☐ No | |

### 1.2 Choose Your Stock Structure

#### OPTION A: Simplified Approach (Quick Implementation)
☐ **SELECT THIS OPTION**

| Field | Description | Your Decision |
|-------|-------------|---------------|
| `stock` | Total physical stock | ☐ Implement |
| `showroom_stock` | Qty per showroom | ☐ Implement |
| `ecommerce_available` | Stock for online sales | ☐ Implement |
| `reserved_online` | Reserved by pending orders | ☐ Implement |

**Notes:**
```
_____________________________________________________________________________
_____________________________________________________________________________
_____________________________________________________________________________
```

#### OPTION B: Advanced Warehouse Model (For Scaling)
☐ **SELECT THIS OPTION**

| Field | Description | Your Decision |
|-------|-------------|---------------|
| `warehouse_stock` | Main warehouse stock | ☐ Implement |
| `showroom_stock.{id}` | Stock per showroom | ☐ Implement |
| `in_transit` | Stock being transferred | ☐ Implement |
| `reserved` | Reserved for orders | ☐ Implement |
| `available_online` | Calculated available | ☐ Implement |

**Notes:**
```
_____________________________________________________________________________
_____________________________________________________________________________
_____________________________________________________________________________
```

### 1.3 Key Decisions

**Q1: Do you ship from warehouse or showrooms?**
☐ Warehouse only  
☐ Showrooms only  
☐ Both (need location-based fulfillment)

**Q2: Should online stock be separate or shared with showrooms?**
☐ Separate (safer - dedicated online pool)  
☐ Shared (more sales potential - real-time sync required)

**Q3: Should deposit orders reserve stock until fulfilled?**
☐ Yes - reserve stock immediately  
☐ No - first come first served

**Notes:**
```
_____________________________________________________________________________
_____________________________________________________________________________
_____________________________________________________________________________
```

---

## 2. 3RD PARTY SUPPLIER INTEGRATION

### 2.1 Integration Method Selection

| Method | Select | Pros | Cons |
|--------|--------|------|------|
| **API Integration** (Real-time) | ☐ | Accurate, automated | Requires supplier API |
| **Data Feed Import** (Scheduled) | ☐ | Simple, works with any supplier | Not real-time |
| **Web Scraping** (Last Resort) | ☐ | Works without supplier cooperation | Fragile, needs maintenance |

### 2.2 List Your Suppliers

| # | Supplier Name | Website URL | Integration Method | Priority |
|---|---------------|-------------|-------------------|----------|
| 1 | | | ☐ API ☐ Feed ☐ Scrape | ☐ High ☐ Medium ☐ Low |
| 2 | | | ☐ API ☐ Feed ☐ Scrape | ☐ High ☐ Medium ☐ Low |
| 3 | | | ☐ API ☐ Feed ☐ Scrape | ☐ High ☐ Medium ☐ Low |
| 4 | | | ☐ API ☐ Feed ☐ Scrape | ☐ High ☐ Medium ☐ Low |
| 5 | | | ☐ API ☐ Feed ☐ Scrape | ☐ High ☐ Medium ☐ Low |

### 2.3 Order Fulfillment Model

**Q1: How should orders be fulfilled when stock comes from supplier?**

☐ **DROPSHIP MODEL** - Supplier ships directly to customer
  - You keep the margin
  - No handling required
  - Best for: Large/heavy items, nationwide delivery

☐ **STOCK-TO-WAREHOUSE MODEL** - Supplier delivers to you first
  - Quality control possible
  - Can bundle orders
  - Best for: Local delivery, mixed orders

☐ **HYBRID MODEL** - Mix of both depending on product/situation

**Notes:**
```
_____________________________________________________________________________
_____________________________________________________________________________
_____________________________________________________________________________
```

---

## 3. PRODUCT MAPPING STRATEGY

### 3.1 Branding Approach

**Do you want to use your own product names and pricing?**
☐ Yes - Full rebranding (your name, your price, your images)  
☐ Partial - Your price only (keep supplier names)  
☐ No - Use supplier details as-is

### 3.2 Product Mapping Example

| Your SKU | Your Product Name | Your Price | Supplier SKU | Supplier Name | Cost Price |
|----------|-------------------|------------|--------------|---------------|------------|
| *Example:* TS-MARBLE-60 | Premium White Marble 60x60 | £34.99 | SUP-MAR-6060 | Italian Carrara Marble | £22.00 |
| | | £ | | | £ |
| | | £ | | | £ |
| | | £ | | | £ |

### 3.3 Pricing Strategy

**How will you set your prices?**
☐ Fixed markup percentage: _______% (e.g., 40%)  
☐ Fixed markup amount: £_______ per item  
☐ Manual pricing for each product  
☐ Tiered markup based on product category

**Price Calculation Formula:**
```
Your Price = Supplier Cost × _______ (e.g., 1.4 for 40% markup)

OR

Your Price = Supplier Cost + £_______ fixed amount
```

### 3.4 Content Management

**For each mapped product, what will you customize?**
| Content | Use Your Own | Use Supplier's | Mix Both |
|---------|--------------|----------------|----------|
| Product Name | ☐ | ☐ | ☐ |
| SKU Code | ☐ | ☐ | ☐ |
| Description | ☐ | ☐ | ☐ |
| Images | ☐ | ☐ | ☐ |
| Specifications | ☐ | ☐ | ☐ |
| Categories | ☐ | ☐ | ☐ |

**Notes:**
```
_____________________________________________________________________________
_____________________________________________________________________________
_____________________________________________________________________________
```

---

## 4. WEB SCRAPING FULL CATALOG SYNC

### 4.1 Data to Scrape

**Select what data you want to import from supplier websites:**

| Data Field | Import? | Priority | Notes |
|------------|---------|----------|-------|
| Product Name | ☐ Yes ☐ No | ☐ Essential ☐ Nice to have | |
| SKU/Product Code | ☐ Yes ☐ No | ☐ Essential ☐ Nice to have | |
| Price | ☐ Yes ☐ No | ☐ Essential ☐ Nice to have | |
| Stock Status | ☐ Yes ☐ No | ☐ Essential ☐ Nice to have | |
| Stock Quantity | ☐ Yes ☐ No | ☐ Essential ☐ Nice to have | |
| Description | ☐ Yes ☐ No | ☐ Essential ☐ Nice to have | |
| Images | ☐ Yes ☐ No | ☐ Essential ☐ Nice to have | |
| Categories | ☐ Yes ☐ No | ☐ Essential ☐ Nice to have | |
| Specifications | ☐ Yes ☐ No | ☐ Essential ☐ Nice to have | |
| Size/Dimensions | ☐ Yes ☐ No | ☐ Essential ☐ Nice to have | |
| m² per box | ☐ Yes ☐ No | ☐ Essential ☐ Nice to have | |
| Pieces per box | ☐ Yes ☐ No | ☐ Essential ☐ Nice to have | |

### 4.2 Import Workflow Preferences

**When new products are scraped, how should they be handled?**

☐ Auto-publish to website immediately  
☐ Save as draft - require manual review before publishing  
☐ Auto-publish only if mapped to existing category  
☐ Send notification for manual approval

**When existing products are updated, how should changes be handled?**

☐ Auto-update all fields  
☐ Auto-update stock and price only (preserve my custom name/description)  
☐ Notify me of changes but don't auto-update  

**When products disappear from supplier website:**

☐ Auto-mark as discontinued on my website  
☐ Auto-hide but keep in database  
☐ Notify me but take no action

**Notes:**
```
_____________________________________________________________________________
_____________________________________________________________________________
_____________________________________________________________________________
```

---

## 5. SUPPLIER API REQUIREMENTS

*Use this section if any supplier offers API access*

### 5.1 Information to Request from Supplier

**Email/Letter Template - Copy and customize:**

```
Subject: API Access Request for Stock Integration - [YOUR COMPANY NAME]

Dear [SUPPLIER NAME] Team,

We are looking to integrate your product catalog and stock levels 
directly into our system for seamless inventory management.

Could you please provide the following:

1. API CREDENTIALS
   - API Key / Client ID
   - API Secret / Token  
   - Our Account/Customer ID
   - Any IP whitelist requirements

2. DOCUMENTATION
   - API documentation link
   - Postman collection (if available)
   - Sample code or integration guide

3. AVAILABLE ENDPOINTS
   Please confirm if these are available:
   - Product catalog (GET all products)
   - Stock/inventory levels
   - Pricing information
   - Order placement

4. DATA FIELDS
   We specifically need:
   - SKU / Product Code
   - Product Name
   - Stock Quantity
   - Price (trade price)
   - Product specifications

5. REAL-TIME UPDATES
   - Do you support webhooks for instant stock updates?
   - If not, what's the recommended polling frequency?

6. RATE LIMITS
   - Requests per minute/hour limits
   - Bulk endpoints available?

7. TESTING
   - Is a sandbox environment available?

8. SUPPORT
   - Technical contact for integration issues

Please let us know if you have any questions.

Best regards,
[YOUR NAME]
[YOUR COMPANY]
[YOUR EMAIL]
[YOUR PHONE]
```

### 5.2 API Credentials Tracking

| Supplier | API Key | API Secret | Account ID | Base URL | Doc URL | Status |
|----------|---------|------------|------------|----------|---------|--------|
| | | | | | | ☐ Pending ☐ Received ☐ Active |
| | | | | | | ☐ Pending ☐ Received ☐ Active |
| | | | | | | ☐ Pending ☐ Received ☐ Active |

---

## 6. SYNC SCHEDULE & ACCURACY

### 6.1 Sync Frequency Selection

**Choose your preferred sync schedule:**

| Sync Type | Time | Frequency | Select |
|-----------|------|-----------|--------|
| **Full Catalog Sync** | | ☐ Daily ☐ Weekly | ☐ |
| (All products, stock, prices) | Preferred time: _______ | | |
| **Stock & Price Only** | | ☐ Every 4 hrs ☐ Every 6 hrs ☐ Every 12 hrs | ☐ |
| (Quick update) | Preferred time: _______ | | |
| **Manual Trigger** | | As needed | ☐ |
| (Before promotions) | | | |

**Recommended: Daily Full Sync at 00:30 AM (Midnight)**
☐ Accept recommended schedule  
☐ Custom schedule: _______________________

### 6.2 Stock Safety Measures

**Stock Buffer - To prevent overselling:**

☐ No buffer (show exact supplier stock)  
☐ 5% buffer  
☐ 10% buffer (Recommended)  
☐ 15% buffer  
☐ Fixed buffer: _______ units  

**Stock Display Rules:**

| Supplier Stock Level | Display to Customer | Select |
|---------------------|---------------------|--------|
| 50+ units | ☐ "In Stock" ☐ Show exact number | ☐ |
| 20-49 units | ☐ "In Stock" ☐ "Limited Stock" | ☐ |
| 10-19 units | ☐ "Limited Stock" ☐ "Low Stock" | ☐ |
| 1-9 units | ☐ "Low Stock" ☐ "Only X left" | ☐ |
| 0 units | ☐ "Out of Stock" ☐ Hide product | ☐ |

### 6.3 Order Verification Process

**When customer places an order, how should stock be verified?**

☐ Auto-confirm immediately (trust sync data)  
☐ Hold order, quick automated verification with supplier, then confirm  
☐ Hold order, manual verification required, then confirm  
☐ Different process based on order size:
  - Small orders (under £_______): _______________
  - Large orders (over £_______): _______________

**Notes:**
```
_____________________________________________________________________________
_____________________________________________________________________________
_____________________________________________________________________________
```

---

## 7. IMPLEMENTATION PRIORITY & TIMELINE

### 7.1 Phase Planning

#### PHASE 1: Foundation (Priority: HIGH)
Target Start Date: _______________

| Task | Include? | Priority | Status |
|------|----------|----------|--------|
| Add `ecommerce_stock` field | ☐ Yes ☐ No | ☐ High ☐ Medium | ☐ Not Started ☐ In Progress ☐ Done |
| Add `reserved_stock` field | ☐ Yes ☐ No | ☐ High ☐ Medium | ☐ Not Started ☐ In Progress ☐ Done |
| Stock buffer implementation | ☐ Yes ☐ No | ☐ High ☐ Medium | ☐ Not Started ☐ In Progress ☐ Done |
| Stock status display rules | ☐ Yes ☐ No | ☐ High ☐ Medium | ☐ Not Started ☐ In Progress ☐ Done |

#### PHASE 2: Supplier Integration (Priority: MEDIUM)
Target Start Date: _______________

| Task | Include? | Priority | Status |
|------|----------|----------|--------|
| Web scraper for Supplier 1 | ☐ Yes ☐ No | ☐ High ☐ Medium | ☐ Not Started ☐ In Progress ☐ Done |
| Web scraper for Supplier 2 | ☐ Yes ☐ No | ☐ High ☐ Medium | ☐ Not Started ☐ In Progress ☐ Done |
| Product mapping UI | ☐ Yes ☐ No | ☐ High ☐ Medium | ☐ Not Started ☐ In Progress ☐ Done |
| Daily sync automation | ☐ Yes ☐ No | ☐ High ☐ Medium | ☐ Not Started ☐ In Progress ☐ Done |

#### PHASE 3: Advanced Features (Priority: LOW)
Target Start Date: _______________

| Task | Include? | Priority | Status |
|------|----------|----------|--------|
| Stock reservation system | ☐ Yes ☐ No | ☐ High ☐ Medium | ☐ Not Started ☐ In Progress ☐ Done |
| Auto-release reserved stock | ☐ Yes ☐ No | ☐ High ☐ Medium | ☐ Not Started ☐ In Progress ☐ Done |
| Multi-supplier per product | ☐ Yes ☐ No | ☐ High ☐ Medium | ☐ Not Started ☐ In Progress ☐ Done |
| Unified stock dashboard | ☐ Yes ☐ No | ☐ High ☐ Medium | ☐ Not Started ☐ In Progress ☐ Done |

### 7.2 Additional Features to Consider

| Feature | Want This? | Priority | Notes |
|---------|------------|----------|-------|
| Auto-replenishment suggestions | ☐ Yes ☐ No ☐ Maybe | ☐ High ☐ Medium ☐ Low | |
| Sales channel analytics | ☐ Yes ☐ No ☐ Maybe | ☐ High ☐ Medium ☐ Low | |
| Supplier performance tracking | ☐ Yes ☐ No ☐ Maybe | ☐ High ☐ Medium ☐ Low | |
| Automatic reordering | ☐ Yes ☐ No ☐ Maybe | ☐ High ☐ Medium ☐ Low | |
| Price change alerts | ☐ Yes ☐ No ☐ Maybe | ☐ High ☐ Medium ☐ Low | |
| New product alerts | ☐ Yes ☐ No ☐ Maybe | ☐ High ☐ Medium ☐ Low | |

**Notes:**
```
_____________________________________________________________________________
_____________________________________________________________________________
_____________________________________________________________________________
```

---

## 8. SUPPLIER INFORMATION SHEET

*Complete one sheet per supplier*

---

### SUPPLIER #1

**Basic Information:**
| Field | Details |
|-------|---------|
| Supplier Name | |
| Website URL | |
| Account Manager | |
| Email | |
| Phone | |
| Your Account/Customer Number | |

**Integration Method:**
☐ API Integration  
☐ Data Feed (CSV/Excel)  
☐ Web Scraping

**Product Categories from this Supplier:**
☐ Floor Tiles  
☐ Wall Tiles  
☐ Outdoor Tiles  
☐ Mosaics  
☐ Bathroom  
☐ Other: _____________

**Approximate Number of Products:** _____________

**API Details (if applicable):**
| Field | Value |
|-------|-------|
| API Key | |
| API Secret | |
| Base URL | |
| Documentation URL | |
| Rate Limits | |
| Sandbox Available? | ☐ Yes ☐ No |

**Scraping Details (if applicable):**
| Field | Value |
|-------|-------|
| Products Page URL | |
| Login Required? | ☐ Yes ☐ No |
| Shows Stock Quantity? | ☐ Yes ☐ No ☐ Status Only |
| Sync Frequency | |

**Notes:**
```
_____________________________________________________________________________
_____________________________________________________________________________
_____________________________________________________________________________
```

---

### SUPPLIER #2

**Basic Information:**
| Field | Details |
|-------|---------|
| Supplier Name | |
| Website URL | |
| Account Manager | |
| Email | |
| Phone | |
| Your Account/Customer Number | |

**Integration Method:**
☐ API Integration  
☐ Data Feed (CSV/Excel)  
☐ Web Scraping

**Product Categories from this Supplier:**
☐ Floor Tiles  
☐ Wall Tiles  
☐ Outdoor Tiles  
☐ Mosaics  
☐ Bathroom  
☐ Other: _____________

**Approximate Number of Products:** _____________

**API Details (if applicable):**
| Field | Value |
|-------|-------|
| API Key | |
| API Secret | |
| Base URL | |
| Documentation URL | |
| Rate Limits | |
| Sandbox Available? | ☐ Yes ☐ No |

**Scraping Details (if applicable):**
| Field | Value |
|-------|-------|
| Products Page URL | |
| Login Required? | ☐ Yes ☐ No |
| Shows Stock Quantity? | ☐ Yes ☐ No ☐ Status Only |
| Sync Frequency | |

**Notes:**
```
_____________________________________________________________________________
_____________________________________________________________________________
_____________________________________________________________________________
```

---

### SUPPLIER #3

**Basic Information:**
| Field | Details |
|-------|---------|
| Supplier Name | |
| Website URL | |
| Account Manager | |
| Email | |
| Phone | |
| Your Account/Customer Number | |

**Integration Method:**
☐ API Integration  
☐ Data Feed (CSV/Excel)  
☐ Web Scraping

**Product Categories from this Supplier:**
☐ Floor Tiles  
☐ Wall Tiles  
☐ Outdoor Tiles  
☐ Mosaics  
☐ Bathroom  
☐ Other: _____________

**Approximate Number of Products:** _____________

**API Details (if applicable):**
| Field | Value |
|-------|-------|
| API Key | |
| API Secret | |
| Base URL | |
| Documentation URL | |
| Rate Limits | |
| Sandbox Available? | ☐ Yes ☐ No |

**Scraping Details (if applicable):**
| Field | Value |
|-------|-------|
| Products Page URL | |
| Login Required? | ☐ Yes ☐ No |
| Shows Stock Quantity? | ☐ Yes ☐ No ☐ Status Only |
| Sync Frequency | |

**Notes:**
```
_____________________________________________________________________________
_____________________________________________________________________________
_____________________________________________________________________________
```

---

## SUMMARY OF DECISIONS

*Fill this section once you've made all decisions above*

### Stock Structure
- Chosen approach: ☐ Simplified ☐ Advanced Warehouse
- Ship from: ☐ Warehouse ☐ Showrooms ☐ Both
- Online stock: ☐ Separate pool ☐ Shared

### Supplier Integration  
- Number of suppliers to integrate: _______
- Primary method: ☐ API ☐ Data Feed ☐ Web Scraping
- Fulfillment model: ☐ Dropship ☐ Stock-to-Warehouse ☐ Hybrid

### Product Mapping
- Branding: ☐ Full rebrand ☐ Partial ☐ Use supplier details
- Pricing: ☐ Fixed markup ____% ☐ Manual pricing

### Sync Schedule
- Full sync: _______ (time) / _______ (frequency)
- Stock buffer: _______%
- Order verification: ☐ Auto ☐ Manual ☐ Hybrid

### Implementation Priority
- Phase 1 start: _______________
- Phase 2 start: _______________
- Phase 3 start: _______________

---

## DOCUMENT HISTORY

| Version | Date | Changes Made | Updated By |
|---------|------|--------------|------------|
| 1.0 | | Initial document | |
| | | | |
| | | | |

---

**END OF DOCUMENT**

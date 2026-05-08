"""
Captures cropped screenshots of EVERY operational page used in the
comprehensive staff training booklet — both EPOS/admin and storefront.

Output: /app/checklists/training_screens/<slug>.png
"""
import asyncio
import os
from pathlib import Path

from playwright.async_api import async_playwright

OUT_DIR = Path("/app/checklists/training_screens")
OUT_DIR.mkdir(parents=True, exist_ok=True)

BASE = os.environ.get("PUBLIC_PREVIEW_URL", "https://feature-verification-7.preview.emergentagent.com")
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"

# Storefront (public, captured BEFORE login)
STOREFRONT_PAGES = [
    ("01_storefront_home",       "/shop"),
    ("02_storefront_catalog",    "/shop/tiles"),
    ("03_storefront_pdp",        "/shop/tiles/alabaster-polished-60x60cm"),
    ("04_storefront_calculator", "/shop/calculator"),
    ("05_storefront_samples",    "/shop/tile-samples"),
    ("06_storefront_sample_svc", "/shop/sample-service"),
    ("07_storefront_cart",       "/shop/tile-cart"),
    ("08_storefront_wishlist",   "/shop/tile-wishlist"),
    ("09_storefront_compare",    "/shop/compare"),
    ("10_storefront_checkout",   "/shop/tile-checkout"),
    ("11_storefront_track",      "/shop/track"),
    ("12_storefront_login",      "/shop/tile-login"),
    ("13_storefront_register",   "/shop/tile-register"),
    ("14_storefront_trade_reg",  "/shop/trade/register"),
    ("15_storefront_trade_login","/shop/trade/login"),
    ("16_storefront_refer",      "/shop/refer"),
    ("17_storefront_contact",    "/shop/contact"),
    ("18_storefront_returns",    "/shop/info/returns"),
    ("19_storefront_delivery",   "/shop/info/delivery"),
    ("20_storefront_faq",        "/shop/info/faq"),
]

# Admin/EPOS (captured AFTER login)
ADMIN_PAGES = [
    ("30_admin_dashboard",       "/admin"),
    ("31_sales_hub",             "/admin/sales-hub"),
    ("32_epos_till",             "/admin/epos"),
    ("33_cash_counter",          "/admin/cash-counter"),
    ("34_store_dashboard",       "/admin/showroom-dashboard"),
    ("35_invoices",              "/admin/invoices"),
    ("36_quotations",            "/admin/quotations"),
    ("37_refunds",                "/admin/refunds"),
    ("38_orders",                "/admin/orders"),
    ("39_online_orders",         "/admin/online-orders"),
    ("40_calculator_admin",      "/admin/calculator"),
    ("41_products_hub",          "/admin/products-hub"),
    ("42_supplier_products",     "/admin/supplier-products"),
    ("43_supplier_health",       "/admin/supplier-health"),
    ("44_sync_hub",              "/admin/sync-hub"),
    ("45_stock_hub",             "/admin/stock-hub"),
    ("46_stock_allocation",      "/admin/stock-allocation"),
    ("47_bulk_stock",            "/admin/bulk-stock"),
    ("48_delivery_check_in",     "/admin/delivery-check-in"),
    ("49_stock_transfers",       "/admin/stock-transfers"),
    ("50_reorder_suggestions",   "/admin/reorder-suggestions"),
    ("51_batch_tracking",        "/admin/batch-tracking"),
    ("52_to_order",              "/admin/to-order"),
    ("53_stocktake",             "/admin/stocktake-report"),
    ("54_delivery_mgmt",         "/admin/delivery-management"),
    ("55_customers_hub",         "/admin/customers-hub"),
    ("56_trade_accounts",        "/admin/trade-accounts"),
    ("57_customer_pricing",      "/admin/pricing"),
    ("58_invites",               "/admin/invites"),
    ("59_inquiries",             "/admin/inquiries"),
    ("60_communication_hub",     "/admin/communication-hub"),
    ("61_staff_chat",            "/admin/chat"),
    ("62_tasks",                 "/admin/tasks"),
    ("63_inbox",                 "/admin/inbox"),
    ("64_send_email",            "/admin/email"),
    ("65_marketing",             "/admin/marketing"),
    ("66_abandoned_baskets",     "/admin/abandoned-baskets"),
    ("67_promo_codes",           "/admin/promo-codes"),
    ("68_reports_hub",           "/admin/reports-hub"),
    ("69_analytics",             "/admin/analytics"),
    ("70_sales_reports",         "/admin/reports"),
    ("71_maintenance",           "/admin/maintenance"),
]


async def login(page):
    await page.goto(f"{BASE}/admin/login", wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(2000)
    await page.fill('input[type="email"]', ADMIN_EMAIL)
    await page.fill('input[type="password"]', ADMIN_PASSWORD)
    await page.click('button[type="submit"]')
    await page.wait_for_timeout(4000)
    print(f"  ✓ logged in (now at {page.url})")


async def capture(page, slug, path, w=1440, h=850):
    out = OUT_DIR / f"{slug}.png"
    if out.exists():
        return  # skip if already captured (allow resume)
    print(f"  → {slug:30s} {path}")
    try:
        await page.set_viewport_size({"width": w, "height": h})
        await page.goto(f"{BASE}{path}", wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(2200)
        await page.add_style_tag(content="""
            ::-webkit-scrollbar { display: none; }
            [data-testid='maintenance-banner'], .cookie-banner, .toast { display: none !important; }
        """)
        await page.screenshot(path=str(out), full_page=False)
        size_kb = out.stat().st_size / 1024
        print(f"     ✓ ({size_kb:.0f} KB)")
    except Exception as e:
        print(f"     ✗ {str(e)[:80]}")


async def main():
    print(f"Base URL: {BASE}\nOutput: {OUT_DIR}\n")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(args=["--no-sandbox"])
        ctx = await browser.new_context(
            viewport={"width": 1440, "height": 850},
            ignore_https_errors=True,
        )
        page = await ctx.new_page()

        print("[1/2] Storefront pages (no auth)...")
        for slug, path in STOREFRONT_PAGES:
            w = 1280  # storefront fits a narrower viewport better
            await capture(page, slug, path, w=w, h=850)

        print("\n[2/2] Admin / EPOS pages...")
        await login(page)
        for slug, path in ADMIN_PAGES:
            await capture(page, slug, path, w=1440, h=850)

        await browser.close()
    print(f"\nDone. {len(list(OUT_DIR.glob('*.png')))} images.")


if __name__ == "__main__":
    asyncio.run(main())

"""
Verona Group Scraper
Scrapes products, images, prices, and stock levels from veronagroup.co.uk

Uses Bright Data residential proxy to bypass Cloudflare protection.
"""
import asyncio
import re
import json
import os
from typing import Dict, List, Optional
import logging

# Optional Playwright import - may not be available on all deployments
try:
    from playwright.async_api import async_playwright, Page, Browser
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    async_playwright = None
    Page = None
    Browser = None

from .base_scraper import BaseScraper, SupplierProduct

logger = logging.getLogger(__name__)


class VeronaScraper(BaseScraper):
    """Scraper for Verona Group B2B portal"""
    
    SUPPLIER_NAME = "Verona"
    BASE_URL = "https://veronagroup.co.uk"
    LOGIN_URL = "https://veronagroup.co.uk/customer/account/login"
    TILES_URL = "https://veronagroup.co.uk/tiles"
    
    # Proxy config path
    PROXY_CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'supplier_data', 'brightdata_proxy.json')
    
    def __init__(self, email: str, password: str):
        super().__init__(email, password)
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.playwright = None
        self.proxy_config = self._load_proxy_config()
    
    def _load_proxy_config(self) -> Optional[dict]:
        """Load Bright Data proxy configuration"""
        try:
            config_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                '..', '..', 'supplier_data', 'brightdata_proxy.json'
            )
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    return json.load(f)
            logger.warning("Bright Data proxy config not found")
            return None
        except Exception as e:
            logger.error(f"Error loading proxy config: {e}")
            return None
    
    async def _init_browser(self):
        """Initialize Playwright browser with Bright Data proxy"""
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("Playwright is not installed. Please install it with: pip install playwright && playwright install chromium")
        self.playwright = await async_playwright().start()
        
        # Configure proxy if available
        proxy = None
        if self.proxy_config:
            host = self.proxy_config['host']
            port = self.proxy_config['port']
            username = self.proxy_config['username']
            password = self.proxy_config['password']
            
            # Target UK IPs for better results with UK sites
            username_uk = f'{username}-country-gb'
            
            proxy = {
                'server': f'http://{host}:{port}',
                'username': username_uk,
                'password': password
            }
            logger.info("Using Bright Data residential proxy with UK targeting")
        
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            proxy=proxy
        )
        
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            ignore_https_errors=True  # Required for proxy
        )
        self.page = await self.context.new_page()
    
    async def _close_browser(self):
        """Close browser"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def login(self) -> bool:
        """Login to Verona portal"""
        try:
            if not self.page:
                await self._init_browser()
            
            # Go to login page
            await self.page.goto(self.LOGIN_URL, timeout=60000)
            await asyncio.sleep(5)  # Wait for Cloudflare
            await self.page.wait_for_load_state("networkidle")
            
            # Fill login form
            email_input = await self.page.query_selector('input[type="email"], input[name="email"]')
            if email_input:
                await email_input.fill(self.email)
                
                password_input = await self.page.query_selector('input[type="password"]')
                if password_input:
                    await password_input.fill(self.password)
                    
                    # Submit
                    submit_btn = await self.page.query_selector('button[type="submit"]')
                    if submit_btn:
                        await submit_btn.click()
                        await asyncio.sleep(3)
                        await self.page.wait_for_load_state("networkidle")
            
            # Check if logged in by looking for account indicators
            if "login" not in self.page.url.lower():
                self.is_authenticated = True
                logger.info("Successfully logged in to Verona")
                return True
            
            logger.error("Failed to login to Verona")
            return False
            
        except Exception as e:
            logger.error(f"Verona login error: {e}")
            return False
    
    async def get_all_products(self) -> List[SupplierProduct]:
        """Fetch all products from Verona"""
        if not self.is_authenticated:
            if not await self.login():
                return []
        
        products = []
        
        try:
            # Go to tiles catalog
            await self.page.goto(f"{self.BASE_URL}/tiles", timeout=60000)
            await self.page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)
            
            # Get total product count
            body_text = await self.page.inner_text('body')
            count_match = re.search(r'of\s+(\d+)\s+items', body_text)
            total_products = int(count_match.group(1)) if count_match else 0
            logger.info(f"Verona has {total_products} products")
            
            # Scrape products page by page
            page_num = 1
            while True:
                logger.info(f"Scraping page {page_num}")
                
                # Get products on current page
                page_products = await self._scrape_product_listing()
                if not page_products:
                    break
                
                products.extend(page_products)
                
                # Check for next page
                next_btn = await self.page.query_selector('a[rel="next"], .next a, a:has-text("Next")')
                if next_btn:
                    await next_btn.click()
                    await asyncio.sleep(2)
                    await self.page.wait_for_load_state("networkidle")
                    page_num += 1
                else:
                    break
                
                # Safety limit
                if page_num > 100:
                    break
            
            self.products = products
            logger.info(f"Total products scraped from Verona: {len(products)}")
            return products
            
        except Exception as e:
            logger.error(f"Error fetching Verona products: {e}")
            return []
        finally:
            await self._close_browser()
    
    async def _scrape_product_listing(self) -> List[SupplierProduct]:
        """Scrape products from current listing page"""
        products = []
        
        # Find all product cards
        product_cards = await self.page.query_selector_all('[class*="product"], .product-item')
        
        for card in product_cards:
            try:
                # Get product link
                link = await card.query_selector('a[href*="/d"]')
                if not link:
                    continue
                
                href = await link.get_attribute('href')
                
                # Get product name
                name_elem = await card.query_selector('h2, h3, .product-name, .product-title')
                name = await name_elem.inner_text() if name_elem else ""
                
                # Get price
                price_elem = await card.query_selector('[class*="price"]')
                price_text = await price_elem.inner_text() if price_elem else ""
                price_match = re.search(r'£([\d.]+)', price_text)
                price = float(price_match.group(1)) if price_match else 0
                
                # Navigate to product detail to get stock
                product = await self._scrape_product_detail(href)
                if product:
                    products.append(product)
                
                await asyncio.sleep(0.3)  # Rate limiting
                
            except Exception as e:
                logger.error(f"Error scraping product card: {e}")
                continue
        
        return products
    
    async def _scrape_product_detail(self, url: str) -> Optional[SupplierProduct]:
        """Scrape product detail page"""
        try:
            await self.page.goto(url, timeout=30000)
            await self.page.wait_for_load_state("networkidle")
            await asyncio.sleep(1)
            
            body_text = await self.page.inner_text('body')
            
            # Extract product name
            h1 = await self.page.query_selector('h1')
            name = await h1.inner_text() if h1 else ""
            
            # Extract code
            code_match = re.search(r'Code[:\s]*([A-Z0-9]+)', body_text, re.I)
            code = code_match.group(1) if code_match else ""
            
            # Extract stock (e.g., "In stock: 7488 (84m²)")
            stock_match = re.search(r'In stock[:\s]*(\d+)\s*\((\d+(?:\.\d+)?)\s*m', body_text, re.I)
            if stock_match:
                stock_pieces = int(stock_match.group(1))
                stock_sqm = float(stock_match.group(2))
            else:
                stock_pieces = 0
                stock_sqm = 0
            
            # Extract price per m²
            price_match = re.search(r'£([\d.]+)\s*per\s*m', body_text, re.I)
            price_per_sqm = float(price_match.group(1)) if price_match else 0
            
            # Extract size
            size_match = re.search(r'Size[:\s]*(\d+)\s*x\s*(\d+)', body_text, re.I)
            size = f"{size_match.group(1)}x{size_match.group(2)}" if size_match else ""
            
            # Extract material
            material = "Porcelain"
            material_match = re.search(r'Material[:\s]*([A-Za-z\s]+)', body_text)
            if material_match:
                material = material_match.group(1).strip()
            
            # Extract finish
            finish_match = re.search(r'Finish[:\s]*([A-Za-z\s]+)', body_text)
            finish = finish_match.group(1).strip() if finish_match else ""
            
            # Extract thickness
            thickness_match = re.search(r'Thickness[:\s]*(\d+)', body_text)
            thickness = f"{thickness_match.group(1)}mm" if thickness_match else ""
            
            # Extract images
            images = []
            img_elements = await self.page.query_selector_all('img[src*="product"], img[src*="tile"]')
            for img in img_elements:
                src = await img.get_attribute('src')
                if src and 'thumb' not in src.lower():
                    if not src.startswith('http'):
                        src = self.BASE_URL + src
                    images.append(src)
            
            product = SupplierProduct(
                supplier_code=code,
                supplier_name=self.SUPPLIER_NAME,
                name=name,
                size=size,
                material=material,
                finish=finish,
                thickness=thickness,
                room_lot_price=price_per_sqm,
                stock_sqm=stock_sqm,
                stock_status="In Stock" if stock_sqm >= 20 else ("Low Stock" if stock_sqm > 0 else "Out of Stock"),
                images=images[:5],
                extra_data={"url": url, "stock_pieces": stock_pieces}
            )
            
            logger.info(f"Scraped: {name} ({code}) - Stock: {stock_sqm}m²")
            return product
            
        except Exception as e:
            logger.error(f"Error scraping product detail {url}: {e}")
            return None
    
    async def get_product_details(self, product_id: str) -> Optional[SupplierProduct]:
        """Get detailed information for a single product"""
        pass
    
    async def get_stock_levels(self) -> Dict[str, float]:
        """Get current stock levels for all products"""
        stock_levels = {}
        for product in self.products:
            stock_levels[product.supplier_code] = product.stock_sqm
        return stock_levels


# Test function
async def test_verona_scraper():
    """Test the Verona scraper"""
    scraper = VeronaScraper(
        email="accounts@tilestation.co.uk",
        password=os.environ.get("VERONA_PORTAL_PASSWORD", "")
    )
    
    print("Testing Verona scraper...")
    if await scraper.login():
        print("Login successful!")
    else:
        print("Login failed")


if __name__ == "__main__":
    asyncio.run(test_verona_scraper())

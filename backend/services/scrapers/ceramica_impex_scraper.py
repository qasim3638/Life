"""
Ceramica Impex Scraper - HTTPX Version (No Playwright Required)
Scrapes products, images, prices, and stock levels from portal.ceramicaimpex.co.uk
Product data is stored in JSON on the listing page, making extraction efficient!
"""
import asyncio
import os
import re
import json
import httpx
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
import logging

from .base_scraper import BaseScraper, SupplierProduct

logger = logging.getLogger(__name__)


class CeramicaImpexScraper(BaseScraper):
    """Scraper for Ceramica Impex B2B portal using httpx (no browser needed)"""
    
    SUPPLIER_NAME = "Ceramica Impex"
    BASE_URL = "https://portal.ceramicaimpex.co.uk"
    LOGIN_URL = "https://portal.ceramicaimpex.co.uk/login/default.aspx"
    
    def __init__(self, email: str, password: str):
        super().__init__(email, password)
        self.client: Optional[httpx.AsyncClient] = None
    
    async def _ensure_client(self):
        """Ensure HTTP client is initialized"""
        if not self.client:
            self.client = httpx.AsyncClient(
                timeout=60.0,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-GB,en;q=0.5",
                }
            )
    
    async def login(self) -> bool:
        """Login to Ceramica Impex portal using httpx"""
        try:
            await self._ensure_client()
            
            # Step 1: Get login page to extract form fields and viewstate
            logger.info("Fetching Ceramica Impex login page...")
            login_page = await self.client.get(self.LOGIN_URL)
            
            if login_page.status_code != 200:
                logger.error(f"Failed to fetch login page: {login_page.status_code}")
                return False
            
            soup = BeautifulSoup(login_page.text, 'html.parser')
            
            # Extract ASP.NET form fields
            viewstate = soup.find('input', {'name': '__VIEWSTATE'})
            viewstate_gen = soup.find('input', {'name': '__VIEWSTATEGENERATOR'})
            event_validation = soup.find('input', {'name': '__EVENTVALIDATION'})
            
            # Find the actual form field names
            username_field = soup.find('input', {'id': 'username'}) or soup.find('input', {'name': re.compile(r'username|user|email', re.I)})
            password_field = soup.find('input', {'id': 'pword'}) or soup.find('input', {'type': 'password'})
            
            username_name = username_field.get('name', 'username') if username_field else 'username'
            password_name = password_field.get('name', 'pword') if password_field else 'pword'
            
            logger.info(f"Found form fields: username={username_name}, password={password_name}")
            
            # Build login form data
            login_data = {
                username_name: self.email,
                password_name: self.password,
            }
            
            # Add ASP.NET hidden fields if present
            if viewstate:
                login_data['__VIEWSTATE'] = viewstate.get('value', '')
            if viewstate_gen:
                login_data['__VIEWSTATEGENERATOR'] = viewstate_gen.get('value', '')
            if event_validation:
                login_data['__EVENTVALIDATION'] = event_validation.get('value', '')
            
            # Find submit button name
            submit_btn = soup.find('input', {'type': 'submit'}) or soup.find('button', {'type': 'submit'})
            if submit_btn and submit_btn.get('name'):
                login_data[submit_btn.get('name')] = submit_btn.get('value', 'Login')
            
            # Step 2: Submit login form
            logger.info("Submitting login credentials...")
            login_response = await self.client.post(
                self.LOGIN_URL,
                data=login_data,
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Referer': self.LOGIN_URL,
                }
            )
            
            # Step 3: Verify login by accessing catalog page
            logger.info("Verifying login by accessing catalog...")
            catalog_url = f"{self.BASE_URL}/Catalogue/Tiles"
            catalog_response = await self.client.get(catalog_url)
            
            # Check if we got product data (FASTNodes JSON)
            if 'FASTNodes' in catalog_response.text or 'Nodes' in catalog_response.text:
                self.is_authenticated = True
                logger.info("Successfully logged in to Ceramica Impex!")
                return True
            
            # Alternative check - look for product elements
            if 'product' in catalog_response.text.lower() and 'login' not in catalog_response.url.path.lower():
                self.is_authenticated = True
                logger.info("Successfully logged in to Ceramica Impex (alternative check)!")
                return True
            
            logger.error(f"Login verification failed - redirected to: {catalog_response.url}")
            logger.error(f"Response contains 'login': {'login' in catalog_response.text.lower()}")
            return False
            
        except Exception as e:
            logger.error(f"Ceramica Impex login error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def get_all_products(self) -> List[SupplierProduct]:
        """
        Fetch all products from Ceramica Impex.
        Product data is in JSON format on the page - very efficient!
        """
        if not self.is_authenticated:
            if not await self.login():
                return []
        
        products = []
        
        # Categories to scrape
        categories = [
            "/Catalogue/Tiles",
            "/Catalogue/LargeFormatSlabs",
            "/Catalogue/Mosaics",
            "/Catalogue/20MMOutdoor",
        ]
        
        try:
            for category in categories:
                logger.info(f"Scraping category: {category}")
                category_products = await self._scrape_category_json(category)
                products.extend(category_products)
                await asyncio.sleep(0.5)
            
            # Remove duplicates by supplier_code
            seen = set()
            unique_products = []
            for p in products:
                if p.supplier_code and p.supplier_code not in seen:
                    seen.add(p.supplier_code)
                    unique_products.append(p)
            
            self.products = unique_products
            logger.info(f"Total unique products scraped from Ceramica Impex: {len(unique_products)}")
            return unique_products
            
        except Exception as e:
            logger.error(f"Error fetching Ceramica Impex products: {e}")
            import traceback
            traceback.print_exc()
            return []
        finally:
            if self.client:
                await self.client.aclose()
                self.client = None
    
    async def _scrape_category_json(self, category_path: str) -> List[SupplierProduct]:
        """
        Scrape products from category by parsing the FASTNodes JSON.
        This is much faster than scraping individual elements!
        """
        products = []
        
        try:
            url = f"{self.BASE_URL}{category_path}"
            response = await self.client.get(url)
            html = response.text
            
            # Try multiple patterns to extract product JSON
            # Pattern 1: FASTNodes script tag
            match = re.search(r'data-type="FASTNodes"[^>]*>(\{.*?\})</script>', html, re.DOTALL)
            
            # Pattern 2: Direct Nodes array
            if not match:
                match = re.search(r'"Nodes"\s*:\s*(\[.*?\])', html, re.DOTALL)
            
            # Pattern 3: Products in JavaScript variable
            if not match:
                match = re.search(r'var\s+products?\s*=\s*(\[.*?\]);', html, re.DOTALL)
            
            if not match:
                logger.warning(f"No product JSON found in {category_path}, trying HTML parsing...")
                return await self._scrape_category_html(category_path, html)
            
            json_str = match.group(1)
            
            try:
                data = json.loads(json_str)
                nodes = data.get('Nodes', []) if isinstance(data, dict) else data
            except json.JSONDecodeError:
                # Try to fix common JSON issues
                json_str = re.sub(r',\s*}', '}', json_str)
                json_str = re.sub(r',\s*]', ']', json_str)
                data = json.loads(json_str)
                nodes = data.get('Nodes', []) if isinstance(data, dict) else data
            
            logger.info(f"Found {len(nodes)} items in JSON for {category_path}")
            
            for node in nodes:
                # Skip non-product nodes
                if isinstance(node, dict) and node.get('Type') and node.get('Type') != 'P':
                    continue
                
                name = node.get('Name', '') or node.get('name', '')
                code = node.get('StockCode', '') or node.get('stockCode', '') or node.get('sku', '')
                price = node.get('SortPrice', 0) or node.get('price', 0)
                href = node.get('Href', '') or node.get('href', '') or node.get('url', '')
                image_url = node.get('ImageHref', '') or node.get('image', '') or node.get('imageUrl', '')
                
                if not name:
                    continue
                
                # Extract size from name
                size_match = re.search(r'(\d+)[xX](\d+)', name)
                size = f"{size_match.group(1)}x{size_match.group(2)}" if size_match else ""
                
                # Determine material
                material = "Porcelain"
                name_lower = name.lower()
                if "ceramic" in name_lower:
                    material = "Ceramic"
                elif "glass" in name_lower or "mosaic" in name_lower:
                    material = "Glass"
                elif "marble" in name_lower:
                    material = "Marble"
                elif "wood" in name_lower:
                    material = "Wood Effect"
                
                # Determine finish
                finish = ""
                if "polished" in name_lower:
                    finish = "Polished"
                elif "matt" in name_lower or "matte" in name_lower:
                    finish = "Matt"
                elif "gloss" in name_lower:
                    finish = "Gloss"
                elif "decor" in name_lower:
                    finish = "Decor"
                
                product = SupplierProduct(
                    supplier_code=code,
                    supplier_name=self.SUPPLIER_NAME,
                    name=name,
                    size=size,
                    material=material,
                    finish=finish,
                    room_lot_price=float(price) if price else 0,
                    stock_sqm=100,  # Default - available if listed
                    stock_status="In Stock",
                    images=[image_url] if image_url else [],
                    extra_data={
                        "url": f"{self.BASE_URL}{href}" if href and not href.startswith('http') else href,
                        "node_id": node.get('NodeId', ''),
                        "purchasable": node.get('Purchasable', True)
                    }
                )
                
                products.append(product)
            
            logger.info(f"Parsed {len(products)} products from {category_path}")
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from {category_path}: {e}")
        except Exception as e:
            logger.error(f"Error processing category {category_path}: {e}")
            import traceback
            traceback.print_exc()
        
        return products
    
    async def _scrape_category_html(self, category_path: str, html: str) -> List[SupplierProduct]:
        """Fallback: Scrape products from HTML if JSON not available"""
        products = []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Try to find product containers
            product_elements = soup.find_all(['div', 'article'], class_=re.compile(r'product|item|tile', re.I))
            
            if not product_elements:
                product_elements = soup.find_all('a', href=re.compile(r'/Product/|/product/', re.I))
            
            logger.info(f"Found {len(product_elements)} product elements via HTML parsing")
            
            for elem in product_elements[:100]:  # Limit for safety
                try:
                    # Extract name
                    name_elem = elem.find(['h2', 'h3', 'h4', 'span', 'div'], class_=re.compile(r'name|title', re.I))
                    name = name_elem.get_text(strip=True) if name_elem else elem.get_text(strip=True)[:100]
                    
                    if not name or len(name) < 3:
                        continue
                    
                    # Extract code/SKU
                    code = ""
                    code_match = re.search(r'([A-Z]{2,}\d+[A-Z]*)', name)
                    if code_match:
                        code = code_match.group(1)
                    
                    # Extract image
                    img = elem.find('img')
                    image_url = img.get('src', '') if img else ''
                    if image_url and not image_url.startswith('http'):
                        image_url = self.BASE_URL + image_url
                    
                    # Extract size
                    size_match = re.search(r'(\d+)[xX](\d+)', name)
                    size = f"{size_match.group(1)}x{size_match.group(2)}" if size_match else ""
                    
                    product = SupplierProduct(
                        supplier_code=code or f"CI-{hash(name) % 100000}",
                        supplier_name=self.SUPPLIER_NAME,
                        name=name,
                        size=size,
                        material="Porcelain",
                        finish="",
                        room_lot_price=0,
                        stock_sqm=100,
                        stock_status="In Stock",
                        images=[image_url] if image_url else [],
                        extra_data={"source": "html_fallback"}
                    )
                    
                    products.append(product)
                    
                except Exception as e:
                    continue
            
        except Exception as e:
            logger.error(f"HTML parsing error: {e}")
        
        return products
    
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
async def test_ceramica_scraper():
    """Test the Ceramica Impex scraper"""
    scraper = CeramicaImpexScraper(
        email="qasim@tilestation.co.uk",
        password=os.environ.get("CERAMICA_PORTAL_PASSWORD", "")
    )
    
    print("Testing Ceramica Impex scraper (httpx version)...")
    if await scraper.login():
        print("Login successful!")
        products = await scraper.get_all_products()
        print(f"Found {len(products)} products")
        
        for p in products[:5]:
            print(f"\n{p.name}")
            print(f"  Code: {p.supplier_code}")
            print(f"  Price: £{p.room_lot_price}")
            print(f"  Size: {p.size}")
    else:
        print("Login failed")


if __name__ == "__main__":
    asyncio.run(test_ceramica_scraper())

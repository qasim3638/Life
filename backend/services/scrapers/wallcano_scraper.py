"""
Wallcano Tiles Scraper
Scrapes products, images, and stock levels from wallcanotiles.com
Uses PDF price list for pricing (no online prices)
"""
import httpx
import os
import asyncio
import re
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
import logging

from .base_scraper import BaseScraper, SupplierProduct

logger = logging.getLogger(__name__)


class WallcanoScraper(BaseScraper):
    """Scraper for Wallcano Tiles dealer portal"""
    
    SUPPLIER_NAME = "Wallcano"
    BASE_URL = "https://www.wallcanotiles.com"
    LOGIN_URL = "https://www.wallcanotiles.com/login"
    PRODUCTS_URL = "https://www.wallcanotiles.com/dealers/products"
    
    def __init__(self, email: str, password: str, price_data: Dict[str, Dict] = None):
        super().__init__(email, password)
        # Price data from PDF: {product_code: {room_lot: x, pallet: y}}
        self.price_data = price_data or {}
    
    async def _ensure_client(self):
        """Ensure HTTP client is initialized"""
        if not self.client:
            self.client = httpx.AsyncClient(
                timeout=60.0,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            )
    
    async def login(self) -> bool:
        """Login to Wallcano dealer portal"""
        try:
            await self._ensure_client()
            # Get login page to find CSRF token
            login_page = await self.client.get(self.LOGIN_URL)
            soup = BeautifulSoup(login_page.text, 'html.parser')
            
            # Find CSRF token
            csrf_token = None
            csrf_input = soup.find('input', {'name': '_token'})
            if csrf_input:
                csrf_token = csrf_input.get('value')
            
            # Prepare login data
            login_data = {
                'email': self.email,
                'password': self.password,
            }
            if csrf_token:
                login_data['_token'] = csrf_token
            
            # Submit login
            response = await self.client.post(
                self.LOGIN_URL,
                data=login_data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            
            # Check if logged in (look for dealer content)
            if 'dealers' in response.url.path or 'Tile Station' in response.text:
                self.is_authenticated = True
                logger.info("Successfully logged in to Wallcano")
                return True
            
            logger.error("Failed to login to Wallcano")
            return False
            
        except Exception as e:
            logger.error(f"Wallcano login error: {e}")
            return False
    
    async def get_all_products(self) -> List[SupplierProduct]:
        """Fetch all products from Wallcano"""
        if not self.is_authenticated:
            if not await self.login():
                return []
        
        products = []
        
        try:
            # Get createOrder page which contains product data in JavaScript
            response = await self.client.get(f"{self.BASE_URL}/dealers/createOrder")
            html = response.text
            
            # Extract sample_product JSON array from JavaScript
            import json
            match = re.search(r'var sample_product = (\[.*?\]);', html, re.DOTALL)
            if not match:
                logger.error("Could not find product data in Wallcano page")
                return []
            
            products_json = match.group(1)
            product_list = json.loads(products_json)
            
            logger.info(f"Found {len(product_list)} products in Wallcano data")
            
            # Process each product
            for p_data in product_list:
                product_id = str(p_data.get('id', ''))
                sku = p_data.get('sku', '')
                
                # Get pricing from PDF price data
                pricing = self.price_data.get(sku, {})
                room_lot_price = pricing.get('room_lot', 0.0)
                pallet_price = pricing.get('pallet', 0.0)
                
                # Get stock from product detail page
                stock_sqm = await self._get_product_stock(product_id)
                
                product = SupplierProduct(
                    supplier_code=sku,
                    supplier_name=self.SUPPLIER_NAME,
                    name=p_data.get('name', ''),
                    size=p_data.get('size', ''),
                    material='Porcelain',  # Default for Wallcano
                    finish=p_data.get('finishing', ''),
                    thickness=str(p_data.get('thickness_in_mm', '')),
                    tiles_per_box=self.parse_int(p_data.get('tiles_per_box', 0)),
                    sqm_per_box=self.parse_float(p_data.get('square_meter_per_box', 0)),
                    boxes_per_pallet=self.parse_int(p_data.get('pallet_size', 0)),
                    room_lot_price=room_lot_price,
                    pallet_price=pallet_price,
                    stock_sqm=stock_sqm,
                    stock_status="In Stock" if stock_sqm >= 20 else ("Low Stock" if stock_sqm > 0 else "Out of Stock"),
                    weight_per_box=self.parse_float(p_data.get('weight_per_box', 0)),
                    extra_data={
                        "portal_id": product_id,
                        "category_id": p_data.get('category_id'),
                        "sub_category_id": p_data.get('sub_category_id'),
                        "wastage": p_data.get('wastage', 5)
                    }
                )
                
                # Get images from product detail page
                product.images = await self._get_product_images(product_id)
                
                products.append(product)
                logger.info(f"Scraped: {product.name} ({sku}) - Stock: {stock_sqm}m²")
                
                await asyncio.sleep(0.3)  # Rate limiting
            
            self.products = products
            return products
            
        except Exception as e:
            logger.error(f"Error fetching Wallcano products: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def _get_product_stock(self, product_id: str) -> float:
        """Get stock level for a specific product"""
        try:
            url = f"{self.BASE_URL}/dealers/product_details/{product_id}"
            response = await self.client.get(url)
            
            # Look for "Available Quantity: X m2"
            match = re.search(r'Available Quantity[:\s]*([\d,.]+)\s*m2', response.text, re.I)
            if match:
                return float(match.group(1).replace(',', ''))
            return 0.0
        except Exception as e:
            logger.error(f"Error getting stock for product {product_id}: {e}")
            return 0.0
    
    async def _get_product_images(self, product_id: str) -> List[str]:
        """Get images for a specific product"""
        try:
            url = f"{self.BASE_URL}/dealers/product_details/{product_id}"
            response = await self.client.get(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            images = []
            img_tags = soup.find_all('img')
            for img in img_tags:
                src = img.get('src', '')
                if src and '/products/' in src and 'logo' not in src.lower():
                    if not src.startswith('http'):
                        src = self.BASE_URL + src
                    images.append(src)
            
            return list(set(images))  # Remove duplicates
        except Exception as e:
            logger.error(f"Error getting images for product {product_id}: {e}")
            return []
    
    async def get_product_details(self, product_id: str) -> Optional[SupplierProduct]:
        """Get detailed information for a single product"""
        try:
            url = f"{self.BASE_URL}/dealers/product_details/{product_id}"
            response = await self.client.get(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract product name
            name_elem = soup.find('h1') or soup.find('h2')
            name = name_elem.get_text(strip=True) if name_elem else ""
            
            # Extract product code
            code_elem = soup.find(string=re.compile(r'^[A-Z]{3}\d+'))
            code = code_elem.strip() if code_elem else ""
            
            # If code not found, try other patterns
            if not code:
                code_pattern = soup.find(string=re.compile(r'[A-Z]+\d+[A-Z]*\d*'))
                code = code_pattern.strip() if code_pattern else f"WC-{product_id}"
            
            # Extract available quantity (stock)
            stock_sqm = 0.0
            stock_elem = soup.find(string=re.compile(r'Available Quantity'))
            if stock_elem:
                stock_text = stock_elem.find_next()
                if stock_text:
                    match = re.search(r'([\d,.]+)\s*m2', stock_text.get_text())
                    if match:
                        stock_sqm = float(match.group(1).replace(',', ''))
            
            # Extract specs from table
            specs = {}
            spec_rows = soup.find_all('tr')
            for row in spec_rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    key = cells[0].get_text(strip=True).lower().replace(':', '')
                    value = cells[1].get_text(strip=True)
                    specs[key] = value
            
            # Extract images
            images = []
            img_tags = soup.find_all('img', src=re.compile(r'/uploads/|/images/|/storage/'))
            for img in img_tags:
                src = img.get('src', '')
                if src and 'logo' not in src.lower():
                    if not src.startswith('http'):
                        src = self.BASE_URL + src
                    images.append(src)
            
            # Get pricing from price_data (from PDF)
            pricing = self.price_data.get(code, {})
            room_lot_price = pricing.get('room_lot', 0.0)
            pallet_price = pricing.get('pallet', 0.0)
            
            # Create product
            product = SupplierProduct(
                supplier_code=code,
                supplier_name=self.SUPPLIER_NAME,
                name=name,
                size=specs.get('size', ''),
                material=specs.get('material', 'Porcelain'),
                finish=specs.get('finish', ''),
                thickness=specs.get('thickness in mm', ''),
                tiles_per_box=self.parse_int(specs.get('tiles per box', 0)),
                sqm_per_box=self.parse_float(specs.get('sqm per box', '').replace('mm', '')),
                boxes_per_pallet=self.parse_int(specs.get('pallet size', '').replace('Box', '').replace('box', '')),
                room_lot_price=room_lot_price,
                pallet_price=pallet_price,
                stock_sqm=stock_sqm,
                stock_status="In Stock" if stock_sqm >= 20 else ("Low Stock" if stock_sqm > 0 else "Out of Stock"),
                images=images,
                weight_per_box=self.parse_float(specs.get('weight per box', '').replace('Kg', '').replace('kg', '')),
                extra_data={"portal_id": product_id, "raw_specs": specs}
            )
            
            logger.info(f"Scraped Wallcano product: {name} ({code}) - Stock: {stock_sqm}m²")
            return product
            
        except Exception as e:
            logger.error(f"Error getting Wallcano product {product_id}: {e}")
            return None
    
    async def get_stock_levels(self) -> Dict[str, float]:
        """Get current stock levels for all products"""
        stock_levels = {}
        
        for product in self.products:
            stock_levels[product.supplier_code] = product.stock_sqm
        
        return stock_levels


def parse_wallcano_pdf_prices(pdf_path: str) -> Dict[str, Dict]:
    """
    Parse Wallcano PDF price list to extract prices by product code
    Returns: {product_code: {room_lot: price, pallet: price}}
    """
    import fitz  # PyMuPDF
    
    prices = {}
    
    try:
        doc = fitz.open(pdf_path)
        
        for page in doc:
            text = page.get_text()
            lines = text.split('\n')
            
            current_product = {}
            
            for i, line in enumerate(lines):
                # Look for product codes (e.g., FEA3045A1, POL3060A5)
                code_match = re.match(r'^([A-Z]{3}\d+[A-Z]*\d*)$', line.strip())
                if code_match:
                    code = code_match.group(1)
                    
                    # Look for prices in nearby lines
                    nearby_text = ' '.join(lines[max(0, i-5):min(len(lines), i+10)])
                    
                    # Extract Room Lot price
                    room_lot_match = re.search(r'£([\d.]+)\s*\(?Room Lot', nearby_text)
                    if room_lot_match:
                        room_lot_price = float(room_lot_match.group(1))
                    else:
                        room_lot_match = re.search(r'Room Lot[^£]*£([\d.]+)', nearby_text)
                        room_lot_price = float(room_lot_match.group(1)) if room_lot_match else 0.0
                    
                    # Extract Pallet price
                    pallet_match = re.search(r'£([\d.]+)\s*\(?Full Pallet', nearby_text)
                    if pallet_match:
                        pallet_price = float(pallet_match.group(1))
                    else:
                        pallet_match = re.search(r'Pallet[^£]*£([\d.]+)', nearby_text)
                        pallet_price = float(pallet_match.group(1)) if pallet_match else 0.0
                    
                    if room_lot_price > 0 or pallet_price > 0:
                        prices[code] = {
                            'room_lot': room_lot_price,
                            'pallet': pallet_price
                        }
        
        doc.close()
        
    except Exception as e:
        logger.error(f"Error parsing Wallcano PDF: {e}")
    
    return prices


# Test function
async def test_wallcano_scraper():
    """Test the Wallcano scraper"""
    # First parse PDF prices
    prices = parse_wallcano_pdf_prices('/app/supplier_data/wallcano_pricelist.pdf')
    print(f"Parsed {len(prices)} prices from PDF")
    
    async with WallcanoScraper(
        email="accounts@tilestation.co.uk",
        password=os.environ.get("WALLCANO_PORTAL_PASSWORD", ""),
        price_data=prices
    ) as scraper:
        if await scraper.login():
            print("Login successful!")
            products = await scraper.get_all_products()
            print(f"Found {len(products)} products")
            
            for p in products[:3]:
                print(f"\n{p.name}")
                print(f"  Code: {p.supplier_code}")
                print(f"  Stock: {p.stock_sqm}m² ({p.stock_status})")
                print(f"  Room Lot: £{p.room_lot_price}")
                print(f"  Images: {len(p.images)}")


if __name__ == "__main__":
    asyncio.run(test_wallcano_scraper())

"""
Web Scraper Service for fetching product images from supplier websites
Supports: Tile Rite, Trimline Group, Ultra Tile (Instarmac)
"""
import asyncio
import aiohttp
import re
from bs4 import BeautifulSoup
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class SupplierScraper:
    """Base class for supplier scrapers"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.5",
        }
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(headers=self.headers)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def fetch_page(self, url: str) -> Optional[str]:
        """Fetch a page and return HTML content"""
        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    return await response.text()
                logger.warning(f"Failed to fetch {url}: status {response.status}")
                return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
    
    async def scrape_product(self, sku: str, product_name: str = "") -> Dict[str, Any]:
        """Override in subclasses to scrape product data"""
        raise NotImplementedError


class TileRiteScraper(SupplierScraper):
    """Scraper for tilerite.co.uk"""
    
    BASE_URL = "https://www.tilerite.co.uk"
    SEARCH_URL = "https://www.tilerite.co.uk/search/"
    
    # Category mappings based on product names
    CATEGORY_PATTERNS = {
        "tile-trim-metal": ["trim", "l shape", "l-shape", "edge", "profile", "listello"],
        "tile-spacers": ["spacer", "levelling", "wedge"],
        "drills-holesaws": ["drill", "holesaw", "diamond", "mill"],
        "tile-cutting-machines": ["cutter", "blade", "cutting"],
        "grout-floats-spreaders": ["float", "spreader", "grout"],
        "adhesive-trowels": ["trowel", "notched"],
        "general-tiling-tools": ["tool", "sponge", "bucket"],
        "matting-thermaboard": ["mat", "matting", "thermaboard", "pro-mat"],
        "clean-seal-range": ["cleaner", "sealer", "polish"],
        "floor-trims": ["floor trim", "carpet"],
        "tile-edge-plastic": ["plastic trim", "pvc"],
        "bath-trims": ["bath trim", "bath seal"],
    }
    
    async def find_product_url(self, sku: str, product_name: str = "") -> Optional[str]:
        """Try to find the product URL using different methods"""
        
        # Method 1: Direct URL construction based on SKU
        # Tile Rite URLs are like: /category/subcategory/SKU/
        
        # Try searching for the product
        search_html = await self.fetch_page(f"{self.SEARCH_URL}?q={sku}")
        if search_html:
            soup = BeautifulSoup(search_html, "html.parser")
            # Look for product links containing the SKU
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if sku.upper() in href.upper():
                    return href if href.startswith("http") else f"{self.BASE_URL}{href}"
        
        # Method 2: Try common category paths
        categories_to_try = ["tile-trim-metal", "drills-holesaws", "tile-spacers", "general-tiling-tools"]
        
        # Determine likely category from product name
        product_lower = product_name.lower()
        for cat, keywords in self.CATEGORY_PATTERNS.items():
            if any(kw in product_lower for kw in keywords):
                categories_to_try.insert(0, cat)
                break
        
        for category in categories_to_try[:3]:  # Only try top 3
            # Try direct URL
            url = f"{self.BASE_URL}/{category}/{sku}/"
            html = await self.fetch_page(url)
            if html and "Product Code:" in html:
                return url
        
        return None
    
    async def scrape_product(self, sku: str, product_name: str = "") -> Dict[str, Any]:
        """Scrape product data from Tile Rite website"""
        result = {
            "sku": sku,
            "supplier": "Tile Rite",
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "success": False,
            "images": [],
            "description": "",
            "specifications": {},
            "error": None
        }
        
        try:
            # Find the product URL
            product_url = await self.find_product_url(sku, product_name)
            
            if not product_url:
                # Try direct image URL construction
                # Tile Rite images: https://www.tilerite.co.uk/images/product/SKU-1.jpg
                for i in range(1, 4):
                    img_url = f"{self.BASE_URL}/images/product/{sku}-{i}.jpg"
                    async with self.session.head(img_url) as resp:
                        if resp.status == 200:
                            result["images"].append(img_url)
                
                if result["images"]:
                    result["success"] = True
                    result["note"] = "Images found via direct URL, product page not located"
                else:
                    result["error"] = f"Product not found for SKU: {sku}"
                return result
            
            # Fetch the product page
            html = await self.fetch_page(product_url)
            if not html:
                result["error"] = f"Failed to fetch product page: {product_url}"
                return result
            
            soup = BeautifulSoup(html, "html.parser")
            
            # Extract images
            # Main product images are in links with class containing product image
            for img_link in soup.find_all("a", href=True):
                href = img_link["href"]
                if "/images/product/" in href and sku.upper() in href.upper():
                    img_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"
                    if img_url not in result["images"]:
                        result["images"].append(img_url)
            
            # Also check img tags
            for img in soup.find_all("img", src=True):
                src = img["src"]
                if "/images/product/" in src and sku.upper() in src.upper():
                    # Get full size image (remove size prefix like 363x363-)
                    img_url = re.sub(r'\d+x\d+-', '', src)
                    img_url = img_url if img_url.startswith("http") else f"{self.BASE_URL}{img_url}"
                    if img_url not in result["images"]:
                        result["images"].append(img_url)
            
            # Extract description
            desc_div = soup.find("div", {"id": "productdesc"}) or soup.find("div", class_="product-description")
            if desc_div:
                # Get list items as description
                items = desc_div.find_all("li")
                if items:
                    result["description"] = " | ".join(li.get_text(strip=True) for li in items)
                else:
                    result["description"] = desc_div.get_text(strip=True)[:500]
            
            # Extract product title
            h1 = soup.find("h1")
            if h1:
                result["product_name"] = h1.get_text(strip=True)
            
            result["product_url"] = product_url
            result["success"] = len(result["images"]) > 0
            
            if not result["success"]:
                result["error"] = "No images found on product page"
            
        except Exception as e:
            logger.error(f"Error scraping Tile Rite product {sku}: {e}")
            result["error"] = str(e)
        
        return result


class TrimlineScraper(SupplierScraper):
    """Scraper for shop.trimlinegroup.com (Shopify-based)"""
    
    BASE_URL = "https://shop.trimlinegroup.com"
    
    async def scrape_product(self, sku: str, product_name: str = "") -> Dict[str, Any]:
        """Scrape product data from Trimline website"""
        result = {
            "sku": sku,
            "supplier": "Trimline",
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "success": False,
            "images": [],
            "description": "",
            "specifications": {},
            "error": None
        }
        
        try:
            # Trimline uses Shopify - search for products
            search_url = f"{self.BASE_URL}/search?q={sku}"
            html = await self.fetch_page(search_url)
            
            if not html:
                result["error"] = "Failed to fetch search page"
                return result
            
            soup = BeautifulSoup(html, "html.parser")
            
            # Find product links in search results
            product_links = soup.find_all("a", href=True)
            product_url = None
            
            for link in product_links:
                href = link["href"]
                if "/products/" in href:
                    # Check if this is the right product
                    product_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"
                    break
            
            if not product_url:
                result["error"] = f"Product not found for SKU: {sku}"
                return result
            
            # Fetch product page
            product_html = await self.fetch_page(product_url)
            if not product_html:
                result["error"] = f"Failed to fetch product page: {product_url}"
                return result
            
            soup = BeautifulSoup(product_html, "html.parser")
            
            # Extract images - Look for main product image first
            # Shopify product pages often have product images in specific containers
            main_images = []
            
            # Method 1: Look for meta og:image tag (often has the main product image)
            og_image = soup.find("meta", property="og:image")
            if og_image and og_image.get("content"):
                img_url = og_image.get("content")
                if img_url.startswith("//"):
                    img_url = "https:" + img_url
                clean_url = re.sub(r'\?.*$', '', img_url)
                main_images.append(clean_url)
            
            # Method 2: Look for images in product gallery/media sections
            product_selectors = [
                "div[class*='product-media']",
                "div[class*='product-gallery']",
                "div[class*='product-image']",
                "div[class*='ProductGallery']",
                "section[class*='product']"
            ]
            
            for selector in product_selectors:
                container = soup.select_one(selector)
                if container:
                    for img in container.find_all("img"):
                        src = img.get("src") or img.get("data-src") or ""
                        if "/cdn/shop/" in src and "/files/" in src:
                            if src.startswith("//"):
                                src = "https:" + src
                            clean_url = re.sub(r'\?.*$', '', src)
                            if clean_url not in main_images:
                                main_images.append(clean_url)
            
            # Method 3: Look for any image with the product name in alt text or filename
            sku_lower = sku.lower().replace("-", "").replace("_", "")
            for img in soup.find_all("img"):
                src = img.get("src") or img.get("data-src") or ""
                alt = (img.get("alt") or "").lower()
                
                if "/cdn/shop/files/" in src:
                    if src.startswith("//"):
                        src = "https:" + src
                    clean_url = re.sub(r'\?.*$', '', src)
                    
                    # Prioritize images with matching alt text or BC_Upload prefix (product uploads)
                    if "BC_Upload" in src or sku_lower in alt.replace(" ", "").replace("-", ""):
                        if clean_url not in main_images:
                            main_images.insert(0, clean_url)  # Add to front
                    elif clean_url not in main_images:
                        main_images.append(clean_url)
            
            # Filter out obvious non-product images and duplicates
            seen_urls = set()
            filtered_images = []
            for img in main_images[:5]:  # Limit to 5 images
                # Normalize URL (ensure https)
                if img.startswith("http://"):
                    img = img.replace("http://", "https://", 1)
                
                # Skip if already seen or matches skip patterns
                if img in seen_urls:
                    continue
                if any(skip in img.lower() for skip in [
                    "collection", "cover_image", "trimline_-_", "banner", "logo"
                ]):
                    continue
                
                seen_urls.add(img)
                filtered_images.append(img)
            
            result["images"] = filtered_images
            
            result["product_url"] = product_url
            result["success"] = len(result["images"]) > 0
            
            if not result["success"]:
                result["error"] = "No images found on product page"
                
        except Exception as e:
            logger.error(f"Error scraping Trimline product {sku}: {e}")
            result["error"] = str(e)
        
        return result


class UltraTileScraper(SupplierScraper):
    """Scraper for instarmac.co.uk UltraTile products"""
    
    BASE_URL = "https://www.instarmac.co.uk"
    PRODUCT_BASE = "https://www.instarmac.co.uk/products/ultratile"
    
    # Product categories
    CATEGORIES = [
        "adhesives",
        "grouts-and-silicones",
        "levelling-compounds",
        "tiling-ancillaries",
        "tile-stone-cleaning-range",
        "outdoor-tile-adhesives",
        "external-tiling"
    ]
    
    async def scrape_product(self, sku: str, product_name: str = "") -> Dict[str, Any]:
        """Scrape product data from UltraTile/Instarmac website"""
        result = {
            "sku": sku,
            "supplier": "Ultra Tile",
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "success": False,
            "images": [],
            "description": "",
            "specifications": {},
            "error": None
        }
        
        try:
            product_url = None
            
            # Clean up search terms from product name - avoid common words
            search_terms = []
            common_words = {"tile", "adhesive", "grout", "compound", "product", "white", "grey", "gray", "the", "and", "for"}
            
            if product_name:
                terms = [t.lower() for t in product_name.replace("-", " ").split() if len(t) > 2]
                search_terms = [t for t in terms if t not in common_words]
            if sku:
                # Add SKU terms (split by - or _)
                sku_parts = [p.lower() for p in sku.replace("-", " ").replace("_", " ").split() if len(p) > 1]
                search_terms = sku_parts + search_terms  # Prioritize SKU
            
            # Try category pages - they list all products with links
            found_products = []
            
            for category in self.CATEGORIES:
                cat_url = f"{self.PRODUCT_BASE}/{category}/"
                cat_html = await self.fetch_page(cat_url)
                
                if not cat_html:
                    continue
                    
                soup = BeautifulSoup(cat_html, "html.parser")
                
                # Look for product links - they have 4+ path segments
                # e.g., /products/ultratile/adhesives/proflex-s2/
                for link in soup.find_all("a", href=True):
                    href = link["href"]
                    link_text = link.get_text().lower()
                    
                    # Skip category links (have only 3 segments like /products/ultratile/adhesives/)
                    # Product links have 4+ segments like /products/ultratile/adhesives/product-name/
                    path_parts = [p for p in href.split("/") if p]
                    if len(path_parts) < 4:
                        continue
                    
                    if "/products/ultratile/" not in href:
                        continue
                    
                    # Calculate match score - higher is better
                    match_score = 0
                    href_lower = href.lower()
                    
                    for term in search_terms:
                        if term in link_text:
                            match_score += 2  # Text match is stronger
                        if term in href_lower:
                            match_score += 1
                    
                    if match_score > 0:
                        # Make URL absolute
                        if not href.startswith("http"):
                            href = self.BASE_URL + href if href.startswith("/") else f"{self.BASE_URL}/{href}"
                        found_products.append((match_score, href))
            
            # Sort by match score (highest first) and pick best match
            if found_products:
                found_products.sort(key=lambda x: x[0], reverse=True)
                product_url = found_products[0][1]
            
            if not product_url:
                result["error"] = f"Product not found for: {product_name or sku}"
                return result
            
            # Fetch product page
            product_html = await self.fetch_page(product_url)
            if not product_html:
                result["error"] = f"Failed to fetch product page: {product_url}"
                return result
            
            soup = BeautifulSoup(product_html, "html.parser")
            
            # Extract images - look for product images in various locations
            # 1. Check og:image meta tag (most reliable)
            og_image = soup.find("meta", property="og:image")
            if og_image and og_image.get("content"):
                img_url = og_image.get("content")
                if img_url and img_url not in result["images"]:
                    result["images"].append(img_url)
            
            # 2. Check twitter:image meta tag
            twitter_image = soup.find("meta", attrs={"name": "twitter:image"})
            if twitter_image and twitter_image.get("content"):
                img_url = twitter_image.get("content")
                if img_url and img_url not in result["images"]:
                    result["images"].append(img_url)
            
            # 3. Look for product images in wp-content/uploads - these contain actual product photos
            # Parse raw HTML for wp-content URLs since they might be in JS or data attributes
            
            # Find all image URLs in wp-content/uploads
            upload_images = re.findall(r'https?://[^"\']+/wp-content/uploads/[^"\']+\.(?:jpg|png|webp)', str(soup))
            
            # Score and sort images by relevance
            scored_images = []
            for img_url in upload_images:
                img_lower = img_url.lower()
                # Skip small thumbnails and non-product images
                if "300x" in img_lower or "logo" in img_lower:
                    continue
                
                score = 0
                # Check for exact SKU match (e.g., proflex_s2 in UT_ProFlex_S2)
                sku_normalized = sku.lower().replace("-", "").replace("_", "").replace(" ", "")
                img_normalized = img_lower.replace("-", "").replace("_", "").replace(" ", "")
                
                if sku_normalized and sku_normalized in img_normalized:
                    score += 10  # Highest priority for SKU match
                elif "ut_" in img_lower and "_web.jpg" in img_lower:
                    score += 3  # Likely a product image
                
                if score > 0:
                    scored_images.append((score, img_url))
            
            # Sort by score (highest first) and add to images
            scored_images.sort(key=lambda x: x[0], reverse=True)
            for score, img_url in scored_images[:3]:
                if img_url not in result["images"]:
                    result["images"].append(img_url)
            
            # Extract description
            desc_elem = soup.find("div", class_="entry-content") or soup.find("article")
            if desc_elem:
                # Get text but limit length
                text = desc_elem.get_text(separator=" ", strip=True)
                result["description"] = text[:500] if len(text) > 500 else text
            
            result["product_url"] = product_url
            result["success"] = len(result["images"]) > 0
            
            if not result["success"]:
                result["error"] = "No images found on product page"
                
        except Exception as e:
            logger.error(f"Error scraping UltraTile product {sku}: {e}")
            result["error"] = str(e)
        
        return result


class SupplierScraperFactory:
    """Factory for creating appropriate scraper based on supplier"""
    
    SUPPLIER_MAPPING = {
        "tile rite": TileRiteScraper,
        "tilerite": TileRiteScraper,
        "tile-rite": TileRiteScraper,
        "trimline": TrimlineScraper,
        "trimline group": TrimlineScraper,
        "ultra tile": UltraTileScraper,
        "ultratile": UltraTileScraper,
        "instarmac": UltraTileScraper,
        "wallcano": "WallcanoScraper",  # Special handling - uses login
    }
    
    @classmethod
    def get_scraper(cls, supplier_name: str) -> Optional[SupplierScraper]:
        """Get the appropriate scraper for a supplier"""
        supplier_lower = supplier_name.lower().strip()
        
        for key, scraper_class in cls.SUPPLIER_MAPPING.items():
            if key in supplier_lower:
                return scraper_class()
        
        return None
    
    @classmethod
    async def scrape_product(cls, supplier_name: str, sku: str, product_name: str = "") -> Dict[str, Any]:
        """Scrape a product from the appropriate supplier"""
        scraper = cls.get_scraper(supplier_name)
        
        if not scraper:
            return {
                "sku": sku,
                "supplier": supplier_name,
                "success": False,
                "error": f"No scraper available for supplier: {supplier_name}",
                "images": []
            }
        
        async with scraper:
            return await scraper.scrape_product(sku, product_name)
    
    @classmethod
    async def scrape_products_batch(cls, products: List[Dict[str, str]], delay: float = 1.0) -> List[Dict[str, Any]]:
        """
        Scrape multiple products with rate limiting
        
        Args:
            products: List of dicts with 'supplier_name', 'sku', 'product_name'
            delay: Seconds to wait between requests
        """
        results = []
        
        # Group products by supplier for efficiency
        by_supplier: Dict[str, List[Dict[str, str]]] = {}
        for product in products:
            supplier = product.get("supplier_name", "").lower()
            if supplier not in by_supplier:
                by_supplier[supplier] = []
            by_supplier[supplier].append(product)
        
        # Process each supplier group
        for supplier, supplier_products in by_supplier.items():
            scraper = cls.get_scraper(supplier)
            
            if not scraper:
                for product in supplier_products:
                    results.append({
                        "sku": product.get("sku"),
                        "supplier": supplier,
                        "success": False,
                        "error": f"No scraper available for supplier: {supplier}",
                        "images": []
                    })
                continue
            
            async with scraper:
                for product in supplier_products:
                    result = await scraper.scrape_product(
                        product.get("sku", ""),
                        product.get("product_name", "")
                    )
                    results.append(result)
                    await asyncio.sleep(delay)  # Rate limiting
        
        return results

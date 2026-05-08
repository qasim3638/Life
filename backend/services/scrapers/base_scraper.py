"""
Base scraper class for all supplier portal scrapers.
Handles authentication, session management, and common scraping operations.
"""
import httpx
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
import json
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SupplierProduct:
    """Standard product model for all suppliers"""
    def __init__(
        self,
        supplier_code: str,
        supplier_name: str,
        name: str,
        size: str = "",
        material: str = "",
        finish: str = "",
        thickness: str = "",
        tiles_per_box: int = 0,
        sqm_per_box: float = 0.0,
        boxes_per_pallet: int = 0,
        pieces_per_sqm: float = 0.0,
        room_lot_price: float = 0.0,
        pallet_price: float = 0.0,
        stock_sqm: float = 0.0,
        stock_status: str = "unknown",
        images: List[str] = None,
        description: str = "",
        category: str = "",
        color: str = "",
        ptv_rating: str = "",
        r_rating: str = "",
        weight_per_box: float = 0.0,
        extra_data: Dict = None
    ):
        self.supplier_code = supplier_code
        self.supplier_name = supplier_name
        self.name = name
        self.size = size
        self.material = material
        self.finish = finish
        self.thickness = thickness
        self.tiles_per_box = tiles_per_box
        self.sqm_per_box = sqm_per_box
        self.boxes_per_pallet = boxes_per_pallet
        self.pieces_per_sqm = pieces_per_sqm
        self.room_lot_price = room_lot_price
        self.pallet_price = pallet_price
        self.stock_sqm = stock_sqm
        self.stock_status = stock_status
        self.images = images or []
        self.description = description
        self.category = category
        self.color = color
        self.ptv_rating = ptv_rating
        self.r_rating = r_rating
        self.weight_per_box = weight_per_box
        self.extra_data = extra_data or {}
        self.scraped_at = datetime.utcnow()
    
    def to_dict(self) -> Dict:
        return {
            "supplier_code": self.supplier_code,
            "supplier_name": self.supplier_name,
            "name": self.name,
            "size": self.size,
            "material": self.material,
            "finish": self.finish,
            "thickness": self.thickness,
            "tiles_per_box": self.tiles_per_box,
            "sqm_per_box": self.sqm_per_box,
            "boxes_per_pallet": self.boxes_per_pallet,
            "pieces_per_sqm": self.pieces_per_sqm,
            "room_lot_price": self.room_lot_price,
            "pallet_price": self.pallet_price,
            "stock_sqm": self.stock_sqm,
            "stock_status": self.stock_status,
            "images": self.images,
            "description": self.description,
            "category": self.category,
            "color": self.color,
            "ptv_rating": self.ptv_rating,
            "r_rating": self.r_rating,
            "weight_per_box": self.weight_per_box,
            "extra_data": self.extra_data,
            "scraped_at": self.scraped_at.isoformat()
        }
    
    def calculate_selling_price(self, markup_percent: float = 90.0) -> float:
        """Calculate selling price with markup on room lot price"""
        if self.room_lot_price > 0:
            return round(self.room_lot_price * (1 + markup_percent / 100), 2)
        return 0.0
    
    def get_stock_display(self) -> str:
        """Get stock display text based on quantity"""
        if self.stock_sqm <= 0:
            return "Out of Stock"
        elif self.stock_sqm < 20:
            return "Low Stock"
        else:
            return "In Stock"


class BaseScraper(ABC):
    """Base class for all supplier scrapers"""
    
    SUPPLIER_NAME = "Unknown"
    BASE_URL = ""
    
    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        self.client: Optional[httpx.AsyncClient] = None
        self.is_authenticated = False
        self.products: List[SupplierProduct] = []
        
    async def __aenter__(self):
        self.client = httpx.AsyncClient(
            timeout=60.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()
    
    @abstractmethod
    async def login(self) -> bool:
        """Authenticate with supplier portal"""
        pass
    
    @abstractmethod
    async def get_all_products(self) -> List[SupplierProduct]:
        """Fetch all products from supplier"""
        pass
    
    @abstractmethod
    async def get_product_details(self, product_id: str) -> Optional[SupplierProduct]:
        """Get detailed information for a single product"""
        pass
    
    @abstractmethod
    async def get_stock_levels(self) -> Dict[str, float]:
        """Get current stock levels for all products"""
        pass
    
    async def download_image(self, url: str) -> Optional[bytes]:
        """Download image from URL"""
        try:
            response = await self.client.get(url)
            if response.status_code == 200:
                return response.content
            return None
        except Exception as e:
            logger.error(f"Failed to download image {url}: {e}")
            return None
    
    def parse_size(self, size_str: str) -> tuple:
        """Parse size string like '60x60' into (width, height)"""
        match = re.search(r'(\d+)\s*[xX×]\s*(\d+)', size_str)
        if match:
            return int(match.group(1)), int(match.group(2))
        return None, None
    
    def parse_price(self, price_str: str) -> float:
        """Parse price string like '£12.99' into float"""
        if not price_str:
            return 0.0
        # Remove currency symbols and whitespace
        cleaned = re.sub(r'[£$€\s,]', '', str(price_str))
        try:
            return float(cleaned)
        except ValueError:
            return 0.0
    
    def parse_float(self, value: Any) -> float:
        """Safely parse a value to float"""
        if value is None:
            return 0.0
        try:
            return float(str(value).replace(',', ''))
        except ValueError:
            return 0.0
    
    def parse_int(self, value: Any) -> int:
        """Safely parse a value to int"""
        if value is None:
            return 0
        try:
            return int(float(str(value).replace(',', '')))
        except ValueError:
            return 0

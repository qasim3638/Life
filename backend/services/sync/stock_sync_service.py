"""
Stock Sync Service
Orchestrates stock synchronization across all suppliers.
Runs nightly at 2:00 AM to update all product stock levels.
"""
import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, TYPE_CHECKING
import logging
from pathlib import Path

# Lazy imports for scrapers - only import when needed to avoid Playwright issues on deployment
# This prevents import errors if Playwright browsers aren't installed
def get_wallcano_scraper():
    from services.scrapers.wallcano_scraper import WallcanoScraper, parse_wallcano_pdf_prices
    return WallcanoScraper, parse_wallcano_pdf_prices

def get_splendour_scraper():
    from services.scrapers.splendour_scraper import SplendourScraper
    return SplendourScraper

def get_verona_scraper():
    from services.scrapers.verona_scraper import VeronaScraper
    return VeronaScraper

def get_ceramica_impex_scraper():
    from services.scrapers.ceramica_impex_scraper import CeramicaImpexScraper
    return CeramicaImpexScraper

def get_base_scraper():
    from services.scrapers.base_scraper import SupplierProduct
    return SupplierProduct

from services.name_generator import get_name_generator

logger = logging.getLogger(__name__)

# Supplier credentials — passwords sourced from env vars (Feb 2026 security)
SUPPLIER_CREDENTIALS = {
    "wallcano": {
        "email": "accounts@tilestation.co.uk",
        "password": os.environ.get("WALLCANO_PORTAL_PASSWORD", "")
    },
    "splendour": {
        "email": "accounts@tilestation.co.uk",
        "password": os.environ.get("SPLENDOUR_PORTAL_PASSWORD", "")
    },
    "verona": {
        "email": "accounts@tilestation.co.uk",
        "password": os.environ.get("VERONA_PORTAL_PASSWORD", "")
    },
    "ceramica_impex": {
        "email": "qasim@tilestation.co.uk",
        "password": os.environ.get("CERAMICA_PORTAL_PASSWORD", "")
    }
}

# Markup percentage
MARKUP_PERCENT = 90.0


class SyncResult:
    """Result of a sync operation"""
    
    def __init__(self, supplier: str):
        self.supplier = supplier
        self.success = False
        self.products_synced = 0
        self.in_stock = 0
        self.low_stock = 0
        self.out_of_stock = 0
        self.errors: List[str] = []
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.duration_seconds: float = 0
    
    def to_dict(self) -> Dict:
        return {
            "supplier": self.supplier,
            "success": self.success,
            "products_synced": self.products_synced,
            "in_stock": self.in_stock,
            "low_stock": self.low_stock,
            "out_of_stock": self.out_of_stock,
            "errors": self.errors,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds
        }


class StockSyncService:
    """
    Service to synchronize stock levels from all suppliers.
    Can run full sync or individual supplier sync.
    """
    
    def __init__(self, db=None):
        self.db = db  # MongoDB database connection
        self.name_generator = get_name_generator()
        self.sync_results: Dict[str, SyncResult] = {}
        self.last_full_sync: Optional[datetime] = None
    
    async def sync_all(self) -> Dict[str, SyncResult]:
        """
        Sync all suppliers.
        This is what runs nightly at 2:00 AM.
        """
        logger.info("=" * 60)
        logger.info("STARTING FULL STOCK SYNC")
        logger.info("=" * 60)
        
        start_time = datetime.now(timezone.utc)
        
        # Sync each supplier
        suppliers = ["wallcano", "splendour", "verona", "ceramica_impex"]
        
        for supplier in suppliers:
            try:
                result = await self.sync_supplier(supplier)
                self.sync_results[supplier] = result
            except Exception as e:
                logger.error(f"Error syncing {supplier}: {e}")
                result = SyncResult(supplier)
                result.errors.append(str(e))
                self.sync_results[supplier] = result
        
        self.last_full_sync = datetime.now(timezone.utc)
        
        # Log summary
        total_products = sum(r.products_synced for r in self.sync_results.values())
        total_duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        logger.info("=" * 60)
        logger.info("FULL STOCK SYNC COMPLETE")
        logger.info(f"Total products synced: {total_products}")
        logger.info(f"Total duration: {total_duration:.1f} seconds")
        logger.info("=" * 60)
        
        # Save sync results
        await self._save_sync_results()
        
        return self.sync_results
    
    async def sync_supplier(self, supplier: str) -> SyncResult:
        """Sync a specific supplier"""
        result = SyncResult(supplier)
        result.started_at = datetime.now(timezone.utc)
        
        logger.info(f"\n{'='*40}")
        logger.info(f"Syncing {supplier.upper()}")
        logger.info(f"{'='*40}")
        
        try:
            # Get credentials
            creds = SUPPLIER_CREDENTIALS.get(supplier)
            if not creds:
                raise ValueError(f"No credentials for supplier: {supplier}")
            
            # Create scraper
            scraper = self._get_scraper(supplier, creds)
            
            # Scrape products
            products = await scraper.get_all_products()
            
            if not products:
                result.errors.append("No products returned from scraper")
                return result
            
            # Process products
            processed_products = self._process_products(products, supplier)
            
            # Save to database
            if self.db:
                await self._save_products_to_db(processed_products, supplier)
            
            # Calculate stats
            result.products_synced = len(processed_products)
            result.in_stock = len([p for p in processed_products if p.get("stock_status") == "In Stock"])
            result.low_stock = len([p for p in processed_products if p.get("stock_status") == "Low Stock"])
            result.out_of_stock = len([p for p in processed_products if p.get("stock_status") == "Out of Stock"])
            result.success = True
            
            logger.info(f"Synced {result.products_synced} products from {supplier}")
            logger.info(f"  In Stock: {result.in_stock}")
            logger.info(f"  Low Stock: {result.low_stock}")
            logger.info(f"  Out of Stock: {result.out_of_stock}")
            
        except Exception as e:
            logger.error(f"Error syncing {supplier}: {e}")
            result.errors.append(str(e))
        
        result.completed_at = datetime.now(timezone.utc)
        result.duration_seconds = (result.completed_at - result.started_at).total_seconds()
        
        return result
    
    def _get_scraper(self, supplier: str, creds: Dict):
        """Get the appropriate scraper for a supplier"""
        if supplier == "wallcano":
            # Load prices from PDF
            WallcanoScraper, parse_wallcano_pdf_prices = get_wallcano_scraper()
            pdf_path = "/app/supplier_data/wallcano_pricelist.pdf"
            prices = {}
            if os.path.exists(pdf_path):
                prices = parse_wallcano_pdf_prices(pdf_path)
            return WallcanoScraper(creds["email"], creds["password"], prices)
        
        elif supplier == "splendour":
            SplendourScraper = get_splendour_scraper()
            return SplendourScraper(creds["email"], creds["password"])
        
        elif supplier == "verona":
            VeronaScraper = get_verona_scraper()
            return VeronaScraper(creds["email"], creds["password"])
        
        elif supplier == "ceramica_impex":
            CeramicaImpexScraper = get_ceramica_impex_scraper()
            return CeramicaImpexScraper(creds["email"], creds["password"])
        
        else:
            raise ValueError(f"Unknown supplier: {supplier}")
    
    def _process_products(self, products, supplier: str) -> List[Dict]:
        """Process scraped products and generate unique names"""
        processed = []
        
        for product in products:
            # Generate unique name
            unique_name = self.name_generator.generate_name(
                supplier_name=product.name,
                material=product.material,
                finish=product.finish
            )
            
            # Calculate selling price with markup
            cost = product.room_lot_price
            selling_price = round(cost * (1 + MARKUP_PERCENT / 100), 2) if cost > 0 else 0
            
            processed_product = {
                # Our data
                "name": unique_name,
                "supplier_product_name": product.name,
                "supplier": supplier,
                "supplier_code": product.supplier_code,
                
                # Pricing
                "cost": cost,
                "price": selling_price,
                "pallet_price": product.pallet_price,
                
                # Stock
                "stock_sqm": product.stock_sqm,
                "stock_status": product.stock_status,
                
                # Specifications
                "size": product.size,
                "material": product.material,
                "finish": product.finish,
                "thickness": product.thickness,
                "tiles_per_box": product.tiles_per_box,
                "sqm_per_box": product.sqm_per_box,
                "boxes_per_pallet": product.boxes_per_pallet,
                
                # Category - can contain multiple categories comma-separated
                "category": product.category,
                
                # Images
                "images": product.images,
                
                # Metadata
                "last_synced": datetime.now(timezone.utc).isoformat(),
                "extra_data": product.extra_data
            }
            
            processed.append(processed_product)
        
        return processed
    
    async def _save_products_to_db(self, products: List[Dict], supplier: str):
        """Save products to MongoDB"""
        if not self.db:
            return
        
        collection = self.db.supplier_products
        
        for product in products:
            # Upsert by supplier + supplier_code
            await collection.update_one(
                {
                    "supplier": supplier,
                    "supplier_code": product["supplier_code"]
                },
                {"$set": product},
                upsert=True
            )
    
    async def _save_sync_results(self):
        """Save sync results to file"""
        results_dir = Path("/app/sync_results")
        results_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = results_dir / f"sync_{timestamp}.json"
        
        results_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "results": {k: v.to_dict() for k, v in self.sync_results.items()}
        }
        
        with open(results_file, "w") as f:
            json.dump(results_data, f, indent=2)
        
        logger.info(f"Sync results saved to {results_file}")
    
    def get_sync_status(self) -> Dict:
        """Get current sync status"""
        return {
            "last_full_sync": self.last_full_sync.isoformat() if self.last_full_sync else None,
            "suppliers": {k: v.to_dict() for k, v in self.sync_results.items()}
        }


# Singleton instance
_sync_service = None

def get_sync_service(db=None) -> StockSyncService:
    """Get the singleton sync service instance"""
    global _sync_service
    if _sync_service is None:
        _sync_service = StockSyncService(db)
    return _sync_service


# CLI function for testing
async def run_full_sync():
    """Run a full sync (for testing or manual trigger)"""
    service = get_sync_service()
    results = await service.sync_all()
    
    print("\n" + "=" * 60)
    print("SYNC RESULTS")
    print("=" * 60)
    
    for supplier, result in results.items():
        print(f"\n{supplier.upper()}")
        print(f"  Success: {result.success}")
        print(f"  Products: {result.products_synced}")
        print(f"  In Stock: {result.in_stock}")
        print(f"  Low Stock: {result.low_stock}")
        print(f"  Out of Stock: {result.out_of_stock}")
        print(f"  Duration: {result.duration_seconds:.1f}s")
        if result.errors:
            print(f"  Errors: {result.errors}")


if __name__ == "__main__":
    asyncio.run(run_full_sync())

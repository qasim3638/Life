"""
Scrapers package for supplier portals
"""
from .base_scraper import BaseScraper, SupplierProduct
from .wallcano_scraper import WallcanoScraper
from .splendour_scraper import SplendourScraper
from .verona_scraper import VeronaScraper
from .ceramica_impex_scraper import CeramicaImpexScraper

__all__ = [
    "BaseScraper",
    "SupplierProduct",
    "WallcanoScraper",
    "SplendourScraper",
    "VeronaScraper",
    "CeramicaImpexScraper",
]

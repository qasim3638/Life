"""
Pydantic models for Products and Categories
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime, timezone


class Category(BaseModel):
    id: str
    name: str
    description: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CategoryCreate(BaseModel):
    name: str
    description: str = ""


class Product(BaseModel):
    model_config = {"extra": "allow"}  # Allow extra fields from MongoDB
    
    id: str
    name: str
    description: str = ""
    sku: str = ""
    barcode: str = ""
    price: float
    cost_price: float = 0
    stock: int = 0
    category_id: str = ""
    category_name: str = ""
    unit: str = "piece"
    m2_quantity: Optional[float] = None
    # Tile size for m² calculation
    tile_width: Optional[float] = None
    tile_height: Optional[float] = None
    tile_m2_per_piece: Optional[float] = None
    # Tiles per box for box calculations
    tiles_per_box: Optional[float] = None
    box_m2_coverage: Optional[float] = None
    # Pallet pricing
    # Legacy single-pallet fields kept for backward-compat:
    pallet_enabled: bool = False
    pallet_quantity: Optional[int] = None
    pallet_price: Optional[float] = None
    # NEW (Feb 2026): full + half pallet, separate £/m² rates.
    # Customer must order at least `m2_per_pallet` (or `_per_half_pallet`)
    # m² to qualify for the corresponding rate. Storefront enforces.
    m2_per_pallet: Optional[float] = None              # e.g. 32.0
    m2_per_half_pallet: Optional[float] = None         # e.g. 16.0 (defaults half of full when None)
    pallet_price_per_m2: Optional[float] = None        # full-pallet £/m² rate
    half_pallet_price_per_m2: Optional[float] = None   # half-pallet £/m² rate
    # Storefront alias: the `tiles` collection stores the £/m² rate as
    # `pallet_price` (for full) and `half_pallet_price` (for half) so we
    # mirror those names on the model too — keeps admin form ↔ tiles
    # collection ↔ storefront PDP using the same field names.
    half_pallet_price: Optional[float] = None
    # Stock status — manual override. None means "use auto-derived from
    # inventory levels". One of:
    #   "in_stock" / "low_stock" / "out_of_stock" / "always_in_stock"
    stock_status: Optional[str] = None
    # Clearance
    clearance: bool = False
    clearance_price: Optional[float] = None
    # Sample availability — when True, hide "Order Sample" on the PDP
    # and Collection page for THIS product (overrides the global toggle).
    # Useful for DTP tiles, job-lot remnants, clearance stock with no
    # sample stock left, etc.
    samples_hidden: bool = False
    # Maximum discount allowed
    max_discount: Optional[float] = None
    reorder_level: int = 10
    images: List[str] = []
    # Supplier info for flexible search (allows searching by original supplier name)
    supplier: Optional[str] = None
    supplier_name: Optional[str] = None  # Supplier company name
    supplier_product_name: Optional[str] = None  # Original product name from supplier
    # Main Category & Sub-Categories (SYNCS with Bulk Category Editor)
    main_category: Optional[str] = None
    sub_categories: Optional[List[str]] = []
    # Website Categories (multi-select for e-commerce)
    rooms: Optional[List[str]] = []
    styles: Optional[List[str]] = []
    colors: Optional[List[str]] = []
    features: Optional[List[str]] = []
    materials: Optional[List[str]] = []
    finishes: Optional[List[str]] = []
    show_on_website: Optional[bool] = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProductCreate(BaseModel):
    name: str
    description: str = ""
    sku: str = ""
    barcode: str = ""
    price: float
    cost_price: float = 0
    stock: int = 0
    category_id: str = ""
    category_name: str = ""
    unit: str = "piece"
    m2_quantity: Optional[float] = None
    tile_width: Optional[float] = None
    tile_height: Optional[float] = None
    tile_m2_per_piece: Optional[float] = None
    tiles_per_box: Optional[float] = None
    box_m2_coverage: Optional[float] = None
    pallet_enabled: bool = False
    pallet_quantity: Optional[int] = None
    pallet_price: Optional[float] = None
    clearance: bool = False
    clearance_price: Optional[float] = None
    max_discount: Optional[float] = None
    reorder_level: int = 10
    images: List[str] = []


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    sku: Optional[str] = None
    barcode: Optional[str] = None
    price: Optional[float] = None
    cost_price: Optional[float] = None
    stock: Optional[int] = None
    showroom_stock: Optional[Dict[str, int]] = None
    category_id: Optional[str] = None
    category_name: Optional[str] = None
    unit: Optional[str] = None
    supplier_name: Optional[str] = None
    supplier_product_name: Optional[str] = None
    m2_quantity: Optional[float] = None
    tile_width: Optional[float] = None
    tile_height: Optional[float] = None
    tile_m2_per_piece: Optional[float] = None
    tiles_per_box: Optional[float] = None
    box_m2_coverage: Optional[float] = None
    pallet_enabled: Optional[bool] = None
    pallet_quantity: Optional[int] = None
    pallet_price: Optional[float] = None
    m2_per_pallet: Optional[float] = None
    m2_per_half_pallet: Optional[float] = None
    pallet_price_per_m2: Optional[float] = None
    half_pallet_price_per_m2: Optional[float] = None
    half_pallet_price: Optional[float] = None
    stock_status: Optional[str] = None
    clearance: Optional[bool] = None
    clearance_price: Optional[float] = None
    samples_hidden: Optional[bool] = None
    max_discount: Optional[float] = None
    reorder_level: Optional[int] = None
    images: Optional[List[str]] = None
    # Main Category & Sub-Categories (SYNCS with Bulk Category Editor)
    main_category: Optional[str] = None
    sub_categories: Optional[List[str]] = None
    # Website Categories (multi-select for e-commerce)
    rooms: Optional[List[str]] = None
    styles: Optional[List[str]] = None
    colors: Optional[List[str]] = None
    features: Optional[List[str]] = None
    materials: Optional[List[str]] = None
    finishes: Optional[List[str]] = None
    show_on_website: Optional[bool] = None

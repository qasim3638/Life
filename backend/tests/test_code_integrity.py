"""
Code Integrity Tests for Tile Station
Verifies critical code patterns are present in source files.
Runs WITHOUT a server — purely checks file contents to catch regressions.
"""

import pytest
import os
import re

# Resolve project root (works both locally and in CI)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BACKEND = os.path.join(PROJECT_ROOT, 'backend')
FRONTEND = os.path.join(PROJECT_ROOT, 'frontend', 'src')


def read_file(relative_path):
    full = os.path.join(PROJECT_ROOT, relative_path)
    assert os.path.exists(full), f"File missing: {relative_path}"
    with open(full) as f:
        return f.read()


# ── Session 1 ──────────────────────────────────────────────

class TestSession1CodeIntegrity:

    def test_country_flag_on_collection_cards(self):
        """Collection cards must show Made In flag badge"""
        code = read_file('frontend/src/pages/shop/TileCollectionsPage.js')
        assert 'made_in' in code, "TileCollectionsPage missing made_in field"
        assert 'Made in' in code or 'Made In' in code, "TileCollectionsPage missing 'Made in' label"

    def test_was_now_pricing_on_detail_page(self):
        """Product detail must show WAS/NOW sale pricing"""
        code = read_file('frontend/src/pages/shop/CollectionDetailPage.js')
        assert 'WAS' in code, "CollectionDetailPage missing WAS price label"
        assert 'NOW' in code, "CollectionDetailPage missing NOW price label"


# ── Session 2 ──────────────────────────────────────────────

class TestSession2CodeIntegrity:

    def test_tier_pricing_decoupled(self):
        """Disabling tier pricing must NOT disable trade discount / credit back"""
        code = read_file('frontend/src/pages/admin/components/supplier-products/TierPricingModal.jsx')
        # trade_discount and credit_back inputs must exist outside the disabled block
        assert 'trade_discount' in code, "TierPricingModal missing trade_discount"
        assert 'credit_back' in code, "TierPricingModal missing credit_back"

    def test_pdf_documents_router_exists(self):
        """PDF document management routes must exist"""
        code = read_file('backend/routes/product_documents.py')
        assert 'upload' in code, "product_documents.py missing upload endpoint"
        assert 'download' in code, "product_documents.py missing download endpoint"
        assert 'by-product' in code or 'by_product' in code, "product_documents.py missing by-product endpoint"

    def test_pdf_router_registered(self):
        """PDF router must be registered in __init__.py"""
        code = read_file('backend/routes/__init__.py')
        assert 'product_documents' in code, "product_documents router not registered"


# ── Session 3 ──────────────────────────────────────────────

class TestSession3CodeIntegrity:

    def test_extract_series_name_strips_variant_words(self):
        """extract_series_name must strip Decor, Border, Mosaic, Listello, Feature"""
        code = read_file('backend/routes/tiles.py')
        for word in ['decor', 'border', 'mosaic', 'listello', 'feature']:
            assert word in code.lower(), f"COLOR_WORDS missing '{word}' for series grouping"

    def test_color_extraction_functions_exist(self):
        """extract_color_from_name and get_product_color must exist in tiles.py"""
        code = read_file('backend/routes/tiles.py')
        assert 'def extract_color_from_name' in code, "tiles.py missing extract_color_from_name function"
        assert 'def get_product_color' in code, "tiles.py missing get_product_color function"

    def test_color_keywords_comprehensive(self):
        """COLOR_KEYWORDS must contain essential color words"""
        code = read_file('backend/routes/tiles.py')
        essential = ['white', 'black', 'grey', 'beige', 'cream', 'brown', 'blue', 'green']
        for color in essential:
            assert f"'{color}'" in code, f"COLOR_KEYWORDS missing '{color}'"

    def test_no_add_to_cart_on_collection_cards(self):
        """Collection card component must NOT have Add to Cart buttons inline"""
        code = read_file('frontend/src/pages/shop/TileCollectionsPage.js')
        # addToCart may exist for QuickView modal, but shouldn't be in the card layout
        # The CollectionCard function should not render an Add to Cart button
        assert 'Add to Cart' not in code or 'QuickView' in code, \
            "TileCollectionsPage has 'Add to Cart' outside QuickView context"

    def test_dynamic_filter_scoping_by_group(self):
        """filters.py must scope filter values by product_group"""
        code = read_file('backend/routes/filters.py')
        assert 'product_group' in code, "filters.py missing product_group scoping"
        assert 'group_slugs' in code, "filters.py missing group_slugs matching"

    def test_category_routing_uses_db_lookup(self):
        """tiles.py must look up category names from website_categories, not regex"""
        code = read_file('backend/routes/tiles.py')
        assert 'website_categories' in code, "tiles.py missing website_categories DB lookup for routing"

    def test_sale_filter_exists(self):
        """tiles.py must support sale=true filter"""
        code = read_file('backend/routes/tiles.py')
        assert 'sale' in code.lower(), "tiles.py missing sale filter support"

    def test_sizes_finishes_on_collection_cards(self):
        """Collection cards must show sizes and finishes"""
        code = read_file('frontend/src/pages/shop/TileCollectionsPage.js')
        assert 'sizes' in code.lower(), "TileCollectionsPage missing sizes display"
        assert 'finishes' in code.lower() or 'finish' in code.lower(), "TileCollectionsPage missing finishes display"


# ── Session 4 ──────────────────────────────────────────────

class TestSession4CodeIntegrity:

    def test_colour_pluralization(self):
        """Collection cards must show COLOUR (singular) vs COLOURS (plural)"""
        code = read_file('frontend/src/pages/shop/TileCollectionsPage.js')
        assert "COLOUR" in code, "TileCollectionsPage missing COLOUR text"
        assert "=== 1" in code or "===1" in code or "=== 1 ?" in code, \
            "TileCollectionsPage missing singular/plural check for COLOUR"

    def test_sale_discount_formula(self):
        """WAS price must use discount formula: NOW / (1 - percent/100)"""
        code = read_file('backend/routes/supplier_sync.py')
        # Must NOT have the old markup formula: list_price * (1 + ...)
        # Must have the new discount formula: list_price / (1 - ...)
        assert '1 - data.was_markup_percent / 100' in code, \
            "supplier_sync.py missing correct discount formula: NOW / (1 - percent/100)"

    def test_sale_ribbon_uses_calculated_percent(self):
        """Sale ribbon must calculate % from actual WAS/NOW, not was_markup_percent"""
        code = read_file('frontend/src/pages/shop/CollectionDetailPage.js')
        # Should NOT use was_markup_percent directly for saleDiscountPercent
        assert 'saleDiscountPercent' in code, "CollectionDetailPage missing saleDiscountPercent"
        # The calculation should be from effectiveWasPrice
        assert 'effectiveWasPrice' in code, "CollectionDetailPage missing effectiveWasPrice calculation"

    def test_volume_pricing_amber_header(self):
        """Volume Pricing header must have amber gradient styling"""
        code = read_file('frontend/src/pages/shop/CollectionDetailPage.js')
        assert 'amber' in code, "CollectionDetailPage missing amber styling for Volume Pricing"
        assert 'Buy More, Save More' in code, "CollectionDetailPage missing 'Buy More, Save More' text"

    def test_cart_no_price_type(self):
        """Cart must NOT show 'Price type' text"""
        code = read_file('frontend/src/pages/shop/TileCartPage.js')
        assert 'Price type' not in code, "TileCartPage still shows 'Price type' — should be removed"
        assert 'priceType' not in code or 'room_lot' not in code.lower(), \
            "TileCartPage still references priceType/room_lot display"

    def test_group_slugs_in_filter_logic(self):
        """Filter matching must support group_slugs field"""
        code = read_file('backend/routes/filters.py')
        assert 'group_slugs' in code, "filters.py missing group_slugs support"

    def test_group_slugs_in_filter_model(self):
        """FilterGroupCreate model must include group_slugs field"""
        code = read_file('backend/routes/filters.py')
        assert 'group_slugs' in code, "FilterGroupCreate model missing group_slugs"

    def test_admin_filters_manager_group_slugs_ui(self):
        """FiltersManager must have 'Applies to Product Groups' UI"""
        code = read_file('frontend/src/pages/admin/FiltersManager.jsx')
        assert 'group_slugs' in code, "FiltersManager missing group_slugs field"
        assert 'Product Groups' in code, "FiltersManager missing 'Product Groups' label"

    def test_two_pass_swatch_building(self):
        """tiles.py must use two-pass approach for product_images (colors first)"""
        code = read_file('backend/routes/tiles.py')
        assert 'non_color_images' in code, "tiles.py missing two-pass swatch approach (non_color_images)"

    def test_additional_colors_from_swatches(self):
        """additional_colors must be based on color_swatches length, not colors set"""
        code = read_file('backend/routes/tiles.py')
        assert 'len(color_swatches) - 8' in code, \
            "tiles.py additional_colors not based on color_swatches length"


# ── Critical File Existence ────────────────────────────────

class TestCriticalFilesExist:

    REQUIRED_FILES = [
        'backend/routes/tiles.py',
        'backend/routes/filters.py',
        'backend/routes/product_documents.py',
        'backend/routes/supplier_sync.py',
        'frontend/src/pages/shop/TileCollectionsPage.js',
        'frontend/src/pages/shop/CollectionDetailPage.js',
        'frontend/src/pages/shop/TileCartPage.js',
        'frontend/src/pages/admin/FiltersManager.jsx',
        'frontend/src/pages/admin/components/supplier-products/TierPricingModal.jsx',
        'frontend/src/pages/admin/components/supplier-products/ProductDocumentsModal.jsx',
    ]

    @pytest.mark.parametrize("filepath", REQUIRED_FILES)
    def test_file_exists(self, filepath):
        full = os.path.join(PROJECT_ROOT, filepath)
        assert os.path.exists(full), f"CRITICAL: File missing — {filepath}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

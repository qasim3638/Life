"""Tests for the Google Shopping XML feed."""
from __future__ import annotations

import pytest

from routes import google_shopping_feed as feed


# ───── Product taxonomy mapping ─────

def test_outdoor_category_maps_to_pavers():
    assert "Pavers" in feed._google_product_category("Outdoor Tiles")
    assert "Stepping Stones" in feed._google_product_category("Outdoor Tiles")


def test_wall_tile_category_maps_to_tile():
    assert feed._google_product_category("Wall Tiles") == "Hardware > Building Materials > Tile"


def test_default_category_is_tile():
    assert feed._google_product_category("Bathroom") == "Hardware > Building Materials > Tile"
    assert feed._google_product_category("Floor Tiles") == "Hardware > Building Materials > Tile"
    assert feed._google_product_category("") == "Hardware > Building Materials > Tile"


def test_category_handles_none():
    assert feed._google_product_category(None) == "Hardware > Building Materials > Tile"


# ───── _product_to_item_xml ─────

def test_product_to_item_xml_happy_path():
    product = {
        "id": "tile-123",
        "slug": "calacatta-marble-60x60",
        "name": "Calacatta Marble 60x60",
        "description": "Premium marble tile",
        "category": "Bathroom",
        "image_url": "https://images.tilestation.co.uk/test.jpg",
        "images": ["https://images.tilestation.co.uk/test.jpg"],
        "price": 28.99,
        "stock": 50,
        "size": "60x60cm",
        "color": "White",
        "finish": "Polished",
    }
    xml = feed._product_to_item_xml(product, "https://tilestation.co.uk")
    assert xml is not None
    assert "<g:id>tile-123</g:id>" in xml
    assert "<title>Calacatta Marble 60x60</title>" in xml
    assert "<g:price>28.99 GBP</g:price>" in xml
    assert "<g:availability>in_stock</g:availability>" in xml
    assert "<g:brand>Tile Station</g:brand>" in xml
    assert "60x60cm" in xml
    assert "utm_source=google_shopping" in xml


def test_product_xml_returns_none_without_essentials():
    # Missing slug
    assert feed._product_to_item_xml(
        {"id": "x", "name": "A", "image_url": "https://x.com/i.jpg", "price": 1}, "https://t.co",
    ) is None
    # Missing name
    assert feed._product_to_item_xml(
        {"id": "x", "slug": "a", "image_url": "https://x.com/i.jpg", "price": 1}, "https://t.co",
    ) is None
    # Missing image
    assert feed._product_to_item_xml(
        {"id": "x", "slug": "a", "name": "A", "price": 1}, "https://t.co",
    ) is None
    # Zero price
    assert feed._product_to_item_xml(
        {"id": "x", "slug": "a", "name": "A", "image_url": "https://x.com/i.jpg", "price": 0}, "https://t.co",
    ) is None


def test_product_xml_out_of_stock_when_zero_stock():
    product = {
        "id": "x", "slug": "a", "name": "A",
        "image_url": "https://x.com/i.jpg", "price": 5.0,
        "stock": 0,
    }
    xml = feed._product_to_item_xml(product, "https://t.co")
    assert "out_of_stock" in xml


def test_product_xml_assumes_in_stock_when_stock_field_missing():
    product = {
        "id": "x", "slug": "a", "name": "A",
        "image_url": "https://x.com/i.jpg", "price": 5.0,
    }
    xml = feed._product_to_item_xml(product, "https://t.co")
    assert "in_stock" in xml


def test_product_xml_handles_dict_stock():
    """Stock can be per-warehouse dict — should sum it."""
    product = {
        "id": "x", "slug": "a", "name": "A",
        "image_url": "https://x.com/i.jpg", "price": 5.0,
        "stock": {"warehouse_a": 10, "warehouse_b": 5},
    }
    xml = feed._product_to_item_xml(product, "https://t.co")
    assert "in_stock" in xml


def test_product_xml_escapes_special_chars():
    """HTML/XML special chars in name must be escaped."""
    product = {
        "id": "x", "slug": "a", "name": "A & B <c> \"d\"",
        "image_url": "https://x.com/i.jpg", "price": 5.0,
    }
    xml = feed._product_to_item_xml(product, "https://t.co")
    assert "&amp;" in xml
    assert "&lt;" in xml
    assert "<c>" not in xml  # raw < should not be in output


def test_product_xml_filters_http_only_images():
    """HTTPS only — http:// images should not be used."""
    product = {
        "id": "x", "slug": "a", "name": "A",
        "image_url": "http://insecure.com/i.jpg",
        "price": 5.0,
    }
    xml = feed._product_to_item_xml(product, "https://t.co")
    assert xml is None


def test_product_xml_truncates_long_titles():
    product = {
        "id": "x", "slug": "a", "name": "X" * 300,
        "image_url": "https://x.com/i.jpg", "price": 5.0,
    }
    xml = feed._product_to_item_xml(product, "https://t.co")
    # Title in XML should be capped at 150
    import re
    title_match = re.search(r"<title>([^<]*)</title>", xml)
    assert title_match
    assert len(title_match.group(1)) <= 150


def test_product_xml_extra_images_capped_at_9():
    product = {
        "id": "x", "slug": "a", "name": "A",
        "images": [f"https://img.com/{i}.jpg" for i in range(15)],
        "image_url": "https://img.com/0.jpg",
        "price": 5.0,
    }
    xml = feed._product_to_item_xml(product, "https://t.co")
    assert xml is not None
    # Count additional_image_link tags (cap = 9, plus the main image_link)
    assert xml.count("<g:additional_image_link>") <= 9

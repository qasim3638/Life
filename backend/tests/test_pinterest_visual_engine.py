"""Tests for the Pinterest Visual Engine — engine + queue logic."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services import pinterest_engine as engine
from services import pinterest_queue as queue


# ───── engine.match_product_to_boards ─────

def test_bathroom_product_matches_bathroom_boards():
    product = {
        "name": "Calacatta Marble 60x60",
        "category": "Bathroom",
        "description": "Premium marble bathroom tile",
        "collection": "Calacatta",
    }
    slugs = engine.match_product_to_boards(product)
    assert "bathroom-ideas" in slugs
    # Calacatta keyword should pull luxury board too
    assert "luxury-bathroom-suites" in slugs
    # Limit of 3 boards max
    assert len(slugs) <= 3


def test_outdoor_product_matches_outdoor_boards():
    product = {
        "name": "Stone Effect 20mm Paver",
        "category": "Outdoor Tiles",
        "description": "Outdoor patio paver, R11 anti-slip",
        "collection": "Outdoor Stone",
    }
    slugs = engine.match_product_to_boards(product)
    assert "outdoor-patios" in slugs
    # At least one of patio-ideas / garden-ideas should also match
    assert any(s in slugs for s in ("patio-ideas", "garden-ideas"))


def test_unmatched_product_falls_back_to_whole_home():
    product = {
        "name": "Random Test Product",
        "category": "Random Category",
        "description": "Has no relevant keywords",
        "collection": "Random",
    }
    slugs = engine.match_product_to_boards(product)
    assert slugs == ["whole-home-renovation"]


def test_blog_target_boards_excluded_from_product_matching():
    """How-To and Whole-Home are reserved for blog Pins, not products
    (except as the no-match fallback)."""
    product = {
        "name": "Tutorial Tile Calacatta Bathroom How To",
        "category": "Bathroom",
        "description": "how to lay marble tutorial",
        "collection": "Calacatta",
    }
    slugs = engine.match_product_to_boards(product)
    # how-to-tile has link_target=blog, must NOT appear here
    assert "how-to-tile" not in slugs
    # bathroom-ideas should still match because of Bathroom category
    assert "bathroom-ideas" in slugs


def test_default_boards_have_required_fields():
    for board in engine.DEFAULT_BOARDS:
        assert board["slug"]
        assert board["name"]
        assert board["description"]
        assert "auto_approve" in board
        assert "category_match" in board
        assert "keywords" in board
        assert board["link_target"] in ("product", "blog", "collection")
        assert board["priority"] in (1, 2, 3)


def test_board_by_slug():
    b = engine.board_by_slug("bathroom-ideas")
    assert b is not None
    assert b["name"].startswith("Bathroom")
    assert engine.board_by_slug("nonexistent") is None


# ───── queue._template_pin_copy (deterministic fallback) ─────

def test_template_pin_copy_under_limits():
    product = {"name": "Calacatta Marble 60x60", "category": "Bathroom"}
    board = engine.board_by_slug("bathroom-ideas")
    out = queue._template_pin_copy(product, board)
    assert len(out["title"]) <= 100
    assert len(out["description"]) <= 500
    assert len(out["alt_text"]) <= 200
    assert out["title"]
    assert out["description"]


def test_template_pin_copy_includes_board_keyword():
    product = {"name": "Black Slate Outdoor Paver", "category": "Outdoor Tiles"}
    board = engine.board_by_slug("outdoor-patios")
    out = queue._template_pin_copy(product, board)
    # Description should mention the product name
    assert "Black Slate Outdoor Paver" in out["description"]


def test_template_pin_copy_handles_missing_fields():
    product = {}
    board = engine.board_by_slug("garden-ideas")
    out = queue._template_pin_copy(product, board)
    assert out["title"]
    assert out["description"]


# ───── queue._product_link ─────

def test_product_link_includes_utm_tracking(monkeypatch):
    monkeypatch.setenv("FRONTEND_BASE_URL", "https://tilestation.co.uk")
    link = queue._product_link({"slug": "calacatta-marble-60x60"})
    assert link.startswith("https://tilestation.co.uk/shop/product/calacatta-marble-60x60")
    assert "utm_source=pinterest" in link
    assert "utm_medium=organic" in link
    assert "utm_campaign=visual_engine" in link


def test_product_link_uses_default_when_no_env(monkeypatch):
    monkeypatch.delenv("FRONTEND_BASE_URL", raising=False)
    link = queue._product_link({"slug": "test-tile"})
    assert "tilestation.co.uk" in link
    assert "/shop/product/test-tile" in link


# ───── queue._select_hero_image ─────

@pytest.mark.asyncio
async def test_select_hero_image_prefers_lifestyle_when_multiple():
    """When images array has multiple URLs, picks the LAST one (suppliers
    put cutouts first, lifestyle later)."""
    product = {
        "images": [
            "https://example.com/cutout.jpg",
            "https://example.com/closeup.jpg",
            "https://example.com/lifestyle-bathroom.jpg",
        ],
        "image_url": "https://example.com/cutout.jpg",
    }
    result = await queue._select_hero_image(product, set())
    assert result["url"] == "https://example.com/lifestyle-bathroom.jpg"
    assert result["tier"] == "lifestyle"


@pytest.mark.asyncio
async def test_select_hero_image_single_image_marked_as_product():
    """Single image = no lifestyle context → labelled product cutout."""
    product = {
        "images": ["https://example.com/only.jpg"],
        "image_url": "https://example.com/only.jpg",
    }
    result = await queue._select_hero_image(product, set())
    assert result["tier"] == "product"


@pytest.mark.asyncio
async def test_select_hero_image_falls_back_to_image_url():
    product = {"image_url": "https://example.com/cutout.jpg"}
    result = await queue._select_hero_image(product, set())
    assert result["url"] == "https://example.com/cutout.jpg"
    assert result["tier"] == "product"


@pytest.mark.asyncio
async def test_select_hero_image_skips_blocked():
    product = {
        "images": [
            "https://example.com/blocked.jpg",
            "https://example.com/good.jpg",
        ],
    }
    blocked = {"https://example.com/blocked.jpg"}
    result = await queue._select_hero_image(product, blocked)
    assert result["url"] == "https://example.com/good.jpg"


@pytest.mark.asyncio
async def test_select_hero_image_rejects_http_only():
    """Pinterest API requires HTTPS — refuse plain HTTP."""
    product = {
        "images": ["http://insecure.example.com/img.jpg"],
        "image_url": "http://insecure.example.com/img.jpg",
    }
    result = await queue._select_hero_image(product, set())
    assert result is None


@pytest.mark.asyncio
async def test_select_hero_image_returns_none_when_empty():
    result = await queue._select_hero_image({}, set())
    assert result is None


# ───── queue._next_drip_slot ─────

def test_next_drip_slot_offsets_correctly():
    s0 = queue._next_drip_slot(0)
    s1 = queue._next_drip_slot(1)
    s2 = queue._next_drip_slot(2)
    # Each successive Pin in the same batch is one drip-interval later
    # (allow a few ms tolerance — wall-clock advances between calls)
    delta_01 = (s1 - s0).total_seconds()
    delta_12 = (s2 - s1).total_seconds()
    assert abs(delta_01 - queue.DRIP_INTERVAL_MINUTES * 60) < 1.0
    assert abs(delta_12 - queue.DRIP_INTERVAL_MINUTES * 60) < 1.0


# ───── queue._serialize ─────

def test_serialize_handles_none():
    assert queue._serialize(None) is None


def test_serialize_converts_datetimes():
    from datetime import datetime, timezone
    row = {
        "id": "x",
        "title": "T",
        "created_at": datetime(2026, 5, 4, 12, 0, tzinfo=timezone.utc),
        "approved_at": datetime(2026, 5, 4, 13, 0, tzinfo=timezone.utc),
    }
    out = queue._serialize(row)
    assert isinstance(out["created_at"], str)
    assert isinstance(out["approved_at"], str)
    assert out["title"] == "T"


# ───── queue.drip_dispatch_tick — locked path ─────

@pytest.mark.asyncio
async def test_drip_dispatch_returns_locked_when_no_token():
    fake_pin_settings = AsyncMock(return_value={})
    with patch("services.pinterest.get_settings", new=fake_pin_settings):
        result = await queue.drip_dispatch_tick()
    assert result["dispatched"] == 0
    assert result["reason"] == "integration_not_connected"


@pytest.mark.asyncio
async def test_drip_dispatch_skips_when_no_board():
    fake_pin_settings = AsyncMock(return_value={"access_token": "tok"})
    with patch("services.pinterest.get_settings", new=fake_pin_settings):
        result = await queue.drip_dispatch_tick()
    assert result["dispatched"] == 0
    assert result["reason"] == "integration_not_connected"

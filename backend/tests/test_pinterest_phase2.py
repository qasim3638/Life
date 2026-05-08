"""Tests for Pinterest Engine Phase 2 — seasonal, A/B, carousel, repin."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from services import pinterest_engine_phase2 as p2
from services import pinterest_engine as engine


# ───── Seasonal weighting ─────

def test_seasonal_weight_january_boosts_bathroom():
    jan = datetime(2026, 1, 15, tzinfo=timezone.utc)
    assert p2.seasonal_weight("bathroom-ideas", jan) > 0
    assert p2.seasonal_weight("luxury-bathroom-suites", jan) > 0


def test_seasonal_weight_summer_boosts_outdoor():
    may = datetime(2026, 5, 15, tzinfo=timezone.utc)
    assert p2.seasonal_weight("outdoor-patios", may) > 0
    assert p2.seasonal_weight("garden-ideas", may) > 0
    assert p2.seasonal_weight("patio-ideas", may) > 0


def test_seasonal_weight_summer_penalises_indoor():
    may = datetime(2026, 5, 15, tzinfo=timezone.utc)
    # Bathroom not actively boosted in May (might be 0 or negative)
    assert p2.seasonal_weight("bathroom-ideas", may) <= 1


def test_seasonal_weight_autumn_boosts_kitchen():
    oct = datetime(2026, 10, 15, tzinfo=timezone.utc)
    assert p2.seasonal_weight("kitchen-ideas", oct) > 0


def test_seasonal_weight_unknown_board_returns_zero():
    when = datetime(2026, 6, 15, tzinfo=timezone.utc)
    assert p2.seasonal_weight("nonexistent-board", when) == 0


def test_seasonal_weight_all_months_have_some_boosts():
    """Every month should have at least one board boost defined."""
    for month in range(1, 13):
        when = datetime(2026, month, 15, tzinfo=timezone.utc)
        any_board_boosted = any(
            p2.seasonal_weight(b["slug"], when) > 0
            for b in engine.DEFAULT_BOARDS
        )
        assert any_board_boosted, f"No boards boosted in month {month}"


# ───── Match product to boards w/ seasonal applied ─────

def test_match_product_with_seasonal_jan_pushes_bathroom_high():
    """In January, a generic Floor Tile should still bias toward bathroom-ideas
    over outdoor-patios via seasonal weighting."""
    product = {
        "name": "Calacatta Marble 60x60",
        "category": "Bathroom",
        "description": "Premium marble bathroom tile",
        "collection": "Calacatta",
    }
    # Force January for deterministic test
    fake_jan = datetime(2026, 1, 15, tzinfo=timezone.utc)
    with patch("services.pinterest_engine_phase2.datetime") as mock_dt:
        mock_dt.now.return_value = fake_jan
        slugs = engine.match_product_to_boards(product)
    # Bathroom should still rank top after seasonal bump
    assert "bathroom-ideas" in slugs


# ───── Carousel slide builder ─────

def test_carousel_slides_returns_4_slides():
    product = {
        "name": "Test Tile",
        "images": [
            "https://example.com/cutout.jpg",
            "https://example.com/closeup.jpg",
            "https://example.com/lifestyle.jpg",
            "https://example.com/altcontext.jpg",
        ],
        "image_url": "https://example.com/cutout.jpg",
    }
    slides = p2.build_carousel_slides(product, "https://example.com/lifestyle.jpg")
    assert len(slides) == 4
    # First slide is the hero
    assert slides[0]["url"] == "https://example.com/lifestyle.jpg"
    # All slides have alt text
    assert all(s.get("alt_text") for s in slides)
    # All slides have a URL
    assert all(s.get("url") for s in slides)


def test_carousel_slides_with_only_hero():
    """If product has only 1 image, all 4 slides fall back to that image."""
    product = {
        "name": "Single Image Tile",
        "image_url": "https://example.com/only.jpg",
        "images": [],
    }
    slides = p2.build_carousel_slides(product, "https://example.com/only.jpg")
    assert len(slides) == 4
    # Every slide URL is valid (might repeat the hero)
    for s in slides:
        assert s["url"].startswith("https://")


def test_carousel_slides_filters_non_https():
    product = {
        "name": "Mixed",
        "images": [
            "http://insecure.example.com/a.jpg",
            "https://secure.example.com/b.jpg",
        ],
        "image_url": "https://hero.example.com/h.jpg",
    }
    slides = p2.build_carousel_slides(product, "https://hero.example.com/h.jpg")
    # No slide should reference the http:// URL
    for s in slides:
        assert not s["url"].startswith("http://insecure")


# ───── Scene prompt generator ─────

def test_scene_prompt_outdoor_includes_garden_context():
    prompt = p2._scene_prompt_for("Stone Paver", "Outdoor Tiles")
    assert "garden" in prompt.lower() or "patio" in prompt.lower()
    assert "Stone Paver" in prompt


def test_scene_prompt_bathroom_includes_bathroom_context():
    prompt = p2._scene_prompt_for("Calacatta Marble", "Bathroom")
    assert "bathroom" in prompt.lower()
    assert "Calacatta Marble" in prompt


def test_scene_prompt_wall_tile_context():
    prompt = p2._scene_prompt_for("Subway Tile", "Wall Tiles")
    assert "splashback" in prompt.lower() or "wall" in prompt.lower() or "kitchen" in prompt.lower()


def test_scene_prompt_unknown_category_falls_back():
    prompt = p2._scene_prompt_for("Mystery Tile", "Some Random")
    assert prompt
    assert "interior" in prompt.lower() or "home" in prompt.lower()


# ───── Performance loop — locked path ─────

@pytest.mark.asyncio
async def test_sync_pin_performance_skips_when_no_token():
    from unittest.mock import AsyncMock
    fake = AsyncMock(return_value={})
    with patch("services.pinterest.get_settings", new=fake):
        result = await p2.sync_pin_performance()
    assert result["synced"] == 0
    assert result["reason"] == "integration_not_connected"


# ───── Image URL extraction ─────

def test_extract_image_url_from_string_http():
    assert p2._extract_image_url("https://example.com/img.jpg") == "https://example.com/img.jpg"


def test_extract_image_url_from_data_url():
    data = "data:image/png;base64,iVBORw0KGgo="
    assert p2._extract_image_url(data) == data


def test_extract_image_url_from_dict():
    assert p2._extract_image_url({"image_url": "https://x.com/i.jpg"}) == "https://x.com/i.jpg"
    assert p2._extract_image_url({"url": "https://x.com/i.jpg"}) == "https://x.com/i.jpg"


def test_extract_image_url_returns_none_for_invalid():
    assert p2._extract_image_url(None) is None
    assert p2._extract_image_url("not a url") is None
    assert p2._extract_image_url({"foo": "bar"}) is None


# ───── Lifestyle render queue ─────

@pytest.mark.asyncio
async def test_queue_lifestyle_render_skips_without_emergent_key(monkeypatch):
    monkeypatch.delenv("EMERGENT_LLM_KEY", raising=False)
    result = await p2.queue_lifestyle_render({"slug": "test-tile", "name": "Test"})
    assert result is None


@pytest.mark.asyncio
async def test_queue_lifestyle_render_skips_when_no_slug(monkeypatch):
    monkeypatch.setenv("EMERGENT_LLM_KEY", "fake-key")
    result = await p2.queue_lifestyle_render({"name": "No slug"})
    assert result is None

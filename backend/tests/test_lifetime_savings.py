"""Unit tests for services.lifetime_savings — pure-function math."""
from __future__ import annotations

import pytest

from services import lifetime_savings as ls


def test_compute_breakdown_zero_counts_returns_six_zero_rows():
    rows = ls._compute_breakdown({})
    assert len(rows) == 6
    for r in rows:
        assert r["count"] == 0
        assert r["value_gbp"] == 0
        assert r["rate_gbp"] > 0  # rates always shown


def test_compute_breakdown_math_matches_rate_card():
    counts = {
        "blog_articles": 3,
        "stealth_promotions": 5,
        "city_pages": 168,
        "banners": 15,
        "videos": 1,
        "stealth_kw_filled_products": 777,
    }
    rows = ls._compute_breakdown(counts)
    by_key = {r["key"]: r for r in rows}

    # Defensible math — multiply count × rate, no fudge factors
    assert by_key["blog_articles"]["value_gbp"] == 3 * 600
    assert by_key["city_pages"]["value_gbp"] == 168 * 200
    assert by_key["stealth_kw_filled_products"]["value_gbp"] == 777 * 15
    assert by_key["stealth_promotions"]["value_gbp"] == 5 * 75
    assert by_key["banners"]["value_gbp"] == 15 * 150
    assert by_key["videos"]["value_gbp"] == 1 * 400


def test_rates_card_is_a_dict_with_six_known_keys():
    expected = {
        "blog_article", "stealth_keyword", "city_page",
        "marketing_banner", "marketing_video", "stealth_kw_filled_product",
    }
    assert set(ls.RATES_GBP.keys()) == expected
    assert all(v > 0 for v in ls.RATES_GBP.values())


def test_breakdown_total_matches_summed_rows():
    counts = {
        "blog_articles": 2,
        "stealth_promotions": 0,
        "city_pages": 50,
        "banners": 10,
        "videos": 0,
        "stealth_kw_filled_products": 100,
    }
    rows = ls._compute_breakdown(counts)
    total = sum(r["value_gbp"] for r in rows)
    expected = 2 * 600 + 0 + 50 * 200 + 10 * 150 + 0 + 100 * 15
    assert total == expected


def test_compute_breakdown_includes_human_explainer_strings():
    rows = ls._compute_breakdown({"blog_articles": 1})
    blog_row = next(r for r in rows if r["key"] == "blog_articles")
    assert "copywriter" in blog_row["explainer"].lower()
    assert "£600" in blog_row["explainer"]


@pytest.mark.asyncio
async def test_safe_returns_default_on_exception():
    async def boom():
        raise RuntimeError("fail")

    result = await ls._safe(boom(), "test_label", default=42)
    assert result == 42


@pytest.mark.asyncio
async def test_safe_returns_value_on_success():
    async def ok():
        return 99

    result = await ls._safe(ok(), "test_label", default=42)
    assert result == 99

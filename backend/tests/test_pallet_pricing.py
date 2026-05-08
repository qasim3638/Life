"""Tests for services.pallet_pricing — guarantees the 3 trade pricing
modes do exactly what's documented and prevents regressions."""
from __future__ import annotations

import pytest

from services.pallet_pricing import (
    PALLET_PRICING_MODES,
    STOCK_STATUSES,
    compute_pallet_pricing,
    derive_stock_status,
    effective_pallet_rate,
    half_pallet_m2,
    is_pallet_visible_to_customer,
)


# -- is_pallet_visible_to_customer --------------------------------------

def test_visibility_same_mode_visible_for_all():
    assert is_pallet_visible_to_customer(mode="same", is_trade=True)
    assert is_pallet_visible_to_customer(mode="same", is_trade=False)


def test_visibility_trade_only_hides_retail():
    assert is_pallet_visible_to_customer(mode="trade_only", is_trade=True)
    assert not is_pallet_visible_to_customer(mode="trade_only", is_trade=False)


def test_visibility_extra_discount_visible_for_all():
    assert is_pallet_visible_to_customer(mode="trade_extra_discount", is_trade=True)
    assert is_pallet_visible_to_customer(mode="trade_extra_discount", is_trade=False)


# -- effective_pallet_rate ----------------------------------------------

def test_rate_unchanged_in_same_mode():
    assert effective_pallet_rate(base_rate_per_m2=28.0, is_trade=False, mode="same") == 28.0
    assert effective_pallet_rate(base_rate_per_m2=28.0, is_trade=True, mode="same") == 28.0


def test_rate_unchanged_for_retail_in_extra_discount_mode():
    """Extra discount only applies to TRADE customers; retail pays
    full pallet rate."""
    rate = effective_pallet_rate(
        base_rate_per_m2=30.0, is_trade=False,
        mode="trade_extra_discount", extra_discount_pct=10,
    )
    assert rate == 30.0


def test_rate_discounted_for_trade_in_extra_discount_mode():
    rate = effective_pallet_rate(
        base_rate_per_m2=30.0, is_trade=True,
        mode="trade_extra_discount", extra_discount_pct=10,
    )
    assert rate == 27.0


def test_rate_clamped_when_pct_invalid():
    """Negative pct or >100 should be clamped, never inflate."""
    rate_neg = effective_pallet_rate(
        base_rate_per_m2=30.0, is_trade=True,
        mode="trade_extra_discount", extra_discount_pct=-50,
    )
    assert rate_neg == 30.0  # clamped to 0%

    rate_huge = effective_pallet_rate(
        base_rate_per_m2=30.0, is_trade=True,
        mode="trade_extra_discount", extra_discount_pct=500,
    )
    assert rate_huge == 0.0  # clamped to 100%


def test_rate_none_passes_through():
    assert effective_pallet_rate(base_rate_per_m2=None, is_trade=True, mode="same") is None


# -- half_pallet_m2 -----------------------------------------------------

def test_half_pallet_explicit_wins():
    p = {"m2_per_pallet": 32.0, "m2_per_half_pallet": 14.0}
    assert half_pallet_m2(p) == 14.0


def test_half_pallet_default_is_half_of_full():
    p = {"m2_per_pallet": 32.0}
    assert half_pallet_m2(p) == 16.0


def test_half_pallet_returns_none_when_no_pallet_data():
    assert half_pallet_m2({}) is None


# -- compute_pallet_pricing — main pricing path -------------------------

def test_full_pallet_block_built_from_product_fields():
    p = {
        "m2_per_pallet": 32.0,
        "pallet_price_per_m2": 28.0,
    }
    out = compute_pallet_pricing(product=p, is_trade=False, mode="same")
    assert out["visible"] is True
    assert out["full"] == {
        "rate_per_m2": 28.0,
        "min_order_m2": 32.0,
        "min_order_total_gbp": 896.0,
    }
    # half not set on product → half block is None
    assert out["half"] is None


def test_half_pallet_block_uses_explicit_when_set():
    p = {
        "m2_per_pallet": 32.0,
        "m2_per_half_pallet": 14.0,
        "pallet_price_per_m2": 28.0,
        "half_pallet_price_per_m2": 32.0,
    }
    out = compute_pallet_pricing(product=p, is_trade=False, mode="same")
    assert out["half"] == {
        "rate_per_m2": 32.0,
        "min_order_m2": 14.0,
        "min_order_total_gbp": 448.0,
    }


def test_trade_only_mode_hides_for_retail():
    p = {"m2_per_pallet": 32.0, "pallet_price_per_m2": 28.0}
    out = compute_pallet_pricing(product=p, is_trade=False, mode="trade_only")
    assert out["visible"] is False
    assert out["full"] is None
    assert out["half"] is None


def test_extra_discount_mode_applies_to_trade_only():
    p = {
        "m2_per_pallet": 32.0,
        "pallet_price_per_m2": 30.0,
    }
    retail = compute_pallet_pricing(
        product=p, is_trade=False,
        mode="trade_extra_discount", extra_discount_pct=10,
    )
    trade = compute_pallet_pricing(
        product=p, is_trade=True,
        mode="trade_extra_discount", extra_discount_pct=10,
    )
    assert retail["full"]["rate_per_m2"] == 30.0
    assert trade["full"]["rate_per_m2"] == 27.0
    # min_order_total reflects the discounted rate
    assert trade["full"]["min_order_total_gbp"] == 32.0 * 27.0


def test_no_pallet_fields_returns_visible_but_no_blocks():
    """Product without pallet fields: visible (so admin can decide later)
    but full/half blocks are None — frontend renders nothing."""
    p = {"name": "Some non-tile product"}
    out = compute_pallet_pricing(product=p, is_trade=False, mode="same")
    assert out["visible"] is True
    assert out["full"] is None
    assert out["half"] is None


# -- derive_stock_status ------------------------------------------------

def test_manual_in_stock_overrides_zero_inventory():
    p = {"stock_status": "always_in_stock", "stock": 0}
    assert derive_stock_status(p) == "always_in_stock"


def test_manual_out_of_stock_overrides_high_inventory():
    p = {"stock_status": "out_of_stock", "stock": 999}
    assert derive_stock_status(p) == "out_of_stock"


def test_invalid_manual_status_falls_through_to_inventory():
    p = {"stock_status": "garbage", "stock": 50}
    assert derive_stock_status(p) == "in_stock"


def test_auto_low_stock_when_below_threshold():
    p = {"stock": 3}
    assert derive_stock_status(p) == "low_stock"


def test_auto_out_of_stock_when_zero():
    p = {"stock": 0}
    assert derive_stock_status(p) == "out_of_stock"
    p = {}  # missing entirely
    assert derive_stock_status(p) == "out_of_stock"


def test_status_constants_complete():
    assert set(STOCK_STATUSES) == {"in_stock", "low_stock", "out_of_stock", "always_in_stock"}
    assert set(PALLET_PRICING_MODES) == {"same", "trade_only", "trade_extra_discount"}

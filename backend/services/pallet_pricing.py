"""
Pallet pricing logic + settings.

Three pricing modes admin can pick:
  • same                — pallet £/m² rate same for retail and trade. The
                          existing trade discount % still applies on top.
  • trade_only          — only trade customers see pallet pricing; retail
                          customers don't see the option at all.
  • trade_extra_discount — pallet £/m² rate is the retail rate. Trade gets
                          an EXTRA % off (separate from any global trade
                          discount). Owner sets the extra % in admin.

Stock statuses (manual overrides on a product):
  • in_stock         — green badge, normal flow
  • low_stock        — yellow "Low stock" badge, still buyable
  • out_of_stock     — red badge, "Add to basket" disabled, sample btn ok
  • always_in_stock  — green badge, ignores numeric inventory
  None / missing     — default; system derives from numeric inventory levels.

This module is the SINGLE SOURCE OF TRUTH for both. PDP, basket and admin
all read from `compute_pallet_pricing()` so a customer can never see a
price the system doesn't enforce server-side.
"""
from __future__ import annotations

from typing import Optional


# Allowed values for `Product.stock_status`
STOCK_STATUSES = ("in_stock", "low_stock", "out_of_stock", "always_in_stock")
STOCK_STATUS_LABELS = {
    "in_stock": "In Stock",
    "low_stock": "Low Stock",
    "out_of_stock": "Out of Stock",
    "always_in_stock": "Always In Stock",
}

# Allowed values for the global pallet-pricing-mode setting
PALLET_PRICING_MODES = ("same", "trade_only", "trade_extra_discount")

# Defaults for `website_settings` document — reasonable safe defaults so
# the pallet feature is fully OFF until owner explicitly configures it.
PALLET_DEFAULTS: dict = {
    "pallet_pricing_mode": "same",
    # Used only when mode == "trade_extra_discount". % off the retail
    # pallet rate when a trade customer buys at pallet quantity.
    "pallet_trade_extra_discount_pct": 0.0,
}


def is_pallet_visible_to_customer(
    *, mode: str, is_trade: bool,
) -> bool:
    """Decides whether to render pallet pricing on a customer's PDP."""
    if mode == "trade_only":
        return bool(is_trade)
    return True  # same / trade_extra_discount → visible to everyone


def effective_pallet_rate(
    *,
    base_rate_per_m2: Optional[float],
    is_trade: bool,
    mode: str,
    extra_discount_pct: float = 0.0,
) -> Optional[float]:
    """Returns the £/m² rate this customer pays at pallet quantity.

    base_rate_per_m2 is the value stored on the product
    (`pallet_price_per_m2` or `half_pallet_price_per_m2`). For modes
    other than `trade_extra_discount`, we return the rate unchanged —
    any global trade % discount is applied at basket time as usual.
    """
    if base_rate_per_m2 is None:
        return None
    if mode == "trade_extra_discount" and is_trade and extra_discount_pct > 0:
        pct = max(0.0, min(100.0, float(extra_discount_pct))) / 100.0
        return round(float(base_rate_per_m2) * (1.0 - pct), 4)
    return float(base_rate_per_m2)


def half_pallet_m2(product: dict) -> Optional[float]:
    """Returns the m² qty for half a pallet — explicit field if set,
    else half of full pallet, else None."""
    explicit = product.get("m2_per_half_pallet")
    if explicit is not None:
        try:
            v = float(explicit)
            if v > 0:
                return v
        except (TypeError, ValueError):
            return None
    full = product.get("m2_per_pallet")
    if full is None:
        return None
    try:
        v = float(full)
        return round(v / 2.0, 4) if v > 0 else None
    except (TypeError, ValueError):
        return None


def compute_pallet_pricing(
    *,
    product: dict,
    is_trade: bool = False,
    mode: str = "same",
    extra_discount_pct: float = 0.0,
) -> dict:
    """Builds the pallet price block to render on PDP / basket.

    Returns:
      {
        "visible": bool,                       # whether to render at all
        "full":  None | {
            "rate_per_m2": float,
            "min_order_m2": float,
            "min_order_total_gbp": float,      # = rate * min_order
        },
        "half":  None | {...same shape...},
        "mode": str,                            # for diagnostics
      }

    All fields are None when the corresponding pallet rate isn't set on
    the product. Frontend can simply ignore None fields.
    """
    visible = is_pallet_visible_to_customer(mode=mode, is_trade=is_trade)
    if not visible:
        return {"visible": False, "full": None, "half": None, "mode": mode}

    full_m2 = product.get("m2_per_pallet")
    full_rate = product.get("pallet_price_per_m2")
    half_m2_val = half_pallet_m2(product)
    half_rate = product.get("half_pallet_price_per_m2")

    full_block = None
    if full_m2 is not None and full_rate is not None:
        try:
            m2 = float(full_m2)
            rate = effective_pallet_rate(
                base_rate_per_m2=full_rate,
                is_trade=is_trade, mode=mode,
                extra_discount_pct=extra_discount_pct,
            )
            if m2 > 0 and rate is not None:
                full_block = {
                    "rate_per_m2": round(rate, 2),
                    "min_order_m2": round(m2, 2),
                    "min_order_total_gbp": round(m2 * rate, 2),
                }
        except (TypeError, ValueError):
            pass

    half_block = None
    if half_m2_val is not None and half_rate is not None:
        try:
            rate = effective_pallet_rate(
                base_rate_per_m2=half_rate,
                is_trade=is_trade, mode=mode,
                extra_discount_pct=extra_discount_pct,
            )
            if rate is not None:
                half_block = {
                    "rate_per_m2": round(rate, 2),
                    "min_order_m2": round(half_m2_val, 2),
                    "min_order_total_gbp": round(half_m2_val * rate, 2),
                }
        except (TypeError, ValueError):
            pass

    return {
        "visible": True,
        "full": full_block,
        "half": half_block,
        "mode": mode,
    }


def derive_stock_status(product: dict, default_low_threshold: int = 5) -> str:
    """Derives a stock status string. Manual override wins; falls back
    to numeric stock-based heuristic."""
    manual = product.get("stock_status")
    if isinstance(manual, str) and manual in STOCK_STATUSES:
        return manual
    stock = product.get("stock")
    try:
        stock_n = int(stock) if stock is not None else 0
    except (TypeError, ValueError):
        stock_n = 0
    if stock_n <= 0:
        return "out_of_stock"
    if stock_n <= default_low_threshold:
        return "low_stock"
    return "in_stock"

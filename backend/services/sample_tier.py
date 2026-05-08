"""
Sample tier classification.

Rules (Feb 2026 — agreed with user):
  • Tiles with any dimension ≤ 200 mm OR size "100x300mm" (small metros,
    mosaics etc.) → FREE_SMALL. The actual tile IS the sample — no cutting
    needed. Free of charge, £2.99 delivery.
  • Tiles with largest dimension ≥ 400 mm AND ≥ 400×800mm equivalent
    (so 600x600, 600x1200, 800x800, 1200x1200, 1200x2400 etc.)
    → eligible for FULL_SIZE paid sample (£5) — a 300×600 mm cut piece
    branded "Full Size Sample". Also still eligible for free cut sample.
  • Everything else → FREE_CUT (standard 10×10 cm cut piece). Free,
    £2.99 delivery.

Every tile is always eligible for at least one free tier; the full-size
tier is additive on large-format tiles only.
"""
from __future__ import annotations

from typing import Optional

# Tuning knobs — deliberately conservative so we don't auto-suppress
# the free cut sample for tiles that fitters still want to see cut.
SMALL_TILE_MAX_MM = 200              # any-dimension ≤ this → sample IS the tile
SMALL_TILE_RECT_NARROW_MM = 100      # matches 100×300, 100×400 etc.
SMALL_TILE_RECT_LONG_MM = 300
LARGE_FORMAT_MIN_LONG_MM = 600       # tiles ≥ this long dimension offer full-size paid
LARGE_FORMAT_MIN_SHORT_MM = 400      # AND short dimension ≥ this


def _norm(value: Optional[float]) -> Optional[float]:
    """Accept None / 0 / floats in mm. Returns float mm or None."""
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    return v


def classify(
    tile_width: Optional[float],
    tile_height: Optional[float],
) -> dict:
    """Returns tier descriptor for a tile's dimensions.

    Output:
      {
        "primary": "free_small" | "free_cut",   # cheapest/default tier
        "offers": ["free_small"] | ["free_cut"] | ["free_cut", "full_size"],
        "width_mm": float | None,
        "height_mm": float | None,
        "full_size_note": None | str,           # shown on PDP when full-size picked
      }

    If dimensions are unknown → defaults to ["free_cut"] (safest).
    """
    w = _norm(tile_width)
    h = _norm(tile_height)

    if w is None or h is None:
        return {
            "primary": "free_cut",
            "offers": ["free_cut"],
            "width_mm": w,
            "height_mm": h,
            "full_size_note": None,
        }

    long_side = max(w, h)
    short_side = min(w, h)

    # Tier 1 — small tile, the tile IS the sample
    is_small_square = long_side <= SMALL_TILE_MAX_MM
    is_narrow_rect = (
        short_side <= SMALL_TILE_RECT_NARROW_MM
        and long_side <= SMALL_TILE_RECT_LONG_MM
    )
    if is_small_square or is_narrow_rect:
        return {
            "primary": "free_small",
            "offers": ["free_small"],
            "width_mm": w,
            "height_mm": h,
            "full_size_note": None,
        }

    # Tier 3 — large format: additive full-size paid option
    if long_side >= LARGE_FORMAT_MIN_LONG_MM and short_side >= LARGE_FORMAT_MIN_SHORT_MM:
        # Exact 300×600 tiles don't need the "cut from larger" caveat
        if long_side <= 600 and short_side <= 300:
            note = None
        else:
            note = (
                f"This is a large sample cut to approximately 300×600 mm "
                f"from a {int(long_side)}×{int(short_side)} mm tile."
            )
        return {
            "primary": "free_cut",
            "offers": ["free_cut", "full_size"],
            "width_mm": w,
            "height_mm": h,
            "full_size_note": note,
        }

    # Tier 2 — everything else: free cut only
    return {
        "primary": "free_cut",
        "offers": ["free_cut"],
        "width_mm": w,
        "height_mm": h,
        "full_size_note": None,
    }


# Prices — kept here so the backend is the source of truth. Frontend
# reads them via /api/content/sample-service if customised; otherwise
# these defaults apply.
FREE_SAMPLE_POSTAGE_GBP = 2.99
FULL_SIZE_SAMPLE_PRICE_GBP = 5.00

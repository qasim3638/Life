"""Tests guaranteeing the storefront tile serializer surfaces the new
Half + Full Pallet pricing fields end-to-end.

Customer's Half/Full Pallet PDP chip selector reads three things off the
serialised tile: m2_per_pallet, m2_per_half_pallet, and half_pallet_price.
These tests pin those fields in the response shape so a future serializer
refactor can't silently drop them and break the PDP UX.
"""
from __future__ import annotations

from routes.tiles import serialize_tile_for_shop


def _base_tile(**over):
    """Realistic tile doc — the storefront pulls from `tiles` collection."""
    base = {
        "_id": "tile-id-1",
        "slug": "alabaster-polished-60x60",
        "name": "Alabaster Polished 60x60cm",
        "display_name": "Alabaster Polished",
        "size": "600x600mm",
        "stock": 100,
        "room_lot_price": 28.99,
        "pallet_price": 26.09,
        "images": ["/img.jpg"],
    }
    base.update(over)
    return base


def test_pallet_fields_present_when_set():
    """When the tile has all the new fields, the response surfaces them
    1:1 so the PDP can render the half + full chip selector."""
    tile = _base_tile(
        m2_per_pallet=32.0,
        m2_per_half_pallet=16.0,
        half_pallet_price=27.50,
    )
    out = serialize_tile_for_shop(tile)
    assert out["m2_per_pallet"] == 32.0
    assert out["m2_per_half_pallet"] == 16.0
    assert out["half_pallet_price"] == 27.50
    # Existing per-m² + full-pallet rates still work alongside
    assert out["pallet_price"] == 26.09
    assert out["room_lot_price"] == 28.99


def test_half_pallet_m2_defaults_to_half_of_full_when_not_set():
    """If admin only sets m2_per_pallet (the common case — most tiles
    ship in standardised pallets), the half-pallet threshold defaults
    to ½ of the full so the PDP doesn't need to guess."""
    tile = _base_tile(m2_per_pallet=40.0)  # no m2_per_half_pallet set
    out = serialize_tile_for_shop(tile)
    assert out["m2_per_pallet"] == 40.0
    assert out["m2_per_half_pallet"] == 20.0


def test_half_pallet_m2_explicit_overrides_default():
    """Admin can set a non-half value (e.g. 14 m² when the supplier
    ships physical half-pallets at 14 m² rather than 16)."""
    tile = _base_tile(m2_per_pallet=32.0, m2_per_half_pallet=14.0)
    out = serialize_tile_for_shop(tile)
    assert out["m2_per_pallet"] == 32.0
    assert out["m2_per_half_pallet"] == 14.0


def test_pallet_fields_none_when_not_set_on_tile():
    """When the tile has no pallet config, the new fields are None /
    0 — PDP hides the chip selector and falls back to per-m² only."""
    tile = _base_tile()  # only legacy room_lot_price + pallet_price
    # remove the legacy pallet_price to simulate a tile without pallet config
    del tile["pallet_price"]
    out = serialize_tile_for_shop(tile)
    assert out["m2_per_pallet"] is None
    assert out["m2_per_half_pallet"] is None
    assert out["half_pallet_price"] == 0


def test_no_full_pallet_m2_means_no_half_default():
    """No m2_per_pallet → half also stays None (avoid defaulting to
    half-of-zero which would create an order-1m² half-pallet bug)."""
    tile = _base_tile()
    out = serialize_tile_for_shop(tile)
    assert out["m2_per_pallet"] is None
    assert out["m2_per_half_pallet"] is None


def test_zero_pallet_m2_does_not_become_half_zero():
    """Defensive: 0 or negative m2_per_pallet should not produce a 0
    half-pallet threshold (would let customers buy 1m² at pallet rate)."""
    tile = _base_tile(m2_per_pallet=0)
    out = serialize_tile_for_shop(tile)
    assert out["m2_per_pallet"] == 0
    # half stays None, not 0.0 — compute_pallet_pricing rejects None,
    # which means PDP correctly hides the half chip
    assert out["m2_per_half_pallet"] is None


def test_zero_half_pallet_price_exposed_as_zero():
    """0 half_pallet_price → exposed as 0 so the PDP can decide to hide
    the half chip rather than rendering 'free' bulk pricing."""
    tile = _base_tile(m2_per_pallet=32.0, half_pallet_price=0)
    out = serialize_tile_for_shop(tile)
    assert out["half_pallet_price"] == 0


def test_admin_sync_fields_list_includes_pallet_fields():
    """Regression — the products UPDATE route must sync new pallet fields
    to the tiles collection. If this list ever drops a field, admin
    edits stop syncing to storefront."""
    import inspect
    from routes import products as products_route
    src = inspect.getsource(products_route.update_product)
    for field in [
        "'m2_per_pallet'",
        "'m2_per_half_pallet'",
        "'half_pallet_price'",
        "'pallet_price'",
        "'pallet_enabled'",
    ]:
        assert field in src, f"Field {field} missing from update_product sync_fields"

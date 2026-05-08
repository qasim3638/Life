"""Regression: GuestCheckoutOrder / GuestCheckoutOrderItem must tolerate
legacy cart items that carry null fields (subtotal/total/name/etc).

Production was returning HTTP 422 when older localStorage carts sent null
instead of omitting the field. Those payloads should now accept cleanly
because:

  * string fields are Optional[str] with default ""
  * numeric fields are Optional[float] with default 0
  * extra/unknown top-level fields (``express_fee``) are ignored via
    ``model_config = ConfigDict(extra="ignore")``
"""

import pytest
from pydantic import ValidationError

from routes.shop import GuestCheckoutOrder, GuestCheckoutOrderItem


def test_item_accepts_all_nulls():
    """Model accepts nulls without raising — endpoint coerces later via `or 0`."""
    item = GuestCheckoutOrderItem.model_validate({
        "product_id": None,
        "name": None,
        "variant": None,
        "price": None,
        "quantity": None,
        "image": None,
    })
    # Optional fields pass None through; endpoint uses ``float(x or 0)``.
    assert item.price is None
    assert item.quantity is None
    assert item.name is None


def test_item_accepts_valid_payload():
    item = GuestCheckoutOrderItem.model_validate({
        "product_id": "sku1",
        "name": "Premium Tile",
        "price": 39.99,
        "quantity": 2.16,
    })
    assert item.price == 39.99
    assert item.quantity == 2.16


def test_order_accepts_null_totals():
    """Null subtotal/total stay None but validation succeeds; endpoint
    recomputes totals server-side so downstream is fine."""
    order = GuestCheckoutOrder.model_validate({
        "items": [{"product_id": "x", "name": "t", "price": 1, "quantity": 1}],
        "customer": {"email": "a@b.com"},
        "delivery": {"method": "delivery"},
        "subtotal": None,
        "delivery_fee": None,
        "total": None,
    })
    assert order.subtotal is None
    assert order.total is None


def test_order_ignores_extra_fields():
    """express_fee + any future additions must not 422."""
    order = GuestCheckoutOrder.model_validate({
        "items": [{"product_id": "x", "name": "t", "price": 1, "quantity": 1}],
        "customer": {},
        "delivery": {},
        "subtotal": 1,
        "total": 1,
        "express_fee": 25,
        "some_future_field": "whatever",
    })
    assert order.total == 1


def test_order_requires_items_list():
    with pytest.raises(ValidationError):
        GuestCheckoutOrder.model_validate({
            "items": None,
            "customer": {},
            "delivery": {},
        })


# ---------------------------------------------------------------------------
# Box metadata backfill helper
# ---------------------------------------------------------------------------
from scripts.backfill_box_metadata import (
    parse_tile_area_m2,
    compute_box_metrics,
)


@pytest.mark.parametrize("size,expected_m2", [
    ("60x60", 0.36),
    ("60x60cm", 0.36),
    ("600x600", 0.36),
    ("600x600mm", 0.36),
    ("30x60", 0.18),
    ("900x300", 0.27),
    ("900x300x14/3mm", 0.27),
    ("800x800x20mm", 0.64),
    ("120x120cm", 1.44),
])
def test_parse_tile_area_known_sizes(size, expected_m2):
    assert parse_tile_area_m2(size) == pytest.approx(expected_m2, abs=1e-4)


@pytest.mark.parametrize("size", ["", None, "not a size", "abc", "x"])
def test_parse_tile_area_invalid(size):
    assert parse_tile_area_m2(size) is None


def test_compute_box_metrics_standard_60x60():
    tpb, spb = compute_box_metrics(0.36)
    assert tpb == 4
    assert spb == 1.44


def test_compute_box_metrics_large_format_single_tile():
    tpb, spb = compute_box_metrics(1.5)
    assert tpb == 1
    assert spb == 1.5


def test_compute_box_metrics_80_80_two_per_box():
    tpb, spb = compute_box_metrics(0.64)
    assert tpb == 2
    assert spb == 1.28

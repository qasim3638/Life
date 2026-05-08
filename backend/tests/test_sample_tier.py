"""Tests for services.sample_tier — keeps the 3-tier classification
stable against product data changes."""
from __future__ import annotations

import pytest
from services.sample_tier import classify


# -- Tier 1: small tiles (the tile IS the sample) -----------------------

@pytest.mark.parametrize("w,h,label", [
    (100, 100,  "mini mosaic"),
    (150, 150,  "small metro-ish"),
    (200, 200,  "boundary — still small"),
    (100, 300,  "classic metro 100×300"),
    (75,  150,  "tiny brick"),
    (100, 400,  "narrow plank <=100 narrow + <=300 long? no, 400 > 300 → cut"),
])
def test_tier_assignment(w, h, label):
    """Small square + narrow-rect tiles are eligible for free_small."""
    r = classify(w, h)
    # The 100x400 edge case should NOT be free_small (it's a long plank)
    if (max(w, h) <= 200) or (min(w, h) <= 100 and max(w, h) <= 300):
        assert r["primary"] == "free_small", f"{label} ({w}×{h})"
        assert r["offers"] == ["free_small"]
    else:
        # 100x400 falls into "free_cut" only (long plank)
        assert r["primary"] == "free_cut"


# -- Tier 2: standard mid-size → free_cut only --------------------------

@pytest.mark.parametrize("w,h", [
    (300, 300),
    (300, 600),    # the "boundary" — not quite large-format
    (400, 400),
])
def test_standard_tiles_free_cut_only(w, h):
    r = classify(w, h)
    assert r["primary"] == "free_cut"
    assert r["offers"] == ["free_cut"]
    assert r["full_size_note"] is None


# -- Tier 3: large-format → free_cut + full_size paid option -----------

def test_600x600_offers_full_size():
    r = classify(600, 600)
    assert r["offers"] == ["free_cut", "full_size"]
    assert r["full_size_note"] is not None
    assert "600×600" in r["full_size_note"]


def test_600x1200_has_clarifying_note():
    r = classify(600, 1200)
    assert r["offers"] == ["free_cut", "full_size"]
    note = r["full_size_note"]
    assert note is not None
    assert "300×600" in note
    assert "1200×600" in note or "600×1200" in note
    # The user specifically asked for "this is a large sample cut to
    # approximately 300×600 from a 600x1200" wording.
    assert "large sample" in note.lower()


def test_800x800_has_clarifying_note():
    r = classify(800, 800)
    assert r["offers"] == ["free_cut", "full_size"]
    assert "800×800" in r["full_size_note"]


def test_1200x2400_has_clarifying_note():
    r = classify(1200, 2400)
    assert r["offers"] == ["free_cut", "full_size"]
    assert r["full_size_note"] is not None


# -- Defensive cases ----------------------------------------------------

def test_missing_dimensions_defaults_to_free_cut():
    assert classify(None, None)["primary"] == "free_cut"
    assert classify(None, 600)["primary"] == "free_cut"
    assert classify(600, None)["primary"] == "free_cut"


def test_small_mosaic_50mm_treated_as_small():
    """50×50mm mosaic — IS the sample (small tier)."""
    r = classify(50, 50)
    assert r["primary"] == "free_small"


def test_zero_and_negative_dims_treated_as_missing():
    assert classify(0, 600)["primary"] == "free_cut"
    assert classify(-1, -1)["primary"] == "free_cut"


def test_output_shape_is_stable():
    """Schema regression — PDP depends on every field being present."""
    r = classify(600, 1200)
    assert set(r.keys()) == {"primary", "offers", "width_mm", "height_mm", "full_size_note"}


# -- Exact 300×600 doesn't need the "cut from larger" caveat -----------

def test_exact_300x600_full_size_has_no_caveat():
    # A 300×600 tile IS the full-size sample — no clarifying note needed
    r = classify(300, 600)
    # 300×600 falls below both large-format thresholds → free_cut only
    assert r["offers"] == ["free_cut"]
    assert r["full_size_note"] is None

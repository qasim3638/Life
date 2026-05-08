"""
Unit tests for business_rules.sanitise_display_name — the single source of truth
for display-name hygiene across supplier imports, sync endpoints, and admin edits.

These tests lock in the behaviour introduced when fixing the Costa Stone
duplicate-size bug (Apr 2026). Future contributors cannot regress any of the
rules below without a test failure.

Run locally:   cd /app/backend && pytest tests/test_display_name_sanitiser.py -v
"""

import os
import sys

import pytest

# Make sure business_config is importable regardless of cwd
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from business_config.business_rules import (  # noqa: E402
    sanitise_display_name,
    strip_duplicate_size_tokens,
)


# ---------------------------------------------------------------------------
# Rule 1: drop duplicate cm + mm size tokens when BOTH forms appear
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("raw,expected", [
    # Costa Stone — cm form at start, mm form trailing
    (
        "Costa Stone Bianco 30x60cm Matt 600x300x7mm",
        "Costa Stone Bianco 30x60cm Matt",
    ),
    (
        "Costa Stone Grey 60x120cm Matt 1200x600x7mm",
        "Costa Stone Grey 60x120cm Matt",
    ),
    # Bestone — with finish between cm and mm
    (
        "Bestone 60x60cm Linear Matt 600x600x10mm",
        "Bestone 60x60cm Linear Matt",
    ),
    # Thickness-split format e.g. "14/3mm"
    (
        "Spendour 90x300cm Oak 900x3000x14/3mm",
        "Spendour 90x300cm Oak",
    ),
])
def test_strips_duplicate_cm_mm_size(raw, expected):
    assert sanitise_display_name(raw) == expected


@pytest.mark.parametrize("raw", [
    # Single-form names must be LEFT UNTOUCHED — they don't have a cm twin
    "Herringbone Borrowdale Oak 90x300x14/3mm",
    "Canopy Oak 70x350x20/5mm",
    # Small mm numbers (< 100) are not real tile dimensions — leave alone
    "Grout Spacer 2x2mm Pack",
])
def test_single_mm_form_is_preserved(raw):
    # Input should survive sanitiser without losing the mm token
    # (other hygiene rules may still run; check mm token is still present)
    assert "mm" in sanitise_display_name(raw).lower() or "mm" not in raw.lower()
    # The trailing size itself is unchanged
    assert strip_duplicate_size_tokens(raw) == raw


# ---------------------------------------------------------------------------
# Rule 2: collapse whitespace (runs of spaces / tabs / newlines -> single space)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("raw,expected", [
    ("Costa  Stone   Bianco    30x60cm  Matt", "Costa Stone Bianco 30x60cm Matt"),
    ("  Leading and trailing   ", "Leading and trailing"),
    ("Tab\tbetween\twords", "Tab between words"),
    ("Newline\nbetween\nwords", "Newline between words"),
])
def test_collapses_whitespace(raw, expected):
    assert sanitise_display_name(raw) == expected


# ---------------------------------------------------------------------------
# Rule 3: normalise size-unit casing + the 'x' separator
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("raw,expected", [
    ("Bestone 30X60CM Matt",            "Bestone 30x60cm Matt"),
    ("Splendour 600X600Mm Polished",    "Splendour 600x600mm Polished"),
    # Unicode multiplication sign should become ASCII 'x'
    ("Ceramica 90 × 300 × 14/3mm Natural", "Ceramica 90x300x14/3mm Natural"),
])
def test_normalises_size_unit_casing(raw, expected):
    assert sanitise_display_name(raw) == expected


# ---------------------------------------------------------------------------
# Rule 4: strip stray punctuation and runs
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("raw,expected", [
    # Double commas, trailing comma
    ("Wallcano, ,  Bianco,  Matt", "Wallcano, Bianco, Matt"),
    # Leading and trailing stray punctuation
    (" ,- Canopy Oak Natural —", "Canopy Oak Natural"),
])
def test_strips_stray_punctuation(raw, expected):
    assert sanitise_display_name(raw) == expected


# ---------------------------------------------------------------------------
# Rule 5: collapse immediate duplicate words (case-insensitive)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("raw,expected", [
    ("Oak Oak Wood Effect",                  "Oak Wood Effect"),
    ("Costa Stone Bianco Matt Matt 30x60cm", "Costa Stone Bianco Matt 30x60cm"),
    # Case-insensitive
    ("Polished polished Gloss",              "Polished Gloss"),
])
def test_collapses_duplicate_words(raw, expected):
    assert sanitise_display_name(raw) == expected


# ---------------------------------------------------------------------------
# Rule 6: title-case known finish / property words
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("raw,expected", [
    ("Costa Stone Bianco 30x60cm matt",       "Costa Stone Bianco 30x60cm Matt"),
    ("Splendour Verde polished",              "Splendour Verde Polished"),
    ("Porcelain 60x60cm LAPPATO",             "Porcelain 60x60cm Lappato"),
    # Mixed case should still normalise
    ("Ceramica Rustic BRUSHED Oak",           "Ceramica Rustic Brushed Oak"),
])
def test_titlecases_finish_words(raw, expected):
    assert sanitise_display_name(raw) == expected


# ---------------------------------------------------------------------------
# Edge cases: None / empty / plain strings pass through safely
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("raw,expected", [
    (None, None),
    ("", ""),
    ("Plain Clean Name", "Plain Clean Name"),
    # Already-clean canonical name — must be unchanged
    ("Costa Stone Bianco 30x60cm Matt", "Costa Stone Bianco 30x60cm Matt"),
])
def test_edge_cases_passthrough(raw, expected):
    assert sanitise_display_name(raw) == expected


# ---------------------------------------------------------------------------
# Idempotency — critical property: running twice == running once
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("raw", [
    "Costa Stone Bianco 30x60cm Matt 600x300x7mm",
    "Costa  Stone   Bianco    30X60CM  matt  600x300x7mm",
    "Herringbone Borrowdale Oak 90x300x14/3mm",
    "Bestone 60x60cm Linear Matt",
    "Simple Name",
    "",
    None,
])
def test_is_idempotent(raw):
    once = sanitise_display_name(raw)
    twice = sanitise_display_name(once)
    assert once == twice, f"Not idempotent for input {raw!r}: {once!r} != {twice!r}"


# ---------------------------------------------------------------------------
# Combo case — all 6 rules firing together on a single messy input
# ---------------------------------------------------------------------------
def test_combo_all_rules():
    messy = "Costa Stone  Bianco,  30X60CM  MATT  600x300x7mm"
    assert sanitise_display_name(messy) == "Costa Stone Bianco, 30x60cm Matt"


# ---------------------------------------------------------------------------
# Defensive: non-string input must not crash
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bad", [
    123,
    12.5,
    ["a", "b"],
    {"name": "x"},
])
def test_non_string_input_does_not_crash(bad):
    # We don't enforce a specific return shape for non-strings — just no exception.
    # Current implementation returns the input unchanged.
    result = sanitise_display_name(bad)
    assert result == bad

"""
Unit tests for utils.request_filters.normalise_filter_value.

Keeps the sentinel-token list and edge-case contract locked in so future
refactors can't silently regress the "supplier='all'" class of bug.
"""
import pytest

from utils.request_filters import normalise_filter_value


@pytest.mark.parametrize(
    "incoming",
    [None, "", "  ", "\t", "\n\n", "all", "ALL", "All", "  all  ",
     "any", "ANY", "null", "NULL", "none", "None", "*"],
)
def test_sentinel_values_become_none(incoming):
    assert normalise_filter_value(incoming) is None


@pytest.mark.parametrize(
    "incoming,expected",
    [
        ("Verona", "Verona"),
        ("Splendour", "Splendour"),
        ("H Martin", "H Martin"),
        ("  Verona  ", "Verona"),              # trims whitespace
        ("RSA Tiles", "RSA Tiles"),
        ("all-stars", "all-stars"),            # 'all' is only a whole-token match
        ("Allison", "Allison"),                # starts with 'all' but full name
        ("any-color", "any-color"),
        ("None-Specified", "None-Specified"),
    ],
)
def test_real_supplier_names_pass_through(incoming, expected):
    assert normalise_filter_value(incoming) == expected


@pytest.mark.parametrize(
    "incoming",
    [0, 1, True, False, 3.14, [], {}, ["Verona"]],
)
def test_non_string_values_pass_through_unchanged(incoming):
    # Helper should be a safe drop-in — non-strings are returned as-is.
    assert normalise_filter_value(incoming) == incoming


def test_is_idempotent():
    for v in ["Verona", "  Splendour  ", "all", None, "", "RSA Tiles"]:
        once = normalise_filter_value(v)
        twice = normalise_filter_value(once)
        assert once == twice, f"Not idempotent for input {v!r}: first={once!r} second={twice!r}"

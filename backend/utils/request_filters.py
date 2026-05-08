"""
Request-filter normalisers.

Centralised so the same silent-failure class of bug (e.g. "supplier='all' "
leaking into a Mongo filter and matching zero documents) can never recur.

Usage:
    from utils.request_filters import normalise_filter_value

    supplier = normalise_filter_value(data.get("supplier"))
    if supplier:                    # now truly None for 'all' / '' / None
        query["supplier"] = supplier
"""
from typing import Any, Optional


# Tokens the frontend uses to mean "no filter" — lower-cased for the comparison.
_SENTINEL_ALL_TOKENS = {"all", "any", "", "null", "none", "*"}


def normalise_filter_value(value: Any) -> Optional[str]:
    """
    Convert a frontend-supplied filter value to either a real string or ``None``.

    Returns ``None`` when the caller effectively means "do not filter":
      - ``None``
      - empty string / whitespace-only string
      - any of the sentinel tokens: ``"all"``, ``"any"``, ``"null"``, ``"none"``, ``"*"``
        (case-insensitive)

    Otherwise returns the trimmed original string.

    Non-string values (ints, bools, etc.) are returned unchanged so this helper
    remains safe to drop into existing code paths.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if stripped.lower() in _SENTINEL_ALL_TOKENS:
        return None
    return stripped

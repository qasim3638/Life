"""
Pytests for the "Did you mean?" fuzzy-match search helper in
`routes/shop.py::_fuzzy_suggestions`.

We exercise the pure helper directly (not the full `/search-all` endpoint)
so we can seed a tiny vocabulary and assert on the matching behaviour
without depending on whatever is currently in Mongo.
"""
from __future__ import annotations

import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _patch_vocab_cache(terms):
    """Stub the in-memory cache with a known set of terms."""
    from routes import shop as shop_mod
    lower_map = {t.lower(): t for t in terms}
    shop_mod._search_vocab_cache["at"] = time.time()
    shop_mod._search_vocab_cache["terms"] = list(lower_map.values())
    shop_mod._search_vocab_cache["lower_map"] = lower_map


import pytest  # noqa: E402


@pytest.mark.asyncio
async def test_fuzzy_catches_adhesive_typo():
    from routes.shop import _fuzzy_suggestions
    _patch_vocab_cache(["Adhesive", "Grout", "Sealer", "Underlay", "Polished"])
    out = await _fuzzy_suggestions(db=None, q="adheisive", limit=5)
    assert "Adhesive" in out


@pytest.mark.asyncio
async def test_fuzzy_catches_porcelain_typo():
    from routes.shop import _fuzzy_suggestions
    _patch_vocab_cache(["Porcelain", "Ceramic", "Marble", "Travertine"])
    out = await _fuzzy_suggestions(db=None, q="porcelian", limit=5)
    assert "Porcelain" in out


@pytest.mark.asyncio
async def test_fuzzy_returns_nothing_for_gibberish():
    from routes.shop import _fuzzy_suggestions
    _patch_vocab_cache(["Porcelain", "Adhesive", "Grout"])
    out = await _fuzzy_suggestions(db=None, q="zzqqxxzzqq", limit=5)
    assert out == []


@pytest.mark.asyncio
async def test_fuzzy_never_suggests_the_query_itself():
    from routes.shop import _fuzzy_suggestions
    _patch_vocab_cache(["Porcelain", "Polished", "Polish"])
    # The query IS "polish" — returning "Polish" would be tautological.
    out = await _fuzzy_suggestions(db=None, q="polish", limit=5)
    lower = [s.lower() for s in out]
    assert "polish" not in lower


@pytest.mark.asyncio
async def test_fuzzy_respects_limit():
    from routes.shop import _fuzzy_suggestions
    _patch_vocab_cache(["Polished", "Polish", "Polisher", "Polishing", "Polystyrene", "Policy"])
    out = await _fuzzy_suggestions(db=None, q="polshd", limit=3)
    assert len(out) <= 3


@pytest.mark.asyncio
async def test_fuzzy_too_short_query_returns_empty():
    from routes.shop import _fuzzy_suggestions
    _patch_vocab_cache(["Porcelain"])
    assert await _fuzzy_suggestions(db=None, q="a") == []
    assert await _fuzzy_suggestions(db=None, q="") == []
    assert await _fuzzy_suggestions(db=None, q="   ") == []

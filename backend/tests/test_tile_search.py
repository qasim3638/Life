"""Tests for services.tile_search — pinned to the customer-reported bugs
where autocomplete and search-results page returned different results
for the same query."""
from __future__ import annotations

from services.tile_search import (
    STOP_WORDS,
    SEARCH_FIELDS,
    _strip_stopwords,
    _tokenise,
    build_tile_search_query,
    build_product_search_query,
    rank_score,
)


# -- Tokenisation -------------------------------------------------------

def test_tokenise_lowercases_and_splits():
    assert _tokenise("Green Polished Tiles") == ["green", "polished", "tiles"]


def test_tokenise_dedupes():
    assert _tokenise("green green tiles tiles") == ["green", "tiles"]


def test_tokenise_strips_punctuation():
    assert _tokenise("60x60 cm") == ["60x60", "cm"]


def test_tokenise_empty_returns_empty_list():
    assert _tokenise("") == []
    assert _tokenise("   ") == []


# -- Stopword stripping -------------------------------------------------

def test_strip_stopwords_drops_tile_tiles_a_the():
    """The literal word 'tile' / 'tiles' adds zero info in a tile shop."""
    tokens = _tokenise("matt tiles for the kitchen")
    meaningful = _strip_stopwords(tokens)
    assert "tiles" not in meaningful
    assert "the" not in meaningful
    assert "matt" in meaningful
    assert "kitchen" in meaningful


def test_strip_stopwords_keeps_at_least_one_token():
    """If user types only stop-words ('tiles'), keep the first one
    rather than producing an empty query."""
    meaningful = _strip_stopwords(["tiles"])
    assert meaningful == ["tiles"]


# -- Tile query construction -------------------------------------------

def test_query_too_short_returns_none():
    assert build_tile_search_query("") is None
    assert build_tile_search_query(" ") is None
    assert build_tile_search_query("a") is None


def test_single_token_produces_or_clause():
    q = build_tile_search_query("polished")
    # is_active filter is wrapped → top level is $and
    assert "$and" in q
    inner = q["$and"][0]
    assert "$or" in inner
    fields_in_or = {next(iter(c.keys())) for c in inner["$or"]}
    # all SEARCH_FIELDS present
    assert "display_name" in fields_in_or
    assert "attributes.finish" in fields_in_or


def test_multi_token_uses_AND_so_every_word_must_match():
    """Regression: 'high polish tiles' must require BOTH 'high' AND
    'polish' to appear (the word 'tiles' is dropped as a stop-word)."""
    q = build_tile_search_query("high polish tiles")
    assert "$and" in q
    # Find the token clauses (each is itself an $or)
    inner_ands = q["$and"]
    or_clauses = [c for c in inner_ands if "$or" in c]
    assert len(or_clauses) == 2  # "high" + "polish", "tiles" stripped


def test_green_tiles_searches_for_green_only():
    """User typed 'green tiles'. After stop-word strip, only 'green'
    remains as a search token. Tile titled 'Cobalt Green Marble' MUST
    match because 'green' is in display_name."""
    q = build_tile_search_query("green tiles")
    inner = q["$and"][0]
    assert "$or" in inner
    # Confirm regex is for "green" specifically
    for clause in inner["$or"]:
        for _field, val in clause.items():
            if isinstance(val, dict) and "$regex" in val:
                assert val["$regex"] == "green"


def test_active_filter_excludes_explicitly_inactive_only():
    """Tiles with `is_active` missing OR True both pass; only `is_active=False` is excluded."""
    q = build_tile_search_query("matt")
    # find the is_active clause
    found = False
    for clause in q["$and"]:
        if "is_active" in clause:
            assert clause["is_active"] == {"$ne": False}
            found = True
    assert found, "is_active clause must be present"


def test_disable_active_filter_for_admin_search():
    q = build_tile_search_query("matt", require_active=False)
    # Just one clause (the $or) — no is_active wrapping
    assert "$and" not in q
    assert "$or" in q


# -- Product query (tools / grouts) -------------------------------------

def test_product_query_uses_strict_active_filter():
    """Products require is_active === True (stricter than tiles)."""
    q = build_product_search_query("grout")
    found = False
    for clause in q["$and"]:
        if "is_active" in clause:
            assert clause["is_active"] is True
            found = True
    assert found


# -- Rank score ---------------------------------------------------------

def test_rank_exact_substring_beats_token_match():
    assert rank_score("Marble Effect Tile", "marble effect") < rank_score(
        "Effect Marble Tile", "marble effect"
    )


def test_rank_handles_empty_inputs():
    assert rank_score("", "anything") == 100
    assert rank_score("a tile", "") == 50


# -- The exact customer-reported scenarios -----------------------------

def test_high_polish_tiles_query_matches_high_polished_product():
    """REGRESSION (May 6, 2026 customer report):
    typing 'high polish tiles' must surface tiles with name like
    'Artists Division Gold 60x120cm High Polished'."""
    q = build_tile_search_query("high polish tiles")
    # Simulate the regex against a real-shape document
    doc = {"display_name": "Artists Division Gold 60x120cm High Polished"}

    # Verify EVERY non-stop-word token has a regex that matches the doc
    import re as re_lib
    inner_ands = q["$and"]
    or_clauses = [c for c in inner_ands if "$or" in c]
    for or_c in or_clauses:
        # at least one regex in this $or matches the document
        token_matched = False
        for sub in or_c["$or"]:
            for field, regex_dict in sub.items():
                value = doc.get(field, "")
                if isinstance(regex_dict, dict) and "$regex" in regex_dict:
                    if re_lib.search(regex_dict["$regex"], value, re_lib.IGNORECASE):
                        token_matched = True
                        break
            if token_matched:
                break
        assert token_matched, f"Token clause didn't match: {or_c}"


def test_wood_effect_tiles_query_works():
    """REGRESSION: typing 'wood effect tiles' must match products with
    'Wood Effect' in their name."""
    q = build_tile_search_query("wood effect tiles")
    import re as re_lib
    doc = {"display_name": "Oakwood Wood Effect Plank 200x1200"}

    inner_ands = q["$and"]
    or_clauses = [c for c in inner_ands if "$or" in c]
    for or_c in or_clauses:
        token_matched = False
        for sub in or_c["$or"]:
            for field, regex_dict in sub.items():
                value = doc.get(field, "")
                if isinstance(regex_dict, dict) and re_lib.search(
                    regex_dict["$regex"], value, re_lib.IGNORECASE
                ):
                    token_matched = True
                    break
            if token_matched:
                break
        assert token_matched


def test_matt_tiles_query_drops_tiles_keeps_matt():
    """REGRESSION: 'matt tiles' → must search for 'matt' only.
    A tile with attributes.finish='Matt' must be findable."""
    q = build_tile_search_query("matt tiles")
    inner = q["$and"][0]
    assert "$or" in inner
    # The 'matt' regex is in there, applied to attributes.finish among others
    found_finish = False
    for clause in inner["$or"]:
        if "attributes.finish" in clause:
            assert clause["attributes.finish"]["$regex"] == "matt"
            found_finish = True
    assert found_finish


def test_green_tiles_includes_attributes_color_field():
    """A tile with attributes.color='Green' must be findable."""
    q = build_tile_search_query("green tiles")
    inner = q["$and"][0]
    assert "$or" in inner
    found_color = False
    for clause in inner["$or"]:
        if "attributes.color" in clause:
            assert clause["attributes.color"]["$regex"] == "green"
            found_color = True
    assert found_color

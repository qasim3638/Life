"""Tests for the Stealth-Keyword Performance attribution layer."""
import os
import sys
import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402


@pytest_asyncio.fixture
async def db(monkeypatch):
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    test_db = client[f"test_stealth_perf_{uuid.uuid4().hex[:8]}"]
    monkeypatch.setattr("services.stealth_seo_performance.get_db", lambda: test_db)
    monkeypatch.setattr("services.stealth_seo.get_db", lambda: test_db)
    yield test_db
    await client.drop_database(test_db.name)
    client.close()


# ───── _query_matches_keyword — the matching primitive ─────

def test_phrase_match_any_token_order():
    from services.stealth_seo_performance import _query_matches_keyword
    assert _query_matches_keyword("onyx white tile uk", "Onyx White")
    assert _query_matches_keyword("white onyx polished tile", "Onyx White")
    assert not _query_matches_keyword("white quartz tile", "Onyx White")  # missing onyx


def test_code_substring_match_with_dash():
    from services.stealth_seo_performance import _query_matches_keyword
    assert _query_matches_keyword("lp-6611 datasheet pdf", "LP-6611")
    assert _query_matches_keyword("LP6611 buy uk", "LP-6611")
    assert _query_matches_keyword("buy lp 6611 polished", "LP-6611")


def test_code_does_not_falsely_match_word():
    """Plain English single words go through the token path. So
    'marble' should match 'marble tile' but NOT 'marbleized'."""
    from services.stealth_seo_performance import _query_matches_keyword
    assert _query_matches_keyword("marble tile uk", "marble")
    # 'marbleized' tokenises to single token — no match
    assert not _query_matches_keyword("marbleized counter top", "marble")


def test_short_kw_token_ignored():
    """Tokens under 3 chars are filtered out — avoids 'tv' false positives."""
    from services.stealth_seo_performance import _query_matches_keyword
    # 'tv' as a query token is too short — no match
    assert not _query_matches_keyword("tv stand uk", "tv")


def test_empty_inputs_safe():
    from services.stealth_seo_performance import _query_matches_keyword
    assert not _query_matches_keyword("", "anything")
    assert not _query_matches_keyword("anything", "")
    assert not _query_matches_keyword("", "")


# ───── _attribute_query — the kind classifier ─────

@pytest.mark.asyncio
async def test_attribute_stealth_win(db):
    from services.stealth_seo_performance import _attribute_query
    universe = {
        "products": [{
            "id": "t1", "name": "Alabaster Polished", "slug": "alabaster",
            "stealth_keywords": ["Onyx White", "LP-6611"],
            "original_name": "Onyx White", "supplier_code": "LP-6611",
            "collection": "Marble",
        }],
        "collection_keywords": {},
    }
    res = _attribute_query("onyx white polished tile uk", universe)
    assert res["kind"] == "stealth_win"
    keywords = {m["keyword"] for m in res["matches"]}
    assert "Onyx White" in keywords


@pytest.mark.asyncio
async def test_attribute_stealth_via_collection(db):
    from services.stealth_seo_performance import _attribute_query
    universe = {
        "products": [],
        "collection_keywords": {"Marble Effect": ["Calacatta", "Carrara"]},
    }
    res = _attribute_query("calacatta marble uk", universe)
    assert res["kind"] == "stealth_win"
    assert res["matches"][0]["scope"] == "collection"
    assert res["matches"][0]["collection"] == "Marble Effect"


@pytest.mark.asyncio
async def test_attribute_brand_win_when_no_stealth_match(db):
    from services.stealth_seo_performance import _attribute_query
    universe = {
        "products": [{
            "id": "t1", "name": "Alabaster Polished", "slug": "alabaster",
            "stealth_keywords": ["Onyx White"],  # not in query
            "original_name": "Onyx White", "supplier_code": "LP-6611",
            "collection": "Marble",
        }],
        "collection_keywords": {},
    }
    res = _attribute_query("alabaster polished bathroom", universe)
    assert res["kind"] == "brand_win"
    assert res["product_id"] == "t1"


@pytest.mark.asyncio
async def test_attribute_other_when_neither(db):
    from services.stealth_seo_performance import _attribute_query
    universe = {
        "products": [{
            "id": "t1", "name": "Alabaster", "slug": "a",
            "stealth_keywords": ["Onyx White"],
            "original_name": "", "supplier_code": "", "collection": "",
        }],
        "collection_keywords": {},
    }
    res = _attribute_query("how to grout tile floor", universe)
    assert res["kind"] == "other"


# ───── _load_stealth_universe — DB load ─────

@pytest.mark.asyncio
async def test_load_universe_includes_stealth_kws_and_collection(db):
    from services.stealth_seo_performance import _load_stealth_universe
    await db.tiles.insert_one({
        "id": "t1", "name": "Alabaster", "is_active": True,
        "collection": "Marble", "hidden_seo_keywords": "Onyx White, LP-6611",
        "original_name": "Onyx White", "supplier_code": "LP-6611",
        "slug": "alabaster",
    })
    await db.seo_collection_keywords.insert_one({
        "collection": "Marble", "keywords": ["Calacatta", "Carrara"],
    })
    u = await _load_stealth_universe()
    assert len(u["products"]) == 1
    assert "Onyx White" in u["products"][0]["stealth_keywords"]
    assert u["collection_keywords"]["Marble"] == ["Calacatta", "Carrara"]


@pytest.mark.asyncio
async def test_load_universe_skips_inactive(db):
    from services.stealth_seo_performance import _load_stealth_universe
    await db.tiles.insert_many([
        {"id": "t1", "name": "Live", "is_active": True,
         "hidden_seo_keywords": "kw"},
        {"id": "t2", "name": "Archived", "is_active": False,
         "hidden_seo_keywords": "kw"},
    ])
    u = await _load_stealth_universe()
    ids = {p["id"] for p in u["products"]}
    assert ids == {"t1"}


# ───── _compute — the full report ─────

@pytest.mark.asyncio
async def test_compute_full_report_with_mocked_gsc(db, monkeypatch):
    from services import stealth_seo_performance as perf
    # Seed catalogue
    await db.tiles.insert_many([
        {"id": "t1", "name": "Alabaster Polished", "slug": "alabaster",
         "is_active": True, "collection": "Marble",
         "hidden_seo_keywords": "Onyx White, LP-6611",
         "original_name": "Onyx White", "supplier_code": "LP-6611"},
        {"id": "t2", "name": "Calacatta Pro", "slug": "calacatta-pro",
         "is_active": True, "collection": "Marble",
         "hidden_seo_keywords": "MarblePro Tiles",
         "original_name": "MarblePro", "supplier_code": "MP-9000"},
    ])
    await db.seo_collection_keywords.insert_one({
        "collection": "Marble", "keywords": ["Statuario"],
    })

    # Mock GSC
    fake_gsc_data = {
        "site_url": "https://tilestation.co.uk",
        "start_date": "2026-04-06",
        "end_date": "2026-05-04",
        "rows": [
            # Stealth win — query matches per-product kw
            {"query": "onyx white tile uk", "clicks": 50, "impressions": 1000, "ctr": 0.05, "position": 4.5},
            # Stealth win — query matches collection kw
            {"query": "statuario marble uk", "clicks": 20, "impressions": 500, "ctr": 0.04, "position": 6.0},
            # Brand win — query matches product name
            {"query": "alabaster polished bathroom", "clicks": 80, "impressions": 1500, "ctr": 0.053, "position": 2.0},
            # Other — high impression, no match → should appear in missed_wins
            {"query": "porcelain bathroom tile uk", "clicks": 5, "impressions": 800, "ctr": 0.006, "position": 12.0},
            # Other — low impression, dropped from missed wins
            {"query": "how to grout tile", "clicks": 0, "impressions": 2, "ctr": 0.0, "position": 50.0},
        ],
    }
    monkeypatch.setattr(perf.gsc_service, "_pick_connected_admin",
                        AsyncMock(return_value="admin-1"))
    monkeypatch.setattr(perf.gsc_service, "get_top_queries",
                        AsyncMock(return_value=fake_gsc_data))

    report = await perf._compute(days=28)

    assert report["gsc_connected"] is True
    assert report["totals"]["clicks"] == 155
    assert report["stealth"]["clicks"] == 70  # 50 + 20
    assert report["brand"]["clicks"] == 80
    assert report["other"]["clicks"] == 5
    assert report["stealth"]["share_pct"] == round((70 / 155) * 100)
    # Top winners contains "Onyx White" (50 clicks > Statuario 20)
    assert report["top_winners"][0]["keyword"] == "Onyx White"
    assert report["top_winners"][0]["clicks"] == 50
    # Missed wins includes the high-impression unmatched query
    missed_qs = {m["query"] for m in report["missed_wins"]}
    assert "porcelain bathroom tile uk" in missed_qs
    assert "how to grout tile" not in missed_qs  # below noise threshold
    # Underperformers — kw set in DB but not in seen-with-traffic.
    # "MarblePro Tiles" was set on t2 but the GSC fixture didn't surface it
    underperformer_kws = {u["keyword"] for u in report["underperformers"]}
    assert "MarblePro Tiles" in underperformer_kws


@pytest.mark.asyncio
async def test_compute_handles_no_gsc(db, monkeypatch):
    from services import stealth_seo_performance as perf
    monkeypatch.setattr(perf.gsc_service, "_pick_connected_admin",
                        AsyncMock(return_value=None))
    report = await perf._compute(days=28)
    assert report["gsc_connected"] is False
    assert report["totals"]["clicks"] == 0
    assert report["top_winners"] == []


@pytest.mark.asyncio
async def test_compute_handles_gsc_error(db, monkeypatch):
    from services import stealth_seo_performance as perf
    monkeypatch.setattr(perf.gsc_service, "_pick_connected_admin",
                        AsyncMock(return_value="admin-1"))
    monkeypatch.setattr(perf.gsc_service, "get_top_queries",
                        AsyncMock(side_effect=RuntimeError("boom")))
    report = await perf._compute(days=28)
    assert report["gsc_connected"] is True
    assert report["reason"] and "gsc_error" in report["reason"]
    assert report["totals"]["clicks"] == 0


@pytest.mark.asyncio
async def test_get_performance_caches(db, monkeypatch):
    from services import stealth_seo_performance as perf
    call_count = {"n": 0}

    async def fake_compute(*, days):
        call_count["n"] += 1
        return {"days": days, "computed_at": call_count["n"]}

    monkeypatch.setattr(perf, "_compute", fake_compute)
    r1 = await perf.get_performance(days=28)
    r2 = await perf.get_performance(days=28)
    assert call_count["n"] == 1  # second call hit cache
    assert r1["computed_at"] == r2["computed_at"]


@pytest.mark.asyncio
async def test_get_performance_force_refresh_bypasses_cache(db, monkeypatch):
    from services import stealth_seo_performance as perf
    call_count = {"n": 0}

    async def fake_compute(*, days):
        call_count["n"] += 1
        return {"days": days, "computed_at": call_count["n"]}

    monkeypatch.setattr(perf, "_compute", fake_compute)
    await perf.get_performance(days=28)
    await perf.get_performance(days=28, force_refresh=True)
    assert call_count["n"] == 2


@pytest.mark.asyncio
async def test_get_performance_different_window_uses_separate_cache(db, monkeypatch):
    from services import stealth_seo_performance as perf
    call_count = {"n": 0}

    async def fake_compute(*, days):
        call_count["n"] += 1
        return {"days": days}

    monkeypatch.setattr(perf, "_compute", fake_compute)
    await perf.get_performance(days=7)
    await perf.get_performance(days=28)
    assert call_count["n"] == 2  # different days → different cache key

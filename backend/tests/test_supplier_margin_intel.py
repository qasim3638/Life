"""Tests for the Supplier Margin Intelligence service."""
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
    test_db = client[f"test_margin_intel_{uuid.uuid4().hex[:8]}"]
    monkeypatch.setattr("services.supplier_margin_intel.get_db", lambda: test_db)
    yield test_db
    await client.drop_database(test_db.name)
    client.close()


# ───── Helpers ─────

def test_margin_math():
    from services.supplier_margin_intel import _margin
    assert _margin(100, 40) == (60, 60.0)
    # Zero / None price
    assert _margin(0, 5) == (None, None)
    assert _margin(None, 5) == (None, None)
    assert _margin(100, None) == (None, None)


def test_composite_score_prefers_margin_plus_traffic_sweet_spot():
    from services.supplier_margin_intel import _composite_score
    # 60% margin, 0 impressions = 0 (nobody finds it)
    assert _composite_score(60, 0) == 0.0
    # 5% margin, massive impressions = low score (loss leader)
    a = _composite_score(5, 2000)
    # 45% margin, moderate impressions = HIGHER score (sweet spot)
    b = _composite_score(45, 500)
    assert b > a


def test_composite_score_zero_when_margin_none_or_negative():
    from services.supplier_margin_intel import _composite_score
    assert _composite_score(None, 1000) == 0.0
    assert _composite_score(-10, 1000) == 0.0


def test_product_query_set_dedupes():
    from services.supplier_margin_intel import _product_query_set
    p = {
        "original_name": "Onyx White",
        "supplier_code": "LP-6611",
        "hidden_seo_keywords": "Onyx White, LP-6611, Onyx White Polished",
    }
    qs = _product_query_set(p)
    assert qs == ["Onyx White", "LP-6611", "Onyx White Polished"]


def test_product_query_set_handles_empty_fields():
    from services.supplier_margin_intel import _product_query_set
    assert _product_query_set({}) == []
    assert _product_query_set({"original_name": "", "supplier_code": None}) == []


# ───── _attribute_gsc_rows ─────

def test_attribute_rows_matches_and_sums():
    from services.supplier_margin_intel import _attribute_gsc_rows
    rows = [
        {"query": "onyx white tile uk", "clicks": 3, "impressions": 50},
        {"query": "lp-6611 datasheet", "clicks": 1, "impressions": 20},
        {"query": "unrelated query", "clicks": 99, "impressions": 999},
    ]
    clicks, impr = _attribute_gsc_rows(rows, ["Onyx White", "LP-6611"])
    assert clicks == 4
    assert impr == 70


def test_attribute_rows_dedupes_same_query_matching_multiple_phrases():
    """Query that matches 2 phrases counts ONCE — not twice."""
    from services.supplier_margin_intel import _attribute_gsc_rows
    rows = [
        {"query": "onyx white lp-6611 datasheet", "clicks": 5, "impressions": 100},
    ]
    phrases = ["Onyx White", "LP-6611"]
    clicks, impr = _attribute_gsc_rows(rows, phrases)
    assert clicks == 5  # NOT 10
    assert impr == 100


def test_attribute_rows_handles_empty():
    from services.supplier_margin_intel import _attribute_gsc_rows
    assert _attribute_gsc_rows([], ["Onyx"]) == (0, 0)
    assert _attribute_gsc_rows([{"query": "x"}], []) == (0, 0)


# ───── _compute_report — end-to-end ─────

@pytest.mark.asyncio
async def test_compute_report_happy_path(db, monkeypatch):
    from services import supplier_margin_intel as mi
    # Seed 3 products with varying margins + GSC-matchable names
    await db.tiles.insert_many([
        # Sweet spot: 65% margin + organic traffic
        {"id": "t1", "slug": "alabaster", "name": "Alabaster",
         "is_active": True, "collection": "Marble",
         "supplier_name": "LEPORCE", "supplier_code": "LP-6611",
         "original_name": "Onyx White", "price": 28.99, "cost_price": 10.5,
         "images": ["https://example.com/t1.jpg"]},
        # Loss leader: 5% margin + lots of traffic
        {"id": "t2", "slug": "basic-white", "name": "Basic White",
         "is_active": True, "collection": "Basic",
         "supplier_name": "CHEAPCORP", "supplier_code": "BW-1",
         "original_name": "White Budget", "price": 10.0, "cost_price": 9.5,
         "images": []},
        # Rich product with NO organic demand
        {"id": "t3", "slug": "luxe", "name": "Luxe Marble",
         "is_active": True, "collection": "Premium",
         "supplier_name": "LEPORCE", "supplier_code": "LX-99",
         "original_name": "Luxe Original", "price": 200.0, "cost_price": 50.0,
         "images": []},
    ])
    fake_this_week = {"rows": [
        {"query": "onyx white uk", "clicks": 5, "impressions": 200, "ctr": 0.025, "position": 5},
        {"query": "lp-6611 datasheet", "clicks": 2, "impressions": 50, "ctr": 0.04, "position": 3},
        {"query": "white budget", "clicks": 10, "impressions": 1500, "ctr": 0.007, "position": 20},
    ]}
    fake_fortnight = {"rows": [
        {"query": "onyx white uk", "clicks": 7, "impressions": 260, "ctr": 0.027, "position": 5},
        {"query": "lp-6611 datasheet", "clicks": 3, "impressions": 70, "ctr": 0.043, "position": 3},
        {"query": "white budget", "clicks": 20, "impressions": 3000, "ctr": 0.007, "position": 20},
    ]}
    monkeypatch.setattr(mi, "_attribute_gsc_rows", mi._attribute_gsc_rows)  # keep the real one
    from services import gsc as gsc_service
    monkeypatch.setattr(gsc_service, "_pick_connected_admin",
                        AsyncMock(return_value="admin"))
    monkeypatch.setattr(gsc_service, "get_top_queries",
                        AsyncMock(side_effect=[fake_this_week, fake_fortnight]))

    report = await mi._compute_report(top_n=5)
    assert report["summary"]["total_products"] == 3
    assert report["summary"]["with_cost_data"] == 3
    assert report["summary"]["gsc_connected"] is True
    # t1 should top the list (65% margin + 250 impressions = high score)
    top = report["top_revenue_gen"]
    assert top[0]["product_id"] == "t1"
    assert top[0]["margin_pct"] > 60
    assert top[0]["impressions_this_week"] == 250  # 200 + 50
    # impressions_this_week=250, last_week=250 impr*2 - 250 = 80 → delta ≈ +212%
    assert top[0]["impressions_delta_pct"] > 0  # growing this week
    # Price-test candidates: t2 (5% margin, 1500 impr) should be there
    pt_candidates = report["price_test_candidates"]
    assert any(c["product_id"] == "t2" for c in pt_candidates)
    # Supplier league: LEPORCE has 2 products, CHEAPCORP has 1
    suppliers = {s["supplier"]: s for s in report["suppliers"]}
    assert suppliers["LEPORCE"]["product_count"] == 2
    assert suppliers["CHEAPCORP"]["product_count"] == 1


@pytest.mark.asyncio
async def test_compute_report_no_gsc(db, monkeypatch):
    """When GSC isn't connected, report still renders — just with
    zero impressions everywhere (so score is 0)."""
    from services import supplier_margin_intel as mi
    from services import gsc as gsc_service
    await db.tiles.insert_one({
        "id": "t1", "slug": "a", "name": "A", "is_active": True,
        "supplier_name": "X", "price": 100, "cost_price": 40,
    })
    monkeypatch.setattr(gsc_service, "_pick_connected_admin",
                        AsyncMock(return_value=None))
    report = await mi._compute_report(top_n=5)
    assert report["summary"]["gsc_connected"] is False
    # Report still builds; score is 0 since no impressions
    assert len(report["top_revenue_gen"]) == 1
    assert report["top_revenue_gen"][0]["score"] == 0.0
    assert report["top_revenue_gen"][0]["margin_pct"] == 60.0


@pytest.mark.asyncio
async def test_compute_report_skips_inactive(db, monkeypatch):
    from services import supplier_margin_intel as mi
    from services import gsc as gsc_service
    await db.tiles.insert_many([
        {"id": "t1", "is_active": True, "price": 100, "cost_price": 40,
         "supplier_name": "X", "name": "Live"},
        {"id": "t2", "is_active": False, "price": 100, "cost_price": 40,
         "supplier_name": "X", "name": "Archived"},
    ])
    monkeypatch.setattr(gsc_service, "_pick_connected_admin",
                        AsyncMock(return_value=None))
    report = await mi._compute_report()
    assert report["summary"]["total_products"] == 1
    assert report["top_revenue_gen"][0]["product_id"] == "t1"


@pytest.mark.asyncio
async def test_compute_report_handles_missing_cost_gracefully(db, monkeypatch):
    from services import supplier_margin_intel as mi
    from services import gsc as gsc_service
    await db.tiles.insert_many([
        {"id": "t1", "is_active": True, "price": 100, "cost_price": None,
         "supplier_name": "X", "name": "No cost"},
        {"id": "t2", "is_active": True, "price": 100, "cost_price": 40,
         "supplier_name": "X", "name": "Has cost"},
    ])
    monkeypatch.setattr(gsc_service, "_pick_connected_admin",
                        AsyncMock(return_value=None))
    report = await mi._compute_report()
    assert report["summary"]["total_products"] == 2
    assert report["summary"]["with_cost_data"] == 1
    by_id = {r["product_id"]: r for r in report["top_revenue_gen"]}
    assert by_id["t1"]["margin_pct"] is None
    assert by_id["t2"]["margin_pct"] == 60.0


@pytest.mark.asyncio
async def test_compute_report_impressions_delta_edge_cases(db, monkeypatch):
    """When last_week=0 + this_week>0 → delta=100%. When both 0 → 0%."""
    from services import supplier_margin_intel as mi
    from services import gsc as gsc_service
    await db.tiles.insert_many([
        {"id": "t1", "is_active": True, "price": 100, "cost_price": 40,
         "supplier_name": "X", "original_name": "Brand New Product",
         "name": "Brand New Product"},
        {"id": "t2", "is_active": True, "price": 100, "cost_price": 40,
         "supplier_name": "X", "original_name": "Silent Product",
         "name": "Silent Product"},
    ])
    # this_week has traffic for "brand new product" but fortnight doesn't
    # → last_week = 0 → delta = 100%
    monkeypatch.setattr(gsc_service, "_pick_connected_admin",
                        AsyncMock(return_value="admin"))
    monkeypatch.setattr(gsc_service, "get_top_queries", AsyncMock(side_effect=[
        {"rows": [{"query": "brand new product uk", "clicks": 5, "impressions": 100}]},
        {"rows": [{"query": "brand new product uk", "clicks": 5, "impressions": 100}]},
    ]))
    report = await mi._compute_report()
    by_id = {r["product_id"]: r for r in report["top_revenue_gen"]}
    assert by_id["t1"]["impressions_delta_pct"] == 100.0  # 0 → 100
    assert by_id["t2"]["impressions_delta_pct"] == 0.0   # 0 → 0 (no traffic)


# ───── get_margin_report — caching ─────

@pytest.mark.asyncio
async def test_get_margin_report_cached(db, monkeypatch):
    from services import supplier_margin_intel as mi
    calls = {"n": 0}

    async def fake_compute(*, top_n):
        calls["n"] += 1
        return {"top_n": top_n, "computed": calls["n"]}

    monkeypatch.setattr(mi, "_compute_report", fake_compute)
    r1 = await mi.get_margin_report()
    r2 = await mi.get_margin_report()
    assert calls["n"] == 1  # 2nd call hit cache


@pytest.mark.asyncio
async def test_get_margin_report_force_refresh(db, monkeypatch):
    from services import supplier_margin_intel as mi
    calls = {"n": 0}

    async def fake_compute(*, top_n):
        calls["n"] += 1
        return {"computed": calls["n"]}

    monkeypatch.setattr(mi, "_compute_report", fake_compute)
    await mi.get_margin_report()
    await mi.get_margin_report(force_refresh=True)
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_get_margin_report_different_top_n_separate_cache(db, monkeypatch):
    from services import supplier_margin_intel as mi
    calls = {"n": 0}

    async def fake_compute(*, top_n):
        calls["n"] += 1
        return {"top_n": top_n}

    monkeypatch.setattr(mi, "_compute_report", fake_compute)
    await mi.get_margin_report(top_n=10)
    await mi.get_margin_report(top_n=50)
    assert calls["n"] == 2  # different top_n → different cache key

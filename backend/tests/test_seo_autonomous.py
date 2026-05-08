"""Tests for autonomous SEO module — internal links, schema, hooks."""
import asyncio
import os
import pytest


def _db():
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
    from motor.motor_asyncio import AsyncIOMotorClient
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return cli, cli[os.environ["DB_NAME"]]


def test_local_business_picks_closest_showroom_by_coords():
    from services.seo_autonomous import local_business_jsonld

    # Coords near Gravesend
    row = {"lat": 51.4419, "lon": 0.3712, "town": "Gravesend"}
    out = local_business_jsonld(row)
    assert out["@type"] == "TileStore"
    assert "Gravesend" in out["name"]
    assert out["address"]["postalCode"] == "DA12 5ND"
    assert out["areaServed"]["name"] == "Gravesend"


def test_local_business_picks_by_city_name_when_no_coords():
    from services.seo_autonomous import local_business_jsonld

    # No coords — should match by name
    row = {"town": "Chingford"}
    out = local_business_jsonld(row)
    assert "Chingford" in out["name"]
    assert out["address"]["addressRegion"] == "London"


def test_local_business_falls_back_to_tonbridge_when_unknown_city():
    from services.seo_autonomous import local_business_jsonld

    row = {"town": "Glasgow"}  # no showroom in Glasgow
    out = local_business_jsonld(row)
    assert "Tonbridge" in out["name"]  # head office fallback


def test_article_jsonld_shape():
    from services.seo_autonomous import article_jsonld

    row = {
        "slug": "tile-shop-london",
        "meta_title": "Tile Shop London",
        "meta_description": "Shop tiles in London",
        "approved_at": "2026-05-03T00:00:00+00:00",
    }
    out = article_jsonld(row)
    assert out["@type"] == "Article"
    assert out["headline"] == "Tile Shop London"
    assert out["author"]["@type"] == "Organization"
    assert "/tile-shop-london" in out["url"]


def test_internal_links_returns_nearby_and_collections():
    from services.seo_autonomous import internal_links_for_city

    async def _go():
        cli, db = _db()
        # We need at least one approved page in the DB. The CI fixture
        # has gravesend; query nearby for it.
        seed_count = await db.city_landing_pages.count_documents({"status": "approved"})
        if seed_count < 2:
            pytest.skip(f"need >=2 approved city pages, got {seed_count}")
        first = await db.city_landing_pages.find_one(
            {"status": "approved"}, {"_id": 0, "slug": 1}
        )
        result = await internal_links_for_city(db, first["slug"])
        cli.close()
        return result

    result = asyncio.get_event_loop().run_until_complete(_go())
    assert "nearby_cities" in result
    assert "related_collections" in result
    # Both should be lists, not None
    assert isinstance(result["nearby_cities"], list)
    assert isinstance(result["related_collections"], list)


def test_on_city_page_published_logs_to_autopilot_trail():
    """Smoke: hook writes a log entry that the daily digest can read."""
    from services.seo_autonomous import on_city_page_published

    async def _go():
        cli, db = _db()
        # Cleanup before
        await db.seo_autopilot_log.delete_many({"slug": "_pytest_smoke_"})
        await on_city_page_published("_pytest_smoke_")
        rows = await db.seo_autopilot_log.find({"slug": "_pytest_smoke_"}).to_list(length=5)
        # Cleanup after
        await db.seo_autopilot_log.delete_many({"slug": "_pytest_smoke_"})
        cli.close()
        return rows

    rows = asyncio.get_event_loop().run_until_complete(_go())
    assert len(rows) >= 1
    assert rows[0]["kind"] == "city_page_published"


def test_daily_digest_aggregates_recent_logs():
    from datetime import datetime, timezone
    from services.seo_autonomous import daily_published_digest

    async def _go():
        cli, db = _db()
        # Inject 3 fake publish logs
        now = datetime.now(timezone.utc)
        await db.seo_autopilot_log.insert_many([
            {"kind": "city_page_published", "slug": "_pytest_a", "url": "x", "ts": now},
            {"kind": "city_page_published", "slug": "_pytest_b", "url": "y", "ts": now},
            {"kind": "variant_promoted", "slug": "_pytest_c", "winner": "b", "ts": now},
        ])
        try:
            digest = await daily_published_digest()
        finally:
            await db.seo_autopilot_log.delete_many({"slug": {"$in": ["_pytest_a", "_pytest_b", "_pytest_c"]}})
        cli.close()
        return digest

    digest = asyncio.get_event_loop().run_until_complete(_go())
    assert digest["published_count"] >= 2
    assert digest["promoted_count"] >= 1


def test_haversine_distance_sanity():
    from services.seo_autonomous import _haversine_km
    # Tonbridge to Gravesend ~30 km
    d = _haversine_km(51.1907, 0.2706, 51.4419, 0.3712)
    assert 25 < d < 40, f"expected 25-40 km, got {d:.1f}"
    # Same point → 0
    d2 = _haversine_km(51.0, 0.0, 51.0, 0.0)
    assert d2 < 0.01

"""Tests for the Editorial Autopilot — competitor-driven article engine."""
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402


@pytest_asyncio.fixture
async def db(monkeypatch):
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    test_db = client[f"test_eap_{uuid.uuid4().hex[:8]}"]
    monkeypatch.setattr("services.editorial_autopilot.get_db", lambda: test_db)
    yield test_db
    await client.drop_database(test_db.name)
    client.close()


# ───── Tile-relevance vocabulary filter ─────

def test_tile_relevance_positive():
    from services.editorial_autopilot import _is_tile_relevant
    assert _is_tile_relevant("https://toppstiles.co.uk/blog/ceramic-vs-porcelain", "ceramic vs porcelain")
    assert _is_tile_relevant("", "marble bathroom inspiration")
    assert _is_tile_relevant("/grout-colours/", "")
    assert _is_tile_relevant("/category/wet-room", "")


def test_tile_relevance_negative():
    from services.editorial_autopilot import _is_tile_relevant
    assert not _is_tile_relevant("https://example.com/2024/best-laptops", "best laptops 2024")
    assert not _is_tile_relevant("", "10 ways to invest in stocks")


def test_normalise_topic_collapses_whitespace_and_punct():
    from services.editorial_autopilot import _normalise_topic
    assert _normalise_topic("https://toppstiles.co.uk/blog/Ceramic-vs-Porcelain", "Ceramic vs Porcelain") \
        == "blog ceramic vs porcelain ceramic vs porcelain"


def test_slugify_handles_unicode_and_caps():
    from services.editorial_autopilot import _slugify
    assert _slugify("Calacatta Marble — A Buyer's Guide") == "calacatta-marble-a-buyers-guide"


# ───── Settings round-trip ─────

@pytest.mark.asyncio
async def test_settings_default_then_update(db):
    from services.editorial_autopilot import get_settings, update_settings
    s = await get_settings()
    assert s["paused"] is False
    assert s["monthly_cap_usd"] == 25.0
    assert s["articles_per_run"] == 3

    s2 = await update_settings(paused=True, monthly_cap_usd=50, articles_per_run=5, admin_email="qasim@x")
    assert s2["paused"] is True
    assert s2["monthly_cap_usd"] == 50.0
    assert s2["articles_per_run"] == 5


@pytest.mark.asyncio
async def test_monthly_cap_clamped(db):
    """User can't disable the cap by setting it to 0."""
    from services.editorial_autopilot import update_settings
    s = await update_settings(monthly_cap_usd=0)
    assert s["monthly_cap_usd"] == 1.0  # clamped to min


# ───── Harvest + score + filter ─────

@pytest.mark.asyncio
async def test_harvest_filters_off_topic_and_low_traffic(db, monkeypatch):
    """top_pages returns ceramic guide (relevant) + best laptops (off-topic)
    + a low-traffic tile page (filtered). Only the ceramic guide should
    survive."""
    from services import editorial_autopilot as eap
    monkeypatch.setattr(eap.ahrefs, "DEFAULT_COMPETITORS", ["toppstiles.co.uk"])

    monkeypatch.setattr(eap.ahrefs, "top_pages", AsyncMock(return_value={
        "pages": [
            {"url": "https://toppstiles.co.uk/blog/ceramic-vs-porcelain", "sum_traffic": 8000, "top_keyword": "ceramic vs porcelain"},
            {"url": "https://toppstiles.co.uk/blog/best-laptops", "sum_traffic": 3000, "top_keyword": "best laptops"},
            {"url": "https://toppstiles.co.uk/blog/grout-tip", "sum_traffic": 30, "top_keyword": "grout tip"},  # low traffic
        ]
    }))
    monkeypatch.setattr(eap.ahrefs, "best_by_links", AsyncMock(return_value={"pages": []}))

    out = await eap.harvest_opportunities()
    keywords = [o["top_keyword"] for o in out]
    assert "ceramic vs porcelain" in keywords
    assert "best laptops" not in keywords
    assert "grout tip" not in keywords


@pytest.mark.asyncio
async def test_harvest_merges_duplicate_url_across_reports(db, monkeypatch):
    """If a URL appears in BOTH top_pages and best_by_links the row
    must be merged (single dedupe key) with kind='both'."""
    from services import editorial_autopilot as eap
    monkeypatch.setattr(eap.ahrefs, "DEFAULT_COMPETITORS", ["toppstiles.co.uk"])
    same_url = "https://toppstiles.co.uk/grout-colours-guide"
    monkeypatch.setattr(eap.ahrefs, "top_pages", AsyncMock(return_value={
        "pages": [{"url": same_url, "sum_traffic": 5000, "top_keyword": "grout colours"}]
    }))
    monkeypatch.setattr(eap.ahrefs, "best_by_links", AsyncMock(return_value={
        "pages": [{"url": same_url, "referring_domains": 80, "top_keyword": "grout colours", "sum_traffic": 5000}]
    }))
    out = await eap.harvest_opportunities()
    # Same URL + same top_keyword → identical dedupe key → exactly one
    # merged row with kind='both'.
    urls = [o["source_url"] for o in out]
    assert urls.count(same_url) == 1
    merged = next(o for o in out if o["source_url"] == same_url)
    assert merged["kind"] == "both"
    assert merged["refdomains"] == 80
    assert merged["traffic"] == 5000


@pytest.mark.asyncio
async def test_filter_already_covered_drops_existing_topic(db, monkeypatch):
    """If we already have a blog article on the same topic, filter it out."""
    from services import editorial_autopilot as eap
    await db.blog_articles.insert_one({
        "slug": "ceramic-vs-porcelain",
        "title": "Ceramic vs Porcelain — Which Wins?",
        "topic_key": "blog ceramic vs porcelain ceramic vs porcelain",
        "status": "published",
    })
    candidates = [
        {"topic_key": "blog ceramic vs porcelain ceramic vs porcelain", "source_url": "x", "top_keyword": "x", "score": 100},
        {"topic_key": "completely different", "source_url": "y", "top_keyword": "y", "score": 50},
    ]
    out = await eap.filter_already_covered(candidates)
    assert len(out) == 1
    assert out[0]["topic_key"] == "completely different"


# ───── Spend cap ─────

@pytest.mark.asyncio
async def test_run_skipped_when_paused(db, monkeypatch):
    from services import editorial_autopilot as eap
    await eap.update_settings(paused=True)
    res = await eap.run_weekly_autopilot(force=False)
    assert res["status"] == "skipped_paused"
    assert res["published"] == 0


@pytest.mark.asyncio
async def test_run_skipped_when_cap_reached(db, monkeypatch):
    from services import editorial_autopilot as eap
    # Seed enough published articles this month to exhaust the cap
    now = datetime.now(timezone.utc)
    await db.blog_articles.insert_many([
        {"slug": f"a{i}", "published_at": now.isoformat(), "cost_usd": 5.0,
         "title": f"A{i}", "status": "published"}
        for i in range(6)
    ])
    res = await eap.run_weekly_autopilot(force=False)
    assert res["status"] == "skipped_cap_reached"
    assert res["spent_usd"] == 30.0  # 6 * $5
    assert res["published"] == 0


# ───── Full happy path with mocks ─────

@pytest.mark.asyncio
async def test_full_run_publishes_articles(db, monkeypatch):
    """Happy path: harvest returns 3 relevant opps, Claude returns
    valid drafts, all 3 publish atomically."""
    from services import editorial_autopilot as eap
    monkeypatch.setattr(eap.ahrefs, "DEFAULT_COMPETITORS", ["toppstiles.co.uk", "wallsandfloors.co.uk"])

    monkeypatch.setattr(eap.ahrefs, "top_pages", AsyncMock(return_value={
        "pages": [
            {"url": "https://toppstiles.co.uk/blog/grout-colours", "sum_traffic": 12000, "top_keyword": "grout colours"},
            {"url": "https://wallsandfloors.co.uk/blog/bathroom-tile-ideas", "sum_traffic": 9000, "top_keyword": "bathroom tile ideas"},
            {"url": "https://toppstiles.co.uk/blog/marble-care", "sum_traffic": 7000, "top_keyword": "how to clean marble tiles"},
        ]
    }))
    monkeypatch.setattr(eap.ahrefs, "best_by_links", AsyncMock(return_value={"pages": []}))

    body = " ".join(["word"] * 1500)
    fake_draft = AsyncMock(side_effect=lambda opp, **kw: {
        "title": f"How to Choose {opp['top_keyword'].title()}",
        "meta_description": f"Our pro guide to {opp['top_keyword']} — TileStation, UK." + " padding " * 5,
        "slug": f"choose-{opp['top_keyword']}".replace(" ", "-"),
        "body_md": f"# {opp['top_keyword']}\n\n{body}",
        "hero_prompt": "luxury bathroom photo",
        "internal_links": [{"anchor": "Shop", "url": "/shop"}],
        "faqs": [{"q": "Q?", "a": "A."} for _ in range(4)],
        "primary_keyword": opp["top_keyword"],
        "cost_usd": 0.20,
    })
    monkeypatch.setattr(eap, "draft_article", fake_draft)
    # Skip the background banner generation (it talks to R2)
    monkeypatch.setattr(eap, "_generate_hero_banner", AsyncMock())
    # And the digest email
    monkeypatch.setattr(eap, "_send_digest_email", AsyncMock())

    res = await eap.run_weekly_autopilot(force=True)
    assert res["status"] == "ok"
    assert res["published_count"] == 3
    assert res["failures"] == 0

    # Articles actually persisted with sane fields
    rows = await db.blog_articles.find({}, {"_id": 0}).to_list(length=None)
    assert len(rows) == 3
    for r in rows:
        assert r["status"] == "published"
        assert r["source"] == "autopilot"
        assert r["slug"]
        assert len(r["body_md"].split()) >= 800
        assert r["meta_description"]
        assert r["topic_key"]
        assert r["source_competitor"]


@pytest.mark.asyncio
async def test_publish_handles_slug_collision(db, monkeypatch):
    """If a draft slug already exists, append -2, -3 etc."""
    from services import editorial_autopilot as eap
    await db.blog_articles.insert_one({"slug": "grout-colours", "title": "Existing", "status": "published"})
    body = " ".join(["w"] * 900)
    draft = {
        "title": "Grout Colours", "meta_description": "g" * 130,
        "slug": "grout-colours", "body_md": body,
        "hero_prompt": "x", "internal_links": [], "faqs": [],
        "primary_keyword": "grout", "cost_usd": 0.20,
    }
    opp = {"topic_key": "k", "source_competitor": "x", "source_url": "y", "top_keyword": "z", "score": 0}
    res = await eap.publish_article(draft, opp)
    assert res["slug"] == "grout-colours-2"


@pytest.mark.asyncio
async def test_run_reports_when_no_candidates(db, monkeypatch):
    """Off-topic competitor data → no candidates → status reflects that
    rather than reporting failure."""
    from services import editorial_autopilot as eap
    monkeypatch.setattr(eap.ahrefs, "DEFAULT_COMPETITORS", ["toppstiles.co.uk"])
    monkeypatch.setattr(eap.ahrefs, "top_pages", AsyncMock(return_value={
        "pages": [{"url": "https://toppstiles.co.uk/laptop", "sum_traffic": 9999, "top_keyword": "laptop"}]
    }))
    monkeypatch.setattr(eap.ahrefs, "best_by_links", AsyncMock(return_value={"pages": []}))
    monkeypatch.setattr(eap, "_send_digest_email", AsyncMock())
    res = await eap.run_weekly_autopilot(force=True)
    assert res["status"] == "no_candidates"
    assert res["published_count"] == 0


@pytest.mark.asyncio
async def test_individual_draft_failures_dont_abort_run(db, monkeypatch):
    """If 2 of 3 candidates fail their drafts, the third should still
    publish and the run reports both numbers."""
    from services import editorial_autopilot as eap
    monkeypatch.setattr(eap.ahrefs, "DEFAULT_COMPETITORS", ["toppstiles.co.uk"])
    monkeypatch.setattr(eap.ahrefs, "top_pages", AsyncMock(return_value={
        "pages": [
            {"url": "https://toppstiles.co.uk/grout", "sum_traffic": 9000, "top_keyword": "grout colours"},
            {"url": "https://toppstiles.co.uk/marble", "sum_traffic": 8000, "top_keyword": "marble tiles"},
            {"url": "https://toppstiles.co.uk/bath", "sum_traffic": 7000, "top_keyword": "bathroom tile ideas"},
        ]
    }))
    monkeypatch.setattr(eap.ahrefs, "best_by_links", AsyncMock(return_value={"pages": []}))

    body = " ".join(["w"] * 900)
    call_count = {"n": 0}
    async def _flaky(opp, **kw):
        call_count["n"] += 1
        if call_count["n"] <= 2:
            raise RuntimeError("Claude returned non-JSON")
        return {
            "title": "Bathroom Tile Ideas",
            "meta_description": "g" * 130,
            "slug": "bathroom-tile-ideas",
            "body_md": body, "hero_prompt": "x",
            "internal_links": [], "faqs": [],
            "primary_keyword": "bathroom tile ideas",
            "cost_usd": 0.20,
        }
    monkeypatch.setattr(eap, "draft_article", _flaky)
    monkeypatch.setattr(eap, "_generate_hero_banner", AsyncMock())
    monkeypatch.setattr(eap, "_send_digest_email", AsyncMock())

    res = await eap.run_weekly_autopilot(force=True, max_articles=1)
    assert res["published_count"] == 1
    assert res["failures"] == 2


@pytest.mark.asyncio
async def test_list_and_delete_article(db, monkeypatch):
    from services import editorial_autopilot as eap
    await db.blog_articles.insert_many([
        {"slug": "a1", "title": "A1", "status": "published", "published_at": "2026-01-02"},
        {"slug": "a2", "title": "A2", "status": "published", "published_at": "2026-01-01", "source": "autopilot"},
    ])
    rows = await eap.list_articles()
    # Newest first
    assert rows[0]["slug"] == "a1"
    rows_filtered = await eap.list_articles(source="autopilot")
    assert len(rows_filtered) == 1 and rows_filtered[0]["slug"] == "a2"

    res = await eap.delete_article("a1")
    assert res["deleted"] == 1
    assert await db.blog_articles.count_documents({}) == 1

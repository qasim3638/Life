"""Tests for the SEO Self-Audit service."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services import seo_self_audit as audit


# ───── _grade_for ─────

def test_grade_a_plus():
    assert audit._grade_for(98.5) == "A+"
    assert audit._grade_for(95.0) == "A+"


def test_grade_a():
    assert audit._grade_for(94.9) == "A"
    assert audit._grade_for(90.0) == "A"


def test_grade_b():
    assert audit._grade_for(89.9) == "B"
    assert audit._grade_for(80.0) == "B"


def test_grade_c():
    assert audit._grade_for(79.9) == "C"
    assert audit._grade_for(70.0) == "C"


def test_grade_d():
    assert audit._grade_for(69.9) == "D"
    assert audit._grade_for(60.0) == "D"


def test_grade_f():
    assert audit._grade_for(59.9) == "F"
    assert audit._grade_for(0) == "F"


# ───── Weights ─────

def test_weights_sum_makes_sense():
    """Aggregate weights should be ~100 so the score is interpretable
    as a percentage. Allow 90-110 wiggle room."""
    total = sum(audit.WEIGHTS.values())
    assert 90 <= total <= 110, f"WEIGHTS total = {total}, expected ~100"


def test_pdp_jsonld_is_highest_weighted():
    """PDP JSON-LD is the most valuable check (rich snippets are
    biggest CTR lever). Should be the heaviest weight."""
    assert audit.WEIGHTS["pdp_jsonld"] == max(audit.WEIGHTS.values())


# ───── Check helpers — sitemap ─────

@pytest.mark.asyncio
async def test_sitemap_accessible_pass():
    fake = ("200", "<?xml version='1.0'?><urlset></urlset>", {})
    with patch.object(audit, "_http_get",
                      AsyncMock(return_value=(200, "<?xml version='1.0'?><urlset></urlset>", {}))):
        res = await audit._check_sitemap_accessible()
    assert res["status"] == "pass"


@pytest.mark.asyncio
async def test_sitemap_accessible_fail_on_404():
    with patch.object(audit, "_http_get",
                      AsyncMock(return_value=(404, "Not Found", {}))):
        res = await audit._check_sitemap_accessible()
    assert res["status"] == "fail"


@pytest.mark.asyncio
async def test_sitemap_has_urls_pass_with_many():
    body = "<?xml version='1.0'?>" + ("<loc>https://x</loc>" * 200)
    with patch.object(audit, "_http_get", AsyncMock(return_value=(200, body, {}))):
        res = await audit._check_sitemap_has_urls()
    assert res["status"] == "pass"
    assert "200" in res["detail"]


@pytest.mark.asyncio
async def test_sitemap_has_urls_warn_with_few():
    body = "<?xml version='1.0'?>" + ("<loc>https://x</loc>" * 30)
    with patch.object(audit, "_http_get", AsyncMock(return_value=(200, body, {}))):
        res = await audit._check_sitemap_has_urls()
    assert res["status"] == "warn"


@pytest.mark.asyncio
async def test_sitemap_has_urls_fail_with_almost_none():
    body = "<?xml version='1.0'?>" + ("<loc>https://x</loc>" * 3)
    with patch.object(audit, "_http_get", AsyncMock(return_value=(200, body, {}))):
        res = await audit._check_sitemap_has_urls()
    assert res["status"] == "fail"


# ───── Check helpers — robots ─────

@pytest.mark.asyncio
async def test_robots_disallows_admin_pass():
    body = "User-agent: *\nDisallow: /admin\nDisallow: /api\n"
    with patch.object(audit, "_http_get", AsyncMock(return_value=(200, body, {}))):
        res = await audit._check_robots_disallows_admin()
    assert res["status"] == "pass"


@pytest.mark.asyncio
async def test_robots_disallows_admin_warn_when_missing():
    body = "User-agent: *\nAllow: /\n"  # no /admin disallow
    with patch.object(audit, "_http_get", AsyncMock(return_value=(200, body, {}))):
        res = await audit._check_robots_disallows_admin()
    assert res["status"] == "warn"


# ───── Check helpers — JSON-LD ─────

@pytest.mark.asyncio
async def test_homepage_jsonld_pass_with_org_and_website():
    body = '<html><head><script type="application/ld+json">{"@type":"Organization"}</script><script type="application/ld+json">{"@type":"WebSite"}</script></head></html>'
    with patch.object(audit, "_http_get", AsyncMock(return_value=(200, body, {}))):
        res = await audit._check_homepage_jsonld()
    assert res["status"] == "pass"
    assert "Organization" in res["detail"]


@pytest.mark.asyncio
async def test_homepage_jsonld_fail_when_missing():
    body = "<html><head><title>x</title></head></html>"
    with patch.object(audit, "_http_get", AsyncMock(return_value=(200, body, {}))):
        res = await audit._check_homepage_jsonld()
    assert res["status"] == "fail"
    assert "fix_hint" in res


@pytest.mark.asyncio
async def test_pdp_jsonld_pass_with_offers():
    body = '<script type="application/ld+json">{"@type":"Product","offers":{"price":35.00}}</script>'
    with patch.object(audit, "_http_get", AsyncMock(return_value=(200, body, {}))):
        res = await audit._check_pdp_jsonld("test-slug")
    assert res["status"] == "pass"


@pytest.mark.asyncio
async def test_pdp_jsonld_warn_without_offers():
    body = '<script type="application/ld+json">{"@type":"Product"}</script>'
    with patch.object(audit, "_http_get", AsyncMock(return_value=(200, body, {}))):
        res = await audit._check_pdp_jsonld("test-slug")
    assert res["status"] == "warn"


@pytest.mark.asyncio
async def test_pdp_jsonld_warn_when_no_slug():
    res = await audit._check_pdp_jsonld(None)
    assert res["status"] == "warn"


# ───── Meta tags check ─────

@pytest.mark.asyncio
async def test_meta_tags_pass_with_perfect_lengths():
    title = "X" * 55
    desc = "Y" * 145
    body = f'<title>{title}</title><meta name="description" content="{desc}">'
    with patch.object(audit, "_http_get", AsyncMock(return_value=(200, body, {}))):
        res = await audit._check_meta_tags("https://example.com/")
    assert res["status"] == "pass"


@pytest.mark.asyncio
async def test_meta_tags_warn_with_too_short_title():
    title = "Short"
    desc = "Y" * 145
    body = f'<title>{title}</title><meta name="description" content="{desc}">'
    with patch.object(audit, "_http_get", AsyncMock(return_value=(200, body, {}))):
        res = await audit._check_meta_tags("https://example.com/")
    assert res["status"] == "warn"
    assert "title too short" in res["detail"]


@pytest.mark.asyncio
async def test_meta_tags_fail_when_no_title_or_desc():
    body = "<html></html>"
    with patch.object(audit, "_http_get", AsyncMock(return_value=(200, body, {}))):
        res = await audit._check_meta_tags("https://example.com/")
    assert res["status"] == "fail"


# ───── End-to-end: run_seo_audit ─────

@pytest.mark.asyncio
async def test_run_audit_assembles_report_with_all_checks():
    """Smoke test — the orchestrator runs every check and produces
    the expected score/grade structure even when individual checks
    fail."""
    # Mock _http_get to return safe garbage for every URL
    fake_db = MagicMock()
    fake_db.list_collection_names = AsyncMock(return_value=[])
    fake_db.gsc_credentials.find_one = AsyncMock(return_value=None)
    fake_db.gsc_query_data.find_one = AsyncMock(return_value=None)
    fake_db.gsc_query_data.aggregate = MagicMock(
        return_value=MagicMock(to_list=AsyncMock(return_value=[])),
    )
    fake_db.tiles.count_documents = AsyncMock(return_value=0)
    fake_db.tiles.find_one = AsyncMock(return_value=None)
    fake_db.tiles.aggregate = MagicMock(
        return_value=type("C", (), {"__aiter__": lambda self: iter(())})(),
    )
    fake_db.editorial_autopilot_settings.find_one = AsyncMock(return_value=None)
    fake_db.city_landing_pages.count_documents = AsyncMock(return_value=0)
    fake_db.seo_audit_runs.insert_one = AsyncMock()
    fake_db.seo_audit_latest.replace_one = AsyncMock()

    with patch("services.seo_self_audit.get_db", return_value=fake_db), \
         patch.object(audit, "_http_get",
                      AsyncMock(return_value=(503, "service unavailable", {}))):
        report = await audit.run_seo_audit(persist=False)

    assert "score" in report
    assert "grade" in report
    assert report["grade"] in ("A+", "A", "B", "C", "D", "F")
    assert "checks" in report
    assert len(report["checks"]) >= 15  # all 19 checks attempted
    # With everything 503/missing, score should be very low (F or D)
    assert report["score"] < 30


@pytest.mark.asyncio
async def test_run_audit_persists_when_requested():
    fake_db = MagicMock()
    fake_db.list_collection_names = AsyncMock(return_value=[])
    fake_db.gsc_credentials.find_one = AsyncMock(return_value=None)
    fake_db.gsc_query_data.find_one = AsyncMock(return_value=None)
    fake_db.gsc_query_data.aggregate = MagicMock(
        return_value=MagicMock(to_list=AsyncMock(return_value=[])),
    )
    fake_db.tiles.count_documents = AsyncMock(return_value=0)
    fake_db.tiles.find_one = AsyncMock(return_value=None)
    fake_db.tiles.aggregate = MagicMock(
        return_value=type("C", (), {"__aiter__": lambda self: iter(())})(),
    )
    fake_db.editorial_autopilot_settings.find_one = AsyncMock(return_value=None)
    fake_db.city_landing_pages.count_documents = AsyncMock(return_value=0)
    fake_db.seo_audit_runs.insert_one = AsyncMock()
    fake_db.seo_audit_latest.replace_one = AsyncMock()

    with patch("services.seo_self_audit.get_db", return_value=fake_db), \
         patch.object(audit, "_http_get",
                      AsyncMock(return_value=(200, "<?xml ?><html></html>", {}))):
        await audit.run_seo_audit(persist=True)

    fake_db.seo_audit_runs.insert_one.assert_awaited_once()
    fake_db.seo_audit_latest.replace_one.assert_awaited_once()


# ───── _http_get ─────

@pytest.mark.asyncio
async def test_http_get_never_raises_on_network_error():
    """The audit must never crash on a network blip — _http_get
    catches and returns -1."""
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=Exception("network down"),
        )
        status, body, headers = await audit._http_get("https://example.com")
    assert status == -1
    assert "error" in body

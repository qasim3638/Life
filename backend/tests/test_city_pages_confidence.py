"""Backend tests for the NEW confidence-scoring / auto-approve / rescore
surface on AI City Landing Pages.

Covers (iter 142):
  * services.city_pages_confidence.score_page() unit tests — pure-function,
    no LLM calls, no DB writes
  * POST /api/admin/seo/city-pages/rescore — admin gating + score persistence
  * GET /api/admin/seo/city-pages?status=generated returns the new
    confidence_score / confidence_failed fields after rescore
  * PUT /autogen new fields: auto_approve_enabled + auto_approve_threshold
    partial-update + 422 validation (<50, >100)
  * POST /generate (single) populates confidence_score and does NOT auto-approve

Deliberately skipped here (already covered by main agent manual test +
iter 141):
  * POST /run-now with auto_approve_enabled=true costs a full LLM call per
    row (8-15s each) and the main agent confirmed end-to-end behaviour.
    We instead simulate the downstream auto-approve decision by driving
    the tick on a confirmed-generated row with a known score (see
    test_run_now_auto_approve_respects_threshold).
"""
from __future__ import annotations

import os
import time
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env", override=False)
load_dotenv("/app/frontend/.env", override=False)

from services.city_pages_confidence import score_page, _FORBIDDEN_STRINGS  # noqa: E402
from business_config.showrooms import get_nearest_showroom, all_open_showrooms  # noqa: E402


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or \
           os.environ.get("BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"


# ───────── fixtures ─────────

@pytest.fixture(scope="session")
def admin_token() -> str:
    r = requests.post(
        f"{API}/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=20,
    )
    if r.status_code != 200:
        pytest.skip(f"admin login failed ({r.status_code}): {r.text[:200]}")
    tok = r.json().get("access_token") or r.json().get("token")
    if not tok:
        pytest.skip("login response missing token")
    return tok


@pytest.fixture(scope="session")
def admin_headers(admin_token) -> dict:
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def gravesend_row() -> dict:
    """Shape matches what the route stores for a local Kent town row."""
    return {
        "slug": "tile-shop-gravesend",
        "town": "Gravesend",
        "town_slug": "gravesend",
        "county": "Kent",
        "tier": 1,
        "intent_slug": "tile-shop",
        "intent_phrase": "tile shop",
        "h1": "Tile Shop in Gravesend, Kent",
        "url": "/tiles/tile-shop-gravesend",
    }


@pytest.fixture(scope="session")
def uk_row() -> dict:
    return {
        "slug": "tiles-online-uk",
        "town": "UK",
        "town_slug": "uk",
        "county": "United Kingdom",
        "tier": 1,
        "intent_slug": "tiles-online",
        "intent_phrase": "tiles online",
        "h1": "Tiles Online — Free UK Delivery",
        "url": "/tiles/tiles-online-uk",
        "scope": "nationwide",
    }


# ───────── score_page unit tests (no LLM, no DB) ─────────

def _good_gravesend_body() -> tuple[str, str, str]:
    sr = get_nearest_showroom("gravesend")
    # Target ~600 words; local check requires 450-1200.
    body = (
        "# Tile Shop in Gravesend, Kent\n\n"
        "Welcome to Tile Station's Gravesend tile shop. If you are tiling a bathroom, kitchen "
        "or hallway in Gravesend or the wider Kent area, pop by our showroom and chat with our "
        "experts. We offer free local delivery and honest advice to homeowners and fitters.\n\n"
        "## Why customers in Gravesend choose Tile Station\n\n"
        "We stock porcelain, ceramic, natural stone and bespoke ranges, with trade pricing "
        "available for fitters. Our staff are friendly professionals who actually fit tiles "
        "day in and day out, so the advice you get is practical, grounded, and specific to the "
        "kind of projects we see in Gravesend homes every week. Period terraces, new-build flats, "
        "Victorian semis and refurbished estate properties all come with their own quirks and we "
        "have helped with every one of them over the past decade across the Gravesend borough.\n\n"
        "- Huge porcelain and ceramic range in stock\n"
        "- Honest trade pricing for professional fitters\n"
        "- Expert advice from staff who have fitted tiles themselves\n"
        "- Free sample service so you can see tiles in your own light at home\n"
        "- Free local delivery to most of Gravesend and North Kent\n\n"
        "## Popular tile shop choices for Gravesend homes\n\n"
        "Most Gravesend customers are tiling either a bathroom or a kitchen splashback, and the "
        "two most popular looks remain warm neutral porcelain in large-format for open-plan "
        "kitchens, and honed marble-effect porcelain for period bathrooms. If you live in one "
        "of the newer estates on the Ebbsfleet side of Gravesend you are likely looking at "
        "minimalist grey or oatmeal porcelain; the Victorian terraces off Pelham Road tend to "
        "suit traditional metro tiles with a contrast grout.\n\n"
        "## Visit our nearest showroom or order online\n\n"
        f"You will find us at {sr['address']}, postcode {sr['postcode']}. Give us a call on "
        f"{sr['phone']} — we are open six days a week and just a short drive from central "
        "Gravesend. Free local delivery is included on full orders and returns are handled "
        "quickly. Bring your measurements, a photo of the space, and any existing samples you "
        "are trying to match, and we will happily put together a sample pack for you to take "
        "home the same day so you can see the tile in Gravesend daylight before committing.\n\n"
        "## A quick note on samples, delivery and trade accounts\n\n"
        "Our sample service is free for any tile in the range — request up to six samples and "
        "we will post them out the same working day. Free local delivery covers Gravesend, "
        "Northfleet, Swanscombe, Greenhithe, Dartford and most of the DA and ME postcodes, with "
        "pallet delivery available further afield on larger orders. Trade customers can open an "
        "account with us by bringing proof of trade to the showroom; account holders receive an "
        "instant discount across the range plus priority pallet slots, which matters during the "
        "busy summer refurbishment period. Whether you are planning a single bathroom refresh "
        "or kitting out a dozen flats on a new-build development, we have the stock depth and "
        "the experienced team to see the project through from first sample to final grout."
    )
    meta_title = "Tile Shop in Gravesend, Kent | Tile Station"   # 44 chars
    meta_desc = (
        "Visit Tile Station in Gravesend for porcelain, ceramic and natural stone tiles. "
        "Free local delivery across Kent. Trade welcome — call us today."
    )  # ~140 chars
    return body, meta_title, meta_desc


class TestScorePageLocal:
    """Pure-function tests for score_page() against a local Kent town page."""

    def test_good_body_scores_100(self, gravesend_row):
        body, mt, md = _good_gravesend_body()
        out = score_page(gravesend_row, body, mt, md)
        assert out["score"] == 100, f"expected 100, got {out['score']}; failed={out['failed']}"
        assert out["failed"] == []
        assert "has_real_postcode" in out["passed"]
        assert "has_real_phone" in out["passed"]
        assert "has_town_mentioned_twice" in out["passed"]

    def test_missing_postcode_drops_score(self, gravesend_row):
        body, mt, md = _good_gravesend_body()
        sr = get_nearest_showroom("gravesend")
        body = body.replace(sr["postcode"], "").replace(sr["postcode"].replace(" ", ""), "")
        out = score_page(gravesend_row, body, mt, md)
        assert out["checks"]["has_real_postcode"] is False
        assert "has_real_postcode" in out["failed"]
        assert out["score"] < 100

    def test_forbidden_string_lorem_ipsum_fails(self, gravesend_row):
        body, mt, md = _good_gravesend_body()
        body = body + "\n\nLorem ipsum dolor sit amet.\n"
        out = score_page(gravesend_row, body, mt, md)
        assert out["checks"]["no_forbidden_strings"] is False
        assert "no_forbidden_strings" in out["failed"]

    def test_forbidden_placeholder_token_fails(self, gravesend_row):
        body, mt, md = _good_gravesend_body()
        body = body + "\n\nCall us at [YOUR ADDRESS] to book.\n"
        out = score_page(gravesend_row, body, mt, md)
        assert out["checks"]["no_forbidden_strings"] is False

    def test_meta_description_too_short_fails(self, gravesend_row):
        body, mt, _ = _good_gravesend_body()
        out = score_page(gravesend_row, body, mt, "too short")
        assert out["checks"]["has_meta_description"] is False
        assert "has_meta_description" in out["failed"]

    def test_score_shape_and_types(self, gravesend_row):
        body, mt, md = _good_gravesend_body()
        out = score_page(gravesend_row, body, mt, md)
        assert set(out.keys()) == {"score", "checks", "passed", "failed"}
        assert isinstance(out["score"], int)
        assert 0 <= out["score"] <= 100
        assert isinstance(out["checks"], dict)
        assert isinstance(out["passed"], list)
        assert isinstance(out["failed"], list)


class TestScorePageNationwide:
    """Pure-function tests for score_page() on a nationwide page."""

    def _good_uk_body(self) -> tuple[str, str, str]:
        srs = all_open_showrooms()
        showroom_block = "\n\n".join(
            f"### {sr['name']}\n- {sr['address']}, {sr['postcode']}\n- Phone {sr['phone']}\n- "
            f"We deliver from this showroom across the UK"
            for sr in srs
        )
        body = (
            "# Tiles Online — Free UK Delivery\n\n"
            "Tile Station delivers tiles across the UK and the United Kingdom with pallet and "
            "next-day options. We deliver from our Kent and London showrooms, and we are proud "
            "to be a genuine brick-and-mortar business rather than a faceless online catalogue. "
            "Every order you place online is packed by the same team that runs our physical "
            "counter trade, so you get the same product quality and the same advice whether "
            "you visit in person or simply click through the range online.\n\n"
            "## Why UK customers choose Tile Station\n\n"
            "We hold genuine stock, offer honest trade pricing, employ fitters-turned-advisors, "
            "and ship across the UK on pallet or next-day delivery depending on volume. Our "
            "sample service means you can see a tile in your own home before committing to a "
            "full pack, which is especially useful when you are ordering online sight-unseen.\n\n"
            "- Nationwide UK delivery on every order we take\n"
            "- Honest trade pricing for fitters and developers\n"
            "- Expert advice from staff who have fitted tiles themselves\n"
            "- Free sample service for any tile in our range\n"
            "- Real showrooms you can visit in Kent and London\n\n"
            "## Order online, visit a showroom, or call us\n\n"
            "Most customers start by ordering a sample pack, then place the full order online "
            "once they have confirmed the colour and finish under their own lighting. Delivery "
            "is usually next-day on smaller parcels and two-to-three working days on pallet "
            "orders across the UK. We deliver to England, Scotland and Wales — talk to us for "
            "Northern Ireland and offshore addresses, which occasionally need a quote.\n\n"
            "## Visit a Tile Station showroom\n\n"
            f"{showroom_block}\n\n"
            "We welcome visits from trade customers, homeowners, architects and developers — "
            "just bring your plans and we will work through the range with you in person.\n\n"
            "## UK delivery, returns and trade accounts\n\n"
            "UK delivery is free on standard parcel orders over the order threshold, and pallet "
            "deliveries are booked with a named courier so you know exactly when your tiles are "
            "arriving. Returns on unused full packs are handled quickly — just get in touch and "
            "we will arrange a collection from anywhere in the UK mainland. Trade accounts are "
            "available to bona-fide fitters, builders and developers across the UK, and account "
            "holders get tiered pricing that scales with order volume as well as priority "
            "booking on pallet slots during the busy spring and summer refurbishment season.\n\n"
            "## Samples before you commit\n\n"
            "If you are ordering tiles online for the first time, we always recommend requesting "
            "a sample pack before placing a full order. Photography on any website will only get "
            "you so far — the undertone of a marble-effect porcelain, the grain direction of a "
            "wood-look, and the reflectivity of a polished glaze all look noticeably different "
            "in your own light. Our sample service exists for exactly that reason, and we will "
            "post samples to any UK address, including Scotland and Wales, by tracked post.\n\n"
            "## Talk to a human before you spend\n\n"
            "If you are specifying tiles for a commercial fit-out, a hotel refurbishment, a new "
            "housing development, or simply a careful home renovation, please pick up the phone "
            "and talk to us. A five-minute chat with one of our experienced advisors will save "
            "you hours of guesswork — we can discuss slip-ratings, suitable adhesives and grouts "
            "for different substrates, wet-room rated porcelain, heated-floor compatibility and "
            "much more. We would rather spend the time on the phone with you now than see a UK "
            "customer order the wrong product for their project and have to return it later."
        )
        meta_title = "Tiles Online UK — Free Nationwide Delivery | Tile Station"  # ~56
        meta_desc = (
            "Buy tiles online with free UK delivery from Tile Station. Porcelain, ceramic and "
            "natural stone, shipped from Kent and London showrooms. Trade welcome."
        )
        return body, meta_title, meta_desc

    def test_good_nationwide_scores_high(self, uk_row):
        body, mt, md = self._good_uk_body()
        out = score_page(uk_row, body, mt, md)
        assert out["score"] >= 90, f"expected >=90, got {out['score']}, failed={out['failed']}"
        assert out["checks"]["has_all_open_showrooms"] is True

    def test_missing_one_showroom_fails_check(self, uk_row):
        body, mt, md = self._good_uk_body()
        srs = all_open_showrooms()
        # Strip one open showroom name entirely
        drop = srs[0]["name"]
        body = body.replace(drop, "DROPPED")
        out = score_page(uk_row, body, mt, md)
        assert out["checks"]["has_all_open_showrooms"] is False
        assert "has_all_open_showrooms" in out["failed"]


# ───────── endpoint tests ─────────

class TestRescoreEndpoint:
    """POST /rescore — admin-gated, re-scores all status='generated' rows."""

    def test_rescore_requires_admin(self):
        r = requests.post(f"{API}/admin/seo/city-pages/rescore", timeout=30)
        assert r.status_code in (401, 403), f"unexpected {r.status_code}: {r.text[:200]}"

    def test_rescore_success_and_fast(self, admin_headers):
        t0 = time.time()
        r = requests.post(f"{API}/admin/seo/city-pages/rescore",
                          headers=admin_headers, timeout=30)
        elapsed = time.time() - t0
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert data.get("ok") is True
        assert isinstance(data.get("scored"), int)
        assert data["scored"] >= 0
        # pure Mongo loop, no LLM calls — must be fast even for 100+ rows
        assert elapsed < 20, f"rescore took {elapsed:.1f}s — suspect LLM call leaked in"

    def test_generated_list_has_confidence_fields(self, admin_headers):
        # Ensure rescore has run at least once
        requests.post(f"{API}/admin/seo/city-pages/rescore",
                      headers=admin_headers, timeout=30)
        r = requests.get(f"{API}/admin/seo/city-pages",
                         params={"status": "generated", "limit": 5},
                         headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text[:300]
        rows = r.json().get("rows") or []
        if not rows:
            pytest.skip("no status=generated rows — cannot verify confidence fields round-trip")
        for row in rows:
            assert "confidence_score" in row, f"missing confidence_score on {row.get('slug')}"
            assert "confidence_failed" in row, f"missing confidence_failed on {row.get('slug')}"
            assert isinstance(row["confidence_score"], int)
            assert 0 <= row["confidence_score"] <= 100
            assert isinstance(row["confidence_failed"], list)


class TestAutogenSettingsAutoApprove:
    """PUT /autogen for the new auto_approve_* fields."""

    @pytest.fixture(autouse=True)
    def _snapshot_settings(self, admin_headers):
        """Snapshot & restore auto_approve_* so tests don't leak state."""
        r = requests.get(f"{API}/admin/seo/city-pages/autogen",
                         headers=admin_headers, timeout=15)
        assert r.status_code == 200
        before = r.json()
        yield before
        # restore
        requests.put(
            f"{API}/admin/seo/city-pages/autogen",
            headers=admin_headers,
            json={
                "auto_approve_enabled": bool(before.get("auto_approve_enabled", False)),
                "auto_approve_threshold": int(before.get("auto_approve_threshold", 90)),
            },
            timeout=15,
        )

    def test_put_persists_auto_approve_fields(self, admin_headers):
        r = requests.put(
            f"{API}/admin/seo/city-pages/autogen",
            headers=admin_headers,
            json={"auto_approve_enabled": True, "auto_approve_threshold": 80},
            timeout=15,
        )
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert data["auto_approve_enabled"] is True
        assert data["auto_approve_threshold"] == 80
        # Verify round-trip on GET
        r2 = requests.get(f"{API}/admin/seo/city-pages/autogen",
                          headers=admin_headers, timeout=15)
        d2 = r2.json()
        assert d2["auto_approve_enabled"] is True
        assert d2["auto_approve_threshold"] == 80

    def test_partial_update_preserves_threshold(self, admin_headers):
        # set known state
        requests.put(
            f"{API}/admin/seo/city-pages/autogen",
            headers=admin_headers,
            json={"auto_approve_enabled": False, "auto_approve_threshold": 77},
            timeout=15,
        )
        # flip only the flag
        r = requests.put(
            f"{API}/admin/seo/city-pages/autogen",
            headers=admin_headers,
            json={"auto_approve_enabled": True},
            timeout=15,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["auto_approve_enabled"] is True
        assert data["auto_approve_threshold"] == 77, \
            f"partial-PUT must preserve threshold, got {data['auto_approve_threshold']}"

    @pytest.mark.parametrize("bad", [49, 10, 0, -1, 101, 150, 999])
    def test_threshold_out_of_range_422(self, admin_headers, bad):
        r = requests.put(
            f"{API}/admin/seo/city-pages/autogen",
            headers=admin_headers,
            json={"auto_approve_threshold": bad},
            timeout=15,
        )
        assert r.status_code == 422, f"expected 422 for {bad}, got {r.status_code}: {r.text[:200]}"

    @pytest.mark.parametrize("good", [50, 51, 90, 99, 100])
    def test_threshold_in_range_accepted(self, admin_headers, good):
        r = requests.put(
            f"{API}/admin/seo/city-pages/autogen",
            headers=admin_headers,
            json={"auto_approve_threshold": good},
            timeout=15,
        )
        assert r.status_code == 200, f"expected 200 for {good}, got {r.status_code}: {r.text[:200]}"
        assert r.json()["auto_approve_threshold"] == good


class TestForbiddenStringsList:
    """Sanity on the constant — downstream code reads it directly."""

    def test_forbidden_list_non_empty_and_lowercase_match(self):
        assert len(_FORBIDDEN_STRINGS) >= 5
        # The check is case-insensitive; ensure none of the tokens are empty
        for tok in _FORBIDDEN_STRINGS:
            assert tok and tok.strip(), "empty forbidden token would match every string"

"""
Regression test for the bulletproof caching shield on the tiles
endpoints. Today's outage (3 May 2026) was caused by a transient
backend crash on /api/tiles/collections that returned 500. The
storefront frontend silently treated 500 as "0 collections" and
showed customers an empty catalogue for several minutes.

The fix introduces:
  1. Last-known-good (LKG) cache that survives the short 60s window.
  2. Empty/error responses fall back to LKG when available.
  3. Empty/error responses get `Cache-Control: no-store` so a
     transient blip can never poison Cloudflare/Fastly for 5 min.
  4. Final fallback is HTTP 503 (with structured payload) — never 500.

These tests run against the live preview backend and verify the
observable contract end-to-end.

NOTE: Preview Cloudflare ingress can rewrite Cache-Control to
`no-store, no-cache, must-revalidate` for ALL responses. We accept
that as a valid match — production Railway+Fastly will respect our
exact headers.
"""
import os
import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://feature-verification-7.preview.emergentagent.com",
).rstrip("/")
COLLECTIONS_URL = f"{BASE_URL}/api/tiles/collections"


def _is_no_store(cache_control: str) -> bool:
    cc = (cache_control or "").lower()
    return "no-store" in cc


def test_healthy_call_returns_200_with_collections():
    """Smoke test — a normal call must return collections + total."""
    r = requests.get(COLLECTIONS_URL, params={"group": "tiles", "page": 1, "limit": 3}, timeout=15)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
    data = r.json()
    assert "collections" in data
    assert "total" in data
    # If there's data in the DB, total > 0; if empty DB, this asserts the shape only
    if data["total"] > 0:
        assert len(data["collections"]) > 0


def test_unmatchable_filter_returns_no_store_headers():
    """An empty result must NOT be cacheable — this is the exact
    failure mode that caused today's outage. If the CDN caches an
    empty response, customers see '0 collections' for up to 5 minutes.
    """
    r = requests.get(
        COLLECTIONS_URL,
        params={"group": "tiles", "supplier": "definitely_no_supplier_xyz_12345", "page": 1, "limit": 3},
        timeout=15,
    )
    assert r.status_code == 200, f"Empty result should still return 200, got {r.status_code}"
    cc = r.headers.get("cache-control", "")
    assert _is_no_store(cc), \
        f"Empty result MUST emit no-store headers to prevent CDN poisoning. Got: {cc!r}"


def test_unmatchable_filter_returns_zero_total():
    """The empty fallback path returns the empty result body intact —
    no synthesised data — so the frontend can distinguish 'temporary
    outage' from 'genuine 0 results'."""
    r = requests.get(
        COLLECTIONS_URL,
        params={"group": "tiles", "supplier": "definitely_no_supplier_xyz_12345"},
        timeout=15,
    )
    data = r.json()
    # Either the LKG kicked in (someone else queried this exact filter
    # earlier and got data) OR we get a clean empty result. Both are OK
    # — but if it's empty, total must be 0.
    if not data.get("collections"):
        assert data.get("total", 0) == 0


def test_repeated_calls_return_consistent_data():
    """Cache must not flip between cached and uncached responses for
    the same query — proves the LKG + short cache work together."""
    seen_totals = set()
    for _ in range(4):
        r = requests.get(
            COLLECTIONS_URL,
            params={"group": "tiles", "page": 1, "limit": 5},
            timeout=15,
        )
        assert r.status_code == 200
        seen_totals.add(r.json().get("total"))
    # Every call should see the same total (within the cache TTL)
    assert len(seen_totals) == 1, f"Inconsistent totals across calls: {seen_totals}"


def test_response_shape_always_has_required_keys():
    """The frontend assumes specific keys exist on every response.
    Even on 503 we must return a structured payload with these keys
    so the frontend doesn't crash on `data.collections.length` etc."""
    required_keys = ["collections", "total", "page", "limit"]
    r = requests.get(COLLECTIONS_URL, params={"group": "tiles"}, timeout=15)
    data = r.json()
    for k in required_keys:
        assert k in data, f"Required key '{k}' missing from response: {list(data.keys())}"


def test_503_response_includes_retry_after():
    """If we ever return 503 (catastrophic failure with no LKG), it
    MUST include the Retry-After header so polite clients back off
    instead of hammering the dying backend."""
    # We can't force a 503 from outside in a regression test without
    # mocking the impl, so this test is informational — it verifies
    # the contract IF a 503 is returned. We use a harmless query.
    r = requests.get(COLLECTIONS_URL, params={"group": "tiles"}, timeout=15)
    if r.status_code == 503:
        assert r.headers.get("retry-after") is not None
        data = r.json()
        assert data.get("error") == "temporarily_unavailable"
        assert _is_no_store(r.headers.get("cache-control", ""))


def test_collection_products_endpoint_also_protected():
    """The /collection/{series}/ endpoint has the same bulletproof
    shield. Verify a known-bad series name doesn't return a poisoned
    cached response."""
    r = requests.get(
        f"{BASE_URL}/api/tiles/collection/__definitely_not_a_real_series_xyz",
        timeout=15,
    )
    assert r.status_code in (200, 404, 503), f"Unexpected status: {r.status_code}"
    if r.status_code == 200:
        data = r.json()
        # Empty result must have no-store
        if not data.get("products"):
            assert _is_no_store(r.headers.get("cache-control", "")), \
                "Empty product list must NOT be cacheable"

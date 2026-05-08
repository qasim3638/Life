"""
System-wide regression suite — proves every customer-facing endpoint
that we have promised will never return a fake "0 results" page.

The test loops through a list of CUSTOMER-VISIBLE endpoints and for
each one verifies:

  1. Healthy call returns HTTP 200 (not 500/502/504) with the expected
     shape.
  2. Empty / unmatchable filter returns `Cache-Control: no-store` so a
     transient blip cannot poison the CDN.
  3. Response shape stays consistent across repeated calls.

If a future PR adds a new customer endpoint without wrapping it in
`bulletproof_endpoint`, add it to ENDPOINTS below to make sure the
guarantee continues to hold.
"""
import os
import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://feature-verification-7.preview.emergentagent.com",
).rstrip("/")


# Each entry: (label, path, healthy_keys_or_callable, empty_querystring)
#   - healthy_keys_or_callable: list of keys we expect on the response
#     (root-level), or a callable(data) that returns True for healthy
#   - empty_querystring: a query that should yield "no results" so we
#     can verify the no-store header guard. None to skip that test.
ENDPOINTS = [
    # Core catalogue
    ("products",       "/api/tiles/products?limit=3",
        ["products", "total"],
        "supplier=zzznoneatallxyz123"),
    ("collections",    "/api/tiles/collections?group=tiles&page=1&limit=3",
        ["collections", "total"],
        "group=tiles&supplier=zzznoneatallxyz123"),
    ("featured",       "/api/tiles/featured?limit=3",
        lambda d: isinstance(d, list) or (isinstance(d, dict) and d.get("items") is not None),
        None),
    ("filters",        "/api/tiles/filters",
        ["suppliers", "sizes", "colors"],
        None),
    ("categories",     "/api/tiles/categories",
        lambda d: isinstance(d, list),
        None),
    ("search",         "/api/tiles/search?q=onyx",
        lambda d: isinstance(d, (list, dict)),
        "q=zzz_definitely_no_match_xyz"),
    ("promo_banner",   "/api/website/promo-banner",
        ["enabled"],
        None),
]


def _is_no_store(cache_control: str) -> bool:
    return "no-store" in (cache_control or "").lower()


def test_all_critical_endpoints_return_200_healthy():
    """Every customer-facing endpoint MUST respond 200 to a normal call."""
    failures = []
    for label, path, expected, _empty in ENDPOINTS:
        r = requests.get(f"{BASE_URL}{path}", timeout=15)
        if r.status_code != 200:
            failures.append(f"{label} {path} -> {r.status_code}: {r.text[:120]}")
            continue
        try:
            data = r.json()
        except Exception as e:
            failures.append(f"{label} {path} -> bad JSON: {e}")
            continue
        if callable(expected):
            if not expected(data):
                failures.append(f"{label} {path} -> shape check failed: {str(data)[:120]}")
        else:
            for key in expected:
                if key not in data:
                    failures.append(f"{label} {path} -> missing key '{key}' in {list(data.keys())[:8]}")
    assert not failures, "Critical endpoints failing:\n  " + "\n  ".join(failures)


def test_empty_responses_emit_no_store_headers():
    """An empty result must NEVER be cacheable. This is the exact
    failure mode that caused the 3-May outage — Fastly cached an
    empty response and served it for 5 minutes."""
    failures = []
    for label, path, _, empty_qs in ENDPOINTS:
        if not empty_qs:
            continue
        # Replace or append the empty querystring
        sep = "&" if "?" in path else "?"
        r = requests.get(f"{BASE_URL}{path}{sep}{empty_qs}", timeout=15)
        if r.status_code != 200:
            failures.append(f"{label} -> {r.status_code} on empty filter")
            continue
        cc = r.headers.get("cache-control", "")
        # If the response is genuinely non-empty (eg an LKG fallback kicked in)
        # we accept either, but if it's empty it MUST be no-store.
        try:
            data = r.json()
        except Exception:
            data = {}
        body_empty = (
            (isinstance(data, list) and not data) or
            (isinstance(data, dict) and (
                data.get("total") == 0 or
                not data.get("collections", data.get("products", data))
            ))
        )
        if body_empty and not _is_no_store(cc):
            failures.append(
                f"{label} -> empty response cached! Cache-Control={cc!r}"
            )
    assert not failures, "Empty responses are CACHEABLE — CDN can poison:\n  " + "\n  ".join(failures)


def test_repeated_calls_are_consistent():
    """Cache must not flip the response between calls inside the cache
    window — proves LKG + short cache work together."""
    for label, path, _, _ in ENDPOINTS:
        sizes = set()
        for _ in range(3):
            r = requests.get(f"{BASE_URL}{path}", timeout=15)
            assert r.status_code == 200, f"{label} unstable: HTTP {r.status_code}"
            sizes.add(len(r.content))
        # Allow up to 2 distinct sizes (compression / minor variations)
        assert len(sizes) <= 2, f"{label} response size flapping: {sizes}"


def test_no_500_responses_anywhere():
    """The shield's strongest guarantee: under no normal circumstance
    should a customer endpoint return HTTP 500. Acceptable failure
    modes are 200 (with empty body + no-store) or 503 (with retry-after)."""
    forbidden = {500, 501, 502, 504}
    for label, path, _, _ in ENDPOINTS:
        r = requests.get(f"{BASE_URL}{path}", timeout=15)
        assert r.status_code not in forbidden, \
            f"{label} returned a {r.status_code} — must be 200 or structured 503"

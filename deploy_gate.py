#!/usr/bin/env python3
"""
PRE-DEPLOYMENT GATE - Storefront Regression Prevention
=======================================================

Run this BEFORE every deployment:
    python3 deploy_gate.py

It will:
  1. Run all backend API health checks
  2. Verify critical frontend elements exist in source code
  3. Verify protected components haven't been deleted or emptied
  4. Check that no conditional rendering hides trade login based on tier pricing
  5. Print a clear PASS/FAIL verdict

Exit code 0 = safe to deploy, Exit code 1 = BLOCKED
"""
import sys
import os
import re
import json
import subprocess

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend", "src")
BACKEND_DIR = os.path.join(os.path.dirname(__file__), "backend")

failures = []
warnings = []
passes = []


def check(name, condition, fail_msg="", warn_only=False):
    if condition:
        passes.append(name)
        print(f"  {GREEN}PASS{RESET}  {name}")
    elif warn_only:
        warnings.append(f"{name}: {fail_msg}")
        print(f"  {YELLOW}WARN{RESET}  {name} — {fail_msg}")
    else:
        failures.append(f"{name}: {fail_msg}")
        print(f"  {RED}FAIL{RESET}  {name} — {fail_msg}")


def file_contains(filepath, search_text):
    """Check if a file contains specific text."""
    try:
        with open(filepath, "r") as f:
            return search_text in f.read()
    except FileNotFoundError:
        return False


def file_exists_and_not_empty(filepath, min_lines=5):
    """Check file exists and has meaningful content."""
    try:
        with open(filepath, "r") as f:
            lines = f.readlines()
            return len(lines) >= min_lines
    except FileNotFoundError:
        return False


# ─────────────────────────────────────────────────────────────
# PHASE 1: Protected Component Integrity
# ─────────────────────────────────────────────────────────────
def phase_1_component_integrity():
    print(f"\n{CYAN}{BOLD}Phase 1: Protected Component Integrity{RESET}")

    trade_prompt = os.path.join(FRONTEND_DIR, "components", "shop", "TradeLoginPrompt.jsx")
    vol_table = os.path.join(FRONTEND_DIR, "components", "shop", "VolumePricingTable.jsx")

    # TradeLoginPrompt.jsx must exist and have content
    check(
        "TradeLoginPrompt.jsx exists",
        file_exists_and_not_empty(trade_prompt, 20),
        "CRITICAL: Protected Trade Login component is missing or empty!"
    )

    # VolumePricingTable.jsx must exist and have content
    check(
        "VolumePricingTable.jsx exists",
        file_exists_and_not_empty(vol_table, 15),
        "CRITICAL: Protected Volume Pricing component is missing or empty!"
    )

    # TradeLoginPrompt must export TradeLoginBox
    check(
        "TradeLoginBox exported",
        file_contains(trade_prompt, "export const TradeLoginBox"),
        "TradeLoginBox component not found in TradeLoginPrompt.jsx"
    )

    # TradeLoginPrompt must export TradeLoginBanner
    check(
        "TradeLoginBanner exported",
        file_contains(trade_prompt, "export const TradeLoginBanner"),
        "TradeLoginBanner component not found in TradeLoginPrompt.jsx"
    )

    # VolumePricingTable must have data-testid
    check(
        "VolumePricingTable has data-testid",
        file_contains(vol_table, 'data-testid="volume-pricing-table"'),
        "VolumePricingTable missing data-testid attribute"
    )

    # TradeLoginBox must have data-testid
    check(
        "TradeLoginBox has data-testid",
        file_contains(trade_prompt, 'data-testid="trade-customer-box"'),
        "TradeLoginBox missing data-testid attribute"
    )

    # TradeLoginBanner must have data-testid
    check(
        "TradeLoginBanner has data-testid",
        file_contains(trade_prompt, 'data-testid="trade-login-banner"'),
        "TradeLoginBanner missing data-testid attribute"
    )


# ─────────────────────────────────────────────────────────────
# PHASE 2: Page Integration Checks
# ─────────────────────────────────────────────────────────────
def phase_2_page_integration():
    print(f"\n{CYAN}{BOLD}Phase 2: Page Integration Checks{RESET}")

    collection_page = os.path.join(FRONTEND_DIR, "pages", "shop", "CollectionDetailPage.js")
    tile_page = os.path.join(FRONTEND_DIR, "pages", "shop", "TileDetailPage.js")
    shop_layout = os.path.join(FRONTEND_DIR, "components", "shop", "ShopLayout.js")

    # CollectionDetailPage must import TradeLoginBox
    check(
        "CollectionDetailPage imports TradeLoginBox",
        file_contains(collection_page, "TradeLoginBox"),
        "CollectionDetailPage.js is NOT using the protected TradeLoginBox component!"
    )

    # CollectionDetailPage must import VolumePricingTable
    check(
        "CollectionDetailPage imports VolumePricingTable",
        file_contains(collection_page, "VolumePricingTable"),
        "CollectionDetailPage.js is NOT using the protected VolumePricingTable component!"
    )

    # TileDetailPage must import TradeLoginBox
    check(
        "TileDetailPage imports TradeLoginBox",
        file_contains(tile_page, "TradeLoginBox"),
        "TileDetailPage.js is NOT using the protected TradeLoginBox component!"
    )

    # ShopProductDetail must import TradeLoginBox
    shop_detail = os.path.join(FRONTEND_DIR, "pages", "shop", "ShopProductDetail.js")
    check(
        "ShopProductDetail imports TradeLoginBox",
        file_contains(shop_detail, "TradeLoginBox"),
        "ShopProductDetail.js is NOT using the protected TradeLoginBox component!"
    )

    # ShopLayout must have the Trade tab
    check(
        "ShopLayout has Trade tab",
        file_contains(shop_layout, 'data-testid="trade-tab"'),
        "Header Trade tab missing from ShopLayout!"
    )

    # ANTI-PATTERN CHECK: Trade Login must NOT be conditional on tier_pricing_disabled
    # Read collection page and check for dangerous patterns
    try:
        with open(collection_page, "r") as f:
            content = f.read()
        dangerous = bool(re.search(
            r"tier_pricing_disabled.*TradeLogin|tier.*disabled.*trade.*login",
            content, re.IGNORECASE
        ))
        check(
            "Trade Login NOT gated by tier_pricing_disabled",
            not dangerous,
            "DANGER: Trade Login visibility is tied to tier_pricing_disabled flag!"
        )
    except FileNotFoundError:
        check("CollectionDetailPage.js exists", False, "File not found!")


# ─────────────────────────────────────────────────────────────
# PHASE 3: Backend Health Check
# ─────────────────────────────────────────────────────────────
def phase_3_backend_health():
    print(f"\n{CYAN}{BOLD}Phase 3: Backend Health Check Endpoint{RESET}")

    health_route = os.path.join(BACKEND_DIR, "routes", "storefront_health.py")

    check(
        "storefront_health.py exists",
        file_exists_and_not_empty(health_route, 10),
        "Backend health check route file missing!"
    )

    # Check it's registered in __init__.py
    init_file = os.path.join(BACKEND_DIR, "routes", "__init__.py")
    check(
        "Health route registered in __init__.py",
        file_contains(init_file, "storefront_health"),
        "storefront_health router not registered in routes/__init__.py"
    )


# ─────────────────────────────────────────────────────────────
# PHASE 4: Run Backend Pytest Suite
# ─────────────────────────────────────────────────────────────
def phase_4_backend_tests():
    print(f"\n{CYAN}{BOLD}Phase 4: Backend Regression Tests{RESET}")

    test_file = os.path.join(BACKEND_DIR, "tests", "test_storefront_health.py")
    if not os.path.exists(test_file):
        check("Backend test file exists", False, "test_storefront_health.py not found!")
        return

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", test_file, "-v", "--tb=short", "-q"],
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "BACKEND_URL": "http://localhost:8001"}
        )
        output = result.stdout + result.stderr
        # Count passes/failures from pytest output
        passed_match = re.search(r"(\d+) passed", output)
        failed_match = re.search(r"(\d+) failed", output)
        passed_count = int(passed_match.group(1)) if passed_match else 0
        failed_count = int(failed_match.group(1)) if failed_match else 0

        check(
            f"Pytest: {passed_count} passed, {failed_count} failed",
            failed_count == 0 and passed_count > 0,
            f"Backend tests failed!\n{output}" if failed_count > 0 else "No tests ran"
        )

        if failed_count > 0:
            # Print the failure details
            print(f"\n{RED}Test output:{RESET}")
            for line in output.split("\n"):
                if "FAILED" in line or "AssertionError" in line or "assert" in line.lower():
                    print(f"    {RED}{line}{RESET}")

    except subprocess.TimeoutExpired:
        check("Backend tests completed", False, "Tests timed out after 30s")
    except Exception as e:
        check("Backend tests ran", False, f"Error: {e}")


# ─────────────────────────────────────────────────────────────
# PHASE 5: Critical Data-TestID Audit
# ─────────────────────────────────────────────────────────────
def phase_5_testid_audit():
    print(f"\n{CYAN}{BOLD}Phase 5: Critical data-testid Audit{RESET}")

    required_testids = {
        "trade-customer-box": "Trade Login Box (collection pages)",
        "trade-login-banner": "Trade Login Banner (product pages)",
        "volume-pricing-table": "Volume Pricing Table",
        "trade-tab": "Header Trade Tab",
        "trade-login-link": "Trade Login button link",
        "trade-signup-link": "Trade Sign Up button link",
    }

    # Search all frontend files for each required testid
    for testid, description in required_testids.items():
        found = False
        for root, dirs, files in os.walk(FRONTEND_DIR):
            dirs[:] = [d for d in dirs if d not in ("node_modules", ".git", "build")]
            for fname in files:
                if fname.endswith((".js", ".jsx", ".tsx")):
                    filepath = os.path.join(root, fname)
                    if file_contains(filepath, f'data-testid="{testid}"'):
                        found = True
                        break
            if found:
                break

        check(
            f'data-testid="{testid}" ({description})',
            found,
            f"Missing from codebase! {description} has no test anchor."
        )


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
def main():
    print(f"\n{'='*60}")
    print(f"{BOLD}  STOREFRONT PRE-DEPLOYMENT GATE{RESET}")
    print(f"{'='*60}")

    phase_1_component_integrity()
    phase_2_page_integration()
    phase_3_backend_health()
    phase_4_backend_tests()
    phase_5_testid_audit()

    # ── VERDICT ──
    print(f"\n{'='*60}")
    total = len(passes) + len(failures) + len(warnings)

    if failures:
        print(f"\n{RED}{BOLD}  DEPLOYMENT BLOCKED{RESET}")
        print(f"  {GREEN}{len(passes)}/{total} passed{RESET}, {RED}{len(failures)} FAILED{RESET}, {YELLOW}{len(warnings)} warnings{RESET}\n")
        print(f"{RED}Failures:{RESET}")
        for f in failures:
            print(f"  {RED}x{RESET} {f}")
        if warnings:
            print(f"\n{YELLOW}Warnings:{RESET}")
            for w in warnings:
                print(f"  {YELLOW}!{RESET} {w}")
        print(f"\n{RED}Fix all failures before deploying.{RESET}\n")
        sys.exit(1)
    else:
        print(f"\n{GREEN}{BOLD}  DEPLOYMENT APPROVED{RESET}")
        print(f"  {GREEN}{len(passes)}/{total} passed{RESET}, {YELLOW}{len(warnings)} warnings{RESET}\n")
        if warnings:
            print(f"{YELLOW}Warnings (non-blocking):{RESET}")
            for w in warnings:
                print(f"  {YELLOW}!{RESET} {w}")
        print(f"\n{GREEN}All critical storefront features verified. Safe to deploy.{RESET}\n")
        sys.exit(0)


if __name__ == "__main__":
    main()

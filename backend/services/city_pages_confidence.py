"""
Deterministic confidence scoring for AI-generated City Landing Pages.

Why not use the LLM to self-grade?
----------------------------------
Asking the same model that wrote the page whether the page is good is
unreliable — LLMs over-rate their own output. Instead we run a
short deterministic check-list based on the prompt contract: did the
model actually keep its promises about town name repetition, real
address inclusion, word count, and required H2 sections?

Each check is 0 or 1. We weight them, sum to a 0-100 score, and record
both the score and the per-check breakdown on the document so the admin
UI can show "why did this fail auto-approval?".

Threshold behaviour
-------------------
* ≥ threshold (default 90)  → auto-approve
* < threshold               → stays in `generated`, waits for human
"""
from __future__ import annotations

import re
from typing import Any

from business_config.showrooms import get_nearest_showroom, all_open_showrooms


# Reject any AI output containing these tokens — they're obvious
# placeholders or hallucinations that must never ship to Google.
_FORBIDDEN_STRINGS: tuple[str, ...] = (
    "[YOUR",
    "[ADDRESS",
    "[PHONE",
    "[TOWN",
    "<address>",
    "lorem ipsum",
    "example.com",
    "placeholder",
    "TODO",
    "xxx-xxx-xxxx",
)


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text or ""))


def _has(body: str, needle: str) -> bool:
    """Case-insensitive substring containment, safe for None input."""
    if not body or not needle:
        return False
    return needle.lower() in body.lower()


def _check_local(row: dict, body: str) -> dict[str, bool]:
    """Run checks for a local town page (non-nationwide). Returns a
    flat dict of check_name → pass/fail booleans."""
    town = row.get("town") or ""
    sr = get_nearest_showroom(row.get("town_slug", ""))
    address_token = sr["address"].split(",")[0].strip()  # e.g. "Unit 3 Trade City"
    phone_digits = re.sub(r"[^\d]", "", sr.get("phone") or "")
    body_digits = re.sub(r"[^\d]", "", body or "")
    words = _word_count(body)
    town_mentions = len(re.findall(re.escape(town), body or "", flags=re.IGNORECASE)) if town else 0

    return {
        "has_h1": _has(body, row.get("h1", "")[:40]) if row.get("h1") else False,
        "has_town_mentioned_twice": town_mentions >= 2,
        "has_real_postcode": _has(body, sr["postcode"]),
        "has_real_phone": bool(phone_digits) and phone_digits in body_digits,
        "has_real_address_fragment": _has(body, address_token),
        "has_required_h2s": _has(body, "## ") and body.count("## ") >= 2,
        "has_word_count_ok": 450 <= words <= 1200,
        "no_forbidden_strings": not any(tok.lower() in (body or "").lower() for tok in _FORBIDDEN_STRINGS),
    }


def _check_nationwide(row: dict, body: str) -> dict[str, bool]:
    """Run checks for a nationwide page. Must name every open showroom
    and have the broader word-count budget."""
    open_srs = all_open_showrooms()
    words = _word_count(body)

    return {
        "has_h1": _has(body, row.get("h1", "")[:40]) if row.get("h1") else False,
        "has_all_open_showrooms": all(_has(body, sr["name"]) for sr in open_srs),
        "has_required_h2s": _has(body, "## ") and body.count("## ") >= 3,
        "has_word_count_ok": 600 <= words <= 1500,
        "no_forbidden_strings": not any(tok.lower() in (body or "").lower() for tok in _FORBIDDEN_STRINGS),
        "mentions_uk": _has(body, "UK") or _has(body, "United Kingdom"),
        "mentions_delivery": _has(body, "deliver"),
    }


def score_page(row: dict, body: str | None, meta_title: str | None = None,
               meta_description: str | None = None) -> dict[str, Any]:
    """Return `{score:int 0-100, checks:dict, passed:list, failed:list}`
    so the admin UI can show a score badge AND explain failures."""
    body = body or ""
    is_nationwide = (row.get("scope") == "nationwide") or row.get("town_slug") == "uk"
    checks = _check_nationwide(row, body) if is_nationwide else _check_local(row, body)

    # Meta tags — always checked
    checks["has_meta_title"] = bool(meta_title and 30 <= len(meta_title) <= 75)
    checks["has_meta_description"] = bool(meta_description and 100 <= len(meta_description) <= 180)

    total = len(checks)
    passed = [name for name, ok in checks.items() if ok]
    failed = [name for name, ok in checks.items() if not ok]
    score = round(100 * len(passed) / total) if total else 0

    return {
        "score": score,
        "checks": checks,
        "passed": passed,
        "failed": failed,
    }

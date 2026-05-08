"""
Launch-eve Product Name Audit — scans db.tiles for business-rule violations.

Checks (per /app/backend/BUSINESS_RULES.md):
  1. Missing `finish` (null/empty/whitespace)
  2. Missing `size`   (null/empty/whitespace)
  3. Duplicate SIZE  token in display_name (e.g., "60x60 ... 60x60" — any case)
  4. Duplicate FINISH token in display_name (same finish word 2+ times, case-insensitive)
  5. Wrong-case size in name (60X60 / 60×60 / 60 x 60) — should be lowercase "60x60"
  6. Redundant words in name ("Tile", "Tiles", "Porcelain", "Ceramic", "Cm", "Mm")
  7. Test placeholders leaked (e.g., "NEW_FINISH_VALUE", "TBD", "UNKNOWN")
  8. Double whitespace / leading-trailing whitespace
  9. Inconsistent name vs display_name vs product_name fields

Dry-run by default — prints what WOULD change. Pass `--apply` to write fixes to DB.
Always writes a CSV audit trail to /app/checklists/name_cleanup_<UTC-date>.csv
"""
import asyncio
import argparse
import csv
import os
import re
import sys
from datetime import datetime, timezone
from collections import Counter

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

# Canonical finish vocabulary (matches business_rules FINISHES list).
KNOWN_FINISHES = [
    "Polished", "Matt", "Matte", "Gloss", "Glossy", "Satin", "Honed",
    "Lappato", "Natural", "Rectified", "Textured", "Anti-Slip", "Structured",
    "Brushed", "Semi-Polished",
]

# Size pattern — WxH in mm-style dimension. Captures both correct "60x60"
# and incorrect variants we need to flag ("60X60", "60×60", "60 x 60").
SIZE_RE = re.compile(r"\b(\d{2,4})\s*[xX×]\s*(\d{2,4})(cm|mm)?\b")
# Strict-correct pattern (lowercase 'x', no spaces).
SIZE_STRICT_RE = re.compile(r"\b\d{2,4}x\d{2,4}(cm|mm)?\b")

REDUNDANT_WORDS = {"tile", "tiles", "porcelain", "ceramic", "cm", "mm"}
TEST_PLACEHOLDERS = {
    "new_finish_value", "tbd", "unknown", "n/a", "na", "none",
    "null", "undefined", "test", "placeholder", "xxx",
}


def find_duplicate_size(name: str):
    """Return the size token if it appears 2+ times in the name (any case)."""
    if not name:
        return None
    matches = SIZE_RE.findall(name)
    # matches = list of (w, h, unit) tuples. Count by w×h regardless of case/unit.
    sig = Counter(f"{w}x{h}" for w, h, _ in matches)
    for token, count in sig.items():
        if count >= 2:
            return token
    return None


def find_duplicate_finish(name: str):
    """Return the finish token if it appears 2+ times in the name."""
    if not name:
        return None
    lowered = name.lower()
    for f in KNOWN_FINISHES:
        # whole-word match, case-insensitive
        matches = re.findall(rf"\b{re.escape(f.lower())}\b", lowered)
        if len(matches) >= 2:
            return f
    return None


def find_wrong_case_size(name: str):
    """Return the bad-case size token if present (only the first one)."""
    if not name:
        return None
    for m in SIZE_RE.finditer(name):
        raw = m.group(0)
        # If the raw token is NOT already lowercase-x / no-spaces, flag it.
        if not SIZE_STRICT_RE.fullmatch(raw.strip()):
            return raw
    return None


def find_redundant_words(name: str):
    if not name:
        return []
    tokens = re.findall(r"[A-Za-z]+", name.lower())
    return sorted({t for t in tokens if t in REDUNDANT_WORDS})


def find_test_placeholders(value):
    """Works on strings OR on missing/None values — we only flag strings here."""
    if not value or not isinstance(value, str):
        return None
    lowered = value.strip().lower()
    return lowered if lowered in TEST_PLACEHOLDERS else None


def normalise_size_in_name(name: str) -> str:
    """Rewrites any size token in the name to strict 'WxH' lowercase form,
    preserving the 'cm'/'mm' unit suffix if present."""
    def _rep(m):
        w, h, unit = m.group(1), m.group(2), m.group(3) or ""
        return f"{w}x{h}{unit.lower()}"
    return SIZE_RE.sub(_rep, name)


def dedupe_size_in_name(name: str) -> str:
    """If a size token appears twice, keeps only the first occurrence."""
    dup = find_duplicate_size(name)
    if not dup:
        return name
    # Find all occurrences and drop all but the first.
    seen = False
    out = []
    last_end = 0
    for m in SIZE_RE.finditer(name):
        w, h = m.group(1), m.group(2)
        if f"{w}x{h}" == dup:
            if seen:
                # Skip this match — don't append it
                out.append(name[last_end:m.start()].rstrip())
                last_end = m.end()
                continue
            seen = True
        out.append(name[last_end:m.end()])
        last_end = m.end()
    out.append(name[last_end:])
    return re.sub(r"\s+", " ", "".join(out)).strip()


def dedupe_finish_in_name(name: str) -> str:
    """If a finish word appears twice, keeps only the LAST occurrence (since
    per business rules the finish goes at the end of the name)."""
    dup = find_duplicate_finish(name)
    if not dup:
        return name
    pattern = re.compile(rf"\b{re.escape(dup)}\b", re.IGNORECASE)
    matches = list(pattern.finditer(name))
    if len(matches) < 2:
        return name
    # Remove all but the LAST match
    keep = matches[-1]
    out = []
    last_end = 0
    for m in matches:
        if m is keep:
            out.append(name[last_end:m.end()])
        else:
            out.append(name[last_end:m.start()].rstrip())
        last_end = m.end()
    out.append(name[last_end:])
    return re.sub(r"\s+", " ", "".join(out)).strip()


def collapse_whitespace(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "")).strip()


def build_fix(doc: dict) -> dict:
    """Given a product doc, return {field: new_value} for any fixable issues.
    Does NOT attempt to infer missing finish/size from name — that's flagged
    for manual review because of ambiguity (e.g., "Carrara" could be honed or polished).
    """
    fixes = {}
    # display_name is the canonical customer-facing field; 'name' is often a mirror.
    canonical_name = doc.get("display_name") or doc.get("name") or doc.get("product_name") or ""
    if not canonical_name:
        return fixes

    new_name = canonical_name
    new_name = normalise_size_in_name(new_name)
    new_name = dedupe_size_in_name(new_name)
    new_name = dedupe_finish_in_name(new_name)
    new_name = collapse_whitespace(new_name)

    if new_name != canonical_name:
        if doc.get("display_name"):
            fixes["display_name"] = new_name
        # Mirror to 'name' only when they were the same originally
        if doc.get("name") == canonical_name:
            fixes["name"] = new_name

    # Test placeholder in finish field → clear it so the gap is visible
    finish_val = (doc.get("finish") or "").strip()
    if finish_val and find_test_placeholders(finish_val):
        fixes["finish"] = ""

    return fixes


async def run(apply: bool):
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    cursor = db.tiles.find({}, {
        "id": 1, "sku": 1, "name": 1, "display_name": 1,
        "product_name": 1, "original_name": 1,
        "finish": 1, "size": 1, "supplier": 1, "is_active": 1,
    })

    # Issue buckets
    missing_finish = []
    missing_size = []
    dup_size = []
    dup_finish = []
    wrong_case_size = []
    redundant_words = []
    test_placeholders = []
    whitespace = []
    inconsistent = []

    all_fixes = []   # (id, before_name, after_name, fix_dict)

    total = 0
    async for doc in cursor:
        total += 1
        pid = doc.get("id") or str(doc.get("_id"))
        sku = doc.get("sku", "")
        display_name = doc.get("display_name") or doc.get("name") or ""
        finish = (doc.get("finish") or "").strip()
        size = (doc.get("size") or "").strip()

        if not finish:
            missing_finish.append((pid, sku, display_name))
        elif find_test_placeholders(finish):
            test_placeholders.append((pid, sku, display_name, f"finish={finish}"))

        if not size:
            missing_size.append((pid, sku, display_name))

        d = find_duplicate_size(display_name)
        if d:
            dup_size.append((pid, sku, display_name, d))
        f = find_duplicate_finish(display_name)
        if f:
            dup_finish.append((pid, sku, display_name, f))

        wc = find_wrong_case_size(display_name)
        if wc:
            wrong_case_size.append((pid, sku, display_name, wc))

        rw = find_redundant_words(display_name)
        if rw:
            redundant_words.append((pid, sku, display_name, ",".join(rw)))

        if display_name != collapse_whitespace(display_name):
            whitespace.append((pid, sku, display_name))

        # Inconsistency: name != display_name (both present)
        if doc.get("name") and doc.get("display_name") and doc["name"] != doc["display_name"]:
            inconsistent.append((pid, sku, doc["name"], doc["display_name"]))

        fix = build_fix(doc)
        if fix:
            all_fixes.append((pid, display_name, fix.get("display_name", display_name), fix))

    # ------------ REPORT ------------
    print(f"\nTotal products audited: {total}")
    buckets = [
        ("Missing finish", missing_finish),
        ("Missing size", missing_size),
        ("Duplicate size in name", dup_size),
        ("Duplicate finish in name", dup_finish),
        ("Wrong-case size in name (60X60 / 60×60)", wrong_case_size),
        ("Redundant words in name (tile/porcelain/cm/mm)", redundant_words),
        ("Test placeholders in finish field", test_placeholders),
        ("Whitespace problems in name", whitespace),
        ("name vs display_name inconsistency", inconsistent),
    ]
    for label, bucket in buckets:
        print(f"  {label:50s} {len(bucket):4d}")

    print(f"\nAuto-fixable: {len(all_fixes)}")
    for pid, before, after, fix in all_fixes[:15]:
        print(f"    [{pid[:8]}]  {before!r}")
        print(f"           →  {after!r}  {fix}")
    if len(all_fixes) > 15:
        print(f"    … {len(all_fixes) - 15} more")

    # ------------ CSV AUDIT TRAIL ------------
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%SZ")
    csv_path = f"/app/checklists/name_cleanup_{today}.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["issue_type", "product_id", "sku", "before", "after_or_details"])
        for kind, bucket in [
            ("missing_finish", missing_finish),
            ("missing_size", missing_size),
        ]:
            for row in bucket:
                pid, sku, n = row
                w.writerow([kind, pid, sku, n, ""])
        for pid, sku, n, d in dup_size:
            w.writerow(["dup_size", pid, sku, n, d])
        for pid, sku, n, fin in dup_finish:
            w.writerow(["dup_finish", pid, sku, n, fin])
        for pid, sku, n, wc in wrong_case_size:
            w.writerow(["wrong_case_size", pid, sku, n, wc])
        for pid, sku, n, rw in redundant_words:
            w.writerow(["redundant_words", pid, sku, n, rw])
        for pid, sku, n, detail in test_placeholders:
            w.writerow(["test_placeholder", pid, sku, n, detail])
        for pid, sku, n in whitespace:
            w.writerow(["whitespace", pid, sku, n, ""])
        for pid, sku, n1, n2 in inconsistent:
            w.writerow(["name_mismatch", pid, sku, n1, n2])
        for pid, before, after, fix in all_fixes:
            w.writerow(["autofix_applied" if apply else "autofix_pending",
                        pid, "", before, after])
    print(f"\n  CSV audit trail: {csv_path}")

    # ------------ APPLY ------------
    if apply and all_fixes:
        print(f"\n  Applying {len(all_fixes)} fixes to db.tiles ...")
        applied = 0
        for pid, before, after, fix in all_fixes:
            r = await db.tiles.update_one({"id": pid}, {"$set": {
                **fix, "updated_at": datetime.now(timezone.utc).isoformat(),
            }})
            if r.modified_count:
                applied += 1
        print(f"  Applied {applied}/{len(all_fixes)} fixes.")
    elif not apply:
        print(f"\n  DRY RUN — no writes. Re-run with --apply to commit fixes.")

    client.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    asyncio.run(run(args.apply))

#!/usr/bin/env python3
"""
Backfill `sqm_per_box` and `tiles_per_box` on `supplier_products` and `tiles`.

Root cause of cart "2 m² / 2 boxes same number" bug: 99% of products have
neither field populated, so the storefront falls back to generic display.

Strategy:
  1. Parse the `size` string (e.g. "60x60cm", "600x600", "900x300", "900x300x14mm").
  2. Compute tile face area in m².
  3. Pick `tiles_per_box` as the integer closest to 1.44 m² / tile_m² (UK
     pallet-optimised standard box target), with sane floors for
     very-large formats.
  4. Persist `sqm_per_box = tiles_per_box * tile_m²` (rounded 4dp) and set
     `sqm_per_box_estimated=true` so the data is transparent.
  5. Skip products that are per-unit (adhesive / grout / tools) — surface
     tiles and flooring only.

Idempotent: second run is a no-op because we gate on `sqm_per_box` already
being populated. `--recompute` overrides that gate.

Run:
  python3 scripts/backfill_box_metadata.py           # dry-run, prints summary
  python3 scripts/backfill_box_metadata.py --apply   # writes to both collections
  python3 scripts/backfill_box_metadata.py --apply --recompute   # re-run even if already set
"""

import argparse
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")


SURFACE_GROUPS = {"tiles", "flooring", "surface", None, ""}
UNIT_PRICING = {"unit", "each", "piece"}
TARGET_BOX_M2 = 1.44  # UK tile industry pallet-optimised standard


def parse_tile_area_m2(size_str):
    """Return tile face area in m², or None if unparseable.

    Accepts: "60x60", "60x60cm", "600x600", "600x600mm",
             "30x60cm", "900x300x14mm", "90x300x14/3mm", "80x80x20mm"
    Rule: first two numeric tokens are the face dimensions.
    Unit detection: explicit 'cm'/'mm' suffix wins; otherwise any dimension
                    >= 100 implies millimetres.
    """
    if not size_str:
        return None
    s = str(size_str).lower().replace("×", "x").strip()
    m = re.search(r"(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)", s)
    if not m:
        return None
    w, h = float(m.group(1)), float(m.group(2))
    if w <= 0 or h <= 0:
        return None

    if "cm" in s and "mm" not in s.split("cm")[0]:
        w_cm, h_cm = w, h
    elif "mm" in s:
        w_cm, h_cm = w / 10.0, h / 10.0
    else:
        # No explicit unit — infer by magnitude
        if max(w, h) >= 100:
            w_cm, h_cm = w / 10.0, h / 10.0
        else:
            w_cm, h_cm = w, h

    area = (w_cm * h_cm) / 10000.0
    # Sanity bounds: 1 cm² (0.0001 m²) … 6 m² per tile
    if area <= 0.0001 or area > 6.0:
        return None
    return round(area, 6)


def compute_box_metrics(tile_m2):
    """Pick (tiles_per_box, sqm_per_box) targeting ~1.44 m² per box.

    - tile_m² >= 1.0 → 1 tile/box (large-format slabs).
    - tile_m² >= 0.55 → 2 tiles/box (80/90 cm format).
    - else → closest integer to TARGET_BOX_M2 / tile_m², floored at 1.
    """
    if not tile_m2 or tile_m2 <= 0:
        return None, None
    if tile_m2 >= 1.0:
        tpb = 1
    elif tile_m2 >= 0.55:
        tpb = 2
    else:
        tpb = max(1, round(TARGET_BOX_M2 / tile_m2))
    spb = round(tpb * tile_m2, 4)
    return tpb, spb


def is_surface_product(doc):
    """Only fill box data for surface products (tiles/flooring), never
    per-unit consumables (adhesive, grout, spacers, tools)."""
    pu = (doc.get("pricing_unit") or "").lower().strip()
    if pu in UNIT_PRICING:
        return False
    pg = (doc.get("product_group") or "").lower().strip()
    if pg and pg not in SURFACE_GROUPS:
        return False
    # Main category "adhesive" / "grout" etc. are always unit products
    mc = (doc.get("main_category") or "").lower().strip()
    if any(kw in mc for kw in ("adhesive", "grout", "tool", "trim", "silicone")):
        return False
    return True


def backfill_collection(db, coll_name, *, apply=False, recompute=False):
    coll = db[coll_name]
    total = coll.count_documents({})

    query = {"size": {"$nin": [None, ""]}}
    if not recompute:
        query["$or"] = [
            {"sqm_per_box": {"$in": [None, 0]}},
            {"sqm_per_box": {"$exists": False}},
        ]

    cursor = coll.find(query)

    stats = {
        "scanned": 0,
        "skipped_unit": 0,
        "skipped_unparseable": 0,
        "updated": 0,
        "already_set": 0,
        "examples": [],
    }

    bulk_ops = []
    from pymongo import UpdateOne

    for doc in cursor:
        stats["scanned"] += 1

        if not is_surface_product(doc):
            stats["skipped_unit"] += 1
            continue

        existing_spb = doc.get("sqm_per_box")
        if existing_spb and existing_spb > 0 and not recompute:
            stats["already_set"] += 1
            continue

        tile_m2 = parse_tile_area_m2(doc.get("size"))
        if not tile_m2:
            stats["skipped_unparseable"] += 1
            continue

        tpb, spb = compute_box_metrics(tile_m2)
        if not spb:
            stats["skipped_unparseable"] += 1
            continue

        if len(stats["examples"]) < 8:
            stats["examples"].append(
                f"  {doc.get('sku') or doc.get('supplier_code') or doc.get('id')} · "
                f"size={doc.get('size')} → tile={tile_m2} m², tpb={tpb}, spb={spb}"
            )

        stats["updated"] += 1

        bulk_ops.append(
            UpdateOne(
                {"_id": doc["_id"]},
                {"$set": {
                    "sqm_per_box": spb,
                    "tiles_per_box": tpb,
                    "sqm_per_box_estimated": True,
                    "box_metadata_updated_at": datetime.now(timezone.utc),
                }},
            )
        )

    print(f"\n=== {coll_name} ({total} docs) ===")
    for k, v in stats.items():
        if k == "examples":
            continue
        print(f"  {k}: {v}")
    if stats["examples"]:
        print("  examples:")
        for ex in stats["examples"]:
            print(ex)

    if apply and bulk_ops:
        result = coll.bulk_write(bulk_ops, ordered=False)
        print(f"  → wrote {result.modified_count} docs")
    elif not apply:
        print("  (dry-run — pass --apply to write)")

    return stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Actually write updates")
    parser.add_argument("--recompute", action="store_true", help="Recompute even for docs already set")
    args = parser.parse_args()

    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        print("MONGO_URL and DB_NAME must be set in environment", file=sys.stderr)
        sys.exit(1)

    client = MongoClient(mongo_url)
    db = client[db_name]

    print(f"Mode: {'APPLY' if args.apply else 'DRY-RUN'}   Recompute: {args.recompute}")

    backfill_collection(db, "supplier_products", apply=args.apply, recompute=args.recompute)
    backfill_collection(db, "tiles", apply=args.apply, recompute=args.recompute)

    print("\nDone.")


if __name__ == "__main__":
    main()

"""
Supplier Health Check API
Automatically scans all suppliers and flags data quality issues.
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone
from collections import Counter
from pymongo import MongoClient
from services import get_current_user
import logging
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/supplier-health", tags=["Supplier Health"])


def get_db():
    mongo_url = os.environ.get('MONGO_URL')
    if not mongo_url:
        raise ValueError("MONGO_URL environment variable is required")
    client = MongoClient(mongo_url)
    return client[os.environ.get('DB_NAME', 'tile_station')]


@router.get("/check")
def run_health_check(current_user: dict = Depends(get_current_user)):
    """
    Run a comprehensive health check across all suppliers.
    Returns per-supplier scores and issue details.
    """
    db = get_db()

    suppliers = db.supplier_products.distinct("supplier")
    # Filter out None/empty
    suppliers = [s for s in suppliers if s]

    results = []

    for supplier in sorted(suppliers):
        products = list(db.supplier_products.find(
            {"supplier": supplier},
            {
                "_id": 1, "sku": 1, "supplier_code": 1, "name": 1,
                "product_name": 1, "display_name": 1, "price": 1,
                "cost_price": 1, "list_price": 1, "images": 1,
                "image": 1, "category": 1, "description": 1,
                "in_products_db": 1
            }
        ))

        total = len(products)
        if total == 0:
            continue

        issues = {
            "missing_sku": [],
            "missing_price": [],
            "missing_images": [],
            "missing_category": [],
            "missing_name": [],
            "missing_description": [],
            "duplicate_codes": [],
            "duplicate_names": [],
            "not_synced": [],
        }

        # Track for duplicates
        codes_seen = Counter()
        names_seen = Counter()

        for p in products:
            pid = str(p["_id"])
            code = p.get("supplier_code") or p.get("sku")
            name = p.get("display_name") or p.get("product_name") or p.get("name") or ""

            # Missing SKU
            if not p.get("sku"):
                issues["missing_sku"].append({
                    "id": pid,
                    "code": code or "N/A",
                    "name": name[:60]
                })

            # Missing price
            price = p.get("price") or p.get("cost_price") or p.get("list_price")
            if not price or price == 0:
                issues["missing_price"].append({
                    "id": pid,
                    "code": code or "N/A",
                    "name": name[:60]
                })

            # Missing images
            imgs = p.get("images") or []
            primary = p.get("image")
            if not imgs and not primary:
                issues["missing_images"].append({
                    "id": pid,
                    "code": code or "N/A",
                    "name": name[:60]
                })

            # Missing category
            if not p.get("category"):
                issues["missing_category"].append({
                    "id": pid,
                    "code": code or "N/A",
                    "name": name[:60]
                })

            # Missing name
            if not name.strip():
                issues["missing_name"].append({
                    "id": pid,
                    "code": code or "N/A",
                    "name": "(empty)"
                })

            # Missing description
            if not p.get("description"):
                issues["missing_description"].append({
                    "id": pid,
                    "code": code or "N/A",
                    "name": name[:60]
                })

            # Not synced to products collection
            if not p.get("in_products_db"):
                issues["not_synced"].append({
                    "id": pid,
                    "code": code or "N/A",
                    "name": name[:60]
                })

            # Track codes and names for duplicate detection
            if code:
                codes_seen[code] += 1
            if name.strip():
                names_seen[name.strip().lower()] += 1

        # Build duplicate lists
        dup_codes = {c: count for c, count in codes_seen.items() if count > 1}
        for code_val, count in dup_codes.items():
            matching = [p for p in products if (p.get("supplier_code") or p.get("sku")) == code_val]
            issues["duplicate_codes"].append({
                "code": code_val,
                "count": count,
                "products": [
                    {
                        "id": str(m["_id"]),
                        "name": (m.get("display_name") or m.get("product_name") or m.get("name") or "")[:60]
                    }
                    for m in matching[:5]  # Limit to 5 examples
                ]
            })

        dup_names = {n: count for n, count in names_seen.items() if count > 1}
        for name_val, count in dup_names.items():
            matching = [
                p for p in products
                if (p.get("display_name") or p.get("product_name") or p.get("name") or "").strip().lower() == name_val
            ]
            issues["duplicate_names"].append({
                "name": name_val[:60],
                "count": count,
                "products": [
                    {
                        "id": str(m["_id"]),
                        "code": (m.get("supplier_code") or m.get("sku") or "N/A")
                    }
                    for m in matching[:5]
                ]
            })

        # Calculate health score (0-100)
        issue_counts = {
            "missing_sku": len(issues["missing_sku"]),
            "missing_price": len(issues["missing_price"]),
            "missing_images": len(issues["missing_images"]),
            "missing_category": len(issues["missing_category"]),
            "missing_name": len(issues["missing_name"]),
            "missing_description": len(issues["missing_description"]),
            "duplicate_codes": len(issues["duplicate_codes"]),
            "duplicate_names": len(issues["duplicate_names"]),
            "not_synced": len(issues["not_synced"]),
        }

        total_issues = sum(issue_counts.values())

        # Weight: critical issues matter more
        weighted_penalty = (
            issue_counts["missing_name"] * 3.0 +
            issue_counts["missing_price"] * 2.5 +
            issue_counts["duplicate_codes"] * 2.0 +
            issue_counts["missing_sku"] * 1.5 +
            issue_counts["missing_images"] * 1.0 +
            issue_counts["missing_category"] * 0.8 +
            issue_counts["missing_description"] * 0.5 +
            issue_counts["duplicate_names"] * 1.5 +
            issue_counts["not_synced"] * 0.3
        )

        # Score: 100 minus penalty per product, clamped 0-100
        score = max(0, min(100, round(100 - (weighted_penalty / max(total, 1)) * 100)))

        # Determine status
        if score >= 80:
            status = "healthy"
        elif score >= 50:
            status = "warning"
        else:
            status = "critical"

        results.append({
            "supplier": supplier,
            "total_products": total,
            "health_score": score,
            "status": status,
            "issue_counts": issue_counts,
            "total_issues": total_issues,
            "issues": issues
        })

    # Sort by health score ascending (worst first)
    results.sort(key=lambda x: x["health_score"])

    # Global stats
    total_products = sum(r["total_products"] for r in results)
    total_issues = sum(r["total_issues"] for r in results)
    healthy_count = sum(1 for r in results if r["status"] == "healthy")
    warning_count = sum(1 for r in results if r["status"] == "warning")
    critical_count = sum(1 for r in results if r["status"] == "critical")

    avg_score = round(sum(r["health_score"] for r in results) / max(len(results), 1))

    # Check for null supplier products
    null_supplier_count = db.supplier_products.count_documents({
        "$or": [{"supplier": None}, {"supplier": {"$exists": False}}, {"supplier": ""}]
    })

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_suppliers": len(results),
            "total_products": total_products,
            "total_issues": total_issues,
            "average_score": avg_score,
            "healthy": healthy_count,
            "warning": warning_count,
            "critical": critical_count,
            "null_supplier_products": null_supplier_count
        },
        "suppliers": results
    }

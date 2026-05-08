"""
Public status page endpoints — read-only summary of system health
for B2B trade customers, support partners, and "is the site really
down?" curiosity. Built on top of the same data the internal health
monitor produces; never exposes incident IDs, internal traces, or
admin acknowledgements.

  GET /api/website/status            → overall + per-endpoint snapshot
  GET /api/website/status/uptime     → last 7 days uptime per endpoint
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter

from config import get_db
from utils.bulletproof import bulletproof_endpoint

router = APIRouter(prefix="/website/status", tags=["Public Status"])


# Customer-friendly labels for the endpoints we monitor. Keys must
# match the `label` field used by the internal health monitor.
PUBLIC_LABELS = {
    "Tile Products": "Product catalogue",
    "Tile Collections": "Collections browser",
    "Featured Tiles": "Featured tiles",
    "Tile Filters": "Search filters",
    "Tile Categories": "Category navigation",
    "Tile Search": "Site search",
    "Promo Banner": "Promotional banner",
    "Backend Health": "Core API",
}


def _public_status_label(internal_label: str) -> str:
    return PUBLIC_LABELS.get(internal_label, internal_label)


@router.get("")
@bulletproof_endpoint(
    cache_namespace="public_status",
    empty_check=lambda r: not (isinstance(r, dict) and r.get("services")),
    empty_fallback={"overall": "unknown", "services": [], "checked_at": None},
    short_ttl=30,
)
async def public_status():
    """High-level: are things working right now? Returns one of:
       'operational', 'degraded' (some endpoints unhealthy),
       'major_outage' (most or all unhealthy), or 'unknown'.
    """
    db = get_db()
    services = []
    for internal_label in PUBLIC_LABELS:
        last = await db.health_checks.find_one(
            {"label": internal_label}, {"_id": 0},
            sort=[("checked_at", -1)],
        )
        if not last:
            services.append({
                "name": _public_status_label(internal_label),
                "status": "unknown",
            })
            continue
        services.append({
            "name": _public_status_label(internal_label),
            "status": "operational" if last.get("healthy") else "degraded",
            "response_ms": last.get("elapsed_ms"),
        })

    healthy = sum(1 for s in services if s["status"] == "operational")
    total = len(services)
    if total == 0:
        overall = "unknown"
    elif healthy == total:
        overall = "operational"
    elif healthy >= total * 0.5:
        overall = "degraded"
    else:
        overall = "major_outage"

    return {
        "overall": overall,
        "services": services,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/uptime")
@bulletproof_endpoint(
    cache_namespace="public_status_uptime",
    empty_check=lambda r: not (isinstance(r, dict) and r.get("services")),
    empty_fallback={"days": 7, "services": []},
    short_ttl=300,  # 5 min
)
async def public_uptime(days: int = 7):
    """Per-service uptime % over the last N days.
    We expose only the percentage and 'incidents' count — never
    raw failure reasons (those can leak internal details)."""
    days = max(1, min(int(days or 7), 30))
    db = get_db()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    services = []
    for internal_label in PUBLIC_LABELS:
        # Count healthy vs unhealthy checks in the window
        total = await db.health_checks.count_documents({
            "label": internal_label, "checked_at": {"$gte": cutoff},
        })
        healthy = await db.health_checks.count_documents({
            "label": internal_label, "checked_at": {"$gte": cutoff}, "healthy": True,
        })
        # Incident count = number of distinct outage incidents
        incidents = await db.health_alerts.count_documents({
            "label": internal_label, "first_failure_at": {"$gte": cutoff},
        })

        uptime_pct = (healthy / total * 100) if total > 0 else None
        services.append({
            "name": _public_status_label(internal_label),
            "uptime_percent": round(uptime_pct, 3) if uptime_pct is not None else None,
            "incidents": incidents,
            "checks_recorded": total,
        })

    return {"days": days, "services": services}

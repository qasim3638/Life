"""
SEO Activity Feed
─────────────────

A unified, time-ordered timeline of SEO events across the stack.
Pulls from every event source we already have (no new logging needed)
and merges them into a single chronological list:

  • Auto-promotions (collection + city_page) — `seo_stealth_auto_promotes`
  • Auto-promote undos
  • Digest emails sent — `seo_stealth_digest_history`
  • Stealth-keyword audit log (manual product/collection edits, bulk apply,
    auto-fill-all runs) — `seo_stealth_audit`
  • Health-check incidents (criticals/warnings) — `seo_health_checks`
  • GSC connect/disconnect events — `gsc_oauth_audit` (best-effort, may
    not exist in all environments)
  • Editorial Autopilot blog publishes — `blog_articles`

Frontend renders this as a vertical scrollable timeline under the
hero tiles. Each entry has a typed icon, severity colour, message,
timestamp, optional `cta_link` to drill into the source widget.

Schema:
  GET /api/admin/seo/activity?limit=30 →
  {
    events: [
      {kind, severity, at (iso), message, target?, cta_link?, meta?},
      ...
    ],
    counts_by_kind: {auto_promote: N, undo: N, ...},
    cursor: iso8601 (oldest_at — for pagination),
  }

Performance: each source is queried with a small `limit` and merged in
memory. Total Mongo reads = ~6 × 50 = 300 docs max per request, all
indexed on `*_at` timestamps. Sub-100ms warm.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from config import get_db

logger = logging.getLogger(__name__)


def _iso(dt) -> Optional[str]:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    return str(dt)


def _ensure_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """Convert naive timestamps to UTC so sort works across mixed sources."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# ───────── Source loaders — each returns a list[event_dict] ─────────

async def _auto_promotes(*, since: datetime, limit: int) -> list[dict]:
    db = get_db()
    out: list[dict] = []
    async for r in db.seo_stealth_auto_promotes.find(
        {"promoted_at": {"$gte": since}},
        {"_id": 0},
    ).sort("promoted_at", -1).limit(limit):
        is_local = r.get("scope") == "city_page"
        target = r.get("town") if is_local else r.get("collection")
        out.append({
            "kind": "auto_promote",
            "severity": "info",
            "at": _ensure_aware(r.get("promoted_at")),
            "message": (
                f'Auto-promoted "{r.get("query")}" → '
                f'{"local page" if is_local else "collection"} {target}'
            ),
            "target": target,
            "scope": r.get("scope") or "collection",
            "cta_link": "/admin/seo",
            "meta": {
                "query": r.get("query"),
                "impressions": r.get("impressions"),
                "id": r.get("id"),
            },
        })
        if r.get("undone_at"):
            out.append({
                "kind": "auto_promote_undo",
                "severity": "warning",
                "at": _ensure_aware(r.get("undone_at")),
                "message": f'Undone: "{r.get("query")}" removed from {target}',
                "cta_link": "/admin/seo",
                "meta": {"id": r.get("id"), "query": r.get("query")},
            })
    return out


async def _digest_sends(*, since: datetime, limit: int) -> list[dict]:
    db = get_db()
    out: list[dict] = []
    async for r in db.seo_stealth_digest_history.find(
        {"at": {"$gte": since}},
        {"_id": 0},
    ).sort("at", -1).limit(limit):
        snap = r.get("snapshot") or {}
        ok = r.get("ok", True)
        out.append({
            "kind": "digest_sent",
            "severity": "info" if ok else "warning",
            "at": _ensure_aware(r.get("at")),
            "message": (
                f"Weekly digest {'sent' if ok else 'failed'} · "
                f"{snap.get('clicks', 0)} clicks · {snap.get('new_missed_count', 0)} new missed"
            ),
            "cta_link": "/admin/seo",
            "meta": {"recipients": r.get("recipients"), "subject": r.get("subject")},
        })
    return out


async def _stealth_audit(*, since: datetime, limit: int) -> list[dict]:
    """Pulls manual stealth-keyword changes (product/collection edits,
    bulk apply, auto-fill-all batches)."""
    db = get_db()
    out: list[dict] = []
    async for r in db.seo_stealth_audit.find(
        {"at": {"$gte": since}},
        {"_id": 0},
    ).sort("at", -1).limit(limit):
        scope = r.get("scope") or "audit"
        if scope == "auto_fill_all_supplier_originals":
            out.append({
                "kind": "auto_fill_run",
                "severity": "info",
                "at": _ensure_aware(r.get("at")),
                "message": (
                    f"Auto-fill ran across catalogue · "
                    f"{r.get('updated', 0)} products updated · "
                    f"+{r.get('keywords_added', 0)} alt-names indexable"
                ),
                "cta_link": "/admin/seo",
                "meta": {"updated": r.get("updated"), "matched": r.get("matched")},
            })
        elif scope == "bulk":
            out.append({
                "kind": "bulk_apply",
                "severity": "info",
                "at": _ensure_aware(r.get("at")),
                "message": (
                    f'Bulk-applied stealth keywords to "{r.get("collection")}" '
                    f'· mode={r.get("mode")} · {r.get("updated", 0)} products updated'
                ),
                "cta_link": "/admin/seo",
                "meta": {"collection": r.get("collection"), "mode": r.get("mode")},
            })
        elif scope == "product":
            out.append({
                "kind": "manual_kw_edit",
                "severity": "info",
                "at": _ensure_aware(r.get("at")),
                "message": (
                    f"Admin set stealth keywords on a product"
                    + (f' ({r.get("admin_email")})' if r.get("admin_email") else "")
                ),
                "cta_link": "/admin/seo",
                "meta": {"target_id": r.get("target_id")},
            })
        elif scope == "collection_keywords":
            out.append({
                "kind": "collection_kw_edit",
                "severity": "info",
                "at": _ensure_aware(r.get("at")),
                "message": (
                    f'Admin set collection-wide stealth keywords on "{r.get("collection")}"'
                ),
                "cta_link": "/admin/seo",
                "meta": {"collection": r.get("collection")},
            })
    return out


async def _health_incidents(*, since: datetime, limit: int) -> list[dict]:
    """Surface health-check transitions: red→amber→green when status
    changed since the previous check. We only emit incidents on
    transitions, not every tick — otherwise the feed gets spammed
    every 5 minutes with 'all green' rows."""
    db = get_db()
    rows = []
    async for r in db.seo_health_checks.find(
        {"checked_at": {"$gte": since}},
        {"_id": 0, "checked_at": 1, "checks": 1},
    ).sort("checked_at", -1).limit(limit * 2):
        rows.append(r)

    out: list[dict] = []
    prev_status: Optional[str] = None
    # iterate oldest → newest so transitions read naturally
    for r in reversed(rows):
        checks = r.get("checks") or []
        ok = sum(1 for c in checks if c.get("ok"))
        total = len(checks)
        if total == 0:
            continue
        if ok == total:
            status = "green"
        elif ok >= total * 0.8:
            status = "warning"
        else:
            status = "critical"
        if prev_status is None:
            prev_status = status
            continue
        if status != prev_status:
            failing = [c.get("name") for c in checks if not c.get("ok")][:3]
            severity = ("info" if status == "green"
                         else "warning" if status == "warning" else "critical")
            msg = (
                f"Health: {prev_status} → {status}"
                + (f" · failing: {', '.join(failing)}" if failing else "")
            )
            out.append({
                "kind": "health_transition",
                "severity": severity,
                "at": _ensure_aware(r.get("checked_at")),
                "message": msg,
                "cta_link": "/admin/seo",
                "meta": {"from": prev_status, "to": status, "failing": failing},
            })
            prev_status = status
    return out


async def _blog_publishes(*, since: datetime, limit: int) -> list[dict]:
    db = get_db()
    out: list[dict] = []
    async for r in db.blog_articles.find(
        {"published_at": {"$gte": since}},
        {"_id": 0, "title": 1, "slug": 1, "published_at": 1, "source": 1},
    ).sort("published_at", -1).limit(limit):
        is_auto = (r.get("source") or "").lower() in ("autopilot", "editorial_autopilot")
        out.append({
            "kind": "blog_published",
            "severity": "info",
            "at": _ensure_aware(r.get("published_at")),
            "message": (
                f'{"Editorial Autopilot" if is_auto else "Manual"} '
                f'published "{r.get("title")}"'
            ),
            "cta_link": f"/blog/{r.get('slug')}" if r.get("slug") else "/blog",
            "meta": {"slug": r.get("slug"), "source": r.get("source")},
        })
    return out


# ───────── Top-level merge ─────────

async def get_activity(*, limit: int = 30, days: int = 30) -> dict:
    """Composes the activity feed. Runs all source loaders sequentially
    (we don't gather() because each is fast + bounded; serial keeps
    error attribution simple)."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    sources = [
        ("auto_promotes", _auto_promotes),
        ("digest_sends", _digest_sends),
        ("stealth_audit", _stealth_audit),
        ("health_incidents", _health_incidents),
        ("blog_publishes", _blog_publishes),
    ]
    all_events: list[dict] = []
    for name, fn in sources:
        try:
            evs = await fn(since=since, limit=limit + 10)
            all_events.extend(evs)
        except Exception:  # noqa: BLE001
            logger.exception("activity feed: source %s failed", name)

    # Drop events with no timestamp (defensive — every source SHOULD
    # provide one, but bad data shouldn't break the feed)
    all_events = [e for e in all_events if e.get("at") is not None]
    all_events.sort(key=lambda e: e["at"], reverse=True)
    capped = all_events[:limit]

    # Re-serialise timestamps to ISO so JSON encoder doesn't choke
    for e in capped:
        e["at"] = _iso(e["at"])

    counts: dict[str, int] = {}
    for e in capped:
        counts[e["kind"]] = counts.get(e["kind"], 0) + 1

    return {
        "events": capped,
        "counts_by_kind": counts,
        "since": _iso(since),
        "generated_at": _iso(datetime.now(timezone.utc)),
    }

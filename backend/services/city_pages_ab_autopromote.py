"""
Daily auto-promotion of A/B winners on AI City Landing Pages.

Goal
----
Once an A/B test on a city landing page has gathered enough data, the
machine should pick the winner and promote it without admin clicks. This
closes the last manual step in the SEO factory — generate → score →
auto-approve → A/B test → AUTO-PROMOTE.

Promotion rules (admin-tunable)
-------------------------------
* Test must have run for ≥ `min_days` (default 14).
* BOTH variants must have impressions ≥ `min_impressions` (default 200).
* Winner = variant with higher click-through rate (clicks / impressions).
* Tiebreaker: higher confidence_score from the deterministic checklist.
* Final tiebreaker: variant A (incumbent stays).

When a winner is picked, the row's primary body/meta is overwritten by
the winner (if B), counters + variant_b are unset, `ab_winner` and
`ab_won_at` are stamped, and a Telegram ping fires under the
`city_page_ab_winner` event toggle.

Settings doc lives in `website_settings._id="city_pages_ab_autopromote"`
mirroring the autogen / quality-digest patterns.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from config import get_db
from services.telegram_notify import notify_event

logger = logging.getLogger(__name__)

SETTINGS_ID = "city_pages_ab_autopromote"

DEFAULT_SETTINGS = {
    "enabled": False,            # Opt-in: admin must turn this on.
    "min_impressions": 200,      # Per-variant impression floor before we judge.
    "min_days": 14,              # Calendar days the test must have run.
    "hour_utc": 5,               # 05:00 UTC (after 04:00 autogen, before 06:15 Ahrefs).
    "last_run_date": None,
    "last_run_promoted": 0,
    "last_run_message": None,
}


async def _load_settings(db) -> dict:
    doc = await db.website_settings.find_one({"_id": SETTINGS_ID}, {"_id": 0}) or {}
    return {**DEFAULT_SETTINGS, **doc}


async def _save_settings(db, patch: dict) -> None:
    await db.website_settings.update_one(
        {"_id": SETTINGS_ID},
        {"$set": {**patch, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )


def _ctr(impressions: int, clicks: int) -> float:
    return (clicks / impressions) if impressions > 0 else 0.0


def _decide_winner(row: dict) -> tuple[str, dict]:
    """Pure helper — returns (winner, decision_metadata) without touching
    the DB. Split out for unit-testability."""
    a_imp = int(row.get("variant_a_impressions") or 0)
    b_imp = int(row.get("variant_b_impressions") or 0)
    a_clk = int(row.get("variant_a_cta_clicks") or 0)
    b_clk = int(row.get("variant_b_cta_clicks") or 0)
    a_ctr = _ctr(a_imp, a_clk)
    b_ctr = _ctr(b_imp, b_clk)
    a_score = int(row.get("confidence_score") or 0)
    b_score = int((row.get("variant_b") or {}).get("confidence_score") or 0)

    # Primary: higher CTR wins.
    if b_ctr > a_ctr:
        winner = "b"
    elif a_ctr > b_ctr:
        winner = "a"
    # Tied CTR (often both 0%) → fall back to confidence score.
    elif b_score > a_score:
        winner = "b"
    elif a_score > b_score:
        winner = "a"
    else:
        # Final tie → keep the incumbent (variant A).
        winner = "a"

    return winner, {
        "a_impressions": a_imp, "b_impressions": b_imp,
        "a_clicks": a_clk, "b_clicks": b_clk,
        "a_ctr": round(100 * a_ctr, 2), "b_ctr": round(100 * b_ctr, 2),
        "a_score": a_score, "b_score": b_score,
    }


def _is_eligible(row: dict, *, min_impressions: int, min_days: int, now_utc: datetime) -> bool:
    """All gates a row must pass before we judge a winner."""
    if not row.get("variant_b"):
        return False
    a_imp = int(row.get("variant_a_impressions") or 0)
    b_imp = int(row.get("variant_b_impressions") or 0)
    if a_imp < min_impressions or b_imp < min_impressions:
        return False
    started = row.get("ab_started_at")
    if not isinstance(started, datetime):
        return False
    age_days = (now_utc - started.replace(tzinfo=timezone.utc) if started.tzinfo is None else now_utc - started).days
    return age_days >= min_days


async def _promote_one(db, row: dict, winner: str, decision: dict) -> None:
    """Apply promote-variant semantics directly. Mirrors the manual
    /promote-variant endpoint so behaviour stays identical."""
    set_payload: dict = {
        "updated_at": datetime.now(timezone.utc),
        "ab_winner": winner,
        "ab_won_at": datetime.now(timezone.utc),
        "ab_won_decision": decision,
    }
    unset_payload: dict = {
        "variant_b": "",
        "variant_a_impressions": "",
        "variant_b_impressions": "",
        "variant_a_cta_clicks": "",
        "variant_b_cta_clicks": "",
        "ab_started_at": "",
    }
    if winner == "b":
        vb = row["variant_b"] or {}
        set_payload["body_md"] = vb.get("body_md")
        set_payload["meta_title"] = vb.get("meta_title")
        set_payload["meta_description"] = vb.get("meta_description")
        set_payload["confidence_score"] = vb.get("confidence_score")
        set_payload["confidence_failed"] = vb.get("confidence_failed")

    await db.city_landing_pages.update_one(
        {"slug": row["slug"]},
        {"$set": set_payload, "$unset": unset_payload},
    )


async def run_ab_autopromote_tick(force: bool = False) -> dict:
    """Hourly probe — only judges and promotes when:
       * settings.enabled is True (opt-in)
       * current UTC hour matches settings.hour_utc (or `force`)
       * we haven't run yet today

    Returns a small status dict for logging / manual-trigger UIs."""
    db = get_db()
    settings = await _load_settings(db)

    if not settings.get("enabled", False) and not force:
        return {"skipped": True, "reason": "disabled"}

    now_utc = datetime.now(timezone.utc)
    today = now_utc.date().isoformat()

    if not force:
        if now_utc.hour != int(settings.get("hour_utc", 5)):
            return {"skipped": True, "reason": "wrong_hour"}
        if settings.get("last_run_date") == today:
            return {"skipped": True, "reason": "already_ran_today"}

    candidates = await db.city_landing_pages.find(
        {"variant_b": {"$exists": True, "$ne": None}}, {"_id": 0}
    ).to_list(2000)

    promoted = 0
    promotions: list[dict] = []
    min_imp = int(settings.get("min_impressions", 200))
    min_days = int(settings.get("min_days", 14))

    for row in candidates:
        if not _is_eligible(row, min_impressions=min_imp, min_days=min_days, now_utc=now_utc):
            continue
        winner, decision = _decide_winner(row)
        await _promote_one(db, row, winner, decision)
        promoted += 1
        promotions.append({"slug": row["slug"], "winner": winner, **decision})

        # Log to the autopilot trail for the daily digest. Idempotent —
        # re-runs after an outage don't double-log because `_is_eligible`
        # filters out already-promoted rows on the next tick.
        try:
            from services.seo_autonomous import on_variant_promoted
            await on_variant_promoted(row["slug"], winner)
        except Exception:
            logger.exception("[seo-autopilot] log variant promotion failed")

        # Telegram ping per promotion. Dedupe on the slug so re-runs after
        # an outage don't double-fire.
        try:
            ctr_line = f"A {decision['a_ctr']}% vs B {decision['b_ctr']}%"
            await notify_event(
                "city_page_ab_winner",
                (
                    f"🏆 <b>A/B winner picked</b> for "
                    f"<code>{row['slug']}</code>\n"
                    f"Winner: <b>Variant {winner.upper()}</b>\n"
                    f"CTR: {ctr_line}\n"
                    f"{decision['a_impressions']} vs {decision['b_impressions']} impressions"
                ),
                dedupe_key=f"ab-winner-{row['slug']}",
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(f"telegram ping for ab-winner failed: {e}")

    await _save_settings(db, {
        "last_run_date": today,
        "last_run_promoted": promoted,
        "last_run_message": (
            f"promoted {promoted} winner{'s' if promoted != 1 else ''} "
            f"from {len(candidates)} candidate{'s' if len(candidates) != 1 else ''}"
        ),
    })

    logger.info(
        f"city-pages ab-autopromote tick: candidates={len(candidates)} promoted={promoted}"
    )
    return {
        "ran": True,
        "candidates": len(candidates),
        "promoted": promoted,
        "promotions": promotions,
    }

"""
AI-generated UK city/town landing pages for tilestation.co.uk.

Why: high-intent local searches like "tile shop maidstone" or "kitchen
tiles dartford" have low keyword difficulty but no dedicated landing
page on the site. Auto-generating one well-written, locally-targeted
page per town fills that gap — Ahrefs typically shows 40-80 of these
indexed within 30 days.

Pipeline:
  1. Curated list of Kent + South-East UK towns (33 entries)
  2. For each town × intent (5 intents), build a `city_landing_pages`
     queue entry with status=pending
  3. Admin-trigger or scheduled batch generates 600-800 word AI copy
     using the Emergent LLM key
  4. Pages live at /tiles-{town-slug} once approved

Stays out of /api auth-free routes — admin-gated everywhere.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from config import get_db
from services import get_current_user
from business_config.showrooms import get_nearest_showroom, all_open_showrooms

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/seo/city-pages", tags=["SEO City Pages"])

# Special pseudo-town slug for nationwide (UK-wide) intent pages.
NATIONWIDE_TOWN = {"name": "UK", "slug": "uk", "county": "United Kingdom", "tier": 1}


# ─── Curated catchment list ────────────────────────────────────────────
# Kent first (your physical showrooms), then SE-England commuter belt.
TOWNS: list[dict] = [
    # Kent — primary catchment
    {"name": "Gravesend", "slug": "gravesend", "county": "Kent", "tier": 1},
    {"name": "Dartford", "slug": "dartford", "county": "Kent", "tier": 1},
    {"name": "Maidstone", "slug": "maidstone", "county": "Kent", "tier": 1},
    {"name": "Sevenoaks", "slug": "sevenoaks", "county": "Kent", "tier": 1},
    {"name": "Tunbridge Wells", "slug": "tunbridge-wells", "county": "Kent", "tier": 1},
    {"name": "Chatham", "slug": "chatham", "county": "Kent", "tier": 1},
    {"name": "Rochester", "slug": "rochester", "county": "Kent", "tier": 1},
    {"name": "Bromley", "slug": "bromley", "county": "Greater London", "tier": 1},
    {"name": "Sittingbourne", "slug": "sittingbourne", "county": "Kent", "tier": 2},
    {"name": "Ashford", "slug": "ashford", "county": "Kent", "tier": 2},
    {"name": "Folkestone", "slug": "folkestone", "county": "Kent", "tier": 2},
    {"name": "Canterbury", "slug": "canterbury", "county": "Kent", "tier": 2},
    {"name": "Dover", "slug": "dover", "county": "Kent", "tier": 2},
    {"name": "Margate", "slug": "margate", "county": "Kent", "tier": 2},
    {"name": "Whitstable", "slug": "whitstable", "county": "Kent", "tier": 2},
    {"name": "Tonbridge", "slug": "tonbridge", "county": "Kent", "tier": 2},
    # London + commuter belt
    {"name": "London", "slug": "london", "county": "Greater London", "tier": 1},
    {"name": "Croydon", "slug": "croydon", "county": "Greater London", "tier": 2},
    {"name": "Bexley", "slug": "bexley", "county": "Greater London", "tier": 2},
    {"name": "Greenwich", "slug": "greenwich", "county": "Greater London", "tier": 2},
    {"name": "Lewisham", "slug": "lewisham", "county": "Greater London", "tier": 2},
    # Essex (across the Dartford crossing)
    {"name": "Grays", "slug": "grays", "county": "Essex", "tier": 2},
    {"name": "Basildon", "slug": "basildon", "county": "Essex", "tier": 2},
    {"name": "Southend-on-Sea", "slug": "southend-on-sea", "county": "Essex", "tier": 2},
    # Surrey (commuter belt)
    {"name": "Guildford", "slug": "guildford", "county": "Surrey", "tier": 3},
    {"name": "Redhill", "slug": "redhill", "county": "Surrey", "tier": 3},
    {"name": "Reigate", "slug": "reigate", "county": "Surrey", "tier": 3},
    # East/West Sussex
    {"name": "Brighton", "slug": "brighton", "county": "East Sussex", "tier": 3},
    {"name": "Eastbourne", "slug": "eastbourne", "county": "East Sussex", "tier": 3},
    {"name": "Hastings", "slug": "hastings", "county": "East Sussex", "tier": 3},
    # Other South-East
    {"name": "Tilbury", "slug": "tilbury", "county": "Essex", "tier": 3},
    {"name": "Chislehurst", "slug": "chislehurst", "county": "Greater London", "tier": 3},
    {"name": "Orpington", "slug": "orpington", "county": "Greater London", "tier": 2},
]


# Intent variants — each town gets one page per intent that has search
# volume according to typical UK Google trends.
INTENTS: list[dict] = [
    {"slug": "tile-shop", "phrase": "tile shop", "h1": "Tile Shop in {town}, {county}"},
    {"slug": "kitchen-tiles", "phrase": "kitchen tiles", "h1": "Kitchen Tiles {town} — Wall & Floor"},
    {"slug": "bathroom-tiles", "phrase": "bathroom tiles", "h1": "Bathroom Tiles {town} — Premium Range"},
    {"slug": "porcelain-tiles", "phrase": "porcelain tiles", "h1": "Porcelain Tiles {town} — Floor & Wall"},
    {"slug": "tile-suppliers", "phrase": "tile suppliers", "h1": "Tile Suppliers {town}, {county}"},
]


# Nationwide / online-delivery intents — only seeded against the special
# UK pseudo-town. These target high-volume non-geo phrases like
# "buy tiles online uk" with no town in the H1.
NATIONWIDE_INTENTS: list[dict] = [
    {"slug": "tiles-online", "phrase": "tiles online", "h1": "Tiles Online — Free UK Delivery"},
    {"slug": "tile-delivery", "phrase": "tile delivery", "h1": "Tile Delivery Across the UK"},
    {"slug": "buy-tiles-online", "phrase": "buy tiles online", "h1": "Buy Tiles Online in the UK"},
]


def _is_admin(user: dict) -> bool:
    return (user or {}).get("role") in {"super_admin", "admin", "manager"}


def _slug(town_slug: str, intent_slug: str) -> str:
    return f"{intent_slug}-{town_slug}"


def _url(town_slug: str, intent_slug: str) -> str:
    return f"/tiles/{_slug(town_slug, intent_slug)}"


async def _ensure_indexes(db) -> None:
    try:
        await db.city_landing_pages.create_index([("slug", 1)], unique=True)
        await db.city_landing_pages.create_index([("status", 1)])
    except Exception as e:  # noqa: BLE001
        logger.debug("city_landing_pages index setup: %s", e)


@router.post("/seed")
async def seed_queue(current_user: dict = Depends(get_current_user)):
    """One-shot seed: creates a `pending` row for every town × intent pair
    that doesn't already exist. Idempotent."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    db = get_db()
    await _ensure_indexes(db)
    created = 0
    skipped = 0
    now = datetime.now(timezone.utc)
    # Per-town × per-local-intent rows
    for town in TOWNS:
        for intent in INTENTS:
            slug = _slug(town["slug"], intent["slug"])
            existing = await db.city_landing_pages.find_one({"slug": slug}, {"_id": 0})
            if existing:
                skipped += 1
                continue
            await db.city_landing_pages.insert_one({
                "slug": slug,
                "town": town["name"],
                "town_slug": town["slug"],
                "county": town["county"],
                "tier": town["tier"],
                "intent_slug": intent["slug"],
                "intent_phrase": intent["phrase"],
                "h1": intent["h1"].format(town=town["name"], county=town["county"]),
                "url": _url(town["slug"], intent["slug"]),
                "status": "pending",
                "body_md": None,
                "meta_title": None,
                "meta_description": None,
                "ai_generated_at": None,
                "approved_at": None,
                "approved_by": None,
                "created_at": now,
            })
            created += 1
    # Nationwide / no-town intent rows (single set)
    for intent in NATIONWIDE_INTENTS:
        slug = _slug(NATIONWIDE_TOWN["slug"], intent["slug"])
        existing = await db.city_landing_pages.find_one({"slug": slug}, {"_id": 0})
        if existing:
            skipped += 1
            continue
        await db.city_landing_pages.insert_one({
            "slug": slug,
            "town": NATIONWIDE_TOWN["name"],
            "town_slug": NATIONWIDE_TOWN["slug"],
            "county": NATIONWIDE_TOWN["county"],
            "tier": NATIONWIDE_TOWN["tier"],
            "intent_slug": intent["slug"],
            "intent_phrase": intent["phrase"],
            "h1": intent["h1"],
            "url": _url(NATIONWIDE_TOWN["slug"], intent["slug"]),
            "status": "pending",
            "scope": "nationwide",
            "body_md": None,
            "meta_title": None,
            "meta_description": None,
            "ai_generated_at": None,
            "approved_at": None,
            "approved_by": None,
            "created_at": now,
        })
        created += 1
    return {"ok": True, "created": created, "skipped": skipped, "total": created + skipped}


@router.post("/refresh-pending")
async def refresh_pending(current_user: dict = Depends(get_current_user)):
    """Wipe AI body / meta on every row that's still `pending` or
    `generated` (i.e. NOT yet approved) and clear the cached generation
    timestamp, so the next /generate call rebuilds them with the current
    real-showroom prompt. Approved rows are left untouched."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    db = get_db()
    res = await db.city_landing_pages.update_many(
        {"status": {"$in": ["pending", "generated"]}},
        {"$set": {
            "status": "pending",
            "body_md": None,
            "meta_title": None,
            "meta_description": None,
            "ai_generated_at": None,
            "updated_at": datetime.now(timezone.utc),
        }},
    )
    return {"ok": True, "reset": res.modified_count}


@router.get("")
async def list_queue(
    status: str = Query(default="pending"),
    limit: int = Query(default=200, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
):
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    db = get_db()
    await _ensure_indexes(db)
    query = {} if status == "all" else {"status": status}
    rows = await db.city_landing_pages.find(query, {"_id": 0}).sort("tier", 1).limit(limit).to_list(limit)
    counts = {}
    for s in ("pending", "generated", "approved", "skipped"):
        counts[s] = await db.city_landing_pages.count_documents({"status": s})
    return {"rows": rows, "counts": counts}


class GenerateRequest(BaseModel):
    slug: str = Field(..., min_length=4, max_length=100)


class GenerateBatchRequest(BaseModel):
    slugs: Optional[list[str]] = None  # explicit list, OR
    limit: int = Field(default=10, ge=1, le=25)  # auto-pick N pending rows
    only_pending: bool = True  # if False, also re-generate `generated` rows


def _build_prompt(row: dict) -> str:
    """Build the LLM prompt for a single queue row, injecting real
    showroom data either for the local town's nearest open showroom or
    for every open showroom on a nationwide page."""
    is_nationwide = (row.get("scope") == "nationwide") or row.get("town_slug") == "uk"
    if is_nationwide:
        open_srs = all_open_showrooms()
        showroom_lines = "\n".join(
            f"  • {sr['name']} — {sr['address']}, {sr['postcode']} — {sr['phone']} — {sr['hours']}"
            for sr in open_srs
        )
        return (
            f"Write a UK-English landing page for Tile Station — a UK tile retailer with "
            f"physical showrooms in Kent and London — targeting the search phrase "
            f"“{row['intent_phrase']} uk”.\n\n"
            f"OUR REAL SHOWROOMS (use them by name and tell readers we deliver UK-wide from these):\n"
            f"{showroom_lines}\n\n"
            f"REQUIRED STRUCTURE:\n"
            f"  • H1 (one line, exactly): {row['h1']}\n"
            f"  • Intro paragraph (~70 words) — friendly, mention nationwide UK delivery and "
            f"the fact that we run real showrooms (not just a faceless e-commerce site).\n"
            f"  • H2: Why UK customers choose Tile Station\n"
            f"  • Bulleted list (4-6 items) — concrete benefits (range, quality, trade pricing, "
            f"sample service, advice from professional fitters, free delivery thresholds).\n"
            f"  • H2: Order online, visit a showroom, or call us\n"
            f"  • Short paragraph (~80 words) recommending sample orders before committing to a "
            f"full pack, plus how delivery works (next-day / pallet for full orders).\n"
            f"  • H2: Visit a Tile Station showroom\n"
            f"  • For each open showroom, a short sub-section listing its address, postcode, "
            f"phone and opening hours — exactly as supplied above. Do NOT invent any details.\n\n"
            f"VOICE: warm, expert, practical. UK-English spelling (colour, organise, kerb). "
            f"No emoji. No fluff. Specific. ~700-900 words total. Output as Markdown.\n\n"
            f"After the body, on a new line, output exactly:\n"
            f"  META_TITLE: <50-60 chars including 'tiles' and 'UK'>\n"
            f"  META_DESCRIPTION: <140-155 chars>"
        )
    sr = get_nearest_showroom(row.get("town_slug", ""))
    return (
        f"Write a UK-English landing page for Tile Station — a tile retailer with physical "
        f"showrooms in Kent and London — targeting the search phrase "
        f"“{row['intent_phrase']} {row['town']}”.\n\n"
        f"NEAREST SHOWROOM TO {row['town'].upper()} (use these EXACT details, do not invent):\n"
        f"  • Name: {sr['name']}\n"
        f"  • Address: {sr['address']}\n"
        f"  • Postcode: {sr['postcode']}\n"
        f"  • Phone: {sr['phone']}\n"
        f"  • Email: {sr['email']}\n"
        f"  • Opening hours: {sr['hours']}\n\n"
        f"REQUIRED STRUCTURE:\n"
        f"  • H1 (one line, exactly): {row['h1']}\n"
        f"  • Intro paragraph (~70 words) — friendly, mention {row['town']} by name twice, "
        f"reference Kent / South-East England context. Mention free local delivery and "
        f"showroom visits welcomed.\n"
        f"  • H2: Why customers in {row['town']} choose Tile Station\n"
        f"  • Bulleted list (4-6 items) — concrete benefits (range, quality, trade pricing, "
        f"sample service, advice from professional fitters)\n"
        f"  • H2: Popular {row['intent_phrase']} for {row['town']} homes\n"
        f"  • Short paragraph (~80 words) about which styles/finishes are popular in the area "
        f"(e.g. period homes need traditional, new-builds prefer minimal large-format).\n"
        f"  • H2: Visit our nearest showroom or order online\n"
        f"  • Closing paragraph with practical CTA — give the EXACT showroom address, postcode "
        f"and phone above, mention typical drive distance from {row['town']}, free returns "
        f"and sample boxes. Do NOT invent any address or phone — use only what is supplied.\n\n"
        f"VOICE: warm, expert, practical. UK-English spelling (colour, organise, kerb). "
        f"No emoji. No fluff. Specific. ~600-800 words total. Output as Markdown.\n\n"
        f"After the body, on a new line, output exactly:\n"
        f"  META_TITLE: <50-60 chars including {row['town']}>\n"
        f"  META_DESCRIPTION: <140-155 chars>"
    )


async def _generate_for_row(db, row: dict, api_key: str) -> tuple[bool, str]:
    """Run the LLM once for `row` and persist result. Returns (ok, msg).

    Also scores the output against a deterministic checklist and stores
    the score + per-check breakdown on the row so the admin UI can show
    a confidence badge (and the autogen tick can optionally auto-approve
    when score ≥ threshold)."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage  # type: ignore
    import uuid as _uuid
    from services.city_pages_confidence import score_page  # noqa: PLC0415

    try:
        chat = LlmChat(
            api_key=api_key,
            session_id=_uuid.uuid4().hex,
            system_message="You are an expert UK SEO copywriter for a tile retailer. Write to rank, write to convert.",
        )
        chat.with_model("anthropic", "claude-haiku-4-5")
        result = await chat.send_message(UserMessage(text=_build_prompt(row)))
    except Exception as e:  # noqa: BLE001
        logger.warning("city-page LLM call failed for %s: %s", row.get("slug"), e)
        return False, f"LLM call failed: {e}"

    body, meta_title, meta_description = _parse_llm_output(result or "")
    scoring = score_page(row, body, meta_title, meta_description)
    now = datetime.now(timezone.utc)
    await db.city_landing_pages.update_one(
        {"slug": row["slug"]},
        {"$set": {
            "status": "generated",
            "body_md": body,
            "meta_title": meta_title,
            "meta_description": meta_description,
            "ai_generated_at": now,
            "updated_at": now,
            "confidence_score": scoring["score"],
            "confidence_checks": scoring["checks"],
            "confidence_failed": scoring["failed"],
        }},
    )
    return True, (body or "")[:300]


@router.post("/generate")
async def generate_one(payload: GenerateRequest, current_user: dict = Depends(get_current_user)):
    """Generate AI copy for a single page using the Emergent LLM key.
    Body lands as `generated`, ready for admin review/approval."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    db = get_db()
    row = await db.city_landing_pages.find_one({"slug": payload.slug}, {"_id": 0})
    if not row:
        raise HTTPException(status_code=404, detail="Page not in queue")

    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="EMERGENT_LLM_KEY not configured")

    ok, msg = await _generate_for_row(db, row, api_key)
    if not ok:
        raise HTTPException(status_code=500, detail=msg)
    return {"ok": True, "slug": payload.slug, "preview": msg}


@router.post("/generate-batch")
async def generate_batch(payload: GenerateBatchRequest, current_user: dict = Depends(get_current_user)):
    """Generate AI copy for up to 25 pages in one call.

    Either pass an explicit list of slugs OR omit and we'll auto-pick the
    next `limit` rows that are still `pending`. Useful for the admin UI's
    "Batch generate next 10" button so you don't click 165 times.

    Status reporting is per-row so a single LLM hiccup doesn't fail the
    whole batch.
    """
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="EMERGENT_LLM_KEY not configured")

    db = get_db()
    if payload.slugs:
        cursor = db.city_landing_pages.find({"slug": {"$in": payload.slugs}}, {"_id": 0})
        rows = await cursor.to_list(len(payload.slugs))
    else:
        status_filter = {"status": "pending"} if payload.only_pending else {
            "status": {"$in": ["pending", "generated"]}
        }
        rows = await db.city_landing_pages.find(status_filter, {"_id": 0}) \
            .sort("tier", 1).limit(payload.limit).to_list(payload.limit)

    results: list[dict] = []
    succeeded = 0
    failed = 0
    for row in rows:
        ok, msg = await _generate_for_row(db, row, api_key)
        results.append({"slug": row["slug"], "ok": ok, "message": msg if not ok else "generated"})
        if ok:
            succeeded += 1
        else:
            failed += 1

    return {
        "ok": True,
        "attempted": len(rows),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    }


def _parse_llm_output(raw: str) -> tuple[str, Optional[str], Optional[str]]:
    """Split the model's output into body + meta_title + meta_description."""
    body = raw
    meta_title = None
    meta_description = None
    for line in raw.splitlines():
        if line.lower().startswith("meta_title:"):
            meta_title = line.split(":", 1)[1].strip()
        elif line.lower().startswith("meta_description:"):
            meta_description = line.split(":", 1)[1].strip()
    if meta_title or meta_description:
        # Strip the meta lines out of the body.
        out_lines = [ln for ln in raw.splitlines()
                     if not ln.lower().startswith(("meta_title:", "meta_description:"))]
        body = "\n".join(out_lines).strip()
    return body, meta_title, meta_description


class ApproveRequest(BaseModel):
    slug: str
    body_md: Optional[str] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None


@router.post("/approve")
async def approve(payload: ApproveRequest, current_user: dict = Depends(get_current_user)):
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    db = get_db()
    update = {
        "status": "approved",
        "approved_at": datetime.now(timezone.utc),
        "approved_by": (current_user or {}).get("email"),
    }
    if payload.body_md is not None:
        update["body_md"] = payload.body_md
    if payload.meta_title is not None:
        update["meta_title"] = payload.meta_title
    if payload.meta_description is not None:
        update["meta_description"] = payload.meta_description
    res = await db.city_landing_pages.update_one({"slug": payload.slug}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Page not in queue")
    # Fire the autonomous SEO hook — re-submits sitemap to GSC + logs
    # for the daily digest. Fail-soft so it never blocks the approve.
    try:
        from services.seo_autonomous import on_city_page_published
        await on_city_page_published(payload.slug)
    except Exception:
        logger.exception("[autonomous-seo] on_city_page_published failed")
    return {"ok": True}


# ─── Daily auto-generator settings ─────────────────────────────────────


class AutogenSettings(BaseModel):
    enabled: Optional[bool] = None
    daily_count: Optional[int] = Field(default=None, ge=1, le=25)
    hour_utc: Optional[int] = Field(default=None, ge=0, le=23)
    auto_approve_enabled: Optional[bool] = None
    auto_approve_threshold: Optional[int] = Field(default=None, ge=50, le=100)


@router.get("/autogen")
async def autogen_get(current_user: dict = Depends(get_current_user)):
    """Return current auto-generator settings + last-run summary so the
    admin UI can render the toggle row + "last ran X / Y today" chip."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    from services.city_pages_autogen import _load_settings  # noqa: PLC0415
    db = get_db()
    settings = await _load_settings(db)
    pending = await db.city_landing_pages.count_documents({"status": "pending"})
    return {**settings, "pending_count": pending}


@router.put("/autogen")
async def autogen_put(payload: AutogenSettings, current_user: dict = Depends(get_current_user)):
    """Update enabled / daily_count / hour_utc. Only the fields you send
    are touched; everything else stays as-is."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    from services.city_pages_autogen import _load_settings, _save_settings  # noqa: PLC0415
    db = get_db()
    patch = {k: v for k, v in payload.model_dump().items() if v is not None}
    if patch:
        await _save_settings(db, patch)
    settings = await _load_settings(db)
    return settings


@router.post("/autogen/run-now")
async def autogen_run_now(current_user: dict = Depends(get_current_user)):
    """Force-trigger the daily tick right now (ignoring hour_gate). Useful
    for testing or to drain the queue on demand."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    from services.city_pages_autogen import run_city_pages_autogen_tick  # noqa: PLC0415
    res = await run_city_pages_autogen_tick(force=True)
    return res


@router.post("/rescore")
async def rescore_generated(current_user: dict = Depends(get_current_user)):
    """Re-run the deterministic confidence scoring against every page
    that's currently in `generated` status. Useful after changing the
    score rubric or when we've added legacy rows that don't yet have a
    score. Does NOT re-call the LLM."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    from services.city_pages_confidence import score_page  # noqa: PLC0415
    db = get_db()
    rows = await db.city_landing_pages.find({"status": "generated"}, {"_id": 0}).to_list(2000)
    updated = 0
    for row in rows:
        scoring = score_page(row, row.get("body_md"), row.get("meta_title"), row.get("meta_description"))
        await db.city_landing_pages.update_one(
            {"slug": row["slug"]},
            {"$set": {
                "confidence_score": scoring["score"],
                "confidence_checks": scoring["checks"],
                "confidence_failed": scoring["failed"],
            }},
        )
        updated += 1
    return {"ok": True, "scored": updated}


@router.post("/quality-digest/send-now")
async def quality_digest_send_now(current_user: dict = Depends(get_current_user)):
    """Force-send the weekly SEO quality digest right now, bypassing the
    'already sent this iso week' guard. Used by the admin's manual
    trigger button so they can preview the email or recover from a
    missed cron."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    from services.seo_quality_digest import run_seo_quality_digest_tick  # noqa: PLC0415
    res = await run_seo_quality_digest_tick(force=True)
    return res


# ─── A/B variant testing ───────────────────────────────────────────────


def _build_prompt_variant_b(row: dict) -> str:
    """Variant B prompt — same SEO target but a deliberately different
    *angle* so the two pages compete on Google for the same query.

    Variant A's prompt focuses on "popular tile styles for {town} homes".
    Variant B pivots to a "design-ideas / room-transformation" angle —
    same showroom data, same town, same word count, totally different
    hook. Google rewards angle diversity within a brand's site."""
    is_nationwide = (row.get("scope") == "nationwide") or row.get("town_slug") == "uk"
    if is_nationwide:
        open_srs = all_open_showrooms()
        showroom_lines = "\n".join(
            f"  • {sr['name']} — {sr['address']}, {sr['postcode']} — {sr['phone']} — {sr['hours']}"
            for sr in open_srs
        )
        return (
            f"Write an alternative UK-English landing page (Variant B) for Tile Station — same "
            f"target phrase “{row['intent_phrase']} uk” but a different angle from Variant A. "
            f"Variant A was about why-choose-us / range. Variant B should focus on PROJECT "
            f"INSPIRATION: how to plan a tiling project (kitchen splashbacks, bathroom feature "
            f"walls, hallway floors), what to budget, how long delivery takes, and how to ask "
            f"the showroom team for free design advice.\n\n"
            f"OUR REAL SHOWROOMS (use them by name and tell readers we deliver UK-wide):\n"
            f"{showroom_lines}\n\n"
            f"REQUIRED STRUCTURE:\n"
            f"  • H1 (one line, exactly): {row['h1']}\n"
            f"  • Intro paragraph (~70 words) — friendly, mention UK delivery, frame the page "
            f"around 'planning your tiling project from inspiration to install'.\n"
            f"  • H2: Pick a project type — kitchen, bathroom, hallway, outdoor\n"
            f"  • Numbered list (4 items) — one tip per project type with concrete tile sizes/finishes\n"
            f"  • H2: Budget &amp; sample-first checklist\n"
            f"  • Short paragraph (~80 words) on £/m² ranges and the importance of ordering samples.\n"
            f"  • H2: Talk to a Tile Station showroom\n"
            f"  • For each open showroom, address + postcode + phone + hours — exactly as supplied.\n\n"
            f"VOICE: warm, practical, 'we've seen 1000s of projects'. UK English. No emoji. "
            f"~700-900 words. Output as Markdown.\n\n"
            f"After the body, on a new line, output exactly:\n"
            f"  META_TITLE: <50-60 chars including 'tiles' and 'UK'>\n"
            f"  META_DESCRIPTION: <140-155 chars>"
        )
    sr = get_nearest_showroom(row.get("town_slug", ""))
    return (
        f"Write an alternative UK-English landing page (Variant B) for Tile Station, targeting "
        f"the same search phrase “{row['intent_phrase']} {row['town']}” — but a different angle "
        f"from Variant A. Variant A focused on popular tile styles. Variant B should focus on "
        f"DESIGN IDEAS: room-transformation case studies, before-and-after thinking, how local "
        f"{row['town']} homeowners typically plan a tiling refresh, and the free design-advice "
        f"service at our showroom.\n\n"
        f"NEAREST SHOWROOM TO {row['town'].upper()} (use these EXACT details, do not invent):\n"
        f"  • Name: {sr['name']}\n"
        f"  • Address: {sr['address']}\n"
        f"  • Postcode: {sr['postcode']}\n"
        f"  • Phone: {sr['phone']}\n"
        f"  • Email: {sr['email']}\n"
        f"  • Opening hours: {sr['hours']}\n\n"
        f"REQUIRED STRUCTURE:\n"
        f"  • H1 (one line, exactly): {row['h1']}\n"
        f"  • Intro paragraph (~70 words) — friendly, mention {row['town']} by name twice, "
        f"frame this page as 'design inspiration for {row['town']} homes' (not a buy-now sell).\n"
        f"  • H2: Three room transformations {row['town']} customers love\n"
        f"  • Bulleted list (3 items) — one short scene per room (kitchen splashback, bathroom "
        f"feature wall, hallway floor) with specific tile sizes/finishes you'd recommend.\n"
        f"  • H2: How to plan your project from samples to install\n"
        f"  • Short paragraph (~80 words) on the order/sample/install timeline.\n"
        f"  • H2: Talk to our {sr['name'].split('Tile Station ')[-1]} team\n"
        f"  • Closing paragraph with the EXACT showroom address, postcode, phone above. "
        f"Mention free design advice and that visitors from {row['town']} are welcome to walk in.\n\n"
        f"VOICE: warm, design-led, story-flavoured. UK English. No emoji. ~600-800 words. "
        f"Output as Markdown.\n\n"
        f"After the body, on a new line, output exactly:\n"
        f"  META_TITLE: <50-60 chars including {row['town']}>\n"
        f"  META_DESCRIPTION: <140-155 chars>"
    )


class GenerateVariantBRequest(BaseModel):
    slug: str = Field(..., min_length=4, max_length=100)


@router.post("/generate-variant-b")
async def generate_variant_b(payload: GenerateVariantBRequest, current_user: dict = Depends(get_current_user)):
    """Generate a B variant for an existing row using the alternative-angle
    prompt. Stores under `variant_b: {body_md, meta_title,
    meta_description, confidence_score, confidence_failed,
    ai_generated_at}` so the public route can A/B-test it against the
    primary `body_md` (variant A).

    Pre-conditions: the row must already have a primary `body_md` (i.e.
    `status` ∈ {generated, approved}). Generating B on a `pending` row
    doesn't make sense — generate A first.
    """
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    db = get_db()
    row = await db.city_landing_pages.find_one({"slug": payload.slug}, {"_id": 0})
    if not row:
        raise HTTPException(status_code=404, detail="Page not in queue")
    if not row.get("body_md"):
        raise HTTPException(status_code=400, detail="Generate variant A first")

    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="EMERGENT_LLM_KEY not configured")

    from emergentintegrations.llm.chat import LlmChat, UserMessage  # type: ignore
    from services.city_pages_confidence import score_page  # noqa: PLC0415
    import uuid as _uuid

    try:
        chat = LlmChat(
            api_key=api_key,
            session_id=_uuid.uuid4().hex,
            system_message="You are an expert UK SEO copywriter for a tile retailer. Write to rank, write to convert.",
        )
        chat.with_model("anthropic", "claude-haiku-4-5")
        result = await chat.send_message(UserMessage(text=_build_prompt_variant_b(row)))
    except Exception as e:  # noqa: BLE001
        logger.warning("city-page variant-B LLM call failed for %s: %s", row["slug"], e)
        raise HTTPException(status_code=500, detail=f"LLM call failed: {e}")

    body, meta_title, meta_description = _parse_llm_output(result or "")
    scoring = score_page(row, body, meta_title, meta_description)
    now = datetime.now(timezone.utc)
    await db.city_landing_pages.update_one(
        {"slug": payload.slug},
        {"$set": {
            "variant_b": {
                "body_md": body,
                "meta_title": meta_title,
                "meta_description": meta_description,
                "confidence_score": scoring["score"],
                "confidence_failed": scoring["failed"],
                "ai_generated_at": now,
            },
            # Reset A/B counters so we measure the new B fairly.
            "variant_a_impressions": 0,
            "variant_b_impressions": 0,
            "variant_a_cta_clicks": 0,
            "variant_b_cta_clicks": 0,
            "ab_started_at": now,
            "updated_at": now,
        }},
    )
    return {
        "ok": True,
        "slug": payload.slug,
        "variant_b_score": scoring["score"],
        "preview": (body or "")[:300],
    }


@router.get("/ab-stats")
async def ab_stats(current_user: dict = Depends(get_current_user)):
    """List every row that's running an A/B test (i.e. has variant_b
    populated) with per-variant impressions + CTA clicks + CTR."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    db = get_db()
    rows = await db.city_landing_pages.find(
        {"variant_b": {"$exists": True, "$ne": None}},
        {"_id": 0,
         "slug": 1, "town": 1, "intent_phrase": 1, "url": 1,
         "confidence_score": 1, "ab_started_at": 1,
         "variant_a_impressions": 1, "variant_b_impressions": 1,
         "variant_a_cta_clicks": 1, "variant_b_cta_clicks": 1,
         "variant_b.confidence_score": 1},
    ).sort("ab_started_at", -1).to_list(500)

    out = []
    for r in rows:
        a_imp = int(r.get("variant_a_impressions") or 0)
        b_imp = int(r.get("variant_b_impressions") or 0)
        a_clk = int(r.get("variant_a_cta_clicks") or 0)
        b_clk = int(r.get("variant_b_cta_clicks") or 0)
        out.append({
            "slug": r.get("slug"),
            "town": r.get("town"),
            "intent_phrase": r.get("intent_phrase"),
            "url": r.get("url"),
            "ab_started_at": r.get("ab_started_at"),
            "variant_a": {
                "score": r.get("confidence_score"),
                "impressions": a_imp,
                "clicks": a_clk,
                "ctr": (round(100 * a_clk / a_imp, 2) if a_imp else None),
            },
            "variant_b": {
                "score": (r.get("variant_b") or {}).get("confidence_score"),
                "impressions": b_imp,
                "clicks": b_clk,
                "ctr": (round(100 * b_clk / b_imp, 2) if b_imp else None),
            },
        })
    return {"rows": out}


class PromoteVariantRequest(BaseModel):
    slug: str
    winner: str = Field(..., pattern="^(a|b)$")


@router.post("/promote-variant")
async def promote_variant(payload: PromoteVariantRequest, current_user: dict = Depends(get_current_user)):
    """Pick a winner. If `b`, copy variant_b's body+meta over the
    primary fields and delete `variant_b`. If `a`, just delete
    `variant_b` (keep current body). Either way, A/B test ends and the
    impression/click counters are reset."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    db = get_db()
    row = await db.city_landing_pages.find_one({"slug": payload.slug}, {"_id": 0})
    if not row:
        raise HTTPException(status_code=404, detail="Page not in queue")
    if not row.get("variant_b"):
        raise HTTPException(status_code=400, detail="No A/B test on this page")

    set_payload: dict = {
        "updated_at": datetime.now(timezone.utc),
        "ab_winner": payload.winner,
        "ab_won_at": datetime.now(timezone.utc),
    }
    unset_payload: dict = {
        "variant_b": "",
        "variant_a_impressions": "",
        "variant_b_impressions": "",
        "variant_a_cta_clicks": "",
        "variant_b_cta_clicks": "",
        "ab_started_at": "",
    }
    if payload.winner == "b":
        vb = row["variant_b"] or {}
        set_payload["body_md"] = vb.get("body_md")
        set_payload["meta_title"] = vb.get("meta_title")
        set_payload["meta_description"] = vb.get("meta_description")
        set_payload["confidence_score"] = vb.get("confidence_score")
        set_payload["confidence_failed"] = vb.get("confidence_failed")

    await db.city_landing_pages.update_one(
        {"slug": payload.slug},
        {"$set": set_payload, "$unset": unset_payload},
    )
    return {"ok": True, "slug": payload.slug, "winner": payload.winner}


# ─── A/B winner auto-promotion ──────────────────────────────────────────


class AbAutopromoteSettings(BaseModel):
    enabled: Optional[bool] = None
    min_impressions: Optional[int] = Field(default=None, ge=50, le=10000)
    min_days: Optional[int] = Field(default=None, ge=1, le=90)
    hour_utc: Optional[int] = Field(default=None, ge=0, le=23)


@router.get("/ab-autopromote")
async def ab_autopromote_get(current_user: dict = Depends(get_current_user)):
    """Read auto-promote settings + current A/B-running candidate count."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    from services.city_pages_ab_autopromote import _load_settings  # noqa: PLC0415
    db = get_db()
    settings = await _load_settings(db)
    candidates = await db.city_landing_pages.count_documents(
        {"variant_b": {"$exists": True, "$ne": None}}
    )
    return {**settings, "candidate_count": candidates}


@router.put("/ab-autopromote")
async def ab_autopromote_put(payload: AbAutopromoteSettings, current_user: dict = Depends(get_current_user)):
    """Patch the auto-promote settings doc. Only fields you send are
    touched; everything else stays as-is."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    from services.city_pages_ab_autopromote import _load_settings, _save_settings  # noqa: PLC0415
    db = get_db()
    patch = {k: v for k, v in payload.model_dump().items() if v is not None}
    if patch:
        await _save_settings(db, patch)
    return await _load_settings(db)


@router.post("/ab-autopromote/run-now")
async def ab_autopromote_run_now(current_user: dict = Depends(get_current_user)):
    """Force-trigger the auto-promoter right now, ignoring hour/day
    gates. Eligibility checks (min_impressions / min_days per row) still
    apply — only ready tests get judged."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    from services.city_pages_ab_autopromote import run_ab_autopromote_tick  # noqa: PLC0415
    return await run_ab_autopromote_tick(force=True)


# ─── Public-facing storefront fetch ─────────────────────────────────────


public_router = APIRouter(prefix="/shop/city-page", tags=["SEO City Pages — Public"])


_VARIANT_COOKIE = "ts_cp_ab"


@public_router.get("/{slug}")
async def get_public_city_page(slug: str, request: Request, response: Response):
    """Storefront fetches an approved landing page by slug. Anonymous,
    no auth — these are public SEO pages.

    A/B logic: if the row has a populated `variant_b`, we serve one of
    A or B based on a sticky cookie (`ts_cp_ab=a|b`). New visitors get a
    50/50 random assignment which is then frozen for that browser. Each
    fetch increments the matching `variant_{a|b}_impressions` counter.
    """
    db = get_db()
    row = await db.city_landing_pages.find_one(
        {"slug": slug, "status": "approved"}, {"_id": 0}
    )
    if not row:
        raise HTTPException(status_code=404, detail="Page not found")

    has_b = bool(row.get("variant_b"))
    if not has_b:
        # No A/B test running — still inject the autonomous-SEO
        # enrichment (internal links + LocalBusiness/Article schema)
        # so single-variant pages get the same SEO benefits.
        try:
            from services.seo_autonomous import (
                internal_links_for_city, local_business_jsonld, article_jsonld,
            )
            links = await internal_links_for_city(db, slug)
            row["nearby_cities"] = links.get("nearby_cities", [])
            row["related_collections"] = links.get("related_collections", [])
            row["jsonld_local_business"] = local_business_jsonld(row)
            row["jsonld_article"] = article_jsonld(row)
        except Exception:
            pass
        return row

    chosen = (request.cookies.get(_VARIANT_COOKIE) or "").lower()
    if chosen not in ("a", "b"):
        chosen = "a" if (uuid.uuid4().int & 1) == 0 else "b"
        # 30-day sticky so the same browser always gets the same variant.
        response.set_cookie(
            _VARIANT_COOKIE, chosen,
            max_age=60 * 60 * 24 * 30,
            samesite="lax", httponly=False, secure=True,
        )

    # Increment impression counter for the served variant.
    await db.city_landing_pages.update_one(
        {"slug": slug},
        {"$inc": {f"variant_{chosen}_impressions": 1}},
    )

    if chosen == "b":
        vb = row["variant_b"] or {}
        # Overwrite the public-facing fields with B's content so the
        # storefront component code stays unchanged.
        row = {
            **row,
            "body_md": vb.get("body_md") or row.get("body_md"),
            "meta_title": vb.get("meta_title") or row.get("meta_title"),
            "meta_description": vb.get("meta_description") or row.get("meta_description"),
            "active_variant": "b",
        }
    else:
        row["active_variant"] = "a"

    # Inject editorial internal links + LocalBusiness/Article schema so
    # the storefront component can render them without a second round
    # trip and so the SSR layer can put the JSON-LD into the raw HTML
    # for crawlers that don't execute JS. Fail-soft — never block the
    # page render on enrichment errors.
    try:
        from services.seo_autonomous import (
            internal_links_for_city, local_business_jsonld, article_jsonld,
        )
        links = await internal_links_for_city(db, slug)
        row["nearby_cities"] = links.get("nearby_cities", [])
        row["related_collections"] = links.get("related_collections", [])
        row["jsonld_local_business"] = local_business_jsonld(row)
        row["jsonld_article"] = article_jsonld(row)
    except Exception:
        # Don't break the page render if enrichment fails; the SPA
        # still has body_md/meta_title to render the core content.
        pass
    return row


class TrackCtaClickRequest(BaseModel):
    slug: str
    variant: str = Field(..., pattern="^(a|b)$")


@public_router.post("/track-cta-click")
async def track_cta_click(payload: TrackCtaClickRequest):
    """Public, unauth endpoint — called by the city landing page when a
    visitor clicks one of the CTA buttons (Browse range / Call showroom).
    Increments `variant_{a|b}_cta_clicks` so the admin A/B stats panel
    can compute click-through rate.

    No PII recorded. Designed to be cheap (one $inc) and fail-soft."""
    db = get_db()
    res = await db.city_landing_pages.update_one(
        {"slug": payload.slug},
        {"$inc": {f"variant_{payload.variant}_cta_clicks": 1}},
    )
    return {"ok": True, "matched": res.matched_count}

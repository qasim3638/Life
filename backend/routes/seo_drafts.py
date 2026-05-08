"""
SEO Description Drafts — review-then-save flow.

Unlike the existing bulk generator (which writes straight to product.description),
this module stages AI-generated descriptions in `seo_description_drafts` so the
admin can review, optionally tweak, and approve before the copy goes live on
the storefront. Feeds the `/admin/marketing → SEO Drafts` inbox.

Pipeline:
  1. `scan_for_missing_descriptions()` — finds products with no description
     across the three allow-listed collections, generates a draft for each
     via `services.ai_descriptions`, appends to the draft's `drafts[]` history.
     Caps per-run spend. Safe to run repeatedly — idempotent on product_id +
     collection.
  2. Admin opens the inbox (`GET /seo-drafts`) and sees a list of
     `status: pending` drafts with the latest suggestion pre-filled.
  3. Admin clicks **Save** / **Edit & Save** → `approve` writes the final copy
     to the product and flips the draft to `status: approved`.
  4. Admin can **Regenerate** with a variant (`default` / `shorter` /
     `more_technical`) — appends to the draft's `drafts[]` history so the
     admin can compare and pick. Old drafts are never destroyed.
  5. Admin can **Skip** — marks `status: skipped` so the scanner won't
     re-generate for that product until explicitly reset.

Cost control:
  • `max_per_run` limits how many LLM calls per scan (default 50, admin-tunable).
  • `max_per_day` is a soft daily budget enforced across scheduled + manual
    scans (checked via `drafts_generated_today()`).
  • The scheduler job is the cheap-and-sleepy half; admins can always click
    the "Scan now" button for an immediate force-run.
"""
from __future__ import annotations

import os
import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from config import get_db
from services import get_current_user
from services.ai_descriptions import (
    ALLOWED_PRODUCT_COLLECTIONS,
    missing_description_filter,
    product_display_name,
    siblings_for,
    generate_one,
    save_generated_description,
    build_prompt,
    DEFAULT_MODEL,
    _SYSTEM_MESSAGE,
)

router = APIRouter(prefix="/marketing/seo-drafts", tags=["Marketing"])
logger = logging.getLogger(__name__)

# Default limits — admin-overridable via the Marketing settings doc.
DEFAULT_LIMITS = {
    "max_per_run": 50,        # cap per scan (manual or nightly)
    "max_per_day": 400,       # soft daily budget (all scans combined)
}
VARIANTS = {"default", "shorter", "more_technical", "warmer", "benefits_focused"}
_MAX_CUSTOM_PROMPT_LEN = 400


def _is_admin(user: dict) -> bool:
    return (user or {}).get("role") in {"super_admin", "admin", "manager"}


def _variant_prompt_suffix(variant: str) -> str:
    """Small prompt nudges for non-default variants. We keep them additive so
    the shared `build_prompt()` still does the heavy lifting."""
    if variant == "shorter":
        return "\n\nEXTRA CONSTRAINT: Target 35-45 words (not 55-65). Be tighter."
    if variant == "more_technical":
        return (
            "\n\nEXTRA CONSTRAINT: Tone should be technical / spec-oriented. "
            "Lean into material science, installation notes, and PEI rating if "
            "inferable. Minimise adjectives; maximise concrete nouns."
        )
    if variant == "warmer":
        return (
            "\n\nEXTRA CONSTRAINT: Warmer, more inviting tone — evoke how the "
            "space will feel. Still 55-65 words, still factual."
        )
    if variant == "benefits_focused":
        return (
            "\n\nEXTRA CONSTRAINT: Lead with the end-customer benefit (low "
            "maintenance, slip-safe, easy to lay) before specs."
        )
    return ""


def _custom_prompt_suffix(custom_instruction: str) -> str:
    """Admin-provided free-text tweak. Sanitised + length-capped so an
    overeager prompt can't dominate the build_prompt contract."""
    cleaned = (custom_instruction or "").strip()
    if not cleaned:
        return ""
    if len(cleaned) > _MAX_CUSTOM_PROMPT_LEN:
        cleaned = cleaned[:_MAX_CUSTOM_PROMPT_LEN]
    # Prevent custom prompt from contradicting the core contract — it
    # augments, never overrides.
    return (
        "\n\nADMIN STEER (apply in addition to the rules above, do not "
        f"contradict them): {cleaned}"
    )


async def _drafts_generated_today(db) -> int:
    """Count how many draft generations have happened in the last 24h across
    BOTH scheduled and manual runs — enforces the daily budget cap."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    return await db.seo_description_drafts.count_documents({
        "last_generated_at": {"$gte": cutoff}
    })


async def _limits(db) -> dict:
    """Read admin-tunable limits from the marketing settings doc, falling back
    to `DEFAULT_LIMITS`."""
    doc = await db.website_settings.find_one(
        {"key": "marketing"}, {"_id": 0, "value.seo_drafts_limits": 1},
    )
    stored = (
        ((doc or {}).get("value") or {}).get("seo_drafts_limits") or {}
    )
    return {**DEFAULT_LIMITS, **stored}


async def _skipped_ids(db, collection: str) -> set:
    """Product IDs the admin has chosen to skip in this collection — the
    scanner must not re-generate for these."""
    cursor = db.seo_description_drafts.find(
        {"collection": collection, "status": "skipped"},
        {"_id": 0, "product_id": 1},
    )
    return {d["product_id"] async for d in cursor}


async def _generate_one_draft(db, collection: str, product: dict, variant: str, api_key: str, sibling_cache: dict, custom_instruction: str = "") -> dict:
    """Call the shared LLM service for one product, respecting the variant
    nudge. Returns the same `{ok, description|error}` shape."""
    siblings = await siblings_for(db, collection, product, sibling_cache)
    # Build base prompt, then append variant instruction + optional admin steer.
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    prompt = (
        build_prompt(product, siblings)
        + _variant_prompt_suffix(variant)
        + _custom_prompt_suffix(custom_instruction)
    )
    try:
        chat = LlmChat(
            api_key=api_key,
            session_id=f"desc-draft-{product.get('id', product.get('sku', 'x'))}-{uuid.uuid4().hex[:6]}",
            system_message=_SYSTEM_MESSAGE,
        ).with_model(*DEFAULT_MODEL)
        desc = await chat.send_message(UserMessage(text=prompt))
        desc = (desc or "").strip()
        if not desc:
            return {"ok": False, "error": "Empty response from LLM"}
        return {"ok": True, "description": desc}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:200]}


async def _upsert_draft(db, *, collection: str, product: dict, new_text: str, variant: str = "default", custom_instruction: str = "") -> dict:
    """Append a new suggestion to the product's draft history and return
    the updated doc. Creates the draft row on first sighting."""
    now = datetime.now(timezone.utc).isoformat()
    pid = product.get("id") or product.get("sku")
    draft_entry = {
        "text": new_text,
        "variant": variant,
        "custom_instruction": (custom_instruction or "").strip()[:_MAX_CUSTOM_PROMPT_LEN],
        "created_at": now,
        "id": uuid.uuid4().hex[:10],
    }
    existing = await db.seo_description_drafts.find_one(
        {"collection": collection, "product_id": pid},
        {"_id": 0},
    )
    if existing:
        history = existing.get("drafts", [])
        history.append(draft_entry)
        # Cap history at 10 entries to keep docs small.
        if len(history) > 10:
            history = history[-10:]
        new_status = "pending" if existing.get("status") in ("pending", "skipped") else existing.get("status")
        await db.seo_description_drafts.update_one(
            {"collection": collection, "product_id": pid},
            {"$set": {
                "drafts": history,
                "last_generated_at": now,
                "updated_at": now,
                # Re-generating a skipped draft re-opens it for review.
                "status": new_status,
            }},
        )
        existing["drafts"] = history
        existing["last_generated_at"] = now
        existing["updated_at"] = now
        existing["status"] = new_status
        return existing
    doc = {
        "id": uuid.uuid4().hex,
        "product_id": pid,
        "collection": collection,
        "product_name": product_display_name(product),
        "product_category": product.get("category", ""),
        "current_description": product.get("description", "") or "",
        "drafts": [draft_entry],
        "status": "pending",
        "created_at": now,
        "updated_at": now,
        "last_generated_at": now,
    }
    await db.seo_description_drafts.insert_one(dict(doc))
    doc.pop("_id", None)
    return doc


async def scan_for_missing_descriptions(*, force: bool = False, max_override: Optional[int] = None) -> dict:
    """Core scanner — finds missing descriptions, generates drafts, stages
    them. Called from both the nightly scheduler and the "Scan now" button.

    Budget behaviour:
      - Hard cap per run: `max_per_run` (or `max_override` for explicit
        manual runs).
      - Soft daily cap: `max_per_day`. When `force=False` we skip the run
        entirely once the daily budget is exhausted. `force=True` (admin
        "Scan now") bypasses ONLY the daily cap, still respects `max_per_run`.
    """
    db = get_db()
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        return {"ok": False, "error": "EMERGENT_LLM_KEY not configured"}

    limits = await _limits(db)
    max_per_run = int(max_override or limits["max_per_run"])
    max_per_day = int(limits["max_per_day"])
    if not force:
        done_today = await _drafts_generated_today(db)
        remaining_budget = max(0, max_per_day - done_today)
        if remaining_budget == 0:
            return {"ok": True, "skipped": True, "reason": "daily budget exhausted"}
        max_per_run = min(max_per_run, remaining_budget)

    # Gather candidates across all three collections, excluding skipped
    # products and anything that already has a pending draft (we don't want
    # to stack duplicate work in the inbox).
    candidates: list[tuple[str, dict]] = []
    already_queued: dict[str, set] = {}
    for col in ALLOWED_PRODUCT_COLLECTIONS:
        cursor = db.seo_description_drafts.find(
            {"collection": col, "status": {"$in": ["pending", "skipped"]}},
            {"_id": 0, "product_id": 1},
        )
        already_queued[col] = {d["product_id"] async for d in cursor}

    for col in ALLOWED_PRODUCT_COLLECTIONS:
        if len(candidates) >= max_per_run:
            break
        cursor = db[col].find(missing_description_filter(), {"_id": 0}).limit(max_per_run * 2)
        async for p in cursor:
            pid = p.get("id") or p.get("sku")
            if pid in already_queued[col]:
                continue
            candidates.append((col, p))
            if len(candidates) >= max_per_run:
                break

    if not candidates:
        return {"ok": True, "processed": 0, "generated": 0, "reason": "nothing to do"}

    sem = asyncio.Semaphore(4)
    sibling_cache: dict = {}

    async def _one(col: str, prod: dict):
        async with sem:
            res = await _generate_one_draft(db, col, prod, "default", api_key, sibling_cache)
            if not res["ok"]:
                return {"ok": False, "product_id": prod.get("id") or prod.get("sku"), "error": res["error"]}
            draft = await _upsert_draft(
                db, collection=col, product=prod, new_text=res["description"], variant="default"
            )
            return {"ok": True, "draft_id": draft["id"], "product_name": draft["product_name"]}

    results = await asyncio.gather(*[_one(col, p) for col, p in candidates])
    generated = sum(1 for r in results if r.get("ok"))

    await db.website_settings.update_one(
        {"key": "marketing"},
        {"$set": {
            "value.seo_drafts_last_run": {
                "at": datetime.now(timezone.utc).isoformat(),
                "generated": generated,
                "force": force,
            }
        }},
        upsert=True,
    )

    return {
        "ok": True,
        "processed": len(results),
        "generated": generated,
        "errors": [r for r in results if not r.get("ok")][:5],
    }


# ───────────────────────── API ROUTES ────────────────────────────────

class ScanRequest(BaseModel):
    limit: Optional[int] = None


@router.post("/scan")
async def admin_scan_now(payload: ScanRequest, current_user: dict = Depends(get_current_user)):
    """Force-run the scanner now. Bypasses the daily soft cap; still respects
    the per-run hard cap."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    return await scan_for_missing_descriptions(force=True, max_override=payload.limit)


@router.get("")
async def list_drafts(
    status: str = "pending",
    limit: int = 100,
    current_user: dict = Depends(get_current_user),
):
    """List drafts for the review inbox. Filter by status (pending by default,
    can request approved/skipped for historical views)."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    if status not in {"pending", "approved", "skipped", "all"}:
        raise HTTPException(status_code=400, detail="invalid status filter")
    db = get_db()
    q = {} if status == "all" else {"status": status}
    cursor = db.seo_description_drafts.find(q, {"_id": 0}).sort("updated_at", -1).limit(max(1, min(int(limit), 500)))
    drafts = await cursor.to_list(500)

    last_run = await db.website_settings.find_one(
        {"key": "marketing"}, {"_id": 0, "value.seo_drafts_last_run": 1}
    )
    totals = {}
    for s in ("pending", "approved", "skipped"):
        totals[s] = await db.seo_description_drafts.count_documents({"status": s})

    return {
        "drafts": drafts,
        "totals": totals,
        "last_run": ((last_run or {}).get("value") or {}).get("seo_drafts_last_run"),
        "limits": await _limits(db),
    }


class RegenerateRequest(BaseModel):
    variant: str = Field(default="default")
    custom_instruction: Optional[str] = Field(default=None, max_length=_MAX_CUSTOM_PROMPT_LEN)


@router.post("/{draft_id}/regenerate")
async def regenerate_draft(
    draft_id: str,
    payload: RegenerateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Generate a fresh variant and append to the draft's history.
    Accepts optional admin free-text steer (e.g. "make it 3x shorter",
    "emphasise underfloor heating compatibility")."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    variant = payload.variant if payload.variant in VARIANTS else "default"
    custom = (payload.custom_instruction or "").strip()
    db = get_db()
    draft = await db.seo_description_drafts.find_one({"id": draft_id}, {"_id": 0})
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    prod = await db[draft["collection"]].find_one(
        {"$or": [{"id": draft["product_id"]}, {"sku": draft["product_id"]}]},
        {"_id": 0},
    )
    if not prod:
        raise HTTPException(status_code=404, detail="Underlying product not found — was it deleted?")

    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="EMERGENT_LLM_KEY not configured")

    res = await _generate_one_draft(db, draft["collection"], prod, variant, api_key, {}, custom)
    if not res["ok"]:
        raise HTTPException(status_code=500, detail=res["error"])
    updated = await _upsert_draft(
        db, collection=draft["collection"], product=prod,
        new_text=res["description"], variant=variant, custom_instruction=custom,
    )
    return {"draft": updated}


class ApproveRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=5000)
    target_keyword: Optional[str] = Field(default=None, max_length=200)


@router.post("/{draft_id}/approve")
async def approve_draft(
    draft_id: str,
    payload: ApproveRequest,
    current_user: dict = Depends(get_current_user),
):
    """Publish the (possibly admin-edited) description to the live product
    and flip the draft to `approved`. This is the ONLY code path in the
    drafts flow that writes to the live storefront.

    If the admin arrived via a Search Insights "target this keyword" deep
    link, the frontend echoes the keyword back here so we can stamp it on
    the draft. The Search Insights card uses these stamps to surface a
    "✓ 3 products targeting this phrase" badge — closing the feedback loop."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    db = get_db()
    draft = await db.seo_description_drafts.find_one({"id": draft_id}, {"_id": 0})
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    final = payload.description.strip()
    if not final:
        raise HTTPException(status_code=400, detail="Description cannot be empty")

    prod = await db[draft["collection"]].find_one(
        {"$or": [{"id": draft["product_id"]}, {"sku": draft["product_id"]}]},
        {"_id": 0},
    )
    if not prod:
        raise HTTPException(status_code=404, detail="Underlying product not found")

    await save_generated_description(db, draft["collection"], prod, final)
    now = datetime.now(timezone.utc).isoformat()
    update_set = {
        "status": "approved",
        "approved_text": final,
        "approved_at": now,
        "approved_by": (current_user or {}).get("email"),
        "updated_at": now,
    }
    target_kw = (payload.target_keyword or "").strip()
    if target_kw:
        update_set["approved_for_keyword"] = target_kw[:200]
        update_set["approved_for_keyword_lower"] = target_kw.lower()[:200]
    await db.seo_description_drafts.update_one(
        {"id": draft_id},
        {"$set": update_set},
    )
    return {"ok": True, "product_id": draft["product_id"]}


@router.post("/{draft_id}/skip")
async def skip_draft(draft_id: str, current_user: dict = Depends(get_current_user)):
    """Mark a draft as skipped so the scanner stops suggesting for it."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    db = get_db()
    res = await db.seo_description_drafts.update_one(
        {"id": draft_id},
        {"$set": {
            "status": "skipped",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Draft not found")
    return {"ok": True}

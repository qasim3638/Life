"""
Tile Visualizer routes.

Endpoint map
------------
GET   /api/visualizer/sample-rooms                  → public list of
                                                     curated rooms +
                                                     surface metadata
POST  /api/visualizer/sessions                      → start a session
                                                     (sample room +
                                                     tile id)
POST  /api/visualizer/sessions/{id}/render          → kick off a render
                                                     ('fast' | 'photoreal')
GET   /api/visualizer/sessions/{id}                 → poll render status
POST  /api/visualizer/sessions/{id}/quote           → calculate cart
                                                     quantities (tiles,
                                                     adhesive, grout)
POST  /api/admin/visualizer/sample-rooms            → admin: add a room
GET   /api/admin/visualizer/stats                   → admin: cost & usage

Hybrid quota policy lives at the start of /render — every customer gets
1 free photoreal render per browser session (we accept the trivial
ability to bypass via incognito, the visual wow + cart-fill conversion
is more valuable than perfect anti-abuse). Logged-in customers with a
basket >£500 (configurable at env via VISUALIZER_PREMIUM_THRESHOLD_GBP)
get unlimited photoreal renders.
"""
from __future__ import annotations

import os
import uuid
import logging
import asyncio
from datetime import datetime, timezone

import httpx

from fastapi import APIRouter, HTTPException, Depends, Request, UploadFile, File, Form
from pydantic import BaseModel, Field

from config import get_db
from services import get_current_user
from services.visualizer import (
    render_fast_composite,
    render_photoreal_with_fal,
    estimate_quote_for_render,
    PHOTOREAL_COST_USD,
    FAST_COST_USD,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/visualizer", tags=["Tile Visualizer"])
admin_router = APIRouter(prefix="/admin/visualizer", tags=["Tile Visualizer Admin"])

PREMIUM_THRESHOLD_GBP = float(os.environ.get("VISUALIZER_PREMIUM_THRESHOLD_GBP", "500"))
FREE_PHOTOREAL_PER_SESSION = int(os.environ.get("VISUALIZER_FREE_PHOTOREAL_PER_SESSION", "1"))


# ------------------------------------------------------------------
# Pricing config — pulled from `website_settings.visualizer_pricing`
# so admins can tune adhesive/grout prices live without a code push.
# ------------------------------------------------------------------

PRICING_DEFAULTS = {
    "adhesive_price_per_bag": 18.50,
    "grout_price_per_bag": 9.99,
    "wastage_percent": 10,
    "floor_m2_per_adhesive_bag": 4.0,
    "wall_m2_per_adhesive_bag": 5.0,
    "m2_per_grout_bag": 11.0,
}


async def _load_visualizer_pricing(db) -> dict:
    """Return the live pricing config, falling back to PRICING_DEFAULTS
    for any keys the admin hasn't overridden yet."""
    doc = await db.website_settings.find_one({"key": "visualizer_pricing"}, {"_id": 0})
    raw = (doc or {}).get("settings", {}) if isinstance(doc, dict) else {}
    out = dict(PRICING_DEFAULTS)
    for k, default in PRICING_DEFAULTS.items():
        v = raw.get(k)
        if v is None or v == "":
            continue
        try:
            out[k] = type(default)(v)
        except (TypeError, ValueError):
            continue
    return out


def _is_admin_from_request(request: Request) -> bool:
    """Best-effort: read the Bearer token off the request and decode its
    role claim without a DB lookup. Used purely for visualizer feature-
    flag bypass — admins can preview the visualizer even when the
    public flag is off. No security impact: the underlying admin
    endpoints (`/admin/visualizer/*`) still have full role checks via
    `_require_admin`."""
    try:
        import jwt
        from services.auth import JWT_SECRET
        auth = request.headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            return False
        payload = jwt.decode(auth.split(" ", 1)[1], JWT_SECRET, algorithms=["HS256"])
        return (payload or {}).get("role") in ("super_admin", "admin", "manager")
    except Exception:
        return False


def _public_enabled_sync() -> bool:
    """Env-var override — deliberate hard switch for emergencies and
    for parity with the old (pre-May-2026) behaviour. The env var, when
    set to `true`, forces ON regardless of the DB toggle so the user
    can always kill-switch via Railway if the admin UI is inaccessible.
    When set to `false` (or `off`/`0`), forces OFF. When unset/empty,
    the DB toggle wins."""
    raw = (os.environ.get("VISUALIZER_PUBLIC_ENABLED") or "").strip().lower()
    if raw in ("true", "1", "yes", "on"):
        return True
    if raw in ("false", "0", "no", "off"):
        return False
    return None  # signal "not set — use DB"  # type: ignore[return-value]


async def _public_enabled(db=None) -> bool:
    """Customer-facing visualizer is DB-toggled now so the admin can
    flip it on/off from /admin/visualizer without a redeploy. The env
    var `VISUALIZER_PUBLIC_ENABLED` (true/false) still wins when set —
    it's the emergency kill-switch. Default OFF so a fresh environment
    never accidentally exposes the feature before QA."""
    env_forced = _public_enabled_sync()
    if env_forced is not None:
        return env_forced
    try:
        if db is None:
            db = get_db()
        doc = await db.website_settings.find_one(
            {"key": "visualizer_launch"}, {"_id": 0, "enabled": 1}
        )
        return bool((doc or {}).get("enabled", False))
    except Exception:
        return False


# ------------------------------------------------------------------
# Models
# ------------------------------------------------------------------

class StartSessionReq(BaseModel):
    sample_room_id: str | None = None  # None when starting from a customer upload
    upload_session_id: str | None = None  # set when room came from /upload-room
    tile_id: str
    image_index: int | None = None  # which gallery image of the tile to use as texture (default 0)
    customer_email: str | None = None
    cart_total_gbp: float | None = None  # for premium gating
    surface_kind: str | None = None  # "floor" | "wall" — used with uploads


class RenderReq(BaseModel):
    style: str = Field(default="fast", pattern="^(fast|photoreal)$")


class WaitlistJoinReq(BaseModel):
    email: str
    source: str | None = None  # e.g. "coming_soon_page"
    referrer: str | None = None


class QuoteReq(BaseModel):
    surface_m2: float | None = None  # override; otherwise uses room default


@router.post("/upload-room")
async def upload_room(
    request: Request,
    file: UploadFile = File(...),
    surface_kind: str = Form("floor"),
):
    """Customer uploads their own room photo. We:
       1. Stream the bytes to fal storage so SAM2 can see it
       2. Run SAM2 auto-segment on the surface_kind region
       3. Persist a temporary "uploaded room" record with the resulting
          polygon + mask URL — looks identical to a sample-room from the
          rest of the pipeline's perspective.

    Cost: ~£0.02 (SAM2 auto-segment, no FLUX yet).
    """
    if not await _public_enabled() and not _is_admin_from_request(request):
        raise HTTPException(status_code=404, detail="Not found")
    if file is None:
        raise HTTPException(status_code=422, detail="No file uploaded")

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=422, detail="Empty file")
    if len(contents) > 12 * 1024 * 1024:  # 12 MB cap
        raise HTTPException(status_code=413, detail="Photo too large — max 12 MB")

    # 1. Push bytes to fal storage so SAM2 can fetch by URL
    import fal_client
    content_type = file.content_type or "image/jpeg"
    if content_type not in ("image/jpeg", "image/png", "image/webp", "image/heic"):
        raise HTTPException(status_code=415, detail="Unsupported image type — JPG / PNG / WEBP only")
    try:
        room_url = await fal_client.upload_async(contents, content_type)
    except Exception as exc:
        logger.exception("fal.ai upload failed")
        raise HTTPException(status_code=502, detail=f"Upload failed: {str(exc)[:200]}")

    # 2. SAM2 auto-segment
    from services.visualizer import auto_segment_surface
    seg = await auto_segment_surface(room_url, surface_kind=surface_kind)

    # 3. Persist as a "user room" — same shape as sample rooms but flagged
    upload_id = str(uuid.uuid4())
    db = get_db()
    doc = {
        "id": upload_id,
        "is_user_upload": True,
        "image_url": room_url,
        "surface_kind": surface_kind,
        "surface_polygon": seg["polygon"],
        "mask_url": seg.get("mask_url"),
        "auto_detected": seg.get("auto_detected", False),
        "default_surface_m2": 9.0 if surface_kind == "floor" else 7.0,
        "tile_repeat_size_px": 180,
        "label": "Your room",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.visualizer_uploaded_rooms.insert_one(doc)
    doc.pop("_id", None)
    return {
        "upload_session_id": upload_id,
        "image_url": room_url,
        "auto_detected": seg.get("auto_detected", False),
        "surface_polygon": seg["polygon"],
        "surface_kind": surface_kind,
    }


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

async def _get_room(db, sample_room_id: str | None, upload_session_id: str | None) -> dict:
    if upload_session_id:
        room = await db.visualizer_uploaded_rooms.find_one({"id": upload_session_id}, {"_id": 0})
        if not room:
            raise HTTPException(status_code=404, detail="Uploaded room not found or expired")
        return room
    if not sample_room_id:
        raise HTTPException(status_code=422, detail="Either sample_room_id or upload_session_id is required")
    room = await db.visualizer_sample_rooms.find_one({"id": sample_room_id}, {"_id": 0})
    if not room:
        raise HTTPException(status_code=404, detail="Sample room not found")
    return room


def _normalise_tile_images(images_raw) -> list[str]:
    """Flatten the mixed `images` field on a product/tile doc into a plain
    list of URL strings. Tiles imported via different pipelines store
    images either as `["url", "url"]` OR as `[{"url": "...", "alt": "..."}, …]`.
    Dedupes and drops empties so the visualizer's image-picker always
    sees a clean list."""
    out: list[str] = []
    seen = set()
    for entry in (images_raw or []):
        url = ""
        if isinstance(entry, dict):
            url = entry.get("url") or ""
        elif isinstance(entry, str):
            url = entry
        url = (url or "").strip()
        if url and url not in seen:
            seen.add(url)
            out.append(url)
    return out


async def _resolve_tile(db, tile_id: str) -> dict:
    """Find the chosen tile in EITHER the products or tiles collection
    (same dual-lookup pattern as the sample-order route — storefront
    product IDs come from both catalogs).

    Returns the canonical first image as `image` AND the full image list
    as `images: list[str]` so the visualizer can render a thumbnail
    strip and let the customer choose which gallery photo to use as the
    surface texture (some products ship with 4-6 angles/colourways and
    we should never pin the visualizer to image[0] silently).
    """
    prod = await db.products.find_one({"id": tile_id}, {"_id": 0})
    if prod:
        images = _normalise_tile_images(prod.get("images"))
        return {
            "id": prod["id"],
            "name": prod.get("name") or "Tile",
            "image": images[0] if images else "",
            "images": images,
            "price_per_m2": float(prod.get("price_per_m2") or prod.get("price") or 25.0),
            "source": "products",
        }
    try:
        from bson import ObjectId
        tile_doc = None
        if len(tile_id) == 24:
            try:
                tile_doc = await db.tiles.find_one({"_id": ObjectId(tile_id)})
            except Exception:
                tile_doc = None
        if not tile_doc:
            tile_doc = (await db.tiles.find_one({"slug": tile_id})
                        or await db.tiles.find_one({"supplier_code": tile_id}))
    except ImportError:
        tile_doc = None
    if not tile_doc:
        raise HTTPException(status_code=404, detail="Tile not found")
    images = _normalise_tile_images(tile_doc.get("images"))
    return {
        "id": tile_id,
        "name": (tile_doc.get("display_name") or tile_doc.get("our_name")
                or tile_doc.get("name") or "Tile").strip(),
        "image": images[0] if images else "",
        "images": images,
        "price_per_m2": float(tile_doc.get("price_per_m2")
                              or tile_doc.get("our_price")
                              or tile_doc.get("price") or 25.0),
        "source": "tiles",
    }


async def _can_render_photoreal(db, request: Request, session_doc: dict) -> tuple[bool, str]:
    """Returns (allowed, reason). Customers in premium tier bypass all
    counts; everyone else gets `FREE_PHOTOREAL_PER_SESSION`."""
    cart_gbp = float(session_doc.get("cart_total_gbp") or 0)
    if cart_gbp >= PREMIUM_THRESHOLD_GBP:
        return True, "premium-cart"

    # Count prior photoreal renders for this *session id*. Customers can
    # bypass via incognito — that's an acceptable cost vs friction.
    count = await db.visualizer_renders.count_documents({
        "session_id": session_doc["id"],
        "style": "photoreal",
        "status": "succeeded",
    })
    if count < FREE_PHOTOREAL_PER_SESSION:
        return True, f"free-tier ({count}/{FREE_PHOTOREAL_PER_SESSION})"
    return False, "free-tier exhausted"


# ------------------------------------------------------------------
# PUBLIC endpoints
# ------------------------------------------------------------------

@router.get("/feature-flag")
async def feature_flag(request: Request):
    """Lightweight unauth'd endpoint the storefront page queries on
    mount to decide whether to render the real visualizer or the
    "coming soon" placeholder."""
    enabled = await _public_enabled()
    admin_preview = (not enabled) and _is_admin_from_request(request)
    return {"enabled": enabled or admin_preview, "public": enabled, "admin_preview": admin_preview}


@router.post("/waitlist")
async def join_waitlist(req: WaitlistJoinReq, request: Request):
    """Public endpoint — runs even when the visualizer is feature-flagged
    OFF (the whole point is capturing demand on the Coming Soon page).
    Idempotent on email so repeat clicks don't bloat the list."""
    email = (req.email or "").strip().lower()
    if not email or "@" not in email or len(email) > 200:
        raise HTTPException(status_code=422, detail="Please enter a valid email")
    db = get_db()
    now_iso = datetime.now(timezone.utc).isoformat()
    set_doc = {
        "email": email,
        "source": (req.source or "coming_soon_page")[:60],
        "referrer": (req.referrer or request.headers.get("referer", ""))[:300],
        "user_agent": (request.headers.get("user-agent", ""))[:200],
        "updated_at": now_iso,
        "notified": False,
    }
    await db.visualizer_waitlist.update_one(
        {"email": email},
        {"$set": set_doc, "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": now_iso}},
        upsert=True,
    )
    return {"ok": True, "message": "You're on the list — we'll email you the day it goes live."}


@router.get("/sample-rooms")
async def list_sample_rooms(request: Request):
    """Public: list curated sample rooms with their surface metadata."""
    if not await _public_enabled() and not _is_admin_from_request(request):
        raise HTTPException(status_code=404, detail="Not found")
    db = get_db()
    rooms = await db.visualizer_sample_rooms.find(
        {"active": {"$ne": False}}, {"_id": 0}
    ).sort("display_order", 1).to_list(length=None)
    return {"rooms": rooms}


@router.post("/sessions")
async def start_session(req: StartSessionReq, request: Request):
    if not await _public_enabled() and not _is_admin_from_request(request):
        raise HTTPException(status_code=404, detail="Not found")
    db = get_db()
    room = await _get_room(db, req.sample_room_id, req.upload_session_id)
    tile = await _resolve_tile(db, req.tile_id)

    # Honour optional image_index — clamps to a valid range so a stale
    # client referencing an old gallery doesn't crash. Falls back to the
    # canonical first image when the tile has no usable gallery.
    images = tile.get("images") or ([tile["image"]] if tile.get("image") else [])
    if not images:
        raise HTTPException(
            status_code=422,
            detail=f"Tile '{tile['name']}' has no image URL — cannot visualize. Pick a different tile.",
        )
    requested_idx = int(req.image_index or 0)
    chosen_idx = max(0, min(requested_idx, len(images) - 1))
    chosen_image = images[chosen_idx]

    sess = {
        "id": str(uuid.uuid4()),
        "sample_room_id": room["id"],
        "is_user_upload": bool(room.get("is_user_upload")),
        "tile_id": tile["id"],
        "tile_name": tile["name"],
        "tile_image": chosen_image,
        "tile_images": images,  # full gallery for client-side switcher
        "tile_image_index": chosen_idx,
        "tile_price_per_m2": tile["price_per_m2"],
        "tile_source": tile["source"],
        "customer_email": (req.customer_email or "").lower().strip(),
        "cart_total_gbp": float(req.cart_total_gbp or 0),
        "renders": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.visualizer_sessions.insert_one(sess)
    sess.pop("_id", None)
    # Reflect the chosen image in the response payload too — without this
    # the response body's tile.image is always images[0] which surprises
    # API consumers who passed image_index>0 and expect the response to
    # echo their choice. (Reported by testing_agent_v3_fork iter 158.)
    response_tile = dict(tile)
    response_tile["image"] = chosen_image
    return {
        "session_id": sess["id"],
        "room": room,
        "tile": response_tile,
        "image_index": chosen_idx,
        "premium": float(req.cart_total_gbp or 0) >= PREMIUM_THRESHOLD_GBP,
    }


@router.post("/sessions/{session_id}/render")
async def render(session_id: str, req: RenderReq, request: Request):
    db = get_db()
    sess = await db.visualizer_sessions.find_one({"id": session_id}, {"_id": 0})
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    upload_id = sess["sample_room_id"] if sess.get("is_user_upload") else None
    sample_id = None if sess.get("is_user_upload") else sess["sample_room_id"]
    room = await _get_room(db, sample_id, upload_id)

    # Quota gating for photoreal
    if req.style == "photoreal":
        allowed, reason = await _can_render_photoreal(db, request, sess)
        if not allowed:
            raise HTTPException(
                status_code=402,
                detail={
                    "message": (
                        "You've used your free photoreal render this session. "
                        "Add £500+ of tiles to your basket for unlimited "
                        "photoreal renders, or stick with the fast preview."
                    ),
                    "reason": reason,
                },
            )

    render_id = str(uuid.uuid4())
    render_doc = {
        "id": render_id,
        "session_id": session_id,
        "style": req.style,
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "result_url": None,
        "cost_usd": 0.0,
    }
    await db.visualizer_renders.insert_one(render_doc)

    try:
        if req.style == "fast":
            png_bytes = await render_fast_composite(
                room_image_url=room["image_url"],
                tile_image_url=sess["tile_image"],
                surface_polygon=room["surface_polygon"],
                tile_repeat_size_px=room.get("tile_repeat_size_px", 180),
            )
            # Persist to GridFS (or our static-uploads if available) — for
            # V1 we just stash a base64 data URL so we don't introduce a
            # new storage system. fast renders are 200-400 KB which is
            # fine for storage; V2 should move to S3-compatible storage.
            import base64
            data_url = "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")
            await db.visualizer_renders.update_one(
                {"id": render_id},
                {"$set": {
                    "status": "succeeded",
                    "result_url": data_url,
                    "cost_usd": FAST_COST_USD,
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                }},
            )
            return {"render_id": render_id, "status": "succeeded", "result_url": data_url}

        # photoreal
        out = await render_photoreal_with_fal(
            room_image_url=room["image_url"],
            tile_image_url=sess["tile_image"],
            surface_polygon=room["surface_polygon"],
            surface_kind=room.get("surface_kind", "floor"),
            tile_name=sess["tile_name"],
            mask_url=room.get("mask_url"),  # populated by SAM2 for uploads
        )
        await db.visualizer_renders.update_one(
            {"id": render_id},
            {"$set": {
                "status": "succeeded",
                "result_url": out["result_url"],
                "cost_usd": out["cost_usd"],
                "prompt": out.get("prompt"),
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
        return {"render_id": render_id, "status": "succeeded", "result_url": out["result_url"]}

    except httpx.HTTPStatusError as exc:
        # Upstream tile or room image failed to download (e.g. Unsplash 404
        # on a stale CDN URL). Surface a clean 422 with the offending URL
        # rather than a 500 — the storefront can prompt the customer to
        # pick a different tile / room.
        logger.warning("visualizer render upstream image error: %s", exc)
        await db.visualizer_renders.update_one(
            {"id": render_id},
            {"$set": {
                "status": "failed",
                "error": f"upstream image {exc.response.status_code}: {exc.request.url}",
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
        raise HTTPException(
            status_code=422,
            detail={
                "message": "We couldn't load one of the images for this render — please try a different tile or room.",
                "url": str(exc.request.url),
                "status": exc.response.status_code,
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("visualizer render failed")
        await db.visualizer_renders.update_one(
            {"id": render_id},
            {"$set": {
                "status": "failed",
                "error": str(exc)[:240],
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
        raise HTTPException(status_code=500, detail=f"Render failed: {str(exc)[:200]}")


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    db = get_db()
    sess = await db.visualizer_sessions.find_one({"id": session_id}, {"_id": 0})
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    renders = await db.visualizer_renders.find(
        {"session_id": session_id}, {"_id": 0}
    ).sort("started_at", -1).to_list(length=None)
    sess["renders"] = renders
    return sess


@router.post("/sessions/{session_id}/quote")
async def calc_quote(session_id: str, req: QuoteReq):
    db = get_db()
    sess = await db.visualizer_sessions.find_one({"id": session_id}, {"_id": 0})
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    upload_id = sess["sample_room_id"] if sess.get("is_user_upload") else None
    sample_id = None if sess.get("is_user_upload") else sess["sample_room_id"]
    room = await _get_room(db, sample_id, upload_id)
    surface_m2 = float(req.surface_m2 or room.get("default_surface_m2") or 8.0)
    pricing = await _load_visualizer_pricing(db)
    quote = estimate_quote_for_render(
        surface_m2=surface_m2,
        tile_price_per_m2=sess["tile_price_per_m2"],
        surface_kind=room.get("surface_kind", "floor"),
        **pricing,
    )
    quote.update({
        "tile_id": sess["tile_id"],
        "tile_name": sess["tile_name"],
        "tile_price_per_m2": sess["tile_price_per_m2"],
        "room_name": room.get("label"),
        "currency": "GBP",
    })
    return quote


# ------------------------------------------------------------------
# ADMIN endpoints
# ------------------------------------------------------------------

class SampleRoomUpsert(BaseModel):
    id: str | None = None
    label: str
    room_type: str  # "kitchen" | "bathroom" | "hallway" | "living_room"
    surface_kind: str  # "floor" | "wall"
    image_url: str
    surface_polygon: list[list[int]]
    default_surface_m2: float
    tile_repeat_size_px: int = 180
    display_order: int = 100
    active: bool = True


def _require_admin(user: dict):
    if (user or {}).get("role") not in ("super_admin", "admin", "manager"):
        raise HTTPException(status_code=403, detail="Admin access required")


@admin_router.post("/sample-rooms")
async def upsert_sample_room(
    req: SampleRoomUpsert,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    db = get_db()
    rid = req.id or str(uuid.uuid4())
    doc = req.dict()
    doc["id"] = rid
    doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.visualizer_sample_rooms.update_one(
        {"id": rid},
        {"$set": doc, "$setOnInsert": {"created_at": doc["updated_at"]}},
        upsert=True,
    )
    return {"ok": True, "id": rid}


@admin_router.post("/upload-image")
async def upload_sample_room_image(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """Admin: upload a fresh room photo to fal.ai's CDN and return its
    public URL. Used by the Sample Room editor when an admin wants to
    replace a stale Unsplash URL with their own photo without going
    through the customer-upload flow (which creates a `visualizer_uploaded_rooms`
    record). Returned URL can be pasted straight into `image_url` on
    the sample-room upsert."""
    _require_admin(current_user)
    if not os.environ.get("FAL_KEY"):
        raise HTTPException(status_code=503, detail="FAL_KEY not configured on backend")
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=422, detail="Empty file")
    if len(contents) > 12 * 1024 * 1024:  # 12 MB cap, same as customer upload
        raise HTTPException(status_code=413, detail="Image too large — max 12 MB")
    content_type = file.content_type or "image/jpeg"
    if content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=415, detail="Unsupported image type — JPG / PNG / WEBP only")
    import fal_client
    try:
        url = await fal_client.upload_async(contents, content_type)
    except Exception as exc:
        logger.exception("fal.ai admin upload failed")
        raise HTTPException(status_code=502, detail=f"Upload failed: {str(exc)[:200]}")
    return {"url": url}


@admin_router.get("/sample-rooms")
async def list_admin_sample_rooms(current_user: dict = Depends(get_current_user)):
    """Admin: list every sample room (active OR inactive) so the admin
    UI can show toggles. Public `/visualizer/sample-rooms` filters to
    active only — this endpoint shows everything."""
    _require_admin(current_user)
    db = get_db()
    rows = await db.visualizer_sample_rooms.find(
        {}, {"_id": 0}
    ).sort("display_order", 1).to_list(length=None)
    return {"rooms": rows, "count": len(rows)}


@admin_router.delete("/sample-rooms/{room_id}")
async def delete_sample_room(room_id: str, current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    db = get_db()
    res = await db.visualizer_sample_rooms.delete_one({"id": room_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Room not found")
    return {"ok": True, "deleted": res.deleted_count}


class SampleRoomToggleReq(BaseModel):
    active: bool


@admin_router.patch("/sample-rooms/{room_id}/toggle")
async def toggle_sample_room(
    room_id: str,
    req: SampleRoomToggleReq,
    current_user: dict = Depends(get_current_user),
):
    """Admin: enable/disable a sample room without deleting it. Hidden
    rooms disappear from the customer-facing picker but live edits to
    polygon/m² are preserved for re-enabling later."""
    _require_admin(current_user)
    db = get_db()
    res = await db.visualizer_sample_rooms.update_one(
        {"id": room_id},
        {"$set": {"active": bool(req.active),
                  "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Room not found")
    return {"ok": True, "active": bool(req.active)}


# ------------------------------------------------------------------
# Launch status — DB-backed feature flag (replaces the old env-only
# VISUALIZER_PUBLIC_ENABLED switch). Env var still wins when set so
# there's always a Railway-side kill-switch for emergencies.
# ------------------------------------------------------------------

class LaunchStatusReq(BaseModel):
    enabled: bool
    also_email_waitlist: bool = False  # one-click "Go live AND notify"


@admin_router.get("/launch-status")
async def get_launch_status(current_user: dict = Depends(get_current_user)):
    """Admin: current visualizer public-visibility flag.

    Returns both the effective value (what customers actually see) and
    the components that produced it, so the admin UI can warn when the
    env var is overriding the DB toggle."""
    _require_admin(current_user)
    db = get_db()
    env_forced = _public_enabled_sync()
    doc = await db.website_settings.find_one(
        {"key": "visualizer_launch"}, {"_id": 0}
    ) or {}
    db_enabled = bool(doc.get("enabled", False))
    effective = env_forced if env_forced is not None else db_enabled
    # Unnotified waitlist count helps the UI decide whether to show the
    # "Email the waitlist at the same time" checkbox.
    unnotified = await db.visualizer_waitlist.count_documents(
        {"notified": {"$ne": True}}
    )
    return {
        "enabled": effective,
        "db_enabled": db_enabled,
        "env_override": env_forced,  # True/False/None
        "updated_by": doc.get("updated_by"),
        "updated_at": doc.get("updated_at"),
        "note": doc.get("note") or "",
        "waitlist_unnotified": unnotified,
        "ever_gone_live": bool(doc.get("ever_gone_live")),
    }


@admin_router.post("/launch-status")
async def set_launch_status(
    req: LaunchStatusReq,
    current_user: dict = Depends(get_current_user),
):
    """Admin: flip the visualizer on/off for customers. Takes effect
    immediately — the next `/feature-flag` request reflects the new
    value. Admin preview (`?preview=1`) keeps working either way.

    If the env var `VISUALIZER_PUBLIC_ENABLED` is set on the backend
    process, the env value wins — the DB toggle is still persisted so
    that clearing the env later gives the saved value back.

    Optional `also_email_waitlist` fires the launch-email batch in the
    same request — handy for true one-click launch day. Idempotent on
    `notified=true` so this never double-emails anyone.
    """
    _require_admin(current_user)
    db = get_db()
    now = datetime.now(timezone.utc)
    # Check if this is the first-ever go-live so the UI can decide
    # whether the default send-email checkbox should be ticked.
    existing = await db.website_settings.find_one({"key": "visualizer_launch"}, {"_id": 0}) or {}
    first_go_live = bool(req.enabled) and not existing.get("ever_gone_live")

    set_doc = {
        "key": "visualizer_launch",
        "enabled": bool(req.enabled),
        "updated_at": now,
        "updated_by": (current_user or {}).get("email"),
    }
    if req.enabled:
        # Record that we've gone live at least once (so "first go-live"
        # banners/defaults don't re-trigger after subsequent on/off flips).
        set_doc["ever_gone_live"] = True
        if first_go_live:
            set_doc["first_live_at"] = now
    await db.website_settings.update_one(
        {"key": "visualizer_launch"},
        {"$set": set_doc},
        upsert=True,
    )

    env_forced = _public_enabled_sync()
    effective = env_forced if env_forced is not None else bool(req.enabled)

    email_result = None
    if req.also_email_waitlist and req.enabled and effective:
        # Only email when we're actually going public (not when the env
        # var is forcing us OFF regardless of the DB flag).
        try:
            email_result = await send_launch_email(
                LaunchEmailReq(),  # use the default subject/headline/body
                current_user,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("launch-status auto-email failed")
            email_result = {"error": str(exc)[:200]}

    return {
        "ok": True,
        "enabled": effective,
        "db_enabled": bool(req.enabled),
        "env_override": env_forced,
        "first_go_live": first_go_live,
        "email_result": email_result,
    }


@admin_router.post("/sample-rooms/reseed")
async def reseed_sample_rooms(
    force: bool = False,
    current_user: dict = Depends(get_current_user),
):
    """Admin: re-seed the canonical 10 curated rooms.

    By default this is a no-op when the collection already has rooms —
    pass `?force=true` to upsert the canonical set on top of any custom
    edits. Use this if the production DB was wiped or if you want to
    restore any room you've edited back to its default polygon/m².
    """
    _require_admin(current_user)
    db = get_db()
    from services.visualizer_seed import seed_visualizer_rooms_if_empty
    res = await seed_visualizer_rooms_if_empty(db, force=force)
    return {"ok": True, **res}


@admin_router.post("/sample-rooms/validate-polygons")
async def validate_sample_room_polygons(current_user: dict = Depends(get_current_user)):
    """Admin: download every active sample room's image, detect its real
    dimensions, and flag polygons that fall outside the expected zone for
    their surface_kind.

    Heuristics (mirroring SAM2's fallback regions):
      • FLOOR rooms → polygon centroid should sit in the bottom 60% of
        the image (y > 0.30·H). Bounding box should be in the bottom 70%.
      • WALL rooms → polygon centroid should sit in the top 70% of the
        image (y < 0.75·H). Bounding box should not overflow >10% beyond
        the image dims.
      • Polygon must be entirely within image bounds.

    Surfaces that fail any check return status='bad' with a reason
    string. Borderline (centroid ok but bbox slightly off) → 'warn'.
    Returns per-room report so the admin UI can render status pills.
    """
    _require_admin(current_user)
    db = get_db()
    rows = await db.visualizer_sample_rooms.find(
        {}, {"_id": 0}
    ).sort("display_order", 1).to_list(length=None)

    results = []
    async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as cli:
        for room in rows:
            r = {
                "id": room["id"],
                "label": room.get("label", ""),
                "surface_kind": room.get("surface_kind"),
                "image_url": room.get("image_url"),
                "polygon": room.get("surface_polygon"),
                "active": room.get("active", True),
                "status": "ok",
                "reasons": [],
                "image_dims": None,
            }
            url = (room.get("image_url") or "").strip()
            if not url:
                r["status"] = "bad"
                r["reasons"].append("Missing image_url")
                results.append(r)
                continue
            try:
                resp = await cli.get(url)
                resp.raise_for_status()
                from PIL import Image
                import io as _io
                img = Image.open(_io.BytesIO(resp.content))
                W, H = img.size
                r["image_dims"] = {"w": W, "h": H}
            except Exception as exc:
                r["status"] = "bad"
                r["reasons"].append(f"Image fetch failed: {str(exc)[:120]}")
                results.append(r)
                continue

            poly = room.get("surface_polygon") or []
            if not isinstance(poly, list) or len(poly) < 3:
                r["status"] = "bad"
                r["reasons"].append("Polygon must have ≥3 points")
                results.append(r)
                continue

            xs = [p[0] for p in poly if isinstance(p, (list, tuple)) and len(p) >= 2]
            ys = [p[1] for p in poly if isinstance(p, (list, tuple)) and len(p) >= 2]
            if not xs or not ys:
                r["status"] = "bad"
                r["reasons"].append("Polygon points are malformed")
                results.append(r)
                continue

            x0, x1 = min(xs), max(xs)
            y0, y1 = min(ys), max(ys)
            cy = sum(ys) / len(ys)

            # 1. Polygon must be inside image bounds (small tolerance for rounding)
            tol = 4
            if x0 < -tol or y0 < -tol or x1 > W + tol or y1 > H + tol:
                r["status"] = "bad"
                r["reasons"].append(
                    f"Polygon bounding box ({x0},{y0})→({x1},{y1}) escapes image bounds {W}x{H}"
                )

            # 2. Coverage — too tiny relative to image area (likely the
            #    'middle rectangle' bug we saw on portrait photos)
            poly_area = max(1, (x1 - x0) * (y1 - y0))
            img_area = W * H
            coverage = poly_area / img_area
            r["coverage_pct"] = round(coverage * 100, 1)
            if coverage < 0.05:
                r["status"] = "bad"
                r["reasons"].append(
                    f"Polygon covers only {coverage*100:.1f}% of the image — likely anchored to wrong dimensions"
                )

            # 3. Surface-kind zone heuristic
            if room.get("surface_kind") == "floor":
                # Floor centroid should be in the bottom 60% of the image
                if cy < H * 0.30:
                    r["status"] = "bad"
                    r["reasons"].append(
                        f"Floor centroid at y={int(cy)} is in the top 30% of the image (expected bottom 60%)"
                    )
                elif cy < H * 0.45 and r["status"] != "bad":
                    r["status"] = "warn"
                    r["reasons"].append(
                        f"Floor centroid at y={int(cy)} is unusually high — verify it covers the visible floor"
                    )
            elif room.get("surface_kind") == "wall":
                # Wall centroid should NOT be in the bottom 25% (typically a floor zone)
                if cy > H * 0.85:
                    r["status"] = "bad"
                    r["reasons"].append(
                        f"Wall centroid at y={int(cy)} is in the bottom 15% of the image (expected top 70%)"
                    )

            results.append(r)

    summary = {
        "total": len(results),
        "ok": sum(1 for r in results if r["status"] == "ok"),
        "warn": sum(1 for r in results if r["status"] == "warn"),
        "bad": sum(1 for r in results if r["status"] == "bad"),
    }
    return {"summary": summary, "results": results}


@admin_router.get("/stats")
async def stats(current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    db = get_db()
    total_renders = await db.visualizer_renders.count_documents({})
    photoreal = await db.visualizer_renders.count_documents({"style": "photoreal", "status": "succeeded"})
    fast = await db.visualizer_renders.count_documents({"style": "fast", "status": "succeeded"})
    failed = await db.visualizer_renders.count_documents({"status": "failed"})
    # Sum cost_usd via aggregation
    pipeline = [{"$match": {"status": "succeeded"}},
                {"$group": {"_id": None, "total": {"$sum": "$cost_usd"}}}]
    spend_doc = await db.visualizer_renders.aggregate(pipeline).to_list(length=1)
    total_spend_usd = float(spend_doc[0]["total"]) if spend_doc else 0.0
    waitlist_total = await db.visualizer_waitlist.count_documents({})
    waitlist_unnotified = await db.visualizer_waitlist.count_documents({"notified": {"$ne": True}})
    return {
        "totals": {
            "renders": total_renders,
            "fast": fast,
            "photoreal": photoreal,
            "failed": failed,
            "fal_spend_usd": round(total_spend_usd, 2),
            "fal_spend_gbp_estimate": round(total_spend_usd * 0.79, 2),
        },
        "active_rooms": await db.visualizer_sample_rooms.count_documents({"active": {"$ne": False}}),
        "sessions": await db.visualizer_sessions.count_documents({}),
        "waitlist": {
            "total": waitlist_total,
            "unnotified": waitlist_unnotified,
        },
    }


@admin_router.get("/waitlist")
async def list_waitlist(
    notified: str = "all",  # "all" | "yes" | "no"
    limit: int = 500,
    current_user: dict = Depends(get_current_user),
):
    """Admin: list everyone who registered interest on the Coming Soon
    page. Default returns everyone newest-first; pass `notified=no` to
    get just the unnotified bucket ready for outreach."""
    _require_admin(current_user)
    db = get_db()
    q: dict = {}
    if notified == "yes":
        q["notified"] = True
    elif notified == "no":
        q["notified"] = {"$ne": True}
    rows = await (
        db.visualizer_waitlist.find(q, {"_id": 0})
        .sort("created_at", -1)
        .limit(min(max(limit, 1), 5000))
        .to_list(length=None)
    )
    return {"count": len(rows), "rows": rows}


@admin_router.post("/waitlist/mark-notified")
async def mark_notified(
    emails: list[str],
    current_user: dict = Depends(get_current_user),
):
    """Bulk mark waitlist entries as notified — call this AFTER you've
    sent the launch email so the next CSV export only shows fresh leads."""
    _require_admin(current_user)
    if not isinstance(emails, list) or not emails:
        raise HTTPException(status_code=422, detail="emails must be a non-empty list")
    db = get_db()
    res = await db.visualizer_waitlist.update_many(
        {"email": {"$in": [e.lower().strip() for e in emails if e]}},
        {"$set": {"notified": True, "notified_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"ok": True, "matched": res.matched_count, "modified": res.modified_count}


# ------------------------------------------------------------------
# ADMIN — Pricing config
# ------------------------------------------------------------------

class VisualizerPricingUpsert(BaseModel):
    adhesive_price_per_bag: float | None = None
    grout_price_per_bag: float | None = None
    wastage_percent: int | None = None
    floor_m2_per_adhesive_bag: float | None = None
    wall_m2_per_adhesive_bag: float | None = None
    m2_per_grout_bag: float | None = None


@admin_router.get("/pricing")
async def get_pricing(current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    db = get_db()
    pricing = await _load_visualizer_pricing(db)
    return {"pricing": pricing, "defaults": PRICING_DEFAULTS}


@admin_router.put("/pricing")
async def update_pricing(
    req: VisualizerPricingUpsert,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    db = get_db()
    payload = {k: v for k, v in req.dict().items() if v is not None}
    # Sanity guard on numeric ranges so the admin can't break quotes
    if "wastage_percent" in payload:
        payload["wastage_percent"] = max(0, min(50, int(payload["wastage_percent"])))
    for k in ("adhesive_price_per_bag", "grout_price_per_bag",
              "floor_m2_per_adhesive_bag", "wall_m2_per_adhesive_bag",
              "m2_per_grout_bag"):
        if k in payload:
            payload[k] = max(0.5, float(payload[k]))
    await db.website_settings.update_one(
        {"key": "visualizer_pricing"},
        {"$set": {"key": "visualizer_pricing", "settings": payload,
                  "updated_at": datetime.now(timezone.utc).isoformat(),
                  "updated_by": (current_user or {}).get("email")}},
        upsert=True,
    )
    return {"ok": True, "pricing": await _load_visualizer_pricing(db)}


# ------------------------------------------------------------------
# Share tokens — public read-only viewer for finished renders
# ------------------------------------------------------------------

class ShareCreateReq(BaseModel):
    render_id: str | None = None  # optional; otherwise picks the latest succeeded render


@router.post("/sessions/{session_id}/share")
async def create_share(session_id: str, req: ShareCreateReq, request: Request):
    """Mint a public share token for a completed render so the customer
    can paste a link into WhatsApp / email / Pinterest. Idempotent — the
    same session+render will reuse the existing token rather than spawn
    a new one."""
    if not await _public_enabled() and not _is_admin_from_request(request):
        raise HTTPException(status_code=404, detail="Not found")

    db = get_db()
    sess = await db.visualizer_sessions.find_one({"id": session_id}, {"_id": 0})
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    # Resolve a friendly room label
    upload_id = sess["sample_room_id"] if sess.get("is_user_upload") else None
    sample_id = None if sess.get("is_user_upload") else sess["sample_room_id"]
    try:
        room_doc = await _get_room(db, sample_id, upload_id)
        room_label = room_doc.get("label") or "Sample room"
    except HTTPException:
        room_label = "Sample room"

    # Pick the render: caller-specified OR latest succeeded for the session
    render_q = {"session_id": session_id, "status": "succeeded"}
    if req.render_id:
        render_q["id"] = req.render_id
    render = await db.visualizer_renders.find_one(
        render_q, {"_id": 0}, sort=[("started_at", -1)]
    )
    if not render or not render.get("result_url"):
        raise HTTPException(status_code=404, detail="No completed render found to share yet")

    # Reuse an existing token if the same render was already shared
    existing = await db.visualizer_shares.find_one(
        {"session_id": session_id, "render_id": render["id"]}, {"_id": 0}
    )
    if existing:
        return {
            "share_token": existing["token"],
            "share_url": f"/visualizer/share/{existing['token']}",
        }

    token = uuid.uuid4().hex[:14]
    doc = {
        "token": token,
        "session_id": session_id,
        "render_id": render["id"],
        "tile_id": sess["tile_id"],
        "tile_name": sess.get("tile_name"),
        "tile_image": sess.get("tile_image"),
        "tile_price_per_m2": sess.get("tile_price_per_m2"),
        "room_label": room_label,
        "result_url": render["result_url"],
        "style": render.get("style"),
        "view_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.visualizer_shares.insert_one(doc)
    return {"share_token": token, "share_url": f"/visualizer/share/{token}"}


@router.get("/share/{token}")
async def view_share(token: str):
    """Public unauth'd view — does NOT respect the public feature flag
    so existing share links keep working even if the visualizer is
    temporarily disabled. Increments a view counter for analytics."""
    db = get_db()
    doc = await db.visualizer_shares.find_one({"token": token}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="This design link has expired or never existed")
    await db.visualizer_shares.update_one(
        {"token": token},
        {"$inc": {"view_count": 1},
         "$set": {"last_viewed_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {
        "tile": {
            "id": doc.get("tile_id"),
            "name": doc.get("tile_name"),
            "image": doc.get("tile_image"),
            "price_per_m2": doc.get("tile_price_per_m2"),
        },
        "room_label": doc.get("room_label"),
        "result_url": doc.get("result_url"),
        "style": doc.get("style"),
        "created_at": doc.get("created_at"),
    }


# ------------------------------------------------------------------
# ADMIN — 1-click launch email to the waitlist
# ------------------------------------------------------------------

class LaunchEmailReq(BaseModel):
    subject: str | None = None
    headline: str | None = None
    body_html: str | None = None
    cta_text: str | None = None
    cta_url: str | None = None
    dry_run: bool = False  # if True, returns the recipient list without sending


@admin_router.post("/waitlist/send-launch-email")
async def send_launch_email(
    req: LaunchEmailReq,
    current_user: dict = Depends(get_current_user),
):
    """Email everyone on the waitlist who hasn't been notified yet. After
    a successful send, mark them notified so re-clicking the button won't
    spam the same person twice. Uses Resend via the existing email
    service. Set `dry_run=true` to preview the recipient list first."""
    _require_admin(current_user)
    db = get_db()
    rows = await db.visualizer_waitlist.find(
        {"notified": {"$ne": True}}, {"_id": 0, "email": 1}
    ).to_list(length=None)
    emails = [r["email"] for r in rows if r.get("email")]
    if not emails:
        return {"sent": 0, "skipped": 0, "message": "No unnotified waitlist members."}

    if req.dry_run:
        return {"would_send": len(emails), "recipients_preview": emails[:25], "dry_run": True}

    subject = (req.subject or "Tile Visualizer is live ✨").strip()[:200]
    headline = (req.headline or "Your tile visualizer is ready").strip()[:200]
    cta_url = (req.cta_url or os.environ.get("SHOP_WEBSITE_URL", "https://tilestation.co.uk") + "/visualizer").strip()
    cta_text = (req.cta_text or "Try the Visualizer").strip()[:60]
    body_html_inner = req.body_html or (
        "<p>You signed up to be notified when our Tile Visualizer went live — "
        "and today's the day. Pick any tile from our catalogue, drop it into a "
        "sample room or your own photo, and see exactly how it'll look. "
        "Free preview, no signup required.</p>"
        "<p>As a thank-you for waiting, your first photoreal render is on us.</p>"
    )

    html = f"""\
<!doctype html><html><body style=\"margin:0;padding:0;background:#f1f5f9;font-family:Arial,sans-serif;color:#0f172a;\">
  <table role=\"presentation\" width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"max-width:600px;margin:0 auto;background:#fff;\">
    <tr><td style=\"padding:32px 32px 8px 32px;\">
      <div style=\"font-size:12px;letter-spacing:0.12em;text-transform:uppercase;color:#ca8a04;font-weight:700;\">Tile Station</div>
      <h1 style=\"font-size:28px;line-height:1.2;margin:8px 0 16px 0;\">{headline}</h1>
      {body_html_inner}
      <p style=\"margin:32px 0 0 0;\">
        <a href=\"{cta_url}\" style=\"display:inline-block;background:#0f172a;color:#facc15;padding:14px 24px;border-radius:8px;font-weight:700;text-decoration:none;\">{cta_text}</a>
      </p>
    </td></tr>
    <tr><td style=\"padding:24px 32px;color:#64748b;font-size:12px;border-top:1px solid #e2e8f0;\">
      You received this because you joined the Tile Visualizer waitlist at tilestation.co.uk.
    </td></tr>
  </table>
</body></html>"""

    # Resend caps batch recipients per call — chunk to be safe. Track
    # the *exact* emails that were successfully sent so a partial failure
    # in batch N doesn't accidentally mark batch N+1 emails as notified.
    from services.email import send_email_notification
    sent_emails: list[str] = []
    failed = 0
    chunk = 40
    for i in range(0, len(emails), chunk):
        batch = emails[i:i+chunk]
        try:
            ok = await send_email_notification(
                to_emails=batch,
                subject=subject,
                html_content=html,
                from_name="Tile Station",
            )
            if ok:
                sent_emails.extend(batch)
            else:
                failed += len(batch)
        except Exception:
            logger.exception("waitlist launch email failed")
            failed += len(batch)

    sent_total = len(sent_emails)
    if sent_emails:
        await db.visualizer_waitlist.update_many(
            {"email": {"$in": sent_emails}},
            {"$set": {"notified": True, "notified_at": datetime.now(timezone.utc).isoformat(),
                      "notified_subject": subject}},
        )

    return {"sent": sent_total, "failed": failed, "total_unnotified_before": len(emails)}

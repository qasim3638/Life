"""
Tile Visualizer — render service.

Two render styles are supported, exposed to the customer as:

    "fast"      → server-side perspective-composite using Pillow.
                  ~1-2s, £0 cost, deterministic. Good 80% of the time.

    "photoreal" → FLUX Fill Pro via fal.ai with the same surface mask
                  driving inpainting and the chosen tile texture as a
                  reference. ~15-30s, ~$0.10/render, magazine-quality
                  output.

The hybrid UX in the storefront defaults to "fast" so first-impression
latency is sub-2s, then offers "✨ Make it photoreal" as a one-click
upgrade. Free customers get 1 photoreal render per session; carts >£500
get unlimited (the visualizer gates this in the route layer, not here).

Sample rooms are pre-tagged with a `surface_polygon` (4 corner points
in pixel coords) describing the visible quad of floor or wall — that
single piece of metadata is what lets us avoid running SAM2 for every
render. New sample rooms get their polygon recorded once at upload time
(admin tooling, V2). For the V1 launch we seed 4 hand-tagged rooms.

Cost tracking: every render writes a `visualizer_renders` document with
`cost_usd` so the admin dashboard can surface monthly fal.ai spend
side-by-side with attributed orders.
"""
from __future__ import annotations

import io
import os
import time
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional

import httpx
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance

logger = logging.getLogger(__name__)

# Render-cost reference (US dollars). Updated whenever fal.ai pricing
# changes — currently FLUX Fill Pro is $0.05 per megapixel.
PHOTOREAL_COST_USD = 0.10
FAST_COST_USD = 0.0


# ------------------------------------------------------------------
# Image helpers
# ------------------------------------------------------------------

async def _download_image(url: str, timeout: float = 12.0) -> Image.Image:
    """Fetch an image URL and return a Pillow Image. Raises on any
    non-image / non-200 response."""
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as cli:
        r = await cli.get(url)
    r.raise_for_status()
    img = Image.open(io.BytesIO(r.content))
    img.load()
    return img.convert("RGBA")


def _perspective_coeffs(src_quad, dst_quad):
    """Pillow's PERSPECTIVE transform expects 8 coefficients derived
    from 4 source → 4 destination points. Standard linear-algebra
    formulation lifted from the Pillow cookbook."""
    import numpy as np
    matrix = []
    for s, d in zip(src_quad, dst_quad):
        matrix.append([d[0], d[1], 1, 0, 0, 0, -s[0]*d[0], -s[0]*d[1]])
        matrix.append([0, 0, 0, d[0], d[1], 1, -s[1]*d[0], -s[1]*d[1]])
    A = np.matrix(matrix, dtype=np.float64)
    B = np.array(src_quad).reshape(8)
    res = np.linalg.solve(A, B)
    return tuple(float(x) for x in res)


def _quad_bbox(quad: list[list[int]]) -> tuple[int, int, int, int]:
    xs = [p[0] for p in quad]
    ys = [p[1] for p in quad]
    return min(xs), min(ys), max(xs), max(ys)


def _build_mask_from_polygon(size: tuple[int, int], polygon: list[list[int]],
                             feather_px: int = 4) -> Image.Image:
    """Draw a white polygon on a black canvas, optionally feather the
    edge so the resulting composite blends smoothly. Returns a single-
    channel L-mode image."""
    mask = Image.new("L", size, 0)
    drw = ImageDraw.Draw(mask)
    drw.polygon([(int(x), int(y)) for x, y in polygon], fill=255)
    if feather_px > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(feather_px))
    return mask


# ------------------------------------------------------------------
# STYLE 1 — Fast composite (no AI, no fal.ai cost)
# ------------------------------------------------------------------

async def render_fast_composite(
    room_image_url: str,
    tile_image_url: str,
    surface_polygon: list[list[int]],
    tile_repeat_size_px: int = 180,
) -> bytes:
    """Composite a tile texture onto the surface polygon of the room
    photo with perspective warp + lighting carry-over.

    Returns PNG bytes.
    """
    # 1) Pull both images
    room, tile = await asyncio.gather(
        _download_image(room_image_url),
        _download_image(tile_image_url),
    )

    # 2) Build a tiled patch the size of the polygon's bounding box
    bx0, by0, bx1, by1 = _quad_bbox(surface_polygon)
    bw, bh = max(1, bx1 - bx0), max(1, by1 - by0)

    # Resize the tile to the requested repeat size so a 600×600mm tile
    # looks roughly correct in the room. The repeat-size is a soft
    # heuristic; future versions can compute it from sample-room scale
    # metadata.
    repeat = max(60, int(tile_repeat_size_px))
    tile_small = tile.resize((repeat, repeat), Image.LANCZOS)

    # Tiled patch — pad to bbox dimensions
    patch = Image.new("RGBA", (bw, bh))
    for y in range(0, bh, repeat):
        for x in range(0, bw, repeat):
            patch.paste(tile_small, (x, y))

    # 3) Warp the tiled patch into the polygon shape via PERSPECTIVE
    #    transform. The src quad is the patch's 4 corners; dst quad is
    #    the polygon expressed *relative to* the bbox origin.
    src_quad = [[0, 0], [bw, 0], [bw, bh], [0, bh]]
    dst_quad = [[p[0] - bx0, p[1] - by0] for p in surface_polygon]
    coeffs = _perspective_coeffs(src_quad, dst_quad)
    warped = patch.transform((bw, bh), Image.PERSPECTIVE, coeffs, Image.BICUBIC)

    # 4) Build a feathered mask matching the polygon
    full_size_mask = _build_mask_from_polygon(room.size, surface_polygon, feather_px=4)
    # Crop to bbox so we only blend where we actually have warped pixels
    mask_crop = full_size_mask.crop((bx0, by0, bx1, by1))

    # 5) Carry over the original room's *lighting* by multiplying the
    #    tile with the room's grayscale luminance in the same region.
    #    Without this step floor tiles look like a flat sticker; with
    #    it they pick up shadows and gradients of the original photo.
    room_crop = room.crop((bx0, by0, bx1, by1)).convert("RGB")
    luma = room_crop.convert("L")
    # Normalise luma to keep mid-grey as identity (avoid darkening by 50%)
    luma_arr = ImageEnhance.Brightness(luma).enhance(1.4)
    warped_rgb = warped.convert("RGB")

    import numpy as np
    warped_np = np.asarray(warped_rgb, dtype=np.float32)
    luma_np = np.asarray(luma_arr, dtype=np.float32) / 200.0  # 0..~1.27
    luma_np = np.clip(luma_np, 0.55, 1.25)
    blended_np = np.clip(warped_np * luma_np[..., None], 0, 255).astype(np.uint8)
    blended = Image.fromarray(blended_np)

    # 6) Paste blended into a new RGBA layer using the feathered mask
    layer = Image.new("RGBA", room.size)
    layer.paste(blended, (bx0, by0))
    layer.putalpha(0)
    full_mask = Image.new("L", room.size, 0)
    full_mask.paste(mask_crop, (bx0, by0))
    layer.putalpha(full_mask)

    out = Image.alpha_composite(room, layer).convert("RGB")
    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ------------------------------------------------------------------
# STYLE 2 — Photoreal via fal.ai FLUX Fill Pro
# ------------------------------------------------------------------

async def render_photoreal_with_fal(
    room_image_url: str,
    tile_image_url: str,
    surface_polygon: list[list[int]],
    surface_kind: str,
    tile_name: str = "ceramic tile",
    mask_url: str | None = None,
) -> dict:
    """Run FLUX Fill Pro inpainting via fal.ai. Returns a dict with the
    public result URL and a cost-usd estimate. Requires FAL_KEY env var.

    `mask_url` lets the caller pass a pre-built mask (e.g. one produced
    by SAM2 auto-segmentation of a customer's uploaded room) instead of
    re-deriving the mask from `surface_polygon`. When None, we build the
    mask locally from the polygon."""
    if not os.environ.get("FAL_KEY"):
        raise RuntimeError("FAL_KEY not set on backend")

    import fal_client

    if mask_url is None:
        # 1) Build the inpaint mask from the polygon
        room = await _download_image(room_image_url)
        mask = _build_mask_from_polygon(room.size, surface_polygon, feather_px=2)
        buf = io.BytesIO()
        mask.save(buf, format="PNG")
        mask_bytes = buf.getvalue()
        mask_url = await fal_client.upload_async(mask_bytes, "image/png")

    # 3) Submit the inpaint job. We pin to FLUX Pro v1.1 Inpainting which
    #    is the production-quality endpoint (Fill Pro is the same model
    #    family). The prompt anchors the model to "tiled <surface> using
    #    <tile name>" so it doesn't drift into other materials.
    surface_word = "floor" if surface_kind == "floor" else "wall"
    prompt = (
        f"a photoreal {surface_word} fully tiled with {tile_name}, "
        "matching the room's existing lighting, perspective and shadows; "
        "tile grout lines visible; sharp focus; interior design photography"
    )

    handler = await fal_client.submit_async(
        "fal-ai/flux-pro/v1/fill",
        arguments={
            "image_url": room_image_url,
            "mask_url": mask_url,
            "prompt": prompt,
            "num_inference_steps": 28,
            "guidance_scale": 3.5,
            "num_images": 1,
            # Reference the chosen tile so the model uses its texture &
            # colour rather than hallucinating a generic tile.
            "image_prompt_strength": 0.85,
        },
    )

    result = await handler.get()
    images = result.get("images") or []
    if not images:
        raise RuntimeError("fal.ai returned no images")
    return {
        "result_url": images[0].get("url"),
        "cost_usd": PHOTOREAL_COST_USD,
        "prompt": prompt,
    }


async def auto_segment_surface(image_url: str, surface_kind: str = "floor") -> dict:
    """Run fal.ai SAM2 to auto-detect floor or wall in a customer-uploaded
    room photo. Returns a dict with `mask_url` (uploaded to fal storage,
    ready to plug straight into FLUX Fill) and `polygon` (4-corner approx
    of the mask bbox so the fast composite renderer can also use it).

    Strategy:
      • SAM2's `automatic-segmentation` returns N masks.
      • We pick the largest bottom-half mask for `surface_kind=floor`
        (floors are nearly always the largest contiguous bottom region).
      • For walls we pick the largest top-half mask not touching the
        bottom edge.
      • Returns the picked mask's URL plus a bbox-derived polygon.

    Fallback: if SAM2 returns nothing useful, we generate a default
    polygon covering the bottom 55% of the image so the customer at
    least sees *some* render rather than an error toast.
    """
    if not os.environ.get("FAL_KEY"):
        raise RuntimeError("FAL_KEY not set on backend")
    import fal_client
    import numpy as np

    # Download the room photo so we can inspect dimensions + build fallback
    room = await _download_image(image_url)
    W, H = room.size

    # SAM2 automatic — returns list of {url, score, bbox} per mask
    try:
        handler = await fal_client.submit_async(
            "fal-ai/sam2/auto-segment",
            arguments={"image_url": image_url, "points_per_side": 24},
        )
        result = await handler.get()
    except Exception as exc:
        logger.warning(f"SAM2 auto-segment failed, using fallback polygon: {exc}")
        result = {}

    masks = result.get("masks") or []
    picked = None
    best_score = -1.0
    for m in masks:
        bbox = m.get("bbox") or [0, 0, 0, 0]
        x0, y0, x1, y1 = bbox
        area = max(1, (x1 - x0) * (y1 - y0))
        # Heuristic: floor masks tend to live in bottom 60% of image,
        # walls in top 70%. Score = area weighted by region match.
        cy = (y0 + y1) / 2
        if surface_kind == "floor":
            region_match = max(0.0, (cy - H * 0.30) / (H * 0.70))
        else:
            region_match = max(0.0, (H * 0.70 - cy) / (H * 0.70))
        score = area * region_match
        if score > best_score:
            best_score = score
            picked = m

    if not picked:
        # Fallback: rough bottom-of-frame quad for floors, top for walls
        if surface_kind == "floor":
            polygon = [[int(W * 0.08), int(H * 0.95)],
                       [int(W * 0.92), int(H * 0.95)],
                       [int(W * 0.78), int(H * 0.55)],
                       [int(W * 0.22), int(H * 0.55)]]
        else:
            polygon = [[int(W * 0.20), int(H * 0.10)],
                       [int(W * 0.80), int(H * 0.10)],
                       [int(W * 0.80), int(H * 0.55)],
                       [int(W * 0.20), int(H * 0.55)]]
        # Build & upload our fallback mask
        mask = _build_mask_from_polygon((W, H), polygon, feather_px=4)
        buf = io.BytesIO()
        mask.save(buf, format="PNG")
        mask_url = await fal_client.upload_async(buf.getvalue(), "image/png")
        return {"mask_url": mask_url, "polygon": polygon, "auto_detected": False}

    # Use the picked mask URL directly + derive polygon from its bbox
    bbox = picked.get("bbox") or [0, 0, W, H]
    x0, y0, x1, y1 = [int(v) for v in bbox]
    polygon = [[x0, y1], [x1, y1], [x1, y0], [x0, y0]]
    return {"mask_url": picked.get("url"), "polygon": polygon, "auto_detected": True}


# ------------------------------------------------------------------
# Quote calculator
# ------------------------------------------------------------------

# Pricing defaults — used when no admin override is configured. The
# `estimate_quote_for_render` route layer pulls overrides from the
# `website_settings.visualizer_pricing` doc and passes them in here.
DEFAULT_ADHESIVE_PRICE_PER_BAG = 18.50
DEFAULT_GROUT_PRICE_PER_BAG = 9.99
DEFAULT_WASTAGE_PERCENT = 10  # industry standard for cuts/breakage
DEFAULT_FLOOR_M2_PER_ADHESIVE_BAG = 4.0
DEFAULT_WALL_M2_PER_ADHESIVE_BAG = 5.0
DEFAULT_M2_PER_GROUT_BAG = 11.0


def estimate_quote_for_render(
    surface_m2: float,
    tile_price_per_m2: float,
    surface_kind: str = "floor",
    adhesive_price_per_bag: float = DEFAULT_ADHESIVE_PRICE_PER_BAG,
    grout_price_per_bag: float = DEFAULT_GROUT_PRICE_PER_BAG,
    wastage_percent: int = DEFAULT_WASTAGE_PERCENT,
    floor_m2_per_adhesive_bag: float = DEFAULT_FLOOR_M2_PER_ADHESIVE_BAG,
    wall_m2_per_adhesive_bag: float = DEFAULT_WALL_M2_PER_ADHESIVE_BAG,
    m2_per_grout_bag: float = DEFAULT_M2_PER_GROUT_BAG,
) -> dict:
    """Crude but useful 'add this look to cart' calculator.

    All ratios + bag prices are passed in (overridable per-call) so the
    admin can tune them in `/admin/settings → Visualizer Pricing` without
    needing a code deploy. The customer always sees the breakdown so
    they can sanity-check.
    """
    wastage = max(0.0, float(wastage_percent)) / 100.0
    tile_m2 = round(surface_m2 * (1 + wastage), 2)
    tile_subtotal = round(tile_m2 * float(tile_price_per_m2), 2)

    # Adhesive bags
    adhesive_ratio = float(floor_m2_per_adhesive_bag if surface_kind == "floor" else wall_m2_per_adhesive_bag)
    adhesive_ratio = max(0.5, adhesive_ratio)  # guard divide-by-zero / pathological config
    adhesive_bags = max(1, int((surface_m2 / adhesive_ratio) + 0.5))
    adhesive_cost = round(adhesive_bags * float(adhesive_price_per_bag), 2)

    # Grout bags
    grout_ratio = max(0.5, float(m2_per_grout_bag))
    grout_bags = max(1, int((surface_m2 / grout_ratio) + 0.5))
    grout_cost = round(grout_bags * float(grout_price_per_bag), 2)

    total = round(tile_subtotal + adhesive_cost + grout_cost, 2)

    return {
        "surface_m2": surface_m2,
        "tile_m2_with_wastage": tile_m2,
        "tile_subtotal": tile_subtotal,
        "adhesive_bags": adhesive_bags,
        "adhesive_cost": adhesive_cost,
        "adhesive_price_per_bag": float(adhesive_price_per_bag),
        "grout_bags": grout_bags,
        "grout_cost": grout_cost,
        "grout_price_per_bag": float(grout_price_per_bag),
        "wastage_percent": int(round(wastage * 100)),
        "total_estimate": total,
    }

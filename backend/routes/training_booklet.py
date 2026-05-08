"""
Staff Training Booklet — DB-backed editable notes + on-demand PDF.

Architecture:
  - `training_booklet_content` collection holds editable notes keyed by
    section_id (e.g. "welcome", "refund_golden_rule"). Super-admin edits
    these via the admin page; the PDF generator pulls them on regenerate.
  - `training_booklet_images` collection holds optional image overrides
    keyed by screenshot slug (e.g. "32_epos_till"). Super-admin can upload
    a replacement PNG/JPEG; the regenerate step writes overrides to
    /app/checklists/training_screens_compressed/<slug>.jpg before the PDF
    builder runs, so the build script doesn't need to know about overrides.
  - The structural booklet (titles, step lists) stays in
    `build_training_booklet.py` — only the *notes* and *images* are
    user-editable.
  - Hot-swappable: regenerating the PDF replaces the file at
    /app/checklists/Staff_Training_Booklet.pdf so the existing
    /api/website-admin/maintenance/checklists download endpoint and the
    public /checklists/ static path both serve the latest version.

Endpoints:
  GET    /api/training-booklet/sections           — list all editable notes
  PUT    /api/training-booklet/sections/{key}     — edit one (super_admin)
  GET    /api/training-booklet/images             — list slugs + override flag
  POST   /api/training-booklet/images/{slug}      — upload override (super_admin)
  DELETE /api/training-booklet/images/{slug}      — restore default (super_admin)
  POST   /api/training-booklet/regenerate         — rebuild PDF (super_admin)
  GET    /api/training-booklet/download.pdf       — stream the current PDF
"""
import logging
import os
import pathlib
import shutil
import subprocess
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel

from routes.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/training-booklet", tags=["Training Booklet"])

# Directory of the canonical (default) screenshots. Originals live here and
# we keep an "overrides applied" mirror in the same dir so the build script
# can stay dumb.
SCREENS_DIR = pathlib.Path("/app/checklists/training_screens_compressed")
ORIGINALS_DIR = pathlib.Path("/app/checklists/training_screens_originals")

MAX_IMAGE_BYTES = 4 * 1024 * 1024  # 4 MB safety limit per image
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}

# Defaults — used to seed the DB on first run, also act as fallback if a row
# is ever missing. KEEP IN SYNC with the placeholders in build_training_booklet.py.
DEFAULT_SECTIONS = {
    "welcome": {
        "label": "Welcome paragraph",
        "description": "First paragraph customers see on the introduction page.",
        "content": (
            "This is your <b>complete operations manual</b>. Every feature you will use during a normal "
            "shift is documented here with real screenshots and step-by-step instructions. "
            "Configuration / settings pages (managers only) are <b>NOT</b> covered."
        ),
    },
    "refund_golden_rule": {
        "label": "Refund golden rule",
        "description": "The single most important rule shown at the top of Part 6.",
        "content": (
            "<b>A refund must always be linked to an invoice.</b> This is the golden rule. "
            "Never process a 'standalone' refund — it breaks the audit trail and the manager will not "
            "be able to reconcile the till at end of day."
        ),
    },
    "refund_no_invoice_warn": {
        "label": "Refund without invoice — warning",
        "description": "What staff should do when a customer has no invoice.",
        "content": (
            "If a customer wants money back but you cannot find their invoice, do NOT issue cash. "
            "Take their details, raise it with a manager, and tell the customer you'll call back "
            "within 24 hours. Manager approval is required for any refund without an invoice."
        ),
    },
    "trade_pricing_tip": {
        "label": "Trade pricing reminder",
        "description": "How trade prices appear automatically.",
        "content": (
            "Don't manually type prices unless the manager has approved a discount. The till already "
            "knows trade prices for trade customers — they appear automatically once the trade customer "
            "is selected."
        ),
    },
    "cash_variance_warn": {
        "label": "Cash variance warning",
        "description": "What to do if the cash drawer total doesn't match.",
        "content": (
            "Never pocket the variance — even small amounts. Always declare and explain. "
            "The system records every count, and managers cross-check against till logs daily."
        ),
    },
    "delivery_promise_warn": {
        "label": "Delivery time promises",
        "description": "What staff should NOT promise customers about delivery times.",
        "content": (
            "Never promise a delivery time you can't see in the system. Drivers don't update times "
            "manually — they're set by the warehouse plan."
        ),
    },
    "abandoned_baskets_tip": {
        "label": "Abandoned baskets opportunity",
        "description": "Why abandoned baskets are valuable leads.",
        "content": (
            "Best lead source you have. Always call the high-value baskets (£500+) within 24 hours — "
            "conversion rate is ~30%."
        ),
    },
    "inbox_response_time": {
        "label": "Inbox response time",
        "description": "Customer-email reply expectations.",
        "content": (
            "Always reply within 24 hours. Older than that = customers escalate to phone calls. "
            "The manager sees the unread queue daily."
        ),
    },
    "golden_rules": {
        "label": "Golden rules (10 rules)",
        "description": "The full list of golden rules at the back of the booklet. Use HTML <br/> for line breaks if needed; one rule per line.",
        "content": (
            "1. Every refund must be linked to its invoice. <b>No exceptions.</b>\n"
            "2. Always log out at end of shift.\n"
            "3. Never share your password — even with a colleague.\n"
            "4. If you don't know, call a manager. Don't guess.\n"
            "5. Be polite even when wrong has been done — every word is recorded.\n"
            "6. Always check stock + batch before promising a customer extra tiles for a job in progress.\n"
            "7. Card refunds take 3–5 working days. Tell every customer this so they don't worry.\n"
            "8. Trade prices apply automatically once the trade customer is selected — never type the discount manually.\n"
            "9. If the system is slow or seems wrong, screenshot the page and message the manager. Don't keep clicking — you may double-charge.\n"
            "10. Sample orders (£1) are not for staff perks. They're customer service. Don't take samples for personal use."
        ),
    },
}

# ----------------------- DB plumbing -----------------------
_mongo_url = os.environ.get("MONGO_URL")
_db_name = os.environ.get("DB_NAME")
_client = AsyncIOMotorClient(_mongo_url) if _mongo_url else None
_db = _client[_db_name] if _client and _db_name else None


async def _seed_defaults_if_empty():
    """Idempotent — seeds default text on first run; never overwrites edits."""
    if _db is None:
        return
    for key, meta in DEFAULT_SECTIONS.items():
        existing = await _db.training_booklet_content.find_one({"_id": key})
        if existing is None:
            await _db.training_booklet_content.insert_one({
                "_id": key,
                "label": meta["label"],
                "description": meta["description"],
                "content": meta["content"],
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "updated_by": "system",
            })


def _strip_id(doc):
    if doc is None:
        return None
    return {k: v for k, v in doc.items() if k != "_id"} | {"key": doc.get("_id")}


# ----------------------- Endpoints -----------------------
@router.get("/sections")
async def list_sections(current_user: dict = Depends(get_current_user)):
    """Returns every editable note. Available to all admins/managers (so a
    manager can read the current text), but only super_admin can edit."""
    if current_user.get("role") not in ("super_admin", "admin", "manager"):
        raise HTTPException(status_code=403, detail="Not authorized")

    await _seed_defaults_if_empty()
    rows = await _db.training_booklet_content.find({}).sort("_id", 1).to_list(length=None)
    # Order by the canonical key list so the editor renders in a sensible order.
    by_key = {r["_id"]: r for r in rows}
    ordered = [_strip_id(by_key[k]) for k in DEFAULT_SECTIONS if k in by_key]
    can_edit = current_user.get("role") == "super_admin"
    return {"sections": ordered, "can_edit": can_edit}


class SectionUpdate(BaseModel):
    content: str


@router.put("/sections/{key}")
async def update_section(
    key: str,
    payload: SectionUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Super-admin only — edit the text of one section."""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin only")

    if key not in DEFAULT_SECTIONS:
        raise HTTPException(status_code=404, detail=f"Unknown section: {key}")

    new_content = (payload.content or "").strip()
    if not new_content:
        raise HTTPException(status_code=400, detail="Content cannot be empty")
    if len(new_content) > 5000:
        raise HTTPException(status_code=400, detail="Content too long (5000 char max)")

    now_iso = datetime.now(timezone.utc).isoformat()
    await _db.training_booklet_content.update_one(
        {"_id": key},
        {"$set": {
            "content": new_content,
            "updated_at": now_iso,
            "updated_by": current_user.get("email"),
            # Keep label/description in sync with defaults in case schema evolves
            "label": DEFAULT_SECTIONS[key]["label"],
            "description": DEFAULT_SECTIONS[key]["description"],
        }},
        upsert=True,
    )
    doc = await _db.training_booklet_content.find_one({"_id": key})
    return _strip_id(doc)


@router.post("/regenerate")
async def regenerate_booklet(current_user: dict = Depends(get_current_user)):
    """Re-runs build_training_booklet.py with the current DB content. Super-admin only.

    Before running the build script, applies any image overrides from the DB
    to the screenshots dir on disk so the builder picks them up.
    """
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin only")

    # Step 1 — sync image overrides to disk
    try:
        await _apply_image_overrides_to_disk()
    except Exception as exc:
        logger.warning(f"Image override sync failed (continuing anyway): {exc}")

    import sys
    try:
        # Use the SAME Python interpreter we're running under so reportlab,
        # PIL, motor etc. are all available (the system /usr/bin/python3 doesn't
        # have them).
        result = subprocess.run(
            [sys.executable, "/app/checklists/build_training_booklet.py"],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"Build failed: {result.stderr[:300]}",
            )
        # Copy to public folder so the no-auth download URL serves the new version
        pdf = pathlib.Path("/app/checklists/Staff_Training_Booklet.pdf")
        public = pathlib.Path("/app/frontend/public/checklists/Staff_Training_Booklet.pdf")
        if pdf.exists():
            try:
                public.parent.mkdir(parents=True, exist_ok=True)
                public.write_bytes(pdf.read_bytes())
            except Exception as exc:
                logger.warning(f"Could not copy PDF to public/: {exc}")
        return {
            "success": True,
            "size_bytes": pdf.stat().st_size if pdf.exists() else 0,
            "regenerated_at": datetime.now(timezone.utc).isoformat(),
            "stdout": result.stdout.strip()[-200:],
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Build timed out (>120 s)")


@router.get("/download.pdf")
async def download_booklet(current_user: dict = Depends(get_current_user)):
    """Streams the current PDF. Available to any logged-in admin or staff."""
    if current_user.get("role") not in ("super_admin", "admin", "manager", "staff", "showroom"):
        raise HTTPException(status_code=403, detail="Not authorized")

    pdf = pathlib.Path("/app/checklists/Staff_Training_Booklet.pdf")
    if not pdf.exists():
        raise HTTPException(
            status_code=404,
            detail="Booklet not generated yet — click 'Regenerate' on the editor page.",
        )
    return FileResponse(
        path=str(pdf),
        media_type="application/pdf",
        filename="TileStation_Staff_Training_Booklet.pdf",
    )


# ─────────────────────────────────────────────────────────────────────────────
# IMAGE OVERRIDES — super_admin can swap any of the 60+ booklet screenshots
# ─────────────────────────────────────────────────────────────────────────────
# The set of slugs known to the booklet. Pulled directly from
# capture_training_screens.py so the editor stays in sync if a new screen is
# added there. Keep grouped + ordered for the admin grid.
IMAGE_SLUG_GROUPS = [
    ("Storefront", [
        ("01_storefront_home", "Homepage"),
        ("02_storefront_catalog", "Catalogue (/shop/tiles)"),
        ("03_storefront_pdp", "Product detail page"),
        ("04_storefront_calculator", "Tile calculator"),
        ("05_storefront_samples", "Tile samples"),
        ("06_storefront_sample_svc", "Sample service"),
        ("07_storefront_cart", "Cart"),
        ("08_storefront_wishlist", "Wishlist"),
        ("09_storefront_compare", "Compare"),
        ("10_storefront_checkout", "Checkout"),
        ("11_storefront_track", "Order tracking"),
        ("12_storefront_login", "Customer login"),
        ("13_storefront_register", "Customer register"),
        ("14_storefront_trade_reg", "Trade register"),
        ("15_storefront_trade_login", "Trade login"),
        ("16_storefront_refer", "Refer-a-friend"),
        ("17_storefront_contact", "Contact page"),
        ("18_storefront_returns", "Returns policy"),
        ("19_storefront_delivery", "Delivery info"),
        ("20_storefront_faq", "FAQ"),
    ]),
    ("Sales & EPOS", [
        ("30_admin_dashboard", "Admin Dashboard"),
        ("31_sales_hub", "Sales Hub"),
        ("32_epos_till", "EPOS till"),
        ("33_cash_counter", "Cash Counter"),
        ("34_store_dashboard", "Store Dashboard"),
        ("35_invoices", "Invoices list"),
        ("36_quotations", "Quotations list"),
        ("37_refunds", "Refunds list"),
        ("38_orders", "Orders list"),
        ("39_online_orders", "Online orders"),
        ("40_calculator_admin", "Calculator (admin)"),
    ]),
    ("Products & Suppliers", [
        ("41_products_hub", "Products Hub"),
        ("42_supplier_products", "Products list"),
        ("43_supplier_health", "Supplier Health"),
        ("44_sync_hub", "Sync Hub"),
    ]),
    ("Stock", [
        ("45_stock_hub", "Stock Hub"),
        ("46_stock_allocation", "Stock Allocation"),
        ("47_bulk_stock", "Bulk Stock Edit"),
        ("48_delivery_check_in", "Delivery Check-In"),
        ("49_stock_transfers", "Stock Transfers"),
        ("50_reorder_suggestions", "Reorder Suggestions"),
        ("51_batch_tracking", "Batch Tracking"),
        ("52_to_order", "To-Order Report"),
        ("53_stocktake", "Stocktake"),
        ("54_delivery_mgmt", "Delivery Management"),
    ]),
    ("Customers", [
        ("55_customers_hub", "Customers Hub"),
        ("56_trade_accounts", "Trade Accounts"),
        ("57_customer_pricing", "Customer Pricing"),
        ("58_invites", "Invitations"),
        ("59_inquiries", "Bulk Inquiries"),
    ]),
    ("Communication", [
        ("60_communication_hub", "Communication Hub"),
        ("61_staff_chat", "Staff Chat"),
        ("62_tasks", "Tasks & Notes"),
        ("63_inbox", "Inbox"),
        ("64_send_email", "Send Email"),
        ("65_marketing", "Marketing"),
        ("66_abandoned_baskets", "Abandoned Baskets"),
        ("67_promo_codes", "Promo Codes"),
    ]),
    ("Reports & Maintenance", [
        ("68_reports_hub", "Reports Hub"),
        ("69_analytics", "Analytics"),
        ("70_sales_reports", "Sales Reports"),
        ("71_maintenance", "Maintenance"),
    ]),
]
ALL_IMAGE_SLUGS = {slug for _, items in IMAGE_SLUG_GROUPS for slug, _ in items}


def _ensure_originals_backed_up():
    """Copy current screenshots to originals dir on first run, so we always
    have a way back to the canonical image even after several overrides.

    Idempotent — only copies files that don't already have an original on disk.
    """
    ORIGINALS_DIR.mkdir(parents=True, exist_ok=True)
    if not SCREENS_DIR.exists():
        return
    for f in SCREENS_DIR.glob("*.jpg"):
        backup = ORIGINALS_DIR / f.name
        if not backup.exists():
            shutil.copy2(f, backup)


async def _apply_image_overrides_to_disk():
    """Before the PDF builder runs, write every override from the DB to the
    screenshots directory (overwriting the canonical file). Restore originals
    for any slug whose override has been removed (DELETE).

    This keeps the build script dumb — it just reads the directory.
    """
    if _db is None:
        return
    _ensure_originals_backed_up()

    # First, restore originals for any slug whose override is missing
    overridden = set()
    async for doc in _db.training_booklet_images.find({}):
        overridden.add(doc.get("_id"))
        slug = doc.get("_id")
        data = doc.get("data")
        if not slug or not data:
            continue
        out_path = SCREENS_DIR / f"{slug}.jpg"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(data)

    # For any slug NOT in the override set, restore from originals if the
    # current file differs (e.g. an override was just deleted).
    for slug in ALL_IMAGE_SLUGS - overridden:
        original = ORIGINALS_DIR / f"{slug}.jpg"
        current = SCREENS_DIR / f"{slug}.jpg"
        if original.exists():
            try:
                if not current.exists() or current.stat().st_size != original.stat().st_size:
                    shutil.copy2(original, current)
            except Exception:
                pass


@router.get("/images")
async def list_images(current_user: dict = Depends(get_current_user)):
    """Returns the slug catalog grouped by section, with `has_override` flag
    + `updated_at` for each. Used by the editor's image grid."""
    if current_user.get("role") not in ("super_admin", "admin", "manager"):
        raise HTTPException(status_code=403, detail="Not authorized")

    _ensure_originals_backed_up()

    # Pull which slugs currently have an override (don't fetch the binary)
    overrides_by_slug = {}
    async for doc in _db.training_booklet_images.find({}, {"data": 0}):
        overrides_by_slug[doc["_id"]] = {
            "updated_at": doc.get("updated_at"),
            "updated_by": doc.get("updated_by"),
            "size_bytes": doc.get("size_bytes"),
            "content_type": doc.get("content_type"),
        }

    out = []
    for group_name, items in IMAGE_SLUG_GROUPS:
        rows = []
        for slug, label in items:
            override = overrides_by_slug.get(slug)
            rows.append({
                "slug": slug,
                "label": label,
                "has_override": override is not None,
                "updated_at": override.get("updated_at") if override else None,
                "updated_by": override.get("updated_by") if override else None,
                "size_bytes": override.get("size_bytes") if override else None,
                # Public preview URL — served from frontend public folder.
                # Cache-busted with updated_at so a new upload shows immediately.
                "preview_url": f"/checklists/training_previews/{slug}.jpg",
            })
        out.append({"group": group_name, "items": rows})

    can_edit = current_user.get("role") == "super_admin"
    return {"groups": out, "can_edit": can_edit, "total_slugs": len(ALL_IMAGE_SLUGS)}


@router.post("/images/{slug}")
async def upload_image_override(
    slug: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """Super-admin uploads a replacement screenshot for one slug.
    Stored as binary in MongoDB so it survives Railway redeploys (where
    the container filesystem is ephemeral)."""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin only")

    if slug not in ALL_IMAGE_SLUGS:
        raise HTTPException(status_code=404, detail=f"Unknown image slug: {slug}")

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Image type must be JPEG/PNG/WebP (got {file.content_type})",
        )

    data = await file.read()
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Image too large ({len(data) // 1024} KB). Max 4 MB.",
        )
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")

    # Convert any uploaded image to JPEG so the build script (which reads
    # *.jpg) Just Works regardless of source format. Resize to max width 1600
    # to keep PDF size sensible.
    try:
        from PIL import Image
        import io
        pim = Image.open(io.BytesIO(data)).convert("RGB")
        if pim.width > 1600:
            ratio = 1600 / pim.width
            pim = pim.resize((1600, int(pim.height * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        pim.save(buf, format="JPEG", quality=78, optimize=True)
        jpeg_bytes = buf.getvalue()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not process image: {exc}")

    now_iso = datetime.now(timezone.utc).isoformat()
    await _db.training_booklet_images.update_one(
        {"_id": slug},
        {"$set": {
            "data": jpeg_bytes,
            "size_bytes": len(jpeg_bytes),
            "content_type": "image/jpeg",
            "original_filename": file.filename,
            "updated_at": now_iso,
            "updated_by": current_user.get("email"),
        }},
        upsert=True,
    )

    # Also write to disk so the public preview folder shows the new image.
    _ensure_originals_backed_up()
    SCREENS_DIR.mkdir(parents=True, exist_ok=True)
    (SCREENS_DIR / f"{slug}.jpg").write_bytes(jpeg_bytes)
    # Mirror to the frontend public preview folder so the editor thumbnail updates
    preview_dir = pathlib.Path("/app/frontend/public/checklists/training_previews")
    preview_dir.mkdir(parents=True, exist_ok=True)
    (preview_dir / f"{slug}.jpg").write_bytes(jpeg_bytes)

    return {
        "success": True,
        "slug": slug,
        "size_bytes": len(jpeg_bytes),
        "updated_at": now_iso,
    }


@router.delete("/images/{slug}")
async def remove_image_override(
    slug: str,
    current_user: dict = Depends(get_current_user),
):
    """Removes the override and restores the original screenshot. Super-admin only."""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin only")

    if slug not in ALL_IMAGE_SLUGS:
        raise HTTPException(status_code=404, detail=f"Unknown image slug: {slug}")

    result = await _db.training_booklet_images.delete_one({"_id": slug})
    # Restore the canonical image
    original = ORIGINALS_DIR / f"{slug}.jpg"
    if original.exists():
        SCREENS_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, SCREENS_DIR / f"{slug}.jpg")
        # Also update preview
        preview_dir = pathlib.Path("/app/frontend/public/checklists/training_previews")
        preview_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, preview_dir / f"{slug}.jpg")

    return {"success": True, "removed": result.deleted_count, "restored_from_original": original.exists()}

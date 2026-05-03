"""File uploads — recipe images etc. Auto-compresses to WebP + thumbnail."""
import io
import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from PIL import Image, ImageOps

router = APIRouter()

UPLOAD_DIR = Path(__file__).parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_BYTES = 5 * 1024 * 1024  # 5MB
FULL_MAX = 1600            # px, longest edge
THUMB_SIZE = (400, 300)    # card thumbnail


def _save_webp(img: Image.Image, path: Path, quality: int) -> None:
    # Strip alpha to RGB for smaller files unless originally transparent
    if img.mode in ("RGBA", "LA"):
        bg = Image.new("RGB", img.size, (253, 251, 247))  # matches app base color
        bg.paste(img, mask=img.split()[-1])
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")
    img.save(path, "WEBP", quality=quality, method=6)


@router.post("/upload/image")
async def upload_image(file: UploadFile = File(...)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"Unsupported file type: {ext or 'unknown'}")
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(400, "File too large (5MB max)")

    try:
        src = Image.open(io.BytesIO(data))
        # Respect EXIF orientation from phones
        src = ImageOps.exif_transpose(src)
    except Exception:
        raise HTTPException(400, "Could not read image")

    stem = uuid.uuid4().hex
    full_path = UPLOAD_DIR / f"{stem}.webp"
    thumb_path = UPLOAD_DIR / f"{stem}_thumb.webp"

    # Full-size: scale so longest edge <= FULL_MAX
    full = src.copy()
    full.thumbnail((FULL_MAX, FULL_MAX), Image.LANCZOS)
    _save_webp(full, full_path, quality=85)

    # Thumbnail: cover-crop to THUMB_SIZE
    thumb = ImageOps.fit(src, THUMB_SIZE, method=Image.LANCZOS)
    _save_webp(thumb, thumb_path, quality=75)

    return {
        "url": f"/api/uploads/{full_path.name}",
        "thumb_url": f"/api/uploads/{thumb_path.name}",
        "filename": full_path.name,
    }

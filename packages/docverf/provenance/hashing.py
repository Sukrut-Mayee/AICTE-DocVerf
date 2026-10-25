"""File hashing (TRD §9.1)."""

import hashlib
import io
from pathlib import Path

import fitz
import imagehash
from PIL import Image, UnidentifiedImageError

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".gif", ".webp"}


def _is_pdf(path: str) -> bool:
    """Detect PDF by magic bytes or extension."""
    p = Path(path)
    if p.suffix.lower() == ".pdf":
        return True
    try:
        with open(path, "rb") as fh:
            return fh.read(5) == b"%PDF-"
    except OSError:
        return False


def _render_page1_at_150dpi(path: str) -> Image.Image:
    """Render the first page of a PDF at 150 DPI and return a PIL image."""
    doc = fitz.open(path)
    try:
        page = doc[0]
        zoom = 150.0 / 72.0
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        return Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    finally:
        doc.close()


def _phash_for_image(path: str) -> str:
    """Perceptual hash of an image file, or empty string when it is not an image."""
    if Path(path).suffix.lower() not in IMAGE_EXTENSIONS:
        return ""
    try:
        with Image.open(path) as img:
            return str(imagehash.phash(img.convert("RGB")))
    except (UnidentifiedImageError, OSError, ValueError):
        return ""


def hash_file(path: str) -> dict[str, str]:
    """Return {"sha256": ..., "phash": ...}.

    SHA-256 is computed over the original file bytes for exact file integrity and
    byte-for-byte duplicate comparison. The perceptual hash (pHash) is computed only
    for photo/image documents. PDFs and other non-image files return an empty perceptual
    hash to prevent false duplicate detection from similar document templates.
    """
    with open(path, "rb") as fh:
        data = fh.read()
    sha256 = hashlib.sha256(data).hexdigest()

    if _is_pdf(path):
        phash = ""
    else:
        phash = _phash_for_image(path)

    return {"sha256": sha256, "phash": phash}

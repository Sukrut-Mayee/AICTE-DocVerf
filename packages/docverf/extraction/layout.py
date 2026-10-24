"""Layout and region detection: signature, seal, qr, photo, table, text_block (TRD §3, §10).

Heuristic v1 using Pillow only. Does not claim reliable semantic detection of
signatures, seals, QR codes or tables. Returns fewer, defensible regions rather
than inventing detections. Returns an empty list when nothing is confidently
detected.
"""

from pathlib import Path

from PIL import Image

from docverf.schemas import Region

# Minimum fraction of dark pixels required to consider a page non-blank.
_DARK_FRACTION_THRESHOLD = 0.005
# Downsample factor for speed.
_DOWNSAMPLE = 16


def detect_regions(image_path: Path) -> list[Region]:
    """Detect document regions using grayscale pixel heuristics.

    Returns a list of schema-valid Region objects (text_block when meaningful
    dark content is present). Returns an empty list for blank/unusable pages.
    Does not attempt signature/seal/qr/table detection at v1.
    """
    if not isinstance(image_path, Path):
        image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")

    try:
        with Image.open(image_path) as img:
            width, height = img.size
            if width <= 0 or height <= 0:
                return []
            gray = img.convert("L")
            sw = max(1, width // _DOWNSAMPLE)
            sh = max(1, height // _DOWNSAMPLE)
            small = gray.resize((sw, sh))
            px = small.load()
            assert px is not None

            min_x, min_y, max_x, max_y = sw, sh, 0, 0
            dark_count = 0
            for y in range(sh):
                for x in range(sw):
                    pixel = px[x, y]
                    pixel_value: int | float
                    if isinstance(pixel, tuple):
                        pixel_value = pixel[0]
                    else:
                        pixel_value = pixel
                    if pixel_value < 128:
                        dark_count += 1
                        if x < min_x:
                            min_x = x
                        if x > max_x:
                            max_x = x
                        if y < min_y:
                            min_y = y
                        if y > max_y:
                            max_y = y
    except (OSError, ValueError) as exc:
        raise FileNotFoundError(f"Unable to read image: {image_path}") from exc

    if dark_count < (sw * sh * _DARK_FRACTION_THRESHOLD):
        return []

    pad = 1
    x1 = max(0, min_x - pad) / sw
    y1 = max(0, min_y - pad) / sh
    x2 = min(1.0, (max_x + 1) / sw)
    y2 = min(1.0, (max_y + 1) / sh)

    return [
        Region(
            type="text_block",
            page=1,
            bbox=[x1, y1, x2, y2],
            score=0.5,
        )
    ]

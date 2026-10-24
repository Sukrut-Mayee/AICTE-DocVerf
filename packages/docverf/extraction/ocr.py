"""OCR engine wrapper; engine chosen by OCR_ENGINE (paddleocr | surya) (TRD §3, §10).

Engine imports are lazy so importing this module does not require either OCR
dependency to be installed. The active engine is read from ``OCR_ENGINE`` via
``docverf.config`` (TRD §1 rule 6).
"""

from pathlib import Path
from typing import Any

from PIL import Image

from docverf.config import get_settings

_SUPPORTED_ENGINES = ("paddleocr", "surya")


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _image_size(image_path: Path) -> tuple[int, int]:
    with Image.open(image_path) as img:
        return img.width, img.height


def _as_points(raw: Any) -> list[tuple[float, float]] | None:
    """Extract a list of (x, y) points from an engine-specific box shape."""
    if raw is None:
        return None
    if isinstance(raw, (list, tuple)):
        # Flat 8 numbers: [x1, y1, x2, y2, x3, y3, x4, y4]
        if len(raw) == 8 and all(isinstance(v, (int, float)) for v in raw):
            return [(raw[0], raw[1]), (raw[2], raw[3]), (raw[4], raw[5]), (raw[6], raw[7])]
        # Flat 4 numbers: [x1, y1, x2, y2]
        if len(raw) == 4 and all(isinstance(v, (int, float)) for v in raw):
            return [(raw[0], raw[1]), (raw[2], raw[3])]
        # List of points: [(x1, y1), (x2, y2), ...] or [[x1, y1], [x2, y2], ...]
        points: list[tuple[float, float]] = []
        for item in raw:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                points.append((float(item[0]), float(item[1])))
        if points:
            return points
    return None


def _points_to_bbox(points: list[tuple[float, float]]) -> tuple[float, float, float, float] | None:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    if not xs or not ys:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def _normalize_box(raw_box: Any, width: int, height: int) -> list[float] | None:
    """Return [x1, y1, x2, y2] normalized to 0..1, origin top-left, or None."""
    if width <= 0 or height <= 0:
        return None
    points = _as_points(raw_box)
    if points is None or len(points) < 2:
        return None
    bbox = _points_to_bbox(points)
    if bbox is None:
        return None
    x1, y1, x2, y2 = bbox
    # If the engine returned [x, y, w, h], detect and convert.
    if x2 < x1 or y2 < y1:
        # Possibly [x, y, w, h] where w/h are small relative to image
        w, h = x2, y2
        if 0 < w <= width and 0 < h <= height and w < width / 2 and h < height / 2:
            x2, y2 = x1 + w, y1 + h
        else:
            return None
    x1 = _clamp(x1 / width)
    y1 = _clamp(y1 / height)
    x2 = _clamp(x2 / width)
    y2 = _clamp(y2 / height)
    if x2 <= x1 or y2 <= y1:
        return None
    return [x1, y1, x2, y2]


def _extract_text_conf(item: Any) -> tuple[str, float] | None:
    """Extract (text, confidence) from an engine-specific word result."""
    if item is None:
        return None
    # Common shape: (text, confidence)
    if isinstance(item, (list, tuple)) and len(item) >= 2:
        text = item[0]
        conf = item[1]
        if text is None:
            return None
        return (str(text), _clamp(float(conf)))
    # Dict shape: {"text": ..., "confidence": ...}
    if isinstance(item, dict):
        text = item.get("text") or item.get("words") or item.get("content")
        conf = item.get("confidence", item.get("score", 1.0))
        if text is None:
            return None
        if conf is None:
            conf = 1.0
        return (str(text), _clamp(float(conf)))
    # Bare text
    if isinstance(item, str):
        return (item, 1.0)
    return None


def _run_paddleocr(image_path: Path) -> list[dict[str, Any]]:
    from paddleocr import PaddleOCR  # type: ignore[import-not-found]

    ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
    result = ocr.ocr(str(image_path), cls=True)
    words: list[dict[str, Any]] = []
    if not result:
        return words
    # PaddleOCR result: list of pages; each page is list of [box, (text, conf)]
    for page in result:
        if page is None:
            continue
        for detection in page:
            if not detection or len(detection) < 2:
                continue
            raw_box = detection[0]
            text_conf = detection[1]
            extracted = _extract_text_conf(text_conf)
            if extracted is None:
                continue
            text, conf = extracted
            if not text.strip():
                continue
            words.append({"text": text, "confidence": conf, "bbox": raw_box})
    return words


def _run_surya(image_path: Path) -> list[dict[str, Any]]:
    from surya.ocr import OCR  # type: ignore[import-not-found]

    model = OCR()
    predictions = model.ocr([str(image_path)])
    words: list[dict[str, Any]] = []
    for pred in predictions:
        # Surya prediction structure varies by version; iterate text lines/words.
        lines = getattr(pred, "text_lines", None) or getattr(pred, "lines", None) or []
        for line in lines:
            bbox = getattr(line, "bbox", None) or getattr(line, "bounding_box", None)
            text = getattr(line, "text", None)
            conf = getattr(line, "confidence", getattr(line, "score", 1.0))
            extracted = _extract_text_conf((text, conf)) if text is not None else None
            if extracted is None:
                continue
            text, conf = extracted
            if not text.strip():
                continue
            words.append({"text": text, "confidence": conf, "bbox": bbox})
    return words


def run_ocr(image_path: Path) -> list[dict[str, Any]]:
    """Word boxes: text, ocr confidence, bbox normalized to 0..1 (origin top-left).

    Engine is selected by ``OCR_ENGINE`` (``paddleocr`` or ``surya``). Engine
    imports are lazy; unsupported engines, missing dependencies, and missing
    image files raise clear errors.
    """
    if not isinstance(image_path, Path):
        image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")

    settings = get_settings()
    engine = settings.OCR_ENGINE
    if engine not in _SUPPORTED_ENGINES:
        raise ValueError(f"Unsupported OCR_ENGINE '{engine}'. Supported: {_SUPPORTED_ENGINES}")

    width, height = _image_size(image_path)

    if engine == "paddleocr":
        raw_words = _run_paddleocr(image_path)
    else:
        raw_words = _run_surya(image_path)

    normalized: list[dict[str, Any]] = []
    for raw in raw_words:
        text = raw.get("text") if isinstance(raw, dict) else None
        conf = raw.get("confidence") if isinstance(raw, dict) else None
        bbox = _normalize_box(raw.get("bbox") if isinstance(raw, dict) else None, width, height)
        if text is None or not str(text).strip():
            continue
        if bbox is None:
            continue
        if conf is None:
            conf = 1.0
        normalized.append(
            {
                "text": str(text),
                "confidence": _clamp(float(conf)),
                "bbox": bbox,
            }
        )
    return normalized

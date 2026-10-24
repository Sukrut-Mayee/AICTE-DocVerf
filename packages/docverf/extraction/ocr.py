"""OCR engine wrapper; engine chosen by OCR_ENGINE (paddleocr | surya) (TRD §3, §10)."""

from pathlib import Path
from typing import Any


def run_ocr(image_path: Path) -> list[dict[str, Any]]:
    """Word boxes: text, ocr confidence, bbox normalized to 0..1 (origin top-left)."""
    raise NotImplementedError

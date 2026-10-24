"""Layout and region detection: signature, seal, qr, photo, table, text_block (TRD §3, §10)."""

from pathlib import Path

from docverf.schemas import Region


def detect_regions(image_path: Path) -> list[Region]:
    raise NotImplementedError

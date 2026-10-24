"""Document classification (TRD §10)."""

from pathlib import Path

from docverf.schemas import DocType


def classify(file_path: Path) -> DocType:
    """VLM zero-shot among the 6 doc types, with a keyword fallback."""
    raise NotImplementedError

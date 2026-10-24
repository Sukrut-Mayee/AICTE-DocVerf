"""Top-level extraction entry point (TRD §10)."""

from pathlib import Path

from docverf.schemas import DocType, ExtractionResult


def extract(file_path: Path, doc_type: DocType | None = None) -> ExtractionResult:
    """Quality gate -> classify (if doc_type is None) -> regions -> OCR -> two extractors ->
    confidence -> normalize.

    TODO(question): ExtractionResult requires doc_id and app_id, which TRD §10 does not pass in.
    """
    raise NotImplementedError

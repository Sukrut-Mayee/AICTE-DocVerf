"""Top-level extraction entry point (TRD §10, §19 Q1)."""

from docverf.schemas import DocType, ExtractionResult


def extract(
    file_path: str, doc_id: str, app_id: str, doc_type: DocType | None = None
) -> ExtractionResult:
    """Quality gate -> classify (if doc_type is None) -> regions -> OCR -> two extractors ->
    confidence -> normalize."""
    raise NotImplementedError

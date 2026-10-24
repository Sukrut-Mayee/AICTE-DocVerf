"""File metadata checks (TRD §9.1)."""

from docverf.schemas import CheckResult


def extract_metadata(path: str, doc_id: str) -> CheckResult:
    """Flag (low) if the producer is image-editing software, or the creation date is more
    than 30 days after the document's printed date."""
    raise NotImplementedError

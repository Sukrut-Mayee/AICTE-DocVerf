"""Source verification against issuers (TRD §9.3). May make network calls."""

from docverf.schemas import CheckResult, ExtractionResult


def lookup(extraction: ExtractionResult) -> CheckResult:
    """Layer A issuer lookup for the document's ref_no; no call is made (manual_review_required)
    when the ref_no confidence is below CONFIDENCE_THRESHOLD. Timeout -> verification_pending."""
    raise NotImplementedError

"""Source verification against issuers (TRD §9.3). May make network calls."""

from datetime import datetime

from docverf.config import get_settings
from docverf.schemas import (
    CheckResult,
    CheckStatus,
    ExtractionResult,
    Layer,
    Severity,
    VerificationStatus,
)
from docverf.verification.connectors.mock import MockIssuerConnector


def _no_call(extraction: ExtractionResult, status: CheckStatus, reason: str) -> CheckResult:
    return CheckResult(
        doc_id=extraction.doc_id,
        layer=Layer.A,
        check="issuer_lookup",
        status=status,
        severity=Severity.INFO,
        reason=reason,
        verification_status=(
            VerificationStatus.MANUAL_REVIEW_REQUIRED if status is CheckStatus.SUSPICIOUS else None
        ),
        checked_at=datetime.now().astimezone(),
    )


def lookup(extraction: ExtractionResult) -> CheckResult:
    """Layer A issuer lookup for the document's ref_no; no call is made (manual_review_required)
    when the ref_no confidence is below CONFIDENCE_THRESHOLD. Timeout -> verification_pending."""
    connector = MockIssuerConnector()
    if extraction.doc_type not in connector.doc_types:
        return _no_call(
            extraction, CheckStatus.NOT_APPLICABLE, "no issuer connector for this document type"
        )
    ref = extraction.fields.get("ref_no")
    threshold = get_settings().CONFIDENCE_THRESHOLD
    if ref is None or not ref.value:
        return _no_call(
            extraction, CheckStatus.SUSPICIOUS, "reference number not read; issuer not contacted"
        )
    if ref.confidence < threshold:
        return _no_call(
            extraction,
            CheckStatus.SUSPICIOUS,
            f"reference number confidence {ref.confidence:.2f} is below {threshold:.2f}; "
            "issuer not contacted",
        )
    result = connector.lookup(str(ref.value), extraction.fields)
    # The connector names timeout / 404 / unreachable results "noc_timeout" etc.; it is never
    # told which document it checked, so the result is attached to it here.
    return result.model_copy(update={"doc_id": extraction.doc_id})

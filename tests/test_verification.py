"""verification.lookup: confidence gate before any call, and the result attached to the document."""

from datetime import datetime

import pytest
from docverf import verification
from docverf.schemas import (
    CheckResult,
    CheckStatus,
    DocType,
    ExtractionResult,
    FieldValue,
    Layer,
    Severity,
    VerificationStatus,
)
from docverf.verification.connectors.mock import MockIssuerConnector


def _noc(**fields: FieldValue) -> ExtractionResult:
    return ExtractionResult(
        doc_id="app001_noc", app_id="app001", doc_type=DocType.NOC, fields=fields
    )


@pytest.fixture
def no_call(monkeypatch):
    def fail(*_args, **_kwargs):
        raise AssertionError("issuer must not be contacted")

    monkeypatch.setattr(MockIssuerConnector, "lookup", fail)


@pytest.mark.parametrize(
    "fields",
    [{}, {"ref_no": FieldValue(value="FIRE/MH/2026/1", confidence=0.4)}],
    ids=["missing", "low-confidence"],
)
def test_unreadable_ref_no_needs_manual_review_without_a_call(no_call, fields):
    result = verification.lookup(_noc(**fields))
    assert result.doc_id == "app001_noc" and result.check == "issuer_lookup"
    assert result.verification_status is VerificationStatus.MANUAL_REVIEW_REQUIRED


def test_other_document_types_are_not_looked_up(no_call):
    deed = ExtractionResult(
        doc_id="app001_land_deed", app_id="app001", doc_type=DocType.LAND_DEED, fields={}
    )
    result = verification.lookup(deed)
    assert result.status is CheckStatus.NOT_APPLICABLE and result.verification_status is None


def test_timeout_result_is_attached_to_the_noc(monkeypatch):
    def timeout(self, ref_no, fields):
        return CheckResult(
            doc_id="noc_timeout",  # what the connector returns: it never sees the doc_id
            layer=Layer.A,
            check="issuer_lookup",
            status=CheckStatus.NOT_APPLICABLE,
            severity=Severity.INFO,
            reason=f"timeout for {ref_no}",
            verification_status=VerificationStatus.VERIFICATION_PENDING,
            checked_at=datetime.now(),
        )

    monkeypatch.setattr(MockIssuerConnector, "lookup", timeout)
    result = verification.lookup(_noc(ref_no=FieldValue(value="FIRE/MH/2026/1", confidence=1.0)))
    assert result.doc_id == "app001_noc"
    assert result.verification_status is VerificationStatus.VERIFICATION_PENDING

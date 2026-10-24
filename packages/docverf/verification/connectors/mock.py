"""Connector for services/mock_issuer (TRD §9.3)."""

from docverf.schemas import CheckResult, DocType, FieldValue


class MockIssuerConnector:
    name = "mock_issuer"
    doc_types = {DocType.NOC}

    def lookup(self, ref_no: str, fields: dict[str, FieldValue]) -> CheckResult:
        """GET MOCK_ISSUER_URL/noc/{ref_no} and compare with the extracted fields ->
        verified / mismatch_detected / expired / source_unavailable (404) /
        verification_pending (timeout, SOURCE_TIMEOUT_S)."""
        raise NotImplementedError

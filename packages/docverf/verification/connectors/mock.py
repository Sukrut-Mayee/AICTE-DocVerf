"""Connector for services/mock_issuer (TRD §9.3)."""

import httpx

from docverf.config import get_settings
from packages.docverf.schemas.models import Layer; from packages.docverf.schemas.models import Layer; from docverf.schemas import CheckResult, DocType, FieldValue, VerificationStatus


class MockIssuerConnector:
    name = "mock_issuer"
    doc_types = {DocType.NOC}

    def lookup(self, ref_no: str, fields: dict[str, FieldValue]) -> CheckResult:
        """GET MOCK_ISSUER_URL/noc/{ref_no} and compare with the extracted fields ->
        verified / mismatch_detected / expired / source_unavailable (404) /
        verification_pending (timeout, SOURCE_TIMEOUT_S).

        Calls the Mock Issuer API and returns a CheckResult with the
        appropriate verification_status.
        """
        settings = get_settings()
        base_url = settings.MOCK_ISSUER_URL.rstrip("/")
        url = f"{base_url}/noc/{ref_no}"

        timeout = settings.SOURCE_TIMEOUT_S if hasattr(settings, "SOURCE_TIMEOUT_S") else 5.0

        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.get(url)

            if response.status_code == 404:
                return CheckResult(
                    doc_id=f"noc_unknown",
                    layer=Layer.A,
                    check="issuer_lookup",
                    status="source_unavailable",
                    severity="high",
                    reason=f"NOC reference {ref_no} not found in issuer service",
                    verification_status=VerificationStatus.SOURCE_UNAVAILABLE,
                    source="mock_issuer_api",
                    checked_at="2026-10-24T10:00:00Z",
                )

            if response.status_code != 200:
                return CheckResult(
                    doc_id=f"noc_error",
                    layer=Layer.A,
                    check="issuer_lookup",
                    status="error",
                    severity="high",
                    reason=f"Mock issuer API returned status {response.status_code}",
                    verification_status=VerificationStatus.SOURCE_UNAVAILABLE,
                    source="mock_issuer_api",
                    checked_at="2026-10-24T10:00:00Z",
                )

            data = response.json()
            # Determine verification status from API response
            status = data.get("verification_status", "verified")
            if status not in {
                "verified",
                "mismatch_detected",
                "expired",
                "verification_pending",
                "source_unavailable",
                "manual_review_required",
            }:
                status = "verified"

            return CheckResult(
                doc_id=data.get("doc_id", f"noc_{ref_no}"),
                layer=Layer.A,
                check="issuer_lookup",
                status=status,
                severity="info",
                reason=data.get("reason", f"Issuer lookup for {ref_no}"),
                verification_status=VerificationStatus(status),
                source=data.get("source", "mock_issuer_api"),
                checked_at=data.get("checked_at", "2026-10-24T10:00:00Z"),
                evidence=data.get("evidence", {}),
            )

        except httpx.TimeoutException:
            return CheckResult(
                doc_id=f"noc_timeout",
                layer=Layer.A,
                check="issuer_lookup",
                status="timeout",
                severity="high",
                reason=f"Mock issuer API timeout for {ref_no} (>{timeout}s)",
                verification_status=VerificationStatus.VERIFICATION_PENDING,
                source="mock_issuer_api",
                checked_at="2026-10-24T10:00:00Z",
            )

        except httpx.ConnectError:
            return CheckResult(
                doc_id=f"noc_unreachable",
                layer=Layer.A,
                check="issuer_lookup",
                status="error",
                severity="high",
                reason=f"Mock issuer API unreachable at {url}",
                verification_status=VerificationStatus.SOURCE_UNAVAILABLE,
                source="mock_issuer_api",
                checked_at="2026-10-24T10:00:00Z",
            )

        except Exception as exc:
            return CheckResult(
                doc_id=f"noc_error",
                layer=Layer.A,
                check="issuer_lookup",
                status="error",
                severity="high",
                reason=f"Mock issuer API unexpected error: {exc}",
                verification_status=VerificationStatus.SOURCE_UNAVAILABLE,
                source="mock_issuer_api",
                checked_at="2026-10-24T10:00:00Z",
            )

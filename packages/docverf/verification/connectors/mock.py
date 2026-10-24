"""Connector for services/mock_issuer (TRD §9.3)."""

from datetime import datetime
from typing import Any

import httpx

from docverf.config import get_settings
from docverf.schemas import (
    CheckResult,
    CheckStatus,
    DocType,
    FieldValue,
    Layer,
    VerificationStatus,
)


def _check_status(verification_status: VerificationStatus) -> CheckStatus:
    if verification_status == VerificationStatus.VERIFIED:
        return CheckStatus.VERIFIED
    if verification_status in {
        VerificationStatus.MISMATCH_DETECTED,
        VerificationStatus.EXPIRED,
    }:
        return CheckStatus.MISMATCH
    if verification_status == VerificationStatus.MANUAL_REVIEW_REQUIRED:
        return CheckStatus.SUSPICIOUS
    if verification_status == VerificationStatus.VERIFICATION_PENDING:
        return CheckStatus.NOT_APPLICABLE
    return CheckStatus.ERROR


def _result(
    doc_id: str,
    reason: str,
    verification_status: VerificationStatus,
    *,
    severity: str = "info",
    source: str = "mock_issuer_api",
    evidence: dict[str, Any] | None = None,
) -> CheckResult:
    return CheckResult(
        doc_id=doc_id,
        layer=Layer.A,
        check="issuer_lookup",
        status=_check_status(verification_status),
        severity=severity,
        reason=reason,
        verification_status=verification_status,
        source=source,
        checked_at=datetime.now().astimezone(),
        evidence=evidence if evidence is not None else {},
    )


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

        timeout = (
            settings.SOURCE_TIMEOUT_S
            if hasattr(settings, "SOURCE_TIMEOUT_S")
            else 5.0
        )

        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.get(url)

            if response.status_code == 404:
                return _result(
                    "noc_unknown",
                    f"NOC reference {ref_no} not found in issuer service",
                    VerificationStatus.SOURCE_UNAVAILABLE,
                    severity="high",
                )

            if response.status_code != 200:
                return _result(
                    "noc_error",
                    f"Mock issuer API returned status {response.status_code}",
                    VerificationStatus.SOURCE_UNAVAILABLE,
                    severity="high",
                )

            data = response.json()
            verification_status = VerificationStatus(data["verification_status"])
            return _result(
                data.get("doc_id", f"noc_{ref_no}"),
                data.get("reason", f"Issuer lookup for {ref_no}"),
                verification_status,
                severity=(
                    "high"
                    if verification_status
                    in {
                        VerificationStatus.MISMATCH_DETECTED,
                        VerificationStatus.EXPIRED,
                    }
                    else "info"
                ),
                source=data.get("source", "mock_issuer_api"),
                evidence=data.get("evidence", {}),
            )

        except httpx.TimeoutException:
            return _result(
                "noc_timeout",
                f"Mock issuer API timeout for {ref_no} (>{timeout}s)",
                VerificationStatus.VERIFICATION_PENDING,
                severity="info",
            )

        except httpx.ConnectError:
            return _result(
                "noc_unreachable",
                f"Mock issuer API unreachable at {url}",
                VerificationStatus.SOURCE_UNAVAILABLE,
                severity="high",
            )

        except httpx.RequestError as exc:
            return _result(
                "noc_unreachable",
                f"Mock issuer API request failed: {exc}",
                VerificationStatus.SOURCE_UNAVAILABLE,
                severity="high",
            )
        except (KeyError, TypeError, ValueError) as exc:
            return _result(
                "noc_error",
                f"Mock issuer API returned an invalid response: {exc}",
                VerificationStatus.SOURCE_UNAVAILABLE,
                severity="high",
            )

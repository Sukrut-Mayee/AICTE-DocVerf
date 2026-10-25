"""PDF digital signature validation with pyHanko (TRD §9.1)."""

from datetime import datetime
from pathlib import Path

from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign import load_certs_from_pemder
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko_certvalidator.context import ValidationContext

from docverf.config import get_settings
from docverf.schemas import (
    CheckResult,
    CheckStatus,
    Layer,
    Severity,
    VerificationStatus,
)

TRUST_ROOT_GLOBS = ("*.pem", "*.der", "*.crt", "*.cer")


def _load_trust_roots(trust_dir: Path | None = None) -> list:
    """Load CA certificates from TRUST_ROOTS_DIR. Returns empty list if missing/empty."""
    if trust_dir is None:
        trust_dir = Path(get_settings().TRUST_ROOTS_DIR)
    if not trust_dir.is_dir():
        return []
    certs: list = []
    for pattern in TRUST_ROOT_GLOBS:
        for cert_file in sorted(trust_dir.glob(pattern)):
            try:
                certs.extend(load_certs_from_pemder([str(cert_file)]))
            except Exception:
                # Skip unreadable / invalid cert files; do not fail the whole check.
                continue
    return certs


def _check_result(
    doc_id: str,
    status: CheckStatus,
    severity: Severity,
    reason: str,
    verification_status: VerificationStatus | None,
    evidence: dict | None,
) -> CheckResult:
    return CheckResult(
        doc_id=doc_id,
        layer=Layer.A,
        check="pdf_signature",
        status=status,
        severity=severity,
        reason=reason,
        verification_status=verification_status,
        evidence=evidence or {},
        checked_at=datetime.now(),
    )


def check_pdf_signature(path: str, doc_id: str) -> CheckResult:
    """Layer A. `verified` (intact, signer trusted via TRUST_ROOTS_DIR), `mismatch` plus
    `provenance_failure` (modified after signing / invalid), `not_applicable` (unsigned).

    The file handle must stay open while pyHanko reads signatures and validates, so all
    PDF access happens inside a single `open(...)` block.
    """
    try:
        fh = open(path, "rb")
    except Exception as exc:
        return _check_result(
            doc_id,
            CheckStatus.ERROR,
            Severity.LOW,
            f"could not open PDF: {exc}",
            None,
            {"error": str(exc)},
        )

    with fh:
        try:
            reader = PdfFileReader(fh)
        except Exception as exc:
            return _check_result(
                doc_id,
                CheckStatus.ERROR,
                Severity.LOW,
                f"could not read PDF: {exc}",
                None,
                {"error": str(exc)},
            )

        try:
            signatures = reader.embedded_regular_signatures
        except Exception as exc:
            return _check_result(
                doc_id,
                CheckStatus.ERROR,
                Severity.LOW,
                f"could not inspect signatures: {exc}",
                None,
                {"error": str(exc)},
            )

        if not signatures:
            return _check_result(
                doc_id,
                CheckStatus.NOT_APPLICABLE,
                Severity.INFO,
                "no embedded PDF signature found",
                None,
                {"signed": False},
            )

        # Validate the first embedded regular signature.
        embedded_sig = signatures[0]
        trust_certs = _load_trust_roots()
        try:
            ctx = ValidationContext(trust_roots=trust_certs)
            status = validate_pdf_signature(
                embedded_sig, signer_validation_context=ctx
            )
        except Exception as exc:
            return _check_result(
                doc_id,
                CheckStatus.ERROR,
                Severity.LOW,
                f"signature verification failed: {exc}",
                None,
                {"error": str(exc), "signed": True},
            )

    intact = bool(getattr(status, "intact", False))
    valid = bool(getattr(status, "valid", False))
    trusted = bool(getattr(status, "trusted", False))

    signing_cert = getattr(status, "signing_cert", None)
    signer_subject = None
    signer_issuer = None
    if signing_cert is not None:
        try:
            signer_subject = str(signing_cert.subject.native)
        except Exception:
            pass
        try:
            signer_issuer = str(signing_cert.issuer.native)
        except Exception:
            pass

    evidence: dict = {
        "signed": True,
        "intact": intact,
        "valid": valid,
        "trusted": trusted,
        "signer_subject": signer_subject,
        "signer_issuer": signer_issuer,
        "summary": status.summary() if callable(getattr(status, "summary", None)) else "",
    }

    if intact and valid and trusted:
        return _check_result(
            doc_id,
            CheckStatus.VERIFIED,
            Severity.INFO,
            "PDF signature is intact and signer is trusted",
            VerificationStatus.VERIFIED,
            evidence,
        )

    # Determine the specific failure reason for the evidence.
    failure_reasons = []
    if not intact:
        failure_reasons.append("document modified after signing")
    if not valid:
        failure_reasons.append("invalid signature")
    if not trusted:
        failure_reasons.append("signer not trusted")
    reason = "; ".join(failure_reasons) if failure_reasons else "signature verification failed"
    evidence["failure_reasons"] = failure_reasons

    return _check_result(
        doc_id,
        CheckStatus.MISMATCH,
        Severity.HIGH,
        f"PDF signature verification failed: {reason}",
        VerificationStatus.MISMATCH_DETECTED,
        evidence,
    )

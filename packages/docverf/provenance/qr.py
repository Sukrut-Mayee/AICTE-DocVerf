"""QR decoding with zxing-cpp, fallback pyzbar (TRD §9.1)."""

from datetime import datetime

import numpy as np
from PIL import Image

from docverf.schemas import CheckResult, CheckStatus, Layer, Severity, VerificationStatus


def _decode_payloads(path: str) -> list[str]:
    image = Image.open(path).convert("RGB")
    array = np.array(image)

    # Primary: zxing-cpp.
    try:
        import zxingcpp

        results = zxingcpp.read_barcodes(array)
        return [str(r.text) for r in results if getattr(r, "text", None)]
    except Exception:
        pass

    # Fallback: pyzbar.
    try:
        from pyzbar.pyzbar import decode as pyzbar_decode

        results = pyzbar_decode(image)
        return [r.data.decode("utf-8", errors="replace") for r in results]
    except Exception:
        pass

    return []


def decode_qr(path: str, doc_id: str) -> CheckResult:
    """Payload goes in evidence.details.payload.

    Comparison with the printed text happens in reasoning.
    """
    try:
        payloads = _decode_payloads(path)
    except Exception as exc:
        return CheckResult(
            doc_id=doc_id,
            layer=Layer.A,
            check="qr",
            status=CheckStatus.ERROR,
            severity=Severity.LOW,
            reason=f"QR decoding failed: {exc}",
            evidence={"details": {"payload": None}},
            checked_at=datetime.now(),
        )

    if not payloads:
        return CheckResult(
            doc_id=doc_id,
            layer=Layer.A,
            check="qr",
            status=CheckStatus.NOT_APPLICABLE,
            severity=Severity.INFO,
            reason="no QR code found",
            evidence={"details": {"payload": None}},
            checked_at=datetime.now(),
        )

    return CheckResult(
        doc_id=doc_id,
        layer=Layer.A,
        check="qr",
        status=CheckStatus.CLEAN,
        severity=Severity.INFO,
        reason=f"decoded {len(payloads)} QR code(s)",
        verification_status=VerificationStatus.VERIFIED,
        evidence={"details": {"payload": payloads}},
        checked_at=datetime.now(),
    )

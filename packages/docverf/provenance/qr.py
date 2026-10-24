"""QR decoding with zxing-cpp, fallback pyzbar (TRD §9.1)."""

from docverf.schemas import CheckResult


def decode_qr(path: str, doc_id: str) -> CheckResult:
    """Payload goes in evidence.details.payload.

    Comparison with the printed text happens in reasoning.
    """
    raise NotImplementedError

"""QR decoding with zxing-cpp, fallback pyzbar (TRD §9.1)."""

from pathlib import Path

from docverf.schemas import CheckResult


def decode_qr(path: Path) -> CheckResult:
    """Payload goes in evidence.details.payload.

    Comparison with the printed text happens in reasoning.
    """
    raise NotImplementedError

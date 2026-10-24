"""Noise inconsistency (TRD §9.2)."""

from docverf.schemas import CheckResult, Region


def noise_inconsistency(
    image_path: str, doc_id: str, regions: list[Region] | None = None
) -> CheckResult:
    """Residual (image - median filtered) std per region vs page; z-score >= 3 -> suspicious."""
    raise NotImplementedError

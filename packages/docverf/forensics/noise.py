"""Noise inconsistency (TRD §9.2)."""

from pathlib import Path

from docverf.schemas import CheckResult, Region


def noise_inconsistency(image_path: Path, regions: list[Region] | None = None) -> CheckResult:
    """Residual (image - median filtered) std per region vs page; z-score >= 3 -> suspicious."""
    raise NotImplementedError

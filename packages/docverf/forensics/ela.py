"""Error level analysis (TRD §9.2)."""

from pathlib import Path

from docverf.schemas import CheckResult, Region


def run_ela(
    image_path: Path, regions: list[Region] | None = None, quality: int = 90
) -> CheckResult:
    """Score = mean ELA intensity in region / page mean; suspicious if >= ELA_RATIO_THRESHOLD.
    Saves a heatmap PNG to data/out/forensics/."""
    raise NotImplementedError

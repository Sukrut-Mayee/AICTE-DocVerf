"""Error level analysis (TRD §9.2)."""

from docverf.schemas import CheckResult, Region


def run_ela(image_path: str, doc_id: str, regions: list[Region] | None = None) -> CheckResult:
    """Score = mean ELA intensity in region / page mean; suspicious if >= ELA_RATIO_THRESHOLD.
    Re-saves at JPEG quality 90 (TRD §9.2) and writes a heatmap PNG to data/out/forensics/."""
    raise NotImplementedError

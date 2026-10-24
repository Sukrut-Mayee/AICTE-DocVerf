"""AI-generation signal, P2 (TRD §9.2). Severity is capped at `low`."""

from pathlib import Path

from docverf.schemas import CheckResult, Region


def ai_gen(image_path: Path, regions: list[Region] | None = None) -> CheckResult:
    raise NotImplementedError

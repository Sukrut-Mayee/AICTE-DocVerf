"""Copy-move detection (TRD §9.2)."""

from docverf.schemas import CheckResult, Region


def detect_copy_move(
    image_path: str, doc_id: str, regions: list[Region] | None = None
) -> CheckResult:
    """ORB matches within the image, clustered by offset > 20 px; suspicious if >= 15 consistent."""
    raise NotImplementedError

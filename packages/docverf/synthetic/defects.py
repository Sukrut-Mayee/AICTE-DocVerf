"""Defect injection from the TRD §13.2 catalog."""

from docverf.schemas import GroundTruth


def inject_defect(app: GroundTruth, defect: str) -> GroundTruth:
    """`defect` is a code from TRD §13.2 (e.g. AREA_MISMATCH); records an InjectedDefect."""
    raise NotImplementedError

"""Generate synthetic applications and ground truth (TRD §13.1)."""

from pathlib import Path

from docverf.schemas import GroundTruth


def generate_dataset(out_dir: Path, n_apps: int = 20) -> list[GroundTruth]:
    """About 8 clean and 12 defective applications under out_dir/app001 ... (data/synthetic)."""
    raise NotImplementedError

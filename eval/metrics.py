"""Evaluation metrics (TRD §16): field accuracy, defect recall/precision, source verification
counts, per-stage timing, alert latency. Output: eval/report.md plus JSON.

TODO(question): TRD §16 gives no function signatures; this one is derived from the prose.
"""

from pathlib import Path


def evaluate(synthetic_dir: Path, out_dir: Path) -> None:
    raise NotImplementedError

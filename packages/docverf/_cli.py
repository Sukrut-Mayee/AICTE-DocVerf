"""Shared argparse stub for `python -m docverf.<module> <path>` (TRD §1 rule 7)."""

import argparse
from pathlib import Path


def cli(module: str, description: str | None) -> None:
    """Parse `path` and `--out`, then fail until the module owner implements the CLI."""
    parser = argparse.ArgumentParser(prog=f"python -m docverf.{module}", description=description)
    parser.add_argument("path", type=Path, help="input file or folder")
    parser.add_argument(
        "--out", type=Path, default=Path("data/out") / module, help="output folder for JSON"
    )
    parser.parse_args()
    raise NotImplementedError(f"docverf.{module} CLI is not implemented yet")

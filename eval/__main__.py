"""CLI stub: python -m eval <synthetic_dir> [--out eval/]."""

import argparse
from pathlib import Path

parser = argparse.ArgumentParser(prog="python -m eval", description=__doc__)
parser.add_argument("path", type=Path, help="folder of synthetic applications with ground truth")
parser.add_argument("--out", type=Path, default=Path("eval"), help="output folder")
parser.parse_args()
raise NotImplementedError("eval CLI is not implemented yet")

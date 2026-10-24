"""Evaluate pipeline findings against injected defects in a synthetic dataset."""

import argparse
from pathlib import Path

from .metrics import evaluate


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m eval", description=__doc__)
    parser.add_argument(
        "path", type=Path, help="folder of synthetic applications with ground truth"
    )
    parser.add_argument("--out", type=Path, default=Path("eval"), help="output folder")
    args = parser.parse_args()

    report = evaluate(args.path, args.out)
    recall = report["defect_recall"]
    print(
        f"Defect recall: {recall['detected']}/{recall['total']} "
        f"({recall['recall']})"
    )
    print(f"Reports written to {args.out}")

    return int(bool(report["errors"] or report["unknown_defects"]))


if __name__ == "__main__":
    raise SystemExit(main())

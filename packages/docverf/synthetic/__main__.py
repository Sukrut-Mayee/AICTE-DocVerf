"""CLI: python -m docverf.synthetic --out data/synthetic --n 20 [--seed 42] [--no-pdf]."""

import argparse
from pathlib import Path

from docverf.synthetic.generate import generate_dataset


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m docverf.synthetic", description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("data/synthetic"), help="output folder")
    parser.add_argument("--n", type=int, default=20, help="number of applications")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-pdf", action="store_true", help="write HTML / JSON / photos only")
    args = parser.parse_args(argv)
    if args.n < 1:
        parser.error("--n must be at least 1")

    truths = generate_dataset(args.out, args.n, args.seed, render=not args.no_pdf)
    for truth in truths:
        codes = sorted({d.defect for d in truth.injected_defects}) or ["(clean)"]
        print(f"{truth.app_id}  {len(truth.documents)} docs  {', '.join(codes)}")
    print(f"\nwrote {len(truths)} applications to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

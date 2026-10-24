"""CLI: python -m docverf.reasoning <folder of ExtractionResult JSON> [--checks checks.json]
[--out data/out/reasoning] [--exclude DOC_ID [DOC_ID ...]].

Prints the findings and writes <out>/<app_id>.json. With --exclude it instead simulates what
happens to every rule when those documents are removed (TRD §8.6) and writes
<out>/<app_id>_impact.json."""

import argparse
import json
import sys
from pathlib import Path

from docverf.reasoning.entity_graph import SEVERITY_RANK
from docverf.reasoning.impact_sim import simulate_exclusion
from docverf.reasoning.run import aggregate, run_reasoning
from docverf.schemas import CheckResult, ExtractionResult


def _table(header: tuple[str, ...], rows: list[tuple[str, ...]]) -> None:
    """Print rows in aligned columns; the last column (a sentence) is left unpadded."""
    widths = [max(len(r[i]) for r in [header, *rows]) for i in range(len(header) - 1)]
    for row in [header, *rows]:
        cells = [cell.ljust(w) for cell, w in zip(row[:-1], widths, strict=True)]
        print("  ".join([*cells, row[-1]]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m docverf.reasoning", description=__doc__)
    parser.add_argument("path", type=Path, help="folder of ExtractionResult JSON files")
    parser.add_argument("--checks", type=Path, help="JSON list of CheckResult (provenance etc.)")
    parser.add_argument(
        "--out", type=Path, default=Path("data/out/reasoning"), help="output folder for JSON"
    )
    parser.add_argument(
        "--exclude", nargs="+", metavar="DOC_ID", help="simulate removing these documents"
    )
    args = parser.parse_args(argv)

    files = [p for p in sorted(args.path.glob("*.json")) if p != args.checks]
    extractions = [ExtractionResult.model_validate_json(p.read_text("utf-8")) for p in files]
    if not extractions:
        parser.error(f"no ExtractionResult JSON files in {args.path}")
    checks = (
        [CheckResult.model_validate(c) for c in json.loads(args.checks.read_text("utf-8"))]
        if args.checks
        else []
    )
    app_id = extractions[0].app_id
    args.out.mkdir(parents=True, exist_ok=True)

    if args.exclude:
        try:
            impact = simulate_exclusion(app_id, extractions, checks, args.exclude)
        except ValueError as exc:
            parser.error(str(exc))
        print(f"{app_id}: if {', '.join(impact['excluded'])} were removed\n")
        _table(
            ("RULE", "BEFORE", "AFTER", "STATUS", "MESSAGE"),
            [
                (c["rule_id"], c["before"], c["after"], c["status"], c["message"])
                for c in impact["conclusions"]
            ],
        )
        out_file = args.out / f"{app_id}_impact.json"
        out_file.write_text(json.dumps(impact, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nwrote {out_file}")
        return 0

    findings = run_reasoning(app_id, extractions, checks)
    findings.sort(key=lambda f: -SEVERITY_RANK[f.severity])
    statuses, priority = aggregate(app_id, findings, checks, [e.doc_id for e in extractions])

    print(f"{app_id}: {len(findings)} finding(s), priority {priority}\n")
    _table(
        ("SEVERITY", "TYPE", "RULE", "DOCUMENTS", "MESSAGE"),
        [
            (f.severity.value, f.type.value, f.rule_id or "-", ", ".join(f.doc_ids), f.message)
            for f in findings
        ],
    )
    print()
    for s in statuses:
        verification = f" [{s.verification.value}]" if s.verification else ""
        print(f"{s.doc_id}: {s.overall.value}{verification} - {s.note}")

    result = {
        "app_id": app_id,
        "priority": priority,
        "findings": [f.model_dump(mode="json") for f in findings],
        "documents": [s.model_dump(mode="json") for s in statuses],
    }
    out_file = args.out / f"{app_id}.json"
    out_file.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {out_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Integration checker (read-only): pipeline JSON vs. the API contract and the synthetic truth.

    python -m scripts.check_integration [--pipeline data/out/pipeline] [--synthetic data/synthetic]

For every <pipeline>/appNNN.json:
  - validate it with the officer API's own loader (services/api/pipeline.py, contract B);
  - compare its findings with data/synthetic/appNNN/ground_truth.json, using eval's
    defect -> finding matcher (eval/metrics.py), so there is one mapping, not two.
Prints: app | contract valid | priority | expected defects | caught | missed | unexpected high.
Exit code 1 if any pipeline file fails the contract.

If the pipeline folder does not exist yet, a TEMPORARY oracle pipeline is built in a temp folder
(run_reasoning + aggregate on the ground-truth fields, no provenance/forensic/issuer checks) and
checked instead. It is never written to data/out/pipeline.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

if __package__ in (None, ""):  # run as a file: make the repo root importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from docverf.reasoning.run import aggregate, run_reasoning  # noqa: E402
from docverf.schemas import GroundTruth  # noqa: E402
from docverf.synthetic.model import extractions_from_truth  # noqa: E402

from eval.metrics import _finding_matches  # noqa: E402
from services.api.pipeline import (  # noqa: E402
    ApplicationNotFound,
    InvalidPipeline,
    PipelineRepository,
    is_valid_app_id,
)

ORACLE_LABEL = "oracle: ground-truth fields through run_reasoning + aggregate, no checks"


@dataclass
class Row:
    app_id: str
    valid: bool | None  # None: no pipeline file
    reason: str = ""
    priority: int | None = None
    expected: list[str] = field(default_factory=list)
    caught: list[str] = field(default_factory=list)
    missed: list[str] = field(default_factory=list)
    unexpected_high: list[str] = field(default_factory=list)


def _reason(exc: Exception) -> str:
    """The loader's message plus the first validation error under it, if any."""
    cause = exc.__cause__
    detail = ""
    if cause is not None and hasattr(cause, "errors"):
        first = cause.errors()[0]
        detail = f": {'.'.join(str(p) for p in first['loc'])} {first['msg']}"
    elif cause is not None:
        detail = f": {cause}"
    return f"{exc}{detail}"


def check_app(pipeline_dir: Path, synthetic_dir: Path, app_id: str) -> Row:
    truth_path = synthetic_dir / app_id / "ground_truth.json"
    truth = (
        GroundTruth.model_validate_json(truth_path.read_text("utf-8"))
        if truth_path.is_file()
        else None
    )
    expected = sorted({d.defect for d in truth.injected_defects}) if truth else []
    row = Row(app_id, valid=None, expected=expected)

    try:
        loaded = PipelineRepository(pipeline_dir).load(app_id)
    except ApplicationNotFound:
        row.reason = "no pipeline file"
        row.missed = expected
        return row
    except InvalidPipeline as exc:
        row.valid, row.reason, row.missed = False, _reason(exc), expected
        return row

    row.valid, row.priority = True, loaded.data.priority
    if truth is None:
        row.reason = "no ground_truth.json"
    findings = [f.model_dump(mode="json") for f in loaded.data.findings]
    for code in expected:
        hit = any(_finding_matches(f, code, app_id) for f in findings)
        (row.caught if hit else row.missed).append(code)
    for f in findings:
        if f["severity"] == "high" and not any(_finding_matches(f, c, app_id) for c in expected):
            row.unexpected_high.append(f.get("rule_id") or f["type"])
    return row


def check(pipeline_dir: Path, synthetic_dir: Path) -> list[Row]:
    """One row per application that has a pipeline file or a ground truth."""
    app_ids = {p.stem for p in pipeline_dir.glob("*.json") if is_valid_app_id(p.stem)}
    app_ids |= {p.parent.name for p in synthetic_dir.glob("app*/ground_truth.json")}
    return [check_app(pipeline_dir, synthetic_dir, app_id) for app_id in sorted(app_ids)]


def build_oracle_pipeline(synthetic_dir: Path, out_dir: Path) -> Path:
    """Contract-B files from the ground truth alone (perfect extraction, no checks). For testing
    the checker before the real pipeline exists; `out_dir` must not be data/out/pipeline."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for truth_path in sorted(synthetic_dir.glob("app*/ground_truth.json")):
        truth = GroundTruth.model_validate_json(truth_path.read_text("utf-8"))
        extractions = extractions_from_truth(truth)
        findings = run_reasoning(truth.app_id, extractions, [])
        documents, priority = aggregate(truth.app_id, findings, [], [e.doc_id for e in extractions])
        output = {
            "app_id": truth.app_id,
            "extractions": [e.model_dump(mode="json") for e in extractions],
            "checks": [],
            "findings": [f.model_dump(mode="json") for f in findings],
            "documents": [d.model_dump(mode="json") for d in documents],
            "priority": priority,
            "audit": None,
            "meta": {"source": ORACLE_LABEL, "temporary": True},
        }
        (out_dir / f"{truth.app_id}.json").write_text(
            json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    return out_dir


def table(rows: list[Row]) -> str:
    def cell(items: list[str]) -> str:
        return ", ".join(items) or "-"

    lines = [
        "| app | contract valid | priority | expected defects | caught | missed "
        "| unexpected high |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        valid = {True: "PASS", False: f"FAIL ({r.reason})", None: r.reason or "-"}[r.valid]
        if r.valid and r.reason:
            valid += f" ({r.reason})"
        priority = "-" if r.priority is None else str(r.priority)
        lines.append(
            f"| {r.app_id} | {valid} | {priority} | {cell(r.expected)} | {cell(r.caught)} | "
            f"{cell(r.missed)} | {cell(r.unexpected_high)} |"
        )
    expected = sum(len(r.expected) for r in rows)
    caught = sum(len(r.caught) for r in rows)
    failed = sum(r.valid is False for r in rows)
    lines.append("")
    lines.append(
        f"{len(rows)} applications, {failed} failing the contract, "
        f"{caught}/{expected} defects caught"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.check_integration", description=__doc__
    )
    parser.add_argument("--pipeline", type=Path, default=Path("data/out/pipeline"))
    parser.add_argument("--synthetic", type=Path, default=Path("data/synthetic"))
    args = parser.parse_args(argv)

    if not args.synthetic.is_dir():
        parser.error(f"synthetic data not found: {args.synthetic}")
    if args.pipeline.is_dir():
        rows = check(args.pipeline, args.synthetic)
        print(f"Pipeline: {args.pipeline}\n")
    else:
        with tempfile.TemporaryDirectory(prefix="docverf-oracle-pipeline-") as tmp:
            oracle = build_oracle_pipeline(args.synthetic, Path(tmp))
            print(f"{args.pipeline} does not exist.")
            print(f"TEMPORARY ORACLE PIPELINE in {oracle} ({ORACLE_LABEL}); deleted afterwards.\n")
            rows = check(oracle, args.synthetic)
    print(table(rows))
    return 1 if any(r.valid is False for r in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Evaluation metrics for synthetic applications and pipeline outputs."""

import json
from collections import defaultdict
from pathlib import Path
from typing import Any


_DEFECT_FINDING_MAP = {
    "AREA_MISMATCH": ({"LAND_AREA_AGREE"}, {"attribute_conflict"}),
    "OWNER_MISMATCH": ({"OWNER_IS_TRUST"}, {"relationship_violation"}),
    "NAME_MISMATCH": ({"INSTITUTE_NAME_AGREE"}, {"attribute_conflict"}),
    "EXPIRED_NOC": ({"NOC_VALID_FOR_YEAR"}, {"expired"}),
    "TIMELINE_NOC_BEFORE_TRUST": ({"TL_NOC_AFTER_TRUST"}, {"timeline_violation"}),
    "BAD_REF_FORMAT": ({"NOC_REF_FORMAT"}, {"rule_failed"}),
    "MISSING_DOC": ({"REQUIRED_DOCS"}, {"missing_doc"}),
    "MORTGAGED_LAND": ({"LAND_NOT_MORTGAGED"}, {"rule_failed"}),
    "SIGNED_THEN_EDITED": (set(), {"provenance_failure"}),
    "PASTED_SIGNATURE": (set(), {"forensic_signal"}),
    "DUPLICATE_PHOTO": (set(), {"duplicate"}),
    "ISSUER_MISMATCH": (set(), {"source_mismatch"}),
    "ISSUER_TIMEOUT": ({"ISSUER_LOOKUP"}, set()),
}

_DEFECT_DOC_SUFFIX = {
    "AREA_MISMATCH": "land_deed",
    "OWNER_MISMATCH": "land_deed",
    "NAME_MISMATCH": "noc",
    "EXPIRED_NOC": "noc",
    "TIMELINE_NOC_BEFORE_TRUST": "noc",
    "BAD_REF_FORMAT": "noc",
    "MISSING_DOC": "affidavit",
    "MORTGAGED_LAND": "land_deed",
    "SIGNED_THEN_EDITED": "noc",
    "PASTED_SIGNATURE": "noc",
    "DUPLICATE_PHOTO": "lab_photo",
    "ISSUER_MISMATCH": "noc",
    "ISSUER_TIMEOUT": "noc",
}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read JSON file {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def _findings_from_pipeline(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if not isinstance(data, dict):
        return []
    findings = data.get("findings")
    if isinstance(findings, list):
        return [item for item in findings if isinstance(item, dict)]
    result = data.get("result")
    if isinstance(result, dict):
        return _findings_from_pipeline(result)
    return []


def _finding_matches(
    finding: dict[str, Any], defect: str, app_id: str
) -> bool:
    rule_ids, finding_types = _DEFECT_FINDING_MAP[defect]
    evidence = finding.get("evidence")
    evidence = evidence if isinstance(evidence, dict) else {}
    explicit_code = (
        finding.get("defect")
        or evidence.get("defect")
        or evidence.get("defect_code")
    )
    doc_ids = finding.get("doc_ids")
    if not isinstance(doc_ids, list):
        doc_ids = [finding.get("doc_id")] if finding.get("doc_id") else []
    target_doc = f"{app_id}_{_DEFECT_DOC_SUFFIX[defect]}"
    right_document = not doc_ids or target_doc in doc_ids

    if explicit_code == defect:
        return right_document
    rule_id = finding.get("rule_id") or evidence.get("rule_id")
    finding_type = finding.get("type")
    if rule_id in rule_ids:
        return right_document
    return finding_type in finding_types and right_document


def evaluate(synthetic_dir: Path, out_dir: Path) -> dict[str, Any]:
    """Measure injected-defect recall against per-application pipeline JSON."""
    synthetic_dir = Path(synthetic_dir)
    out_dir = Path(out_dir)
    pipeline_dir = synthetic_dir.parent / "out" / "pipeline"
    if not pipeline_dir.is_dir() and (out_dir / "pipeline").is_dir():
        pipeline_dir = out_dir / "pipeline"

    report: dict[str, Any] = {
        "defect_recall": {"detected": 0, "total": 0, "recall": None},
        "per_defect": {},
        "applications": {},
        "errors": [],
        "unknown_defects": [],
    }
    per_defect: dict[str, dict[str, int]] = defaultdict(
        lambda: {"detected": 0, "total": 0}
    )

    for gt_path in sorted(synthetic_dir.glob("app*/ground_truth.json")):
        app_id = gt_path.parent.name
        try:
            ground_truth = _read_json(gt_path)
        except ValueError as exc:
            report["errors"].append(str(exc))
            report["applications"][app_id] = {"error": str(exc)}
            continue

        injected = ground_truth.get("injected_defects", [])
        if not isinstance(injected, list):
            error = f"Expected injected_defects list in {gt_path}"
            report["errors"].append(error)
            report["applications"][app_id] = {"error": error}
            continue

        pipeline_path = pipeline_dir / f"{app_id}.json"
        findings: list[dict[str, Any]] = []
        pipeline_error = None
        if pipeline_path.is_file():
            try:
                findings = _findings_from_pipeline(_read_json(pipeline_path))
            except ValueError as exc:
                pipeline_error = str(exc)
                report["errors"].append(pipeline_error)
        else:
            pipeline_error = f"Missing pipeline output: {pipeline_path}"
            report["errors"].append(pipeline_error)

        app_detected = 0
        app_total = 0
        defect_results = []
        for injected_defect in injected:
            if not isinstance(injected_defect, dict):
                report["errors"].append(f"Malformed injected defect in {gt_path}")
                continue
            code = injected_defect.get("defect")
            if not isinstance(code, str) or code not in _DEFECT_FINDING_MAP:
                report["unknown_defects"].append(
                    {"app_id": app_id, "defect": code, "detail": injected_defect}
                )
                continue
            detected = any(_finding_matches(item, code, app_id) for item in findings)
            per_defect[code]["total"] += 1
            report["defect_recall"]["total"] += 1
            app_total += 1
            if detected:
                per_defect[code]["detected"] += 1
                report["defect_recall"]["detected"] += 1
                app_detected += 1
            defect_results.append({"defect": code, "detected": detected})

        report["applications"][app_id] = {
            "detected": app_detected,
            "total": app_total,
            "defects": defect_results,
        }
        if pipeline_error:
            report["applications"][app_id]["pipeline_error"] = pipeline_error

    total = report["defect_recall"]["total"]
    if total:
        report["defect_recall"]["recall"] = report["defect_recall"]["detected"] / total
    report["per_defect"] = {
        code: {
            **counts,
            "recall": counts["detected"] / counts["total"] if counts["total"] else None,
        }
        for code, counts in sorted(per_defect.items())
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    lines = [
        "# Evaluation report",
        "",
        f"Defect recall: {report['defect_recall']['detected']}/{total} "
        f"({report['defect_recall']['recall']})",
        "",
        "| Defect | Detected | Total | Recall |",
        "|---|---:|---:|---:|",
    ]
    for code, values in report["per_defect"].items():
        lines.append(
            f"| {code} | {values['detected']} | {values['total']} | {values['recall']} |"
        )
    if report["errors"]:
        lines.extend(["", "## Data errors", ""])
        lines.extend(f"- {error}" for error in report["errors"])
    if report["unknown_defects"]:
        lines.extend(["", "## Unknown defect codes", ""])
        lines.extend(
            f"- {item['app_id']}: {item['defect']}" for item in report["unknown_defects"]
        )
    (out_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report

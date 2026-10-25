import json
import subprocess
import sys

import pytest

from eval.metrics import evaluate


def _write_app(root, app_id, defects):
    app_dir = root / app_id
    app_dir.mkdir(parents=True)
    (app_dir / "ground_truth.json").write_text(
        json.dumps({"app_id": app_id, "injected_defects": defects}),
        encoding="utf-8",
    )


def test_defect_recall_matches_rule_finding_on_target_document(tmp_path):
    synthetic = tmp_path / "data" / "synthetic"
    _write_app(
        synthetic,
        "app001",
        [{"doc_id": "app001_mortgagedland", "defect": "MORTGAGED_LAND", "detail": "Synthetic"}],
    )
    pipeline = tmp_path / "data" / "out" / "pipeline"
    pipeline.mkdir(parents=True)
    (pipeline / "app001.json").write_text(
        json.dumps(
            {
                "findings": [
                    {
                        "finding_id": "f_1",
                        "app_id": "app001",
                        "type": "rule_failed",
                        "rule_id": "LAND_NOT_MORTGAGED",
                        "doc_ids": ["app001_land_deed"],
                        "message": "Synthetic fixture finding",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    report = evaluate(synthetic, tmp_path / "eval")
    assert report["defect_recall"] == {"detected": 1, "total": 1, "recall": 1.0}
    assert report["per_defect"]["MORTGAGED_LAND"]["recall"] == 1.0
    assert (tmp_path / "eval" / "report.json").is_file()
    assert (tmp_path / "eval" / "report.md").is_file()


def test_missing_pipeline_and_unknown_defect_are_explicit(tmp_path):
    synthetic = tmp_path / "synthetic"
    _write_app(
        synthetic,
        "app001",
        [
            {"doc_id": "app001_noc", "defect": "BAD_REF_FORMAT", "detail": "Synthetic"},
            {"doc_id": "app001_unknown", "defect": "UNLISTED_CODE", "detail": "Synthetic"},
        ],
    )

    report = evaluate(synthetic, tmp_path / "eval")
    assert report["defect_recall"] == {"detected": 0, "total": 1, "recall": 0.0}
    assert report["applications"]["app001"]["pipeline_error"]
    assert report["unknown_defects"][0]["defect"] == "UNLISTED_CODE"


def test_no_injected_defects_has_undefined_recall(tmp_path):
    synthetic = tmp_path / "synthetic"
    _write_app(synthetic, "app001", [])

    report = evaluate(synthetic, tmp_path / "eval")
    assert report["defect_recall"] == {"detected": 0, "total": 0, "recall": None}


def test_invalid_pipeline_json_is_reported(tmp_path):
    synthetic = tmp_path / "data" / "synthetic"
    _write_app(
        synthetic,
        "app001",
        [{"doc_id": "app001_noc", "defect": "BAD_REF_FORMAT", "detail": "Synthetic"}],
    )
    pipeline = tmp_path / "data" / "out" / "pipeline"
    pipeline.mkdir(parents=True)
    (pipeline / "app001.json").write_text("{invalid", encoding="utf-8")

    report = evaluate(synthetic, tmp_path / "eval")
    assert report["defect_recall"] == {"detected": 0, "total": 1, "recall": 0.0}
    assert any("Could not read JSON file" in error for error in report["errors"])


def test_missing_document_recall_uses_injected_document_id(tmp_path):
    synthetic = tmp_path / "data" / "synthetic"
    _write_app(
        synthetic,
        "app001",
        [{"doc_id": "app001_affidavit", "defect": "MISSING_DOC", "detail": "Synthetic"}],
    )
    pipeline = tmp_path / "data" / "out" / "pipeline"
    pipeline.mkdir(parents=True)
    (pipeline / "app001.json").write_text(
        json.dumps(
            {
                "findings": [
                    {
                        "finding_id": "f_1",
                        "app_id": "app001",
                        "type": "missing_doc",
                        "doc_ids": ["app001_affidavit"],
                        "message": "Required affidavit is missing",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    report = evaluate(synthetic, tmp_path / "eval")
    assert report["defect_recall"] == {"detected": 1, "total": 1, "recall": 1.0}


def test_eval_cli_reads_data_pipeline_outputs(tmp_path):
    synthetic = tmp_path / "data" / "synthetic"
    _write_app(
        synthetic,
        "app001",
        [{"doc_id": "app001_land_deed", "defect": "MORTGAGED_LAND", "detail": "Synthetic"}],
    )
    pipeline = tmp_path / "data" / "out" / "pipeline"
    pipeline.mkdir(parents=True)
    (pipeline / "app001.json").write_text(
        json.dumps(
            {
                "findings": [
                    {
                        "finding_id": "f_1",
                        "app_id": "app001",
                        "type": "rule_failed",
                        "rule_id": "LAND_NOT_MORTGAGED",
                        "doc_ids": ["app001_land_deed"],
                        "message": "Synthetic fixture finding",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    report_dir = tmp_path / "reports"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "eval",
            str(synthetic),
            "--out",
            str(report_dir),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Defect recall: 1/1 (1.0)" in result.stdout
    assert (report_dir / "report.json").is_file()
    assert (report_dir / "report.md").is_file()


def _issuer_timeout_report(tmp_path, documents, findings=()):
    synthetic = tmp_path / "data" / "synthetic"
    _write_app(
        synthetic,
        "app020",
        [{"doc_id": "app020_noc", "defect": "ISSUER_TIMEOUT", "detail": "Synthetic"}],
    )
    pipeline = tmp_path / "data" / "out" / "pipeline"
    pipeline.mkdir(parents=True)
    (pipeline / "app020.json").write_text(
        json.dumps({"findings": list(findings), "documents": documents}), encoding="utf-8"
    )
    return evaluate(synthetic, tmp_path / "eval")["defect_recall"]


def _doc(doc_id, verification):
    return {"doc_id": doc_id, "overall": "manual_review_required", "verification": verification}


def test_issuer_timeout_is_caught_by_a_pending_noc_not_a_finding(tmp_path):
    recall = _issuer_timeout_report(tmp_path, [_doc("app020_noc", "verification_pending")])
    assert recall == {"detected": 1, "total": 1, "recall": 1.0}


@pytest.mark.parametrize(
    "documents",
    [
        [_doc("app020_noc", "verified")],
        [_doc("app020_noc", None)],
        [_doc("app020_land_deed", "verification_pending")],  # pending, but not the NOC
        [],
    ],
    ids=["verified", "no-status", "wrong-document", "no-documents"],
)
def test_issuer_timeout_is_missed_without_a_pending_noc(tmp_path, documents):
    assert _issuer_timeout_report(tmp_path, documents)["detected"] == 0

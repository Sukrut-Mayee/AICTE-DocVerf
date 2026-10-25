"""scripts/check_integration.py on a temporary oracle pipeline built from synthetic ground truth."""

import json

import pytest
from docverf.synthetic.generate import generate_dataset

from scripts.check_integration import build_fallback_pipeline, check, main, table

REASONING = {  # defects reasoning finds from the fields alone (TRD §13.2)
    "AREA_MISMATCH", "OWNER_MISMATCH", "NAME_MISMATCH", "EXPIRED_NOC",
    "TIMELINE_NOC_BEFORE_TRUST", "BAD_REF_FORMAT", "MISSING_DOC", "MORTGAGED_LAND",
}  # fmt: skip


@pytest.fixture(scope="module")
def dirs(tmp_path_factory):
    root = tmp_path_factory.mktemp("integration")
    synthetic = root / "synthetic"
    generate_dataset(synthetic, 20, render=False)
    return synthetic, build_fallback_pipeline(synthetic, root / "pipeline")


def test_oracle_pipeline_passes_the_contract_and_catches_every_reasoning_defect(dirs):
    synthetic, pipeline = dirs
    rows = check(pipeline, synthetic)
    assert len(rows) == 20 and all(r.valid for r in rows)
    for r in rows:
        assert set(r.caught) == set(r.expected) & REASONING, r.app_id
        assert set(r.missed) == set(r.expected) - REASONING, (
            r.app_id
        )  # need provenance / issuer checks
        assert r.unexpected_high == [], r.app_id
    assert [r.priority for r in rows[:8]] == [0] * 8  # clean applications


def test_oracle_files_are_labelled_temporary(dirs):
    _, pipeline = dirs
    data = json.loads((pipeline / "app009.json").read_text("utf-8"))
    assert data["meta"]["source"] == "ground_truth_fallback" and "Not live" in data["meta"]["note"]
    assert {"app_id", "extractions", "checks", "findings", "documents", "priority"} <= set(data)


def test_contract_failures_are_reported_with_a_reason(dirs, tmp_path):
    synthetic, pipeline = dirs
    bad = tmp_path / "pipeline"
    bad.mkdir()
    for p in pipeline.glob("*.json"):
        (bad / p.name).write_text(p.read_text("utf-8"), encoding="utf-8")
    (bad / "app001.json").write_text("{not json", encoding="utf-8")
    wrong = json.loads((bad / "app002.json").read_text("utf-8"))
    wrong["priority"] = -5
    (bad / "app002.json").write_text(json.dumps(wrong), encoding="utf-8")
    other = json.loads((bad / "app009.json").read_text("utf-8"))
    other["findings"][0]["app_id"] = "app999"
    (bad / "app009.json").write_text(json.dumps(other), encoding="utf-8")
    (bad / "app010.json").unlink()

    rows = {r.app_id: r for r in check(bad, synthetic)}
    assert rows["app001"].valid is False and "not readable JSON" in rows["app001"].reason
    assert rows["app002"].valid is False and "priority" in rows["app002"].reason
    assert rows["app009"].valid is False and "different application" in rows["app009"].reason
    assert rows["app010"].valid is None and rows["app010"].missed == [
        "MORTGAGED_LAND",
        "OWNER_MISMATCH",
    ]
    assert "FAIL" in table(list(rows.values()))
    assert main(["--pipeline", str(bad), "--synthetic", str(synthetic)]) == 1


def test_an_unexpected_high_finding_is_listed(dirs, tmp_path):
    synthetic, pipeline = dirs
    data = json.loads((pipeline / "app001.json").read_text("utf-8"))
    finding = json.loads((pipeline / "app012.json").read_text("utf-8"))["findings"][0]
    data["findings"] = [{**finding, "app_id": "app001"}]
    (tmp_path / "app001.json").write_text(json.dumps(data), encoding="utf-8")
    (row,) = [r for r in check(tmp_path, synthetic) if r.app_id == "app001"]
    assert row.valid and row.unexpected_high == ["NOC_VALID_FOR_YEAR"]


def test_cli_without_a_pipeline_uses_a_temporary_oracle_and_writes_nothing(dirs, tmp_path, capsys):
    synthetic, _ = dirs
    missing = tmp_path / "out" / "pipeline"
    assert main(["--pipeline", str(missing), "--synthetic", str(synthetic)]) == 0
    out = capsys.readouterr().out
    assert "TEMPORARY ORACLE PIPELINE" in out and "| app020 | PASS |" in out
    assert not missing.exists()


def test_cli_on_a_real_pipeline_folder(dirs, capsys):
    synthetic, pipeline = dirs
    assert main(["--pipeline", str(pipeline), "--synthetic", str(synthetic)]) == 0
    out = capsys.readouterr().out
    assert "TEMPORARY" not in out and "0 failing the contract, 13/18 defects caught" in out


# ---- --emit: the demo fallback pipeline ----


def test_emit_writes_all_20_apps_with_every_document(dirs, tmp_path, capsys):
    synthetic, _ = dirs
    out = tmp_path / "pipeline"
    assert main(["--synthetic", str(synthetic), "--emit", str(out)]) == 0
    assert "FALLBACK" in capsys.readouterr().out
    files = sorted(out.glob("app*.json"))
    assert len(files) == 20
    for path in files:
        data = json.loads(path.read_text("utf-8"))
        truth = json.loads((synthetic / path.stem / "ground_truth.json").read_text("utf-8"))
        doc_ids = [d["doc_id"] for d in truth["documents"]]
        assert data["meta"] == {
            "source": "ground_truth_fallback",
            "note": data["meta"]["note"],
            "temporary": False,
        }
        assert [e["doc_id"] for e in data["extractions"]] == doc_ids
        assert sorted(d["doc_id"] for d in data["documents"]) == sorted(doc_ids)  # ALL docs
        assert data["checks"] == [] and data["audit"] is None
    rows = check(out, synthetic)
    assert all(r.valid for r in rows) and len(rows) == 20


def test_emit_can_rerun_over_its_own_output(dirs, tmp_path):
    synthetic, _ = dirs
    out = tmp_path / "pipeline"
    assert main(["--synthetic", str(synthetic), "--emit", str(out)]) == 0
    assert main(["--synthetic", str(synthetic), "--emit", str(out)]) == 0


def test_emit_refuses_to_overwrite_real_pipeline_output(dirs, tmp_path):
    synthetic, _ = dirs
    out = tmp_path / "pipeline"
    out.mkdir()
    real = out / "app005.json"
    real.write_text(
        json.dumps({"app_id": "app005", "meta": {"source": "pipeline"}}), encoding="utf-8"
    )
    broken = out / "app006.json"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        main(["--synthetic", str(synthetic), "--emit", str(out)])
    assert exc.value.code == 2
    assert json.loads(real.read_text("utf-8"))["meta"]["source"] == "pipeline"  # untouched
    assert broken.read_text("utf-8") == "{not json"
    assert not (out / "app001.json").exists()  # refused before writing anything
    assert main(["--synthetic", str(synthetic), "--emit", str(out), "--force"]) == 0
    assert json.loads(real.read_text("utf-8"))["meta"]["source"] == "ground_truth_fallback"


def test_a_pending_noc_counts_as_issuer_timeout_caught(dirs, tmp_path):
    synthetic, pipeline = dirs
    rows = check(pipeline, synthetic)
    (before,) = [r for r in rows if "ISSUER_TIMEOUT" in r.expected]
    timeout_app = before.app_id
    data = json.loads((pipeline / f"{timeout_app}.json").read_text("utf-8"))
    assert "ISSUER_TIMEOUT" in before.missed  # no issuer check in the fallback

    noc = next(d for d in data["documents"] if d["doc_id"] == f"{timeout_app}_noc")
    noc["verification"] = "verification_pending"
    (tmp_path / f"{timeout_app}.json").write_text(json.dumps(data), encoding="utf-8")
    (after,) = [r for r in check(tmp_path, synthetic) if r.app_id == timeout_app]
    assert "ISSUER_TIMEOUT" in after.caught and "ISSUER_TIMEOUT" not in after.missed

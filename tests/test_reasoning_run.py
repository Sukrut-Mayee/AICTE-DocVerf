"""Checkpoint 4: run_reasoning, checks_to_findings, aggregate and the CLI (TRD §8.7, App. A)."""

import json
import subprocess
import sys
from datetime import datetime

import pytest
from docverf.reasoning.__main__ import main
from docverf.reasoning.entity_graph import build_claims
from docverf.reasoning.rule_engine import new_finding
from docverf.reasoning.run import (
    _field_key,
    aggregate,
    checks_to_findings,
    dedupe,
    run_reasoning,
)
from docverf.schemas import (
    CheckResult,
    CheckStatus,
    DocOverallStatus,
    Finding,
    FindingType,
    Layer,
    Severity,
    VerificationStatus,
)

from tests.apps import FIXTURES, load_app

VS = VerificationStatus


def check(doc_id, name, status=CheckStatus.CLEAN, severity=Severity.INFO, vs=None, layer=Layer.D):
    return CheckResult(
        doc_id=doc_id,
        layer=layer,
        check=name,
        status=status,
        severity=severity,
        reason=f"{name} reason",
        evidence={"detail": 1},
        verification_status=vs,
        checked_at=datetime(2027, 1, 1),
    )


def triples(findings):
    return {(f.rule_id, f.type.value, f.severity.value) for f in findings}


def test_appendix_a_conflict_app_gives_exactly_the_expected_findings():
    findings = run_reasoning("appx", load_app("app_conflict"), [])
    assert len(findings) == 5
    assert triples(findings) == {
        ("NOC_VALID_FOR_YEAR", "expired", "high"),
        ("LAND_AREA_AGREE", "attribute_conflict", "high"),
        ("LAND_AREA_AGREE", "unreadable", "low"),  # the affidavit area, confidence 0.62
        ("OWNER_IS_TRUST", "relationship_violation", "high"),
        ("TL_NOC_AFTER_TRUST", "timeline_violation", "high"),
    }


def test_clean_app_gives_zero_findings_and_all_documents_clean():
    docs = load_app("app_clean")
    assert run_reasoning("appx", docs, []) == []
    statuses, priority = aggregate("appx", [], [], [d.doc_id for d in docs])
    assert priority == 0
    assert {s.overall for s in statuses} == {DocOverallStatus.NO_ISSUES}
    assert {s.note for s in statuses} == {"No issues found."}


def test_aggregate_conflict_app():
    docs = load_app("app_conflict")
    findings = run_reasoning("appx", docs, [])
    statuses, priority = aggregate("appx", findings, [], [d.doc_id for d in docs])
    assert priority == 4 * 100 + 1  # four high, one low
    overall = {s.doc_id: s.overall for s in statuses}
    assert overall == {
        "appx_affidavit": DocOverallStatus.MANUAL_REVIEW_REQUIRED,  # only an unreadable field
        "appx_application_form": DocOverallStatus.FLAGGED,
        "appx_land_deed": DocOverallStatus.FLAGGED,
        "appx_noc": DocOverallStatus.FLAGGED,
    }
    noc = next(s for s in statuses if s.doc_id == "appx_noc")
    assert len(noc.finding_ids) == 2 and noc.note.endswith(".")
    assert noc.note.startswith("NOC expires on")


def test_duplicate_unreadable_findings_are_reduced_to_one():
    def low_valid_until(docs):  # noted by NOC_VALID_FOR_YEAR and TL_NOC_ISSUE_BEFORE_EXPIRY
        next(d for d in docs if d.doc_type.value == "noc").fields["valid_until"].confidence = 0.4

    docs = load_app("app_clean")
    low_valid_until(docs)
    findings = run_reasoning("appx", docs, [])
    assert [(f.type.value, f.attribute) for f in findings] == [("undetermined", "valid_until")]


def test_graph_and_rule_findings_share_a_field_key():
    (unreadable,) = [
        f
        for f in run_reasoning("appx", load_app("app_conflict"), [])
        if f.type is FindingType.UNREADABLE
    ]
    assert unreadable.attribute == "area"  # the claim attribute ...
    assert _field_key("appx", unreadable) == (
        "appx_affidavit",
        "land_area_declared",
    )  # ... the field


def test_dedupe_keeps_the_most_severe():
    rule = {"id": "R", "finding_type": "undetermined", "severity": "info"}

    def make(ftype, severity):
        return new_finding(
            "appx", rule, "m", ftype=ftype, severity=severity, doc_ids=["appx_noc"], attribute="x"
        )

    info, low = (
        make(FindingType.UNDETERMINED, Severity.INFO),
        make(FindingType.UNREADABLE, Severity.LOW),
    )
    assert dedupe("appx", [info, low]) == [low]
    assert dedupe("appx", [low, info]) == [low]


@pytest.mark.parametrize(
    "c, expected",
    [
        (
            check(
                "d", "pdf_signature", CheckStatus.MISMATCH, Severity.MEDIUM, VS.MISMATCH_DETECTED
            ),
            (FindingType.PROVENANCE_FAILURE, Severity.HIGH),
        ),
        (
            check("d", "hash_duplicate", CheckStatus.SUSPICIOUS, Severity.LOW),
            (FindingType.DUPLICATE, Severity.HIGH),
        ),
        (
            check("d", "ela", CheckStatus.SUSPICIOUS, Severity.MEDIUM),
            (FindingType.FORENSIC_SIGNAL, Severity.MEDIUM),
        ),
        (
            check("d", "copy_move", CheckStatus.SUSPICIOUS, Severity.HIGH),
            (FindingType.FORENSIC_SIGNAL, Severity.HIGH),
        ),
        (
            check("d", "noise", CheckStatus.SUSPICIOUS, Severity.LOW),
            (FindingType.FORENSIC_SIGNAL, Severity.LOW),
        ),
        (
            check("d", "metadata", CheckStatus.SUSPICIOUS, Severity.MEDIUM),
            (FindingType.FORENSIC_SIGNAL, Severity.MEDIUM),
        ),
        (
            check("d", "ai_gen", CheckStatus.SUSPICIOUS, Severity.HIGH),
            (FindingType.FORENSIC_SIGNAL, Severity.LOW),
        ),  # capped
        (
            check("d", "ai_gen", CheckStatus.SUSPICIOUS, Severity.INFO),
            (FindingType.FORENSIC_SIGNAL, Severity.INFO),
        ),  # a cap never raises
        (
            check("d", "ref_format", CheckStatus.MISMATCH, Severity.MEDIUM, layer=Layer.C),
            (FindingType.RULE_FAILED, Severity.MEDIUM),
        ),
        (
            check("d", "template", CheckStatus.SUSPICIOUS, Severity.LOW, layer=Layer.C),
            (FindingType.RULE_FAILED, Severity.LOW),
        ),
        (
            check("d", "issuer_lookup", vs=VS.MISMATCH_DETECTED, layer=Layer.A),
            (FindingType.SOURCE_MISMATCH, Severity.HIGH),
        ),
        (
            check("d", "issuer_lookup", vs=VS.EXPIRED, layer=Layer.A),
            (FindingType.EXPIRED, Severity.HIGH),
        ),
    ],
)
def test_checks_to_findings_mapping(c, expected):
    (f,) = checks_to_findings("appx", [c])
    assert (f.type, f.severity) == expected
    assert (f.doc_ids, f.layer) == ([c.doc_id], c.layer)
    assert f.evidence == {"check": c.check, "detail": 1}  # the check's evidence is kept
    if f.type is FindingType.FORENSIC_SIGNAL:
        assert f.message == f"Preliminary indicator: {c.reason}"
    assert "forged" not in f.message.lower() and "fake" not in f.message.lower()


@pytest.mark.parametrize(
    "c",
    [
        check("d", "ela"),  # clean
        check("d", "ela", CheckStatus.ERROR),  # could not run
        check("d", "ela", CheckStatus.NOT_APPLICABLE),
        check("d", "pdf_signature", CheckStatus.VERIFIED, vs=VS.VERIFIED),
        check("d", "qr", CheckStatus.CLEAN, vs=VS.VERIFIED),
        check("d", "issuer_lookup", vs=VS.VERIFIED),
        check("d", "issuer_lookup", vs=VS.VERIFICATION_PENDING),
        check("d", "issuer_lookup", vs=VS.SOURCE_UNAVAILABLE),
        check("d", "issuer_lookup", vs=VS.MANUAL_REVIEW_REQUIRED),
        check("d", "issuer_lookup", CheckStatus.ERROR),  # no verification_status at all
    ],
)
def test_checks_that_need_no_finding(c):
    assert checks_to_findings("appx", [c]) == []


def test_fake_checks_through_run_reasoning_and_aggregate():
    docs = load_app("app_clean")
    checks = [
        check(
            "appx_land_deed", "hash_duplicate", CheckStatus.MISMATCH, Severity.HIGH, layer=Layer.A
        ),
        check(
            "appx_noc",
            "pdf_signature",
            CheckStatus.MISMATCH,
            Severity.HIGH,
            VS.MISMATCH_DETECTED,
            Layer.A,
        ),
        check(
            "appx_affidavit",
            "issuer_lookup",
            CheckStatus.NOT_APPLICABLE,
            vs=VS.VERIFICATION_PENDING,
            layer=Layer.A,
        ),
        check("appx_application_form", "ela", CheckStatus.SUSPICIOUS, Severity.MEDIUM),
        check("appx_noc", "issuer_lookup", vs=VS.VERIFIED, layer=Layer.A),
    ]
    findings = run_reasoning("appx", docs, checks)
    assert sorted((f.type.value, f.severity.value, f.doc_ids[0][5:]) for f in findings) == [
        ("duplicate", "high", "land_deed"),
        ("forensic_signal", "medium", "application_form"),
        ("provenance_failure", "high", "noc"),
    ]  # the pending issuer lookup gives no finding
    statuses, priority = aggregate("appx", findings, checks, [d.doc_id for d in docs])
    assert priority == 2 * 100 + 10
    by_doc = {s.doc_id[5:]: s for s in statuses}
    assert by_doc["land_deed"].overall is DocOverallStatus.FLAGGED
    assert by_doc["application_form"].overall is DocOverallStatus.FLAGGED  # medium finding
    assert by_doc["application_form"].note.startswith("Preliminary indicator: ela reason")
    assert by_doc["noc"].overall is DocOverallStatus.FLAGGED
    assert by_doc["noc"].verification is VS.MISMATCH_DETECTED  # worst of mismatch / verified
    affidavit = by_doc["affidavit"]
    assert affidavit.overall is DocOverallStatus.MANUAL_REVIEW_REQUIRED
    assert affidavit.verification is VS.VERIFICATION_PENDING
    assert affidavit.finding_ids == [] and affidavit.note == "Verification pending."


def test_aggregate_precedence():
    rule = {"id": "R", "finding_type": "rule_failed", "severity": "low"}

    def f(ftype, severity):
        return new_finding(
            "appx", rule, "msg.", ftype=ftype, severity=severity, doc_ids=["appx_noc"]
        )

    def overall(findings, checks=()):
        (s,), _ = aggregate("appx", findings, list(checks))
        return s.overall

    flagged, manual, clean = (
        DocOverallStatus.FLAGGED,
        DocOverallStatus.MANUAL_REVIEW_REQUIRED,
        DocOverallStatus.NO_ISSUES,
    )
    unreadable = f(FindingType.UNREADABLE, Severity.LOW)
    medium = f(FindingType.RULE_FAILED, Severity.MEDIUM)
    pending = check("appx_noc", "issuer_lookup", vs=VS.VERIFICATION_PENDING)
    assert overall([f(FindingType.SOURCE_MISMATCH, Severity.LOW)]) is flagged  # 1: type alone
    assert overall([f(FindingType.PROVENANCE_FAILURE, Severity.INFO)]) is flagged
    assert overall([unreadable, f(FindingType.EXPIRED, Severity.HIGH)]) is flagged  # 2 beats 3
    assert overall([unreadable, medium]) is manual  # 3 beats 4
    assert overall([medium], [pending]) is manual
    assert overall([medium]) is flagged  # 4
    assert overall([f(FindingType.UNDETERMINED, Severity.INFO)]) is clean  # 5
    assert overall([], [check("appx_noc", "issuer_lookup", vs=VS.VERIFIED)]) is clean


def test_cli_prints_table_and_writes_json(tmp_path, capsys):
    out = tmp_path / "out"
    assert main([str(FIXTURES / "app_conflict"), "--out", str(out)]) == 0
    printed = capsys.readouterr().out
    for rule_id in (
        "NOC_VALID_FOR_YEAR",
        "LAND_AREA_AGREE",
        "OWNER_IS_TRUST",
        "TL_NOC_AFTER_TRUST",
    ):
        assert rule_id in printed
    result = json.loads((out / "appx.json").read_text(encoding="utf-8"))
    assert result["priority"] == 401 and len(result["findings"]) == 5
    assert {Finding.model_validate(f).app_id for f in result["findings"]} == {"appx"}
    assert len(result["documents"]) == 4


def test_cli_reads_checks_file(tmp_path, capsys):
    checks = [check("appx_land_deed", "hash_duplicate", CheckStatus.MISMATCH, Severity.HIGH)]
    checks_file = tmp_path / "checks.json"
    checks_file.write_text(
        json.dumps([c.model_dump(mode="json") for c in checks]), encoding="utf-8"
    )
    assert (
        main([str(FIXTURES / "app_clean"), "--checks", str(checks_file), "--out", str(tmp_path)])
        == 0
    )
    result = json.loads((tmp_path / "appx.json").read_text(encoding="utf-8"))
    assert [f["type"] for f in result["findings"]] == ["duplicate"]
    assert "duplicate" in capsys.readouterr().out


def test_cli_empty_folder_is_an_error(tmp_path):
    with pytest.raises(SystemExit) as exc:
        main([str(tmp_path)])
    assert exc.value.code == 2


def test_cli_runs_as_module(tmp_path):
    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "docverf.reasoning",
            str(FIXTURES / "app_clean"),
            "--out",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stderr
    assert "0 finding(s), priority 0" in run.stdout


# ---- area units that cannot be converted must never crash the pipeline ----


def set_deed_unit(docs, unit):
    next(d for d in docs if d.doc_type.value == "land_deed").fields["area"].unit = unit


@pytest.mark.parametrize("unit", ["bigha", "", None])
def test_unknown_area_unit_gives_one_undetermined_finding_not_an_error(unit):
    docs = load_app("app_clean")
    set_deed_unit(docs, unit)
    findings = run_reasoning("appx", docs, [])  # must not raise
    (f,) = findings  # form and affidavit still agree at 2.5 acres, so no conflict
    assert (f.type, f.severity, f.doc_ids, f.attribute) == (
        FindingType.UNDETERMINED,
        Severity.INFO,
        ["appx_land_deed"],
        "area",
    )
    assert f.layer is Layer.B and f.evidence["unit"] == unit and f.evidence["value"] == 2.5
    assert (f"'{unit}'" in f.message) if unit else ("no unit" in f.message)
    assert "area" not in {c.attribute for c in build_claims(docs, []) if c.doc_id.endswith("deed")}


def test_unknown_unit_does_not_hide_or_invent_a_conflict():
    docs = load_app("app_clean")
    set_deed_unit(docs, "bigha")
    next(d for d in docs if d.doc_type.value == "application_form").fields["land_area"].value = 4.0
    kinds = sorted(f.type.value for f in run_reasoning("appx", docs, []))
    # form 4.0 vs affidavit 2.5 still conflict (self vs self); the deed is simply left out
    assert kinds == ["attribute_conflict", "undetermined"]


def test_other_unit_spellings_are_accepted_by_the_pipeline():
    docs = load_app("app_clean")
    set_deed_unit(docs, "ACRES")
    assert run_reasoning("appx", docs, []) == []
    next(d for d in docs if d.doc_type.value == "land_deed").fields["area"].unit = "हेक्टर"
    kinds = [f.type.value for f in run_reasoning("appx", docs, [])]
    assert kinds == ["attribute_conflict"]  # 2.5 hectare is 6.18 acres: a real conflict


def test_unknown_unit_finding_reaches_the_document_status():
    docs = load_app("app_clean")
    set_deed_unit(docs, "bigha")
    findings = run_reasoning("appx", docs, [])
    statuses, priority = aggregate("appx", findings, [], [d.doc_id for d in docs])
    deed = next(s for s in statuses if s.doc_id == "appx_land_deed")
    assert deed.overall is DocOverallStatus.NO_ISSUES and priority == 0  # info only
    assert "unknown area unit 'bigha'" in deed.note

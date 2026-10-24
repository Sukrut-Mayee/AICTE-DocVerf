"""Checkpoint 1: YAML rule engine on the Appendix A fixtures (TRD §8.4, §17)."""

import json
from pathlib import Path

import pytest
from docverf.reasoning.rule_engine import _evaluate, load_checklist, load_rules, run_rules
from docverf.schemas import ExtractionResult, FindingType, RuleOutcome, Severity

FIXTURES = Path(__file__).parent / "fixtures" / "apps"


def load_app(name: str) -> list[ExtractionResult]:
    return [
        ExtractionResult.model_validate(json.loads(p.read_text(encoding="utf-8")))
        for p in sorted((FIXTURES / name).glob("*.json"))
    ]


def outcomes(extractions):
    rules, checklist = load_rules("rules"), load_checklist("eoa")
    return {r["id"]: [o for o, _ in _evaluate("appx", r, extractions, checklist)] for r in rules}


def test_conflict_app_only_noc_expiry_fails():
    findings = run_rules("appx", load_app("app_conflict"), load_checklist("eoa"), {})
    assert [f.rule_id for f in findings] == ["NOC_VALID_FOR_YEAR"]
    f = findings[0]
    assert (f.type, f.severity, f.doc_ids) == (
        FindingType.EXPIRED,
        Severity.HIGH,
        ["appx_noc"],
    )
    assert f.message == ("NOC expires on 2027-12-31 before the academic year ends (2028-06-30)")


def test_conflict_app_other_rules_pass():
    got = outcomes(load_app("app_conflict"))
    assert got["NOC_VALID_FOR_YEAR"] == [RuleOutcome.FAIL]
    for rule_id in ("NOC_REF_FORMAT", "LAND_NOT_MORTGAGED"):
        assert got[rule_id] == [RuleOutcome.PASS]
    assert got["REQUIRED_DOCS"] == [RuleOutcome.PASS] * 4


def test_clean_app_has_no_findings():
    assert run_rules("appx", load_app("app_clean"), load_checklist("eoa"), {}) == []


def test_missing_doc_is_reported():
    docs = [d for d in load_app("app_clean") if d.doc_type.value != "land_deed"]
    findings = run_rules("appx", docs, load_checklist("eoa"), {})
    assert [(f.type, f.message) for f in findings] == [
        (FindingType.MISSING_DOC, "Required document 'land_deed' is missing")
    ]


def test_low_confidence_or_missing_field_is_undetermined_not_fail():
    docs = load_app("app_conflict")
    noc = next(d for d in docs if d.doc_type.value == "noc")
    noc.fields["valid_until"].confidence = 0.5  # below CONFIDENCE_THRESHOLD
    del noc.fields["ref_no"]
    got = outcomes(docs)
    assert got["NOC_VALID_FOR_YEAR"] == [RuleOutcome.UNDETERMINED]
    assert got["NOC_REF_FORMAT"] == [RuleOutcome.UNDETERMINED]
    assert run_rules("appx", docs, load_checklist("eoa"), {}) == []


def test_regex_and_equals_failures():
    docs = load_app("app_clean")
    for d in docs:
        if d.doc_type.value == "noc":
            d.fields["ref_no"].value = "FIRE/MH/26/1"
        if d.doc_type.value == "land_deed":
            d.fields["mortgage_status"].value = "mortgaged"
    findings = {f.rule_id: f for f in run_rules("appx", docs, load_checklist("eoa"), {})}
    assert set(findings) == {"NOC_REF_FORMAT", "LAND_NOT_MORTGAGED"}
    assert findings["NOC_REF_FORMAT"].layer.value == "C"
    assert findings["LAND_NOT_MORTGAGED"].message == "Land deed shows mortgage status 'mortgaged'"


def test_unknown_rule_type_is_loud():
    with pytest.raises(ValueError, match="unsupported rule type"):
        _evaluate(
            "appx",
            {"id": "X", "type": "nope", "field": {"doc_type": "noc", "field": "ref_no"}},
            load_app("app_clean"),
            {},
        )

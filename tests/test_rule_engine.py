"""Checkpoint 1: YAML rule engine on the Appendix A fixtures (TRD §8.4, §17)."""

import pytest
from docverf.reasoning.rule_engine import (
    _evaluate,
    load_checklist,
    load_rules,
    rule_title,
    run_rules,
)
from docverf.schemas import FindingType, RuleOutcome, Severity

from tests.apps import load_app


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


def test_missing_doc_does_not_trigger_its_field_rules():
    """LAND_NOT_MORTGAGED does not apply when the deed is absent: only REQUIRED_DOCS speaks."""
    docs = [d for d in load_app("app_clean") if d.doc_type.value != "land_deed"]
    assert outcomes(docs)["LAND_NOT_MORTGAGED"] == []


def test_low_confidence_or_missing_field_is_undetermined_not_fail():
    docs = load_app("app_conflict")
    noc = next(d for d in docs if d.doc_type.value == "noc")
    noc.fields["valid_until"].confidence = 0.5  # below CONFIDENCE_THRESHOLD
    del noc.fields["ref_no"]
    got = outcomes(docs)
    assert got["NOC_VALID_FOR_YEAR"] == [RuleOutcome.UNDETERMINED]
    assert got["NOC_REF_FORMAT"] == [RuleOutcome.UNDETERMINED]
    findings = {f.rule_id: f for f in run_rules("appx", docs, load_checklist("eoa"), {})}
    assert set(findings) == {"NOC_VALID_FOR_YEAR", "NOC_REF_FORMAT"}
    for f in findings.values():
        assert (f.type, f.severity, f.doc_ids) == (
            FindingType.UNDETERMINED,
            Severity.INFO,
            ["appx_noc"],
        )
    low, missing = findings["NOC_VALID_FOR_YEAR"], findings["NOC_REF_FORMAT"]
    assert low.attribute == "valid_until" and "confidence 0.50 is below" in low.message
    assert missing.attribute == "ref_no" and "field is missing" in missing.message
    assert missing.evidence["value"] is None


def test_failure_evidence_lets_ui_highlight_the_box():
    docs = load_app("app_conflict")
    noc = next(d for d in docs if d.doc_type.value == "noc")
    noc.fields["valid_until"].page, noc.fields["valid_until"].bbox = 1, [0.1, 0.2, 0.3, 0.4]
    (f,) = run_rules("appx", docs, load_checklist("eoa"), {})
    assert f.attribute == "valid_until" and f.claims == []
    assert f.evidence == {
        "rule_description": "NOC must be valid until the end of the academic year",
        "field": "valid_until",
        "value": "2027-12-31",
        "confidence": 0.9,
        "page": 1,
        "bbox": [0.1, 0.2, 0.3, 0.4],
        "compared_to": "2028-06-30",
    }


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


# ---- plain-English rule descriptions ----


@pytest.mark.parametrize("subdir", ["rules", "graph", "timeline"])
def test_every_rule_has_a_plain_english_description(subdir):
    for rule in load_rules(subdir):
        assert rule.get("description", "").strip(), rule["id"]
        assert rule_title(rule) == rule["description"]


def test_rule_title_falls_back_to_the_id():
    assert rule_title({"id": "X_RULE"}) == "X_RULE"


def test_undetermined_message_uses_the_description():
    docs = load_app("app_conflict")
    next(d for d in docs if d.doc_type.value == "noc").fields["valid_until"].confidence = 0.5
    (f,) = run_rules("appx", docs, load_checklist("eoa"))
    assert f.message == (
        'Cannot evaluate "NOC must be valid until the end of the academic year" on appx_noc: '
        "valid_until - confidence 0.50 is below the threshold 0.75"
    )


# ---- TER_PAID: field_present + payment records (TRD §8.4) ----

TXN = "TER2027000123"  # the reference on both fixture application forms
PAID = {"payments": {TXN: {"paid": True, "amount": 25000, "date": "2027-01-19"}}}


def ter_findings(docs, records=None):
    return [
        f
        for f in run_rules("appx", docs, load_checklist("eoa"), records)
        if f.rule_id == "TER_PAID"
    ]


def clean_with(**field_changes):
    docs = load_app("app_clean")
    form = next(d for d in docs if d.doc_type.value == "application_form")
    for attr, value in field_changes.items():
        setattr(form.fields["ter_txn_id"], attr, value)
    return docs, form


def test_ter_paid_passes_when_the_reference_is_present_and_paid():
    docs = load_app("app_clean")
    assert run_rules("appx", docs, load_checklist("eoa"), PAID) == []  # whole app: zero findings
    assert outcomes(docs)["TER_PAID"] == [RuleOutcome.PASS]  # no records: presence is enough


def test_ter_reference_missing_fails_with_or_without_records():
    docs, form = clean_with()
    del form.fields["ter_txn_id"]
    for records in (None, PAID):
        (f,) = ter_findings(docs, records)
        assert (f.type, f.severity, f.doc_ids, f.attribute) == (
            FindingType.RULE_FAILED,
            Severity.HIGH,
            ["appx_application_form"],
            "ter_txn_id",
        )
        assert f.message == "The application gives no TER payment reference"
        assert f.evidence["value"] is None


@pytest.mark.parametrize("blank", ["", "   ", None])
def test_ter_blank_reference_counts_as_missing(blank):
    docs, _ = clean_with(value=blank)
    (f,) = ter_findings(docs)
    assert f.message == "The application gives no TER payment reference"


@pytest.mark.parametrize(
    "records, compared_to",
    [
        (
            {"payments": {TXN: {"paid": False, "amount": 25000}}},
            {"found": True, "paid": False, "amount": 25000},
        ),
        ({"payments": {TXN: {"paid": "yes"}}}, {"found": True, "paid": "yes"}),  # only True counts
        ({"payments": {TXN: {}}}, {"found": True}),
        ({"payments": {"OTHER": {"paid": True}}}, {"found": False}),  # transaction not found
        ({"payments": {}}, {"found": False}),  # records fetched, but empty
    ],
)
def test_ter_unpaid_or_unknown_transaction_fails(records, compared_to):
    (f,) = ter_findings(load_app("app_clean"), records)
    assert (f.type, f.severity) == (FindingType.RULE_FAILED, Severity.HIGH)
    assert f.message == f"TER payment reference '{TXN}' is not recorded as paid"
    assert f.evidence["compared_to"] == compared_to
    assert f.attribute == "ter_txn_id" and f.claims == []


@pytest.mark.parametrize("records", [None, {}, {"approved_intake": {}}])
def test_ter_without_payment_records_is_skipped_silently(records):
    """Records that were not fetched are not evidence of non-payment."""
    assert ter_findings(load_app("app_clean"), records) == []
    assert run_rules("appx", load_app("app_clean"), load_checklist("eoa"), records) == []


def test_ter_unreadable_reference_is_undetermined_not_unpaid():
    docs, _ = clean_with(confidence=0.5)
    unpaid = {"payments": {TXN: {"paid": False}}}
    (f,) = ter_findings(docs, unpaid)
    assert (f.type, f.severity) == (FindingType.UNDETERMINED, Severity.INFO)
    assert "confidence 0.50" in f.message and "The technical evaluation fee" in f.message


def test_ter_does_not_apply_when_the_form_is_absent():
    docs = [d for d in load_app("app_clean") if d.doc_type.value != "application_form"]
    assert ter_findings(docs, PAID) == []

"""Checkpoint 5: evidence-removal impact simulator (TRD §8.6)."""

import json
from datetime import datetime

import pytest
from docverf.reasoning.__main__ import main
from docverf.reasoning.impact_sim import _status, simulate_exclusion
from docverf.schemas import (
    CheckResult,
    CheckStatus,
    Layer,
    RuleOutcome,
    Severity,
    VerificationStatus,
)

from tests.apps import FIXTURES, load_app

FORM, DEED, NOC, AFFIDAVIT = (
    f"appx_{d}" for d in ("application_form", "land_deed", "noc", "affidavit")
)
RULE_IDS = [
    "NOC_VALID_FOR_YEAR", "NOC_REF_FORMAT", "LAND_NOT_MORTGAGED", "REQUIRED_DOCS",
    "LAND_AREA_AGREE", "INSTITUTE_NAME_AGREE", "SURVEY_NO_AGREE", "OWNER_IS_TRUST",
    "TL_NOC_AFTER_TRUST", "TL_NOC_ISSUE_BEFORE_EXPIRY", "TL_DEED_BEFORE_APPLICATION",
    "TL_AFFIDAVIT_IN_WINDOW",
]  # fmt: skip


def simulate(app, exclude, checks=(), edit=None):
    docs = load_app(app)
    if edit:
        edit({d.doc_type.value: d for d in docs})
    result = simulate_exclusion("appx", docs, list(checks), exclude)
    return result, {c["rule_id"]: c for c in result["conclusions"]}


def moves(by_rule):
    return {r: (c["before"], c["after"], c["status"]) for r, c in by_rule.items()}


def test_excluding_form_and_affidavit():
    result, rules = simulate("app_conflict", [FORM, AFFIDAVIT])
    assert result["excluded"] == [FORM, AFFIDAVIT]
    assert list(rules) == RULE_IDS  # every rule, in rules -> graph -> timeline order
    assert moves(rules) == {
        "NOC_VALID_FOR_YEAR": ("fail", "fail", "still_failing"),
        "NOC_REF_FORMAT": ("pass", "pass", "still_supported"),
        "LAND_NOT_MORTGAGED": ("pass", "pass", "still_supported"),
        "REQUIRED_DOCS": ("pass", "fail", "now_failing"),  # both are required documents
        "LAND_AREA_AGREE": ("fail", "undetermined", "now_uncertain"),
        "INSTITUTE_NAME_AGREE": ("pass", "undetermined", "now_uncertain"),  # only the NOC left
        "SURVEY_NO_AGREE": ("pass", "undetermined", "now_uncertain"),
        "OWNER_IS_TRUST": ("fail", "undetermined", "now_uncertain"),  # trust name was on the form
        "TL_NOC_AFTER_TRUST": ("fail", "undetermined", "now_uncertain"),  # trust date: the form
        "TL_NOC_ISSUE_BEFORE_EXPIRY": ("pass", "pass", "still_supported"),
        "TL_DEED_BEFORE_APPLICATION": ("pass", "undetermined", "now_uncertain"),
        "TL_AFFIDAVIT_IN_WINDOW": ("pass", "undetermined", "now_uncertain"),
    }
    assert rules["LAND_AREA_AGREE"]["message"] == (
        "Land parcel area can no longer be cross-checked: only the land deed remains."
    )
    assert rules["OWNER_IS_TRUST"]["message"] == (
        "Land parcel owner vs trust name can no longer be cross-checked: "
        "only the land deed remains."
    )
    assert rules["REQUIRED_DOCS"]["message"] == (
        "Now fails: Required document 'application_form' is missing; "
        "Required document 'affidavit' is missing."
    )
    assert rules["TL_NOC_AFTER_TRUST"]["message"] == (
        "Rule TL_NOC_AFTER_TRUST can no longer be checked: the application form was removed."
    )


def test_excluding_noc():
    _, rules = simulate("app_conflict", [NOC])
    got = moves(rules)
    assert got["REQUIRED_DOCS"] == ("pass", "fail", "now_failing")  # the NOC is required
    assert rules["REQUIRED_DOCS"]["message"] == "Now fails: Required document 'noc' is missing."
    # Rules about the NOC cannot run any more: undetermined, never "pass".
    for rule_id in ("NOC_VALID_FOR_YEAR", "NOC_REF_FORMAT", "TL_NOC_AFTER_TRUST",
                    "TL_NOC_ISSUE_BEFORE_EXPIRY"):  # fmt: skip
        assert got[rule_id][1:] == ("undetermined", "now_uncertain"), rule_id
    assert rules["NOC_VALID_FOR_YEAR"]["message"] == (
        'Rule "NOC must be valid until the end of the academic year" '
        "can no longer be checked: the noc was removed."
    )
    # Everything that never depended on the NOC is unchanged.
    assert got["LAND_AREA_AGREE"] == ("fail", "fail", "still_failing")
    assert got["OWNER_IS_TRUST"] == ("fail", "fail", "still_failing")
    assert got["INSTITUTE_NAME_AGREE"] == ("pass", "pass", "still_supported")  # form + affidavit


def test_no_exclusion_changes_nothing():
    result, rules = simulate("app_conflict", [])
    assert result["excluded"] == []
    assert {c["status"] for c in rules.values()} == {"still_supported", "still_failing"}
    assert {r for r, c in rules.items() if c["status"] == "still_failing"} == {
        "NOC_VALID_FOR_YEAR", "LAND_AREA_AGREE", "OWNER_IS_TRUST", "TL_NOC_AFTER_TRUST",
    }  # fmt: skip


def test_clean_app_stays_supported_when_two_agreeing_documents_remain():
    _, rules = simulate("app_clean", [AFFIDAVIT])
    assert moves(rules)["LAND_AREA_AGREE"] == ("pass", "pass", "still_supported")  # form + deed
    assert moves(rules)["INSTITUTE_NAME_AGREE"] == ("pass", "pass", "still_supported")
    assert moves(rules)["TL_AFFIDAVIT_IN_WINDOW"][1:] == ("undetermined", "now_uncertain")
    assert moves(rules)["REQUIRED_DOCS"][1:] == ("fail", "now_failing")


def test_removing_the_odd_one_out_resolves_a_conflict():
    def affidavit_disagrees(docs):
        docs["affidavit"].fields["land_area_declared"].value = 3.0  # confidence stays 0.92

    _, rules = simulate("app_clean", [AFFIDAVIT], edit=affidavit_disagrees)
    assert moves(rules)["LAND_AREA_AGREE"] == ("fail", "pass", "changed")
    assert rules["LAND_AREA_AGREE"]["message"] == (
        "Land parcel area changed from fail to pass without the affidavit."
    )


def test_excluded_documents_checks_are_dropped_too():
    """A verified signature on the deed makes it issuer_verified; without the deed it is gone."""
    signature = CheckResult(
        doc_id=DEED, layer=Layer.A, check="pdf_signature", status=CheckStatus.VERIFIED,
        severity=Severity.INFO, reason="ok", verification_status=VerificationStatus.VERIFIED,
        checked_at=datetime(2027, 1, 1),
    )  # fmt: skip
    result, _ = simulate("app_conflict", [DEED], checks=[signature])  # must not raise
    assert result["excluded"] == [DEED]


def test_document_missing_from_the_start_is_undetermined_before_and_after():
    docs = [d for d in load_app("app_conflict") if d.doc_type.value != "land_deed"]
    result = simulate_exclusion("appx", docs, [], [AFFIDAVIT])
    rules = {c["rule_id"]: c for c in result["conclusions"]}
    assert moves(rules)["LAND_NOT_MORTGAGED"] == ("undetermined", "undetermined", "still_uncertain")
    assert rules["LAND_NOT_MORTGAGED"]["message"] == (
        "Rule LAND_NOT_MORTGAGED still cannot be checked: no source document is available."
    )


def test_unknown_document_id_is_rejected():
    with pytest.raises(ValueError, match="unknown document id"):
        simulate("app_conflict", ["appx_lab_photo"])


def test_inputs_are_not_modified_and_result_is_json():
    docs = load_app("app_conflict")
    before = [d.model_dump() for d in docs]
    result = simulate_exclusion("appx", docs, [], [NOC, NOC])  # duplicates collapse
    assert [d.model_dump() for d in docs] == before
    assert result["excluded"] == [NOC]
    assert json.loads(json.dumps(result)) == result


R = RuleOutcome


@pytest.mark.parametrize(
    "before, after, status",
    [
        (R.PASS, R.PASS, "still_supported"),
        (R.FAIL, R.FAIL, "still_failing"),
        (R.UNDETERMINED, R.UNDETERMINED, "still_uncertain"),
        (R.PASS, R.UNDETERMINED, "now_uncertain"),
        (R.FAIL, R.UNDETERMINED, "now_uncertain"),
        (R.PASS, R.FAIL, "now_failing"),
        (R.FAIL, R.PASS, "changed"),
        (R.UNDETERMINED, R.PASS, "changed"),
        (R.UNDETERMINED, R.FAIL, "changed"),
    ],
)
def test_status_table(before, after, status):
    assert _status(before, after) == status


def test_cli_exclude_prints_table_and_writes_json(tmp_path, capsys):
    argv = [str(FIXTURES / "app_conflict"), "--exclude", FORM, AFFIDAVIT, "--out", str(tmp_path)]
    assert main(argv) == 0
    printed = capsys.readouterr().out
    assert "now_uncertain" in printed and "LAND_AREA_AGREE" in printed
    result = json.loads((tmp_path / "appx_impact.json").read_text(encoding="utf-8"))
    assert set(result) == {"excluded", "conclusions"} and result["excluded"] == [FORM, AFFIDAVIT]
    assert {c["rule_id"] for c in result["conclusions"]} == set(RULE_IDS)


def test_cli_exclude_unknown_id_is_a_usage_error(tmp_path):
    with pytest.raises(SystemExit) as exc:
        main([str(FIXTURES / "app_conflict"), "--exclude", "appx_nope", "--out", str(tmp_path)])
    assert exc.value.code == 2

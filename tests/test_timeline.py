"""Checkpoint 3: timeline engine on the Appendix A fixtures (TRD §8.5)."""

from datetime import date

import pytest
from docverf.reasoning.entity_graph import build_claims
from docverf.reasoning.timeline import timeline_checks

from tests.apps import load_app


def timeline(app="app_clean", edit=None, drop=()):
    docs = [d for d in load_app(app) if d.doc_type.value not in drop]
    if edit:
        edit({d.doc_type.value: d for d in docs})
    return timeline_checks("appx", build_claims(docs, []))


def summary(findings):
    return [(f.type.value, f.severity.value, f.rule_id) for f in findings]


def test_conflict_app_noc_predates_trust():
    (f,) = timeline("app_conflict")
    assert summary([f]) == [("timeline_violation", "high", "TL_NOC_AFTER_TRUST")]
    assert f.message == "NOC dated 2008-06-10 is earlier than trust registration 2009-04-15"
    assert f.doc_ids == ["appx_application_form", "appx_noc"]
    assert f.evidence == {"before": "2009-04-15", "after": "2008-06-10"}


def test_clean_app_has_no_timeline_findings():
    assert timeline("app_clean") == []


def test_low_confidence_date_is_undetermined_never_a_violation():
    def edit(d):
        d["noc"].fields["issue_date"].confidence = 0.5

    findings = timeline("app_conflict", edit)  # would be a violation if it were trusted
    assert summary(findings) == [
        ("undetermined", "info", "TL_NOC_AFTER_TRUST"),
        ("undetermined", "info", "TL_NOC_ISSUE_BEFORE_EXPIRY"),
    ]
    assert "confidence 0.50" in findings[0].message and findings[0].doc_ids == ["appx_noc"]
    assert findings[0].attribute == "issue_date"


def test_missing_date_field_is_undetermined():
    findings = timeline("app_clean", lambda d: d["noc"].fields.pop("valid_until"))
    assert summary(findings) == [("undetermined", "info", "TL_NOC_ISSUE_BEFORE_EXPIRY")]
    assert "noc.valid_until is missing" in findings[0].message


def test_unparseable_date_is_undetermined():
    findings = timeline(
        "app_clean", lambda d: d["noc"].fields["issue_date"].__setattr__("value", "10/11/25")
    )
    assert {f.type.value for f in findings} == {"undetermined"}


def test_absent_document_means_rule_does_not_apply():
    assert timeline("app_clean", drop=("noc",)) == []
    assert timeline("app_clean", drop=("application_form",)) == []


def test_issue_after_expiry_is_a_violation():
    def edit(d):
        d["noc"].fields["valid_until"].value = "2025-01-01"

    findings = timeline("app_clean", edit)
    assert summary(findings) == [("timeline_violation", "high", "TL_NOC_ISSUE_BEFORE_EXPIRY")]
    assert findings[0].message == "NOC expires on 2025-01-01, before its issue date 2025-11-10"


@pytest.mark.parametrize(
    "day, bad", [("2027-02-01", False), ("2026-12-01", False), ("2027-04-01", True)]
)
def test_affidavit_must_fall_in_application_window(day, bad):
    findings = timeline(
        "app_clean", lambda d: d["affidavit"].fields["date"].__setattr__("value", day)
    )
    assert summary(findings) == (
        [("timeline_violation", "medium", "TL_AFFIDAVIT_IN_WINDOW")] if bad else []
    )
    if bad:
        assert (
            findings[0].message == "Affidavit is dated 2027-04-01, "
            "outside the application window 2026-12-01 to 2027-03-31"
        )


def test_window_comes_from_config(monkeypatch):
    from docverf.config import get_settings

    monkeypatch.setenv("APPLICATION_WINDOW_END", "2027-01-10")
    get_settings.cache_clear()
    try:
        findings = timeline("app_clean")  # affidavit is dated 2027-01-18
        assert summary(findings) == [("timeline_violation", "medium", "TL_AFFIDAVIT_IN_WINDOW")]
        assert date(2027, 1, 10).isoformat() in findings[0].message
    finally:
        monkeypatch.delenv("APPLICATION_WINDOW_END")
        get_settings.cache_clear()


def test_deed_registered_after_the_application_is_a_violation():
    def edit(d):
        d["land_deed"].fields["registration_date"].value = "2027-02-01"  # application: 2027-01-20

    findings = timeline("app_clean", edit)
    assert summary(findings) == [("timeline_violation", "medium", "TL_DEED_BEFORE_APPLICATION")]
    assert findings[0].message == (
        "Application is dated 2027-01-20, before the land deed was registered on 2027-02-01"
    )


def test_undetermined_message_names_the_rule_in_plain_english():
    findings = timeline("app_conflict", lambda d: d["noc"].fields.pop("issue_date"))
    assert findings[0].message == (
        'Cannot check "NOC must be issued after the trust was registered": '
        "noc.issue_date is missing"
    )

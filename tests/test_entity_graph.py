"""Checkpoints 2-3: build_claims and graph_checks on the Appendix A fixtures (TRD §6, §8)."""

from datetime import datetime

import pytest
from docverf.reasoning import entity_graph
from docverf.reasoning.entity_graph import _pair_severity, build_claims, graph_checks
from docverf.schemas import (
    AuthorityTier,
    CheckResult,
    CheckStatus,
    Layer,
    Severity,
    VerificationStatus,
)

from tests.apps import load_app


def pick(claims, doc_suffix, attribute):
    (c,) = [c for c in claims if c.doc_id.endswith(doc_suffix) and c.attribute == attribute]
    return c


def make_check(doc_id, check, verification_status, status=CheckStatus.CLEAN):
    return CheckResult(
        doc_id=doc_id,
        layer=Layer.A,
        check=check,
        status=status,
        severity=Severity.INFO,
        reason="test",
        verification_status=verification_status,
        checked_at=datetime(2027, 1, 1),
    )


def test_conflict_app_claim_mapping():
    claims = build_claims(load_app("app_conflict"), [])
    assert {c.entity for c in claims if not c.entity.startswith("doc:")} == {
        "institute:1-9876543",
        "trust:E-12345/PUNE",
        "land_parcel:45/2",
    }
    area = [c for c in claims if c.attribute == "area"]
    assert {(c.doc_id[5:], c.value) for c in area} == {
        ("application_form", 2.5),
        ("land_deed", 2.1),
        ("affidavit", 2.5),
    }
    names = sorted(c.entity.split(":")[0] for c in claims if c.attribute == "name")
    assert names == ["institute"] * 3 + ["trust"]  # form, noc, affidavit + trust name
    deed_area = pick(claims, "land_deed", "area")
    assert deed_area.authority is AuthorityTier.THIRD_PARTY
    assert (deed_area.page, deed_area.bbox, deed_area.confidence) == (
        1,
        [0.12, 0.41, 0.35, 0.44],
        0.93,
    )
    assert pick(claims, "application_form", "area").authority is AuthorityTier.SELF_DECLARED
    assert pick(claims, "affidavit", "area").confidence == 0.62  # kept; graph_checks drops it


def test_default_tiers_by_doc_type():
    claims = build_claims(load_app("app_clean"), [])
    tiers = {c.doc_id[5:]: c.authority for c in claims}
    assert tiers == {
        "application_form": AuthorityTier.SELF_DECLARED,
        "affidavit": AuthorityTier.SELF_DECLARED,
        "land_deed": AuthorityTier.THIRD_PARTY,
        "noc": AuthorityTier.THIRD_PARTY,
    }


def test_timeline_dates_become_claims():
    claims = build_claims(load_app("app_conflict"), [])
    assert pick(claims, "noc", "issue_date").value == "2008-06-10"
    assert pick(claims, "noc", "issue_date").entity == "doc:appx_noc"
    assert pick(claims, "application_form", "reg_date").entity == "trust:E-12345/PUNE"
    assert pick(claims, "application_form", "application_date").value == "2027-01-20"


def test_verified_check_upgrades_only_that_doc():
    checks = [make_check("appx_noc", "qr", VerificationStatus.VERIFIED)]
    tiers = {c.doc_id[5:]: c.authority for c in build_claims(load_app("app_conflict"), checks)}
    assert tiers["noc"] is AuthorityTier.ISSUER_VERIFIED
    assert tiers["land_deed"] is AuthorityTier.THIRD_PARTY


def test_unverified_or_unrelated_checks_do_not_upgrade():
    checks = [
        make_check("appx_noc", "qr", VerificationStatus.SOURCE_UNAVAILABLE),
        make_check("appx_land_deed", "ela", None),
        make_check("appx_affidavit", "metadata", VerificationStatus.VERIFIED),
    ]
    claims = build_claims(load_app("app_conflict"), checks)
    assert AuthorityTier.ISSUER_VERIFIED not in {c.authority for c in claims}


def test_missing_application_form_falls_back_to_app_id():
    docs = [d for d in load_app("app_conflict") if d.doc_type.value != "application_form"]
    entities = {c.entity for c in build_claims(docs, []) if not c.entity.startswith("doc:")}
    assert entities == {"institute:appx", "land_parcel:appx"}


# ---- Checkpoint 3: graph_checks (TRD §8.2, §8.3) ----

THIRD, SELF, VERIFIED = (
    AuthorityTier.THIRD_PARTY,
    AuthorityTier.SELF_DECLARED,
    AuthorityTier.ISSUER_VERIFIED,
)


def graph(app="app_clean", checks=(), edit=None):
    """Run graph_checks on a fixture app; `edit` mutates {doc_type: ExtractionResult} first."""
    docs = load_app(app)
    if edit:
        edit({d.doc_type.value: d for d in docs})
    return graph_checks("appx", build_claims(docs, list(checks)))


def summary(findings):
    return [(f.type.value, f.severity.value, f.rule_id) for f in findings]


def set_field(doc_type, field, **attrs):
    def edit(docs):
        for name, value in attrs.items():
            setattr(docs[doc_type].fields[field], name, value)

    return edit


def test_conflict_app_graph_findings():
    findings = graph("app_conflict")
    assert summary(findings) == [
        ("unreadable", "low", "LAND_AREA_AGREE"),
        ("attribute_conflict", "high", "LAND_AREA_AGREE"),
        ("relationship_violation", "high", "OWNER_IS_TRUST"),
    ]  # INSTITUTE_NAME_AGREE and SURVEY_NO_AGREE pass
    unreadable, conflict, owner = findings
    assert unreadable.doc_ids == ["appx_affidavit"] and unreadable.attribute == "area"
    assert unreadable.evidence["confidence"] == 0.62
    assert conflict.doc_ids == ["appx_application_form", "appx_land_deed"]
    assert [c.value for c in conflict.claims] == [2.5, 2.1]  # the 0.62 claim is excluded
    assert conflict.message == (
        "Land parcel area conflicts: 2.5 in application_form vs 2.1 in land_deed"
    )
    assert owner.message == (
        "Land owner 'Shree Vidya Charitable Society' does not match "
        "the trust 'Shree Vidya Education Trust'"
    )
    assert {c.attribute for c in owner.claims} == {"owner", "name"}


def test_clean_app_graph_has_no_findings():
    assert graph("app_clean") == []


@pytest.mark.parametrize(
    "a, b, expected",
    [
        (VERIFIED, SELF, Severity.HIGH),
        (VERIFIED, THIRD, Severity.HIGH),
        (VERIFIED, VERIFIED, Severity.HIGH),
        (THIRD, SELF, Severity.HIGH),
        (THIRD, THIRD, Severity.MEDIUM),
        (SELF, SELF, Severity.MEDIUM),
    ],
)
def test_pair_severity_table(a, b, expected):
    assert _pair_severity(a, b) == expected
    assert _pair_severity(b, a) == expected


def form_vs_affidavit_only(docs):
    """Leave two self-declared area claims (form 2.5, affidavit 3.0) by dropping the deed's."""
    set_field("land_deed", "area", confidence=0.5)(docs)
    set_field("affidavit", "land_area_declared", value=3.0)(docs)


def test_self_vs_self_conflict_is_medium():
    findings = graph(edit=form_vs_affidavit_only)
    assert summary(findings) == [
        ("unreadable", "low", "LAND_AREA_AGREE"),  # the deed's low-confidence area
        ("attribute_conflict", "medium", "LAND_AREA_AGREE"),
    ]


def test_issuer_verified_document_raises_conflict_to_high():
    verified = make_check("appx_affidavit", "qr", VerificationStatus.VERIFIED)
    findings = graph(checks=[verified], edit=form_vs_affidavit_only)
    assert summary(findings)[1] == ("attribute_conflict", "high", "LAND_AREA_AGREE")


def test_relative_tolerance_on_area_after_unit_conversion():
    def deed_area(value, unit="acre"):
        return set_field("land_deed", "area", value=value, unit=unit)

    assert graph(edit=deed_area(2.52)) == []  # 0.8% apart: inside the 1% tolerance
    assert summary(graph(edit=deed_area(2.6))) == [
        ("attribute_conflict", "high", "LAND_AREA_AGREE")
    ]
    assert graph(edit=deed_area(1.01175, "hectare")) == []  # 1.01175 ha is about 2.5 acres


def test_exact_tolerance_on_survey_number():
    assert graph(edit=set_field("land_deed", "survey_no", value=" 45 / 2")) == []
    conflict = graph(edit=set_field("land_deed", "survey_no", value="45/3"))
    assert summary(conflict) == [("attribute_conflict", "high", "SURVEY_NO_AGREE")]


def test_fuzzy_tolerance_on_institute_name():
    findings = graph(edit=set_field("affidavit", "institute_name", value="Some Other College"))
    assert summary(findings) == [("attribute_conflict", "high", "INSTITUTE_NAME_AGREE")]
    assert sorted(findings[0].doc_ids) == ["appx_affidavit", "appx_application_form", "appx_noc"]


def test_too_few_usable_claims_is_undetermined_not_conflict():
    def only_form(docs):
        set_field("affidavit", "land_area_declared", confidence=0.5)(docs)
        set_field("land_deed", "area", confidence=0.5)(docs)

    assert summary(graph(edit=only_form)) == [
        ("unreadable", "low", "LAND_AREA_AGREE"),
        ("unreadable", "low", "LAND_AREA_AGREE"),
        ("undetermined", "info", "LAND_AREA_AGREE"),
    ]


def test_no_claims_at_all_is_silent():
    assert graph_checks("appx", []) == []


def test_unreadable_is_reported_once_across_rules(monkeypatch):
    area = next(r for r in entity_graph.load_rules("graph") if r["id"] == "LAND_AREA_AGREE")
    monkeypatch.setattr(entity_graph, "load_rules", lambda _: [area, {**area, "id": "AREA_AGAIN"}])
    kinds = [f.type.value for f in graph_checks("appx", build_claims(load_app("app_conflict"), []))]
    assert kinds.count("unreadable") == 1  # one dropped claim, two rules
    assert kinds.count("attribute_conflict") == 2  # but each rule still reports its conflict


def test_unreadable_owner_makes_relationship_undetermined():
    findings = graph(edit=set_field("land_deed", "owner_name", confidence=0.4))
    assert summary(findings) == [
        ("unreadable", "low", "OWNER_IS_TRUST"),
        ("undetermined", "info", "OWNER_IS_TRUST"),
    ]

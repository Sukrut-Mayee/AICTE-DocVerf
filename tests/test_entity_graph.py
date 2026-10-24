"""Checkpoint 2: build_claims on the Appendix A fixtures (TRD §8.1, §6)."""

from datetime import datetime

from docverf.reasoning.entity_graph import build_claims
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

"""Cross-institution reuse: same land parcel / trust registration under a different institute."""

import json

from docverf.reasoning.cross_institution import check_cross_institution, load_prior
from docverf.schemas import DocType, ExtractionResult, FieldValue, FindingType, Severity
from fastapi.testclient import TestClient

from services.api.main import create_app
from services.api.settings import ApiSettings


def _fv(value):
    return FieldValue(value=value, confidence=1.0)


def app(app_id, institute_id, name, survey="66/8", trust="E-9128/PUNE", village="Lonavala"):
    """The extractions of one application: its form, and a land deed when `village` is given."""
    form = {
        "institute_name": _fv(name),
        "aicte_permanent_id": _fv(institute_id),
        "land_survey_no": _fv(survey),
        "trust_reg_no": _fv(trust),
    }
    out = [
        ExtractionResult(
            doc_id=f"{app_id}_application_form",
            app_id=app_id,
            doc_type=DocType.APPLICATION_FORM,
            fields=form,
        )
    ]
    if village:
        deed = {"survey_no": _fv(survey), "village": _fv(village), "district": _fv("Sangli")}
        out.append(
            ExtractionResult(
                doc_id=f"{app_id}_land_deed",
                app_id=app_id,
                doc_type=DocType.LAND_DEED,
                fields=deed,
            )
        )
    return out


FIRST = app("app009", "1-1001329", "Sant Dnyaneshwar Institute", trust="E-9128/PUNE")


def test_shared_survey_number_under_another_institute_is_flagged_once():
    later = app("app021", "1-2002000", "Other Institute", trust="E-1111/PUNE")
    findings = check_cross_institution("app021", later, [FIRST])
    assert len(findings) == 1
    f = findings[0]
    assert f.type is FindingType.RELATIONSHIP_VIOLATION and f.severity is Severity.HIGH
    assert f.app_id == "app021" and f.doc_ids == ["app021_land_deed"]
    assert f.evidence["entity"] == "land_parcel" and f.evidence["value"] == "66/8"
    assert f.evidence["also_claimed_by"] == [
        {
            "app_id": "app009",
            "institute_name": "Sant Dnyaneshwar Institute",
            "doc_id": "app009_land_deed",
        }
    ]
    assert f.evidence["rule_description"]
    assert "reused across institutions" in f.message
    text = f.message.lower()
    assert not any(word in text for word in ("fraud", "fake", "forged"))


def test_the_earlier_application_is_not_flagged_by_the_later_one():
    assert check_cross_institution("app009", FIRST, []) == []


def test_shared_trust_registration_is_flagged():
    later = app("app021", "1-2002000", "Other Institute", survey="12/3", village="Karad")
    findings = check_cross_institution("app021", later, [FIRST])
    assert [f.evidence["entity"] for f in findings] == ["trust"]
    assert findings[0].evidence["value"] == "E-9128/PUNE"
    assert findings[0].doc_ids == ["app021_application_form"]


def test_different_institutes_with_different_parcels_are_not_flagged():
    other = app("app021", "1-2002000", "Other Institute", survey="12/3", trust="E-1111/PUNE")
    assert check_cross_institution("app021", other, [FIRST]) == []


def test_same_institute_resubmitting_is_not_flagged():
    again = app("app021", "1-1001329", "Sant Dnyaneshwar Institute")
    assert check_cross_institution("app021", again, [FIRST]) == []


def test_survey_number_matches_after_normalisation_but_not_across_villages():
    spaced = app("app021", "1-2002000", "Other", survey="66 / 8", trust="E-1/PUNE")
    assert len(check_cross_institution("app021", spaced, [FIRST])) == 1
    elsewhere = app("app022", "1-3003000", "Third", trust="E-2/PUNE", village="Karad")
    assert check_cross_institution("app022", elsewhere, [FIRST]) == []


def test_load_prior_reads_only_earlier_applications(tmp_path):
    for extractions in (FIRST, app("app021", "1-2", "Later")):
        app_id = extractions[0].app_id
        (tmp_path / f"{app_id}.json").write_text(
            json.dumps({"extractions": [e.model_dump(mode="json") for e in extractions]})
        )
    (tmp_path / "app005.json").write_text("not json")  # an unreadable output is skipped
    prior = load_prior(tmp_path, "app021")
    assert [p[0].app_id for p in prior] == ["app009"]


def test_network_lists_shared_parcels_and_duplicate_photos(tmp_path):
    pipeline = tmp_path / "pipeline"
    pipeline.mkdir()
    duplicate = {
        "finding_id": "f_1",
        "app_id": "app021",
        "type": "duplicate",
        "severity": "high",
        "doc_ids": ["app021_lab_photo"],
        "message": "Duplicate",
        "evidence": {"duplicate_of": {"app_id": "app009", "doc_id": "app009_lab_photo_1"}},
    }
    for extractions, findings in ((FIRST, []), (app("app021", "1-2", "Later"), [duplicate])):
        app_id = extractions[0].app_id
        (pipeline / f"{app_id}.json").write_text(
            json.dumps(
                {
                    "app_id": app_id,
                    "extractions": [e.model_dump(mode="json") for e in extractions],
                    "findings": findings,
                }
            )
        )
    settings = ApiSettings(
        pipeline_dir=pipeline, synthetic_dir=tmp_path, db_path=tmp_path / "officer.db"
    )
    entities = TestClient(create_app(settings)).get("/v1/network").json()["entities"]
    by_kind = {e["kind"]: e for e in entities}
    assert set(by_kind) == {"land_parcel", "trust", "photo"}
    assert {a["app_id"] for a in by_kind["land_parcel"]["applications"]} == {"app009", "app021"}
    assert {a["app_id"] for a in by_kind["photo"]["applications"]} == {"app009", "app021"}

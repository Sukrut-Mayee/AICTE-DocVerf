"""Every fixture under tests/fixtures must validate against the §5 schemas (TRD §17)."""

import json
from pathlib import Path

import pytest
from docverf.schemas import DocType, ExtractionResult

FIXTURES = Path(__file__).parent / "fixtures" / "apps"
FILES = sorted(FIXTURES.glob("*/*.json"))


def test_both_apps_have_four_documents():
    for app in ("app_conflict", "app_clean"):
        names = {p.stem for p in (FIXTURES / app).glob("*.json")}
        assert names == {"application_form", "land_deed", "noc", "affidavit"}


@pytest.mark.parametrize("path", FILES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_fixture_validates(path):
    result = ExtractionResult.model_validate(json.loads(path.read_text(encoding="utf-8")))
    assert result.doc_type == DocType(path.stem)
    assert result.doc_id == f"{result.app_id}_{result.doc_type.value}"  # TRD §5.3


def test_clean_variant_differs_only_as_specified():
    def load(app, doc):
        return json.loads((FIXTURES / app / f"{doc}.json").read_text(encoding="utf-8"))

    clean_deed, conflict_deed = load("app_clean", "land_deed"), load("app_conflict", "land_deed")
    trust = load("app_clean", "application_form")["fields"]["trust_name"]["value"]
    assert clean_deed["fields"]["area"]["value"] == 2.5
    assert clean_deed["fields"]["owner_name"]["value"] == trust
    assert conflict_deed["fields"]["area"]["value"] == 2.1
    noc = load("app_clean", "noc")["fields"]
    assert (noc["issue_date"]["value"], noc["valid_until"]["value"]) == ("2025-11-10", "2028-12-31")


def test_clean_affidavit_area_is_readable():
    """TRD v0.2 Appendix A: app_clean must yield zero findings, so no low-confidence field."""
    area = json.loads((FIXTURES / "app_clean" / "affidavit.json").read_text(encoding="utf-8"))[
        "fields"
    ]["land_area_declared"]
    assert area["confidence"] == 0.92 and area["extractor_agreement"] is True
    for path in (FIXTURES / "app_clean").glob("*.json"):
        for name, field in json.loads(path.read_text(encoding="utf-8"))["fields"].items():
            assert field["confidence"] >= 0.75, f"{path.name}:{name}"

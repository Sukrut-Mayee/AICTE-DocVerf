"""ORACLE: the synthetic data and the reasoning module agree (TRD §13.2, §8).

Each application's true fields become perfect extractions (confidence 1.0) and go through
run_reasoning. Clean applications must give no findings; defective ones exactly the findings their
defects predict (the table below is written from TRD §13.2, not from the output).
"""

from collections import Counter

import pytest
from docverf.provenance.duplicates import check_duplicates
from docverf.provenance.hashing import hash_file
from docverf.reasoning.run import run_reasoning
from docverf.synthetic.generate import build_apps, generate_dataset
from docverf.synthetic.model import extraction_results

Finding = tuple[str | None, str, str]  # (rule_id, type, severity)

# TRD §13.2: defect -> the finding reasoning must report. Defects with no entry are found by other
# modules (provenance signatures, forensics, mock issuer) and give reasoning nothing to report.
EXPECTED: dict[str, list[Finding]] = {
    "AREA_MISMATCH": [("LAND_AREA_AGREE", "attribute_conflict", "high")],
    "OWNER_MISMATCH": [("OWNER_IS_TRUST", "relationship_violation", "high")],
    "NAME_MISMATCH": [("INSTITUTE_NAME_AGREE", "attribute_conflict", "high")],
    "EXPIRED_NOC": [("NOC_VALID_FOR_YEAR", "expired", "high")],
    "TIMELINE_NOC_BEFORE_TRUST": [("TL_NOC_AFTER_TRUST", "timeline_violation", "high")],
    "BAD_REF_FORMAT": [("NOC_REF_FORMAT", "rule_failed", "medium")],
    "MORTGAGED_LAND": [("LAND_NOT_MORTGAGED", "rule_failed", "medium")],
    "MISSING_DOC": [("REQUIRED_DOCS", "missing_doc", "high")],
}
# Without a land deed the survey number and the owner can no longer be cross-checked: reasoning
# says so with two informational findings (it never calls that a conflict).
MISSING_DEED_NOTES: list[Finding] = [
    ("SURVEY_NO_AGREE", "undetermined", "info"),
    ("OWNER_IS_TRUST", "undetermined", "info"),
]
# TRD §13.2: found by the provenance duplicate check, which needs the other applications. An exact
# copy matches on both hashes (sha256 and pHash), and each match is its own `duplicate` finding.
PROVENANCE: dict[str, list[Finding]] = {"DUPLICATE_PHOTO": [(None, "duplicate", "high")] * 2}

APPS = build_apps(20, seed=42)


def predicted(app, table: dict[str, list[Finding]]) -> Counter:
    """The findings `table` predicts for the distinct defect codes of `app`."""
    out: Counter = Counter()
    for code in {d.defect for d in app.defects}:
        out.update(table.get(code, []))
    return out


def expected(app) -> Counter:
    out = predicted(app, EXPECTED)
    if "land_deed" in app.missing:
        out.update(MISSING_DEED_NOTES)
    return out


def found(app, checks=()) -> Counter:
    findings = run_reasoning(app.app_id, extraction_results(app), list(checks))
    return Counter((f.rule_id, f.type.value, f.severity.value) for f in findings)


def codes(app) -> str:
    return ", ".join(sorted({d.defect for d in app.defects})) or "(clean)"


@pytest.mark.parametrize("app", APPS, ids=lambda a: f"{a.app_id}[{codes(a)}]")
def test_reasoning_reports_exactly_what_the_defects_predict(app):
    assert found(app) == expected(app)


def test_clean_applications_give_zero_findings():
    clean = [a for a in APPS if not a.defects]
    assert len(clean) == 8
    assert all(not found(a) for a in clean)


def test_every_finding_points_at_the_document_carrying_the_defect():
    """InjectedDefect.doc_id is a document the matching finding highlights."""
    for app in APPS:
        findings = run_reasoning(app.app_id, extraction_results(app), [])
        for d in app.defects:
            if d.defect not in EXPECTED or d.defect == "MISSING_DOC":
                continue  # a missing document has no document to point at
            rule_ids = {rule for rule, _, _ in EXPECTED[d.defect]}
            highlighted = {x for f in findings if f.rule_id in rule_ids for x in f.doc_ids}
            assert d.doc_id in highlighted, (app.app_id, d.defect, d.doc_id, highlighted)


def test_duplicate_photo_is_found_by_provenance_and_reaches_the_findings(tmp_path):
    """DUPLICATE_PHOTO: hash every lab photo in application order, as the pipeline would."""
    generate_dataset(tmp_path, 20, render=False)
    index: dict[str, list[tuple[str, str]]] = {}
    seen = 0
    for app in APPS:
        checks = []
        for photo in app.photos:
            doc_id = app.photo_doc_id(photo)
            hashes = hash_file(str(tmp_path / app.app_id / f"lab_photo_{photo.n}.jpg"))
            checks += check_duplicates(app.app_id, doc_id, hashes, index)
            for value in hashes.values():
                index.setdefault(value, []).append((app.app_id, doc_id))
        want = expected(app) + predicted(app, PROVENANCE)
        assert found(app, checks) == want, app.app_id
        seen += bool(checks)
    assert seen == 1  # exactly one application carries a duplicate; its source stays clean

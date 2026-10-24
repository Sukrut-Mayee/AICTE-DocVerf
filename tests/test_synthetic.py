"""Synthetic generator (TRD §13): constraints, defects, labels, photos, CLI. No browser needed."""

import copy
import hashlib
import itertools
import json
import random
import re
from datetime import timedelta

import imagehash
import pytest
from docverf.config import get_settings
from docverf.extraction.extract import _check_quality
from docverf.extraction.rules_extractor import _LABEL_SPECS, rules_extract
from docverf.reasoning.entity_resolution import names_match, normalize_name
from docverf.reasoning.rule_engine import load_checklist
from docverf.schemas import DocType, GroundTruth
from docverf.synthetic import defects as defect_module
from docverf.synthetic.__main__ import main
from docverf.synthetic.generate import SCENARIOS, build_apps, generate_dataset
from docverf.synthetic.model import build_clean_app, ground_truth, true_fields
from docverf.synthetic.render import render_html
from PIL import Image

from tests.synth import as_truth, differences, html_lines, html_words, label_lines

ALL_CODES = set(defect_module.DEFECTS)
TRD_FIELDS = {  # TRD §6, exactly
    "application_form": {
        "institute_name", "aicte_permanent_id", "application_no", "trust_name", "trust_reg_no",
        "trust_reg_date", "address", "land_survey_no", "land_area", "built_up_area_sqm", "programs",
        "principal_name", "application_date", "ter_txn_id",
    },
    "land_deed": {
        "owner_name", "survey_no", "area", "village", "district", "registration_no",
        "registration_date", "mortgage_status",
    },
    "noc": {
        "issuer", "ref_no", "institute_name", "purpose", "issue_date", "valid_until", "signatory",
    },
    "affidavit": {
        "deponent_name", "institute_name", "application_no", "date", "land_area_declared",
        "notary_reg_no",
    },
    "accreditation_cert": {
        "body", "cert_no", "institute_name", "programs", "valid_from", "valid_to",
    },
    "lab_photo": {"room_label", "equipment_count", "capture_date"},
}  # fmt: skip
DOC_ID = re.compile(
    r"^app\d{3}_(application_form|land_deed|noc|affidavit|accreditation_cert|lab_photo(_\d)?)$"
)


@pytest.fixture(scope="module")
def apps():
    return build_apps(20, seed=42)


def doc_type_of(doc_id):
    return re.sub(r"^app\d{3}_", "", re.sub(r"_\d$", "", doc_id))


# ---- schedule ----


def test_eight_clean_and_twelve_defective_with_every_code_used(apps):
    clean = [a for a in apps if not a.defects]
    defective = [a for a in apps if a.defects]
    assert (len(clean), len(defective)) == (8, 12)
    assert [a.app_id for a in apps] == [f"app{i:03d}" for i in range(1, 21)]
    for a in defective:
        assert 1 <= len({d.defect for d in a.defects}) <= 3, a.app_id
    assert {d.defect for a in apps for d in a.defects} == ALL_CODES  # all 13 codes


def test_small_datasets_have_both_kinds():
    one_each = build_apps(2)
    assert [bool(a.defects) for a in one_each] == [False, True]
    assert {d.defect for d in one_each[1].defects} == {"AREA_MISMATCH"}
    assert [a.app_id for a in build_apps(1)] == ["app001"] and not build_apps(1)[0].defects


def test_scenarios_only_use_known_codes():
    codes = {spec.split(":")[0] for scenario in SCENARIOS for spec in scenario}
    assert codes == ALL_CODES


def test_generation_is_deterministic(apps):
    again = build_apps(20, seed=42)
    assert [ground_truth(a) for a in apps] == [ground_truth(a) for a in again]
    assert render_html(apps[3], "noc") == render_html(again[3], "noc")
    other = build_apps(20, seed=7)
    assert [ground_truth(a) for a in apps] != [ground_truth(a) for a in other]


# ---- clean applications satisfy every rule's precondition ----


def test_clean_dates_follow_the_rules(apps):
    s = get_settings()
    clean = [a for a in apps if not a.defects]
    for a in clean:
        assert a.trust_reg_date < a.registration_date < a.noc_issue_date < a.application_date
        for day in (a.application_date, a.affidavit_date):
            assert s.APPLICATION_WINDOW_START <= day <= s.APPLICATION_WINDOW_END
        assert a.noc_valid_until > s.ACADEMIC_YEAR_END
        assert a.noc_issue_date < a.noc_valid_until
        if a.accreditation:
            assert a.accreditation.valid_to >= s.ACADEMIC_YEAR_END
            assert a.accreditation.valid_from > a.trust_reg_date


def test_clean_apps_have_every_required_document_and_the_rest_vary(apps):
    required = set(load_checklist("eoa")["required_docs"])
    clean = [a for a in apps if not a.defects]
    for a in clean:
        assert required <= {t for _, t, _ in a.documents()}
        assert 1 <= len(a.photos) <= 2
    assert {bool(a.accreditation) for a in apps} == {True, False}
    assert {len(a.photos) for a in apps} == {1, 2}


def test_clean_apps_agree_on_area_across_units_and_on_the_trust_as_owner(apps):
    units = set()
    for a in (a for a in apps if not a.defects):
        acres = [a.form_area.acres, a.deed_area.acres, a.affidavit_area.acres]
        assert max(acres) - min(acres) <= 0.01 * max(acres), a.app_id  # within the 1% tolerance
        units |= {a.form_area.unit, a.deed_area.unit, a.affidavit_area.unit}
        assert a.owner_name == a.trust_name and a.mortgage_status == "none"
        assert re.fullmatch(r"FIRE/[A-Z]{2}/\d{4}/\d{6}", a.noc_ref_no)
    assert units == {"acre", "hectare", "guntha"}
    assert any(a.deed_area.marathi for a in apps)  # Devanagari digits and unit on some deeds


def test_affidavit_sometimes_abbreviates_the_institute(apps):
    short = [a for a in apps if not a.defects and a.institute_short]
    assert short and any(not a.institute_short for a in apps if not a.defects)
    for a in short:
        assert a.institute_short != a.institute_name
        assert normalize_name(a.institute_short) == normalize_name(a.institute_name)


# ---- ground truth ----


def test_true_fields_use_exactly_the_trd_field_names(apps):
    for a in apps:
        truth = true_fields(a)
        for doc_id, fields in truth.items():
            assert DOC_ID.match(doc_id), doc_id
            assert set(fields) == TRD_FIELDS[doc_type_of(doc_id)], doc_id
    deed = true_fields(apps[0])["app001_land_deed"]
    assert set(deed["area"]) == {"value", "unit"} and "land_area" not in deed
    assert deed["mortgage_status"] == "none"


def test_ground_truth_is_a_valid_trd_ground_truth_and_names_the_files(apps):
    for a in apps:
        gt = ground_truth(a)
        assert GroundTruth.model_validate_json(gt.model_dump_json()) == gt
        assert {d.doc_id for d in gt.documents} == set(gt.true_fields)
        for d in gt.documents:
            expected = {
                "application_form": "application_form.json",
                "land_deed": "land_deed.pdf",
                "noc": "noc.pdf",
                "affidavit": "affidavit.pdf",
                "accreditation_cert": "accreditation_cert.pdf",
            }.get(d.doc_type.value, f"lab_photo_{d.path.split('_')[-1]}")
            assert d.path == expected
        if a.accreditation:
            assert "accreditation_cert.pdf" in {d.path for d in gt.documents}


def test_defect_doc_ids_are_real_documents(apps):
    for a in apps:
        gt = ground_truth(a)
        present = {d.doc_id for d in gt.documents}
        for d in a.defects:
            assert DOC_ID.match(d.doc_id) and d.doc_id.startswith(a.app_id), d
            if d.defect == "MISSING_DOC":
                assert d.doc_id not in present  # the document that is missing
                assert doc_type_of(d.doc_id) in {"noc", "affidavit", "land_deed"}
            else:
                assert d.doc_id in present, d  # the document that carries the defect
            assert d.detail


# ---- one test per defect: the documents really change ----


def fresh(index=3):
    app = build_clean_app(index)
    return app, copy.deepcopy(app), random.Random(1)


def inject(app, code, rng, ctx=None):
    app.defects += defect_module.DEFECTS[code](app, rng, ctx or {})


def test_area_mismatch_changes_form_and_affidavit_but_not_the_deed():
    app, before, rng = fresh()
    inject(app, "AREA_MISMATCH", rng)
    assert app.deed_area == before.deed_area
    for area in (app.form_area, app.affidavit_area):
        assert abs(area.acres - before.deed_area.acres) > 0.2 * before.deed_area.acres
    assert {d.doc_id for d in app.defects} == {
        app.doc_id("application_form"),
        app.doc_id("affidavit"),
    }


def test_owner_mismatch_makes_a_different_owner():
    app, before, rng = fresh()
    inject(app, "OWNER_MISMATCH", rng)
    assert app.owner_name != before.owner_name and not names_match(app.owner_name, app.trust_name)
    assert [d.doc_id for d in app.defects] == [app.doc_id("land_deed")]


def test_name_mismatch_changes_only_the_noc():
    app, before, rng = fresh()
    inject(app, "NAME_MISMATCH", rng)
    assert not names_match(app.noc_institute_name, app.institute_name)
    assert app.institute_name == before.institute_name and app.owner_name == before.owner_name


def test_expired_noc_ends_before_the_academic_year_but_after_issue():
    app, before, rng = fresh()
    inject(app, "EXPIRED_NOC", rng)
    s = get_settings()
    assert app.noc_issue_date < app.noc_valid_until < s.ACADEMIC_YEAR_END
    assert app.noc_valid_until != before.noc_valid_until


def test_timeline_defect_puts_the_noc_before_the_trust():
    app, before, rng = fresh()
    inject(app, "TIMELINE_NOC_BEFORE_TRUST", rng)
    assert app.noc_issue_date < app.trust_reg_date and app.noc_issue_date < app.noc_valid_until
    assert f"/{app.noc_issue_date.year}/" in app.noc_ref_no


def test_bad_ref_format_breaks_the_format_but_changes_the_number():
    pattern = re.compile(r"^FIRE/[A-Z]{2}/\d{4}/\d{6}$")
    for index in range(1, 9):  # all four malformed variants appear over a few seeds
        app, before, _ = fresh(index)
        inject(app, "BAD_REF_FORMAT", random.Random(index))
        assert not pattern.match(app.noc_ref_no) and pattern.match(before.noc_ref_no)


def test_missing_doc_drops_the_document_from_the_files_and_the_truth():
    for doc_type in ("noc", "affidavit", "land_deed"):
        app, _, rng = fresh()
        app.defects += defect_module.missing_doc(app, rng, {}, doc_type)
        assert doc_type in app.missing
        assert app.doc_id(doc_type) not in true_fields(app)
        assert doc_type not in {t for _, t, _ in app.documents()}
    with pytest.raises(ValueError, match="cannot drop"):
        defect_module.missing_doc(build_clean_app(1), random.Random(1), {}, "application_form")


def test_mortgaged_land_changes_the_printed_deed():
    app, _, rng = fresh()
    inject(app, "MORTGAGED_LAND", rng)
    assert app.mortgage_status == "mortgaged"
    lines = html_lines(render_html(app, "land_deed"))
    assert any("Mortgage Status: Mortgaged" in line for line in lines)  # not a label only


def test_printed_documents_carry_the_injected_values():
    """Every reasoning-detectable defect changes the HTML that is rendered, not just the label."""
    app, _, rng = fresh()
    for code in ("OWNER_MISMATCH", "EXPIRED_NOC", "BAD_REF_FORMAT", "NAME_MISMATCH"):
        inject(app, code, rng)
    deed, noc = html_lines(render_html(app, "land_deed")), html_lines(render_html(app, "noc"))
    assert any(app.owner_name in line for line in deed)
    assert any(f"{app.noc_valid_until:%d %B %Y}" in line for line in noc)
    assert any(app.noc_ref_no in line for line in noc)
    assert any(app.noc_institute_name in line and "Institute Name" in line for line in noc)


def test_duplicate_photo_reuses_an_earlier_photo_exactly(tmp_path):
    from docverf.synthetic.images import save_lab_photo

    source_app = build_clean_app(1)
    app, _, rng = fresh(2)
    source = source_app.photos[0]
    inject(
        app, "DUPLICATE_PHOTO", rng, {"photo_sources": [(source_app.photo_doc_id(source), source)]}
    )
    save_lab_photo(source, tmp_path / "a.jpg")
    save_lab_photo(app.photos[0], tmp_path / "b.jpg")
    assert (tmp_path / "a.jpg").read_bytes() == (tmp_path / "b.jpg").read_bytes()
    assert app.photos[0].copied_from == source_app.photo_doc_id(source)
    assert true_fields(app)[app.photo_doc_id(app.photos[0])]["room_label"] == source.room_label


def test_label_only_defects_leave_the_documents_clean():
    for code in ("SIGNED_THEN_EDITED", "ISSUER_MISMATCH", "ISSUER_TIMEOUT"):
        app, before, rng = fresh()
        inject(app, code, rng)
        assert true_fields(app) == true_fields(before)
        assert [d.doc_id for d in app.defects] == [app.doc_id("noc")]
        assert "label only" in app.defects[0].detail
    mismatch = json.loads(app_detail("ISSUER_MISMATCH").split("record ")[1].split(", document")[0])
    assert mismatch["ref_no"].startswith("FIRE/")


def app_detail(code):
    app, _, rng = fresh()
    inject(app, code, rng)
    return app.defects[0].detail


def test_pasted_signature_only_marks_the_noc_for_rendering():
    app, before, rng = fresh()
    inject(app, "PASTED_SIGNATURE", rng)
    assert app.pasted_signature and true_fields(app) == true_fields(before)


def test_unknown_defect_is_refused():
    with pytest.raises(ValueError, match="unknown defect"):
        defect_module.inject_defect(build_clean_app(1), "NOT_A_DEFECT", random.Random(1), {})


# ---- the rules extractor's labels are the template labels ----


def test_every_label_spec_matches_exactly_one_line_of_its_template(apps):
    for a in apps[:6]:
        for doc_type, specs in _LABEL_SPECS.items():
            kind = doc_type.value
            if kind == "application_form" or (kind == "accreditation_cert" and not a.accreditation):
                continue
            html = render_html(a, kind)
            for field, labels, _ in specs:
                assert label_lines(html, labels[0]) == 1, (a.app_id, kind, field, labels[0])


def test_rules_extractor_reads_every_template_back_to_the_truth(apps):
    """The template labels and rules_extractor._LABEL_SPECS agree for all 20 applications."""
    problems = []
    for a in apps:
        truth = true_fields(a)
        for doc_id, doc_type, _ in a.documents():
            if doc_type in ("application_form", "lab_photo"):
                continue
            got = as_truth(rules_extract(html_words(render_html(a, doc_type)), DocType(doc_type)))
            # a malformed NOC reference number is not matched by the extractor's reference pattern
            may_miss = (
                {"ref_no"}
                if a.defects and "BAD_REF_FORMAT" in {d.defect for d in a.defects}
                else set()
            )
            problems += [f"{doc_id} {p}" for p in differences(got, truth[doc_id], may_miss)]
    assert problems == []


# ---- photos ----


@pytest.fixture(scope="module")
def photo_files(apps, tmp_path_factory):
    out = tmp_path_factory.mktemp("synthetic")
    generate_dataset(out, 20, render=False)
    return out


def test_photos_pass_the_quality_gate_and_carry_the_capture_date_in_exif(apps, photo_files):
    for a in apps:
        for p in a.photos:
            path = photo_files / a.app_id / f"lab_photo_{p.n}.jpg"
            assert _check_quality(path, get_settings().BLUR_THRESHOLD)[0], path
            exif = Image.open(path).getexif()
            assert exif.get_ifd(0x8769)[0x9003].startswith(f"{p.capture_date:%Y:%m:%d}")


def test_only_the_injected_photos_are_duplicates(apps, photo_files):
    hashes = {}
    for a in apps:
        for p in a.photos:
            path = photo_files / a.app_id / f"lab_photo_{p.n}.jpg"
            hashes[(a.app_id, p.n)] = (
                hashlib.sha256(path.read_bytes()).hexdigest(),
                imagehash.phash(Image.open(path)),
                p.copied_from,
            )
    limit = get_settings().PHASH_MAX_DIST
    for (ka, (sa, pa, ca)), (kb, (sb, pb, cb)) in itertools.combinations(hashes.items(), 2):
        if ca or cb:  # one of the pair is the injected copy
            continue
        assert sa != sb and pa - pb > limit, (ka, kb)
    copies = [k for k, v in hashes.items() if v[2]]
    assert len(copies) == 1
    (copy_key,) = copies
    twin = [k for k, v in hashes.items() if k != copy_key and v[0] == hashes[copy_key][0]]
    assert len(twin) == 1 and twin[0][0] != copy_key[0]  # same bytes, in another application


# ---- dataset on disk without PDFs, and the CLI ----


def test_generate_dataset_without_pdfs_writes_json_html_and_photos(tmp_path):
    truths = generate_dataset(tmp_path, 2, render=False)
    assert [t.app_id for t in truths] == ["app001", "app002"]
    names = {p.name for p in (tmp_path / "app001").iterdir()}
    assert {"application_form.json", "ground_truth.json", "land_deed.html", "noc.html",
            "affidavit.html", "lab_photo_1.jpg"} <= names  # fmt: skip
    assert not any(n.endswith(".pdf") for n in names)
    gt = GroundTruth.model_validate_json(
        (tmp_path / "app002" / "ground_truth.json").read_text("utf-8")
    )
    assert [d.defect for d in gt.injected_defects] == ["AREA_MISMATCH", "AREA_MISMATCH"]


def test_cli_writes_a_dataset(tmp_path, capsys):
    assert main(["--out", str(tmp_path), "--n", "3", "--no-pdf"]) == 0
    out = capsys.readouterr().out
    assert "app001" in out and "(clean)" in out and "AREA_MISMATCH" in out
    assert (tmp_path / "app003" / "ground_truth.json").exists()
    with pytest.raises(SystemExit):
        main(["--out", str(tmp_path), "--n", "0"])


def test_clean_late_binding_dates_never_leave_the_window_for_other_seeds():
    s = get_settings()
    for seed in (1, 2, 3, 99):
        for index in range(1, 12):
            a = build_clean_app(index, seed)
            assert s.APPLICATION_WINDOW_START <= a.affidavit_date <= a.application_date
            assert a.application_date <= s.APPLICATION_WINDOW_END
            assert a.noc_valid_until - s.ACADEMIC_YEAR_END >= timedelta(days=30)

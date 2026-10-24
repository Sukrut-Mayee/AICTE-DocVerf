"""The generated files on disk: PDFs rendered with a real browser (skipped if none is installed)."""

import json
import re
from pathlib import Path

import fitz
import pytest
from docverf.config import get_settings
from docverf.extraction.extract import _check_quality, _render_pdf_pages
from docverf.extraction.rules_extractor import rules_extract
from docverf.forensics.ela import run_ela
from docverf.reasoning.run import checks_to_findings
from docverf.schemas import DocType, ExtractionResult, GroundTruth, Region
from docverf.synthetic.generate import build_apps, generate_dataset, write_app
from docverf.synthetic.model import extraction_results, ground_truth
from docverf.synthetic.render import PdfRenderer, find_browser, render_html

from tests.synth import as_truth, differences, pdf_words

pytestmark = pytest.mark.skipif(find_browser() is None, reason="no Chrome / Edge to render PDFs")


@pytest.fixture(scope="module")
def dataset(tmp_path_factory):
    out = tmp_path_factory.mktemp("dataset")
    return out, generate_dataset(out, n_apps=2)


def test_files_follow_the_trd_layout(dataset):
    out, truths = dataset
    first = {p.name for p in (out / "app001").iterdir()}
    assert {
        "application_form.json", "land_deed.pdf", "noc.pdf", "affidavit.pdf",
        "accreditation_cert.pdf", "lab_photo_1.jpg", "ground_truth.json",
    } <= first  # fmt: skip
    assert {"land_deed.html", "noc.html", "affidavit.html", "accreditation_cert.html"} <= first
    second = {p.name for p in (out / "app002").iterdir()}
    assert "accreditation_cert.pdf" not in second  # only some applications carry one
    for truth in truths:
        for doc in truth.documents:
            assert (out / truth.app_id / doc.path).is_file(), doc.path
        assert {p.name for p in (out / truth.app_id).glob("*.pdf")} == {
            d.path for d in truth.documents if d.path.endswith(".pdf")
        }


def test_pdfs_are_single_a4_pages_with_a_text_layer_and_devanagari_labels(dataset):
    out, _ = dataset
    for pdf in sorted(out.glob("app*/*.pdf")):
        with fitz.open(str(pdf)) as doc:
            assert doc.page_count == 1, pdf
            assert abs(doc[0].rect.width - 595) < 2 and abs(doc[0].rect.height - 842) < 2
            text = doc[0].get_text()
        assert "Village:" in text or "Reference No." in text or "Institute Name:" in text
        if pdf.name in ("land_deed.pdf", "noc.pdf", "affidavit.pdf"):
            assert re.search("[ऀ-ॿ]", text), f"{pdf} has no Devanagari label"


def test_application_form_json_and_ground_truth_validate_and_match_the_data(dataset):
    out, truths = dataset
    apps = build_apps(2)
    for app, truth in zip(apps, truths, strict=True):
        folder = out / app.app_id
        form = ExtractionResult.model_validate_json(
            (folder / "application_form.json").read_text("utf-8")
        )
        want = next(r for r in extraction_results(app) if r.doc_type == DocType.APPLICATION_FORM)
        assert form == want and all(f.confidence == 1.0 for f in form.fields.values())
        on_disk = GroundTruth.model_validate_json((folder / "ground_truth.json").read_text("utf-8"))
        assert on_disk == truth == ground_truth(app)


def test_the_html_is_kept_and_is_what_the_pdf_was_printed_from(dataset):
    out, _ = dataset
    app = build_apps(2)[0]
    for doc_type in ("land_deed", "noc", "affidavit", "accreditation_cert"):
        assert (out / "app001" / f"{doc_type}.html").read_text("utf-8") == render_html(
            app, doc_type
        )


def test_rules_extractor_reads_the_real_pdfs_back_to_the_truth(dataset):
    """OCR stand-in: the PDF's own word boxes. Labels, layout and extractor agree."""
    out, truths = dataset
    problems = []
    for truth in truths:
        for doc in truth.documents:
            if doc.doc_type.value in ("application_form", "lab_photo"):
                continue
            got = as_truth(rules_extract(pdf_words(out / truth.app_id / doc.path), doc.doc_type))
            problems += [
                f"{doc.doc_id} {p}" for p in differences(got, truth.true_fields[doc.doc_id])
            ]
    assert problems == []


def test_extraction_quality_gate_accepts_every_pdf_and_photo(dataset):
    out, _ = dataset
    threshold = get_settings().BLUR_THRESHOLD
    for pdf in sorted(out.glob("app*/*.pdf")):
        for _, image in _render_pdf_pages(pdf):
            assert _check_quality(image, threshold)[0], pdf
    for photo in sorted(out.glob("app*/*.jpg")):
        assert _check_quality(photo, threshold)[0], photo


# ---- PASTED_SIGNATURE: a scanned NOC page that forensics flags ----


@pytest.fixture(scope="module")
def pasted(tmp_path_factory):
    out = tmp_path_factory.mktemp("pasted")
    app = next(a for a in build_apps(20) if a.pasted_signature)
    with PdfRenderer(out) as renderer:
        truth = write_app(app, out, renderer)
    return out, app, truth


def test_pasted_signature_noc_is_a_scanned_page_with_the_region_recorded(pasted):
    out, app, truth = pasted
    with fitz.open(str(out / app.app_id / "noc.pdf")) as doc:
        assert doc.page_count == 1 and doc[0].get_text().strip() == ""  # no text layer
        assert len(doc[0].get_images()) == 1
    (defect,) = [d for d in truth.injected_defects if d.defect == "PASTED_SIGNATURE"]
    assert defect.doc_id == f"{app.app_id}_noc"
    bbox = json.loads(re.search(r"bbox (\[.*\])", defect.detail).group(1))
    assert (
        len(bbox) == 4
        and all(0 <= v <= 1 for v in bbox)
        and bbox[0] < bbox[2]
        and bbox[1] < bbox[3]
    )
    assert (
        truth.injected_defects
        == GroundTruth.model_validate_json(
            (out / app.app_id / "ground_truth.json").read_text("utf-8")
        ).injected_defects
    )


def test_ela_flags_the_pasted_signature_region_and_it_reaches_the_findings(pasted):
    out, app, truth = pasted
    (defect,) = [d for d in truth.injected_defects if d.defect == "PASTED_SIGNATURE"]
    bbox = json.loads(re.search(r"bbox (\[.*\])", defect.detail).group(1))
    with fitz.open(str(out / app.app_id / "noc.pdf")) as doc:
        jpeg = out / "scan.jpg"
        jpeg.write_bytes(doc.extract_image(doc[0].get_images()[0][0])["image"])
    check = run_ela(str(jpeg), defect.doc_id, [Region(type="signature", page=1, bbox=bbox)])
    assert check.status.value == "suspicious"
    (finding,) = checks_to_findings(app.app_id, [check])
    assert finding.type.value == "forensic_signal" and finding.doc_ids == [defect.doc_id]
    assert finding.message.startswith("Preliminary indicator:")
    # the same region of the page elsewhere, away from the paste, is not flagged
    elsewhere = run_ela(
        str(jpeg), defect.doc_id, [Region(type="signature", page=1, bbox=[0.05, 0.05, 0.3, 0.12])]
    )
    assert elsewhere.status.value == "clean"


def test_cli_end_to_end_with_pdfs(tmp_path):
    from docverf.synthetic.__main__ import main

    assert main(["--out", str(tmp_path), "--n", "1"]) == 0
    assert (tmp_path / "app001" / "land_deed.pdf").is_file()
    assert not list(Path(tmp_path).glob(".chrome-profile-*"))  # the browser profile is cleaned up

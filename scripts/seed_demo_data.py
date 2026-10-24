"""Seed git-ignored demo data for the officer dashboard.

Writes:
  data/out/pipeline/app001.json       contract-B pipeline result
  data/synthetic/app001/*             fixture-derived PDFs and the application form

The PDFs are simple, clearly labelled demo documents whose text sits inside the
normalized evidence boxes used by the UI.  They are not authentic issued documents.
Real pipeline output is never overwritten unless `--force` is passed.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

import pymupdf

from services.api.mock_data import (
    APP_ID,
    FIXTURE_DIR,
    build_mock_app001,
    write_mock_app001,
)
from services.api.settings import REPO_ROOT

PIPELINE_PATH = REPO_ROOT / "data" / "out" / "pipeline" / f"{APP_ID}.json"
APP_DIR = REPO_ROOT / "data" / "synthetic" / APP_ID

PAGE_WIDTH = 595
PAGE_HEIGHT = 842
FOOTER = (
    "Demo fixture document generated from tests/fixtures/apps/app_conflict for UI "
    "development. Not an authentic issued document."
)


def _fields_by_doc(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        extraction["doc_id"].removeprefix(f"{APP_ID}_"): extraction["fields"]
        for extraction in payload["extractions"]
    }


def _new_page(title: str, subtitle: str) -> tuple[pymupdf.Document, pymupdf.Page]:
    document = pymupdf.open()
    page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    page.insert_textbox(
        pymupdf.Rect(40, 40, PAGE_WIDTH - 40, 80),
        title,
        fontsize=18,
        fontname="helv",
    )
    page.insert_textbox(
        pymupdf.Rect(40, 82, PAGE_WIDTH - 40, 108),
        subtitle,
        fontsize=9,
        fontname="helv",
        color=(0.35, 0.35, 0.35),
    )
    page.draw_line((40, 112), (PAGE_WIDTH - 40, 112), color=(0.6, 0.6, 0.6))
    page.insert_textbox(
        pymupdf.Rect(40, PAGE_HEIGHT - 70, PAGE_WIDTH - 40, PAGE_HEIGHT - 30),
        FOOTER,
        fontsize=7,
        fontname="helv",
        color=(0.45, 0.45, 0.45),
    )
    return document, page


def _text_in_bbox(page: pymupdf.Page, bbox: list[float], text: str, size: float = 10) -> None:
    rect = pymupdf.Rect(
        bbox[0] * PAGE_WIDTH,
        bbox[1] * PAGE_HEIGHT,
        bbox[2] * PAGE_WIDTH,
        bbox[3] * PAGE_HEIGHT,
    )
    page.insert_textbox(rect, text, fontsize=size, fontname="helv")


def _draw_lines(page: pymupdf.Page, lines: list[str], start_y: int = 150) -> None:
    for index, line in enumerate(lines):
        page.insert_textbox(
            pymupdf.Rect(48, start_y + index * 20, PAGE_WIDTH - 48, start_y + index * 20 + 18),
            line,
            fontsize=9,
            fontname="helv",
        )


def _make_land_deed(fields: dict[str, Any]) -> pymupdf.Document:
    document, page = _new_page(
        "LAND DEED",
        "Sale deed extract - Survey No. 45/2, Pune",
    )
    _text_in_bbox(page, fields["owner_name"]["bbox"], str(fields["owner_name"]["value"]))
    _text_in_bbox(page, fields["survey_no"]["bbox"], f"Survey No. {fields['survey_no']['value']}")
    _text_in_bbox(
        page,
        fields["area"]["bbox"],
        f"Area: {fields['area']['value']} {fields['area'].get('unit', '')}",
    )
    _draw_lines(
        page,
        [
            "This extract records the transfer of the land parcel described above.",
            f"Registration date: {fields['registration_date']['value']}",
            f"Mortgage status: {fields['mortgage_status']['value']}",
            "Executed before the Sub-Registrar, Pune.",
        ],
        start_y=430,
    )
    return document


def _make_noc(fields: dict[str, Any]) -> pymupdf.Document:
    document, page = _new_page(
        "NO OBJECTION CERTIFICATE",
        "Maharashtra Fire Services - Fire safety clearance",
    )
    _text_in_bbox(page, fields["issuer"]["bbox"], str(fields["issuer"]["value"]))
    _text_in_bbox(page, fields["ref_no"]["bbox"], f"Ref: {fields['ref_no']['value']}")
    _text_in_bbox(
        page, fields["issue_date"]["bbox"], f"Issue date: {fields['issue_date']['value']}"
    )
    _text_in_bbox(
        page, fields["valid_until"]["bbox"], f"Valid until: {fields['valid_until']['value']}"
    )
    _text_in_bbox(
        page,
        fields["institute_name"]["bbox"],
        f"Institute: {fields['institute_name']['value']}",
    )
    _draw_lines(
        page,
        [
            "The premises have been inspected for fire safety compliance.",
            "This certificate is subject to the conditions printed on the reverse.",
        ],
        start_y=430,
    )
    return document


def _make_affidavit(fields: dict[str, Any]) -> pymupdf.Document:
    document, page = _new_page(
        "AFFIDAVIT",
        "Declaration by the applicant institute",
    )
    _text_in_bbox(
        page,
        fields["institute_name"]["bbox"],
        f"Institute: {fields['institute_name']['value']}",
    )
    _text_in_bbox(
        page,
        fields["application_no"]["bbox"],
        f"Application No: {fields['application_no']['value']}",
    )
    _text_in_bbox(page, fields["date"]["bbox"], f"Date: {fields['date']['value']}")
    _text_in_bbox(
        page,
        fields["land_area_declared"]["bbox"],
        f"Declared land area: {fields['land_area_declared']['value']} acre",
    )
    _draw_lines(
        page,
        [
            "I declare that the information furnished in this application is true.",
            "The declared land area is subject to verification against the land deed.",
        ],
        start_y=430,
    )
    return document


def _write_pdf(document: pymupdf.Document, path: Path) -> None:
    document.save(path)
    document.close()


def seed(*, force: bool = False) -> None:
    wrote = write_mock_app001(PIPELINE_PATH, force=force)
    if not wrote:
        print(
            f"Refusing to overwrite non-mock pipeline output at {PIPELINE_PATH}. "
            "Pass --force to replace it."
        )
        return

    payload = build_mock_app001()
    fields = _fields_by_doc(payload)
    APP_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(
        FIXTURE_DIR / "application_form.json",
        APP_DIR / "application_form.json",
    )
    form_path = APP_DIR / "application_form.json"
    form = json.loads(form_path.read_text(encoding="utf-8"))
    form["app_id"] = APP_ID
    form["doc_id"] = f"{APP_ID}_application_form"
    form_path.write_text(json.dumps(form, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    builders = {
        "land_deed.pdf": _make_land_deed(fields["land_deed"]),
        "noc.pdf": _make_noc(fields["noc"]),
        "affidavit.pdf": _make_affidavit(fields["affidavit"]),
    }
    for name, document in builders.items():
        target = APP_DIR / name
        if target.exists() and not force:
            document.close()
            continue
        _write_pdf(document, target)

    print(f"Seeded mock pipeline output: {PIPELINE_PATH}")
    print(f"Seeded demo documents:       {APP_DIR}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace existing pipeline output and demo PDFs.",
    )
    args = parser.parse_args()
    seed(force=args.force)


if __name__ == "__main__":
    main()

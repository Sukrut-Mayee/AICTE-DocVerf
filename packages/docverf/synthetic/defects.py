"""Defect injection from the TRD §13.2 catalog.

One function per defect. Each changes the application data so that the expected detector fires
and returns an InjectedDefect for every document that carries the defect (its real doc_id).
SIGNED_THEN_EDITED, ISSUER_MISMATCH and ISSUER_TIMEOUT are label-only: the documents stay clean,
and the signer / mock issuer act on the recorded label.
"""

import json
import random
import re
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from docverf.config import get_settings
from docverf.reasoning.entity_resolution import names_match
from docverf.schemas import InjectedDefect
from docverf.synthetic.model import (
    INSTITUTE_TYPES,
    PREFIXES,
    AppSpec,
    make_area,
)

Context = dict[str, Any]  # photo_sources: [(doc_id, Photo)] of earlier applications
OTHER_OWNERS = ["Charitable Society", "Welfare Foundation", "Shikshan Mandal"]
REQUIRED_TO_DROP = ["noc", "affidavit", "land_deed"]  # application_form is the JSON backbone


def _defect(app: AppSpec, doc_id: str, code: str, detail: str) -> InjectedDefect:
    return InjectedDefect(doc_id=doc_id, defect=code, detail=detail)


def _unlike(rng: random.Random, make: Callable[[str], str], *names: str) -> str:
    """A name from `make(prefix)` that the entity matcher does not take for any of `names`."""
    for _ in range(100):
        candidate = make(rng.choice(PREFIXES))
        if not any(names_match(candidate, name) for name in names):
            return candidate
    raise RuntimeError(f"no name differing from {names}")


def area_mismatch(app: AppSpec, rng: random.Random, ctx: Context) -> list[InjectedDefect]:
    """Form and affidavit state another area than the deed (LAND_AREA_AGREE)."""
    deed_acres = app.deed_area.acres
    new_acres = round(deed_acres * rng.choice([0.5, 0.6, 1.5, 1.75, 2.0]) / 0.025) * 0.025
    out = []
    for attr, doc_type in (("form_area", "application_form"), ("affidavit_area", "affidavit")):
        if doc_type in app.missing:
            continue
        old = getattr(app, attr)
        setattr(app, attr, make_area(round(new_acres, 3), old.unit))
        out.append(
            _defect(
                app,
                app.doc_id(doc_type),
                "AREA_MISMATCH",
                f"area {getattr(app, attr).value:g} {old.unit} instead of the deed's "
                f"{app.deed_area.value:g} {app.deed_area.unit}",
            )
        )
    return out


def owner_mismatch(app: AppSpec, rng: random.Random, ctx: Context) -> list[InjectedDefect]:
    """The deed owner is not the applicant trust (OWNER_IS_TRUST)."""
    old = app.owner_name
    app.owner_name = _unlike(rng, lambda p: f"{p} {rng.choice(OTHER_OWNERS)}", app.trust_name)
    return [
        _defect(
            app,
            app.doc_id("land_deed"),
            "OWNER_MISMATCH",
            f"owner '{app.owner_name}' instead of the trust '{old}'",
        )
    ]


def name_mismatch(app: AppSpec, rng: random.Random, ctx: Context) -> list[InjectedDefect]:
    """The NOC names a different institute (INSTITUTE_NAME_AGREE)."""
    app.noc_institute_name = _unlike(
        rng, lambda p: f"{p} {rng.choice(INSTITUTE_TYPES)}", app.institute_name
    )
    return [
        _defect(
            app,
            app.doc_id("noc"),
            "NAME_MISMATCH",
            f"NOC names '{app.noc_institute_name}' instead of '{app.institute_name}'",
        )
    ]


def expired_noc(app: AppSpec, rng: random.Random, ctx: Context) -> list[InjectedDefect]:
    """The NOC ends before the academic year does (NOC_VALID_FOR_YEAR)."""
    last_day = get_settings().ACADEMIC_YEAR_END - timedelta(days=1)
    latest = (last_day - app.application_date).days
    app.noc_valid_until = app.application_date + timedelta(days=rng.randint(30, latest))
    return [
        _defect(
            app,
            app.doc_id("noc"),
            "EXPIRED_NOC",
            f"valid until {app.noc_valid_until}, before the academic year ends "
            f"({get_settings().ACADEMIC_YEAR_END})",
        )
    ]


def timeline_noc_before_trust(
    app: AppSpec, rng: random.Random, ctx: Context
) -> list[InjectedDefect]:
    """The NOC was issued before the trust existed (TL_NOC_AFTER_TRUST)."""
    app.noc_issue_date = app.trust_reg_date - timedelta(days=rng.randint(120, 2000))
    app.noc_ref_no = re.sub(r"/\d{4}/", f"/{app.noc_issue_date.year}/", app.noc_ref_no)
    return [
        _defect(
            app,
            app.doc_id("noc"),
            "TIMELINE_NOC_BEFORE_TRUST",
            f"issued {app.noc_issue_date}, trust registered {app.trust_reg_date}",
        )
    ]


def bad_ref_format(app: AppSpec, rng: random.Random, ctx: Context) -> list[InjectedDefect]:
    """The NOC reference number is malformed (NOC_REF_FORMAT)."""
    year, serial = app.noc_issue_date.year, app.noc_ref_no.rsplit("/", 1)[-1]
    app.noc_ref_no = rng.choice(
        [
            f"FIRE/MH/{str(year)[2:]}/{serial}",  # two-digit year
            f"FIRE/MH/{year}/{serial[:5]}",  # five-digit serial
            f"FIRE-MH-{year}-{serial}",  # wrong separators
            f"fire/mh/{year}/{serial}",  # lower case
        ]
    )
    return [
        _defect(
            app,
            app.doc_id("noc"),
            "BAD_REF_FORMAT",
            f"reference number '{app.noc_ref_no}' does not follow FIRE/XX/YYYY/NNNNNN",
        )
    ]


def missing_doc(
    app: AppSpec, rng: random.Random, ctx: Context, doc_type: str | None = None
) -> list[InjectedDefect]:
    """A required document is left out (REQUIRED_DOCS). The doc_id is the missing document's."""
    doc_type = doc_type or rng.choice(REQUIRED_TO_DROP)
    if doc_type not in REQUIRED_TO_DROP:
        raise ValueError(f"cannot drop {doc_type!r}; choose one of {REQUIRED_TO_DROP}")
    app.missing.add(doc_type)
    return [
        _defect(
            app,
            app.doc_id(doc_type),
            "MISSING_DOC",
            f"required document '{doc_type}' not submitted",
        )
    ]


def mortgaged_land(app: AppSpec, rng: random.Random, ctx: Context) -> list[InjectedDefect]:
    """The deed shows the land as mortgaged (LAND_NOT_MORTGAGED)."""
    app.mortgage_status = "mortgaged"
    return [_defect(app, app.doc_id("land_deed"), "MORTGAGED_LAND", "mortgage status 'mortgaged'")]


def duplicate_photo(app: AppSpec, rng: random.Random, ctx: Context) -> list[InjectedDefect]:
    """A lab photo is byte-identical to one in an earlier application (provenance duplicates)."""
    source_id, source = rng.choice(ctx["photo_sources"])
    photo = app.photos[0]
    photo.seed, photo.room_label = source.seed, source.room_label
    photo.equipment_count, photo.capture_date = source.equipment_count, source.capture_date
    photo.copied_from = source_id
    return [
        _defect(
            app,
            app.photo_doc_id(photo),
            "DUPLICATE_PHOTO",
            f"same image bytes as {source_id}",
        )
    ]


def pasted_signature(app: AppSpec, rng: random.Random, ctx: Context) -> list[InjectedDefect]:
    """A signature image is pasted onto the rasterised NOC page (forensics ELA / noise)."""
    app.pasted_signature = True
    return [
        _defect(
            app,
            app.doc_id("noc"),
            "PASTED_SIGNATURE",
            "noc.pdf is a scanned page with a pasted signature image",
        )
    ]


def signed_then_edited(app: AppSpec, rng: random.Random, ctx: Context) -> list[InjectedDefect]:
    """Label only: the signer signs noc.pdf, then edits it (provenance pdf_signature)."""
    return [
        _defect(
            app,
            app.doc_id("noc"),
            "SIGNED_THEN_EDITED",
            "label only: sign noc.pdf with the trust tooling, then edit it after signing",
        )
    ]


def issuer_mismatch(app: AppSpec, rng: random.Random, ctx: Context) -> list[InjectedDefect]:
    """Label only: the mock issuer's record for this NOC differs from the document."""
    record = {
        "ref_no": app.noc_ref_no,
        "valid_until": (app.noc_valid_until + timedelta(days=rng.randint(200, 600))).isoformat(),
    }
    detail = f"label only: mock issuer record {json.dumps(record)}, document {app.noc_valid_until}"
    return [_defect(app, app.doc_id("noc"), "ISSUER_MISMATCH", detail)]


def issuer_timeout(app: AppSpec, rng: random.Random, ctx: Context) -> list[InjectedDefect]:
    """Label only: the mock issuer delays its answer for this NOC (verification_pending)."""
    return [
        _defect(
            app,
            app.doc_id("noc"),
            "ISSUER_TIMEOUT",
            f"label only: mock issuer delays the response for {app.noc_ref_no}",
        )
    ]


DEFECTS: dict[str, Callable[..., list[InjectedDefect]]] = {
    "AREA_MISMATCH": area_mismatch,
    "OWNER_MISMATCH": owner_mismatch,
    "NAME_MISMATCH": name_mismatch,
    "EXPIRED_NOC": expired_noc,
    "TIMELINE_NOC_BEFORE_TRUST": timeline_noc_before_trust,
    "BAD_REF_FORMAT": bad_ref_format,
    "MISSING_DOC": missing_doc,
    "MORTGAGED_LAND": mortgaged_land,
    "DUPLICATE_PHOTO": duplicate_photo,
    "PASTED_SIGNATURE": pasted_signature,
    "SIGNED_THEN_EDITED": signed_then_edited,
    "ISSUER_MISMATCH": issuer_mismatch,
    "ISSUER_TIMEOUT": issuer_timeout,
}


def inject_defect(app: AppSpec, spec: str, rng: random.Random, ctx: Context) -> None:
    """Apply `spec` (a TRD §13.2 code, optionally 'MISSING_DOC:noc') and record it on `app`."""
    code, _, argument = spec.partition(":")
    if code not in DEFECTS:
        raise ValueError(f"unknown defect {code!r}; known: {sorted(DEFECTS)}")
    app.defects += DEFECTS[code](app, rng, ctx, *([argument] if argument else []))

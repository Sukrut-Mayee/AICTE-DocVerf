"""Generate synthetic applications and ground truth (TRD §13.1)."""

import random
from pathlib import Path

from docverf.schemas import GroundTruth
from docverf.synthetic.defects import inject_defect
from docverf.synthetic.images import paste_signature_pdf, save_lab_photo
from docverf.synthetic.model import (
    AppSpec,
    Photo,
    build_clean_app,
    extraction_results,
    ground_truth,
)
from docverf.synthetic.render import PdfRenderer, render_html

CLEAN_SHARE = 0.4  # TRD §13.1: about 8 of 20 applications are clean

# The defects of the defective applications, in order (cycled for datasets larger than 20).
# Fixed so that every TRD §13.2 code is used, 1-3 per application, in combinations that do not
# contradict each other (e.g. no NOC defect on an application whose NOC is missing).
SCENARIOS: list[list[str]] = [
    ["AREA_MISMATCH"],
    ["OWNER_MISMATCH", "MORTGAGED_LAND"],
    ["NAME_MISMATCH"],
    ["EXPIRED_NOC"],
    ["TIMELINE_NOC_BEFORE_TRUST"],
    ["BAD_REF_FORMAT"],
    ["MISSING_DOC:affidavit"],
    ["MISSING_DOC:land_deed", "EXPIRED_NOC"],
    ["DUPLICATE_PHOTO", "MISSING_DOC:noc"],
    ["SIGNED_THEN_EDITED"],
    ["PASTED_SIGNATURE", "ISSUER_MISMATCH"],
    ["ISSUER_TIMEOUT", "AREA_MISMATCH", "OWNER_MISMATCH"],
]


def build_apps(n_apps: int = 20, seed: int = 42) -> list[AppSpec]:
    """The applications, defects applied: app001... clean first, then the defective ones."""
    n_clean = min(n_apps, max(1, round(CLEAN_SHARE * n_apps)))
    apps: list[AppSpec] = []
    photo_sources: list[tuple[str, Photo]] = []  # earlier applications' photos (DUPLICATE_PHOTO)
    for index in range(1, n_apps + 1):
        app = build_clean_app(index, seed)
        if index > n_clean:
            rng = random.Random(f"{seed}:defects:{index}")
            for spec in SCENARIOS[(index - n_clean - 1) % len(SCENARIOS)]:
                inject_defect(app, spec, rng, {"photo_sources": photo_sources})
        photo_sources += [(app.photo_doc_id(p), p) for p in app.photos if not p.copied_from]
        apps.append(app)
    return apps


def write_app(app: AppSpec, out_dir: Path, renderer: PdfRenderer | None) -> GroundTruth:
    """Write one application under out_dir/<app_id>/ (TRD §13.1); HTML is always kept."""
    app_dir = out_dir / app.app_id
    app_dir.mkdir(parents=True, exist_ok=True)
    form = next(r for r in extraction_results(app) if r.doc_type == "application_form")
    (app_dir / "application_form.json").write_text(
        form.model_dump_json(indent=2, exclude_none=True), encoding="utf-8"
    )
    for _, doc_type, name in app.documents():
        if doc_type == "lab_photo":
            photo = next(p for p in app.photos if name == f"lab_photo_{p.n}.jpg")
            save_lab_photo(photo, app_dir / name)
        elif doc_type != "application_form":
            html = app_dir / f"{doc_type}.html"
            html.write_text(render_html(app, doc_type), encoding="utf-8")
            if renderer:
                renderer.render(html, app_dir / name)
    if renderer and app.pasted_signature:  # the NOC becomes a scanned page with a pasted signature
        noc, scanned = app_dir / "noc.pdf", app_dir / "noc.scanned.pdf"
        bbox = paste_signature_pdf(noc, scanned, seed=app.index)
        scanned.replace(noc)
        for d in app.defects:
            if d.defect == "PASTED_SIGNATURE" and "pasted region" not in d.detail:
                d.detail += f"; pasted region page 1 bbox {bbox}"
    truth = ground_truth(app)  # after rendering: the pasted region is recorded in the defect
    (app_dir / "ground_truth.json").write_text(truth.model_dump_json(indent=2), encoding="utf-8")
    return truth


def generate_dataset(
    out_dir: Path, n_apps: int = 20, seed: int = 42, render: bool = True
) -> list[GroundTruth]:
    """About 40% clean and 60% defective applications under out_dir/app001 ... (data/synthetic).

    Deterministic in (n_apps, seed) apart from the timestamps Chrome puts in the PDFs.
    `render=False` skips the PDFs (HTML, JSON and photos are still written)."""
    out_dir = Path(out_dir)
    apps = build_apps(n_apps, seed)
    if not render:
        return [write_app(app, out_dir, None) for app in apps]
    with PdfRenderer(out_dir) as renderer:
        return [write_app(app, out_dir, renderer) for app in apps]

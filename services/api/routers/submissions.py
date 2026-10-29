"""Institute portal submissions: save the documents, run the live pipeline for that application.

POST /v1/submissions takes the multipart payload the portal builds: `form` (JSON of the
application form), `files` (repeated) and `doc_types` (JSON array, same order as `files`).
The application is saved to a NEW folder `<synthetic_dir>/appNNN` (next free id) and processed by
the same code as `python -m services.worker.pipeline --apps appNNN`, so the duplicate and
cross-institution checks see every earlier application.
"""

from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from typing import Any

from docverf.schemas import DocType, ExtractionResult, FieldValue
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from ..settings import ApiSettings

router = APIRouter(tags=["submissions"])

ALLOWED_SUFFIXES = {".pdf", ".jpg", ".jpeg", ".png"}
MAX_FILE_BYTES = 15 * 1024 * 1024
MAX_FILES = 12
NUMERIC_FIELDS = {"land_area", "built_up_area_sqm"}
# One submission at a time: ids are allocated from the folders on disk and the pipeline shares
# one ledger.
_LOCK = threading.Lock()


def _next_app_dir(settings: ApiSettings) -> tuple[str, Path]:
    """Create and return the first free `appNNN` folder (never an existing one)."""
    taken = [
        int(m.group(1))
        for parent in (settings.synthetic_dir, settings.pipeline_dir)
        if parent.is_dir()
        for p in parent.iterdir()
        if (m := re.fullmatch(r"app(\d+)(?:\.json)?", p.name))
    ]
    number = max(taken, default=0) + 1
    settings.synthetic_dir.mkdir(parents=True, exist_ok=True)
    while True:
        app_id = f"app{number:03d}"
        try:
            (settings.synthetic_dir / app_id).mkdir()  # fails if it exists
            return app_id, settings.synthetic_dir / app_id
        except FileExistsError:
            number += 1


def _form_fields(form: dict[str, Any]) -> dict[str, FieldValue]:
    fields = {}
    for key, value in form.items():
        if value is None or str(value).strip() == "":
            continue
        if key in NUMERIC_FIELDS:
            try:
                value = float(value)
            except (TypeError, ValueError) as exc:
                raise HTTPException(422, f"'{key}' must be a number") from exc
        fields[key] = FieldValue(value=value, confidence=1.0)
    return fields


def _parse(form: str, doc_types: str, files: list[UploadFile]) -> tuple[dict[str, Any], list[str]]:
    try:
        form_json = json.loads(form)
        types = json.loads(doc_types)
    except ValueError as exc:
        raise HTTPException(422, "'form' and 'doc_types' must be JSON") from exc
    if not isinstance(form_json, dict) or not form_json.get("institute_name"):
        raise HTTPException(422, "'form' must be a JSON object with an institute_name")
    valid = {t.value for t in DocType} - {DocType.APPLICATION_FORM.value}
    if not isinstance(types, list) or any(t not in valid for t in types):
        raise HTTPException(422, f"'doc_types' entries must be among {sorted(valid)}")
    if not files or len(files) != len(types):
        raise HTTPException(422, "'files' and 'doc_types' must be the same, non-zero length")
    if len(files) > MAX_FILES:
        raise HTTPException(422, f"At most {MAX_FILES} files per application")
    for upload in files:
        if Path(upload.filename or "").suffix.lower() not in ALLOWED_SUFFIXES:
            raise HTTPException(422, f"{upload.filename}: only PDF, JPG and PNG are accepted")
    return form_json, types


def _save(
    app_id: str, app_dir: Path, form: dict[str, Any], types: list[str], files: list[UploadFile]
) -> list[dict[str, str]]:
    """Write the documents, application_form.json and the manifest; return the manifest."""
    photos = types.count(DocType.LAB_PHOTO.value)
    documents = [
        {
            "doc_id": f"{app_id}_application_form",
            "doc_type": "application_form",
            "path": "application_form.json",
        }
    ]
    seen: dict[str, int] = {}
    for doc_type, upload in zip(types, files, strict=True):
        suffix = Path(upload.filename or "").suffix.lower()
        n = seen[doc_type] = seen.get(doc_type, 0) + 1
        numbered = doc_type == DocType.LAB_PHOTO.value
        name = f"{doc_type}_{n}{suffix}" if numbered else f"{doc_type}{suffix}"
        if not numbered and n > 1:
            raise HTTPException(422, f"Only one {doc_type} document is accepted")
        data = upload.file.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            raise HTTPException(422, f"{upload.filename}: larger than 15 MB")
        (app_dir / name).write_bytes(data)
        doc_id = f"{app_id}_{doc_type}" + (f"_{n}" if numbered and photos > 1 else "")
        documents.append({"doc_id": doc_id, "doc_type": doc_type, "path": name})

    form_doc = ExtractionResult(
        doc_id=f"{app_id}_application_form",
        app_id=app_id,
        doc_type=DocType.APPLICATION_FORM,
        fields=_form_fields(form),
    )
    (app_dir / "application_form.json").write_text(form_doc.model_dump_json(indent=2), "utf-8")
    # Same shape as the synthetic dataset's ground_truth.json, with nothing known about the truth.
    manifest = {"app_id": app_id, "documents": documents, "true_fields": {}, "injected_defects": []}
    (app_dir / "ground_truth.json").write_text(json.dumps(manifest, indent=2), "utf-8")
    return documents


@router.post("/submissions")
def submit_application(
    request: Request,
    form: str = Form(...),
    doc_types: str = Form(...),
    files: list[UploadFile] = File(...),  # noqa: B008
) -> dict[str, Any]:
    settings: ApiSettings = request.app.state.settings
    form_json, types = _parse(form, doc_types, files)

    from docverf.config import get_settings

    from services.worker.pipeline import _issuer_up, run  # heavy imports, only when needed

    with _LOCK:
        app_id, app_dir = _next_app_dir(settings)
        start = time.perf_counter()
        try:
            _save(app_id, app_dir, form_json, types, files)
            url = get_settings().MOCK_ISSUER_URL
            issuer = {"url": url, "reachable": _issuer_up(url), "started_by_pipeline": False}
            if run(settings.synthetic_dir, settings.pipeline_dir, [app_id], issuer) != 0:
                raise RuntimeError("the pipeline failed for this application (see the API log)")
            result = request.app.state.pipelines.load(app_id).data
        except Exception as exc:
            # Keep the saved files for inspection, but take the application out of the dataset.
            manifest = app_dir / "ground_truth.json"
            if manifest.exists():
                manifest.rename(app_dir / "ground_truth.failed.json")
            if isinstance(exc, HTTPException):
                raise
            raise HTTPException(500, f"Processing failed: {exc}") from exc
    return {
        "app_id": app_id,
        "priority": result.priority,
        "findings_count": len(result.findings),
        "status": "review_pending",
        "seconds": round(time.perf_counter() - start, 1),
    }

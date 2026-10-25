"""Build officer-facing views over validated pipeline output.

These helpers deliberately derive only presentation metadata (file name, URL, counts,
sort order) from the filesystem.  Findings, severities, document statuses and priority
remain exactly as the pipeline emitted them.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

from docverf.schemas import DocumentStatus, Finding, Severity

from .pipeline import LoadedApplication
from .settings import ApiSettings
from .store import OfficerStore

PREVIEWABLE_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg"}
SAFE_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SEVERITY_ORDER = {
    Severity.HIGH.value: 0,
    Severity.MEDIUM.value: 1,
    Severity.LOW.value: 2,
    Severity.INFO.value: 3,
}
DOC_ORDER = {"flagged": 0, "manual_review_required": 1, "no_issues": 2}


def finding_counts(findings: list[Finding]) -> dict[str, int]:
    counts = {"total": len(findings), "high": 0, "medium": 0, "low": 0, "info": 0}
    for finding in findings:
        counts[finding.severity.value] += 1
    return counts


def _field_value(application: LoadedApplication, field_name: str, doc_type: str) -> Any:
    ordered = sorted(
        application.data.extractions,
        key=lambda extraction: extraction.doc_type.value != doc_type,
    )
    for extraction in ordered:
        field = extraction.fields.get(field_name)
        if field is not None and field.value is not None:
            return field.value
    return None


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def document_index(settings: ApiSettings, app_id: str) -> dict[str, Path]:
    """Map `doc_id` -> document file for the application folder.

    The pipeline contract stores `DocumentStatus` (which has no file name), while the
    synthetic-data contract uses `{doc_type}.pdf` / `{doc_type}.json` names.  This is the
    only place that bridges the two conventions.
    """

    app_dir = settings.synthetic_dir / app_id
    if not app_dir.is_dir():
        return {}

    index: dict[str, Path] = {}
    for path in sorted(app_dir.iterdir()):
        if (
            not path.is_file()
            or path.name.startswith(".")
            or not SAFE_FILENAME.fullmatch(path.name)
        ):
            continue
        stem = path.stem
        doc_id = stem if stem.startswith(f"{app_id}_") else f"{app_id}_{stem}"
        current = index.get(doc_id)
        if current is None or (
            path.suffix.lower() in PREVIEWABLE_SUFFIXES
            and current.suffix.lower() not in PREVIEWABLE_SUFFIXES
        ):
            index[doc_id] = path

    # The synthetic manifest numbers photos only when an application has several: a lone
    # lab_photo_1.jpg is the document `{app_id}_lab_photo`. Resolve it under both names.
    numbered: dict[str, list[str]] = {}
    for doc_id in index:
        if match := re.fullmatch(r"(.+)_\d+", doc_id):
            numbered.setdefault(match.group(1), []).append(doc_id)
    for base, doc_ids in numbered.items():
        if len(doc_ids) == 1 and base not in index:
            index[base] = index[doc_ids[0]]
    return index


def _infer_doc_type(app_id: str, doc_id: str) -> str | None:
    base = doc_id[len(app_id) + 1 :] if doc_id.startswith(f"{app_id}_") else doc_id
    base = re.sub(r"_\d+$", "", base)
    known = {
        "application_form",
        "land_deed",
        "noc",
        "affidavit",
        "accreditation_cert",
        "lab_photo",
    }
    return base if base in known else None


def _max_severity(findings: list[Finding]) -> str | None:
    if not findings:
        return None
    return min(findings, key=lambda finding: SEVERITY_ORDER[finding.severity.value]).severity.value


def _serialize_document(
    status: DocumentStatus,
    app_id: str,
    extraction_types: dict[str, str],
    files: dict[str, Path],
) -> dict[str, Any]:
    path = files.get(status.doc_id)
    filename = path.name if path else None
    previewable = bool(path and path.suffix.lower() in PREVIEWABLE_SUFFIXES)
    payload = status.model_dump(mode="json")
    payload.update(
        {
            "doc_type": extraction_types.get(status.doc_id)
            or _infer_doc_type(app_id, status.doc_id),
            "filename": filename,
            "file_url": f"/v1/files/{app_id}/{quote(filename)}" if filename else None,
            "previewable": previewable,
        }
    )
    return payload


def build_documents(
    application: LoadedApplication, settings: ApiSettings, store: OfficerStore
) -> list[dict[str, Any]]:
    data = application.data
    findings_by_id = {finding.finding_id: finding for finding in data.findings}
    extraction_types = {
        extraction.doc_id: extraction.doc_type.value for extraction in data.extractions
    }
    files = document_index(settings, data.app_id)

    documents: list[dict[str, Any]] = []
    for status in data.documents:
        payload = _serialize_document(status, data.app_id, extraction_types, files)
        linked = [
            findings_by_id[finding_id]
            for finding_id in status.finding_ids
            if finding_id in findings_by_id
        ]
        payload["high_findings"] = sum(1 for finding in linked if finding.severity == Severity.HIGH)
        payload["max_severity"] = _max_severity(linked)
        documents.append(payload)

    documents.sort(
        key=lambda document: (
            DOC_ORDER.get(document["overall"], 9),
            -document["high_findings"],
            SEVERITY_ORDER.get(document["max_severity"], 9),
            document["doc_id"],
        )
    )
    return documents


def serialize_finding(finding: Finding, action: dict[str, Any] | None) -> dict[str, Any]:
    payload = finding.model_dump(mode="json")
    payload["officer_action"] = action
    return payload


def build_findings(application: LoadedApplication, store: OfficerStore) -> list[dict[str, Any]]:
    actions = store.latest_actions_for_app(application.data.app_id)
    findings = [
        serialize_finding(finding, actions.get(finding.finding_id))
        for finding in application.data.findings
    ]
    findings.sort(
        key=lambda finding: (
            SEVERITY_ORDER.get(finding["severity"], 9),
            finding["rule_id"] or "",
            finding["finding_id"],
        )
    )
    return findings


def build_summary(application: LoadedApplication, store: OfficerStore) -> dict[str, Any]:
    data = application.data
    actions = store.latest_actions_for_app(data.app_id)
    high_pending = sum(
        1
        for finding in data.findings
        if finding.severity == Severity.HIGH and finding.finding_id not in actions
    )
    decision = store.latest_decision(data.app_id)
    counts = finding_counts(data.findings)
    document_counts = {
        "total": len(data.documents),
        "flagged": sum(1 for doc in data.documents if doc.overall.value == "flagged"),
        "manual_review": sum(
            1 for doc in data.documents if doc.overall.value == "manual_review_required"
        ),
        "no_issues": sum(1 for doc in data.documents if doc.overall.value == "no_issues"),
    }
    return {
        "app_id": data.app_id,
        "institute_name": _string_or_none(
            _field_value(application, "institute_name", "application_form")
        ),
        "application_no": _string_or_none(
            _field_value(application, "application_no", "application_form")
        ),
        "status": "decided" if decision else "review_pending",
        "priority": data.priority,
        "finding_counts": counts,
        "document_counts": document_counts,
        "checks_count": len(data.checks),
        "high_pending": high_pending,
        "decision_allowed": high_pending == 0,
        "decision": decision,
        "audit": data.audit.model_dump(mode="json") if data.audit else None,
        "meta": data.meta,
    }


def build_queue(applications: list[LoadedApplication], store: OfficerStore) -> list[dict[str, Any]]:
    queue = [build_summary(application, store) for application in applications]
    queue.sort(
        key=lambda item: (
            -item["priority"],
            -item["high_pending"],
            item["app_id"],
        )
    )
    return queue


def build_detail(
    application: LoadedApplication, settings: ApiSettings, store: OfficerStore
) -> dict[str, Any]:
    summary = build_summary(application, store)
    summary["documents"] = build_documents(application, settings, store)
    summary["findings"] = build_findings(application, store)
    return summary

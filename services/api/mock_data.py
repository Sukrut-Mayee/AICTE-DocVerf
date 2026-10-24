"""Seed a contract-shaped mock pipeline result from the `app_conflict` fixture.

This is development data only.  The findings reproduce the expected outcomes documented
in TRD Appendix A; no extraction, provenance, issuer or reasoning module was re-run.
`meta.source == "mock_fixture"` marks the file so the API/UI can label it honestly and
the seed script will not overwrite real pipeline output.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from docverf.schemas import (
    AuthorityTier,
    Claim,
    DocOverallStatus,
    DocumentStatus,
    ExtractionResult,
    Finding,
    FindingType,
    Layer,
    Severity,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "apps" / "app_conflict"
APP_ID = "app001"
MOCK_SOURCE = "mock_fixture"

NOC_BOXES = {
    "issuer": [0.10, 0.12, 0.80, 0.155],
    "institute_name": [0.10, 0.18, 0.80, 0.215],
    "ref_no": [0.10, 0.24, 0.62, 0.275],
    "issue_date": [0.10, 0.30, 0.42, 0.335],
    "valid_until": [0.10, 0.36, 0.42, 0.395],
}
AFFIDAVIT_BOXES = {
    "institute_name": [0.10, 0.16, 0.80, 0.195],
    "application_no": [0.10, 0.22, 0.62, 0.255],
    "date": [0.10, 0.28, 0.42, 0.315],
    "land_area_declared": [0.10, 0.34, 0.55, 0.375],
}
AFFIDAVIT_BOX = AFFIDAVIT_BOXES["land_area_declared"]


def _load_extraction(name: str) -> ExtractionResult:
    raw = json.loads((FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8"))
    raw = copy.deepcopy(raw)
    raw["app_id"] = APP_ID
    raw["doc_id"] = f"{APP_ID}_{name}"
    raw["warnings"] = [
        "Mock fixture seeded from tests/fixtures/apps/app_conflict; "
        "not produced by a live extraction run."
    ]
    if name == "noc":
        for field_name, bbox in NOC_BOXES.items():
            raw["fields"][field_name].update({"page": 1, "bbox": bbox})
    if name == "affidavit":
        for field_name, bbox in AFFIDAVIT_BOXES.items():
            raw["fields"][field_name].update({"page": 1, "bbox": bbox})
    return ExtractionResult.model_validate(raw)


def _claim(
    doc_type: str,
    entity: str,
    attribute: str,
    value: Any,
    authority: AuthorityTier,
    confidence: float,
    *,
    page: int | None = None,
    bbox: list[float] | None = None,
) -> Claim:
    return Claim(
        doc_id=f"{APP_ID}_{doc_type}",
        entity=entity,
        attribute=attribute,
        value=value,
        authority=authority,
        confidence=confidence,
        page=page,
        bbox=bbox,
    )


def _findings() -> list[Finding]:
    parcel = "land_parcel:45/2"
    trust = "trust:E-12345/PUNE"

    area = Finding(
        finding_id="f_1a2b3c4d",
        app_id=APP_ID,
        type=FindingType.ATTRIBUTE_CONFLICT,
        severity=Severity.HIGH,
        layer=Layer.B,
        rule_id="LAND_AREA_AGREE",
        entity=parcel,
        attribute="area",
        claims=[
            _claim(
                "application_form",
                parcel,
                "area",
                2.5,
                AuthorityTier.SELF_DECLARED,
                1.0,
            ),
            _claim(
                "land_deed",
                parcel,
                "area",
                2.1,
                AuthorityTier.THIRD_PARTY,
                0.93,
                page=1,
                bbox=[0.12, 0.41, 0.35, 0.44],
            ),
        ],
        doc_ids=[f"{APP_ID}_application_form", f"{APP_ID}_land_deed"],
        message="Declared land area (2.5 acre) conflicts with the land deed (2.1 acre).",
        evidence={
            "rule": "LAND_AREA_AGREE",
            "attribute": "land_parcel.area",
            "values": {"application_form": 2.5, "land_deed": 2.1},
            "unit": "acre",
        },
    )

    owner = Finding(
        finding_id="f_2b3c4d5e",
        app_id=APP_ID,
        type=FindingType.RELATIONSHIP_VIOLATION,
        severity=Severity.HIGH,
        layer=Layer.B,
        rule_id="OWNER_IS_TRUST",
        entity=parcel,
        attribute="owner",
        claims=[
            _claim(
                "application_form",
                trust,
                "name",
                "Shree Vidya Education Trust",
                AuthorityTier.SELF_DECLARED,
                1.0,
            ),
            _claim(
                "land_deed",
                parcel,
                "owner",
                "Shree Vidya Charitable Society",
                AuthorityTier.THIRD_PARTY,
                0.88,
                page=1,
                bbox=[0.12, 0.30, 0.70, 0.34],
            ),
        ],
        doc_ids=[f"{APP_ID}_application_form", f"{APP_ID}_land_deed"],
        message=(
            "The land deed owner (Shree Vidya Charitable Society) does not match "
            "the trust name on the application (Shree Vidya Education Trust)."
        ),
        evidence={
            "rule": "OWNER_IS_TRUST",
            "attribute": "land_parcel.owner",
            "values": {
                "application_form.trust_name": "Shree Vidya Education Trust",
                "land_deed.owner_name": "Shree Vidya Charitable Society",
            },
        },
    )

    timeline = Finding(
        finding_id="f_3c4d5e6f",
        app_id=APP_ID,
        type=FindingType.TIMELINE_VIOLATION,
        severity=Severity.HIGH,
        layer=Layer.B,
        rule_id="TL_NOC_AFTER_TRUST",
        entity=trust,
        attribute="reg_date",
        claims=[
            _claim(
                "application_form",
                trust,
                "reg_date",
                "2009-04-15",
                AuthorityTier.SELF_DECLARED,
                1.0,
            ),
            _claim(
                "noc",
                trust,
                "noc_issue_date",
                "2008-06-10",
                AuthorityTier.THIRD_PARTY,
                0.90,
                page=1,
                bbox=NOC_BOXES["issue_date"],
            ),
        ],
        doc_ids=[f"{APP_ID}_application_form", f"{APP_ID}_noc"],
        message="The fire NOC was issued before the trust was registered.",
        evidence={
            "rule": "TL_NOC_AFTER_TRUST",
            "events": {
                "noc.issue_date": "2008-06-10",
                "trust.reg_date": "2009-04-15",
            },
        },
    )

    expired = Finding(
        finding_id="f_4d5e6f70",
        app_id=APP_ID,
        type=FindingType.EXPIRED,
        severity=Severity.HIGH,
        layer=Layer.B,
        rule_id="NOC_VALID_FOR_YEAR",
        entity=trust,
        attribute="noc_valid_until",
        claims=[
            _claim(
                "noc",
                trust,
                "noc_valid_until",
                "2027-12-31",
                AuthorityTier.THIRD_PARTY,
                0.90,
                page=1,
                bbox=NOC_BOXES["valid_until"],
            )
        ],
        doc_ids=[f"{APP_ID}_noc"],
        message="The fire NOC expires before the end of the 2027-28 academic year.",
        evidence={
            "rule": "NOC_VALID_FOR_YEAR",
            "valid_until": "2027-12-31",
            "academic_year_end": "2028-06-30",
        },
    )

    unreadable = Finding(
        finding_id="f_5e6f7081",
        app_id=APP_ID,
        type=FindingType.UNREADABLE,
        severity=Severity.LOW,
        rule_id=None,
        entity=parcel,
        attribute="area",
        claims=[
            _claim(
                "affidavit",
                parcel,
                "area",
                2.5,
                AuthorityTier.SELF_DECLARED,
                0.62,
                page=1,
                bbox=AFFIDAVIT_BOX,
            )
        ],
        doc_ids=[f"{APP_ID}_affidavit"],
        message=("The land area in the affidavit is low-confidence; confirm the value manually."),
        evidence={
            "reason": "extractors_disagree",
            "confidence": 0.62,
            "confidence_threshold": 0.75,
        },
    )

    return [area, owner, timeline, expired, unreadable]


def _documents() -> list[DocumentStatus]:
    return [
        DocumentStatus(
            doc_id=f"{APP_ID}_application_form",
            overall=DocOverallStatus.FLAGGED,
            note="Land-area and trust-name conflicts involve this form.",
            finding_ids=["f_1a2b3c4d", "f_2b3c4d5e", "f_3c4d5e6f"],
        ),
        DocumentStatus(
            doc_id=f"{APP_ID}_land_deed",
            overall=DocOverallStatus.FLAGGED,
            note="Deed area and owner conflict with the application.",
            finding_ids=["f_1a2b3c4d", "f_2b3c4d5e"],
        ),
        DocumentStatus(
            doc_id=f"{APP_ID}_noc",
            overall=DocOverallStatus.FLAGGED,
            note=(
                "NOC was issued before trust registration and expires before "
                "the academic year ends."
            ),
            finding_ids=["f_3c4d5e6f", "f_4d5e6f70"],
        ),
        DocumentStatus(
            doc_id=f"{APP_ID}_affidavit",
            overall=DocOverallStatus.MANUAL_REVIEW_REQUIRED,
            note="Land area is low-confidence; confirm manually.",
            finding_ids=["f_5e6f7081"],
        ),
    ]


def build_mock_app001() -> dict[str, Any]:
    findings = _findings()
    documents = _documents()
    extractions = [
        _load_extraction(name)
        for name in (
            "application_form",
            "land_deed",
            "noc",
            "affidavit",
        )
    ]
    high = sum(1 for finding in findings if finding.severity == Severity.HIGH)
    medium = sum(1 for finding in findings if finding.severity == Severity.MEDIUM)
    low = sum(1 for finding in findings if finding.severity == Severity.LOW)
    priority = 100 * high + 10 * medium + low

    payload: dict[str, Any] = {
        "app_id": APP_ID,
        "extractions": [extraction.model_dump(mode="json") for extraction in extractions],
        "checks": [],
        "findings": [finding.model_dump(mode="json") for finding in findings],
        "documents": [document.model_dump(mode="json") for document in documents],
        "priority": priority,
        "audit": {
            "seq": 0,
            "hash": hashlib.sha256(b"mock app001 pipeline fixture").hexdigest(),
            "tx": None,
        },
        "meta": {
            "source": MOCK_SOURCE,
            "fixture": "tests/fixtures/apps/app_conflict",
            "note": (
                "Hand-built from the TRD Appendix A expected findings. "
                "Extraction, checks, reasoning and anchoring were not re-run."
            ),
            "seeded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        },
    }
    return payload


def write_mock_app001(path: Path, *, force: bool = False) -> bool:
    """Write the mock JSON unless a non-mock pipeline result already exists."""

    if path.exists() and not force:
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}
        if existing.get("meta", {}).get("source") != MOCK_SOURCE:
            return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_mock_app001(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return True

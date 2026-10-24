"""TRD §5.2 models. Frozen contract: do not change field names or types without lead approval."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from .enums import (
    AuthorityTier,
    CheckStatus,
    DocOverallStatus,
    DocType,
    FindingType,
    Layer,
    Severity,
    VerificationStatus,
)

# normalized [x1, y1, x2, y2] in 0..1 relative to page width/height; origin top-left
BBox = list[float]


class FieldValue(BaseModel):
    value: Any  # normalized value (ISO date string, float, str, list)
    unit: str | None = None  # e.g. "acre", "sqm"
    raw: str | None = None  # text exactly as read
    confidence: float = Field(ge=0, le=1)
    page: int | None = None  # 1-based
    bbox: BBox | None = None
    extractor_agreement: bool | None = None


class Region(BaseModel):
    type: Literal["signature", "seal", "qr", "photo", "table", "text_block"]
    page: int
    bbox: BBox
    score: float | None = None


class ExtractionResult(BaseModel):
    doc_id: str
    app_id: str
    doc_type: DocType
    fields: dict[str, FieldValue]
    regions: list[Region] = []
    page_count: int = 1
    engines: dict[str, str] = {}  # {"ocr": "paddleocr", "vlm": "<model>"}
    warnings: list[str] = []


class CheckResult(BaseModel):
    doc_id: str
    layer: Layer
    check: Literal[
        "pdf_signature",
        "qr",
        "hash_duplicate",
        "metadata",
        "template",
        "ref_format",
        "ela",
        "copy_move",
        "noise",
        "ai_gen",
        "issuer_lookup",
    ]
    status: CheckStatus
    severity: Severity
    reason: str
    # e.g. {"heatmap_path": ..., "bbox": ..., "page": 1, "signer": ..., "details": {...}}
    evidence: dict[str, Any] = {}
    # set for pdf_signature / qr / issuer_lookup
    verification_status: VerificationStatus | None = None
    source: str | None = None  # e.g. "mock_issuer:fire_dept"
    checked_at: datetime


class Claim(BaseModel):
    doc_id: str
    entity: str  # entity ID, see TRD §8.1
    attribute: str
    value: Any
    authority: AuthorityTier
    confidence: float
    page: int | None = None
    bbox: BBox | None = None


class Finding(BaseModel):
    finding_id: str  # "f_" + short uuid
    app_id: str
    type: FindingType
    severity: Severity
    layer: Layer | None = None
    rule_id: str | None = None
    entity: str | None = None
    attribute: str | None = None
    claims: list[Claim] = []
    doc_ids: list[str] = []  # documents to highlight
    message: str  # one plain-English sentence for the officer
    evidence: dict[str, Any] = {}


class DocumentStatus(BaseModel):
    doc_id: str
    overall: DocOverallStatus
    verification: VerificationStatus | None = None
    note: str  # short summary shown above the document in the UI
    finding_ids: list[str] = []


class AuditEntry(BaseModel):
    seq: int
    ts: datetime
    event_type: str  # "finding_created", "check_result", "flag_action", "decision", "anchor"
    payload_hash: str  # sha256 hex of canonical JSON payload
    prev_hash: str  # "0"*64 for seq 0
    hash: str  # sha256(prev_hash + str(seq) + ts.isoformat() + event_type + payload_hash)


class InjectedDefect(BaseModel):
    doc_id: str
    defect: str  # code from TRD §13.2
    detail: str


class GroundTruthDoc(BaseModel):
    doc_id: str
    doc_type: DocType
    path: str  # relative to the application folder


class GroundTruth(BaseModel):
    app_id: str
    documents: list[GroundTruthDoc]
    true_fields: dict[str, dict[str, Any]]  # doc_id -> field -> true normalized value
    injected_defects: list[InjectedDefect] = []

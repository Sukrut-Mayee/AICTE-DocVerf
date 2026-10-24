# TRD — AICTE DocVerf

**Version:** 0.2 (adds §19 resolved questions) · **Date:** 2026-10-24 · **Owner:** Sukrut Mayee (team lead)
**Repo:** https://github.com/Sukrut-Mayee/AICTE-DocVerf
**Companion doc:** `docs/PRD.md` (what and why)

> **For AI coding agents — read §1 before writing any code.** This document is the technical source of truth. The schemas in §5 are frozen contracts. If something is ambiguous or missing, leave a `TODO(question):` comment and tell the human; do not invent new contracts.

---

## 1. Rules for AI coding agents

1. **Contracts are frozen.** `packages/docverf/schemas/` implements §5 exactly. Never change a schema field name, type or enum value without the team lead's approval.
2. **Lean code.** No abstraction without a second use. If it works in fewer lines, use fewer lines. No speculative features.
3. **Stay in your module.** Only edit files in the module you were asked to work on, plus its tests. Shared code goes through the team lead.
4. **No new dependencies silently.** If you add a package, add it (pinned) to the right `requirements/*.txt` file and mention it in your summary.
5. **Pure functions where possible.** Modules in `packages/docverf/` take inputs and return schema objects. Only `verification/` and `ledger/` may make network calls. Only `services/` touch the queue and object storage. Databases: `services/` own the main tables; `ledger/` is the one exception and owns the `audit_log` and `anchors` tables through its own store (see §19).
6. **Config from env.** Read thresholds, URLs and paths from environment variables via `docverf.config` (§15). Rule values come from YAML in `rules/`.
7. **Every module has a CLI** (`python -m docverf.<module> ...`) that runs on a file or folder and writes schema-valid JSON to `data/out/<module>/`.
8. **Tests.** Add pytest tests using fixtures in `tests/fixtures/`. A module is not done until its tests pass and its output validates against the schemas.
9. **Never call external AI APIs** with document content unless `ALLOW_CLOUD_AI=true`.
10. **Never label anything "forged" or "fake"** in code, messages or UI. Use "suspicious", "conflict", "preliminary indicator".

---

## 2. System overview

Six layers. AI models only perceive; deterministic code reasons; the trust layer proves.

```
Clients            Next.js officer UI · mock institute portal · digital twin · capture PWA (P2)
API/orchestration  FastAPI (REST, RBAC) · Celery + Redis (DAG) · alerts
AI perception      OCR (PaddleOCR/Surya) · CNN models (layout, region YOLO, forensics) · VLM (Ollama/vLLM) · AI-gen detector
Reasoning          Rule engine (YAML) · entity graph · timeline engine · impact simulator
Trust              Provenance (pyHanko, QR, hashes, metadata) · issuer connectors · hash-chained audit log
Data/ledger        PostgreSQL · MinIO (encrypted) · Hyperledger Besu (anchors)
```

Integration: the AICTE portal (mock in prototype) calls our REST API and receives a webhook on completion. We never depend on AICTE's internal stack.

---

## 3. Tech stack

| Area | Choice |
|---|---|
| Language (backend/AI) | Python 3.11 |
| API | FastAPI, Pydantic v2, Uvicorn |
| Queue / DAG | Celery + Redis (`chain`, `group`, `chord`) |
| DB | PostgreSQL + SQLAlchemy 2 + Alembic |
| Object storage | MinIO (S3-compatible, server-side encryption) |
| Auth | Simple JWT with roles for prototype; Keycloak-ready (P2) |
| OCR | PaddleOCR or Surya (decided by benchmark; set via `OCR_ENGINE`) |
| Layout / regions | DocLayout-YOLO or PP-Structure; YOLO fine-tuned for signature/seal/QR (later) |
| VLM | Small Qwen-VL-family instruct model via Ollama (default) or vLLM |
| PDF/image | PyMuPDF, pdf2image, Pillow, OpenCV |
| Normalization | dateparser, pint, rapidfuzz, indic-transliteration |
| Provenance | pyHanko, pikepdf, pyexiftool, imagehash, zxing-cpp (fallback pyzbar) |
| Forensics | OpenCV, NumPy, scikit-image; TruFor/CAT-Net optional |
| Graph | NetworkX (in memory) + Postgres tables |
| Blockchain | Hyperledger Besu dev node (Docker), Solidity + Hardhat, web3.py |
| Frontend | Next.js (App Router), TypeScript, Tailwind, shadcn/ui, react-pdf (PDF.js), Cytoscape.js, vis-timeline |
| Synthetic data | Faker (en_IN), Jinja2, Playwright (PDF render; WeasyPrint optional), Augraphy |
| Dev mail | MailHog |
| Tooling | ruff, mypy (lenient), pytest, pre-commit, GitHub Actions |
| Runtime | Docker Compose |

**Windows note:** PaddleOCR, WeasyPrint and ExifTool can be painful on native Windows. Prefer WSL2 or the Docker images for those modules. Playwright works natively.

---

## 4. Repository structure

```
AICTE-DocVerf/
├─ docs/                    PRD.md, TRD.md
├─ CLAUDE.md / AGENTS.md    short agent guide pointing to docs/TRD.md §1
├─ apps/
│  ├─ web/                  Next.js: (officer) and (portal) route groups
│  └─ capture-pwa/          placeholder (P2)
├─ services/
│  ├─ api/                  FastAPI app (routers, db models, auth)
│  ├─ worker/               Celery app + pipeline DAG
│  └─ mock_issuer/          FastAPI mock issuer + mock AICTE records
├─ packages/docverf/        single installable Python package (pip install -e .)
│  ├─ config.py
│  ├─ schemas/              §5 Pydantic models (frozen contracts)
│  ├─ provenance/           hashing, pdf_signature, qr, metadata, duplicates
│  ├─ extraction/           ocr, layout, vlm, rules_extractor, confidence, normalize, classify, extract
│  ├─ forensics/            ela, copy_move, noise, ai_gen
│  ├─ reasoning/            rule_engine, entity_resolution, entity_graph, timeline, impact_sim, run
│  ├─ verification/         connectors/base.py, connectors/mock.py
│  ├─ ledger/               audit_log, anchor
│  └─ synthetic/            templates/, generate, defects, scan_effects
├─ rules/                   checklists/eoa.yaml · rules/*.yaml · graph/*.yaml · timeline/*.yaml
├─ blockchain/              Hardhat project: contracts/AuditAnchor.sol, scripts/deploy.ts
├─ data/                    gitignored: synthetic/, samples/, out/
├─ eval/                    metrics.py, report
├─ infra/                   docker-compose.yml, besu/
├─ requirements/            base, extraction, provenance, forensics, reasoning, ledger, synthetic, dev
├─ tests/                   mirrors packages/docverf; fixtures/
├─ .env.example · Makefile · pyproject.toml · README.md
```

Import style: `from docverf.schemas import ExtractionResult`. The single `docverf` package avoids name collisions (`extraction`, `ledger` are generic names).

---

## 5. Data contracts (frozen)

### 5.1 Enums

```python
class DocType(str, Enum):
    APPLICATION_FORM = "application_form"
    LAND_DEED = "land_deed"
    NOC = "noc"
    AFFIDAVIT = "affidavit"
    ACCREDITATION_CERT = "accreditation_cert"
    LAB_PHOTO = "lab_photo"

class Layer(str, Enum):
    A = "A"  # provenance / source verification
    B = "B"  # consistency (graph, history, cross-institution, timeline)
    C = "C"  # template / structure / format
    D = "D"  # pixel forensics + metadata
    E = "E"  # AI-generation signal

class CheckStatus(str, Enum):
    VERIFIED = "verified"; MISMATCH = "mismatch"; SUSPICIOUS = "suspicious"
    CLEAN = "clean"; NOT_APPLICABLE = "not_applicable"; ERROR = "error"

class Severity(str, Enum):
    HIGH = "high"; MEDIUM = "medium"; LOW = "low"; INFO = "info"

class AuthorityTier(str, Enum):
    ISSUER_VERIFIED = "issuer_verified"; THIRD_PARTY = "third_party"; SELF_DECLARED = "self_declared"

class VerificationStatus(str, Enum):   # problem statement's six statuses
    VERIFIED = "verified"; MISMATCH_DETECTED = "mismatch_detected"; EXPIRED = "expired"
    VERIFICATION_PENDING = "verification_pending"; SOURCE_UNAVAILABLE = "source_unavailable"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"

class FindingType(str, Enum):
    ATTRIBUTE_CONFLICT = "attribute_conflict"
    RELATIONSHIP_VIOLATION = "relationship_violation"
    TIMELINE_VIOLATION = "timeline_violation"
    RULE_FAILED = "rule_failed"
    MISSING_DOC = "missing_doc"
    EXPIRED = "expired"
    UNREADABLE = "unreadable"              # low-confidence data; confirm manually
    UNDETERMINED = "undetermined"          # not enough evidence to evaluate
    DUPLICATE = "duplicate"
    FORENSIC_SIGNAL = "forensic_signal"
    PROVENANCE_FAILURE = "provenance_failure"
    SOURCE_MISMATCH = "source_mismatch"

class RuleOutcome(str, Enum):
    PASS = "pass"; FAIL = "fail"; UNDETERMINED = "undetermined"

class DocOverallStatus(str, Enum):
    NO_ISSUES = "no_issues"; FLAGGED = "flagged"; MANUAL_REVIEW_REQUIRED = "manual_review_required"

class Decision(str, Enum):
    APPROVE = "approve"; APPROVE_WITH_DEFICIENCIES = "approve_with_deficiencies"
    REQUEST_RECTIFICATION = "request_rectification"; SITE_INSPECTION = "site_inspection"; REJECT = "reject"
```

### 5.2 Models

```python
BBox = list[float]  # normalized [x1, y1, x2, y2] in 0..1 relative to page width/height; origin top-left

class FieldValue(BaseModel):
    value: Any                      # normalized value (ISO date string, float, str, list)
    unit: str | None = None         # e.g. "acre", "sqm"
    raw: str | None = None          # text exactly as read
    confidence: float = Field(ge=0, le=1)
    page: int | None = None         # 1-based
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
    engines: dict[str, str] = {}    # {"ocr": "paddleocr", "vlm": "<model>"}
    warnings: list[str] = []

class CheckResult(BaseModel):
    doc_id: str
    layer: Layer
    check: Literal["pdf_signature", "qr", "hash_duplicate", "metadata", "template",
                   "ref_format", "ela", "copy_move", "noise", "ai_gen", "issuer_lookup"]
    status: CheckStatus
    severity: Severity
    reason: str
    evidence: dict[str, Any] = {}   # e.g. {"heatmap_path": ..., "bbox": ..., "page": 1, "signer": ..., "details": {...}}
    verification_status: VerificationStatus | None = None   # set for pdf_signature / qr / issuer_lookup
    source: str | None = None       # e.g. "mock_issuer:fire_dept"
    checked_at: datetime

class Claim(BaseModel):
    doc_id: str
    entity: str                     # entity ID, see §8.1
    attribute: str
    value: Any
    authority: AuthorityTier
    confidence: float
    page: int | None = None
    bbox: BBox | None = None

class Finding(BaseModel):
    finding_id: str                 # "f_" + short uuid
    app_id: str
    type: FindingType
    severity: Severity
    layer: Layer | None = None
    rule_id: str | None = None
    entity: str | None = None
    attribute: str | None = None
    claims: list[Claim] = []
    doc_ids: list[str] = []         # documents to highlight
    message: str                    # one plain-English sentence for the officer
    evidence: dict[str, Any] = {}

class DocumentStatus(BaseModel):
    doc_id: str
    overall: DocOverallStatus
    verification: VerificationStatus | None = None
    note: str                       # short summary shown above the document in the UI
    finding_ids: list[str] = []

class AuditEntry(BaseModel):
    seq: int
    ts: datetime
    event_type: str                 # "finding_created", "check_result", "flag_action", "decision", "anchor"
    payload_hash: str               # sha256 hex of canonical JSON payload
    prev_hash: str                  # "0"*64 for seq 0
    hash: str                       # sha256(prev_hash + str(seq) + ts.isoformat() + event_type + payload_hash)

class InjectedDefect(BaseModel):
    doc_id: str
    defect: str                     # code from §13.2
    detail: str

class GroundTruthDoc(BaseModel):
    doc_id: str
    doc_type: DocType
    path: str                       # relative to the application folder

class GroundTruth(BaseModel):
    app_id: str
    documents: list[GroundTruthDoc]
    true_fields: dict[str, dict[str, Any]]   # doc_id -> field -> true normalized value
    injected_defects: list[InjectedDefect] = []
```

### 5.3 ID conventions
- `app_id`: `app001`, `app002`, …
- `doc_id`: `{app_id}_{doc_type}`; multiple of one type: `{app_id}_{doc_type}_{n}` (e.g. `app001_lab_photo_2`).
- `finding_id`: `f_` + 8-char uuid.

---

## 6. Document types and fields

| doc_type | Field | Type | Notes |
|---|---|---|---|
| **application_form** (JSON, no OCR, confidence = 1.0) | institute_name | str | |
| | aicte_permanent_id | str | e.g. `1-1234567` |
| | application_no | str | |
| | trust_name | str | |
| | trust_reg_no | str | strong ID |
| | trust_reg_date | date | |
| | address | str | |
| | land_survey_no | str | strong ID |
| | land_area | float + unit | |
| | built_up_area_sqm | float | |
| | programs | list[{name, intake}] | |
| | principal_name | str | |
| | application_date | date | |
| | ter_txn_id | str | |
| **land_deed** | owner_name | str | |
| | survey_no | str | |
| | area | float + unit | may be in Marathi/Hindi |
| | village, district | str | |
| | registration_no | str | |
| | registration_date | date | |
| | mortgage_status | str | normalized: `none` / `mortgaged` |
| **noc** | issuer | str | |
| | ref_no | str | format per issuer, e.g. `FIRE/MH/2026/123456` |
| | institute_name | str | |
| | purpose | str | |
| | issue_date | date | |
| | valid_until | date | |
| | signatory | str | |
| **affidavit** | deponent_name | str | |
| | institute_name | str | |
| | application_no | str | |
| | date | date | |
| | land_area_declared | float + unit | |
| | notary_reg_no | str | |
| **accreditation_cert** | body | str | e.g. NBA |
| | cert_no | str | |
| | institute_name | str | |
| | programs | list[str] | |
| | valid_from, valid_to | date | |
| **lab_photo** | room_label | str | |
| | capture_date | date | from EXIF if present |
| | equipment_count | int | VLM count; advisory |

**Default authority tier by doc type:** `application_form`, `affidavit`, `lab_photo` → `self_declared`; `land_deed`, `noc`, `accreditation_cert` → `third_party`. Upgraded to `issuer_verified` when the document has a verified `pdf_signature`, `qr` or `issuer_lookup` check.

---

## 7. Pipeline

### 7.1 Stages
| Stage | What | Module |
|---|---|---|
| 0 Intake | Store files, load checklist, fetch mock AICTE records (TER, approved intake) | services/api, worker |
| 1 Provenance | hashes, PDF signature, QR, metadata (raw bytes only) | provenance |
| 2 Understanding | quality → classify → layout/regions → OCR → 2 extractors → confidence → normalize | extraction |
| 3 Graphs | entity resolution → claims → entity graph, timeline events, evidence DAG | reasoning |
| 4 Checks (parallel) | rules · graph checks · timeline · cross-institution · template/format · forensics + AI-gen | reasoning, forensics |
| 5 Source verify (parallel with 4) | issuer lookup for high-confidence ref numbers | verification |
| 6 Aggregate | per-doc status, notes, priority | reasoning |
| 7 Anchor | append to audit log; anchor chain head | ledger |
| 8 Review | officer UI; actions; impact sim; decision → webhook | api, web |
| 9 Loop | re-upload → recompute affected nodes only | worker |

### 7.2 Dependencies (who needs whose output)
| Function | Needs | Produces |
|---|---|---|
| provenance.* | raw file | CheckResult (layer A/D) |
| extraction.extract | file, doc_type (or classify) | ExtractionResult |
| reasoning.build_claims | ExtractionResults + provenance CheckResults (for authority upgrade) | list[Claim] |
| reasoning.rule_engine | ExtractionResults + checklist + AICTE records | list[Finding] |
| reasoning.graph_checks | Claims | list[Finding] |
| reasoning.timeline | Claims (dates) | list[Finding] |
| forensics.* | file + Regions; **skipped** if pdf_signature verified | CheckResult (layer D/E) |
| verification.lookup | ExtractionResult ref_no with confidence ≥ threshold | CheckResult (issuer_lookup) |
| reasoning.aggregate | all Findings + CheckResults | list[DocumentStatus], priority |
| ledger.append | every Finding, CheckResult, action, decision | AuditEntry |

### 7.3 Celery DAG
```
chain(
  intake.s(app_id),
  group(provenance.s(doc) for doc in docs),
  group(extraction.s(doc) for doc in docs),
  build_graph.s(app_id),
  chord(
    group(rules.s(), graph_checks.s(), timeline.s(), cross_institution.s(),
          forensics_all.s(), source_verify_all.s()),
    aggregate.s(app_id)
  ),
  anchor.s(app_id),
  notify.s(app_id),
)
```
Every task stores its output in Postgres keyed by `app_id`/`doc_id`; tasks pass IDs, not large payloads. External calls use timeouts (`SOURCE_TIMEOUT_S`); on timeout → `verification_pending`.

---

## 8. Reasoning specification

### 8.1 Entities and claim mapping
Entity IDs: `institute:{aicte_permanent_id}` · `trust:{trust_reg_no}` · `land_parcel:{normalized survey_no}` · `person:{normalized_name}`.

| Source field | Entity.attribute |
|---|---|
| form.institute_name, affidavit.institute_name, noc.institute_name, accreditation_cert.institute_name | institute.name |
| form.application_no, affidavit.application_no | institute.application_no |
| form.trust_name | trust.name |
| form.trust_reg_date | trust.reg_date |
| form.land_survey_no, land_deed.survey_no | land_parcel.survey_no (anchor) |
| form.land_area, land_deed.area, affidavit.land_area_declared | land_parcel.area |
| land_deed.owner_name | land_parcel.owner |
| land_deed.mortgage_status | land_parcel.mortgage_status |

**Entity resolution:** normalize (lowercase, strip punctuation, expand abbreviations: inst→institute, tech→technology, engg→engineering; transliterate Devanagari to Latin), then RapidFuzz `token_sort_ratio`. Strong IDs match exactly after normalization. Name similarity ≥ `NAME_MATCH_THRESHOLD` (default 90) = same.

### 8.2 Comparison outcomes
For each attribute: group claims into clusters of agreeing values (tolerance per attribute). Then:
- Any claim with confidence < `CONFIDENCE_THRESHOLD` (default 0.75) is excluded from conflict detection. If excluding it leaves fewer than 2 claims, emit `unreadable` (severity `low`) for that claim.
- One cluster → agree (no finding).
- More than one cluster → `attribute_conflict`, severity from §8.3.
- Fewer than 2 usable claims and the rule requires 2 → `undetermined` (severity `info`).

Tolerances: area ±1% after unit conversion to acres; names via the fuzzy threshold; dates exact; IDs exact after normalization.

### 8.3 Severity from authority tiers
| Conflict between clusters containing | Severity |
|---|---|
| issuer_verified vs anything else | high |
| third_party vs self_declared | high |
| third_party vs third_party | medium |
| self_declared vs self_declared | medium |
| shared strong ID across institutions | high |

### 8.4 Rule YAML format

```yaml
# rules/rules/eoa_basic.yaml
- id: NOC_VALID_FOR_YEAR
  description: NOC must be valid until the end of the academic year
  illustrative: true                 # value to be configured from the Approval Process Handbook
  type: field_compare                # field_compare | field_present | field_regex | field_equals | required_docs
  left:  {doc_type: noc, field: valid_until}
  op: gte                            # eq | ne | gt | gte | lt | lte
  right: {config: ACADEMIC_YEAR_END}
  severity: high
  finding_type: expired
  message: "NOC expires on {left} before the academic year ends ({right})"

- id: NOC_REF_FORMAT
  type: field_regex
  field: {doc_type: noc, field: ref_no}
  pattern: '^FIRE/[A-Z]{2}/\d{4}/\d{6}$'
  severity: medium
  layer: C
  finding_type: rule_failed
  message: "NOC reference number '{value}' does not match the expected format"

- id: LAND_NOT_MORTGAGED
  type: field_equals
  field: {doc_type: land_deed, field: mortgage_status}
  value: none
  severity: medium
  finding_type: rule_failed
  message: "Land deed shows mortgage status '{value}'"
```

```yaml
# rules/rules/eoa_basic.yaml (continued)
- id: REQUIRED_DOCS
  type: required_docs
  checklist: eoa                     # reads rules/checklists/eoa.yaml
  severity: high
  finding_type: missing_doc
  message: "Required document '{doc_type}' is missing"
```

```yaml
# rules/checklists/eoa.yaml
category: eoa
required_docs: [application_form, land_deed, noc, affidavit]
optional_docs: [accreditation_cert, lab_photo]
```

```yaml
# rules/graph/eoa_graph.yaml
- id: LAND_AREA_AGREE
  type: attribute_agree
  entity_type: land_parcel
  attribute: area
  tolerance: {relative: 0.01, unit: acre}
  min_claims: 2
- id: INSTITUTE_NAME_AGREE
  type: attribute_agree
  entity_type: institute
  attribute: name
  tolerance: {fuzzy: 90}
- id: SURVEY_NO_AGREE
  type: attribute_agree
  entity_type: land_parcel
  attribute: survey_no
  tolerance: {exact: true}
- id: OWNER_IS_TRUST
  type: relationship_equal
  left:  {entity_type: land_parcel, attribute: owner}
  right: {entity_type: trust, attribute: name}
  tolerance: {fuzzy: 90}
  severity: high
  message: "Land owner '{left}' does not match the trust '{right}'"
```

**Starter rule set (prototype):**
| ID | Kind | Priority |
|---|---|---|
| REQUIRED_DOCS | required_docs | P0 |
| NOC_VALID_FOR_YEAR | field_compare | P0 |
| NOC_REF_FORMAT | field_regex (Layer C) | P0 |
| LAND_NOT_MORTGAGED | field_equals | P0 |
| TER_PAID | field_present + mock records match | P1 |
| INTAKE_WITHIN_APPROVED | per program vs mock records | P1 |
| ACCREDITATION_COVERS_YEAR | field_compare (only if doc present) | P1 |
| LAND_AREA_AGREE · INSTITUTE_NAME_AGREE · SURVEY_NO_AGREE · OWNER_IS_TRUST | graph | P0 |

### 8.5 Timeline engine
Events are date claims with names: `trust.reg_date`, `land_deed.registration_date`, `noc.issue_date`, `noc.valid_until`, `affidavit.date`, `form.application_date`, `accreditation.valid_from/valid_to`, plus config constants (`APPLICATION_WINDOW_START/END`, `ACADEMIC_YEAR_START/END`).

```yaml
# rules/timeline/eoa_timeline.yaml
- id: TL_NOC_AFTER_TRUST
  before: trust.reg_date
  after: noc.issue_date
  severity: high
  message: "NOC dated {after} is earlier than trust registration {before}"
- id: TL_NOC_ISSUE_BEFORE_EXPIRY
  before: noc.issue_date
  after: noc.valid_until
  severity: high
- id: TL_DEED_BEFORE_APPLICATION
  before: land_deed.registration_date
  after: form.application_date
  severity: medium
- id: TL_AFFIDAVIT_IN_WINDOW
  within: affidavit.date
  start: config.APPLICATION_WINDOW_START
  end: config.APPLICATION_WINDOW_END
  severity: medium
```
Outcome per rule: `pass`, `fail` → `timeline_violation`, or `undetermined` (a date missing or below confidence) → `undetermined` finding (severity `info`). Never report a missing date as a violation.

### 8.6 Impact simulator
Evidence DAG nodes: `requirement:{rule_id}` ← `conclusion:{rule_id}` ← `claim:{doc_id}:{attribute}` ← `doc:{doc_id}`. `simulate_exclusion(app_id, doc_ids)` removes the doc nodes, re-evaluates the affected conclusions with the same rule logic, and returns:
```json
{"excluded": ["app001_application_form", "app001_affidavit"],
 "conclusions": [
   {"rule_id": "LAND_AREA_AGREE", "before": "fail", "after": "pass", "status": "changed"},
   {"rule_id": "LAND_MIN_AREA", "before": "pass", "after": "fail", "status": "now_failing"},
   {"rule_id": "OWNER_IS_TRUST", "before": "pass", "after": "undetermined", "status": "now_uncertain"}]}
```
Statuses: `still_supported`, `now_uncertain`, `now_failing`, `changed`.

### 8.7 Aggregation
Per document, in precedence order:
1. Any `provenance_failure` or `source_mismatch` → `flagged`.
2. Any `high` finding → `flagged`.
3. Verification `verification_pending` / `source_unavailable` / `manual_review_required`, or any `unreadable` → `manual_review_required`.
4. Any `medium` finding → `flagged`.
5. Otherwise → `no_issues`.

`note` = one sentence built from the top 2 findings (e.g. "Land area conflicts with 2 other documents; issuer verification unavailable.").
Application priority = 100 × high + 10 × medium + 1 × low (transparent, shown to the officer).

`run_reasoning(app_id, extractions, checks) -> list[Finding]` runs rules, graph checks and timeline; `aggregate(app_id, findings, checks) -> (list[DocumentStatus], int)` runs separately.

---

## 9. Provenance, forensics, verification

### 9.1 Provenance (Layer A, D-metadata)
- `hash_file(path) -> dict` → `{"sha256": ..., "phash": ...}` (pHash of page 1 rendered at 150 DPI, or of the image).
- `check_pdf_signature(path) -> CheckResult` with pyHanko: `verified` (intact, trusted signer from `TRUST_ROOTS_DIR`), `mismatch` + `provenance_failure` (modified after signing / invalid), `not_applicable` (unsigned).
- `decode_qr(path) -> CheckResult` → payload in `evidence.details.payload`; comparison with printed text happens in reasoning.
- `extract_metadata(path) -> CheckResult` → flag (low) if the producer is image-editing software, or creation date is more than 30 days after the document's printed date.
- `check_duplicates(app_id, hashes, index) -> list[CheckResult]` → exact or pHash distance ≤ `PHASH_MAX_DIST` (default 6) under a different `app_id` → `duplicate` (high).

**Mock issuer CA:** `infra/pki/` holds a dev CA ("Mock Fire Dept CA"). Synthetic NOCs for clean applications are signed with it; its root cert goes in `TRUST_ROOTS_DIR`.

### 9.2 Forensics (Layer D, E)
Signature: `fn(image_path, regions: list[Region] | None = None) -> CheckResult`.
- `run_ela(quality=90)`: score = mean ELA intensity in region ÷ page mean; `suspicious` if ratio ≥ `ELA_RATIO_THRESHOLD` (default 2.0). Saves heatmap PNG to `data/out/forensics/`.
- `detect_copy_move()`: ORB keypoints, match within the same image, cluster matched pairs with spatial offset > 20 px; `suspicious` if ≥ 15 consistent matches.
- `noise_inconsistency()`: noise residual (image − median-filtered) std per region vs page; z-score ≥ 3 → `suspicious`.
- `ai_gen()` (P2): severity capped at `low`.
- All forensic findings are `forensic_signal` with message prefix "Preliminary indicator:".
- Skip all forensics for a document whose `pdf_signature` check is `verified`.

### 9.3 Verification connectors
```python
class IssuerConnector(Protocol):
    name: str
    doc_types: set[DocType]
    def lookup(self, ref_no: str, fields: dict[str, FieldValue]) -> CheckResult: ...
```
`MockIssuerConnector` calls `MOCK_ISSUER_URL/noc/{ref_no}`. It compares the returned record with the extracted fields → `verified` / `mismatch_detected` / `expired` / `source_unavailable` (404 for unknown issuer) / `verification_pending` (timeout) / `manual_review_required` (ref number below the confidence threshold, so no call is made).

---

## 10. Extraction specification
- `extract(file_path, doc_type=None) -> ExtractionResult`.
- Quality gate: reject if shorter side < 800 px at render or Laplacian variance < `BLUR_THRESHOLD`; add a warning; return empty fields.
- Classification: VLM zero-shot among the 6 types + keyword fallback.
- Extractor 1: OCR text + regex/keyword rules per doc type.
- Extractor 2: VLM with page image + JSON schema of that doc type's fields; validate with Pydantic; one retry.
- Confidence: `ocr_conf × agreement_factor × format_factor`, where agreement_factor = 1.0 if both extractors agree after normalization, 0.6 if only one produced a value, 0.4 if they disagree; format_factor = 1.0 valid, 0.5 invalid. Take the value from the extractor with the valid format; prefer extractor 1 on ties.
- `bbox` from OCR word boxes of the chosen value (normalized 0..1).
- Normalization: dates → ISO `YYYY-MM-DD`; areas → value + unit, converted copy in acres in reasoning; Devanagari digits → ASCII.

---

## 11. API (FastAPI, prefix `/v1`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | liveness |
| POST | `/v1/applications` | multipart: `form` (JSON) + `files[]` with `doc_type` each → `202 {app_id, job_id}` |
| GET | `/v1/applications` | queue, sorted by priority; filters: status |
| GET | `/v1/applications/{app_id}` | summary: counts, priority, status |
| GET | `/v1/applications/{app_id}/documents` | list with DocumentStatus + signed file URL |
| GET | `/v1/applications/{app_id}/findings` | findings (+ claims, evidence) |
| GET | `/v1/applications/{app_id}/graph` | nodes/edges for Cytoscape |
| GET | `/v1/applications/{app_id}/timeline` | events + violations |
| POST | `/v1/applications/{app_id}/simulate-exclusion` | `{doc_ids}` → §8.6 result |
| POST | `/v1/findings/{finding_id}/action` | `{action: confirm|dismiss, reason}` (reason required) |
| POST | `/v1/applications/{app_id}/decision` | `{decision, reason, deficiencies[]}`; 409 if any high finding has no action; reason required for reject |
| POST | `/v1/applications/{app_id}/documents` | re-upload (rectification) → partial recompute |
| GET | `/v1/audit/verify` | `{valid, head_seq, head_hash, last_anchor_tx}` |
| — | Webhook `POST {PORTAL_CALLBACK_URL}` | `{app_id, event: "validation_complete" | "decision_recorded", ...}` |

Roles (JWT claim `role`): `institute`, `officer`, `approver`, `admin`, `auditor`. Every document fetch writes an `access_log` row.

---

## 12. Database (PostgreSQL)

| Table | Key columns |
|---|---|
| applications | app_id PK, category, status, priority, form JSONB, created_at |
| documents | doc_id PK, app_id FK, doc_type, object_key, sha256, phash, uploaded_at, version |
| extractions | doc_id PK, result JSONB |
| check_results | id PK, doc_id FK, layer, check, status, severity, result JSONB |
| claims | id PK, app_id, doc_id, entity, attribute, value JSONB, authority, confidence |
| findings | finding_id PK, app_id, type, severity, rule_id, payload JSONB |
| finding_actions | id PK, finding_id FK, user_id, action, reason, ts |
| decisions | id PK, app_id FK, user_id, decision, reason, deficiencies JSONB, ts |
| audit_log | seq PK, ts, event_type, payload_hash, prev_hash, hash |
| anchors | id PK, seq, head_hash, tx_hash, block_number, ts |
| access_log | id PK, user_id, role, doc_id, action, ts |

---

## 13. Synthetic data specification

### 13.1 Layout
```
data/synthetic/app001/
  application_form.json
  land_deed.pdf  noc.pdf  affidavit.pdf  accreditation_cert.pdf  lab_photo_1.jpg
  ground_truth.json
```
20 applications: about 8 clean, 12 with 1–3 defects. Mix of digital PDFs and scan-simulated PDFs (Augraphy). Land deeds include Marathi/Hindi labels. Clean NOCs are signed with the mock issuer CA.

### 13.2 Defect catalog
| Code | Injection | Expected detector | Expected finding |
|---|---|---|---|
| AREA_MISMATCH | form & affidavit area ≠ deed area | graph LAND_AREA_AGREE | attribute_conflict (high) |
| OWNER_MISMATCH | deed owner ≠ trust name | graph OWNER_IS_TRUST | relationship_violation (high) |
| NAME_MISMATCH | NOC institute name differs substantially | graph INSTITUTE_NAME_AGREE | attribute_conflict |
| EXPIRED_NOC | valid_until before academic year end | rule NOC_VALID_FOR_YEAR | expired (high) |
| TIMELINE_NOC_BEFORE_TRUST | NOC issue_date < trust_reg_date | timeline TL_NOC_AFTER_TRUST | timeline_violation (high) |
| BAD_REF_FORMAT | malformed NOC ref_no | rule NOC_REF_FORMAT | rule_failed (medium) |
| MISSING_DOC | drop a required doc | rule REQUIRED_DOCS | missing_doc (high) |
| MORTGAGED_LAND | mortgage_status = mortgaged | rule LAND_NOT_MORTGAGED | rule_failed (medium) |
| SIGNED_THEN_EDITED | modify a signed NOC after signing | provenance pdf_signature | provenance_failure (high) |
| PASTED_SIGNATURE | paste signature image onto scanned page | forensics ELA/noise | forensic_signal |
| DUPLICATE_PHOTO | same lab photo in two applications | provenance duplicates | duplicate (high) |
| ISSUER_MISMATCH | mock issuer record differs from document | verification | source_mismatch (high) |
| ISSUER_TIMEOUT | mock issuer delays response | verification | verification_pending |

### 13.3 Mock services (`services/mock_issuer`)
- `GET /noc/{ref_no}` → record from ground truth; deliberate mismatches and one delayed response per §13.2.
- `GET /aicte/records/{aicte_permanent_id}` → approved intake per program, previous EoA year.
- `GET /aicte/payments/{ter_txn_id}` → `{paid: bool, amount, date}`.

---

## 14. Audit log and blockchain
- `append(event_type, payload) -> AuditEntry`: canonical JSON (`sort_keys=True, separators=(",", ":")`) → `payload_hash`; compute `hash` per §5.2; insert atomically with `seq = last + 1`.
- `verify_chain() -> bool`: recompute every hash from seq 0; also compare the head at each anchored seq with the on-chain value.
- Anchoring: after each application completes processing and after each decision, call `anchor_root(seq, head_hash)`.
- Contract:
```solidity
// blockchain/contracts/AuditAnchor.sol
contract AuditAnchor {
    event Anchored(uint256 indexed seq, bytes32 rootHash, uint256 timestamp);
    mapping(uint256 => bytes32) public roots;
    address public immutable owner;
    constructor() { owner = msg.sender; }
    function anchor(uint256 seq, bytes32 rootHash) external {
        require(msg.sender == owner, "not owner");
        require(roots[seq] == bytes32(0), "exists");
        roots[seq] = rootHash;
        emit Anchored(seq, rootHash, block.timestamp);
    }
}
```
- Besu runs in dev mode in Docker (RPC `BESU_RPC_URL`, default `http://localhost:8545`). Deploy with Hardhat; store the address in `.env`.
- Documents and personal data are **never** written on-chain; only hashes.

---

## 15. Configuration (`.env`)

```
DATABASE_URL=postgresql+psycopg://docverf:docverf@localhost:5432/docverf
REDIS_URL=redis://localhost:6379/0
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=docverf
MINIO_SECRET_KEY=docverf-secret
MINIO_BUCKET=documents
BESU_RPC_URL=http://localhost:8545
ANCHOR_CONTRACT_ADDRESS=
ANCHOR_PRIVATE_KEY=            # dev key only
OLLAMA_URL=http://localhost:11434
VLM_MODEL=
OCR_ENGINE=paddleocr           # paddleocr | surya
ALLOW_CLOUD_AI=false
CONFIDENCE_THRESHOLD=0.75
NAME_MATCH_THRESHOLD=90
PHASH_MAX_DIST=6
ELA_RATIO_THRESHOLD=2.0
BLUR_THRESHOLD=100
SOURCE_TIMEOUT_S=5
MOCK_ISSUER_URL=http://localhost:8100
PORTAL_CALLBACK_URL=http://localhost:3000/api/callbacks
TRUST_ROOTS_DIR=infra/pki/trust_roots
ACADEMIC_YEAR_START=2027-07-01         # illustrative
ACADEMIC_YEAR_END=2028-06-30           # illustrative
APPLICATION_WINDOW_START=2026-12-01    # illustrative
APPLICATION_WINDOW_END=2027-03-31      # illustrative
RETENTION_DAYS=365
JWT_SECRET=dev-secret
```

---

## 16. Evaluation (`eval/metrics.py`)
- Field extraction: exact match per field after normalization vs `true_fields`; report per doc type.
- Defect detection: for each injected defect, check that a finding with the expected type exists on the right doc → recall per defect code; findings not matching any defect on clean applications → false positives → precision.
- Source verification: count per VerificationStatus.
- Timing: per-stage and total processing time per application (from task timestamps).
- Alert latency: time from finding creation to alert delivery.
- Output: `eval/report.md` + JSON.

---

## 17. Testing
- `tests/fixtures/apps/app_clean/` and `tests/fixtures/apps/app_conflict/`: hand-made `ExtractionResult` JSON (Appendix A) so reasoning can be tested without OCR.
- Unit tests per module; one integration test running the DAG on one synthetic application (marked `slow`).
- CI: ruff + pytest (excluding `slow`).

---

## 18. Ownership (current phase)
| Owner | Module |
|---|---|
| Lead (Sukrut) | repo, schemas, config, api, worker DAG, integration |
| Person A | `synthetic/`, `services/mock_issuer` |
| Person B | `extraction/` |
| Person C | `provenance/`, `forensics/`, `ledger/`, `blockchain/` |
| Person D | `reasoning/` (rule engine + graph checks first) |
| Later | `apps/web` officer UI, digital twin, impact sim UI, eval, PPT |

---

## 19. Resolved questions (v0.2)

**Q1 — IDs in function signatures.** Every function that returns a schema object needing IDs receives them explicitly:
```python
# provenance
hash_file(path: str) -> dict[str, str]                      # {"sha256": ..., "phash": ...}
check_pdf_signature(path: str, doc_id: str) -> CheckResult
decode_qr(path: str, doc_id: str) -> CheckResult
extract_metadata(path: str, doc_id: str) -> CheckResult
# forensics
run_ela(image_path: str, doc_id: str, regions: list[Region] | None = None) -> CheckResult
detect_copy_move(image_path: str, doc_id: str, regions: list[Region] | None = None) -> CheckResult
noise_inconsistency(image_path: str, doc_id: str, regions: list[Region] | None = None) -> CheckResult
ai_gen(image_path: str, doc_id: str) -> CheckResult
# extraction
extract(file_path: str, doc_id: str, app_id: str, doc_type: DocType | None = None) -> ExtractionResult
```

**Q2 — `check_duplicates` types.**
```python
HashIndex = dict[str, list[tuple[str, str]]]   # hash value -> [(app_id, doc_id), ...]
check_duplicates(app_id: str, doc_id: str, hashes: dict[str, str], index: HashIndex) -> list[CheckResult]
```
Pure function: it does not mutate `index`; the caller adds the new hashes afterwards.

**Q3 — Ledger DB access.** `ledger/` owns its storage. `AuditLog(db_url: str = config.DATABASE_URL)` uses SQLAlchemy and works with SQLite for local dev (e.g. `sqlite:///data/ledger.db`) and Postgres in Docker. No other module writes `audit_log` or `anchors`.

**Q4 — `cross_institution` module.** `packages/docverf/reasoning/cross_institution.py` with `check_cross_institution(app_id: str, claims: list[Claim], hash_index: HashIndex) -> list[Finding]`. P1; stub for now.

**Q5 — `anchor_root` return.** `anchor_root(seq: int, root_hash: str) -> str` returns the transaction hash (hex).

**Q6 — Placement.** Accepted as scaffolded: `verification.lookup` in `verification/__init__.py`, `build_claims` in `reasoning/entity_graph.py`, `aggregate` in `reasoning/run.py`.

**Q7 — Signatures derived from prose.** Accepted. Module owners may refine signatures *inside their own module* as long as the public function returns the §5 schema type. Changes to anything another module calls go through the lead.

**Q8 — Missing rule YAML.** `REQUIRED_DOCS` YAML added to §8.4. `TER_PAID`, `INTAKE_WITHIN_APPROVED`, `ACCREDITATION_COVERS_YEAR` and `LAND_MIN_AREA` are P1: the reasoning owner adds their YAML when implementing them. `LAND_MIN_AREA` (land area ≥ an illustrative minimum from config) exists only for the impact-simulator example.

**Q9 — `app_clean` fixture.** Fixed in Appendix A: affidavit area confidence 0.92, agreement true; `app_clean` must yield zero findings. Dropping stale `raw` values is correct.

**Q10 — Multipart upload shape.** `POST /v1/applications` multipart parts:
- `form`: JSON string of the application_form fields,
- `files`: repeated file parts,
- `doc_types`: JSON array of DocType values, same length and order as `files`.

**Q11 — Python version.** `requires-python = ">=3.11,<3.13"` accepted; the team develops on 3.11 via uv.

---

## Appendix A — fixture: conflict application (`app_conflict`)

Clean variant (`app_clean`): same values but deed `area` = 2.5, deed `owner_name` = trust name, NOC `issue_date` = 2025-11-10, NOC `valid_until` = 2028-12-31, affidavit `land_area_declared` confidence = 0.92 with `extractor_agreement: true`. Drop `raw` on any field whose value changed. `app_clean` must produce **zero** findings.

```json
[
  {"doc_id": "appx_application_form", "app_id": "appx", "doc_type": "application_form",
   "fields": {
     "institute_name": {"value": "Shree Vidya Institute of Technology", "confidence": 1.0},
     "aicte_permanent_id": {"value": "1-9876543", "confidence": 1.0},
     "application_no": {"value": "1-46200000001", "confidence": 1.0},
     "trust_name": {"value": "Shree Vidya Education Trust", "confidence": 1.0},
     "trust_reg_no": {"value": "E-12345/PUNE", "confidence": 1.0},
     "trust_reg_date": {"value": "2009-04-15", "confidence": 1.0},
     "land_survey_no": {"value": "45/2", "confidence": 1.0},
     "land_area": {"value": 2.5, "unit": "acre", "confidence": 1.0},
     "application_date": {"value": "2027-01-20", "confidence": 1.0},
     "ter_txn_id": {"value": "TER2027000123", "confidence": 1.0}
   }},
  {"doc_id": "appx_land_deed", "app_id": "appx", "doc_type": "land_deed",
   "fields": {
     "owner_name": {"value": "Shree Vidya Charitable Society", "raw": "श्री विद्या चॅरिटेबल सोसायटी", "confidence": 0.88, "page": 1, "bbox": [0.12, 0.30, 0.70, 0.34], "extractor_agreement": true},
     "survey_no": {"value": "45/2", "confidence": 0.95, "page": 1, "bbox": [0.12, 0.36, 0.30, 0.39], "extractor_agreement": true},
     "area": {"value": 2.1, "unit": "acre", "raw": "2.10 एकर", "confidence": 0.93, "page": 1, "bbox": [0.12, 0.41, 0.35, 0.44], "extractor_agreement": true},
     "registration_date": {"value": "2010-02-03", "confidence": 0.90},
     "mortgage_status": {"value": "none", "confidence": 0.85}
   }},
  {"doc_id": "appx_noc", "app_id": "appx", "doc_type": "noc",
   "fields": {
     "issuer": {"value": "Maharashtra Fire Services", "confidence": 0.92},
     "ref_no": {"value": "FIRE/MH/2008/004512", "confidence": 0.91, "extractor_agreement": true},
     "institute_name": {"value": "Shree Vidya Institute of Technology", "confidence": 0.94},
     "issue_date": {"value": "2008-06-10", "confidence": 0.90, "extractor_agreement": true},
     "valid_until": {"value": "2027-12-31", "confidence": 0.90, "extractor_agreement": true}
   }},
  {"doc_id": "appx_affidavit", "app_id": "appx", "doc_type": "affidavit",
   "fields": {
     "institute_name": {"value": "Shree Vidya Inst. of Tech.", "confidence": 0.89},
     "application_no": {"value": "1-46200000001", "confidence": 0.93},
     "date": {"value": "2027-01-18", "confidence": 0.92},
     "land_area_declared": {"value": 2.5, "unit": "acre", "confidence": 0.62, "extractor_agreement": false}
   }}
]
```

**Expected findings for `app_conflict`:**
| Rule | Expected |
|---|---|
| LAND_AREA_AGREE | attribute_conflict, high (form 2.5 self-declared vs deed 2.1 third-party). The affidavit's 2.5 is excluded (confidence 0.62) → also an `unreadable` finding for that field |
| OWNER_IS_TRUST | relationship_violation, high |
| INSTITUTE_NAME_AGREE | pass (abbreviation expansion makes the affidavit name match) |
| TL_NOC_AFTER_TRUST | timeline_violation, high (2008-06-10 < 2009-04-15) |
| NOC_VALID_FOR_YEAR | expired, high (2027-12-31 < 2028-06-30) |
| REQUIRED_DOCS | pass |
| LAND_NOT_MORTGAGED | pass |

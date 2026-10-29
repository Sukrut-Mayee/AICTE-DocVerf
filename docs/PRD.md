# PRD — AICTE DocVerif

**Product:** AI-powered application validation, document authentication and regulatory compliance verification for AICTE
**Context:** Smart India Hackathon (SIH) prototype
**Repo:** https://github.com/Sukrut-Mayee/AICTE-DocVerf
**Version:** 0.1 (prototype build) · **Date:** 2026-10-24 · **Owner:** Sukrut Mayee (team lead)
**Companion doc:** `docs/TRD.md` (technical source of truth: contracts, schemas, module specs)

> For AI coding agents: read this file for *what* and *why*, and read `docs/TRD.md` for *how*. If the two conflict, stop and ask; do not guess.

---

## 1. Summary

AICTE processes Extension of Approval (EoA) applications from technical institutions every year. Each application has a large set of supporting documents (land records, NOCs, affidavits, accreditation certificates, infrastructure photos and more) that officials check by hand. This is slow, inconsistent, and exposed to forged or altered documents.

AICTE DocVerif is a **decision-support layer** that sits between application submission and human scrutiny. It:

1. checks whether each document can **prove its own origin** (digital signatures, QR codes, issuer lookups),
2. extracts structured data from documents with OCR and AI,
3. builds an **evidence graph** across all documents and checks that they agree with each other, with AICTE records, and with a consistent timeline,
4. looks for manipulation signals (pixel forensics, duplicates, metadata, AI-generation signals),
5. presents every flag to an AICTE officer **with its evidence**, document by document,
6. records every finding and decision in a **tamper-evident audit log anchored to a blockchain**.

**The system never approves or rejects. A human officer always decides.**

---

## 2. Background and problem

### 2.1 Current process (simplified)
Institute fills online application + uploads documents → Scrutiny (experts check form and documents) → Expert Visit Committee (physical visit, notes deficiencies) → Standing Hearing Committee (institutes present their case on deficiencies) → EoA letter issued (possibly listing deficiencies to comply with).

### 2.2 Pain points
- Manual checking of every document against form fields is slow and repetitive.
- Missing, expired or inconsistent documents are often found late (at the visit or hearing stage).
- Verifying a document with its issuing authority is manual and slow.
- Altered or fabricated documents (edited dates, pasted signatures or stamps, recycled photos) are hard to spot by eye.
- Institutes re-upload near-identical documents every year; changes between years are not tracked.
- There is no single evidence-linked view of why an application has problems.

### 2.3 Problem statement (one line)
Give AICTE officials an early, explainable, evidence-linked first pass over every application so their time goes to the cases that actually need human judgement.

---

## 3. Goals and non-goals

### 3.1 Goals
- **G1** Detect missing, incomplete, expired and inconsistent information at the application stage.
- **G2** Verify documents at the source wherever an official mechanism exists (digital signature, QR, issuer lookup).
- **G3** Detect cross-document, cross-year and cross-institution inconsistencies through an evidence graph.
- **G4** Surface manipulation signals as **preliminary indicators with evidence**, never as verdicts.
- **G5** Give officers a clear, document-by-document review with highlighted flags and short notes, ending in a decision screen.
- **G6** Keep a tamper-evident audit trail of everything the system found and every action an officer took.
- **G7** Make all checklists and rules configurable without code changes.
- **G8** Be integration-ready: API-first, stack-agnostic, self-hostable, open-source components.

### 3.2 Non-goals
- Automatically approving or rejecting applications.
- Declaring a document "forged" or an institution "fraudulent".
- Replacing physical inspections where regulations require them.
- Accessing restricted government databases without authorization (the prototype uses mocks).
- Supporting every AICTE application category and every document type (prototype scope is limited; see §5).

---

## 4. Users and roles

| Role | Description | Key needs |
|---|---|---|
| **Institute user** | Submits application and documents (via mock portal in prototype) | Know quickly what is missing or wrong; fix it |
| **Scrutiny officer** | AICTE official reviewing applications | Prioritized queue; per-document flags with evidence; record decisions |
| **Approver / senior officer** | Takes or confirms the final decision | Summary, unresolved items, audit history |
| **Rules admin** | Maintains checklists and rules from the Approval Process Handbook | Edit YAML rules without code changes |
| **Inspector** (P2) | Conducts site visits | Targeted inspection checklist; signed on-site capture |
| **Auditor** | Reviews integrity of the process | Verify that the audit log has not been tampered with |

All access is role-based. Every document view by any user is logged.

---

## 5. Prototype scope

- **Application category:** Extension of Approval (EoA) only.
- **Document types (6):** `application_form` (structured data), `land_deed`, `noc` (fire/building NOC), `affidavit`, `accreditation_cert`, `lab_photo`.
- **Data:** synthetic applications with known injected defects (no real institutional data).
- **External sources:** mock issuer API and mock AICTE records API (behind a connector interface that real APIs can replace).
- **Languages in documents:** English, plus Hindi/Marathi on land documents.

---

## 6. Core principles (design rules that every feature must follow)

1. **Prove genuine before detecting fake.** Provenance checks run first; a valid issuer signature skips weaker checks.
2. **Cheap and certain before expensive and uncertain.**
3. **AI extracts, rules decide, humans judge.** AI models only turn documents into data. Deterministic, configurable rules produce findings. Officers make decisions.
4. **Extract once, reuse everywhere.** All checks consume the same normalized data.
5. **Evidence or it didn't happen.** Every finding links to source documents, regions, values and the rule that fired.
6. **Missing ≠ contradiction.** Three outcomes per check: agrees / conflicts / not enough evidence. Low-confidence data can never produce a "conflict".

---

## 7. Functional requirements

Priority: **P0** = must work in the finale demo · **P1** = should · **P2** = stretch.

### Intake
**FR-01 Application intake (P0).** The mock portal submits an application (form data + files) to the API. The API returns `202 Accepted` with an `app_id` immediately and processes asynchronously. When processing finishes, the system calls a configurable webhook URL.
*Acceptance:* submitting a synthetic application returns 202 within 2 s; a webhook fires on completion.

**FR-02 Category checklist (P0).** The system loads the checklist for the application category from YAML (required document types, rules, validity windows).
*Acceptance:* changing the YAML (e.g. making `accreditation_cert` required) changes results without code changes.

**FR-27 TER payment check (P1).** The system checks that the application's TER transaction ID exists in AICTE payment records (mock).
*Acceptance:* a missing or unmatched transaction ID produces a `rule_failed` finding.

### Provenance and verification (Layer A)
**FR-03 Provenance checks (P0).** For every file: SHA-256 and perceptual hash; PDF digital signature validation (valid / invalid / modified after signing / none); QR decode; metadata extraction.
*Acceptance:* a signed synthetic NOC is marked verified; the same NOC edited after signing is marked as a provenance failure (high).

**FR-12 Source verification (P0).** For document types with an issuer connector, the system queries the issuer (mock) using the extracted reference number, but only if that number was extracted with high confidence. Result statuses: `verified`, `mismatch_detected`, `expired`, `verification_pending`, `source_unavailable`, `manual_review_required`. The source, timestamp and result are recorded.
*Acceptance:* demo shows all six statuses across the synthetic set, including a timeout → `verification_pending`.

### Understanding
**FR-04 Extraction (P0).** For each document: quality gate, classification, layout/regions, OCR, two independent extractors (OCR + rules, and VLM), normalization (dates, units, names).
*Acceptance:* field-level exact-match accuracy is reported against ground truth for `land_deed`, `noc`, `affidavit`.

**FR-05 Confidence and "unreadable" (P0).** Each field gets a computed confidence (OCR confidence × extractor agreement × format validity). Fields below the threshold produce "unreadable, confirm manually" and never a conflict.
*Acceptance:* a field where extractors disagree shows as unreadable in the review UI, with a crop.

### Consistency and rules (Layer B, Layer C)
**FR-06 Rule engine (P0).** Configurable YAML rules: required documents, validity/expiry, field thresholds, reference-number formats, mortgage status.
*Acceptance:* each rule in `rules/` produces a pass/fail/undetermined result with evidence.

**FR-07 Evidence graph consistency (P0).** All claims about the same real-world entity (institute, trust, land parcel, person) are linked. Disagreements are reported as conflict clusters labelled by authority tier (issuer-verified > third-party > self-declared). Relationship rules: deed owner = trust; affidavit institute = form institute.
*Acceptance:* the "form 2.5 acres vs deed 2.1 acres" synthetic case produces one high-severity finding listing all sources.

**FR-08 Timeline contradiction engine (P0).** All dates become events on a timeline; configurable temporal rules check the sequence (e.g. NOC issued after trust registration). Missing or uncertain dates are reported as "undetermined", not as violations.
*Acceptance:* the synthetic "NOC before trust registration" defect is detected; a missing date is not flagged as a violation.

**FR-11 Duplicates and cross-institution (P1).** The same file or photo (exact or perceptual hash), survey number or certificate number appearing under different institutes is flagged.
*Acceptance:* the synthetic duplicate lab photo is flagged on both applications.

**FR-28 Historical diff (P2).** Compare this year's graph with last year's approved graph; changes to immutable attributes (survey number, trust registration number) are flagged.

### Manipulation signals (Layer D, Layer E)
**FR-09 Pixel forensics (P0).** ELA, noise inconsistency and copy-move detection, run on detected regions (signature, seal, numbers). Skipped for documents already verified by issuer signature. Output includes heatmaps.
*Acceptance:* the synthetic pasted-signature document shows a suspicious region with a heatmap.

**FR-10 AI-generation signal (P2).** An AI-generated-image detector runs on photos as a weak signal only. It can never alone raise severity above `low`.

### Aggregation and review
**FR-13 Aggregation (P0).** Each document gets an overall status (`no_issues`, `flagged`, `manual_review_required`) plus its verification status and linked findings. Applications are prioritized by transparent severity rules.

**FR-14 Officer review UI (P0).**
1. Application summary (counts of documents, flags by severity, verification statuses).
2. Document-by-document review, flagged documents first. Each document shows a **short note** summarizing its issues and **highlighted regions** colored by severity.
3. Clicking a flag shows the evidence: conflicting claims side by side, the rule that fired, heatmap or issuer response.
4. Clean documents are listed collapsed ("12 documents, no issues").
*Acceptance:* an officer can review a defective synthetic application end to end without opening raw JSON.

**FR-15 Flag actions (P0).** For each flag the officer can confirm or dismiss with a mandatory reason. Every action is logged.

**FR-16 Evidence removal impact simulator (P1).** The officer can temporarily exclude one or more documents; the system recomputes affected conclusions and shows which remain supported, become uncertain, or fail.
*Acceptance:* excluding the self-declared documents in the land case flips "land requirement met" to "not met".

**FR-17 Decision screen (P0).** Options: Approve · Approve with deficiencies (listed) · Request rectification · Send for site inspection · Reject (reason required). The decision button is enabled only after every high-severity flag has an action. The decision is sent to the portal via webhook and recorded in the audit log.

**FR-18 Rectification loop (P1).** Deficiencies go back to the institute; re-uploaded documents re-run only the affected checks.

**FR-19 Alerts (P1).** In-app and email alerts for: missing documents, expired documents, pending source verification, high-severity findings, decision recorded.

**FR-22 Infrastructure digital twin (P1).** A sample floor plan with clickable rooms; each room shows linked photos, certificates, checklist items, unresolved checks and whether a site visit may be needed. Photos are never presented as proof of dimensions, occupancy or compliance.

**FR-23 Site inspection capture (P2).** A PWA for inspectors: camera-only capture, GPS geofence, timestamp, signed at capture; results feed back as findings.

**FR-26 Video evidence (P2).** Videos are sampled into frames and processed like photos.

### Trust and governance
**FR-20 Audit log and blockchain anchoring (P0).** Every finding, verification result, flag action and decision is appended to a hash-chained log. The chain head is periodically anchored to a permissioned blockchain (Hyperledger Besu in the prototype). A verify function detects any tampering.
*Acceptance:* demo edits one log row in the database → verification fails and the on-chain anchor no longer matches.

**FR-21 Access logging and retention (P1).** Every document view is logged with user, role and time. Documents are purged after a configurable retention period; hashes on the ledger are kept.

### Data and evaluation
**FR-24 Synthetic dataset (P0).** At least 20 synthetic applications with ground truth and a catalog of injected defects (see TRD §13).

**FR-25 Evaluation report (P0).** Field extraction accuracy, defect detection precision and recall per defect type, source verification success rate, average processing time per application, alert latency.

---

## 8. Key user flows

### 8.1 Institute submission
Portal form → upload documents → submit → (async) receive status and deficiency list → re-upload where permitted → resubmit.

### 8.2 Officer review
Queue sorted by priority → open application → summary → review documents one by one (note + highlights + evidence) → confirm/dismiss each flag with a reason → optionally run the impact simulator / timeline / graph / digital twin views → decision screen → decision recorded, webhook sent, audit entry anchored.

### 8.3 Auditor verification
Open audit page → run "verify chain" → see pass/fail and the latest anchored block reference.

---

## 9. Non-functional requirements

| Area | Requirement |
|---|---|
| Explainability | Every finding carries rule ID, values, source documents, regions and a human-readable message |
| Safety | No adverse action without human sign-off; manipulation signals are labelled "preliminary" |
| Security | RBAC; encrypted object storage; secrets in env vars; no documents sent to external AI APIs by default |
| Privacy | Access logging; retention policy; ledger stores hashes only, never documents or personal data |
| Configurability | Checklists, rules, thresholds, tolerances and timeline rules in YAML |
| Performance (prototype) | One application with about 6 documents processed in under 3 minutes on the demo machine |
| Integration | REST + OpenAPI spec; async with webhook; no dependency on AICTE's internal stack |
| Portability | Everything runs with Docker Compose; open-source components only |
| Reliability | A slow or failing external source never blocks the pipeline (timeout → pending) |

---

## 10. Success metrics (reported in the eval report)

| Metric | Target for demo |
|---|---|
| Field extraction exact-match (3 core doc types) | ≥ 85% on synthetic data |
| Defect detection recall (P0 defect types) | ≥ 90% |
| Defect detection precision | ≥ 80% |
| False "conflict" from low-confidence data | 0 (by design) |
| Source verification success rate (mock) | Reported per status |
| Avg processing time per application | < 3 min |
| Officer review time: assisted vs manual (small user test) | Reported |

---

## 11. Problem statement traceability

| Problem statement item | Covered by |
|---|---|
| Identify category, determine checklist | FR-02 |
| Retrieve AICTE records (past EoA, intake, faculty, deficiency, TER) | FR-07, FR-27, FR-28, mock records API |
| OCR, classification, extraction | FR-04, FR-05 |
| Missing, incomplete, expired, inconsistent | FR-06, FR-07, FR-08 |
| Rectification where permitted | FR-18 |
| Alterations, duplication, metadata, mismatched IDs, irregular dates | FR-03, FR-09, FR-11, FR-07, FR-08 |
| Flags with evidence, treated as preliminary | FR-13, FR-14, principle 5 |
| Issuer verification (API, portal, QR, digital signature, reference no.) | FR-03, FR-12 |
| Six verification statuses, source + timestamp | FR-12 |
| Infrastructure evidence (photos, videos, floor plans) | FR-22, FR-23, FR-26 |
| Dashboard, alerts, audit trail | FR-14, FR-19, FR-20 |
| Role-based access, secure handling, confidentiality | §4, FR-21, §9 |
| Human review before adverse action | FR-17 |
| Synthetic or anonymized demo data + evaluation | FR-24, FR-25 |

---

## 12. Assumptions, constraints, risks

**Assumptions**
- Real issuer APIs and AICTE internal records are not available; mocks behind a connector interface stand in.
- Handbook rule values used in the prototype are illustrative and marked as such.

**Constraints**
- Hackathon timeline; limited GPU access; open-source components only.

**Key risks**
| Risk | Mitigation |
|---|---|
| No GPU for VLM | OCR + rules as primary extractor; small quantized VLM; pre-processed demo results |
| Poor OCR on Devanagari scans | Benchmark engines early; low confidence → human |
| Forensics false positives on scans | Region-localized; weak signal only; heatmaps, not verdicts |
| Entity resolution errors | Strong IDs as anchors; fuzzy threshold; human confirmation |
| Scope creep | Stick to 6 doc types and P0 list |
| Blockchain setup time | Hash-chained log first; Besu dev node second |

---

## 13. Out of scope (prototype)
Real AICTE portal integration, real issuer integrations, categories other than EoA, signature-to-person matching, production deployment hardening, mobile app store builds.

## 14. Milestones
1. Repo scaffold + contracts frozen.
2. Module MVPs (synthetic data, extraction, trust module, reasoning).
3. Pipeline integration (Celery DAG) + API.
4. Officer UI on real findings.
5. Eval report + demo script + PPT.

## 15. Glossary
| Term | Meaning |
|---|---|
| EoA | Extension of Approval: yearly AICTE approval for existing institutions |
| EVC | Expert Visit Committee (physical inspection) |
| SHC | Standing Hearing Committee |
| NOC | No Objection Certificate |
| TER | AICTE processing fee payment |
| DSC | Digital Signature Certificate (IT Act) |
| Provenance | Proof of where a document came from |
| Claim | One fact a document states about one entity, with source and confidence |
| Authority tier | issuer-verified > third-party > self-declared |
| Finding | A flagged issue with evidence, shown to the officer |
| Anchoring | Writing a hash of the audit log to the blockchain |

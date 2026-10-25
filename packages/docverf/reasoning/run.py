"""Reasoning entry points (TRD §8.7)."""

from typing import Any

from docverf.reasoning.entity_graph import (
    FIELD_MAP,
    SEVERITY_RANK,
    build_claims,
    graph_checks,
    unit_findings,
)
from docverf.reasoning.rule_engine import load_checklist, new_finding_id, run_rules
from docverf.reasoning.timeline import timeline_checks
from docverf.schemas import (
    CheckResult,
    CheckStatus,
    DocOverallStatus,
    DocumentStatus,
    ExtractionResult,
    Finding,
    FindingType,
    Severity,
    VerificationStatus,
)

# check name -> (finding type, severity that overrides the check's own, or None to keep it)
CHECK_FINDINGS = {
    "pdf_signature": (FindingType.PROVENANCE_FAILURE, Severity.HIGH),
    "hash_duplicate": (FindingType.DUPLICATE, Severity.HIGH),
    "ela": (FindingType.FORENSIC_SIGNAL, None),
    "copy_move": (FindingType.FORENSIC_SIGNAL, None),
    "noise": (FindingType.FORENSIC_SIGNAL, None),
    "metadata": (FindingType.FORENSIC_SIGNAL, None),
    "ai_gen": (FindingType.FORENSIC_SIGNAL, None),
    "ref_format": (FindingType.RULE_FAILED, None),
    "template": (FindingType.RULE_FAILED, None),
}
FLAGGED_STATUSES = {CheckStatus.MISMATCH, CheckStatus.SUSPICIOUS}
# issuer_lookup is read from verification_status; pending / unavailable / manual review give
# no finding and show up as DocumentStatus.verification instead.
ISSUER_FINDINGS = {
    VerificationStatus.MISMATCH_DETECTED: FindingType.SOURCE_MISMATCH,
    VerificationStatus.EXPIRED: FindingType.EXPIRED,
}
# Verification states that need a human, and how a note words them.
UNRESOLVED = {
    VerificationStatus.VERIFICATION_PENDING: "verification pending",
    VerificationStatus.SOURCE_UNAVAILABLE: "source unavailable",
    VerificationStatus.MANUAL_REVIEW_REQUIRED: "needs manual review",
}
# Worst first: a document with several verification checks shows its worst state.
VERIFICATION_ORDER = [
    VerificationStatus.MISMATCH_DETECTED,
    VerificationStatus.EXPIRED,
    VerificationStatus.MANUAL_REVIEW_REQUIRED,
    VerificationStatus.SOURCE_UNAVAILABLE,
    VerificationStatus.VERIFICATION_PENDING,
    VerificationStatus.VERIFIED,
]
# (doc_type, entity type, claim attribute) -> source field, to compare graph findings with others.
FIELD_FOR = {(dt.value, et, attr): field for (dt, field), (et, attr) in FIELD_MAP.items()}


# Duplicate-detection methods, strongest first: an exact byte match beats a perceptual one.
DUPLICATE_METHODS = ["sha256", "phash"]


def _method_rank(method: object) -> int:
    return (
        DUPLICATE_METHODS.index(method) if method in DUPLICATE_METHODS else len(DUPLICATE_METHODS)
    )


def _duplicate_findings(app_id: str, checks: list[CheckResult]) -> list[Finding]:
    """One `duplicate` finding per (document, document it duplicates).

    An exact copy matches on both hashes, so provenance reports it twice (sha256 and pHash). They
    collapse into one finding with the strongest check's evidence and every method that matched."""
    groups: dict[tuple[str, tuple[str, ...] | None], list[CheckResult]] = {}
    for c in checks:
        for source in c.evidence.get("duplicates") or [None]:
            groups.setdefault((c.doc_id, tuple(source) if source else None), []).append(c)
    findings = []
    for (doc_id, source), group in groups.items():
        best = min(group, key=lambda c: _method_rank(c.evidence.get("hash_type")))
        methods = sorted(
            {str(c.evidence.get("hash_type", "unknown")) for c in group}, key=_method_rank
        )
        evidence = {"check": best.check, **best.evidence, "methods": methods}
        message = best.reason
        if source:
            evidence["duplicates"] = [list(source)]
            evidence["duplicate_of"] = {"app_id": source[0], "doc_id": source[-1]}
            how = " and ".join(methods)
            message = f"Duplicate of {source[-1]} in application {source[0]} ({how} match)"
        findings.append(
            Finding(
                finding_id=new_finding_id(),
                app_id=app_id,
                type=FindingType.DUPLICATE,
                severity=Severity.HIGH,
                layer=best.layer,
                doc_ids=[doc_id],
                message=message,
                evidence=evidence,
            )
        )
    return findings


def checks_to_findings(app_id: str, checks: list[CheckResult]) -> list[Finding]:
    """Turn non-clean provenance / forensic / verification checks into findings."""
    findings = []
    duplicates = []
    for c in checks:
        if c.check == "hash_duplicate":
            if c.status in FLAGGED_STATUSES:
                duplicates.append(c)
            continue
        if c.check == "issuer_lookup":
            ftype = ISSUER_FINDINGS.get(c.verification_status) if c.verification_status else None
            severity = Severity.HIGH
        elif c.status in FLAGGED_STATUSES and c.check in CHECK_FINDINGS:
            ftype, fixed = CHECK_FINDINGS[c.check]
            severity = fixed or c.severity
            if c.check == "ai_gen" and SEVERITY_RANK[severity] > SEVERITY_RANK[Severity.LOW]:
                severity = Severity.LOW  # an AI-generation score is only ever a weak signal
        else:
            continue
        if ftype is None:
            continue
        findings.append(
            Finding(
                finding_id=new_finding_id(),
                app_id=app_id,
                type=ftype,
                severity=severity,
                layer=c.layer,
                doc_ids=[c.doc_id],
                message=(
                    f"Preliminary indicator: {c.reason}"
                    if ftype is FindingType.FORENSIC_SIGNAL
                    else c.reason
                ),
                evidence={"check": c.check, **c.evidence},
            )
        )
    return findings + _duplicate_findings(app_id, duplicates)


def _field_key(app_id: str, f: Finding) -> tuple[str, str] | None:
    """(doc_id, source field) for an unreadable / undetermined finding about one field."""
    if f.type not in (FindingType.UNREADABLE, FindingType.UNDETERMINED):
        return None
    if len(f.doc_ids) != 1 or f.attribute is None:
        return None
    doc_type = f.doc_ids[0].removeprefix(f"{app_id}_")
    entity_type = f.entity.split(":")[0] if f.entity else ""
    # Graph findings name the claim attribute ("area"); rules and the timeline name the field.
    return f.doc_ids[0], FIELD_FOR.get((doc_type, entity_type, f.attribute), f.attribute)


def dedupe(app_id: str, findings: list[Finding]) -> list[Finding]:
    """Keep one unreadable / undetermined finding per (doc_id, field): the most severe, else the
    first. Rules, graph checks and the timeline can all notice the same unreadable field."""
    best: dict[tuple[str, str], Finding] = {}
    for f in findings:
        key = _field_key(app_id, f)
        if key and (
            key not in best or SEVERITY_RANK[f.severity] > SEVERITY_RANK[best[key].severity]
        ):
            best[key] = f
    return [f for f in findings if (k := _field_key(app_id, f)) is None or best[k] is f]


def evaluate_rules(
    app_id: str,
    extractions: list[ExtractionResult],
    checks: list[CheckResult],
    aicte_records: dict[str, Any] | None = None,
) -> list[Finding]:
    """Findings of every YAML rule: rules, graph checks and timeline, before de-duplication."""
    claims = build_claims(extractions, checks)
    return [
        *run_rules(app_id, extractions, load_checklist("eoa"), aicte_records),
        *graph_checks(app_id, claims),
        *timeline_checks(app_id, claims),
    ]


def run_reasoning(
    app_id: str,
    extractions: list[ExtractionResult],
    checks: list[CheckResult],
    aicte_records: dict[str, Any] | None = None,
) -> list[Finding]:
    """Run rules, graph checks and timeline, add findings from the checks, drop duplicates.

    `aicte_records` are records the pipeline fetched (e.g. {"payments": {txn_id: {...}}}); rules
    that need records which are absent skip that check. Nothing here touches the network."""
    findings = [
        *evaluate_rules(app_id, extractions, checks, aicte_records),
        *unit_findings(app_id, extractions),
        *checks_to_findings(app_id, checks),
    ]
    return dedupe(app_id, findings)


def _note(top: list[Finding], verification: VerificationStatus | None) -> str:
    """One sentence from the document's two most severe findings."""
    parts = [f.message.rstrip(".") for f in top[:2]]
    if verification in UNRESOLVED and len(parts) < 2:
        parts.append(UNRESOLVED[verification])
    if not parts:
        return "No issues found."
    sentence = "; ".join(parts)
    return f"{sentence[0].upper()}{sentence[1:]}."


def aggregate(
    app_id: str,
    findings: list[Finding],
    checks: list[CheckResult],
    doc_ids: list[str] | None = None,
) -> tuple[list[DocumentStatus], int]:
    """Per-document status by the §8.7 precedence; priority = 100*high + 10*medium + 1*low.

    Documents are those named by findings or checks, plus `doc_ids` (pass every submitted
    document so that clean ones are listed too)."""
    all_ids = [*(doc_ids or []), *(d for f in findings for d in f.doc_ids)]
    all_ids += [c.doc_id for c in checks]
    statuses = []
    for doc_id in dict.fromkeys(all_ids):
        mine = sorted(
            (f for f in findings if doc_id in f.doc_ids), key=lambda f: -SEVERITY_RANK[f.severity]
        )
        seen = [
            c.verification_status
            for c in checks
            if c.doc_id == doc_id and c.verification_status is not None
        ]
        verification = min(seen, key=VERIFICATION_ORDER.index, default=None)
        types, severities = {f.type for f in mine}, {f.severity for f in mine}
        if types & {FindingType.PROVENANCE_FAILURE, FindingType.SOURCE_MISMATCH}:
            overall = DocOverallStatus.FLAGGED
        elif Severity.HIGH in severities:
            overall = DocOverallStatus.FLAGGED
        elif verification in UNRESOLVED or FindingType.UNREADABLE in types:
            overall = DocOverallStatus.MANUAL_REVIEW_REQUIRED
        elif Severity.MEDIUM in severities:
            overall = DocOverallStatus.FLAGGED
        else:
            overall = DocOverallStatus.NO_ISSUES
        statuses.append(
            DocumentStatus(
                doc_id=doc_id,
                overall=overall,
                verification=verification,
                note=_note(mine, verification),
                finding_ids=[f.finding_id for f in mine],
            )
        )
    weights = {Severity.HIGH: 100, Severity.MEDIUM: 10, Severity.LOW: 1}
    return statuses, sum(weights.get(f.severity, 0) for f in findings)

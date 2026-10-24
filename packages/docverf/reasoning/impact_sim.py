"""Evidence-removal impact simulator (TRD §8.6)."""

from typing import Any

from docverf.reasoning.entity_graph import build_claims
from docverf.reasoning.rule_engine import load_rules
from docverf.reasoning.run import evaluate_rules
from docverf.reasoning.timeline import event_doc_id, rule_events
from docverf.schemas import CheckResult, Claim, ExtractionResult, Finding, FindingType, RuleOutcome

# Findings that mean "could not decide", as opposed to "the rule failed".
UNCERTAIN_TYPES = {FindingType.UNDETERMINED, FindingType.UNREADABLE}
PASS, FAIL, UNDETERMINED = RuleOutcome.PASS, RuleOutcome.FAIL, RuleOutcome.UNDETERMINED

# (rule set, rule, documents the rule reads). The documents are None for REQUIRED_DOCS, which
# reads the whole submission.
Catalogue = list[tuple[str, dict[str, Any], set[str] | None]]


def _catalogue(app_id: str, extractions: list[ExtractionResult], claims: list[Claim]) -> Catalogue:
    """Every YAML rule with the documents it reads, taken from the full submission."""
    out: Catalogue = []
    for rule in load_rules("rules"):
        docs = None
        if rule["type"] != "required_docs":
            doc_type = (rule.get("field") or rule["left"])["doc_type"]
            docs = {e.doc_id for e in extractions if e.doc_type.value == doc_type}
        out.append(("rules", rule, docs))
    for rule in load_rules("graph"):
        refs = [rule] if rule["type"] == "attribute_agree" else [rule["left"], rule["right"]]
        docs = {
            c.doc_id
            for c in claims
            for r in refs
            if c.entity.startswith(f"{r['entity_type']}:") and c.attribute == r["attribute"]
        }
        out.append(("graph", rule, docs))
    for rule in load_rules("timeline"):
        docs = {d for event in rule_events(rule) if (d := event_doc_id(app_id, event))}
        out.append(("timeline", rule, docs))
    return out


def _applicable(kind: str, docs: set[str] | None, present: set[str]) -> bool:
    """Could the rule have produced a result? A timeline rule needs all of its documents; the
    others need at least one claim (graph checks report too few claims themselves)."""
    if docs is None:
        return True
    return docs <= present if kind == "timeline" else bool(docs & present)


def _outcomes(
    app_id: str,
    extractions: list[ExtractionResult],
    checks: list[CheckResult],
    catalogue: Catalogue,
) -> dict[str, tuple[RuleOutcome, list[Finding]]]:
    """Per rule_id: fail if it produced a finding that is not just uncertainty (with those
    findings), undetermined if it produced only uncertainty or could not run, else pass."""
    present = {e.doc_id for e in extractions}
    findings = evaluate_rules(app_id, extractions, checks)
    outcomes: dict[str, tuple[RuleOutcome, list[Finding]]] = {}
    for kind, rule, docs in catalogue:
        mine = [f for f in findings if f.rule_id == rule["id"]]
        failing = [f for f in mine if f.type not in UNCERTAIN_TYPES]
        if failing:
            outcomes[rule["id"]] = (FAIL, failing)
        elif mine or not _applicable(kind, docs, present):
            outcomes[rule["id"]] = (UNDETERMINED, [])
        else:
            outcomes[rule["id"]] = (PASS, [])
    return outcomes


def _status(before: RuleOutcome, after: RuleOutcome) -> str:
    if before is after:
        return {PASS: "still_supported", FAIL: "still_failing", UNDETERMINED: "still_uncertain"}[
            before
        ]
    if after is UNDETERMINED:
        return "now_uncertain"
    if before is PASS:
        return "now_failing"
    return "changed"  # fail -> pass, or undetermined -> pass / fail


def _label(app_id: str, doc_ids: set[str]) -> str:
    """{'appx_land_deed', 'appx_noc'} -> 'land deed and noc'."""
    names = sorted(d.removeprefix(f"{app_id}_").replace("_", " ") for d in doc_ids) or ["document"]
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


def _subject(kind: str, rule: dict[str, Any]) -> str:
    if kind == "graph":
        refs = [rule] if rule["type"] == "attribute_agree" else [rule["left"], rule["right"]]
        text = " vs ".join(f"{r['entity_type']} {r['attribute']}" for r in refs).replace("_", " ")
        return text.capitalize()
    return f'Rule "{rule["description"]}"' if "description" in rule else f"Rule {rule['id']}"


def _message(
    app_id: str,
    status: str,
    kind: str,
    rule: dict[str, Any],
    docs: set[str] | None,
    present: set[str],
    excluded: set[str],
    outcome: tuple[RuleOutcome, list[Finding]],
    before: RuleOutcome,
) -> str:
    """One plain sentence about what happened to the rule."""
    subject = _subject(kind, rule)
    if status in ("now_uncertain", "still_uncertain"):
        remaining, lost = (docs or set()) & present, (docs or set()) & excluded
        if kind == "graph" and remaining:
            verb = "remains" if len(remaining) == 1 else "remain"
            why = f"only the {_label(app_id, remaining)} {verb}"
        elif lost:
            why = f"the {_label(app_id, lost)} {'was' if len(lost) == 1 else 'were'} removed"
        else:
            why = "no source document is available"
        action = "cross-checked" if kind == "graph" else "checked"
        when = "can no longer be" if status == "now_uncertain" else "still cannot be"
        return f"{subject} {when} {action}: {why}."
    if status in ("now_failing", "still_failing"):
        failing = "; ".join(f.message.rstrip(".") for f in outcome[1])
        return f"{'Now' if status == 'now_failing' else 'Still'} fails: {failing}."
    if status == "still_supported":
        return f"{subject} is still supported by the remaining documents."
    return (
        f"{subject} changed from {before.value} to {outcome[0].value} "
        f"without the {_label(app_id, excluded)}."
    )


# TRD §8.6 gives simulate_exclusion(app_id, doc_ids), which has no way to receive the documents
# to re-evaluate, so extractions and checks are passed in and doc_ids is named exclude_doc_ids.
def simulate_exclusion(
    app_id: str,
    extractions: list[ExtractionResult],
    checks: list[CheckResult],
    exclude_doc_ids: list[str],
) -> dict[str, Any]:
    """Re-evaluate every rule with `exclude_doc_ids` (and their checks) removed.

    Returns {"excluded": [...], "conclusions": [{rule_id, before, after, status, message}]}
    where status is still_supported | still_failing | still_uncertain | now_uncertain |
    now_failing | changed."""
    excluded = set(exclude_doc_ids)
    unknown = excluded - {e.doc_id for e in extractions}
    if unknown:
        raise ValueError(f"unknown document id(s): {sorted(unknown)}")
    kept = [e for e in extractions if e.doc_id not in excluded]
    kept_checks = [c for c in checks if c.doc_id not in excluded]

    catalogue = _catalogue(app_id, extractions, build_claims(extractions, checks))
    before = _outcomes(app_id, extractions, checks, catalogue)
    after = _outcomes(app_id, kept, kept_checks, catalogue)
    present = {e.doc_id for e in kept}
    conclusions = []
    for kind, rule, docs in catalogue:
        b, a = before[rule["id"]][0], after[rule["id"]]
        status = _status(b, a[0])
        conclusions.append(
            {
                "rule_id": rule["id"],
                "before": b.value,
                "after": a[0].value,
                "status": status,
                "message": _message(app_id, status, kind, rule, docs, present, excluded, a, b),
            }
        )
    return {"excluded": list(dict.fromkeys(exclude_doc_ids)), "conclusions": conclusions}

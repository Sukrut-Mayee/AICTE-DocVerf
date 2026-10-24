"""YAML rule engine (TRD §8.4)."""

import operator
import re
import uuid
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from docverf.config import get_settings
from docverf.schemas import (
    ExtractionResult,
    Finding,
    FindingType,
    Layer,
    RuleOutcome,
    Severity,
)

RULES_DIR = Path(__file__).resolve().parents[3] / "rules"  # config.py has no RULES_DIR
_OPS = {
    "eq": operator.eq,
    "ne": operator.ne,
    "gt": operator.gt,
    "gte": operator.ge,
    "lt": operator.lt,
    "lte": operator.le,
}


def load_rules(subdir: str = "rules") -> list[dict[str, Any]]:
    """Concatenate every rules/<subdir>/*.yaml list, in file-name order."""
    rules: list[dict[str, Any]] = []
    for path in sorted((RULES_DIR / subdir).glob("*.yaml")):
        rules.extend(yaml.safe_load(path.read_text(encoding="utf-8")))
    return rules


def load_checklist(name: str = "eoa") -> dict[str, Any]:
    return yaml.safe_load((RULES_DIR / "checklists" / f"{name}.yaml").read_text(encoding="utf-8"))


def new_finding_id() -> str:
    return f"f_{uuid.uuid4().hex[:8]}"  # TRD §5.3


def new_finding(
    app_id: str,
    rule: dict[str, Any],
    message: str,
    ftype: FindingType | None = None,
    severity: Severity | None = None,
    **fields: Any,
) -> Finding:
    """Build a Finding from a rule's YAML header; ftype/severity override it (undetermined)."""
    return Finding(
        finding_id=new_finding_id(),
        app_id=app_id,
        type=ftype or FindingType(rule["finding_type"]),
        severity=severity or Severity(rule["severity"]),
        layer=Layer(rule["layer"]) if "layer" in rule else None,
        rule_id=rule["id"],
        message=message,
        **fields,
    )


def _check_field(rule: dict[str, Any], value: Any) -> tuple[RuleOutcome, dict[str, Any], Any, str]:
    """Evaluate one rule against one confident field value.

    Returns the outcome, the values for the message template, what the value was compared to,
    and (for undetermined) the reason."""
    kind = rule["type"]
    if kind == "field_compare":
        right = getattr(get_settings(), rule["right"]["config"])
        try:  # extractions carry dates as ISO strings; settings carry date objects
            left = date.fromisoformat(value) if isinstance(right, date) else value
        except (TypeError, ValueError):
            return RuleOutcome.UNDETERMINED, {}, str(right), f"value {value!r} is not a valid date"
        ok = _OPS[rule["op"]](left, right)
        shown, compared_to = {"left": str(left), "right": str(right)}, str(right)
    elif kind == "field_regex":
        ok = re.search(rule["pattern"], str(value)) is not None
        shown, compared_to = {"value": value}, rule["pattern"]
    elif kind == "field_equals":
        ok, shown, compared_to = value == rule["value"], {"value": value}, rule["value"]
    else:
        raise ValueError(f"unsupported rule type {kind!r} in rule {rule['id']}")
    return (RuleOutcome.PASS if ok else RuleOutcome.FAIL), shown, compared_to, ""


def _evaluate(
    app_id: str,
    rule: dict[str, Any],
    extractions: list[ExtractionResult],
    checklist: dict[str, Any],
) -> list[tuple[RuleOutcome, Finding | None]]:
    """One (outcome, finding) per document the rule applies to; finding only on fail/undetermined.

    A rule does not apply to a document type that is absent (REQUIRED_DOCS reports that)."""
    if rule["type"] == "required_docs":
        present = {e.doc_type.value for e in extractions}
        return [
            (
                RuleOutcome.FAIL,
                new_finding(app_id, rule, rule["message"].format(doc_type=doc_type)),
            )
            if doc_type not in present
            else (RuleOutcome.PASS, None)
            for doc_type in checklist["required_docs"]
        ]

    ref = rule.get("field") or rule["left"]
    field = ref["field"]
    threshold = get_settings().CONFIDENCE_THRESHOLD
    results: list[tuple[RuleOutcome, Finding | None]] = []
    for doc in (e for e in extractions if e.doc_type.value == ref["doc_type"]):
        fv = doc.fields.get(field)
        reason = ""
        if fv is None:
            reason = "the field is missing"
        elif fv.confidence < threshold:
            reason = f"confidence {fv.confidence:.2f} is below the threshold {threshold:.2f}"
        outcome, compared_to = RuleOutcome.UNDETERMINED, None
        shown: dict[str, Any] = {}
        if not reason:
            assert fv is not None
            outcome, shown, compared_to, reason = _check_field(rule, fv.value)
        if outcome is RuleOutcome.PASS:
            results.append((outcome, None))
            continue
        evidence = {
            "field": field,
            "value": fv.value if fv else None,
            "confidence": fv.confidence if fv else None,
            "page": fv.page if fv else None,
            "bbox": fv.bbox if fv else None,
            "compared_to": compared_to,
        }
        if outcome is RuleOutcome.UNDETERMINED:
            finding = new_finding(
                app_id,
                rule,
                f"Cannot evaluate {rule['id']} on {doc.doc_id}: {field} - {reason}",
                ftype=FindingType.UNDETERMINED,
                severity=Severity.INFO,
                doc_ids=[doc.doc_id],
                attribute=field,
                evidence=evidence,
            )
        else:
            finding = new_finding(
                app_id,
                rule,
                rule["message"].format_map(shown),
                doc_ids=[doc.doc_id],
                attribute=field,
                evidence=evidence,
            )
        results.append((outcome, finding))
    return results


def run_rules(
    app_id: str,
    extractions: list[ExtractionResult],
    checklist: dict[str, Any],
    aicte_records: dict[str, Any],
) -> list[Finding]:
    """Evaluate rules/rules/*.yaml and the checklist.

    Each rule yields pass / fail / undetermined. A fail gives the rule's finding; undetermined
    (field missing or low confidence in a present document) gives an `undetermined` info finding.
    `aicte_records` is unused until the P1 rules (TER_PAID, INTAKE_WITHIN_APPROVED).
    """
    return [
        finding
        for rule in load_rules("rules")
        for _, finding in _evaluate(app_id, rule, extractions, checklist)
        if finding is not None
    ]

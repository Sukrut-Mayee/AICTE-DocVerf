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


def new_finding(app_id: str, rule: dict[str, Any], message: str, **fields: Any) -> Finding:
    """Build a Finding from a rule's YAML header (type, severity, optional layer)."""
    return Finding(
        finding_id=f"f_{uuid.uuid4().hex[:8]}",
        app_id=app_id,
        type=FindingType(rule["finding_type"]),
        severity=Severity(rule["severity"]),
        layer=Layer(rule["layer"]) if "layer" in rule else None,
        rule_id=rule["id"],
        message=message,
        **fields,
    )


def _check_field(rule: dict[str, Any], value: Any) -> tuple[RuleOutcome, dict[str, Any]]:
    """Evaluate one rule against one (confident) field value; return the outcome and the
    values to show in the message."""
    kind = rule["type"]
    if kind == "field_compare":
        right = getattr(get_settings(), rule["right"]["config"])
        try:  # extractions carry dates as ISO strings; settings carry date objects
            left = date.fromisoformat(value) if isinstance(right, date) else value
        except (TypeError, ValueError):
            return RuleOutcome.UNDETERMINED, {}
        ok = _OPS[rule["op"]](left, right)
        shown = {"left": str(left), "right": str(right)}
    elif kind == "field_regex":
        ok, shown = re.search(rule["pattern"], str(value)) is not None, {"value": value}
    elif kind == "field_equals":
        ok, shown = value == rule["value"], {"value": value}
    else:
        raise ValueError(f"unsupported rule type {kind!r} in rule {rule['id']}")
    return (RuleOutcome.PASS if ok else RuleOutcome.FAIL), shown


def _evaluate(
    app_id: str,
    rule: dict[str, Any],
    extractions: list[ExtractionResult],
    checklist: dict[str, Any],
) -> list[tuple[RuleOutcome, Finding | None]]:
    """One (outcome, finding-if-failed) per document the rule applies to."""
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
    threshold = get_settings().CONFIDENCE_THRESHOLD
    results: list[tuple[RuleOutcome, Finding | None]] = []
    for doc in (e for e in extractions if e.doc_type.value == ref["doc_type"]):
        fv = doc.fields.get(ref["field"])
        if fv is None or fv.confidence < threshold:  # unreadable is not the same as wrong
            results.append((RuleOutcome.UNDETERMINED, None))
            continue
        outcome, shown = _check_field(rule, fv.value)
        if outcome is not RuleOutcome.FAIL:
            results.append((outcome, None))
            continue
        finding = new_finding(
            app_id,
            rule,
            rule["message"].format_map(shown),
            doc_ids=[doc.doc_id],
            evidence={"field": ref["field"], "confidence": fv.confidence, **shown},
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

    Each rule yields pass / fail / undetermined; only a fail produces a Finding.
    `aicte_records` is unused until the P1 rules (TER_PAID, INTAKE_WITHIN_APPROVED).
    """
    return [
        finding
        for rule in load_rules("rules")
        for _, finding in _evaluate(app_id, rule, extractions, checklist)
        if finding is not None
    ]

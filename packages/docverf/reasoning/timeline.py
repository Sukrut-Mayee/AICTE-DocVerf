"""Timeline contradiction engine (TRD §8.5)."""

from datetime import date
from typing import Any

from docverf.config import get_settings
from docverf.reasoning.rule_engine import load_rules, new_finding, rule_title
from docverf.schemas import Claim, Finding, FindingType, Severity

# YAML event prefixes that are not the doc_type value itself.
DOC_TYPE_ALIASES = {"form": "application_form", "accreditation": "accreditation_cert"}


def event_doc_id(app_id: str, event: str) -> str:
    """The document an event name such as 'noc.issue_date' is read from. The trust registration
    date is taken from the application form; 'config.X' needs no document ('')."""
    prefix = event.split(".", 1)[0]
    if prefix == "config":
        return ""
    prefix = "form" if prefix == "trust" else prefix
    return f"{app_id}_{DOC_TYPE_ALIASES.get(prefix, prefix)}"


def rule_events(rule: dict[str, Any]) -> list[str]:
    """The event names a timeline rule compares (before/after, or within/start/end)."""
    if "before" in rule:
        return [rule["before"], rule["after"]]
    return [rule["within"], rule["start"], rule["end"]]


def timeline_checks(app_id: str, claims: list[Claim]) -> list[Finding]:
    """Evaluate rules/timeline/*.yaml. A missing or low-confidence date is `undetermined`
    (severity info), never a violation. A rule whose document is absent does not apply
    (REQUIRED_DOCS reports that)."""
    settings = get_settings()
    findings: list[Finding] = []

    def locate(event: str) -> tuple[str, Claim | None]:
        """'noc.issue_date' -> (that document's id, its claim). The trust registration date is
        the trust's claim, taken from the application form. 'config.X' needs no document."""
        prefix, attribute = event.split(".", 1)
        doc_id = event_doc_id(app_id, event)
        claim = next(
            (
                c
                for c in claims
                if c.doc_id == doc_id
                and c.attribute == attribute
                and (
                    c.entity.startswith("trust:")
                    if prefix == "trust"
                    else c.entity.startswith("doc:")
                )
            ),
            None,
        )
        return doc_id, claim

    def read(event: str) -> tuple[date | None, str, Claim | None, str]:
        """(date, doc_id, claim, why-not). config constants come from docverf.config."""
        if event.startswith("config."):
            return getattr(settings, event.removeprefix("config.")), "", None, ""
        doc_id, claim = locate(event)
        if claim is None:
            return None, doc_id, None, f"{event} is missing"
        if claim.confidence < settings.CONFIDENCE_THRESHOLD:
            return (
                None,
                doc_id,
                claim,
                (
                    f"{event} has confidence {claim.confidence:.2f}, below "
                    f"the threshold {settings.CONFIDENCE_THRESHOLD:.2f}"
                ),
            )
        try:
            return date.fromisoformat(str(claim.value)), doc_id, claim, ""
        except ValueError:
            return None, doc_id, claim, f"{event} value {claim.value!r} is not a valid date"

    for rule in load_rules("timeline"):
        rule = {"layer": "B", **rule}  # timeline checks are Layer B (consistency)
        read_events = {e: read(e) for e in rule_events(rule)}
        # A rule does not apply when one of its documents is absent altogether.
        if any(
            doc_id and not any(c.doc_id == doc_id for c in claims)
            for _, doc_id, _, _ in read_events.values()
        ):
            continue
        broken = [(e, r) for e, r in read_events.items() if r[0] is None]
        if broken:
            event, (_, doc_id, claim, why) = broken[0]
            findings.append(
                new_finding(
                    app_id,
                    rule,
                    f'Cannot check "{rule_title(rule)}": {why}',
                    ftype=FindingType.UNDETERMINED,
                    severity=Severity.INFO,
                    doc_ids=[doc_id],
                    entity=claim.entity if claim else None,
                    attribute=event.split(".", 1)[1],
                    claims=[claim] if claim else [],
                )
            )
            continue

        d = {e: r[0] for e, r in read_events.items() if r[0] is not None}
        if "before" in rule:
            before, after = d[rule["before"]], d[rule["after"]]
            violated = after < before
            default = f"{rule['after']} {after} is earlier than {rule['before']} {before}"
            shown: dict[str, Any] = {"before": before, "after": after}
        else:
            value, start, end = d[rule["within"]], d[rule["start"]], d[rule["end"]]
            violated = not (start <= value <= end)
            default = f"{rule['within']} {value} is outside {start} to {end}"
            shown = {"value": value, "start": start, "end": end}
        if violated:
            used = [r[2] for r in read_events.values() if r[2] is not None]
            findings.append(
                new_finding(
                    app_id,
                    rule,
                    rule.get("message", default).format_map(shown),
                    ftype=FindingType.TIMELINE_VIOLATION,
                    doc_ids=list(dict.fromkeys(c.doc_id for c in used)),
                    claims=used,
                    evidence={k: str(v) for k, v in shown.items()},
                )
            )
    return findings

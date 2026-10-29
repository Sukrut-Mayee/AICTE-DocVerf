"""Cross-institution reuse, P1 (TRD §7.3, §19 Q4).

Flags a land parcel (survey number, plus village / district when both sides state them) or a
trust registration number that an earlier application already claims under a DIFFERENT institute.
The same institute re-submitting is not flagged. Photo reuse is already reported by the
`duplicate` finding (provenance hash index), so photos are not flagged a second time here.

Unlike TRD §19 Q4's `(app_id, claims, hash_index)`, this takes the extractions (they carry the
institute id and the deed's village / district) and `prior`, the earlier applications' extractions.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from docverf.reasoning.entity_resolution import normalize_id, normalize_name
from docverf.reasoning.rule_engine import new_finding_id
from docverf.schemas import (
    DocType,
    ExtractionResult,
    Finding,
    FindingType,
    Layer,
    Severity,
)

RULES = {
    "land_parcel": (
        "CROSS_INSTITUTION_LAND",
        "The same land parcel should not be claimed by more than one institute",
        "Land survey number",
    ),
    "trust": (
        "CROSS_INSTITUTION_TRUST",
        "The same trust registration should not be claimed by more than one institute",
        "Trust registration number",
    ),
}


@dataclass(frozen=True)
class Claimed:
    """One land parcel or trust an application claims, and the document that states it."""

    kind: str  # "land_parcel" | "trust"
    value: str  # as written
    key: str  # normalised, what matches
    locality: tuple[str, str]  # (village, district), normalised; "" when not stated
    app_id: str
    institute_id: str  # normalised permanent id, else normalised name
    institute_name: str
    doc_id: str


def _value(ex: ExtractionResult | None, name: str) -> str:
    fv = ex.fields.get(name) if ex else None
    return "" if fv is None or fv.value is None else str(fv.value).strip()


def claimed_entities(extractions: list[ExtractionResult]) -> list[Claimed]:
    """The land parcel and the trust one application claims (empty for a missing ID)."""
    by_type = {e.doc_type: e for e in extractions}
    form, deed = by_type.get(DocType.APPLICATION_FORM), by_type.get(DocType.LAND_DEED)
    if not extractions:
        return []
    app_id = extractions[0].app_id
    name = _value(form, "institute_name")
    institute_id = normalize_id(_value(form, "aicte_permanent_id")) or normalize_name(name)
    base = {"app_id": app_id, "institute_id": institute_id, "institute_name": name}
    out = []
    survey = _value(deed, "survey_no") or _value(form, "land_survey_no")
    doc = deed or form
    if survey and doc:
        locality = (
            normalize_name(_value(deed, "village")),
            normalize_name(_value(deed, "district")),
        )
        out.append(
            Claimed(
                "land_parcel", survey, normalize_id(survey), locality, doc_id=doc.doc_id, **base
            )
        )
    trust = _value(form, "trust_reg_no")
    if trust and form:
        out.append(
            Claimed("trust", trust, normalize_id(trust), ("", ""), doc_id=form.doc_id, **base)
        )
    return out


def _same_place(a: tuple[str, str], b: tuple[str, str]) -> bool:
    """Localities agree wherever both state a value; an unstated one never rules a match out."""
    return all(not x or not y or x == y for x, y in zip(a, b, strict=True))


def _matches(mine: Claimed, other: Claimed) -> bool:
    return (
        mine.kind == other.kind
        and mine.key == other.key
        and mine.institute_id != other.institute_id
        and _same_place(mine.locality, other.locality)
    )


def check_cross_institution(
    app_id: str, extractions: list[ExtractionResult], prior: list[list[ExtractionResult]]
) -> list[Finding]:
    """One high `relationship_violation` per land parcel / trust that an earlier application
    claims under a different institute. `prior` holds the earlier applications' extractions."""
    earlier = [c for ex in prior for c in claimed_entities(ex) if c.app_id != app_id]
    findings = []
    for mine in claimed_entities(extractions):
        others = [c for c in earlier if _matches(mine, c)]
        if not others:
            continue
        rule_id, description, label = RULES[mine.kind]
        also = list(
            {
                o.app_id: {
                    "app_id": o.app_id,
                    "institute_name": o.institute_name,
                    "doc_id": o.doc_id,
                }
                for o in others
            }.values()
        )
        place = ", ".join(p for p in (_title(mine.locality[0]), _title(mine.locality[1])) if p)
        who = ", ".join(f"{a['institute_name']} ({a['app_id']})" for a in also)
        findings.append(
            Finding(
                finding_id=new_finding_id(),
                app_id=app_id,
                type=FindingType.RELATIONSHIP_VIOLATION,
                severity=Severity.HIGH,
                layer=Layer.B,
                rule_id=rule_id,
                entity=f"{mine.kind}:{mine.value}",
                attribute="survey_no" if mine.kind == "land_parcel" else "reg_no",
                doc_ids=[mine.doc_id],
                message=(
                    f"{label} {mine.value}{f' ({place})' if place else ''} is reused across "
                    f"institutions: also claimed by {who}"
                ),
                evidence={
                    "rule_description": description,
                    "entity": mine.kind,
                    "value": mine.value,
                    "also_claimed_by": also,
                },
            )
        )
    return findings


def _title(normalised: str) -> str:
    return normalised.title()


def load_prior(pipeline_dir: Path, app_id: str) -> list[list[ExtractionResult]]:
    """Extractions of every application in `pipeline_dir` with a smaller id than `app_id`
    (applications are processed in id order, so those are the earlier ones)."""
    prior = []
    for path in sorted(pipeline_dir.glob("app*.json")):
        if path.stem >= app_id:
            continue
        try:
            raw: dict[str, Any] = json.loads(path.read_text("utf-8"))
            prior.append([ExtractionResult.model_validate(e) for e in raw["extractions"]])
        except (OSError, ValueError, KeyError):
            continue  # an unreadable earlier output must not stop this application
    return prior


def shared_entities(applications: list[list[ExtractionResult]]) -> list[dict[str, Any]]:
    """Every land parcel / trust registration that two or more institutes claim, with who claims
    it (for the officer console's network view)."""
    clusters: list[list[Claimed]] = []
    for claim in (c for ex in applications for c in claimed_entities(ex)):
        for cluster in clusters:
            head = cluster[0]
            if (
                head.kind == claim.kind
                and head.key == claim.key
                and any(_same_place(m.locality, claim.locality) for m in cluster)
            ):
                cluster.append(claim)
                break
        else:
            clusters.append([claim])
    shared = []
    for cluster in clusters:
        if len({c.institute_id for c in cluster}) < 2:
            continue
        head = cluster[0]
        shared.append(
            {
                "id": f"{head.kind}:{head.key}:{'/'.join(head.locality)}",
                "kind": head.kind,
                "value": head.value,
                "applications": [
                    {"app_id": c.app_id, "institute_name": c.institute_name, "doc_id": c.doc_id}
                    for c in cluster
                ],
            }
        )
    return shared

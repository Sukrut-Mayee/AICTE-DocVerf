"""Claims and entity-graph consistency checks (TRD §7.2, §8.1-§8.3)."""

from collections.abc import Callable
from typing import Any

from docverf.config import get_settings
from docverf.reasoning.entity_resolution import names_match, normalize_id
from docverf.reasoning.rule_engine import load_rules, new_finding, new_finding_id, rule_title
from docverf.schemas import (
    AuthorityTier,
    CheckResult,
    Claim,
    DocType,
    ExtractionResult,
    FieldValue,
    Finding,
    FindingType,
    Layer,
    Severity,
    VerificationStatus,
)
from docverf.units import acres_per_unit, to_acres

# TRD §8.1: (doc_type, field) -> (entity type, attribute). Area fields are converted to acres.
FIELD_MAP = {
    (DocType.APPLICATION_FORM, "institute_name"): ("institute", "name"),
    (DocType.AFFIDAVIT, "institute_name"): ("institute", "name"),
    (DocType.NOC, "institute_name"): ("institute", "name"),
    (DocType.ACCREDITATION_CERT, "institute_name"): ("institute", "name"),
    (DocType.APPLICATION_FORM, "application_no"): ("institute", "application_no"),
    (DocType.AFFIDAVIT, "application_no"): ("institute", "application_no"),
    (DocType.APPLICATION_FORM, "trust_name"): ("trust", "name"),
    (DocType.APPLICATION_FORM, "trust_reg_date"): ("trust", "reg_date"),
    (DocType.APPLICATION_FORM, "land_survey_no"): ("land_parcel", "survey_no"),
    (DocType.LAND_DEED, "survey_no"): ("land_parcel", "survey_no"),
    (DocType.APPLICATION_FORM, "land_area"): ("land_parcel", "area"),
    (DocType.LAND_DEED, "area"): ("land_parcel", "area"),
    (DocType.AFFIDAVIT, "land_area_declared"): ("land_parcel", "area"),
    (DocType.LAND_DEED, "owner_name"): ("land_parcel", "owner"),
    (DocType.LAND_DEED, "mortgage_status"): ("land_parcel", "mortgage_status"),
}
# A document is its own entity for its own dates: these become claims on "doc:{doc_id}" with the
# field name as the attribute. The one exception is the trust registration date, which belongs to
# the trust (trust:{trust_reg_no}.reg_date, in FIELD_MAP above).
TIMELINE_FIELDS = {
    (DocType.APPLICATION_FORM, "application_date"),
    (DocType.LAND_DEED, "registration_date"),
    (DocType.NOC, "issue_date"),
    (DocType.NOC, "valid_until"),
    (DocType.AFFIDAVIT, "date"),
    (DocType.ACCREDITATION_CERT, "valid_from"),
    (DocType.ACCREDITATION_CERT, "valid_to"),
}
# TRD §6: default authority tier by doc type.
DEFAULT_TIER = {
    DocType.APPLICATION_FORM: AuthorityTier.SELF_DECLARED,
    DocType.AFFIDAVIT: AuthorityTier.SELF_DECLARED,
    DocType.LAB_PHOTO: AuthorityTier.SELF_DECLARED,
    DocType.LAND_DEED: AuthorityTier.THIRD_PARTY,
    DocType.NOC: AuthorityTier.THIRD_PARTY,
    DocType.ACCREDITATION_CERT: AuthorityTier.THIRD_PARTY,
}
UPGRADING_CHECKS = {"pdf_signature", "qr", "issuer_lookup"}


def _entity_ids(extractions: list[ExtractionResult]) -> dict[str, str]:
    """Prototype simplification: one entity per type per application (institute, trust,
    land_parcel), identified by the application_form's strong IDs. If the form or an ID is
    missing, the app_id stands in so that claims of one application still group together."""
    form = next((e for e in extractions if e.doc_type is DocType.APPLICATION_FORM), None)

    def strong(field: str, norm: bool = False) -> str:
        fv = form.fields.get(field) if form else None
        if fv is None:
            return extractions[0].app_id if extractions else ""
        return normalize_id(str(fv.value)) if norm else str(fv.value)

    return {
        "institute": f"institute:{strong('aicte_permanent_id')}",
        "trust": f"trust:{strong('trust_reg_no')}",
        "land_parcel": f"land_parcel:{strong('land_survey_no', norm=True)}",
    }


def _unknown_unit(doc_type: DocType, name: str, fv: FieldValue) -> bool:
    """An area field whose unit we cannot convert to acres."""
    return (
        FIELD_MAP.get((doc_type, name), ("", ""))[1] == "area" and acres_per_unit(fv.unit) is None
    )


def unit_findings(app_id: str, extractions: list[ExtractionResult]) -> list[Finding]:
    """One undetermined (info) finding per area whose unit is unknown; build_claims leaves those
    areas out, so they never cause or hide a conflict."""
    return [
        Finding(
            finding_id=new_finding_id(),
            app_id=app_id,
            type=FindingType.UNDETERMINED,
            severity=Severity.INFO,
            layer=Layer.B,
            doc_ids=[doc.doc_id],
            attribute=name,
            message=(
                f"Cannot compare {name} in {doc.doc_id.removeprefix(f'{app_id}_')}: "
                + (f"unknown area unit {fv.unit!r}" if fv.unit else "the area has no unit")
            ),
            evidence={
                "field": name,
                "value": fv.value,
                "unit": fv.unit,
                "confidence": fv.confidence,
                "page": fv.page,
                "bbox": fv.bbox,
            },
        )
        for doc in extractions
        for name, fv in doc.fields.items()
        if _unknown_unit(doc.doc_type, name, fv)
    ]


def build_claims(extractions: list[ExtractionResult], checks: list[CheckResult]) -> list[Claim]:
    """Map fields to entity.attribute (§8.1); authority tier from §6, upgraded to issuer_verified
    by a verified pdf_signature / qr / issuer_lookup check."""
    entities = _entity_ids(extractions)
    verified_docs = {
        c.doc_id
        for c in checks
        if c.check in UPGRADING_CHECKS and c.verification_status is VerificationStatus.VERIFIED
    }
    claims = []
    for doc in extractions:
        tier = (
            AuthorityTier.ISSUER_VERIFIED
            if doc.doc_id in verified_docs
            else DEFAULT_TIER[doc.doc_type]
        )
        for name, fv in doc.fields.items():
            if (doc.doc_type, name) in FIELD_MAP:
                entity_type, attribute = FIELD_MAP[(doc.doc_type, name)]
                entity = entities[entity_type]
            elif (doc.doc_type, name) in TIMELINE_FIELDS:
                entity, attribute = f"doc:{doc.doc_id}", name
            else:
                continue
            if _unknown_unit(doc.doc_type, name, fv):  # reported by unit_findings
                continue
            value = to_acres(fv.value, fv.unit) if attribute == "area" else fv.value
            claims.append(
                Claim(
                    doc_id=doc.doc_id,
                    entity=entity,
                    attribute=attribute,
                    value=value,
                    authority=tier,
                    confidence=fv.confidence,
                    page=fv.page,
                    bbox=fv.bbox,
                )
            )
    return claims


SEVERITY_RANK = {Severity.INFO: 0, Severity.LOW: 1, Severity.MEDIUM: 2, Severity.HIGH: 3}


def _pair_severity(a: AuthorityTier, b: AuthorityTier) -> Severity:
    """TRD §8.3: issuer_verified vs anything, or third_party vs self_declared -> high;
    two claims of the same tier (third/third, self/self) -> medium."""
    if AuthorityTier.ISSUER_VERIFIED in (a, b) or a != b:
        return Severity.HIGH
    return Severity.MEDIUM


def _matcher(tolerance: dict[str, Any]) -> Callable[[Any, Any], bool]:
    """Turn a graph rule's tolerance (relative / fuzzy / exact) into an 'agree?' function.
    Area claims are already in acres (build_claims), so the rule's `unit` needs no conversion."""
    if "relative" in tolerance:
        return lambda a, b: abs(a - b) <= tolerance["relative"] * max(abs(a), abs(b))
    if "fuzzy" in tolerance:
        return lambda a, b: names_match(str(a), str(b), tolerance["fuzzy"])
    if tolerance.get("exact"):
        return lambda a, b: normalize_id(str(a)) == normalize_id(str(b))
    raise ValueError(f"unsupported tolerance {tolerance!r}")


def graph_checks(app_id: str, claims: list[Claim]) -> list[Finding]:
    """Evaluate rules/graph/*.yaml: attribute_agree and relationship_equal (§8.2, §8.3).

    Claims below CONFIDENCE_THRESHOLD never take part in a comparison; each gives one
    `unreadable` finding, however many rules look at it. Too few usable claims gives an
    `undetermined` info finding, never a conflict."""
    threshold = get_settings().CONFIDENCE_THRESHOLD
    findings: list[Finding] = []
    reported: set[tuple[str, str, str]] = set()

    def label(doc_id: str) -> str:
        return doc_id.removeprefix(f"{app_id}_")

    def usable(rule: dict[str, Any], entity_type: str, attribute: str) -> tuple[list, list]:
        """(all claims for entity_type.attribute, the confident ones)."""
        selected = [
            c for c in claims if c.entity.startswith(f"{entity_type}:") and c.attribute == attribute
        ]
        keep = [c for c in selected if c.confidence >= threshold]
        for c in selected:
            key = (c.doc_id, c.entity, c.attribute)
            if c.confidence < threshold and key not in reported:
                reported.add(key)
                findings.append(
                    new_finding(
                        app_id,
                        rule,
                        f"{c.attribute} in {label(c.doc_id)} could not be read reliably "
                        f"(confidence {c.confidence:.2f}); please confirm it manually",
                        ftype=FindingType.UNREADABLE,
                        severity=Severity.LOW,
                        doc_ids=[c.doc_id],
                        entity=c.entity,
                        attribute=c.attribute,
                        claims=[c],
                        evidence={
                            "value": c.value,
                            "confidence": c.confidence,
                            "page": c.page,
                            "bbox": c.bbox,
                        },
                    )
                )
        return selected, keep

    def undetermined(rule: dict[str, Any], selected: list[Claim], why: str) -> Finding:
        return new_finding(
            app_id,
            rule,
            f'Cannot check "{rule_title(rule)}": {why}',
            ftype=FindingType.UNDETERMINED,
            severity=Severity.INFO,
            doc_ids=list(dict.fromkeys(c.doc_id for c in selected)),
            entity=selected[0].entity,
            attribute=selected[0].attribute,
            claims=selected,
        )

    for rule in load_rules("graph"):
        rule = {"layer": "B", **rule}  # graph checks are Layer B (consistency)
        same = _matcher(rule["tolerance"])
        if rule["type"] == "attribute_agree":
            selected, keep = usable(rule, rule["entity_type"], rule["attribute"])
            need = rule.get("min_claims", 2)
            if len(keep) < need:
                if selected:  # nothing asserted at all means nothing to check
                    why = f"only {len(keep)} readable claim(s), {need} needed"
                    findings.append(undetermined(rule, selected, why))
                continue
            clusters: list[list[Claim]] = []
            for c in keep:
                for cluster in clusters:
                    if same(cluster[0].value, c.value):
                        cluster.append(c)
                        break
                else:
                    clusters.append([c])
            if len(clusters) > 1:
                severity = max(
                    (
                        _pair_severity(x.authority, y.authority)
                        for i, ca in enumerate(clusters)
                        for cb in clusters[i + 1 :]
                        for x in ca
                        for y in cb
                    ),
                    key=SEVERITY_RANK.__getitem__,
                    default=Severity.INFO,
                )
                kind = rule["entity_type"].replace("_", " ")
                shown = " vs ".join(
                    f"{cl[0].value} in {', '.join(label(c.doc_id) for c in cl)}" for cl in clusters
                )
                findings.append(
                    new_finding(
                        app_id,
                        rule,
                        f"{kind.capitalize()} {rule['attribute']} conflicts: {shown}",
                        ftype=FindingType.ATTRIBUTE_CONFLICT,
                        severity=severity,
                        doc_ids=list(dict.fromkeys(c.doc_id for c in keep)),
                        entity=keep[0].entity,
                        attribute=rule["attribute"],
                        claims=keep,
                        evidence={
                            "clusters": [
                                {"value": cl[0].value, "doc_ids": [c.doc_id for c in cl]}
                                for cl in clusters
                            ]
                        },
                    )
                )
        elif rule["type"] == "relationship_equal":
            l_sel, l_keep = usable(rule, **rule["left"])
            r_sel, r_keep = usable(rule, **rule["right"])
            if not (l_keep and r_keep):
                if l_sel or r_sel:
                    side = "left" if not l_keep else "right"
                    findings.append(undetermined(rule, l_sel + r_sel, f"no readable {side} claim"))
                continue
            for left in l_keep:
                for right in r_keep:
                    if not same(left.value, right.value):
                        findings.append(
                            new_finding(
                                app_id,
                                rule,
                                rule["message"].format(left=left.value, right=right.value),
                                ftype=FindingType.RELATIONSHIP_VIOLATION,
                                doc_ids=[left.doc_id, right.doc_id],
                                entity=left.entity,
                                attribute=left.attribute,
                                claims=[left, right],
                            )
                        )
        else:
            raise ValueError(f"unsupported graph rule type {rule['type']!r} in {rule['id']}")
    return findings

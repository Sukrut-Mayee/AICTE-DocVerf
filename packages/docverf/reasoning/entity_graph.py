"""Claims and entity-graph consistency checks (TRD §7.2, §8.1-§8.3)."""

from docverf.reasoning.entity_resolution import normalize_id, to_acres
from docverf.schemas import (
    AuthorityTier,
    CheckResult,
    Claim,
    DocType,
    ExtractionResult,
    Finding,
    VerificationStatus,
)

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


def graph_checks(claims: list[Claim]) -> list[Finding]:
    """Evaluate rules/graph/*.yaml: attribute_agree and relationship_equal (§8.2, §8.3)."""
    raise NotImplementedError

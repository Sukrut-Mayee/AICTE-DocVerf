"""Claims and entity-graph consistency checks (TRD §7.2, §8.1-§8.3)."""

from docverf.schemas import CheckResult, Claim, ExtractionResult, Finding


def build_claims(extractions: list[ExtractionResult], checks: list[CheckResult]) -> list[Claim]:
    """Map fields to entity.attribute (§8.1); authority tier from §6, upgraded to issuer_verified
    by a verified pdf_signature / qr / issuer_lookup check."""
    raise NotImplementedError


def graph_checks(claims: list[Claim]) -> list[Finding]:
    """Evaluate rules/graph/*.yaml: attribute_agree and relationship_equal (§8.2, §8.3)."""
    raise NotImplementedError

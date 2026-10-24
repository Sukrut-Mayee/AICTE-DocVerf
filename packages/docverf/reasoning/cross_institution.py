"""Cross-institution checks, P1 (TRD §7.3, §19 Q4)."""

from docverf.provenance.duplicates import HashIndex
from docverf.schemas import Claim, Finding


def check_cross_institution(
    app_id: str, claims: list[Claim], hash_index: HashIndex
) -> list[Finding]:
    """Flag a strong ID (survey no., certificate no.) or file hash shared across institutions."""
    raise NotImplementedError

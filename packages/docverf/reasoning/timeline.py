"""Timeline contradiction engine (TRD §8.5)."""

from docverf.schemas import Claim, Finding


def timeline_checks(claims: list[Claim]) -> list[Finding]:
    """Evaluate rules/timeline/*.yaml. A missing or low-confidence date is `undetermined`
    (severity info), never a violation."""
    raise NotImplementedError

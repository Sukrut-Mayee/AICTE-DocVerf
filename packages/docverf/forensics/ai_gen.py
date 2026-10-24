"""AI-generation signal, P2 (TRD §9.2). Severity is capped at `low`."""

from datetime import datetime

from docverf.schemas import CheckResult, CheckStatus, Layer, Severity


def ai_gen(image_path: str, doc_id: str) -> CheckResult:
    """P2 placeholder: AI-generation detection is not yet implemented.

    Severity is capped at `low` per TRD §9.2; no reliable claim is made.
    Returns NOT_APPLICABLE so callers do not act on an unimplemented detector.
    """
    return CheckResult(
        doc_id=doc_id,
        layer=Layer.E,
        check="ai_gen",
        status=CheckStatus.NOT_APPLICABLE,
        severity=Severity.INFO,
        reason=(
            "Preliminary indicator: AI-generation detection is a P2 feature and is "
            "not yet implemented; no signal reported."
        ),
        evidence={
            "implemented": False,
            "details": {"method": "none", "stage": "P2"},
        },
        checked_at=datetime.now(),
    )

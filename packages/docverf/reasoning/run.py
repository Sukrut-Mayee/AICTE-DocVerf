"""Reasoning entry points (TRD §8.7)."""

from docverf.schemas import CheckResult, DocumentStatus, ExtractionResult, Finding


def run_reasoning(
    app_id: str, extractions: list[ExtractionResult], checks: list[CheckResult]
) -> list[Finding]:
    """Run rules, graph checks and timeline."""
    raise NotImplementedError


def aggregate(
    app_id: str, findings: list[Finding], checks: list[CheckResult]
) -> tuple[list[DocumentStatus], int]:
    """Per-document status by the §8.7 precedence; priority = 100*high + 10*medium + 1*low."""
    raise NotImplementedError

"""AI-generation signal, P2 (TRD §9.2). Severity is capped at `low`."""

from docverf.schemas import CheckResult


def ai_gen(image_path: str, doc_id: str) -> CheckResult:
    raise NotImplementedError

"""Load the hand-made Appendix A applications (TRD §17) as ExtractionResult lists."""

import json
from pathlib import Path

from docverf.schemas import ExtractionResult

FIXTURES = Path(__file__).parent / "fixtures" / "apps"


def load_app(name: str) -> list[ExtractionResult]:
    return [
        ExtractionResult.model_validate(json.loads(p.read_text(encoding="utf-8")))
        for p in sorted((FIXTURES / name).glob("*.json"))
    ]

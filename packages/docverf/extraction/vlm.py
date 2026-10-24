"""Extractor 2: VLM (Ollama by default) with page image + JSON schema of the doc type (TRD §10)."""

from pathlib import Path

from docverf.schemas import DocType, FieldValue


def vlm_extract(image_path: Path, doc_type: DocType) -> dict[str, FieldValue]:
    """Validate the model output with Pydantic; one retry. Never calls a cloud API unless
    ALLOW_CLOUD_AI=true (TRD §1 rule 9)."""
    raise NotImplementedError

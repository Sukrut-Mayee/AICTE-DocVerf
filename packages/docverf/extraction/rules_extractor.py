"""Extractor 1: regex/keyword rules over OCR text, per doc type (TRD §10)."""

from typing import Any

from docverf.schemas import DocType, FieldValue


def rules_extract(ocr_words: list[dict[str, Any]], doc_type: DocType) -> dict[str, FieldValue]:
    raise NotImplementedError

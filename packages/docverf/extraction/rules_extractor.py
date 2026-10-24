"""Extractor 1: regex/keyword rules over OCR text, per doc type (TRD §10).

Keyword/regex extraction over OCR word boxes for land_deed, noc, affidavit and
accreditation_cert.
Missing or ambiguous fields are omitted rather than guessed. Confidence is
the OCR confidence times the format factor. The agreement factor is applied once, by the
merge in ``extract._merge_fields``, after the VLM extractor has been compared.
"""

import re
from typing import Any

from docverf.extraction.confidence import field_confidence
from docverf.extraction.normalize import (
    devanagari_to_ascii_digits,
    normalize_area,
    normalize_date,
)
from docverf.schemas import DocType, FieldValue

# Smallest vertical tolerance (normalized 0..1) for grouping words into a text line; the real
# tolerance is half the median word height (see _group_lines).
_MIN_LINE_TOLERANCE = 0.004

# Survey number like "45/2" or "45/2A".
_SURVEY_RE = re.compile(r"\d+\s*/\s*\d+[A-Za-z]?")
# NOC reference like "FIRE/MH/2008/004512".
_REF_NO_RE = re.compile(r"[A-Za-z]{2,}/[A-Za-z]{2}/\d{4}/\d+")

# Each spec: (field_name, [label keywords], extraction kind).
# Kind: text | date | area | survey_no | ref_no | mortgage | list
# The first label of each field is the exact English label printed by the synthetic templates
# (synthetic/templates/*.html.j2); a line is matched by the first label found in it, so the exact
# label wins on its own line. The looser keywords after it are for other documents.
_LABEL_SPECS: dict[DocType, list[tuple[str, list[str], str]]] = {
    DocType.LAND_DEED: [
        ("owner_name", ["owner name", "owner", "मालक", "स्वामी"], "text"),
        (
            "survey_no",
            ["survey/gat no", "survey no", "survey", "सर्वे नंबर", "गट नंबर", "गट"],
            "survey_no",
        ),
        ("area", ["land area", "area", "क्षेत्रफळ"], "area"),
        ("village", ["village", "गाव"], "text"),
        ("district", ["district", "जिल्हा"], "text"),
        (
            "registration_no",
            ["deed registration no", "registration no", "registration", "नोंदणी क्रमांक"],
            "text",
        ),
        ("registration_date", ["registration date", "date", "तारीख"], "date"),
        ("mortgage_status", ["mortgage status", "mortgage", "बंधक"], "mortgage"),
    ],
    DocType.NOC: [
        ("issuer", ["issuing authority", "issuer", "जारी करणारा"], "text"),
        (
            "ref_no",
            ["noc reference no", "ref no", "reference no", "संदर्भ क्रमांक"],
            "ref_no",
        ),
        ("institute_name", ["institute name", "institute", "महाविद्यालय"], "text"),
        ("purpose", ["purpose of noc", "purpose", "उद्देश"], "text"),
        ("issue_date", ["issue date"], "date"),
        ("valid_until", ["valid until", "valid upto", "वैधता"], "date"),
        ("signatory", ["signatory name", "signatory", "स्वाक्षरीकर्ता"], "text"),
    ],
    DocType.AFFIDAVIT: [
        ("deponent_name", ["deponent name", "deponent", "प्रतिज्ञाकर्ता"], "text"),
        ("institute_name", ["institute name", "institute", "महाविद्यालय"], "text"),
        (
            "application_no",
            ["application no", "application", "अर्ज क्रमांक"],
            "text",
        ),
        ("date", ["date of affidavit", "date", "तारीख"], "date"),
        (
            "land_area_declared",
            ["declared land area", "land area", "घोषित क्षेत्रफळ"],
            "area",
        ),
        (
            "notary_reg_no",
            ["notary reg. no", "notary reg no", "notary", "नोटरी क्रमांक"],
            "text",
        ),
    ],
    DocType.ACCREDITATION_CERT: [
        ("cert_no", ["certificate no"], "text"),
        ("body", ["accrediting body"], "text"),
        ("institute_name", ["institute name"], "text"),
        ("programs", ["accredited programmes"], "list"),
        ("valid_from", ["valid from"], "date"),
        ("valid_to", ["valid to"], "date"),
    ],
}

_MORTGAGE_NONE = {"none", "नाही", "कोणताही नाही"}
_MORTGAGE_MORTGAGED = {"mortgaged", "बंधक", "हस्तगत"}


def _ascii(text: str) -> str:
    return devanagari_to_ascii_digits(text or "")


def _group_lines(
    ocr_words: list[dict[str, Any]],
) -> list[list[dict[str, Any]]]:
    """Group words into text lines, each sorted left to right.

    Two words share a line when their vertical centres differ by less than half a typical (median)
    word height, so neighbouring rows of an ordinary A4 page stay separate lines."""
    if not ocr_words:
        return []

    def centre(w: dict[str, Any]) -> float:
        return (float(w["bbox"][1]) + float(w["bbox"][3])) / 2

    heights = sorted(float(w["bbox"][3]) - float(w["bbox"][1]) for w in ocr_words)
    tolerance = max(heights[len(heights) // 2] / 2, _MIN_LINE_TOLERANCE)
    ordered = sorted(ocr_words, key=lambda w: (centre(w), float(w["bbox"][0])))
    lines: list[list[dict[str, Any]]] = [[ordered[0]]]
    cur_y = centre(ordered[0])
    for w in ordered[1:]:
        y = centre(w)
        if abs(y - cur_y) > tolerance:
            lines.append([w])
            cur_y = y
        else:
            lines[-1].append(w)
            cur_y = (cur_y + y) / 2
    return [sorted(line, key=lambda w: float(w["bbox"][0])) for line in lines]


def _line_text(line: list[dict[str, Any]]) -> str:
    return " ".join(w["text"] for w in line)


def _bbox_of(words: list[dict[str, Any]]) -> list[float] | None:
    if not words:
        return None
    return [
        min(float(w["bbox"][0]) for w in words),
        min(float(w["bbox"][1]) for w in words),
        max(float(w["bbox"][2]) for w in words),
        max(float(w["bbox"][3]) for w in words),
    ]


def _avg_conf(words: list[dict[str, Any]]) -> float:
    if not words:
        return 0.0
    return sum(float(w["confidence"]) for w in words) / len(words)


def _text_after_keyword(
    line: list[dict[str, Any]], keyword: str
) -> tuple[str, list[dict[str, Any]]]:
    """Return (text after the first keyword occurrence, words after it)."""
    joined = _line_text(line)
    low = joined.lower()
    k = keyword.lower()
    pos = low.find(k)
    if pos < 0:
        return "", []
    after_text = joined[pos + len(k) :].lstrip(" :\t-–—|.,;")
    char = 0
    after_words: list[dict[str, Any]] = []
    for w in line:
        w_start = char
        w_end = char + len(w["text"])
        char = w_end + 1  # +1 for the joining space
        if w_start >= pos + len(k):
            after_words.append(w)
    return after_text, after_words


def _extract_mortgage(candidate: str) -> str | None:
    low = _ascii(candidate).lower()
    for token in _MORTGAGE_NONE:
        if token in low:
            return "none"
    for token in _MORTGAGE_MORTGAGED:
        if token in low:
            return "mortgaged"
    return None


def _build_field(
    value_words: list[dict[str, Any]],
    raw: str | None,
    value: Any,
    unit: str | None,
    format_valid: bool,
) -> FieldValue | None:
    if value is None:
        return None
    page = int(value_words[0].get("page", 1)) if value_words else None
    # extractors_agree=True is the neutral 1.0 factor: agreement is applied later, in the merge.
    confidence = field_confidence(_avg_conf(value_words), True, format_valid)
    return FieldValue(
        value=value,
        unit=unit,
        raw=raw,
        confidence=confidence,
        page=page,
        bbox=_bbox_of(value_words),
        extractor_agreement=None,
    )


def rules_extract(ocr_words: list[dict[str, Any]], doc_type: DocType) -> dict[str, FieldValue]:
    """Extract fields using keyword/regex rules over OCR word boxes."""
    result: dict[str, FieldValue] = {}
    if not ocr_words:
        return result
    specs = _LABEL_SPECS.get(doc_type)
    if not specs:
        return result
    lines = _group_lines(ocr_words)
    for field_name, labels, kind in specs:
        for line in lines:
            line_lower = _line_text(line).lower()
            matched_label = None
            for label in labels:
                if label.lower() in line_lower:
                    matched_label = label
                    break
            if matched_label is None:
                continue
            after_text, after_words = _text_after_keyword(line, matched_label)
            value: Any = None
            unit: str | None = None
            format_valid = False
            raw: str | None = after_text or None
            val: str | None = None
            if kind == "text":
                val = " ".join(w["text"] for w in after_words).strip()
                if val:
                    value = val
                    format_valid = True
                    raw = val
            elif kind == "date":
                val = normalize_date(_ascii(after_text))
                if val:
                    value = val
                    format_valid = True
            elif kind == "area":
                parsed = normalize_area(_ascii(after_text))
                if parsed:
                    value, unit = parsed
                    format_valid = True
            elif kind == "survey_no":
                m = _SURVEY_RE.search(_ascii(after_text))
                if m:
                    value = m.group(0)
                    format_valid = True
                    raw = value
            elif kind == "ref_no":
                m = _REF_NO_RE.search(_ascii(after_text))
                if m:
                    value = m.group(0)
                    format_valid = True
                    raw = value
            elif kind == "list":  # "A; B" or "A, B"
                items = [t.strip() for t in re.split(r"[;,]", after_text) if t.strip()]
                if items:
                    value = items
                    format_valid = True
            elif kind == "mortgage":
                val = _extract_mortgage(after_text)
                if val:
                    value = val
                    format_valid = True
            if value is not None:
                field = _build_field(after_words, raw, value, unit, format_valid)
                if field is not None:
                    result[field_name] = field
            break
    return result

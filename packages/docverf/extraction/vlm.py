"""Extractor 2: VLM (Ollama by default) with page image + JSON schema of the doc type (TRD §10).

Calls the local Ollama HTTP API using the standard library only (no Ollama Python
package required). Never calls a cloud API unless ALLOW_CLOUD_AI=true (TRD §1 rule 9).
"""

import base64
import json
import math
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from docverf.config import get_settings
from docverf.extraction.normalize import devanagari_to_ascii_digits, normalize_area
from docverf.schemas import DocType, FieldValue

# Runtime fallback when VLM_MODEL is blank in config (TRD §15). Documented here;
# shared configuration is not changed.
_FALLBACK_MODEL = "qwen3-vl:2b-instruct-q4_K_M"

# Safe default confidence for VLM-only values (no OCR confidence available).
_VLM_CONFIDENCE = 0.5

# HTTP timeout for the Ollama call (seconds).
_OLLAMA_TIMEOUT_S = 60

# Text a model writes instead of a JSON null. "none" is also the real value of mortgage_status.
_NULL_WORDS = {"null", "none", "n/a", "-"}
# Fields that hold an area: the model answers "<number> <unit>" and we split it.
_AREA_FIELDS = {"area", "land_area_declared"}

# Field names per doc type, per TRD §6.
_FIELD_NAMES: dict[DocType, list[str]] = {
    DocType.LAND_DEED: [
        "owner_name",
        "survey_no",
        "area",
        "village",
        "district",
        "registration_no",
        "registration_date",
        "mortgage_status",
    ],
    DocType.NOC: [
        "issuer",
        "ref_no",
        "institute_name",
        "purpose",
        "issue_date",
        "valid_until",
        "signatory",
    ],
    DocType.AFFIDAVIT: [
        "deponent_name",
        "institute_name",
        "application_no",
        "date",
        "land_area_declared",
        "notary_reg_no",
    ],
    DocType.ACCREDITATION_CERT: [
        "body",
        "cert_no",
        "institute_name",
        "programs",
        "valid_from",
        "valid_to",
    ],
    # capture_date comes from EXIF, not from the VLM.
    DocType.LAB_PHOTO: ["room_label", "equipment_count"],
}

# Short type hints included in the prompt so the model emits sensible values.
_FIELD_HINTS: dict[DocType, dict[str, str]] = {
    DocType.LAND_DEED: {
        "owner_name": "string (person/organization name)",
        "survey_no": "string (e.g. 45/2)",
        "area": 'string: number and unit as printed, e.g. "2.5 acre" (keep the unit)',
        "village": "string",
        "district": "string",
        "registration_no": "string",
        "registration_date": "ISO date YYYY-MM-DD",
        "mortgage_status": "'none' or 'mortgaged'",
    },
    DocType.NOC: {
        "issuer": "string",
        "ref_no": "string (e.g. FIRE/MH/2008/004512)",
        "institute_name": "string",
        "purpose": "string",
        "issue_date": "ISO date YYYY-MM-DD",
        "valid_until": "ISO date YYYY-MM-DD",
        "signatory": "string",
    },
    DocType.AFFIDAVIT: {
        "deponent_name": "string",
        "institute_name": "string",
        "application_no": "string",
        "date": "ISO date YYYY-MM-DD",
        "land_area_declared": 'string: number and unit as printed, e.g. "2.5 acre" (keep the unit)',
        "notary_reg_no": "string",
    },
    DocType.ACCREDITATION_CERT: {
        "body": "string (accrediting body, e.g. NBA)",
        "cert_no": "string (certificate number)",
        "institute_name": "string",
        "programs": "JSON array of strings (programme names)",
        "valid_from": "ISO date YYYY-MM-DD",
        "valid_to": "ISO date YYYY-MM-DD",
    },
    DocType.LAB_PHOTO: {
        "room_label": "string (text visible in the photo, e.g. a sign) or null",
        "equipment_count": (
            "integer (count of computers/workstations clearly visible), null if none"
        ),
    },
}


def _model_name() -> str:
    settings = get_settings()
    return settings.VLM_MODEL or _FALLBACK_MODEL


def _encode_image(image_path: Path) -> str:
    with open(image_path, "rb") as fh:
        return base64.b64encode(fh.read()).decode("ascii")


def _build_prompt(doc_type: DocType) -> str:
    fields = _FIELD_NAMES[doc_type]
    hints = _FIELD_HINTS.get(doc_type, {})
    lines = [
        "You are a document extraction model. Extract the following fields from the",
        "provided document image and return ONLY a JSON object.",
        "",
        "Fields to extract:",
    ]
    for name in fields:
        hint = hints.get(name, "string")
        lines.append(f"  - {name}: {hint}")
    lines += [
        "",
        "Rules:",
        "  - Return valid JSON only, no markdown code fences, no extra text.",
        "  - Include only the fields listed above that are present in the document.",
        "  - Use null for missing values.",
        "  - Dates must be ISO YYYY-MM-DD strings.",
        "  - Numbers should be numeric, not strings.",
        "  - Copy values exactly as printed. Never guess or infer; if a value is unclear or",
        "    absent, use null.",
        "  - Names of people/organisations: return them in Latin script. If the document prints",
        "    the name in both English and Devanagari, use the English one. If only Devanagari,",
        "    transliterate it the way it would be written in English",
        "    (e.g. श्री विद्या एज्युकेशन ट्रस्ट → Shree Vidya Education Trust).",
        "  - Do not translate or rewrite numbers, IDs, reference numbers or dates —",
        "    only reformat dates to ISO.",
        "",
        "JSON object:",
    ]
    return "\n".join(lines)


def _ollama_generate(settings, model: str, image_b64: str, prompt: str) -> str:
    """POST to Ollama /api/generate and return the raw response text."""
    url = settings.OLLAMA_URL.rstrip("/") + "/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "images": [image_b64],
        "format": "json",
        "stream": False,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=_OLLAMA_TIMEOUT_S) as resp:
        body = resp.read().decode("utf-8")
    parsed = json.loads(body)
    return parsed.get("response", "")


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        # Remove opening fence and optional language tag.
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    return text


def _validate_field_value(
    raw_value: Any, unit: str | None = None, raw: str | None = None
) -> FieldValue | None:
    """Build a FieldValue from a cleaned VLM value, or None if invalid."""
    try:
        return FieldValue(
            value=raw_value,
            unit=unit,
            confidence=_VLM_CONFIDENCE,
            raw=raw,
            page=None,
            bbox=None,
            extractor_agreement=None,
        )
    except Exception:
        return None


def _is_null_word(name: str, text: str) -> bool:
    word = text.strip().lower()
    return word in _NULL_WORDS and not (name == "mortgage_status" and word == "none")


def _parse_area(value: Any) -> tuple[float, str | None] | None:
    """Split an area answer into (number, unit), or None if it has no usable number.

    "2.10 acre" -> (2.1, "acre"); a bare number keeps unit None (reasoning then reports the
    missing unit instead of guessing one). normalize_area gives the canonical unit
    ("acres", "एकर" -> "acre") or, for an unknown unit, the text as written."""
    number: float
    unit: str | None = None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = value
    elif isinstance(value, str):
        parsed = normalize_area(value)
        if parsed is not None:
            number, unit = parsed
        else:
            try:
                number = float(devanagari_to_ascii_digits(value.strip()))
            except ValueError:
                return None
    else:
        return None
    return (number, unit) if math.isfinite(number) and number >= 0 else None


def _clean_value(name: str, value: Any) -> Any:
    """The value to keep for a field, or None when the field must be treated as absent.

    A null, a blank string, a null word ("null", "n/a", ...) or an empty list never becomes a
    value. equipment_count must be an integer and programs a list of strings; anything else is
    dropped rather than guessed."""
    if value is None or value == []:
        return None
    if isinstance(value, str) and (not value.strip() or _is_null_word(name, value)):
        return None
    if name == "mortgage_status" and isinstance(value, str):
        return value.strip().lower()  # the rules compare against 'none' / 'mortgaged'
    if name == "equipment_count":
        if isinstance(value, bool):
            return None
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
        return value if isinstance(value, int) else None
    if name == "programs":
        if not isinstance(value, list):
            return None
        names = [
            p for p in value if isinstance(p, str) and p.strip() and not _is_null_word(name, p)
        ]
        return names or None
    return value


def _parse_response(response_text: str, doc_type: DocType) -> dict[str, FieldValue]:
    """Parse the VLM JSON response and validate each field against the schema."""
    text = _strip_code_fences(response_text)
    if not text:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    allowed = set(_FIELD_NAMES[doc_type])
    result: dict[str, FieldValue] = {}
    for name, raw_value in data.items():
        if name not in allowed:
            continue
        value = _clean_value(name, raw_value)
        if value is None:
            continue
        unit = None
        if name in _AREA_FIELDS:
            parsed = _parse_area(value)
            if parsed is None:
                continue
            value, unit = parsed
        fv = _validate_field_value(value, unit, raw_value if isinstance(raw_value, str) else None)
        if fv is not None:
            result[name] = fv
    return result


def vlm_extract(image_path: Path, doc_type: DocType) -> dict[str, FieldValue]:
    """Extract structured fields from a document page image via local Ollama.

    Returns a dict of FieldValue (extractor 2 output). Retries exactly once on
    malformed JSON or validation failure. Returns an empty dict if extraction
    cannot produce valid output.
    """
    if not isinstance(image_path, Path):
        image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")

    settings = get_settings()
    model = _model_name()

    if doc_type not in _FIELD_NAMES:
        raise ValueError(f"Unsupported doc_type for VLM extraction: {doc_type}")

    image_b64 = _encode_image(image_path)
    prompt = _build_prompt(doc_type)

    for _attempt in range(2):
        try:
            response_text = _ollama_generate(settings, model, image_b64, prompt)
        except (urllib.error.URLError, OSError) as exc:
            # Ollama unavailable: do not retry network failures.
            raise ConnectionError(f"Ollama unavailable at {settings.OLLAMA_URL}: {exc}") from exc
        except Exception:  # HTTP error, unexpected: retry once
            continue

        result = _parse_response(response_text, doc_type)
        if result:
            return result
        # Empty/invalid output: retry once.

    # Retry exhausted.
    return {}

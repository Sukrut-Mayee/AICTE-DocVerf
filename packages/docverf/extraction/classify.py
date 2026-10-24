"""Document classification (TRD §10).

Zero-shot VLM classification via the local Ollama API, with a keyword-based
fallback when Ollama is unavailable or returns invalid output. Never calls a
cloud API unless ALLOW_CLOUD_AI=true (TRD §1 rule 9).
"""

import json
import urllib.error
import urllib.request
from pathlib import Path

from docverf.config import get_settings
from docverf.schemas import DocType

# Runtime fallback model when VLM_MODEL is blank in config (documented; config
# itself is not changed).
_FALLBACK_MODEL = "qwen3-vl:2b-instruct-q4_K_M"

_OLLAMA_TIMEOUT_S = 60

# Keyword hints per doc type for the keyword fallback (English + Devanagari).
_KEYWORDS: dict[DocType, list[str]] = {
    DocType.LAND_DEED: [
        "land deed",
        "sale deed",
        "survey no",
        "survey number",
        "registration",
        "mortgage",
        "owner name",
        "रजिस्ट्रेशन",
    ],
    DocType.NOC: [
        "noc",
        "no objection certificate",
        "ref no",
        "reference no",
        "valid until",
        "issuer",
        "fire services",
    ],
    DocType.AFFIDAVIT: [
        "affidavit",
        "deponent",
        "notary",
        "solemnly affirm",
        "sworn",
    ],
    DocType.ACCREDITATION_CERT: [
        "accreditation",
        "nba",
        "naac",
        "cert no",
        "valid from",
        "valid to",
    ],
    DocType.LAB_PHOTO: [
        "laboratory",
        "lab",
        "equipment",
        "room label",
        "room no",
    ],
    DocType.APPLICATION_FORM: [
        "application form",
        "aicte",
        "permanent id",
        "intake",
        "principal",
        "trust",
    ],
}

# Safe default when no signal is available.
_DEFAULT = DocType.APPLICATION_FORM


def _ollama_classify(image_path: Path, model: str) -> DocType | None:
    """Ask Ollama to classify the document image into one of the six doc types.

    Returns a DocType or None if Ollama is unavailable / output is invalid.
    """
    settings = get_settings()
    url = settings.OLLAMA_URL.rstrip("/") + "/api/generate"
    type_list = ", ".join(f"'{t.value}'" for t in DocType)
    prompt = (
        "Classify the document in the image into exactly one of these types: "
        + type_list
        + '. Return ONLY a JSON object with a single key "doc_type" set to one of '
        "the listed type strings. No markdown, no extra text."
    )
    try:
        import base64

        with open(image_path, "rb") as fh:
            image_b64 = base64.b64encode(fh.read()).decode("ascii")
    except OSError:
        return None
    payload = {
        "model": model,
        "prompt": prompt,
        "images": [image_b64],
        "format": "json",
        "stream": False,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=_OLLAMA_TIMEOUT_S) as resp:
            body = resp.read().decode("utf-8")
    except (urllib.error.URLError, OSError):
        return None
    try:
        parsed = json.loads(body)
        response_text = parsed.get("response", "")
        data_obj = json.loads(response_text)
        value = data_obj.get("doc_type")
    except (json.JSONDecodeError, AttributeError, ValueError):
        return None
    if not isinstance(value, str):
        return None
    for doc_type in DocType:
        if doc_type.value == value:
            return doc_type
    return None


def _extract_pdf_text(file_path: Path) -> str:
    """Best-effort text extraction from a digital PDF using PyMuPDF."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return ""
    text_parts = []
    try:
        with fitz.open(str(file_path)) as doc:
            for page in doc:
                text_parts.append(page.get_text())
    except Exception:
        return ""
    return "\n".join(text_parts)


def _keyword_fallback(file_path: Path) -> DocType:
    """Classify by matching keywords against extracted text / filename."""
    text = ""
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        text = _extract_pdf_text(file_path)
    if not text:
        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except (OSError, UnicodeDecodeError):
            text = ""
    text = (text + " " + file_path.stem).lower()
    best = _DEFAULT
    best_score = 0
    for doc_type, keywords in _KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in text)
        if score > best_score:
            best_score = score
            best = doc_type
    return best if best_score > 0 else _DEFAULT


def classify(file_path: Path) -> DocType:
    """Classify a document file into one of the six DocType values.

    Tries the local Ollama vision model first (zero-shot). Falls back to
    keyword matching when Ollama is unavailable or returns invalid output.
    Returns APPLICATION_FORM as a safe default when no signal is available.
    """
    if not isinstance(file_path, Path):
        file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    settings = get_settings()
    model = settings.VLM_MODEL or _FALLBACK_MODEL

    doc_type = _ollama_classify(file_path, model)
    if doc_type is not None:
        return doc_type
    return _keyword_fallback(file_path)

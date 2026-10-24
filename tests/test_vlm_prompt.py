"""VLM prompt rules, accreditation / lab-photo specs, null handling and routing (TRD §10).

Ollama is mocked at `vlm._ollama_generate`; `vlm_extract` itself is the real code.
"""

import json
import urllib.error

import docverf.extraction.extract as extract_module
import docverf.extraction.vlm as vlm_module
import pytest
from docverf.extraction.vlm import _build_prompt, vlm_extract
from docverf.schemas import DocType, ExtractionResult
from PIL import Image

VLM_TYPES = [
    DocType.LAND_DEED,
    DocType.NOC,
    DocType.AFFIDAVIT,
    DocType.ACCREDITATION_CERT,
    DocType.LAB_PHOTO,
]
NEW_RULES = [
    "Copy values exactly as printed. Never guess or infer; if a value is unclear or absent, "
    "use null.",
    "Names of people/organisations: return them in Latin script. If the document prints the "
    "name in both English and Devanagari, use the English one. If only Devanagari, "
    "transliterate it the way it would be written in English "
    "(e.g. श्री विद्या एज्युकेशन ट्रस्ट → Shree Vidya Education Trust).",
    "Do not translate or rewrite numbers, IDs, reference numbers or dates — only reformat "
    "dates to ISO.",
]


def prompt_text(doc_type):
    return " ".join(_build_prompt(doc_type).split())  # undo the line wrapping


def image(tmp_path, name="page.png"):
    path = tmp_path / name
    Image.new("RGB", (1000, 1000), color="white").save(path)
    return path


def fake_ollama(monkeypatch, reply, calls=None):
    """Make the model answer `reply` (a dict, a string, or an exception to raise)."""

    def generate(settings, model, image_b64, prompt):
        if calls is not None:
            calls.append(prompt)
        if isinstance(reply, Exception):
            raise reply
        return reply if isinstance(reply, str) else json.dumps(reply)

    monkeypatch.setattr(vlm_module, "_ollama_generate", generate)


# ---- prompt ----


@pytest.mark.parametrize("doc_type", VLM_TYPES)
def test_prompt_contains_the_new_rules_and_keeps_the_old_ones(doc_type):
    text = prompt_text(doc_type)
    for rule in NEW_RULES:
        assert rule in text
    assert "Return valid JSON only" in text and "Use null for missing values." in text
    assert "Dates must be ISO YYYY-MM-DD strings." in text


@pytest.mark.parametrize("doc_type", VLM_TYPES)
def test_response_format_is_still_a_flat_object_without_raw(doc_type):
    text = prompt_text(doc_type)
    assert "return ONLY a JSON object" in text
    assert "raw" not in text.lower().replace("translat", "")  # no nested / parallel raw keys


def test_new_doc_types_list_their_fields_with_hints():
    accreditation = prompt_text(DocType.ACCREDITATION_CERT)
    for line in (
        "- body: string (accrediting body, e.g. NBA)",
        "- cert_no: string (certificate number)",
        "- institute_name: string",
        "- programs: JSON array of strings (programme names)",
        "- valid_from: ISO date YYYY-MM-DD",
        "- valid_to: ISO date YYYY-MM-DD",
    ):
        assert line in accreditation
    photo = prompt_text(DocType.LAB_PHOTO)
    assert "- room_label: string (text visible in the photo, e.g. a sign) or null" in photo
    assert (
        "- equipment_count: integer (count of computers/workstations clearly visible), "
        "null if none" in photo
    )
    assert "capture_date" not in photo  # comes from EXIF, never from the VLM


# ---- parsing the two new types ----


def test_accreditation_cert_fields(monkeypatch, tmp_path):
    fake_ollama(
        monkeypatch,
        {
            "body": "NBA",
            "cert_no": "NBA/2024/123",
            "institute_name": "Shree Vidya Institute of Technology",
            "programs": ["Computer Engineering", "Mechanical Engineering"],
            "valid_from": "2024-07-01",
            "valid_to": "2027-06-30",
            "capture_date": "2024-01-01",  # not a field of this type: dropped
        },
    )
    result = vlm_extract(image(tmp_path), DocType.ACCREDITATION_CERT)
    assert set(result) == {
        "body",
        "cert_no",
        "institute_name",
        "programs",
        "valid_from",
        "valid_to",
    }
    assert result["programs"].value == ["Computer Engineering", "Mechanical Engineering"]
    assert result["valid_to"].value == "2027-06-30"
    assert {fv.confidence for fv in result.values()} == {0.5}


def test_lab_photo_fields_and_capture_date_is_not_taken_from_the_vlm(monkeypatch, tmp_path):
    fake_ollama(
        monkeypatch,
        {"room_label": "Computer Lab 2", "equipment_count": 24, "capture_date": "2024-05-01"},
    )
    result = vlm_extract(image(tmp_path), DocType.LAB_PHOTO)
    assert set(result) == {"room_label", "equipment_count"}
    assert (result["room_label"].value, result["equipment_count"].value) == ("Computer Lab 2", 24)


@pytest.mark.parametrize(
    "given, kept",
    [
        (5, 5),
        (0, 0),  # a real answer: nothing visible
        (4.0, 4),
        ("5", 5),
        (" 12 ", 12),
        (4.5, None),
        ("many", None),
        ("5 computers", None),
        (True, None),
        ([3], None),
    ],
)
def test_equipment_count_must_be_an_integer(monkeypatch, tmp_path, given, kept):
    fake_ollama(monkeypatch, {"room_label": "Lab", "equipment_count": given})
    result = vlm_extract(image(tmp_path), DocType.LAB_PHOTO)
    if kept is None:
        assert "equipment_count" not in result
    else:
        assert result["equipment_count"].value == kept
        assert type(result["equipment_count"].value) is int


@pytest.mark.parametrize(
    "given, kept",
    [
        (["BE Computer", "BE Civil"], ["BE Computer", "BE Civil"]),
        (["BE Computer", "", "  ", 3, None], ["BE Computer"]),
        ([], None),
        ([3, None], None),
        ("BE Computer", None),  # not a list
    ],
)
def test_programs_must_be_a_list_of_strings(monkeypatch, tmp_path, given, kept):
    fake_ollama(monkeypatch, {"body": "NBA", "programs": given})
    result = vlm_extract(image(tmp_path), DocType.ACCREDITATION_CERT)
    if kept is None:
        assert "programs" not in result
    else:
        assert result["programs"].value == kept


# ---- a null never becomes a value ----


def test_null_blank_and_empty_values_are_absent(monkeypatch, tmp_path):
    fake_ollama(
        monkeypatch,
        {"owner_name": None, "survey_no": "", "village": "   ", "district": [], "area": 2.5},
    )
    result = vlm_extract(image(tmp_path), DocType.LAND_DEED)
    assert set(result) == {"area"}
    assert all(fv.value is not None for fv in result.values())


@pytest.mark.parametrize("doc_type", VLM_TYPES)
def test_all_null_answer_gives_no_fields_after_exactly_one_retry(monkeypatch, tmp_path, doc_type):
    calls = []
    fake_ollama(monkeypatch, {name: None for name in vlm_module._FIELD_NAMES[doc_type]}, calls)
    assert vlm_extract(image(tmp_path), doc_type) == {}
    assert len(calls) == 2  # first attempt + one retry, as for malformed JSON


# ---- routing through extract() ----


@pytest.fixture
def pipeline(monkeypatch):
    """extract() with the quality gate, regions and OCR stubbed; records who was called."""
    calls = {"ocr": 0, "rules": 0}

    def run_ocr(path):
        calls["ocr"] += 1
        return []

    def rules_extract(words, doc_type):
        calls["rules"] += 1
        return {}

    monkeypatch.setattr(extract_module, "_check_quality", lambda p, t: (True, None))
    monkeypatch.setattr(extract_module, "detect_regions", lambda p: [])
    monkeypatch.setattr(extract_module, "run_ocr", run_ocr)
    monkeypatch.setattr(extract_module, "rules_extract", rules_extract)
    return calls


def test_accreditation_cert_uses_ocr_rules_and_vlm(monkeypatch, tmp_path, pipeline):
    fake_ollama(
        monkeypatch,
        {
            "body": "NBA",
            "cert_no": None,  # unclear: must not appear
            "programs": ["Computer Engineering"],
            "valid_to": "2027-06-30",
        },
    )
    result = extract_module.extract(
        str(image(tmp_path)), "app001_accreditation_cert", "app001", DocType.ACCREDITATION_CERT
    )
    assert pipeline == {"ocr": 1, "rules": 1}
    assert result.doc_type is DocType.ACCREDITATION_CERT
    assert set(result.fields) == {"body", "programs", "valid_to"}
    assert result.fields["programs"].value == ["Computer Engineering"]
    assert {"ocr", "vlm"} <= set(result.engines)
    # only one extractor produced the value: VLM base 0.5 x 0.6 x 1.0 (TRD §10)
    assert all(fv.confidence == pytest.approx(0.3) for fv in result.fields.values())
    assert ExtractionResult.model_validate_json(result.model_dump_json()) == result


def test_lab_photo_goes_to_the_vlm_only(monkeypatch, tmp_path, pipeline):
    fake_ollama(monkeypatch, {"room_label": None, "equipment_count": "6"})
    result = extract_module.extract(
        str(image(tmp_path)), "app001_lab_photo", "app001", DocType.LAB_PHOTO
    )
    assert pipeline == {"ocr": 0, "rules": 0}  # a photo has no text to read
    assert result.doc_type is DocType.LAB_PHOTO
    assert set(result.engines) == {"vlm"}
    assert result.warnings == []
    assert set(result.fields) == {"equipment_count"}  # the null room label is absent
    fv = result.fields["equipment_count"]
    assert fv.value == 6 and type(fv.value) is int
    assert fv.confidence == pytest.approx(0.5 * 0.6 * 1.0)  # VLM-only factor
    assert fv.extractor_agreement is None
    assert ExtractionResult.model_validate_json(result.model_dump_json()) == result


def test_lab_photo_without_a_vlm_does_not_crash(monkeypatch, tmp_path, pipeline):
    fake_ollama(monkeypatch, urllib.error.URLError("connection refused"))
    result = extract_module.extract(
        str(image(tmp_path)), "app001_lab_photo", "app001", DocType.LAB_PHOTO
    )
    assert result.fields == {} and result.doc_type is DocType.LAB_PHOTO
    assert any("VLM unavailable" in w for w in result.warnings)
    assert pipeline == {"ocr": 0, "rules": 0}


def test_other_doc_types_are_routed_as_before(monkeypatch, tmp_path, pipeline):
    calls = []
    fake_ollama(monkeypatch, {"owner_name": "Alice"}, calls)
    extract_module.extract(str(image(tmp_path)), "d", "a", DocType.APPLICATION_FORM)
    assert calls == []  # the JSON application form never goes to the VLM
    assert pipeline == {"ocr": 1, "rules": 0}
    extract_module.extract(str(image(tmp_path)), "d", "a", DocType.LAND_DEED)
    assert len(calls) == 1 and pipeline == {"ocr": 2, "rules": 1}

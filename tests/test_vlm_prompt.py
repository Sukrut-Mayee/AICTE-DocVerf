"""VLM prompt rules, accreditation / lab-photo specs, null handling and routing (TRD §10).

Ollama is mocked at `vlm._ollama_generate`; `vlm_extract` itself is the real code.
"""

import json
import urllib.error

import docverf.extraction.extract as extract_module
import docverf.extraction.vlm as vlm_module
import pytest
from docverf.extraction.vlm import _build_prompt, vlm_extract
from docverf.reasoning.entity_graph import build_claims, unit_findings
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


# ---- prompt wording ----


@pytest.mark.parametrize("doc_type", VLM_TYPES)
def test_prompt_says_document_image(doc_type):
    text = prompt_text(doc_type)
    assert "provided document image and return ONLY a JSON object" in text
    assert "page image" not in text


@pytest.mark.parametrize("doc_type", [DocType.LAND_DEED, DocType.AFFIDAVIT])
def test_area_hint_asks_for_number_and_unit(doc_type):
    hint = 'string: number and unit as printed, e.g. "2.5 acre" (keep the unit)'
    assert hint in prompt_text(doc_type)


# ---- area answers become value + unit ----

AREA_FIELDS = [(DocType.LAND_DEED, "area"), (DocType.AFFIDAVIT, "land_area_declared")]


@pytest.mark.parametrize("doc_type, field", AREA_FIELDS)
@pytest.mark.parametrize(
    "given, number, unit",
    [
        ("2.10 acre", 2.1, "acre"),
        ("1.8 acres", 1.8, "acre"),
        ("0.85 ha", 0.85, "hectare"),
        ("2 एकर", 2.0, "acre"),
        ("२.५ एकर", 2.5, "acre"),  # Devanagari digits
        (2.5, 2.5, None),  # a bare number: no unit is guessed
        ("2.5", 2.5, None),
        ("10 sq. m.", 10.0, "sqm"),  # dotted units parse
        ("10 चौ.मी.", 10.0, "sqm"),
        ("3 bigha", 3.0, "bigha"),  # unknown unit stays as written
    ],
)
def test_area_is_split_into_value_and_unit(
    monkeypatch, tmp_path, doc_type, field, given, number, unit
):
    fake_ollama(monkeypatch, {field: given})
    fv = vlm_extract(image(tmp_path), doc_type)[field]
    assert (fv.value, fv.unit) == (number, unit)
    assert fv.raw == (given if isinstance(given, str) else None)  # the printed text is kept


@pytest.mark.parametrize("doc_type, field", AREA_FIELDS)
@pytest.mark.parametrize(
    "given",
    ["abc", "acre", "", "N/A", "-", "nan", "inf", "-3", "-3 acre", None, True, [2.5],
     {"value": 2.5, "unit": "acre"}],
)  # fmt: skip
def test_area_without_a_usable_number_is_dropped(monkeypatch, tmp_path, doc_type, field, given):
    fake_ollama(monkeypatch, {field: given})
    assert field not in vlm_extract(image(tmp_path), doc_type)


@pytest.mark.parametrize(
    "given, acres",
    [("2.10 acre", 2.1), ("1.8 acres", 1.8), ("0.85 ha", 0.85 * 2.47105), ("2 एकर", 2.0),
     ("40 guntha", 1.0)],
)  # fmt: skip
def test_vlm_area_reaches_reasoning_with_its_unit(monkeypatch, tmp_path, given, acres):
    """The unit is canonical, so reasoning converts it with the shared docverf.units table."""
    fake_ollama(monkeypatch, {"owner_name": "Shree Vidya Education Trust", "area": given})
    fields = vlm_extract(image(tmp_path), DocType.LAND_DEED)
    deed = ExtractionResult(
        doc_id="appx_land_deed", app_id="appx", doc_type=DocType.LAND_DEED, fields=fields
    )
    (claim,) = [c for c in build_claims([deed], []) if c.attribute == "area"]
    assert claim.value == pytest.approx(acres)
    assert unit_findings("appx", [deed]) == []


@pytest.mark.parametrize("given, message", [("3 bigha", "'bigha'"), (2.5, "no unit")])
def test_unknown_or_missing_unit_is_reported_by_reasoning_not_guessed(
    monkeypatch, tmp_path, given, message
):
    fake_ollama(monkeypatch, {"area": given})
    fields = vlm_extract(image(tmp_path), DocType.LAND_DEED)
    deed = ExtractionResult(
        doc_id="appx_land_deed", app_id="appx", doc_type=DocType.LAND_DEED, fields=fields
    )
    assert [c for c in build_claims([deed], []) if c.attribute == "area"] == []
    (finding,) = unit_findings("appx", [deed])
    assert message in finding.message


# ---- null words ----


@pytest.mark.parametrize("word", ["null", "NULL", "None", "n/a", "N/A", " n/a ", "-", " - "])
def test_null_words_are_treated_as_null(monkeypatch, tmp_path, word):
    fake_ollama(monkeypatch, {"owner_name": word, "village": "Pune"})
    assert set(vlm_extract(image(tmp_path), DocType.LAND_DEED)) == {"village"}


def test_none_stays_a_real_value_for_mortgage_status_only(monkeypatch, tmp_path):
    """'none' means no mortgage; LAND_NOT_MORTGAGED compares against it."""
    fake_ollama(monkeypatch, {"mortgage_status": "none", "owner_name": "none"})
    result = vlm_extract(image(tmp_path), DocType.LAND_DEED)
    assert set(result) == {"mortgage_status"} and result["mortgage_status"].value == "none"


@pytest.mark.parametrize("word", ["null", "n/a", "-"])
def test_other_null_words_still_null_for_mortgage_status(monkeypatch, tmp_path, word):
    fake_ollama(monkeypatch, {"mortgage_status": word, "village": "Pune"})
    assert set(vlm_extract(image(tmp_path), DocType.LAND_DEED)) == {"village"}


def test_a_real_value_that_merely_contains_a_null_word_is_kept(monkeypatch, tmp_path):
    fake_ollama(monkeypatch, {"owner_name": "Nonesuch Trust", "village": "N/A Nagar"})
    result = vlm_extract(image(tmp_path), DocType.LAND_DEED)
    assert (result["owner_name"].value, result["village"].value) == ("Nonesuch Trust", "N/A Nagar")


def test_null_words_inside_programs_are_dropped(monkeypatch, tmp_path):
    fake_ollama(monkeypatch, {"body": "NBA", "programs": ["N/A", "BE Computer", "-"]})
    result = vlm_extract(image(tmp_path), DocType.ACCREDITATION_CERT)
    assert result["programs"].value == ["BE Computer"]
    fake_ollama(monkeypatch, {"body": "NBA", "programs": ["none"]})
    assert "programs" not in vlm_extract(image(tmp_path), DocType.ACCREDITATION_CERT)


# ---- mortgage_status: trimmed and lowercased ----


@pytest.mark.parametrize(
    "given, kept",
    [("none", "none"), ("None", "none"), (" NONE ", "none"), ("Mortgaged", "mortgaged"),
     (" mortgaged\n", "mortgaged")],
)  # fmt: skip
def test_mortgage_status_is_trimmed_and_lowercased(monkeypatch, tmp_path, given, kept):
    fake_ollama(monkeypatch, {"mortgage_status": given})
    assert vlm_extract(image(tmp_path), DocType.LAND_DEED)["mortgage_status"].value == kept


def test_other_text_fields_keep_their_case(monkeypatch, tmp_path):
    fake_ollama(monkeypatch, {"owner_name": "Shree Vidya Education Trust", "village": " Pune "})
    result = vlm_extract(image(tmp_path), DocType.LAND_DEED)
    assert result["owner_name"].value == "Shree Vidya Education Trust"
    assert result["village"].value == " Pune "  # copied exactly as printed


def test_vlm_none_reaches_the_mortgage_rule_as_a_pass(monkeypatch, tmp_path):
    from docverf.reasoning.rule_engine import load_checklist, run_rules

    fake_ollama(monkeypatch, {"mortgage_status": "None"})
    fields = vlm_extract(image(tmp_path), DocType.LAND_DEED)
    for f in fields.values():
        f.confidence = 0.9  # as after a two-extractor merge
    deed = ExtractionResult(
        doc_id="appx_land_deed", app_id="appx", doc_type=DocType.LAND_DEED, fields=fields
    )
    findings = run_rules("appx", [deed], load_checklist("eoa"))
    assert [f.rule_id for f in findings if f.rule_id == "LAND_NOT_MORTGAGED"] == []

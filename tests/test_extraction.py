"""Focused tests for the extraction normalization layer (TRD §10).

Covers ``devanagari_to_ascii_digits``, ``normalize_date``, and
``normalize_area`` for valid inputs, Devanagari digits, invalid dates,
missing units, and unsupported area formats.
"""

import json
import subprocess
import sys

import pytest
from docverf.extraction.classify import classify
from docverf.extraction.confidence import field_confidence
from docverf.extraction.layout import detect_regions
from docverf.extraction.normalize import (
    devanagari_to_ascii_digits,
    normalize_area,
    normalize_date,
)
from docverf.extraction.rules_extractor import rules_extract
from docverf.extraction.vlm import vlm_extract
from docverf.schemas import DocType, ExtractionResult, FieldValue, Region


def test_devanagari_to_ascii_digits_converts_all_digits():
    assert devanagari_to_ascii_digits("०१२३४५६७८९") == "0123456789"


def test_devanagari_to_ascii_digits_preserves_other_chars():
    assert devanagari_to_ascii_digits("२.१० एकर") == "2.10 एकर"
    assert devanagari_to_ascii_digits("abc१२३xyz") == "abc123xyz"
    assert devanagari_to_ascii_digits("no digits here") == "no digits here"


def test_devanagari_to_ascii_digits_empty():
    assert devanagari_to_ascii_digits("") == ""


def test_normalize_date_iso_input():
    assert normalize_date("2027-01-20") == "2027-01-20"
    assert normalize_date("2009-04-15") == "2009-04-15"


def test_normalize_date_day_first_formats():
    assert normalize_date("15/04/2009") == "2009-04-15"
    assert normalize_date("03-02-2010") == "2010-02-03"
    assert normalize_date("2027/01/20") == "2027-01-20"


def test_normalize_date_named_month_formats():
    assert normalize_date("15 April 2009") == "2009-04-15"
    assert normalize_date("April 15, 2009") == "2009-04-15"
    assert normalize_date("15 Apr 2009") == "2009-04-15"


def test_normalize_date_devanagari_digits():
    assert normalize_date("१५/०४/२००९") == "2009-04-15"


def test_normalize_date_invalid_returns_none():
    assert normalize_date("") is None
    assert normalize_date("not a date") is None
    assert normalize_date("2023-13-01") is None  # invalid month
    assert normalize_date("30/02/2023") is None  # impossible date


def test_normalize_date_ambiguous_two_digit_year_returns_none():
    # Two-digit year: century cannot be determined -> reject rather than guess.
    assert normalize_date("01/02/23") is None
    assert normalize_date("1-2-99") is None


def test_normalize_area_valid():
    assert normalize_area("2.5 acre") == (2.5, "acre")
    assert normalize_area("1200 sqm") == (1200.0, "sqm")
    assert normalize_area("0.001 hectare") == (0.001, "hectare")


def test_normalize_area_devanagari_digits_and_unit():
    # Devanagari digits converted to ASCII; Marathi unit preserved as written.
    assert normalize_area("२.१० एकर") == (2.10, "एकर")


def test_normalize_area_missing_unit_returns_none():
    assert normalize_area("2.5") is None
    assert normalize_area("") is None


def test_normalize_area_unit_first_returns_none():
    assert normalize_area("acre 2.5") is None


def test_normalize_area_unsupported_format_returns_none():
    assert normalize_area("abc") is None
    assert normalize_area("2.5 123") is None  # unit contains digits
    assert normalize_area("2.5acre") is None  # no separator


def test_field_confidence_both_agree_valid_format():
    assert field_confidence(0.9, True, True) == 0.9
    assert field_confidence(1.0, True, True) == 1.0


def test_field_confidence_one_extractor_valid_format():
    assert field_confidence(0.9, None, True) == 0.54


def test_field_confidence_disagree_valid_format():
    assert field_confidence(0.9, False, True) == pytest.approx(0.36)


def test_field_confidence_both_agree_invalid_format():
    assert field_confidence(0.9, True, False) == pytest.approx(0.45)


def test_field_confidence_one_extractor_invalid_format():
    assert field_confidence(0.9, None, False) == pytest.approx(0.27)


def test_field_confidence_disagree_invalid_format():
    assert field_confidence(0.9, False, False) == pytest.approx(0.18)


def test_field_confidence_ocr_confidence_clamped_below_zero():
    assert field_confidence(-0.5, True, True) == 0.0


def test_field_confidence_ocr_confidence_clamped_above_one():
    assert field_confidence(1.5, True, True) == 1.0


def test_field_confidence_result_clamped_to_one():
    assert field_confidence(1.0, True, True) == 1.0


def test_field_confidence_zero_confidence():
    assert field_confidence(0.0, True, True) == 0.0
    assert field_confidence(0.0, None, True) == 0.0
    assert field_confidence(0.0, False, True) == 0.0


def _make_image(tmp_path, width=100, height=100):
    from PIL import Image

    img = Image.new("RGB", (width, height), color="white")
    path = tmp_path / "page.png"
    img.save(path)
    return path


def _fake_settings(engine):
    class FakeSettings:
        OCR_ENGINE = engine

    return FakeSettings()


def test_run_ocr_paddleocr_valid(monkeypatch, tmp_path):
    import docverf.extraction.ocr as ocr_module

    path = _make_image(tmp_path)

    def fake_paddle(image_path):
        return [
            {
                "text": "Hello",
                "confidence": 0.95,
                "bbox": [(10, 10), (90, 10), (90, 30), (10, 30)],
            },
            {
                "text": "World",
                "confidence": 0.88,
                "bbox": [10, 40, 90, 40, 90, 60, 10, 60],
            },
        ]

    monkeypatch.setattr(ocr_module, "get_settings", lambda: _fake_settings("paddleocr"))
    monkeypatch.setattr(ocr_module, "_run_paddleocr", fake_paddle)
    monkeypatch.setattr(
        ocr_module,
        "_run_surya",
        lambda p: (_ for _ in ()).throw(AssertionError("surya should not be called")),
    )

    words = ocr_module.run_ocr(path)
    assert len(words) == 2
    assert words[0]["text"] == "Hello"
    assert words[0]["confidence"] == 0.95
    assert words[0]["bbox"] == [0.10, 0.10, 0.90, 0.30]
    assert words[1]["text"] == "World"
    assert words[1]["bbox"] == [0.10, 0.40, 0.90, 0.60]
    for w in words:
        assert all(0.0 <= v <= 1.0 for v in w["bbox"])
        assert 0.0 <= w["confidence"] <= 1.0


def test_run_ocr_surya_valid(monkeypatch, tmp_path):
    import docverf.extraction.ocr as ocr_module

    path = _make_image(tmp_path)

    def fake_surya(image_path):
        return [
            {"text": "Namaste", "confidence": 0.9, "bbox": [(5, 5), (50, 5), (50, 25), (5, 25)]},
        ]

    monkeypatch.setattr(ocr_module, "get_settings", lambda: _fake_settings("surya"))
    monkeypatch.setattr(
        ocr_module,
        "_run_paddleocr",
        lambda p: (_ for _ in ()).throw(AssertionError("paddleocr should not be called")),
    )
    monkeypatch.setattr(ocr_module, "_run_surya", fake_surya)

    words = ocr_module.run_ocr(path)
    assert len(words) == 1
    assert words[0]["text"] == "Namaste"
    assert words[0]["confidence"] == 0.9
    assert words[0]["bbox"] == [0.05, 0.05, 0.50, 0.25]


def test_run_ocr_skips_empty_text(monkeypatch, tmp_path):
    import docverf.extraction.ocr as ocr_module

    path = _make_image(tmp_path)

    def fake_paddle(image_path):
        return [
            {"text": "", "confidence": 0.9, "bbox": [0, 0, 10, 10]},
            {"text": "   ", "confidence": 0.8, "bbox": [0, 0, 10, 10]},
            {"text": "Valid", "confidence": 0.7, "bbox": [0, 0, 50, 50]},
        ]

    monkeypatch.setattr(ocr_module, "get_settings", lambda: _fake_settings("paddleocr"))
    monkeypatch.setattr(ocr_module, "_run_paddleocr", fake_paddle)
    monkeypatch.setattr(ocr_module, "_run_surya", lambda p: [])

    words = ocr_module.run_ocr(path)
    assert len(words) == 1
    assert words[0]["text"] == "Valid"


def test_run_ocr_skips_invalid_bbox(monkeypatch, tmp_path):
    import docverf.extraction.ocr as ocr_module

    path = _make_image(tmp_path)

    def fake_paddle(image_path):
        return [
            {"text": "BadBox", "confidence": 0.9, "bbox": None},
            {"text": "Good", "confidence": 0.8, "bbox": [10, 10, 90, 90]},
        ]

    monkeypatch.setattr(ocr_module, "get_settings", lambda: _fake_settings("paddleocr"))
    monkeypatch.setattr(ocr_module, "_run_paddleocr", fake_paddle)
    monkeypatch.setattr(ocr_module, "_run_surya", lambda p: [])

    words = ocr_module.run_ocr(path)
    assert len(words) == 1
    assert words[0]["text"] == "Good"


def test_run_ocr_confidence_clamped(monkeypatch, tmp_path):
    import docverf.extraction.ocr as ocr_module

    path = _make_image(tmp_path)

    def fake_paddle(image_path):
        return [
            {"text": "Low", "confidence": -0.5, "bbox": [10, 10, 50, 50]},
            {"text": "High", "confidence": 1.5, "bbox": [10, 10, 50, 50]},
        ]

    monkeypatch.setattr(ocr_module, "get_settings", lambda: _fake_settings("paddleocr"))
    monkeypatch.setattr(ocr_module, "_run_paddleocr", fake_paddle)
    monkeypatch.setattr(ocr_module, "_run_surya", lambda p: [])

    words = ocr_module.run_ocr(path)
    assert words[0]["confidence"] == 0.0
    assert words[1]["confidence"] == 1.0


def test_run_ocr_missing_file_raises(tmp_path):
    import docverf.extraction.ocr as ocr_module

    missing = tmp_path / "does_not_exist.png"
    try:
        ocr_module.run_ocr(missing)
    except FileNotFoundError as exc:
        assert "does_not_exist.png" in str(exc)
    else:
        raise AssertionError("Expected FileNotFoundError")


def test_run_ocr_unsupported_engine_raises(monkeypatch, tmp_path):
    import docverf.extraction.ocr as ocr_module

    path = _make_image(tmp_path)

    monkeypatch.setattr(ocr_module, "get_settings", lambda: _fake_settings("tesseract"))

    try:
        ocr_module.run_ocr(path)
    except ValueError as exc:
        assert "Unsupported OCR_ENGINE" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_run_ocr_normalizes_coordinates_to_zero_one(monkeypatch, tmp_path):
    import docverf.extraction.ocr as ocr_module

    path = _make_image(tmp_path, width=200, height=100)

    def fake_paddle(image_path):
        return [
            {"text": "X", "confidence": 0.5, "bbox": [20, 10, 180, 90]},
        ]

    monkeypatch.setattr(ocr_module, "get_settings", lambda: _fake_settings("paddleocr"))
    monkeypatch.setattr(ocr_module, "_run_paddleocr", fake_paddle)
    monkeypatch.setattr(ocr_module, "_run_surya", lambda p: [])

    words = ocr_module.run_ocr(path)
    assert len(words) == 1
    assert words[0]["bbox"] == [0.10, 0.10, 0.90, 0.90]


def test_run_ocr_skips_degenerate_bbox(monkeypatch, tmp_path):
    import docverf.extraction.ocr as ocr_module

    path = _make_image(tmp_path, width=200, height=100)

    def fake_paddle(image_path):
        return [
            {"text": "X", "confidence": 0.5, "bbox": [200, 100, 200, 100]},
        ]

    monkeypatch.setattr(ocr_module, "get_settings", lambda: _fake_settings("paddleocr"))
    monkeypatch.setattr(ocr_module, "_run_paddleocr", fake_paddle)
    monkeypatch.setattr(ocr_module, "_run_surya", lambda p: [])

    assert ocr_module.run_ocr(path) == []


def _word(text, conf=0.9, x1=0.1, y1=0.2, x2=0.3, y2=0.25, page=1):
    return {
        "text": text,
        "confidence": conf,
        "bbox": [x1, y1, x2, y2],
        "page": page,
    }


def _line(words, y=0.2):
    # place words left-to-right on the same line
    x = 0.1
    out = []
    for w in words:
        out.append(_word(w, x1=x, y1=y, x2=x + 0.15, y2=y + 0.05))
        x += 0.16
    return out


def test_rules_extract_land_deed():
    words = []
    words += _line(["Owner:", "श्री", "विद्या", "चॅरिटेबल", "सोसायटी"], y=0.30)
    words += _line(["Survey", "No:", "45/2"], y=0.36)
    words += _line(["Area:", "2.10", "एकर"], y=0.41)
    words += _line(["Village:", "Pune"], y=0.46)
    words += _line(["District:", "Pune"], y=0.51)
    words += _line(["Registration", "No:", "REG12345"], y=0.56)
    words += _line(["Registration", "Date:", "03/02/2010"], y=0.61)
    words += _line(["Mortgage:", "none"], y=0.66)

    result = rules_extract(words, DocType.LAND_DEED)
    assert "owner_name" in result
    assert result["owner_name"].value == "श्री विद्या चॅरिटेबल सोसायटी"
    assert result["owner_name"].raw == "श्री विद्या चॅरिटेबल सोसायटी"
    assert result["survey_no"].value == "45/2"
    assert result["area"].value == 2.10
    assert result["area"].unit == "एकर"
    assert result["registration_date"].value == "2010-02-03"
    assert result["mortgage_status"].value == "none"
    # confidence/bbox/page propagated
    assert 0.0 <= result["owner_name"].confidence <= 1.0
    assert result["owner_name"].page == 1
    assert result["owner_name"].bbox == pytest.approx([0.26, 0.3, 0.89, 0.35])
    assert result["owner_name"].extractor_agreement is None


def test_rules_extract_noc():
    words = []
    words += _line(["Issuer:", "Maharashtra", "Fire", "Services"], y=0.30)
    words += _line(["Ref", "No:", "FIRE/MH/2008/004512"], y=0.36)
    words += _line(["Institute:", "Shree", "Vidya", "Institute"], y=0.41)
    words += _line(["Purpose:", "Approval"], y=0.46)
    words += _line(["Issue", "Date:", "10/06/2008"], y=0.51)
    words += _line(["Valid", "Until:", "31/12/2027"], y=0.56)
    words += _line(["Signatory:", "John", "Doe"], y=0.61)

    result = rules_extract(words, DocType.NOC)
    assert result["issuer"].value == "Maharashtra Fire Services"
    assert result["ref_no"].value == "FIRE/MH/2008/004512"
    assert result["institute_name"].value == "Shree Vidya Institute"
    assert result["issue_date"].value == "2008-06-10"
    assert result["valid_until"].value == "2027-12-31"
    assert result["signatory"].value == "John Doe"
    assert result["ref_no"].confidence == pytest.approx(0.9 * 0.6 * 1.0)


def test_rules_extract_affidavit():
    words = []
    words += _line(["Deponent:", "Jane", "Smith"], y=0.30)
    words += _line(["Institute:", "Shree", "Vidya"], y=0.36)
    words += _line(["Application", "No:", "1-46200000001"], y=0.41)
    words += _line(["Date:", "18/01/2027"], y=0.46)
    words += _line(["Land", "Area:", "2.5", "acre"], y=0.51)
    words += _line(["Notary", "Reg", "No:", "N999"], y=0.56)

    result = rules_extract(words, DocType.AFFIDAVIT)
    assert result["deponent_name"].value == "Jane Smith"
    assert result["institute_name"].value == "Shree Vidya"
    assert result["application_no"].value == "1-46200000001"
    assert result["date"].value == "2027-01-18"
    assert result["land_area_declared"].value == 2.5
    assert result["land_area_declared"].unit == "acre"
    assert result["notary_reg_no"].value == "N999"


def test_rules_extract_devanagari_digits():
    words = []
    words += _line(["Survey", "No:", "४५/२"], y=0.36)
    words += _line(["Area:", "२.१०", "एकर"], y=0.41)
    words += _line(["Registration", "Date:", "०३/०२/२०१०"], y=0.61)

    result = rules_extract(words, DocType.LAND_DEED)
    assert result["survey_no"].value == "45/2"
    assert result["area"].value == 2.10
    assert result["registration_date"].value == "2010-02-03"


def test_rules_extract_missing_fields_omitted():
    words = _line(["Owner:", "Alice"], y=0.30)
    # only owner present; survey_no, area, etc. missing
    result = rules_extract(words, DocType.LAND_DEED)
    assert "owner_name" in result
    assert "survey_no" not in result
    assert "area" not in result
    assert "mortgage_status" not in result


def test_rules_extract_empty_ocr():
    assert rules_extract([], DocType.LAND_DEED) == {}
    assert rules_extract([], DocType.NOC) == {}
    assert rules_extract([], DocType.AFFIDAVIT) == {}


def test_rules_extract_unsupported_doc_type():
    words = _line(["Owner:", "Alice"], y=0.30)
    assert rules_extract(words, DocType.APPLICATION_FORM) == {}
    assert rules_extract(words, DocType.LAB_PHOTO) == {}


def test_rules_extract_mortgage_mortgaged():
    words = _line(["Mortgage:", "mortgaged"], y=0.66)
    result = rules_extract(words, DocType.LAND_DEED)
    assert result["mortgage_status"].value == "mortgaged"


def test_rules_extract_confidence_bbox_propagation():
    words = _line(["Survey", "No:", "45/2"], y=0.36)
    result = rules_extract(words, DocType.LAND_DEED)
    fv = result["survey_no"]
    assert fv.bbox == pytest.approx([0.42, 0.36, 0.57, 0.41])
    assert fv.page == 1
    assert fv.confidence == pytest.approx(0.9 * 0.6 * 1.0)
    assert fv.extractor_agreement is None


def _make_image_file(tmp_path, name="page.png"):
    from PIL import Image

    img = Image.new("RGB", (200, 100), color="white")
    path = tmp_path / name
    img.save(path)
    return path


def test_vlm_extract_success(monkeypatch, tmp_path):
    import docverf.extraction.vlm as vlm_module

    path = _make_image_file(tmp_path)

    def fake_generate(settings, model, image_b64, prompt):
        return (
            '{"owner_name": "Alice", "survey_no": "45/2", "area": 2.5, "mortgage_status": "none"}'
        )

    monkeypatch.setattr(vlm_module, "_ollama_generate", fake_generate)

    result = vlm_extract(path, DocType.LAND_DEED)
    assert result["owner_name"].value == "Alice"
    assert result["owner_name"].raw == "Alice"
    assert result["survey_no"].value == "45/2"
    assert result["area"].value == 2.5
    assert result["mortgage_status"].value == "none"
    assert result["owner_name"].confidence == 0.5
    assert result["owner_name"].page is None
    assert result["owner_name"].bbox is None
    assert result["owner_name"].extractor_agreement is None


def test_vlm_extract_invalid_json_then_retry(monkeypatch, tmp_path):
    import docverf.extraction.vlm as vlm_module

    path = _make_image_file(tmp_path)
    calls = {"n": 0}

    def fake_generate(settings, model, image_b64, prompt):
        calls["n"] += 1
        if calls["n"] == 1:
            return "not json {{{"
        return '{"owner_name": "Bob"}'

    monkeypatch.setattr(vlm_module, "_ollama_generate", fake_generate)

    result = vlm_extract(path, DocType.LAND_DEED)
    assert calls["n"] == 2
    assert result["owner_name"].value == "Bob"


def test_vlm_extract_repeated_invalid_returns_empty(monkeypatch, tmp_path):
    import docverf.extraction.vlm as vlm_module

    path = _make_image_file(tmp_path)

    def fake_generate(settings, model, image_b64, prompt):
        return "still not json"

    monkeypatch.setattr(vlm_module, "_ollama_generate", fake_generate)

    result = vlm_extract(path, DocType.LAND_DEED)
    assert result == {}


def test_vlm_extract_missing_image(tmp_path):
    missing = tmp_path / "does_not_exist.png"
    try:
        vlm_extract(missing, DocType.LAND_DEED)
    except FileNotFoundError as exc:
        assert "does_not_exist.png" in str(exc)
    else:
        raise AssertionError("Expected FileNotFoundError")


def test_vlm_extract_unsupported_doc_type(tmp_path, monkeypatch):
    import docverf.extraction.vlm as vlm_module

    path = _make_image_file(tmp_path)

    def fake_generate(settings, model, image_b64, prompt):
        return "{}"

    monkeypatch.setattr(vlm_module, "_ollama_generate", fake_generate)

    try:
        vlm_extract(path, DocType.APPLICATION_FORM)  # JSON form: no VLM extraction
    except ValueError as exc:
        assert "Unsupported doc_type" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_vlm_extract_ollama_connection_failure(monkeypatch, tmp_path):
    import urllib.error

    import docverf.extraction.vlm as vlm_module

    path = _make_image_file(tmp_path)

    def fake_generate(settings, model, image_b64, prompt):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(vlm_module, "_ollama_generate", fake_generate)

    try:
        vlm_extract(path, DocType.LAND_DEED)
    except ConnectionError as exc:
        assert "Ollama unavailable" in str(exc)
    else:
        raise AssertionError("Expected ConnectionError")


def test_vlm_extract_filters_unknown_fields(monkeypatch, tmp_path):
    import docverf.extraction.vlm as vlm_module

    path = _make_image_file(tmp_path)

    def fake_generate(settings, model, image_b64, prompt):
        return '{"owner_name": "Alice", "made_up_field": 123}'

    monkeypatch.setattr(vlm_module, "_ollama_generate", fake_generate)

    result = vlm_extract(path, DocType.LAND_DEED)
    assert "owner_name" in result
    assert "made_up_field" not in result


def test_vlm_extract_uses_fallback_model(monkeypatch, tmp_path):
    import docverf.extraction.vlm as vlm_module

    path = _make_image_file(tmp_path)
    seen = {}

    def fake_generate(settings, model, image_b64, prompt):
        seen["model"] = model
        return "{}"

    monkeypatch.setattr(vlm_module, "_ollama_generate", fake_generate)

    # VLM_MODEL blank -> should use fallback.
    class BlankSettings:
        OLLAMA_URL = "http://localhost:11434"
        VLM_MODEL = ""

    monkeypatch.setattr(vlm_module, "get_settings", lambda: BlankSettings())

    vlm_extract(path, DocType.LAND_DEED)
    assert seen["model"] == "qwen3-vl:2b-instruct-q4_K_M"


def test_classify_all_six_types_keyword(tmp_path):
    cases = {
        "land deed": DocType.LAND_DEED,
        "no objection certificate": DocType.NOC,
        "affidavit deponent notary": DocType.AFFIDAVIT,
        "accreditation nba cert no": DocType.ACCREDITATION_CERT,
        "laboratory equipment room label": DocType.LAB_PHOTO,
        "application form aicte intake": DocType.APPLICATION_FORM,
    }
    for content, expected in cases.items():
        p = tmp_path / "doc.pdf"
        p.write_text(content)
        assert classify(p) == expected


def test_classify_keyword_from_content(tmp_path):
    p = tmp_path / "doc.pdf"
    p.write_text("This is a No Objection Certificate issued by fire services.")
    assert classify(p) == DocType.NOC


def test_classify_devanagari_content(tmp_path):
    p = tmp_path / "deed.pdf"
    p.write_text("land deed survey no registration mortgage")
    assert classify(p) == DocType.LAND_DEED


def test_classify_default_application_form(tmp_path):
    p = tmp_path / "unknown.pdf"
    p.write_text("random document with no keywords")
    assert classify(p) == DocType.APPLICATION_FORM


def test_classify_missing_file(tmp_path):
    missing = tmp_path / "does_not_exist.pdf"
    try:
        classify(missing)
    except FileNotFoundError as exc:
        assert "does_not_exist.pdf" in str(exc)
    else:
        raise AssertionError("Expected FileNotFoundError")


def test_classify_returns_doc_type_enum(tmp_path):
    p = tmp_path / "noc.pdf"
    p.write_text("no objection certificate")
    result = classify(p)
    assert isinstance(result, DocType)
    assert result == DocType.NOC


def test_detect_regions_blank_image_returns_empty(tmp_path):
    path = _make_image_file(tmp_path, name="blank.png")
    # blank white image -> no dark content -> empty list
    assert detect_regions(path) == []


def test_detect_regions_text_block(tmp_path):
    path = _make_image_file(tmp_path, name="text.png")
    # draw dark content by creating an image with a dark rectangle
    from PIL import Image, ImageDraw

    img = Image.new("L", (200, 100), color=255)
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 20, 180, 80], fill=0)  # dark text block
    img.save(path)

    regions = detect_regions(path)
    assert len(regions) == 1
    assert regions[0].type == "text_block"
    assert regions[0].page == 1
    assert len(regions[0].bbox) == 4
    assert all(0.0 <= v <= 1.0 for v in regions[0].bbox)
    assert regions[0].bbox[0] < regions[0].bbox[2]
    assert regions[0].bbox[1] < regions[0].bbox[3]


def test_detect_regions_missing_file(tmp_path):
    missing = tmp_path / "does_not_exist.png"
    try:
        detect_regions(missing)
    except FileNotFoundError as exc:
        assert "does_not_exist.png" in str(exc)
    else:
        raise AssertionError("Expected FileNotFoundError")


def test_detect_regions_region_type_valid(tmp_path):
    from PIL import Image, ImageDraw

    path = _make_image_file(tmp_path, name="region.png")
    img = Image.new("L", (200, 100), color=255)
    draw = ImageDraw.Draw(img)
    draw.rectangle([10, 10, 190, 90], fill=0)
    img.save(path)

    regions = detect_regions(path)
    for r in regions:
        assert r.type in {"signature", "seal", "qr", "photo", "table", "text_block"}
        assert isinstance(r, Region)
        assert r.page == 1
        assert len(r.bbox) == 4


def _fv(value, unit=None, raw=None, confidence=0.9, page=1, bbox=None, agreement=None):
    return FieldValue(
        value=value,
        unit=unit,
        raw=raw,
        confidence=confidence,
        page=page,
        bbox=bbox,
        extractor_agreement=agreement,
    )


def _make_test_image(tmp_path, name="page.png"):
    from PIL import Image

    img = Image.new("RGB", (1000, 1000), color="white")
    path = tmp_path / name
    img.save(path)
    return path


def test_extract_image_supplied_doctype(monkeypatch, tmp_path):
    import docverf.extraction.extract as extract_module

    path = _make_test_image(tmp_path)

    monkeypatch.setattr(extract_module, "_check_quality", lambda p, t: (True, None))
    monkeypatch.setattr(extract_module, "classify", lambda p: DocType.APPLICATION_FORM)
    monkeypatch.setattr(extract_module, "detect_regions", lambda p: [])
    monkeypatch.setattr(extract_module, "run_ocr", lambda p: [])
    monkeypatch.setattr(
        extract_module,
        "rules_extract",
        lambda words, dt: {"owner_name": _fv("Alice")},
    )
    monkeypatch.setattr(
        extract_module,
        "vlm_extract",
        lambda p, dt: {"owner_name": _fv("Alice")},
    )

    result = extract_module.extract(str(path), "app001", "app001", DocType.LAND_DEED)
    assert result.doc_id == "app001"
    assert result.app_id == "app001"
    assert result.doc_type == DocType.LAND_DEED
    assert "owner_name" in result.fields
    assert result.fields["owner_name"].value == "Alice"
    assert result.page_count == 1
    assert "ocr" in result.engines
    assert "vlm" in result.engines


def test_extract_inferred_doctype(monkeypatch, tmp_path):
    import docverf.extraction.extract as extract_module

    path = _make_test_image(tmp_path)

    monkeypatch.setattr(extract_module, "_check_quality", lambda p, t: (True, None))
    monkeypatch.setattr(extract_module, "classify", lambda p: DocType.NOC)
    monkeypatch.setattr(extract_module, "detect_regions", lambda p: [])
    monkeypatch.setattr(extract_module, "run_ocr", lambda p: [])
    monkeypatch.setattr(
        extract_module,
        "rules_extract",
        lambda words, dt: {"issuer": _fv("Fire Dept")},
    )
    monkeypatch.setattr(
        extract_module,
        "vlm_extract",
        lambda p, dt: {"issuer": _fv("Fire Dept")},
    )

    result = extract_module.extract(str(path), "app002", "app002")
    assert result.doc_type == DocType.NOC


def test_extract_multi_page_pdf(monkeypatch, tmp_path):
    import docverf.extraction.extract as extract_module

    page1 = _make_test_image(tmp_path, "page1.png")
    page2 = _make_test_image(tmp_path, "page2.png")

    monkeypatch.setattr(
        extract_module,
        "_render_pdf_pages",
        lambda p: [(1, page1), (2, page2)],
    )
    monkeypatch.setattr(extract_module, "_check_quality", lambda p, t: (True, None))
    monkeypatch.setattr(extract_module, "classify", lambda p: DocType.LAND_DEED)
    monkeypatch.setattr(
        extract_module,
        "detect_regions",
        lambda p: [Region(type="text_block", page=1, bbox=[0.1, 0.1, 0.9, 0.9])],
    )
    monkeypatch.setattr(
        extract_module,
        "run_ocr",
        lambda p: [{"text": "x", "confidence": 0.9, "bbox": [0.1, 0.1, 0.2, 0.2]}],
    )
    monkeypatch.setattr(
        extract_module,
        "rules_extract",
        lambda words, dt: {"owner_name": _fv("Alice", bbox=[0.1, 0.1, 0.2, 0.2])},
    )
    monkeypatch.setattr(
        extract_module,
        "vlm_extract",
        lambda p, dt: {"owner_name": _fv("Alice")},
    )

    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_text("fake pdf")
    result = extract_module.extract(str(pdf_path), "app003", "app003")
    assert result.page_count == 2
    assert len(result.regions) == 2
    assert result.regions[0].page == 1
    assert result.regions[1].page == 2


def test_extract_quality_gate_failure(monkeypatch, tmp_path):
    import docverf.extraction.extract as extract_module

    path = _make_test_image(tmp_path)

    monkeypatch.setattr(
        extract_module,
        "_check_quality",
        lambda p, t: (False, "shorter side 400px < 800px"),
    )

    result = extract_module.extract(str(path), "app004", "app004")
    assert result.fields == {}
    assert len(result.warnings) > 0
    assert "quality" in result.warnings[0].lower() or "shorter side" in result.warnings[0]


def test_extract_merge_both_agree(monkeypatch, tmp_path):
    import docverf.extraction.extract as extract_module

    path = _make_test_image(tmp_path)

    monkeypatch.setattr(extract_module, "_check_quality", lambda p, t: (True, None))
    monkeypatch.setattr(extract_module, "classify", lambda p: DocType.LAND_DEED)
    monkeypatch.setattr(extract_module, "detect_regions", lambda p: [])
    monkeypatch.setattr(extract_module, "run_ocr", lambda p: [])
    monkeypatch.setattr(
        extract_module,
        "rules_extract",
        lambda words, dt: {"owner_name": _fv("Alice", confidence=0.9)},
    )
    monkeypatch.setattr(
        extract_module,
        "vlm_extract",
        lambda p, dt: {"owner_name": _fv("Alice", confidence=0.8)},
    )

    result = extract_module.extract(str(path), "app005", "app005", DocType.LAND_DEED)
    fv = result.fields["owner_name"]
    assert fv.value == "Alice"
    assert fv.extractor_agreement is True
    # agreement_factor=1.0, format_valid=1.0 -> confidence = 0.9 * 1.0 * 1.0 = 0.9
    assert fv.confidence == pytest.approx(0.9 * 1.0 * 1.0)


def test_extract_merge_disagree(monkeypatch, tmp_path):
    import docverf.extraction.extract as extract_module

    path = _make_test_image(tmp_path)

    monkeypatch.setattr(extract_module, "_check_quality", lambda p, t: (True, None))
    monkeypatch.setattr(extract_module, "classify", lambda p: DocType.LAND_DEED)
    monkeypatch.setattr(extract_module, "detect_regions", lambda p: [])
    monkeypatch.setattr(extract_module, "run_ocr", lambda p: [])
    monkeypatch.setattr(
        extract_module,
        "rules_extract",
        lambda words, dt: {"owner_name": _fv("Alice", confidence=0.9)},
    )
    monkeypatch.setattr(
        extract_module,
        "vlm_extract",
        lambda p, dt: {"owner_name": _fv("Bob", confidence=0.8)},
    )

    result = extract_module.extract(str(path), "app006", "app006", DocType.LAND_DEED)
    fv = result.fields["owner_name"]
    # Prefer rules on disagreement
    assert fv.value == "Alice"
    assert fv.extractor_agreement is False
    # agreement_factor=0.4
    assert fv.confidence == pytest.approx(0.9 * 0.4 * 1.0)


def test_extract_merge_only_rules(monkeypatch, tmp_path):
    import docverf.extraction.extract as extract_module

    path = _make_test_image(tmp_path)

    monkeypatch.setattr(extract_module, "_check_quality", lambda p, t: (True, None))
    monkeypatch.setattr(extract_module, "classify", lambda p: DocType.LAND_DEED)
    monkeypatch.setattr(extract_module, "detect_regions", lambda p: [])
    monkeypatch.setattr(extract_module, "run_ocr", lambda p: [])
    monkeypatch.setattr(
        extract_module,
        "rules_extract",
        lambda words, dt: {"owner_name": _fv("Alice", confidence=0.9)},
    )
    monkeypatch.setattr(
        extract_module,
        "vlm_extract",
        lambda p, dt: {},
    )

    result = extract_module.extract(str(path), "app007", "app007", DocType.LAND_DEED)
    fv = result.fields["owner_name"]
    assert fv.value == "Alice"
    assert fv.extractor_agreement is None  # only one extractor
    # agreement_factor=0.6
    assert fv.confidence == pytest.approx(0.9 * 0.6 * 1.0)


def test_extract_vlm_unavailable(monkeypatch, tmp_path):
    import docverf.extraction.extract as extract_module

    path = _make_test_image(tmp_path)

    monkeypatch.setattr(extract_module, "_check_quality", lambda p, t: (True, None))
    monkeypatch.setattr(extract_module, "classify", lambda p: DocType.LAND_DEED)
    monkeypatch.setattr(extract_module, "detect_regions", lambda p: [])
    monkeypatch.setattr(extract_module, "run_ocr", lambda p: [])
    monkeypatch.setattr(
        extract_module,
        "rules_extract",
        lambda words, dt: {"owner_name": _fv("Alice")},
    )
    monkeypatch.setattr(
        extract_module,
        "vlm_extract",
        lambda p, dt: (_ for _ in ()).throw(ConnectionError("Ollama down")),
    )

    result = extract_module.extract(str(path), "app008", "app008", DocType.LAND_DEED)
    assert "owner_name" in result.fields
    assert len(result.warnings) > 0
    assert "VLM" in result.warnings[0] or "unavailable" in result.warnings[0].lower()


def test_extract_unsupported_doctype(monkeypatch, tmp_path):
    import docverf.extraction.extract as extract_module

    path = _make_test_image(tmp_path)

    monkeypatch.setattr(extract_module, "_check_quality", lambda p, t: (True, None))
    monkeypatch.setattr(extract_module, "classify", lambda p: DocType.APPLICATION_FORM)
    monkeypatch.setattr(extract_module, "detect_regions", lambda p: [])
    monkeypatch.setattr(extract_module, "run_ocr", lambda p: [])
    monkeypatch.setattr(
        extract_module,
        "rules_extract",
        lambda words, dt: {},
    )
    monkeypatch.setattr(
        extract_module,
        "vlm_extract",
        lambda p, dt: {},
    )

    result = extract_module.extract(str(path), "app009", "app009", DocType.APPLICATION_FORM)
    assert result.fields == {}
    assert result.doc_type == DocType.APPLICATION_FORM


def test_extract_schema_valid(monkeypatch, tmp_path):
    import docverf.extraction.extract as extract_module

    path = _make_test_image(tmp_path)

    monkeypatch.setattr(extract_module, "_check_quality", lambda p, t: (True, None))
    monkeypatch.setattr(extract_module, "classify", lambda p: DocType.LAND_DEED)
    monkeypatch.setattr(extract_module, "detect_regions", lambda p: [])
    monkeypatch.setattr(extract_module, "run_ocr", lambda p: [])
    monkeypatch.setattr(
        extract_module,
        "rules_extract",
        lambda words, dt: {"owner_name": _fv("Alice", confidence=0.9)},
    )
    monkeypatch.setattr(
        extract_module,
        "vlm_extract",
        lambda p, dt: {},
    )

    result = extract_module.extract(str(path), "app010", "app010", DocType.LAND_DEED)
    # Validate against schema
    validated = ExtractionResult.model_validate(result.model_dump())
    assert validated.doc_id == "app010"
    assert validated.app_id == "app010"
    assert validated.doc_type == DocType.LAND_DEED
    assert validated.page_count == 1
    assert isinstance(validated.fields, dict)
    assert isinstance(validated.regions, list)
    assert isinstance(validated.warnings, list)
    assert isinstance(validated.engines, dict)


def test_cli_help_output():
    """CLI --help should work and list --out."""
    run = subprocess.run(
        [sys.executable, "-m", "docverf.extraction", "--help"],
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0
    assert "--out" in run.stdout


def test_cli_single_file_mocked(monkeypatch, tmp_path):
    import docverf.extraction.__main__ as cli_module

    img = tmp_path / "land_deed.png"
    img.write_bytes(b"fake image data")

    captured = {}

    def fake_extract(file_path, doc_id, app_id, doc_type=None):
        captured["doc_id"] = doc_id
        captured["app_id"] = app_id
        captured["file_path"] = file_path
        from docverf.schemas import ExtractionResult

        return ExtractionResult(
            doc_id=doc_id,
            app_id=app_id,
            doc_type=DocType.LAND_DEED,
            fields={},
            regions=[],
            page_count=1,
            engines={},
            warnings=[],
        )

    monkeypatch.setattr(cli_module, "extract", fake_extract)

    out_dir = tmp_path / "out"
    exit_code = cli_module.main([str(img), "--out", str(out_dir)])
    assert exit_code == 0
    out_file = out_dir / "app001_land_deed.json"
    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["doc_id"] == "app001_land_deed"
    assert data["doc_type"] == "land_deed"


def test_cli_folder_processing_mocked(monkeypatch, tmp_path):
    import docverf.extraction.__main__ as cli_module

    (tmp_path / "a.pdf").write_bytes(b"fake pdf")
    (tmp_path / "b.png").write_bytes(b"fake image")
    (tmp_path / "ignore.txt").write_text("not a file")

    calls = []

    def fake_extract(file_path, doc_id, app_id, doc_type=None):
        calls.append((file_path, doc_id, app_id, doc_type))
        from docverf.schemas import ExtractionResult

        return ExtractionResult(
            doc_id=doc_id,
            app_id=app_id,
            doc_type=DocType.NOC,
            fields={},
            regions=[],
            page_count=1,
            engines={},
            warnings=[],
        )

    monkeypatch.setattr(cli_module, "extract", fake_extract)

    out_dir = tmp_path / "out"
    exit_code = cli_module.main([str(tmp_path), "--out", str(out_dir)])
    assert exit_code == 0
    assert len(calls) == 2  # only supported files
    processed = sorted(c[1] for c in calls)
    folder_name = tmp_path.name
    assert processed == [f"{folder_name}_a", f"{folder_name}_b"]
    out_files = sorted(p.name for p in out_dir.iterdir())
    assert out_files == [f"{folder_name}_a.json", f"{folder_name}_b.json"]


def test_cli_individual_file_failure(monkeypatch, tmp_path):
    import docverf.extraction.__main__ as cli_module

    (tmp_path / "ok.png").write_bytes(b"fake image")
    (tmp_path / "bad.png").write_bytes(b"fake image")

    def fake_extract(file_path, doc_id, app_id, doc_type=None):
        if "bad" in file_path:
            raise ValueError("processing failed")
        from docverf.schemas import ExtractionResult

        return ExtractionResult(
            doc_id=doc_id,
            app_id=app_id,
            doc_type=DocType.NOC,
            fields={},
            regions=[],
            page_count=1,
            engines={},
            warnings=[],
        )

    monkeypatch.setattr(cli_module, "extract", fake_extract)

    out_dir = tmp_path / "out"
    exit_code = cli_module.main([str(tmp_path), "--out", str(out_dir)])
    # One file failed, but the other succeeded -> exit code 1 (partial failure)
    assert exit_code == 1
    folder_name = tmp_path.name
    assert (out_dir / f"{folder_name}_ok.json").exists()
    assert not (out_dir / f"{folder_name}_bad.json").exists()


def test_cli_missing_input_path(tmp_path):
    missing = tmp_path / "does_not_exist"
    run = subprocess.run(
        [sys.executable, "-m", "docverf.extraction", str(missing)],
        capture_output=True,
        text=True,
    )
    assert run.returncode != 0
    assert "not found" in run.stderr.lower()


def test_cli_no_supported_files(tmp_path):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    run = subprocess.run(
        [sys.executable, "-m", "docverf.extraction", str(empty_dir)],
        capture_output=True,
        text=True,
    )
    assert run.returncode != 0
    assert "no supported files" in run.stderr.lower()

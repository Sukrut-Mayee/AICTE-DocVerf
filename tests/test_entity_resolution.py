"""Checkpoint 2: name normalisation, fuzzy matching and area units (TRD §8.1, §8.2)."""

import pytest
from docverf.reasoning.entity_resolution import names_match, normalize_id, normalize_name, to_acres


def test_normalize_expands_abbreviations_and_strips_punctuation():
    assert normalize_name("Shree Vidya Inst. of Tech.") == "shree vidya institute of technology"
    assert normalize_name("  ABC  Engg.,College ") == "abc engineering college"


def test_normalize_transliterates_devanagari():
    out = normalize_name("श्री विद्या")
    assert out.isascii() and "vidyA".lower() in out


def test_normalize_id_ignores_case_and_spaces_but_keeps_slash():
    assert normalize_id(" 45 / 2 ") == "45/2"
    assert normalize_id("E-12345/PUNE") == "e-12345/pune"


def test_names_match_uses_threshold():
    assert names_match("Shree Vidya Institute of Technology", "Shree Vidya Inst. of Tech.")
    assert names_match("Vidya Shree Institute", "Shree Vidya Institute")  # token order ignored
    assert not names_match("Shree Vidya Charitable Society", "Shree Vidya Education Trust")


@pytest.mark.parametrize(
    "value, unit, acres",
    [(2.5, "acre", 2.5), (1, "hectare", 2.47105), (4046.86, "sqm", 1.0), (40, "guntha", 1.0)],
)
def test_to_acres(value, unit, acres):
    assert to_acres(value, unit) == pytest.approx(acres, rel=1e-4)


@pytest.mark.parametrize("unit", ["bigha", "", None])
def test_to_acres_unknown_unit_raises(unit):
    with pytest.raises(ValueError, match="unknown area unit"):
        to_acres(1, unit)

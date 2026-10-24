"""Checkpoint 2: name normalisation, fuzzy matching and area units (TRD §8.1, §8.2)."""

import pytest
from docverf.reasoning.entity_resolution import names_match, normalize_id, normalize_name
from docverf.units import ACRES_PER_UNIT, acres_per_unit, to_acres


def test_normalize_expands_abbreviations_and_strips_punctuation():
    assert normalize_name("Shree Vidya Inst. of Tech.") == "shri vidya institute of technology"
    assert normalize_name("  ABC  Engg.,College ") == "abc engineering college"


def test_normalize_transliterates_devanagari():
    out = normalize_name("श्री विद्या")
    assert out.isascii() and "vidyA".lower() in out


def test_spelling_variants_are_unified():
    assert normalize_name("Shree Vidya Mahavidyalaya") == "shri vidya college"
    assert normalize_name("Sri Vidyalay") == normalize_name("Shri Vidyalaya")


def test_devanagari_shri_vidya_equals_latin_shree_vidya():
    """Sanskrit-origin words match across scripts; English loanwords (एज्युकेशन) do not."""
    assert normalize_name("श्री विद्या") == normalize_name("Shree Vidya") == "shri vidya"


def test_normalize_id_ignores_case_and_spaces_but_keeps_slash():
    assert normalize_id(" 45 / 2 ") == "45/2"
    assert normalize_id("E-12345/PUNE") == "e-12345/pune"


def test_names_match_uses_threshold():
    assert names_match("Shree Vidya Institute of Technology", "Shree Vidya Inst. of Tech.")
    assert names_match("Vidya Shree Institute", "Shree Vidya Institute")  # token order ignored
    assert not names_match("Shree Vidya Charitable Society", "Shree Vidya Education Trust")


def test_spelling_variant_names_match_but_different_bodies_do_not():
    assert names_match("Shree Vidya Education Trust", "Sri Vidya Education Trust")
    assert not names_match("Sri Vidya Charitable Society", "Shree Vidya Education Trust")


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


UNIT_SPELLINGS = {
    "acre": ["acre", "acres", "ac", "Acres", " ACRE ", "एकर"],
    "hectare": ["hectare", "hectares", "ha", "Hectares", "हेक्टर"],
    "sqm": [
        "sqm",
        "sq m",
        "sq.m",
        "Sq. M.",
        "square metre",
        "Square Metres",
        "square meter",
        "square meters",
    ],
    "guntha": ["guntha", "gunthas", "Guntha", "गुंठा"],
}


@pytest.mark.parametrize(
    "unit, canonical",
    [(spelling, canon) for canon, spellings in UNIT_SPELLINGS.items() for spelling in spellings],
)
def test_unit_spellings_convert_like_the_canonical_unit(unit, canonical):
    assert to_acres(3, unit) == to_acres(3, canonical)
    assert acres_per_unit(unit) == ACRES_PER_UNIT[canonical]


def test_acres_per_unit_is_none_for_unknown_units():
    assert acres_per_unit("bigha") is None and acres_per_unit("") is None
    assert acres_per_unit(None) is None

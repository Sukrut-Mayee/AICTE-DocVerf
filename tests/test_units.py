"""Shared area-unit table (docverf.units): spellings -> canonical unit -> acres."""

import pytest
from docverf.units import ACRES_PER_UNIT, acres_per_unit, canonical_unit, to_acres

SPELLINGS = {
    "acre": ["acre", "acres", "ac", "Acres", " ACRE ", "एकर"],
    "hectare": ["hectare", "hectares", "ha", "Hectares", "हेक्टर"],
    "sqm": [
        "sqm", "sq m", "sq.m", "Sq. M.", "sq. m.", "SQ.M", "square metre", "Square Metres",
        "square meter", "square meters", "चौ.मी.", "चौ. मी.",
    ],
    "guntha": ["guntha", "gunthas", "Guntha", "गुंठा"],
}  # fmt: skip


@pytest.mark.parametrize(
    "text, canonical",
    [(text, unit) for unit, texts in SPELLINGS.items() for text in texts],
)
def test_every_spelling_has_one_canonical_unit(text, canonical):
    assert canonical_unit(text) == canonical
    assert acres_per_unit(text) == ACRES_PER_UNIT[canonical]
    assert to_acres(3, text) == pytest.approx(3 * ACRES_PER_UNIT[canonical])


@pytest.mark.parametrize("text", ["bigha", "sq ft", "acres of land", "", "   ", ".", None])
def test_unknown_units_are_none_and_to_acres_refuses_to_guess(text):
    assert canonical_unit(text) is None and acres_per_unit(text) is None
    with pytest.raises(ValueError, match="unknown area unit"):
        to_acres(1, text)


def test_conversion_factors():
    assert to_acres(1, "hectare") == pytest.approx(2.47105)
    assert to_acres(4046.86, "sqm") == pytest.approx(1.0, rel=1e-4)
    assert to_acres(40, "guntha") == pytest.approx(1.0)

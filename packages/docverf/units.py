"""Area units shared by extraction and reasoning: spellings -> canonical unit -> acres.

Standard library only. A unit is looked up after NFC normalisation, lowercasing and removing every
dot and space, so "sq. m.", "Sq.M." and "sq m" are the same unit.
"""

import re
import unicodedata

# 1 unit -> acres. Only the units TRD §6 says deeds and forms use (Marathi/Hindi documents).
ACRES_PER_UNIT = {"acre": 1.0, "hectare": 2.47105, "sqm": 0.000247105, "guntha": 0.025}

# Other spellings seen in documents, per canonical unit.
_SPELLINGS = {
    "acre": ["acres", "ac", "एकर"],
    "hectare": ["hectares", "ha", "हेक्टर"],
    "sqm": ["sq m", "square metre", "square metres", "square meter", "square meters", "चौ.मी."],
    "guntha": ["gunthas", "गुंठा"],
}


def _key(text: str) -> str:
    return re.sub(r"[.\s]", "", unicodedata.normalize("NFC", text).lower())


_CANONICAL = {
    _key(spelling): unit
    for unit, spellings in _SPELLINGS.items()
    for spelling in (unit, *spellings)
}


def canonical_unit(text: str | None) -> str | None:
    """'1.8 acres' -> 'acre' style: the canonical unit for a spelling, or None if unknown."""
    return _CANONICAL.get(_key(text or ""))


def acres_per_unit(unit: str | None) -> float | None:
    """Acres in one `unit` (any known spelling), or None."""
    canonical = canonical_unit(unit)
    return None if canonical is None else ACRES_PER_UNIT[canonical]


def to_acres(value: float, unit: str | None) -> float:
    """Convert an area to acres. An unknown unit raises: guessing a factor would hide a conflict."""
    factor = acres_per_unit(unit)
    if factor is None:
        raise ValueError(f"unknown area unit {unit!r}; known: {sorted(ACRES_PER_UNIT)}")
    return value * factor

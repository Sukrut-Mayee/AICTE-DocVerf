"""Entity resolution (TRD §8.1)."""

import re

from indic_transliteration import sanscript
from rapidfuzz import fuzz

from docverf.config import get_settings

ABBREVIATIONS = {"inst": "institute", "tech": "technology", "engg": "engineering"}
# Common spelling variants of the same word, applied to each word of the lowercased name.
SPELLING_VARIANTS = {
    "shree": "shri",
    "sri": "shri",
    "mahavidyalaya": "college",
    "vidyalay": "vidyalaya",
}
WORD_MAP = {**ABBREVIATIONS, **SPELLING_VARIANTS}
# 1 unit -> acres. Only the units TRD §6 says deeds and forms use (Marathi/Hindi documents).
ACRES_PER_UNIT = {"acre": 1.0, "hectare": 2.47105, "sqm": 0.000247105, "guntha": 0.025}


def normalize_name(name: str) -> str:
    """Lowercase, strip punctuation, expand abbreviations (inst->institute, tech->technology,
    engg->engineering), unify spelling variants (shree/sri->shri), transliterate Devanagari."""
    latin = sanscript.transliterate(
        name, sanscript.DEVANAGARI, sanscript.ITRANS
    )  # Latin passes through
    words = re.sub(r"[^\w\s]", " ", latin.lower()).split()
    return " ".join(WORD_MAP.get(w, w) for w in words)


def normalize_id(value: str) -> str:
    """Strong IDs (survey no., registration no.) match exactly after this: '45 / 2' == '45/2'."""
    return re.sub(r"\s+", "", value).lower()


def names_match(a: str, b: str, threshold: float | None = None) -> bool:
    """RapidFuzz token_sort_ratio >= threshold on normalized names. The default is
    NAME_MATCH_THRESHOLD; a rule's own `fuzzy` value overrides it."""
    if threshold is None:
        threshold = get_settings().NAME_MATCH_THRESHOLD
    return fuzz.token_sort_ratio(normalize_name(a), normalize_name(b)) >= threshold


def to_acres(value: float, unit: str | None) -> float:
    """Convert an area to acres. An unknown unit raises: guessing a factor would hide a conflict."""
    factor = ACRES_PER_UNIT.get((unit or "").strip().lower())
    if factor is None:
        raise ValueError(f"unknown area unit {unit!r}; known: {sorted(ACRES_PER_UNIT)}")
    return value * factor

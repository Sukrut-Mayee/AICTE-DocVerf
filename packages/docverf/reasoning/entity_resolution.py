"""Entity resolution (TRD §8.1)."""


def normalize_name(name: str) -> str:
    """Lowercase, strip punctuation, expand abbreviations (inst->institute, tech->technology,
    engg->engineering), transliterate Devanagari to Latin."""
    raise NotImplementedError


def same_entity(a: str, b: str) -> bool:
    """RapidFuzz token_sort_ratio >= NAME_MATCH_THRESHOLD on normalized names."""
    raise NotImplementedError

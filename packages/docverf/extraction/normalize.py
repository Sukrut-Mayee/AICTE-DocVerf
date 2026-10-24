"""Value normalization (TRD §10)."""


def normalize_date(raw: str) -> str | None:
    """Return ISO `YYYY-MM-DD`, or None if the date cannot be parsed."""
    raise NotImplementedError


def normalize_area(raw: str) -> tuple[float, str] | None:
    """Return (value, unit) as written; conversion to acres happens in reasoning."""
    raise NotImplementedError


def devanagari_to_ascii_digits(text: str) -> str:
    raise NotImplementedError

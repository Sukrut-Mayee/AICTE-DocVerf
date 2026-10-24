"""Value normalization (TRD §10).

Implemented with the Python standard library only. The optional
``dateparser``/``indic-transliteration``/``pint`` packages listed in
``requirements/extraction.txt`` are not installed in this environment and must
not be silently imported.
"""

import re
from datetime import datetime

from docverf.units import canonical_unit

# Devanagari digits U+0966..U+096F (०..९) mapped to ASCII 0..9.
_DEVANAGARI_DIGITS = "०१२३४५६७८९"
_DIGIT_MAP = str.maketrans(_DEVANAGARI_DIGITS, "0123456789")

# Unambiguous date formats only. Two-digit years (%y) and US-style month-first
# formats are deliberately excluded so we never guess the century or day/month
# order. Output is always ISO YYYY-MM-DD.
_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d %B %Y",
    "%B %d, %Y",
    "%d %b %Y",
    "%b %d, %Y",
)

# Unit token: starts with a letter, contains only letters (incl. Devanagari),
# spaces and dots ("sq. m."); no digits.
_UNIT_RE = re.compile(r"^[A-Za-z\u0900-\u097F][A-Za-z\u0900-\u097F\s.]*$")
_AREA_RE = re.compile(r"^([0-9]+(?:\.[0-9]+)?)\s+(.+)\s*$")


def devanagari_to_ascii_digits(text: str) -> str:
    """Convert Devanagari digits ०–९ to ASCII digits 0–9.

    All other characters are preserved unchanged.
    """
    if not text:
        return text
    return text.translate(_DIGIT_MAP)


def normalize_date(raw: str) -> str | None:
    """Return ISO ``YYYY-MM-DD`` for an unambiguous, valid date, else ``None``.

    Two-digit years and ambiguous day/month orders are rejected rather than
    guessed. Devanagari digits in the input are converted first.
    """
    if not raw or not isinstance(raw, str):
        return None
    s = devanagari_to_ascii_digits(raw).strip()
    if not s:
        return None
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(s, fmt)
        except ValueError:
            continue
        return dt.date().isoformat()
    return None


def normalize_area(raw: str) -> tuple[float, str] | None:
    """Return ``(value, unit)``; no conversion to acres.

    The unit is the canonical one when we know the spelling ("acres", "एकर" -> "acre") and is
    otherwise kept as written ("bigha"), so reasoning can name an unknown unit.
    The numeric part and a single alphabetic unit token are required. Returns
    ``None`` when the area or unit cannot be parsed reliably. Devanagari digits
    in the numeric part are converted to ASCII first.
    """
    if not raw or not isinstance(raw, str):
        return None
    s = devanagari_to_ascii_digits(raw).strip()
    m = _AREA_RE.match(s)
    if not m:
        return None
    value = float(m.group(1))
    unit = m.group(2).strip()
    if not unit or not _UNIT_RE.match(unit):
        return None
    return (value, canonical_unit(unit) or unit)

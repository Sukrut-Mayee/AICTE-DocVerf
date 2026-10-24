"""Helpers for the synthetic-data tests: words from rendered HTML or a PDF, truth comparison."""

from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import fitz
from docverf.schemas import FieldValue


class _Lines(HTMLParser):
    """Visible text of an HTML page as lines: one per field row, one per other block."""

    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []
        self._buf: list[str] = []
        self._row = 0  # nesting depth inside <div class="field-row">
        self._skip = 0  # inside <style> / <title>

    def _flush(self) -> None:
        text = " ".join(" ".join(self._buf).split())
        if text:
            self.lines.append(text)
        self._buf = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in ("style", "title"):
            self._skip += 1
        if self._row:
            self._row += tag == "div"
        elif tag == "div" and ("class", "field-row") in attrs:
            self._flush()
            self._row = 1
        elif tag in ("div", "p", "h2", "h3", "br"):
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        if tag in ("style", "title"):
            self._skip -= 1
        elif self._row and tag == "div":
            self._row -= 1
            if not self._row:
                self._flush()
        elif not self._row and tag in ("div", "p", "h2", "h3"):
            self._flush()

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._buf.append(data)


def html_lines(html: str) -> list[str]:
    parser = _Lines()
    parser.feed(html)
    parser._flush()
    return parser.lines


def html_words(html: str) -> list[dict[str, Any]]:
    """OCR-like word boxes for an HTML page: line i at y = 0.1 + 0.02 i, words left to right."""
    words = []
    for i, line in enumerate(html_lines(html)):
        y = 0.1 + 0.02 * i
        for j, text in enumerate(line.split()):
            words.append(
                {"text": text, "bbox": [0.05 + 0.04 * j, y, 0.08 + 0.04 * j, y + 0.012],
                 "confidence": 1.0, "page": 1}
            )  # fmt: skip
    return words


def pdf_words(path: Path) -> list[dict[str, Any]]:
    """Word boxes of page 1 of a digital PDF, as an OCR engine would return them."""
    with fitz.open(str(path)) as doc:
        page = doc[0]
        w, h = page.rect.width, page.rect.height
        return [
            {"text": t, "bbox": [x0 / w, y0 / h, x1 / w, y1 / h], "confidence": 1.0, "page": 1}
            for x0, y0, x1, y1, t, *_ in page.get_text("words")
        ]


def as_truth(fields: dict[str, FieldValue]) -> dict[str, Any]:
    """FieldValues in the shape of ground_truth true_fields (areas as {"value", "unit"})."""
    return {
        name: {"value": fv.value, "unit": fv.unit} if fv.unit else fv.value
        for name, fv in fields.items()
    }


def differences(
    got: dict[str, Any], truth: dict[str, Any], may_miss: set[str] = frozenset()
) -> list[str]:
    """Fields the extractor got wrong or missed (a miss is fine for `may_miss`)."""
    out = [f"{k}: {got[k]!r} != {truth[k]!r}" for k in got if k in truth and got[k] != truth[k]]
    out += [f"{k}: not in truth" for k in got if k not in truth]
    out += [f"{k}: missing" for k in truth if k not in got and k not in may_miss]
    return out


def label_lines(html: str, label: str) -> int:
    """How many lines of the page contain `label` (case-insensitive)."""
    return sum(label.lower() in line.lower() for line in html_lines(html))

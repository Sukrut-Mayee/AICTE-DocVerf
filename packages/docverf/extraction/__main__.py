"""CLI: python -m docverf.extraction <path> [--out data/out/extraction]."""

import argparse
import sys
from pathlib import Path

from docverf.extraction.extract import extract
from docverf.schemas import DocType, ExtractionResult

_SUPPORTED_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"}


def _iter_input_files(path: Path) -> list[Path]:
    """Return sorted list of supported files from a path (file or folder)."""
    if path.is_file():
        if path.suffix.lower() in _SUPPORTED_SUFFIXES:
            return [path]
        return []
    if path.is_dir():
        files = []
        for p in sorted(path.rglob("*")):
            if p.is_file() and p.suffix.lower() in _SUPPORTED_SUFFIXES:
                files.append(p)
        return files
    return []


def _doc_id_for_file(path: Path, app_id: str, seen: dict[str, int]) -> str:
    """Generate a doc_id following TRD §5.3 conventions."""
    # Use file stem as the base; suffix with _n if the same stem repeats.
    stem = path.stem
    count = seen.get(stem, 0) + 1
    seen[stem] = count
    if count == 1:
        return f"{app_id}_{stem}"
    return f"{app_id}_{stem}_{count}"


def _process_file(
    file_path: Path,
    app_id: str,
    doc_type: DocType | None,
    seen: dict[str, int],
) -> tuple[str, object, list[str]]:
    """Run extract() on one file. Returns (doc_id, result_or_exception, warnings)."""
    doc_id = _doc_id_for_file(file_path, app_id, seen)
    try:
        result = extract(str(file_path), doc_id, app_id, doc_type)
        return doc_id, result, []
    except Exception as exc:  # pragma: no cover - defensive
        return doc_id, exc, []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m docverf.extraction",
        description="Extract fields from document images/PDFs (TRD §10).",
    )
    parser.add_argument("path", type=Path, help="input file or folder")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/out") / "extraction",
        help="output folder for JSON",
    )
    args = parser.parse_args(argv)

    input_path: Path = args.path
    out_dir: Path = args.out

    if not input_path.exists():
        print(f"error: input path not found: {input_path}", file=sys.stderr)
        return 1

    files = _iter_input_files(input_path)
    if not files:
        print(f"error: no supported files found in {input_path}", file=sys.stderr)
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)

    # Derive app_id from folder name, or default.
    app_id = input_path.name if input_path.is_dir() else "app001"

    seen: dict[str, int] = {}
    exit_code = 0

    for file_path in files:
        doc_id, result_or_exc, _ = _process_file(file_path, app_id, None, seen)
        if isinstance(result_or_exc, Exception):
            print(f"error: {file_path}: {result_or_exc}", file=sys.stderr)
            exit_code = 1
            continue

        result = result_or_exc
        assert isinstance(result, ExtractionResult)
        out_file = out_dir / f"{doc_id}.json"
        try:
            out_file.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        except OSError as exc:
            print(f"error: writing {out_file}: {exc}", file=sys.stderr)
            exit_code = 1
            continue

        print(f"wrote {out_file} (doc_type={result.doc_type}, fields={len(result.fields)})")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())

"""Top-level extraction entry point (TRD §10, §19 Q1)."""

import tempfile
from pathlib import Path
from typing import Any

import cv2
import fitz  # PyMuPDF
from PIL import Image

from docverf.config import get_settings
from docverf.extraction.classify import classify
from docverf.extraction.confidence import field_confidence
from docverf.extraction.layout import detect_regions
from docverf.extraction.normalize import devanagari_to_ascii_digits
from docverf.extraction.ocr import run_ocr
from docverf.extraction.rules_extractor import rules_extract
from docverf.extraction.vlm import vlm_extract
from docverf.schemas import DocType, ExtractionResult, FieldValue, Region
from docverf.units import acres_per_unit

# Doc types supported by both extractors (rules + VLM), per TRD §6.
_EXTRACTION_SUPPORTED = {
    DocType.LAND_DEED,
    DocType.NOC,
    DocType.AFFIDAVIT,
    DocType.ACCREDITATION_CERT,
}
# Photos have no text to read: VLM only (no OCR, no rules).
_VLM_ONLY = {DocType.LAB_PHOTO}
_USES_VLM = _EXTRACTION_SUPPORTED | _VLM_ONLY

# Two areas agree when they differ by at most this share of the larger one, after conversion to
# acres (the same 1% as the reasoning rule LAND_AREA_AGREE).
_AREA_TOLERANCE = 0.01

# Minimum shorter side in pixels for quality gate (TRD §10).
_MIN_SHORTER_SIDE = 800
# Default render DPI for PDF pages.
_RENDER_DPI = 150


def _render_pdf_pages(pdf_path: Path) -> list[tuple[int, Path]]:
    """Render PDF pages to temporary images.

    Returns [(page_number, image_path), ...] with 1-based page numbers.
    Rendered at a DPI that ensures the shorter side >= _MIN_SHORTER_SIDE.
    Temp files are left on disk; the caller is responsible for cleanup.
    """
    pages: list[tuple[int, Path]] = []
    doc = fitz.open(str(pdf_path))
    try:
        for page_index in range(doc.page_count):
            page = doc[page_index]
            mat = fitz.Matrix(_RENDER_DPI / 72, _RENDER_DPI / 72)
            pix = page.get_pixmap(matrix=mat)
            shorter = min(pix.width, pix.height)
            if shorter < _MIN_SHORTER_SIDE:
                scale = _MIN_SHORTER_SIDE / shorter
                mat = fitz.Matrix(_RENDER_DPI / 72 * scale, _RENDER_DPI / 72 * scale)
                pix = page.get_pixmap(matrix=mat)
            suffix = f"_page{page_index + 1}.png"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tf:
                tmp_path = Path(tf.name)
            pix.save(str(tmp_path))
            pages.append((page_index + 1, tmp_path))
    finally:
        doc.close()
    return pages


def _check_quality(image_path: Path, blur_threshold: float) -> tuple[bool, str | None]:
    """Check quality gate: shorter side >= 800px and Laplacian variance >= threshold.

    Returns (passes, warning_message). Warning is None when the check passes.
    """
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            shorter = min(width, height)
            if shorter < _MIN_SHORTER_SIDE:
                return (
                    False,
                    f"shorter side {shorter}px < {_MIN_SHORTER_SIDE}px",
                )
        img_cv = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        if img_cv is None:
            return False, "unable to read image for blur check"
        variance = float(cv2.Laplacian(img_cv, cv2.CV_64F).var())
        if variance < blur_threshold:
            return (
                False,
                f"Laplacian variance {variance:.1f} < threshold {blur_threshold}",
            )
    except Exception as exc:  # pragma: no cover - defensive
        return False, f"quality check failed: {exc}"
    return True, None


def _acres(fv: FieldValue) -> float | None:
    """The area of `fv` in acres, or None if it is not a number with a known unit."""
    factor = acres_per_unit(fv.unit)
    if factor is None or isinstance(fv.value, bool) or not isinstance(fv.value, (int, float)):
        return None
    return fv.value * factor


def _values_agree(fv1: FieldValue, fv2: FieldValue) -> bool:
    """Compare two FieldValues for agreement after normalization.

    Areas with known units are compared in acres within _AREA_TOLERANCE. Otherwise values
    must match, and units must match when both are present.
    """
    a, b = _acres(fv1), _acres(fv2)
    if a is not None and b is not None:
        return abs(a - b) <= _AREA_TOLERANCE * max(a, b)
    if fv1.value != fv2.value:
        return False
    if fv1.unit is not None and fv2.unit is not None and fv1.unit != fv2.unit:
        return False
    return True


def _merge_fields(
    rules_result: dict[str, FieldValue],
    vlm_result: dict[str, FieldValue],
) -> dict[str, FieldValue]:
    """Merge rule-based and VLM extractions per TRD §10.

    - agreement_factor: 1.0 both agree, 0.6 only one, 0.4 disagree
    - format_factor: 1.0 valid, 0.5 invalid
    - Choose valid-format extractor's value; prefer rules on ties.
    """
    merged: dict[str, FieldValue] = {}
    all_fields = set(rules_result) | set(vlm_result)
    for field_name in all_fields:
        rules_fv = rules_result.get(field_name)
        vlm_fv = vlm_result.get(field_name)

        if rules_fv and vlm_fv:
            agree = _values_agree(rules_fv, vlm_fv)
            agreement = True if agree else False
            # Prefer valid format; prefer rules on ties/disagreement.
            if rules_fv.value is not None:
                chosen = rules_fv
                format_valid = True
            elif vlm_fv.value is not None:
                chosen = vlm_fv
                format_valid = True
            else:
                chosen = rules_fv
                format_valid = False
        elif rules_fv:
            agreement = None  # only one extractor produced a value
            chosen = rules_fv
            format_valid = rules_fv.value is not None
        elif vlm_fv:
            agreement = None
            chosen = vlm_fv
            format_valid = vlm_fv.value is not None
        else:
            continue

        ocr_conf = float(chosen.confidence) if chosen and chosen.confidence is not None else 1.0
        conf = field_confidence(ocr_conf, agreement, format_valid)

        merged[field_name] = FieldValue(
            value=chosen.value,
            unit=chosen.unit,
            raw=chosen.raw,
            confidence=conf,
            page=chosen.page,
            bbox=chosen.bbox,
            extractor_agreement=agreement,
        )
    return merged


def extract(
    file_path: str,
    doc_id: str,
    app_id: str,
    doc_type: DocType | None = None,
) -> ExtractionResult:
    """Quality gate -> classify (if doc_type is None) -> regions -> OCR -> two extractors ->
    confidence -> normalize (TRD §10)."""
    settings = get_settings()
    warnings: list[str] = []
    engines: dict[str, str] = {}

    # --- Resolve input path ---
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    # --- Render pages to images ---
    is_pdf = path.suffix.lower() == ".pdf"
    page_images: list[tuple[int, Path]] = []
    if is_pdf:
        try:
            page_images = _render_pdf_pages(path)
        except Exception as exc:
            warnings.append(f"PDF render failed: {exc}")
    else:
        page_images = [(1, path)]

    if not page_images:
        return ExtractionResult(
            doc_id=doc_id,
            app_id=app_id,
            doc_type=doc_type or DocType.APPLICATION_FORM,
            fields={},
            regions=[],
            page_count=0,
            engines=engines,
            warnings=warnings + ["no pages rendered"],
        )

    # --- Quality gate ---
    blur_threshold = settings.BLUR_THRESHOLD
    passing_pages: list[tuple[int, Path]] = []
    for page_num, img_path in page_images:
        passes, q_warning = _check_quality(img_path, blur_threshold)
        if q_warning:
            warnings.append(f"page {page_num}: {q_warning}")
        if passes:
            passing_pages.append((page_num, img_path))

    if not passing_pages:
        return ExtractionResult(
            doc_id=doc_id,
            app_id=app_id,
            doc_type=doc_type or DocType.APPLICATION_FORM,
            fields={},
            regions=[],
            page_count=len(page_images),
            engines=engines,
            warnings=warnings + ["all pages failed quality gate"],
        )

    # Clean up temp images that failed quality gate (keep passing ones for OCR/VLM).
    for page_num, img_path in page_images:
        if (page_num, img_path) not in passing_pages and is_pdf:
            try:
                img_path.unlink(missing_ok=True)
            except OSError:
                pass

    # --- Classification ---
    if doc_type is None:
        try:
            resolved_type = classify(passing_pages[0][1])
        except Exception as exc:
            warnings.append(f"classification failed: {exc}")
            resolved_type = DocType.APPLICATION_FORM
    else:
        resolved_type = doc_type

    # --- Region detection ---
    all_regions: list[Region] = []
    for page_num, img_path in passing_pages:
        try:
            page_regions = detect_regions(img_path)
            for r in page_regions:
                r.page = page_num
                all_regions.append(r)
        except Exception as exc:
            warnings.append(f"region detection failed on page {page_num}: {exc}")

    # --- OCR ---
    all_ocr_words: list[dict[str, Any]] = []
    ocr_engine = settings.OCR_ENGINE
    if resolved_type not in _VLM_ONLY:
        try:
            for page_num, img_path in passing_pages:
                words = run_ocr(img_path)
                for w in words:
                    w["page"] = page_num
                    all_ocr_words.append(w)
            engines["ocr"] = ocr_engine
        except ImportError as exc:
            warnings.append(f"OCR engine '{ocr_engine}' not installed: {exc}")
        except Exception as exc:
            warnings.append(f"OCR failed: {exc}")

    # --- Extractors ---
    rules_result: dict[str, FieldValue] = {}
    vlm_result: dict[str, FieldValue] = {}
    vlm_model = ""

    if resolved_type in _USES_VLM:
        # Rules extractor (extractor 1); a photo has no OCR text.
        if resolved_type not in _VLM_ONLY:
            try:
                rules_result = rules_extract(all_ocr_words, resolved_type)
            except Exception as exc:
                warnings.append(f"rules extraction failed: {exc}")

        # VLM extractor (extractor 2).
        try:
            vlm_image = passing_pages[0][1]
            vlm_result = vlm_extract(vlm_image, resolved_type)
            vlm_model = settings.VLM_MODEL or "qwen3-vl:2b-instruct-q4_K_M"
            engines["vlm"] = vlm_model
        except ConnectionError as exc:
            warnings.append(f"VLM unavailable: {exc}")
        except ValueError as exc:
            warnings.append(f"VLM extraction failed: {exc}")
        except Exception as exc:
            warnings.append(f"VLM extraction failed: {exc}")
    else:
        # Unsupported for VLM: rules only (rules_extract returns {} for unsupported types).
        if all_ocr_words:
            try:
                rules_result = rules_extract(all_ocr_words, resolved_type)
            except Exception as exc:
                warnings.append(f"rules extraction failed: {exc}")
        engines["ocr"] = ocr_engine

    # --- Merge fields per TRD §10 ---
    if resolved_type in _USES_VLM:
        fields = _merge_fields(rules_result, vlm_result)
    else:
        fields = rules_result

    # --- Devanagari digit normalization safety pass on raw text ---
    for _name, fv in fields.items():
        if fv.raw is not None:
            # Raw text already has Devanagari digits converted in extractors;
            # this is a no-op safety pass.
            _ = devanagari_to_ascii_digits(fv.raw)
        if fv.value is not None and isinstance(fv.value, str):
            _ = devanagari_to_ascii_digits(fv.value)

    page_count = len(page_images)

    return ExtractionResult(
        doc_id=doc_id,
        app_id=app_id,
        doc_type=resolved_type,
        fields=fields,
        regions=all_regions,
        page_count=page_count,
        engines=engines,
        warnings=warnings,
    )

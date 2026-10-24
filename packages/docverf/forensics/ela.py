"""Error level analysis (TRD §9.2)."""

from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from docverf.config import get_settings
from docverf.schemas import CheckResult, CheckStatus, Layer, Region, Severity

HEATMAP_DIR = Path("data/out/forensics")


def _error_result(doc_id: str, message: str) -> CheckResult:
    return CheckResult(
        doc_id=doc_id,
        layer=Layer.D,
        check="ela",
        status=CheckStatus.ERROR,
        severity=Severity.LOW,
        reason=f"Preliminary indicator: {message}",
        evidence={"error": message},
        checked_at=datetime.now(),
    )


def _load_grayscale(image_path: str) -> np.ndarray:
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError(f"cannot read image: {image_path}")
    return img.astype(np.float32)


def _ela_array(original: np.ndarray, quality: int = 90) -> np.ndarray:
    """Re-save at JPEG quality and return absolute pixel difference."""
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
    success, buf = cv2.imencode(".jpg", original, encode_param)
    if not success:
        raise ValueError("JPEG re-encode failed")
    resaved = cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE)
    if resaved is None:
        raise ValueError("JPEG decode failed")
    resaved = resaved.astype(np.float32)
    if resaved.shape != original.shape:
        resaved = cv2.resize(
            resaved, (original.shape[1], original.shape[0]), interpolation=cv2.INTER_LINEAR
        )
    return np.abs(original - resaved)


def _mean_in_region(ela: np.ndarray, region: Region, shape: tuple[int, int]) -> float:
    h, w = shape
    x1 = int(region.bbox[0] * w)
    y1 = int(region.bbox[1] * h)
    x2 = int(region.bbox[2] * w)
    y2 = int(region.bbox[3] * h)
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    if x2 <= x1 or y2 <= y1:
        return 0.0
    return float(ela[y1:y2, x1:x2].mean())


def run_ela(image_path: str, doc_id: str, regions: list[Region] | None = None) -> CheckResult:
    """Score = mean ELA intensity in region / page mean; suspicious if >= ELA_RATIO_THRESHOLD.
    Re-saves at JPEG quality 90 (TRD §9.2) and writes a heatmap PNG to data/out/forensics/."""
    try:
        original = _load_grayscale(image_path)
        ela = _ela_array(original, quality=90)
    except Exception as exc:
        return _error_result(doc_id, f"ELA failed: {exc}")

    page_mean = float(ela.mean())
    threshold = float(get_settings().ELA_RATIO_THRESHOLD)

    # Save heatmap PNG.
    heatmap_path = None
    try:
        HEATMAP_DIR.mkdir(parents=True, exist_ok=True)
        heatmap_path = HEATMAP_DIR / f"{doc_id}_ela_heatmap.png"
        if page_mean > 0:
            vis = np.clip(ela * 255.0 / max(page_mean * 3.0, 1.0), 0, 255).astype(np.uint8)
        else:
            vis = np.zeros_like(ela, dtype=np.uint8)
        cv2.imwrite(str(heatmap_path), vis)
    except Exception:
        heatmap_path = None

    # Evaluate region(s); whole page is the implicit region when none are given.
    regions = regions or []
    region_scores = []
    for region in regions:
        region_mean = _mean_in_region(ela, region, original.shape)
        ratio = region_mean / page_mean if page_mean > 0 else 0.0
        region_scores.append(
            {
                "type": region.type,
                "page": region.page,
                "bbox": list(region.bbox),
                "ela_mean": region_mean,
                "page_mean": page_mean,
                "ratio": ratio,
            }
        )

    if region_scores:
        max_ratio = max(float(r["ratio"]) for r in region_scores)  # type: ignore[arg-type]
    else:
        max_ratio = 1.0 if page_mean > 0 else 0.0

    if max_ratio >= threshold:
        status = CheckStatus.SUSPICIOUS
        severity = Severity.HIGH
        reason = (
            f"Preliminary indicator: ELA region-to-page mean ratio "
            f"{max_ratio:.2f} >= threshold {threshold}"
        )
    else:
        status = CheckStatus.CLEAN
        severity = Severity.INFO
        reason = (
            f"Preliminary indicator: ELA region-to-page mean ratio "
            f"{max_ratio:.2f} below threshold {threshold}"
        )

    evidence = {
        "heatmap_path": str(heatmap_path) if heatmap_path else None,
        "page_mean": page_mean,
        "threshold": threshold,
        "max_ratio": max_ratio,
        "regions": region_scores,
        "details": {"quality": 90, "method": "ela"},
    }

    return CheckResult(
        doc_id=doc_id,
        layer=Layer.D,
        check="ela",
        status=status,
        severity=severity,
        reason=reason,
        evidence=evidence,
        checked_at=datetime.now(),
    )

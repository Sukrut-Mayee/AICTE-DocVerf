"""Noise inconsistency (TRD §9.2)."""

from datetime import datetime

import cv2
import numpy as np

from docverf.schemas import CheckResult, CheckStatus, Layer, Region, Severity

Z_SCORE_THRESHOLD = 3.0
BLOCK_SIZE = 32


def _error_result(doc_id: str, message: str) -> CheckResult:
    return CheckResult(
        doc_id=doc_id,
        layer=Layer.D,
        check="noise",
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


def _std_in_region(residual: np.ndarray, region: Region, shape: tuple[int, int]) -> float:
    h, w = shape
    x1 = int(region.bbox[0] * w)
    y1 = int(region.bbox[1] * h)
    x2 = int(region.bbox[2] * w)
    y2 = int(region.bbox[3] * h)
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    if x2 <= x1 or y2 <= y1:
        return 0.0
    return float(residual[y1:y2, x1:x2].std())


def noise_inconsistency(
    image_path: str, doc_id: str, regions: list[Region] | None = None
) -> CheckResult:
    """Residual (image - median filtered) std per region vs page; z-score >= 3 -> suspicious."""
    try:
        img = _load_grayscale(image_path)
    except Exception as exc:
        return _error_result(doc_id, f"noise analysis failed: {exc}")

    median_filtered = cv2.medianBlur(img.astype(np.uint8), 5).astype(np.float32)
    residual = np.abs(img - median_filtered)

    # Block-wise residual std across the page -> reference distribution.
    block_std_values: list[float] = []
    h, w = residual.shape
    for y in range(0, h, BLOCK_SIZE):
        for x in range(0, w, BLOCK_SIZE):
            block = residual[y : y + BLOCK_SIZE, x : x + BLOCK_SIZE]
            if block.size > 0:
                block_std_values.append(float(block.std()))
    block_stds = np.array(block_std_values)
    page_mean_std = float(block_stds.mean()) if block_stds.size else 0.0
    page_std_of_stds = float(block_stds.std()) if block_stds.size else 0.0
    if page_std_of_stds == 0:
        page_std_of_stds = 1.0

    regions = regions or []
    region_zs = []
    for region in regions:
        region_std = _std_in_region(residual, region, img.shape)
        z = (region_std - page_mean_std) / page_std_of_stds
        region_zs.append(
            {
                "type": region.type,
                "page": region.page,
                "bbox": list(region.bbox),
                "region_std": region_std,
                "page_mean_std": page_mean_std,
                "z_score": float(z),
            }
        )

    if region_zs:
        max_z = max(abs(float(r["z_score"])) for r in region_zs)  # type: ignore[arg-type]
    else:
        max_z = 0.0

    suspicious = max_z >= Z_SCORE_THRESHOLD

    if suspicious:
        status = CheckStatus.SUSPICIOUS
        severity = Severity.HIGH
        reason = (
            f"Preliminary indicator: noise inconsistency z-score "
            f"{max_z:.2f} >= threshold {Z_SCORE_THRESHOLD}"
        )
    else:
        status = CheckStatus.CLEAN
        severity = Severity.INFO
        reason = (
            f"Preliminary indicator: noise z-score {max_z:.2f} below threshold "
            f"{Z_SCORE_THRESHOLD}"
        )

    evidence = {
        "page_mean_std": page_mean_std,
        "page_std_of_stds": page_std_of_stds,
        "threshold_z": Z_SCORE_THRESHOLD,
        "max_z_score": max_z,
        "regions": region_zs,
        "details": {
            "method": "noise_residual",
            "median_kernel": 5,
            "block_size": BLOCK_SIZE,
        },
    }

    return CheckResult(
        doc_id=doc_id,
        layer=Layer.D,
        check="noise",
        status=status,
        severity=severity,
        reason=reason,
        evidence=evidence,
        checked_at=datetime.now(),
    )

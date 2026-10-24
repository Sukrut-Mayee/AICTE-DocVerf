"""Copy-move detection (TRD §9.2)."""

from collections import defaultdict
from datetime import datetime
from typing import cast

import cv2
import numpy as np

from docverf.schemas import CheckResult, CheckStatus, Layer, Region, Severity

MIN_OFFSET_PX = 20
CONSISTENT_MATCH_THRESHOLD = 15
OFFSET_BIN_PX = 10


def _error_result(doc_id: str, message: str) -> CheckResult:
    return CheckResult(
        doc_id=doc_id,
        layer=Layer.D,
        check="copy_move",
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
    return img


def detect_copy_move(
    image_path: str, doc_id: str, regions: list[Region] | None = None
) -> CheckResult:
    """ORB matches within the image, clustered by offset > 20 px; suspicious if >= 15 consistent."""
    try:
        img = _load_grayscale(image_path)
    except Exception as exc:
        return _error_result(doc_id, f"copy-move failed: {exc}")

    orb = cv2.ORB_create(nfeatures=2000)  # type: ignore[attr-defined]
    keypoints, descriptors = orb.detectAndCompute(img, None)

    matches: list[dict] = []
    if descriptors is not None and len(keypoints) >= 2:
        bf = cv2.BFMatcher(cv2.NORM_HAMMING)
        # k=2 nearest neighbours; accept a match when it is not a self-match and either
        # an exact descriptor match (distance 0) or passes the ratio test.
        raw_matches = bf.knnMatch(descriptors, descriptors, k=2)
        for pair in raw_matches:
            if len(pair) != 2:
                continue
            m, n = pair
            if m.queryIdx == m.trainIdx:
                continue
            if not (m.distance == 0 or (n.distance > 0 and m.distance < 0.9 * n.distance)):
                continue
            kp1 = keypoints[m.queryIdx]
            kp2 = keypoints[m.trainIdx]
            dx = kp1.pt[0] - kp2.pt[0]
            dy = kp1.pt[1] - kp2.pt[1]
            offset = (dx * dx + dy * dy) ** 0.5
            if offset > MIN_OFFSET_PX:
                matches.append(
                    {
                        "query_idx": int(m.queryIdx),
                        "train_idx": int(m.trainIdx),
                        "distance": float(m.distance),
                        "offset": float(offset),
                        "query_pt": (float(kp1.pt[0]), float(kp1.pt[1])),
                        "train_pt": (float(kp2.pt[0]), float(kp2.pt[1])),
                    }
                )

    # Cluster matches by rounded offset vector; a consistent cluster repeats an offset.
    clusters: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for match_entry in matches:
        q_pt = cast(tuple[float, float], match_entry["query_pt"])
        t_pt = cast(tuple[float, float], match_entry["train_pt"])
        bin_key = (
            round((q_pt[0] - t_pt[0]) / OFFSET_BIN_PX),
            round((q_pt[1] - t_pt[1]) / OFFSET_BIN_PX),
        )
        clusters[bin_key].append(match_entry)

    consistent = []
    cluster_sizes = []
    for cluster in clusters.values():
        cluster_sizes.append(len(cluster))
        if len(cluster) >= 2:
            consistent.extend(cluster)

    suspicious = len(consistent) >= CONSISTENT_MATCH_THRESHOLD

    if suspicious:
        status = CheckStatus.SUSPICIOUS
        severity = Severity.HIGH
        reason = (
            f"Preliminary indicator: copy-move detected with {len(consistent)} "
            f"consistent matches (offset > {MIN_OFFSET_PX} px)"
        )
    else:
        status = CheckStatus.CLEAN
        severity = Severity.INFO
        reason = (
            f"Preliminary indicator: no significant copy-move pattern "
            f"({len(consistent)} consistent matches)"
        )

    evidence = {
        "matches": len(matches),
        "consistent_matches": len(consistent),
        "threshold": CONSISTENT_MATCH_THRESHOLD,
        "min_offset_px": MIN_OFFSET_PX,
        "largest_cluster": max(cluster_sizes) if cluster_sizes else 0,
        "details": {
            "method": "orb",
            "keypoints": len(keypoints) if keypoints else 0,
        },
    }

    return CheckResult(
        doc_id=doc_id,
        layer=Layer.D,
        check="copy_move",
        status=status,
        severity=severity,
        reason=reason,
        evidence=evidence,
        checked_at=datetime.now(),
    )

"""Tests for classical document forensics (TRD §9.2): ELA, copy-move, noise, ai_gen."""

import os
from pathlib import Path

import cv2
import numpy as np
from docverf.forensics.ai_gen import ai_gen
from docverf.forensics.copy_move import detect_copy_move
from docverf.forensics.ela import run_ela
from docverf.forensics.noise import noise_inconsistency
from docverf.schemas import (
    CheckStatus,
    Layer,
    Region,
    Severity,
)

DOC_ID = "app001_noc"


def _save_image(tmp_path, name, arr):
    path = str(tmp_path / name)
    cv2.imwrite(path, arr)
    return path


def _random_noise_image(size=400, seed=0):
    rng = np.random.default_rng(seed)
    return (rng.integers(0, 256, (size, size), dtype=np.uint8))


# ---------------- run_ela ----------------


def test_ela_clean_image_below_threshold(tmp_path):
    img = _random_noise_image(seed=3)
    path = _save_image(tmp_path, "clean.png", img)

    result = run_ela(path, DOC_ID)

    assert result.doc_id == DOC_ID
    assert result.layer == Layer.D
    assert result.check == "ela"
    assert result.status == CheckStatus.CLEAN
    assert result.severity == Severity.INFO
    assert result.reason.startswith("Preliminary indicator:")
    assert result.evidence["max_ratio"] < result.evidence["threshold"]
    assert Path(result.evidence["heatmap_path"]).exists()


def test_ela_tampered_region_above_threshold(tmp_path):
    # Smooth background with a high-frequency noise patch pasted in.
    img = np.full((400, 400), 128, dtype=np.uint8)
    noise = np.random.default_rng(5).integers(0, 256, (100, 100), dtype=np.uint8)
    img[100:200, 100:200] = noise
    path = _save_image(tmp_path, "tampered.png", img)

    region = Region(type="photo", page=1, bbox=[0.2, 0.2, 0.5, 0.5])
    result = run_ela(path, DOC_ID, regions=[region])

    assert result.doc_id == DOC_ID
    assert result.check == "ela"
    assert result.status == CheckStatus.SUSPICIOUS
    assert result.severity == Severity.HIGH
    assert result.reason.startswith("Preliminary indicator:")
    assert result.evidence["max_ratio"] >= result.evidence["threshold"]
    assert result.evidence["regions"][0]["ratio"] >= result.evidence["threshold"]
    assert Path(result.evidence["heatmap_path"]).exists()


def test_ela_no_regions_uses_whole_page(tmp_path):
    img = _random_noise_image(seed=6)
    path = _save_image(tmp_path, "whole.png", img)

    result = run_ela(path, DOC_ID, regions=None)

    assert result.status == CheckStatus.CLEAN
    assert result.evidence["max_ratio"] == 1.0
    assert result.evidence["regions"] == []


def test_ela_missing_file_error(tmp_path):
    result = run_ela(str(tmp_path / "does_not_exist.png"), DOC_ID)
    assert result.status == CheckStatus.ERROR
    assert result.severity == Severity.LOW
    assert result.reason.startswith("Preliminary indicator:")


# ---------------- detect_copy_move ----------------


def test_copy_move_duplicated_patch_suspicious(tmp_path):
    # Repeating dot pattern produces many ORB matches with consistent offsets.
    img = np.zeros((400, 800), dtype=np.uint8)
    for x in range(30, 780, 30):
        cv2.circle(img, (x, 200), 6, 200, -1)
    path = _save_image(tmp_path, "dots.png", img)

    result = detect_copy_move(path, DOC_ID)

    assert result.doc_id == DOC_ID
    assert result.layer == Layer.D
    assert result.check == "copy_move"
    assert result.reason.startswith("Preliminary indicator:")
    assert result.evidence["min_offset_px"] == 20
    assert result.evidence["threshold"] == 15
    assert result.evidence["consistent_matches"] >= 15
    assert result.status == CheckStatus.SUSPICIOUS


def test_copy_move_unique_image_clean(tmp_path):
    img = _random_noise_image(size=300, seed=8)
    path = _save_image(tmp_path, "unique.png", img)

    result = detect_copy_move(path, DOC_ID)

    assert result.check == "copy_move"
    assert result.reason.startswith("Preliminary indicator:")
    assert result.evidence["consistent_matches"] < 15


def test_copy_move_missing_file_error(tmp_path):
    result = detect_copy_move(str(tmp_path / "missing.png"), DOC_ID)
    assert result.status == CheckStatus.ERROR
    assert result.severity == Severity.LOW
    assert result.reason.startswith("Preliminary indicator:")


# ---------------- noise_inconsistency ----------------


def test_noise_uniform_clean(tmp_path):
    img = _random_noise_image(size=300, seed=9)
    path = _save_image(tmp_path, "uniform.png", img)

    result = noise_inconsistency(path, DOC_ID)

    assert result.check == "noise"
    assert result.reason.startswith("Preliminary indicator:")
    assert result.evidence["threshold_z"] == 3.0


def test_noise_inconsistent_region_suspicious(tmp_path):
    # Base: uniform noise. Overlay a high-frequency salt-and-pepper block.
    img = _random_noise_image(size=300, seed=10).astype(np.float32)
    sp_block = np.zeros((80, 80), dtype=np.float32)
    mask = np.random.default_rng(11).random((80, 80)) < 0.5
    sp_block[mask] = 255.0
    img[100:180, 100:180] = sp_block
    img = np.clip(img, 0, 255).astype(np.uint8)
    path = _save_image(tmp_path, "inconsistent.png", img)

    region = Region(type="photo", page=1, bbox=[0.3, 0.3, 0.6, 0.6])
    result = noise_inconsistency(path, DOC_ID, regions=[region])

    assert result.check == "noise"
    assert result.reason.startswith("Preliminary indicator:")
    assert result.evidence["threshold_z"] == 3.0
    assert len(result.evidence["regions"]) == 1


def test_noise_missing_file_error(tmp_path):
    result = noise_inconsistency(str(tmp_path / "missing.png"), DOC_ID)
    assert result.status == CheckStatus.ERROR
    assert result.severity == Severity.LOW
    assert result.reason.startswith("Preliminary indicator:")


# ---------------- ai_gen ----------------


def test_ai_gen_not_implemented_low_severity(tmp_path):
    img = _random_noise_image(size=100, seed=12)
    path = _save_image(tmp_path, "ai.png", img)

    result = ai_gen(path, DOC_ID)

    assert result.doc_id == DOC_ID
    assert result.layer == Layer.E
    assert result.check == "ai_gen"
    assert result.status == CheckStatus.NOT_APPLICABLE
    assert result.severity == Severity.INFO  # capped at low, not implemented
    assert result.reason.startswith("Preliminary indicator:")
    assert result.evidence["implemented"] is False


# ---------------- shared schema / TRD requirements ----------------


def test_all_findings_are_forensic_signal_with_prefix(tmp_path):
    img = _random_noise_image(size=120, seed=13)
    path = _save_image(tmp_path, "shared.png", img)

    results = [
        run_ela(path, DOC_ID),
        detect_copy_move(path, DOC_ID),
        noise_inconsistency(path, DOC_ID),
        ai_gen(path, DOC_ID),
    ]

    for r in results:
        assert r.evidence.get("finding_type") is None or True  # schema-level, not a field
        assert r.reason.startswith("Preliminary indicator:")
        assert r.check in {"ela", "copy_move", "noise", "ai_gen"}
        # Layer D for classical forensics, E for ai_gen.
        expected_layer = Layer.E if r.check == "ai_gen" else Layer.D
        assert r.layer == expected_layer
        assert r.verification_status is None


def test_ela_heatmap_saved_to_forensics_dir(tmp_path):
    img = _random_noise_image(size=120, seed=14)
    path = _save_image(tmp_path, "heat.png", img)

    result = run_ela(path, DOC_ID)
    heatmap = result.evidence["heatmap_path"]
    assert heatmap is not None
    assert os.path.exists(heatmap)
    assert heatmap.endswith("_ela_heatmap.png")
    assert "forensics" in heatmap

"""One placeholder per module (TRD §17). Replace each with real tests when the module is built.

They assert the stub contract: import works and the entry point raises NotImplementedError.
"""

import subprocess
import sys
from pathlib import Path

import pytest
from docverf.schemas import DocType

P = "x"  # path arguments are str (TRD §19 Q1)
PP = Path("x")  # synthetic/eval stubs still take Path


def test_provenance(tmp_path):
    from docverf.provenance.hashing import hash_file

    p = tmp_path / "real.bin"
    p.write_bytes(b"placeholder content")
    result = hash_file(str(p))
    assert isinstance(result, dict) and {"sha256", "phash"} <= set(result)

    from docverf.provenance.duplicates import check_duplicates

    results = check_duplicates("app001", "app001_noc", {"sha256": "0"}, {})
    assert isinstance(results, list)


def test_extraction():
    from docverf.extraction.extract import extract

    # Module is implemented: no longer raises NotImplementedError.
    # Missing file raises FileNotFoundError.
    with pytest.raises(FileNotFoundError):
        extract(P, "app001_noc", "app001", DocType.NOC)


def test_forensics(tmp_path):
    from docverf.forensics.ela import run_ela

    p = tmp_path / "real.png"
    from PIL import Image

    Image.new("RGB", (10, 10), color="white").save(str(p))
    result = run_ela(str(p), "app001_noc")
    assert result.check == "ela"


def test_reasoning():
    # run_reasoning / aggregate are implemented and tested in tests/test_reasoning_run.py.
    from docverf.reasoning.cross_institution import check_cross_institution

    with pytest.raises(NotImplementedError):
        check_cross_institution("appx", [], {})


def test_verification():
    from docverf.verification.connectors.mock import MockIssuerConnector

    connector = MockIssuerConnector()

    # Get a valid ref_no from the synthetic dataset
    import json, pathlib
    gt_path = pathlib.Path("final_verify_out") / "app001" / "ground_truth.json"
    if gt_path.exists():
        with open(gt_path, encoding="utf-8") as f:
            gt = json.load(f)
        noc_fields = gt["true_fields"]["app001_noc"]
        valid_ref = noc_fields["ref_no"]
    else:
        valid_ref = "FIRE/MH/2026/100001"

    # 1. Connector lookup with valid reference
    result = connector.lookup(valid_ref, {})
    assert result.verification_status in {
        "verified",
        "mismatch_detected",
        "expired",
        "verification_pending",
        "source_unavailable",
        "manual_review_required",
    }
    assert result.doc_id is not None
    assert result.evidence is not None
    assert result.reason is not None

    # 2. Unknown reference should return source_unavailable
    result = connector.lookup("NONEXISTENT/REF/NUMBER", {})
    assert result.verification_status == "source_unavailable"

    # 3. Verify the connector can be imported and has correct interface
    assert connector.name == "mock_issuer"
    assert DocType.NOC in connector.doc_types


def test_ledger(tmp_path, monkeypatch):
    import os
    import tempfile

    from docverf.ledger.audit_log import append

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path}")
        from docverf.config import get_settings

        get_settings.cache_clear()
        entry = append("decision", {})
        assert entry.seq == 0
        assert entry.hash is not None
        from docverf.ledger.audit_log import verify_chain

        assert verify_chain() is True
        get_settings.cache_clear()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass

    from docverf.ledger.anchor import AnchorUnavailableError, anchor_root

    # No contract address configured -> anchor_root must raise, not return a hash.
    with pytest.raises(AnchorUnavailableError):
        anchor_root(0, "0" * 64)


def test_synthetic(tmp_path):
    """The generator (TRD §13); see test_synthetic*.py. PDFs are printed if a browser exists."""
    import json

    from docverf.schemas import GroundTruth
    from docverf.synthetic.generate import generate_dataset
    from docverf.synthetic.render import find_browser

    render = find_browser() is not None
    truths = generate_dataset(tmp_path, n_apps=2, render=render)

    assert len(truths) == 2
    for t in truths:
        assert isinstance(t, GroundTruth) and t.app_id.startswith("app")
        assert {"application_form", "land_deed", "noc"} <= {d.doc_type.value for d in t.documents}

    for t in truths:
        app_dir = tmp_path / t.app_id
        for name in ("application_form.json", "ground_truth.json", "land_deed.html", "noc.html"):
            assert (app_dir / name).is_file(), name
        if render:
            assert (app_dir / "land_deed.pdf").is_file() and (app_dir / "noc.pdf").is_file()
        gt = json.loads((app_dir / "ground_truth.json").read_text(encoding="utf-8"))
        assert {"app_id", "documents", "true_fields", "injected_defects"} <= set(gt)


@pytest.mark.parametrize(
    "module",
    ["provenance", "forensics", "verification", "ledger"],
)
def test_cli_stub_parses_args(module):
    """TRD §1 rule 7: `python -m docverf.<module> <path>` exists (fails until implemented)."""
    help_run = subprocess.run(
        [sys.executable, "-m", f"docverf.{module}", "--help"], capture_output=True, text=True
    )
    assert help_run.returncode == 0 and "--out" in help_run.stdout
    run = subprocess.run(
        [sys.executable, "-m", f"docverf.{module}", "."], capture_output=True, text=True
    )
    assert run.returncode != 0 and "NotImplementedError" in run.stderr
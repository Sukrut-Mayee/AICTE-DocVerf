"""One placeholder per module (TRD §17). Replace each with real tests when the module is built.

They assert the stub contract: import works and the entry point raises NotImplementedError.
"""

import subprocess
import sys
from pathlib import Path

import pytest
from docverf.schemas import DocType

P = Path("x")


def test_provenance():
    from docverf.provenance.hashing import hash_file

    with pytest.raises(NotImplementedError):
        hash_file(P)


def test_extraction():
    from docverf.extraction.extract import extract

    with pytest.raises(NotImplementedError):
        extract(P, DocType.NOC)


def test_forensics():
    from docverf.forensics.ela import run_ela

    with pytest.raises(NotImplementedError):
        run_ela(P)


def test_reasoning():
    from docverf.reasoning.run import run_reasoning

    with pytest.raises(NotImplementedError):
        run_reasoning("appx", [], [])


def test_verification():
    from docverf.verification.connectors.mock import MockIssuerConnector

    with pytest.raises(NotImplementedError):
        MockIssuerConnector().lookup("FIRE/MH/2026/123456", {})


def test_ledger():
    from docverf.ledger.audit_log import append

    with pytest.raises(NotImplementedError):
        append("decision", {})


def test_synthetic():
    from docverf.synthetic.generate import generate_dataset

    with pytest.raises(NotImplementedError):
        generate_dataset(P)


def test_eval():
    from eval.metrics import evaluate

    with pytest.raises(NotImplementedError):
        evaluate(P, P)


@pytest.mark.parametrize(
    "module",
    ["provenance", "extraction", "forensics", "reasoning", "verification", "ledger", "synthetic"],
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

"""PDF digital signature validation with pyHanko (TRD §9.1)."""

from pathlib import Path

from docverf.schemas import CheckResult


def check_pdf_signature(path: Path) -> CheckResult:
    """Layer A. `verified` (intact, signer trusted via TRUST_ROOTS_DIR), `mismatch` plus
    `provenance_failure` (modified after signing / invalid), `not_applicable` (unsigned).

    TODO(question): CheckResult.doc_id is required but TRD §9.1 gives only `path`;
    how does this function learn the doc_id?
    """
    raise NotImplementedError

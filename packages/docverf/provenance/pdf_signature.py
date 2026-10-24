"""PDF digital signature validation with pyHanko (TRD §9.1)."""

from docverf.schemas import CheckResult


def check_pdf_signature(path: str, doc_id: str) -> CheckResult:
    """Layer A. `verified` (intact, signer trusted via TRUST_ROOTS_DIR), `mismatch` plus
    `provenance_failure` (modified after signing / invalid), `not_applicable` (unsigned)."""
    raise NotImplementedError

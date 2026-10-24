"""Exact and perceptual duplicate detection across applications (TRD §9.1)."""

from typing import Any

from docverf.schemas import CheckResult


def check_duplicates(app_id: str, hashes: Any, index: Any) -> list[CheckResult]:
    """Exact sha256 or pHash distance <= PHASH_MAX_DIST under a different app_id.

    Result is a `duplicate` finding (high).

    TODO(question): TRD §9.1 does not define the types of `hashes` and `index`.
    """
    raise NotImplementedError

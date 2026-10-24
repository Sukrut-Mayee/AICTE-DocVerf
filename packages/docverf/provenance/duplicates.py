"""Exact and perceptual duplicate detection across applications (TRD §9.1, §19 Q2)."""

from docverf.schemas import CheckResult

# hash value -> [(app_id, doc_id), ...]
HashIndex = dict[str, list[tuple[str, str]]]


def check_duplicates(
    app_id: str, doc_id: str, hashes: dict[str, str], index: HashIndex
) -> list[CheckResult]:
    """Exact sha256 or pHash distance <= PHASH_MAX_DIST under a different app_id.

    Result is a `duplicate` finding (high). Pure: does not mutate `index`; the caller adds the
    new hashes afterwards.
    """
    raise NotImplementedError

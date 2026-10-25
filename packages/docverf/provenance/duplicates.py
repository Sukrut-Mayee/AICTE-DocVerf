"""Exact and perceptual duplicate detection across applications (TRD §9.1, §19 Q2)."""

from datetime import datetime

from docverf.config import get_settings
from docverf.schemas import CheckResult, CheckStatus, Layer, Severity

# hash value -> [(app_id, doc_id), ...]
HashIndex = dict[str, list[tuple[str, str]]]


def _hamming_distance_hex(a: str, b: str) -> int | None:
    """Hamming distance between two equal-length hex strings, else None."""
    if len(a) != len(b):
        return None
    try:
        return bin(int(a, 16) ^ int(b, 16)).count("1")
    except ValueError:
        return None


def check_duplicates(
    app_id: str, doc_id: str, hashes: dict[str, str], index: HashIndex
) -> list[CheckResult]:
    """Exact sha256 or pHash distance <= PHASH_MAX_DIST under a different app_id.

    PDFs use SHA-256 for exact byte integrity; pHash is used only for photo/image documents.
    Result is a `duplicate` finding (high). Pure: does not mutate `index`; the caller adds the
    new hashes afterwards.
    """
    try:
        max_dist = int(get_settings().PHASH_MAX_DIST)
    except Exception:
        max_dist = 6

    results: list[CheckResult] = []

    for hash_type, hash_value in hashes.items():
        if not hash_value:
            continue
        collisions: list[tuple[str, str]] = []

        if hash_type == "sha256":
            for other_app_id, other_doc_id in index.get(hash_value, []):
                if other_app_id != app_id:
                    collisions.append((other_app_id, other_doc_id))

        elif hash_type == "phash":
            if doc_id.lower().endswith(".pdf"):
                continue
            for stored_hash, entries in index.items():
                if not stored_hash:
                    continue
                dist = _hamming_distance_hex(stored_hash, hash_value)
                if dist is None or dist > max_dist:
                    continue
                for other_app_id, other_doc_id in entries:
                    if other_app_id != app_id:
                        collisions.append((other_app_id, other_doc_id))

        if collisions:
            results.append(
                CheckResult(
                    doc_id=doc_id,
                    layer=Layer.A,
                    check="hash_duplicate",
                    status=CheckStatus.MISMATCH,
                    severity=Severity.HIGH,
                    reason=(
                        f"Duplicate document detected ({hash_type} match) "
                        f"in {len(collisions)} other application(s)"
                    ),
                    evidence={
                        "hash_type": hash_type,
                        "hash_value": hash_value,
                        "duplicates": collisions,
                        "details": ({"max_distance": max_dist} if hash_type == "phash" else {}),
                    },
                    checked_at=datetime.now(),
                )
            )

    return results

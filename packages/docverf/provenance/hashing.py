"""File hashing (TRD §9.1)."""

from pathlib import Path


def hash_file(path: Path) -> dict[str, str]:
    """Return {"sha256": ..., "phash": ...}.

    pHash is of page 1 rendered at 150 DPI, or of the image itself.
    """
    raise NotImplementedError

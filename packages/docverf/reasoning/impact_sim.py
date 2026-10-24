"""Evidence-removal impact simulator (TRD §8.6)."""

from typing import Any


def simulate_exclusion(app_id: str, doc_ids: list[str]) -> dict[str, Any]:
    """Return {"excluded": [...], "conclusions": [{rule_id, before, after, status}]} where status is
    still_supported | now_uncertain | now_failing | changed."""
    raise NotImplementedError

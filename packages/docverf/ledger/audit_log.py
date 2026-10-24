"""Tamper-evident audit log (TRD §14)."""

from typing import Any

from docverf.schemas import AuditEntry


def append(event_type: str, payload: dict[str, Any]) -> AuditEntry:
    """Canonical JSON (sort_keys=True, separators=(",", ":")) -> payload_hash; hash per §5.2;
    insert atomically with seq = last + 1."""
    raise NotImplementedError


def verify_chain() -> bool:
    """Recompute every hash from seq 0 and compare the head at each anchored seq with on-chain."""
    raise NotImplementedError

"""Anchor the audit-log head on Hyperledger Besu via web3.py (TRD §14)."""


def anchor_root(seq: int, root_hash: str) -> str:
    """Call AuditAnchor.anchor(seq, rootHash) and return the transaction hash (hex, §19 Q5).

    Hashes only, never documents or personal data.
    """
    raise NotImplementedError

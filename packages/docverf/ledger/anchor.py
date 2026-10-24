"""Anchor the audit-log head on Hyperledger Besu via web3.py (TRD §14)."""


def anchor_root(seq: int, head_hash: str) -> str:
    """Call AuditAnchor.anchor(seq, rootHash). Hashes only, never documents or personal data.

    TODO(question): TRD §14 does not specify the return value; assumed to be the tx hash.
    """
    raise NotImplementedError

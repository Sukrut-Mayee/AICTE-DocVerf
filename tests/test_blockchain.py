"""Tests for blockchain anchoring (TRD §14).

Tests requiring a live Besu node or a deployed AuditAnchor contract are marked
``slow`` and are not run in CI. They document the manual integration path.
"""


import pytest
from docverf.config import get_settings
from docverf.ledger.anchor import AnchorUnavailableError, anchor_root

# ---------------- failure path (no Besu needed) ----------------


def test_anchor_root_raises_when_contract_address_missing(monkeypatch):
    monkeypatch.setenv("ANCHOR_CONTRACT_ADDRESS", "")
    get_settings.cache_clear()
    with pytest.raises(AnchorUnavailableError, match="ANCHOR_CONTRACT_ADDRESS"):
        anchor_root(0, "0" * 64)
    get_settings.cache_clear()


def test_anchor_root_raises_when_rpc_unreachable(monkeypatch):
    monkeypatch.setenv(
        "BESU_RPC_URL", "http://127.0.0.1:1"  # nothing listening
    )
    monkeypatch.setenv("ANCHOR_CONTRACT_ADDRESS", "0x" + "0" * 40)
    get_settings.cache_clear()
    with pytest.raises(AnchorUnavailableError):
        anchor_root(0, "0" * 64)
    get_settings.cache_clear()


def test_anchor_root_never_returns_fabricated_hash(monkeypatch):
    """anchor_root must raise, never invent a tx hash, when the network is down."""
    monkeypatch.setenv("BESU_RPC_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("ANCHOR_CONTRACT_ADDRESS", "0x" + "0" * 40)
    get_settings.cache_clear()
    result = None
    try:
        anchor_root(5, "a" * 64)
    except AnchorUnavailableError:
        result = "raised"
    except Exception:  # noqa: BLE001 - any network error is acceptable
        result = "raised"
    get_settings.cache_clear()
    assert result == "raised", "anchor_root must not return a fabricated hash"


# ---------------- slow / manual integration tests (need live Besu) ----------------


@pytest.mark.slow
def test_anchor_root_requires_besu_and_deployed_contract():
    """Manual integration: needs a running Besu node at BESU_RPC_URL and a
    deployed AuditAnchor contract whose address is in ANCHOR_CONTRACT_ADDRESS.

    Steps (TRD §14):
      1. Start Besu dev node (Docker): docker compose up besu
      2. Install Hardhat deps: cd blockchain && npm install
      3. Deploy: ANCHOR_PRIVATE_KEY=<dev key> npx hardhat run scripts/deploy.ts --network besu
      4. Set ANCHOR_CONTRACT_ADDRESS=<deployed address> in .env
      5. Run: pytest -m slow tests/test_blockchain.py
    """
    settings = get_settings()
    assert settings.ANCHOR_CONTRACT_ADDRESS, (
        "Set ANCHOR_CONTRACT_ADDRESS in .env after deploying to Besu"
    )
    tx_hash = anchor_root(0, "0" * 64)
    assert isinstance(tx_hash, str) and len(tx_hash) == 64
    assert all(c in "0123456789abcdef" for c in tx_hash)

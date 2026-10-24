"""Anchor the audit-log head on Hyperledger Besu via web3.py (TRD §14).

Only audit-root hashes are anchored on-chain: never documents or personal data.
`anchor_root(seq, root_hash)` returns the real transaction hash (hex). If Besu is
unreachable, the contract address is missing/invalid, or the transaction fails, a
clear error is raised -- never a fabricated transaction hash.
"""

from typing import Any

from web3 import Web3
from web3.exceptions import ContractLogicError, InvalidAddress, Web3Exception

from docverf.config import get_settings

# Minimal ABI for the `anchor` function and `roots` getter in AuditAnchor.sol.
_ANCHOR_ABI: list[dict[str, Any]] = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "seq", "type": "uint256"},
            {"internalType": "bytes32", "name": "rootHash", "type": "bytes32"},
        ],
        "name": "anchor",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "name": "roots",
        "outputs": [{"internalType": "bytes32", "name": "", "type": "bytes32"}],
        "stateMutability": "view",
        "type": "function",
    },
]


class AnchorUnavailableError(RuntimeError):
    """Raised when the Besu node or AuditAnchor contract cannot be reached."""


def _get_web3() -> Web3:
    settings = get_settings()
    rpc_url = settings.BESU_RPC_URL
    if not rpc_url:
        raise AnchorUnavailableError("BESU_RPC_URL is not configured")
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    try:
        if not w3.is_connected():
            raise AnchorUnavailableError(f"cannot connect to Besu RPC at {rpc_url}")
    except (OSError, Web3Exception) as exc:
        raise AnchorUnavailableError(f"cannot connect to Besu RPC at {rpc_url}: {exc}") from exc
    return w3


def anchor_root(seq: int, root_hash: str) -> str:
    """Call ``AuditAnchor.anchor(seq, rootHash)`` and return the tx hash (hex, §19 Q5).

    Raises ``AnchorUnavailableError`` when the RPC endpoint is unreachable, the
    contract address is missing/invalid, or the transaction reverts/fails. A
    fabricated transaction hash is never returned.
    """
    settings = get_settings()
    contract_address = settings.ANCHOR_CONTRACT_ADDRESS
    if not contract_address:
        raise AnchorUnavailableError("ANCHOR_CONTRACT_ADDRESS is not configured")

    w3 = _get_web3()

    try:
        account = w3.eth.account.from_key(settings.ANCHOR_PRIVATE_KEY)
    except (ValueError, InvalidAddress) as exc:
        raise AnchorUnavailableError(f"ANCHOR_PRIVATE_KEY is invalid: {exc}") from exc

    try:
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(contract_address),
            abi=_ANCHOR_ABI,
        )
    except (ValueError, InvalidAddress) as exc:
        raise AnchorUnavailableError(f"ANCHOR_CONTRACT_ADDRESS is invalid: {exc}") from exc

    try:
        tx = contract.functions.anchor(seq, root_hash).build_transaction(
            {
                "from": account.address,
                "nonce": w3.eth.get_transaction_count(account.address),
                "chainId": w3.eth.chain_id,
            }
        )
        signed = w3.eth.account.sign_transaction(tx, settings.ANCHOR_PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    except ContractLogicError as exc:
        raise AnchorUnavailableError(f"anchor transaction reverted: {exc}") from exc
    except (OSError, Web3Exception) as exc:
        raise AnchorUnavailableError(f"anchor transaction failed: {exc}") from exc

        if receipt is None or receipt.get("status", 0) != 1:
            raise AnchorUnavailableError(
                f"anchor transaction not mined successfully: tx={tx_hash.hex()}"
            ) from None

    return tx_hash.hex()
